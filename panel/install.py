#!/usr/bin/env python3
import grp
import json
import os
import re
import secrets
import stat
import subprocess
import tempfile
from pathlib import Path

app_src = Path('/tmp/proxy-panel-app.py')
launcher_src = Path('/tmp/mtproxy-launcher.py')
mtproxy_unit_src = Path(__file__).with_name('mtproxy.service')
if not app_src.is_file() or not launcher_src.is_file() or not mtproxy_unit_src.is_file():
    raise SystemExit('panel source files missing')

panel_dir = Path('/opt/tproxy-panel')
config_dir = Path('/etc/tproxy-panel')
panel_dir.mkdir(parents=True, exist_ok=True)
config_dir.mkdir(parents=True, exist_ok=True)

def install_file(source, dest, mode, uid=0, gid=0):
    data = source.read_bytes()
    temp = dest.with_name(dest.name + '.new')
    temp.write_bytes(data)
    os.chown(temp, uid, gid)
    os.chmod(temp, mode)
    os.replace(temp, dest)

install_file(app_src, panel_dir/'app.py', 0o644)
install_file(launcher_src, Path('/usr/local/sbin/mtproxy-panel-launcher'), 0o750)

config_path = Path('/etc/tproxy-server/config.json')
profile_path = Path('/etc/tproxy-server/profiles.json')
config = json.loads(config_path.read_text())
existing = json.loads(profile_path.read_text()).get('profiles', [])
if not existing:
    raise SystemExit('there must be an active profile before installing the panel')
state_path = config_dir/'proxies.json'
if state_path.exists():
    state = json.loads(state_path.read_text())
else:
    state = {
        'hostname': config['public_hostname'],
        'base_path': config.get('base_path', ''),
        'proxies': [
            {'name': p['name'], 'secret': p['secret'], 'backend': p['backend'],
             'mtproxy_port': int(p['backend'].rsplit(':', 1)[1]),
             'carrier_mode': p.get('carrier_mode', 'https'), 'enabled': True}
            for p in existing
        ],
    }


def atomic_write(path, content, mode, uid, gid):
    fd, temporary = tempfile.mkstemp(prefix=path.name+'.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
        os.chown(temporary, uid, gid)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


atomic_write(state_path, json.dumps(state, separators=(',', ':')).encode()+b'\n', 0o600, 0, 0)

# The launcher reads the active credential set from the root-only manager state.
# Keep the service environment limited to MTProxy's non-secret runtime options.
env_path = Path('/etc/mtproxy/mtproxy.env')
env_info = env_path.stat()
env_lines = []
for line in env_path.read_text().splitlines():
    key = line.split('=', 1)[0] if '=' in line else ''
    if key not in ('MTPROXY_SECRET', 'MTPROXY_EXTRA_SECRET', 'MTPROXY_SECRET_ARGS'):
        env_lines.append(line)
new_env = ('\n'.join(env_lines).rstrip() + '\n').encode()
atomic_write(env_path, new_env, stat.S_IMODE(env_info.st_mode), env_info.st_uid, env_info.st_gid)

unit_path = Path('/etc/systemd/system/mtproxy.service')
install_file(mtproxy_unit_src, unit_path, 0o644)

panel_env = config_dir/'panel.env'
if panel_env.exists():
    password = re.search(r'(?m)^PANEL_PASSWORD=(.+)$', panel_env.read_text())
    if not password:
        raise SystemExit('existing panel.env has no PANEL_PASSWORD')
    panel_password = password.group(1)
else:
    panel_password = secrets.token_urlsafe(24)
    atomic_write(panel_env, ('PANEL_PASSWORD='+panel_password+'\n').encode(), 0o600, 0, 0)

unit_text = '''[Unit]
Description=Private WEB proxy management panel
After=network.target mtproxy.service tproxy-server.service
Wants=network.target

[Service]
Type=simple
User=root
Group=root
EnvironmentFile=/etc/tproxy-panel/panel.env
ExecStart=/usr/bin/python3 /opt/tproxy-panel/app.py
Restart=on-failure
RestartSec=2s
UMask=0077
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
LockPersonality=yes
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
ReadWritePaths=/etc/tproxy-panel /etc/tproxy-server /etc/mtproxy /run/systemd/private

[Install]
WantedBy=multi-user.target
'''
atomic_write(Path('/etc/systemd/system/webproxy-panel.service'), unit_text.encode(), 0o644, 0, 0)

result = subprocess.run(['systemctl', 'daemon-reload'], capture_output=True, text=True)
if result.returncode:
    raise SystemExit(result.stderr)
for unit_name in ('mtproxy', 'tproxy-server'):
    result = subprocess.run(['systemctl', 'restart', unit_name], capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise SystemExit(unit_name + ' restart failed: ' + result.stderr)
result = subprocess.run(['systemctl', 'enable', '--now', 'webproxy-panel.service'], capture_output=True, text=True)
if result.returncode:
    raise SystemExit(result.stderr)

print('panel_password=' + panel_password)
print('panel_url=http://127.0.0.1:8765')
print('profile_count=' + str(len(state['proxies'])))
