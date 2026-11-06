#!/usr/bin/env python3
import json
import os
import re
import shlex
import signal
import subprocess
import time
from pathlib import Path

STATE = Path('/etc/tproxy-panel/proxies.json')
BINARY = '/opt/MTProxy/objs/bin/mtproto-proxy'
children = {}
stopping = False

def stop_child(entry):
    process = entry['process']
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)

def stop(_signum, _frame):
    global stopping
    stopping = True

def start_profile(profile):
    secret = profile.get('secret', '')
    port = profile.get('mtproxy_port')
    if not re.fullmatch(r'(?:[0-9a-f]{32}|dd[0-9a-f]{32})', secret):
        raise ValueError('invalid secret in proxy registry')
    if not isinstance(port, int) or not 2398 <= port <= 2429:
        raise ValueError('invalid backend port in proxy registry')
    backend = profile.get('backend')
    if backend != f'127.0.0.1:{port}':
        raise ValueError('backend and MTProxy port do not match')
    args = [BINARY, '-u', 'mtproxy', '--disable-tcp',
            '-H', str(port), '-S', secret]
    args.extend(shlex.split(os.environ.get('MTPROXY_NAT_ARGS', '')))
    args.extend(['--aes-pwd', '/etc/mtproxy/proxy-secret',
                 '/etc/mtproxy/proxy-multi.conf',
                 '-M', os.environ.get('MTPROXY_WORKERS', '1'),
                 '-C', os.environ.get('MTPROXY_MAX_CONNECTIONS', '4096')])
    return {'signature': (secret, port), 'process': subprocess.Popen(args)}

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
while not stopping:
    try:
        state = json.loads(STATE.read_text())
        desired = {p['mtproxy_port']: p for p in state['proxies'] if p.get('enabled')}
        for port, entry in list(children.items()):
            profile = desired.get(port)
            signature = (profile.get('secret'), port) if profile else None
            if signature != entry['signature'] or entry['process'].poll() is not None:
                stop_child(entry)
                children.pop(port, None)
        for port, profile in desired.items():
            if port not in children:
                children[port] = start_profile(profile)
    except Exception as exc:
        print(f'mtproxy profile reconcile error: {exc}', flush=True)
    time.sleep(0.5)
for entry in list(children.values()):
    stop_child(entry)
