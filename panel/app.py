#!/usr/bin/env python3
import base64
import http.cookies
import json
import os
import re
import secrets
import socket
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

STATE_PATH = Path('/etc/tproxy-panel/proxies.json')
PROFILE_PATH = Path('/etc/tproxy-server/profiles.json')
SESSION_TTL = 8 * 60 * 60
SESSIONS = {}
LOGIN_FAILURES = {}
LOCK = threading.RLock()
PASSWORD = os.environ.get('PANEL_PASSWORD', '')
FONT_PATH = Path('/opt/tproxy-panel/Vazirmatn.ttf')

PAGE = r'''<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>مدیریت پروکسی WEB</title><style>
@font-face{font-family:Vazirmatn;src:url('/font.ttf') format('truetype');font-weight:100 900;font-display:swap}:root{color-scheme:dark;--bg:#0c1117;--panel:#131b24;--panel2:#18232e;--line:#263541;--text:#e7edf1;--muted:#91a1ad;--accent:#57d1b1;--danger:#ff7f86;--blue:#83b7ff}*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 80% -10%,#173139 0,transparent 36%),var(--bg);color:var(--text);font:15px/1.7 Vazirmatn,Tahoma,"Segoe UI",sans-serif}.wrap{width:min(980px,calc(100% - 32px));margin:42px auto 64px}.top{display:flex;align-items:center;justify-content:space-between;margin-bottom:26px}.brand{display:flex;gap:14px;align-items:center}.mark{width:44px;height:44px;border-radius:14px;background:linear-gradient(145deg,#65dfbd,#287e79);display:grid;place-items:center;color:#071b19;font-weight:bold;font-size:20px}.brand h1{font-size:20px;margin:0}.brand p{color:var(--muted);margin:2px 0 0;font-size:13px}.toolbar{display:flex;gap:8px}.button{border:1px solid var(--line);background:var(--panel2);color:var(--text);padding:9px 13px;border-radius:10px;cursor:pointer;font:inherit;transition:.15s}.button:hover{border-color:#507265;transform:translateY(-1px)}.button.primary{background:var(--accent);color:#06231d;border-color:var(--accent);font-weight:700}.button.danger{color:var(--danger);border-color:#653a40}.button:disabled{opacity:.5;cursor:wait;transform:none}.summary{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px}.pill{background:#111a22;border:1px solid var(--line);color:var(--muted);border-radius:999px;padding:6px 11px;font-size:13px}.pill b{color:var(--text);margin-inline-start:5px}.list{display:grid;gap:13px}.card{border:1px solid var(--line);border-radius:16px;background:linear-gradient(145deg,rgba(24,35,46,.96),rgba(17,25,34,.96));padding:20px;box-shadow:0 14px 40px #0002}.cardhead{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}.titleline{display:flex;align-items:center;gap:10px}.titleline h2{font-size:18px;margin:0}.badge{font-size:12px;padding:3px 9px;border-radius:99px;background:#12382f;color:var(--accent);border:1px solid #245d50}.badge.off{background:#2a3036;color:#aab4bc;border-color:#3b454e}.host{direction:ltr;text-align:left;color:#a9bac6;font:13px ui-monospace,Consolas,monospace;overflow-wrap:anywhere;margin:10px 0 14px}.secretrow{display:flex;align-items:center;gap:9px;flex-wrap:wrap;padding:11px 12px;background:#0c131a;border:1px solid #202c37;border-radius:10px}.secretlabel{color:var(--muted);font-size:12px}.secret{direction:ltr;font:14px ui-monospace,Consolas,monospace;letter-spacing:.02em;color:#eaf4f3;user-select:all}.cardactions{display:flex;gap:8px;flex-wrap:wrap;margin-top:15px}.hint{color:var(--muted);font-size:13px;margin:16px 0 0}.toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%);background:#e5fff7;color:#10221d;border-radius:10px;padding:10px 16px;box-shadow:0 8px 30px #0005;opacity:0;pointer-events:none;transition:.2s;z-index:5}.toast.show{opacity:1}.empty{border:1px dashed var(--line);border-radius:14px;padding:34px;text-align:center;color:var(--muted)}.login{max-width:420px;margin:12vh auto;padding:26px;border:1px solid var(--line);border-radius:18px;background:var(--panel)}.login h2{margin:0 0 8px}.login p{color:var(--muted);margin:0 0 18px}.login input{width:100%;padding:12px;border-radius:10px;border:1px solid var(--line);background:#0b1117;color:var(--text);font:inherit;direction:ltr}.login .button{width:100%;margin-top:12px}.err{color:var(--danger);min-height:24px;margin-top:10px}@media(max-width:600px){.wrap{margin-top:24px}.top{align-items:flex-start}.card{padding:16px}.cardhead{align-items:center}.toolbar .button{padding:8px 10px}}
</style></head><body><div id="app"></div><div class="toast" id="toast"></div><script>
let csrf='';let proxies=[];const root=document.getElementById('app');const toastEl=document.getElementById('toast');let toastTimer;
function toast(s){toastEl.textContent=s;toastEl.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>toastEl.classList.remove('show'),2400)}
async function api(url,method='GET',body){const headers={'Content-Type':'application/json'};if(csrf)headers['X-CSRF-Token']=csrf;const r=await fetch(url,{method,headers,body:body?JSON.stringify(body):undefined,credentials:'same-origin',cache:'no-store'});let d={};try{d=await r.json()}catch{}if(!r.ok)throw Error(d.error||'درخواست انجام نشد');return d}
function button(label,cls,fn){const b=document.createElement('button');b.className='button '+(cls||'');b.textContent=label;b.onclick=fn;return b}
function renderLogin(message=''){root.innerHTML='';const box=document.createElement('section');box.className='login';box.innerHTML='<div class="brand"><div class="mark">W</div><div><h1>مدیریت پروکسی WEB</h1><p>ورود امن از طریق تونل SSH</p></div></div><div style="height:22px"></div><h2>ورود مدیر</h2><p>رمز مدیریتی را وارد کن.</p><form id="form"><input id="pass" type="password" autocomplete="current-password" placeholder="رمز پنل" required><button class="button primary" type="submit">ورود</button><div class="err" id="err"></div></form>';root.append(box);box.querySelector('#form').onsubmit=async e=>{e.preventDefault();const err=box.querySelector('#err');err.textContent='';try{const d=await api('/api/login','POST',{password:box.querySelector('#pass').value});csrf=d.csrf;await load()}catch(x){err.textContent=x.message}};if(message)box.querySelector('#err').textContent=message}
function render(){root.innerHTML='';const wrap=document.createElement('main');wrap.className='wrap';const top=document.createElement('header');top.className='top';top.innerHTML='<div class="brand"><div class="mark">W</div><div><h1>مدیریت پروکسی WEB</h1><p id="subtitle"></p></div></div>';const toolbar=document.createElement('div');toolbar.className='toolbar';toolbar.append(button('افزودن پروکسی','primary',()=>showAdd()));toolbar.append(button('به‌روزرسانی','',()=>load().catch(e=>toast(e.message))));const logout=button('خروج','',async()=>{try{await api('/api/logout','POST',{});csrf='';renderLogin()}catch(e){toast(e.message)}});toolbar.append(logout);top.append(toolbar);wrap.append(top);
const summary=document.createElement('div');summary.className='summary';const on=proxies.filter(p=>p.enabled).length;summary.innerHTML='<span class="pill">پروفایل‌ها <b>'+proxies.length+'</b></span><span class="pill">فعال <b>'+on+'</b></span><span class="pill">هر پروفایل؛ اتصال جدید جایگزین قبلی <b>۱ نشست همزمان</b></span>';wrap.append(summary);const list=document.createElement('section');list.className='list';if(!proxies.length){const e=document.createElement('div');e.className='empty';e.textContent='پروفایلی وجود ندارد.';list.append(e)}
for(const p of proxies){const card=document.createElement('article');card.className='card';const head=document.createElement('div');head.className='cardhead';const title=document.createElement('div');const line=document.createElement('div');line.className='titleline';const h=document.createElement('h2');h.textContent=p.name;const badge=document.createElement('span');badge.className='badge'+(p.enabled?'':' off');badge.textContent=p.enabled?'فعال':'خاموش';const online=document.createElement('span');online.className='badge'+(p.enabled&&p.online?'':' off');online.textContent=!p.enabled?'—':(p.online?'متصل':'آفلاین');line.append(h,badge,online);title.append(line);const host=document.createElement('div');host.className='host';host.textContent=p.server;title.append(host);head.append(title);card.append(head);
const sr=document.createElement('div');sr.className='secretrow';const sl=document.createElement('span');sl.className='secretlabel';sl.textContent='Secret دستی';const sv=document.createElement('code');sv.className='secret';sv.textContent=p.manual_secret;sr.append(sl,sv);card.append(sr);
const actions=document.createElement('div');actions.className='cardactions';const copyLink=button('کپی لینک تلگرام','primary',async()=>copy(p.share_link,'لینک اتصال کپی شد'));const copyManual=button('کپی مشخصات دستی','',async()=>copy('Server: '+p.server+'\nSecret: '+p.manual_secret,'مشخصات دستی کپی شد'));const rename=button('تغییر نام','',async()=>{const n=prompt('نام جدید پروکسی',p.name);if(n&&n.trim()!==p.name)await renameProxy(p.name,n.trim())});const toggle=button(p.enabled?'خاموش‌کردن':'روشن‌کردن','',async()=>mutate(p.name,'toggle'));const del=button('حذف','danger',async()=>{if(confirm('پروفایل «'+p.name+'» برای همیشه حذف شود؟'))await mutate(p.name,'delete')});actions.append(copyLink,copyManual,rename,toggle,del);card.append(actions);list.append(card)}wrap.append(list);const hint=document.createElement('p');hint.className='hint';hint.textContent='خاموش‌کردن یا حذف یک پروفایل، فقط همان secret را از دسترس خارج می‌کند. نشست‌های فعال هنگام اعمال تغییر بسته می‌شوند.';wrap.append(hint);root.append(wrap);}
async function showAdd(){const name=prompt('نام دلخواه برای پروکسی جدید');if(!name||!name.trim())return;try{await api('/api/proxies','POST',{name:name.trim()});await load();toast('پروکسی جدید ساخته شد')}catch(e){toast(e.message)}}
async function renameProxy(oldName,newName){try{await api('/api/proxies/rename','POST',{old_name:oldName,new_name:newName});await load();toast('نام پروکسی تغییر کرد')}catch(e){toast(e.message)}}
async function copy(s,msg){try{await navigator.clipboard.writeText(s);toast(msg)}catch{const t=document.createElement('textarea');t.value=s;document.body.append(t);t.select();document.execCommand('copy');t.remove();toast(msg)}}
async function load(){const d=await api('/api/proxies');csrf=d.csrf;proxies=d.proxies;render()}
async function mutate(name,action){try{const buttons=[...document.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);await api('/api/proxies/'+encodeURIComponent(name)+'/'+action,'POST',{});await load();toast(action==='delete'?'پروفایل حذف شد':'وضعیت پروفایل تغییر کرد')}catch(e){toast(e.message);buttonsState()}function buttonsState(){document.querySelectorAll('button').forEach(b=>b.disabled=false)}}
async function init(){try{const d=await api('/api/me');csrf=d.csrf;await load();setInterval(()=>load().catch(()=>{}),10000)}catch{renderLogin()}}init();
</script></body></html>'''


def atomic_write(path, data, mode, group=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        os.chown(tmp, 0, group if group is not None else 0)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def valid_name(name):
    return 1 <= len(name.encode('utf-8')) <= 64 and '/' not in name and '\\' not in name and not any(ord(c) < 32 for c in name)

def read_state():
    return json.loads(STATE_PATH.read_text())


def active_profiles(state):
    return [p for p in state['proxies'] if p['enabled']]


def render_profiles(state):
    profiles = []
    for p in active_profiles(state):
        profiles.append({
            'name': p['name'], 'secret': p['secret'], 'backend': p['backend'],
            'carrier_mode': p.get('carrier_mode', 'https'),
            'limits': {'max_sessions': 1},
        })
    return json.dumps({'profiles': profiles}, separators=(',', ':')).encode() + b'\n'


def reload_relay(profiles):
    request = urllib.request.Request(
        'http://127.0.0.1:8081/reload', data=profiles,
        headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError('relay rejected profile update')


def wait_for_backends(state, timeout=20):
    deadline = time.monotonic() + timeout
    for profile in active_profiles(state):
        host, port = profile['backend'].rsplit(':', 1)
        while time.monotonic() < deadline:
            try:
                with socket.create_connection((host, int(port)), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.25)
        else:
            raise RuntimeError('MTProxy backend did not become ready')


def commit_state(new_state):
    with LOCK:
        old_state = STATE_PATH.read_bytes()
        old_profiles = PROFILE_PATH.read_bytes()
        active = active_profiles(new_state)
        if not active:
            raise ValueError('حداقل یک پروفایل باید فعال بماند.')
        if len(new_state['proxies']) > 32:
            raise ValueError('حداکثر ۳۲ پروفایل پشتیبانی می‌شود.')
        seen = set()
        ports = set()
        for p in new_state['proxies']:
            if not valid_name(p['name']):
                raise ValueError('نام پروفایل نامعتبر است.')
            if p['name'] in seen:
                raise ValueError('نام پروفایل تکراری است.')
            seen.add(p['name'])
            port = p.get('mtproxy_port')
            if not isinstance(port, int) or not 2398 <= port <= 2429 or port in ports:
                raise ValueError('پورت داخلی پروکسی نامعتبر یا تکراری است.')
            ports.add(port)
            if p.get('backend') != f'127.0.0.1:{port}':
                raise ValueError('نشانی backend با پورت داخلی پروکسی هماهنگ نیست.')
            if not re.fullmatch(r'(?:[0-9a-f]{32}|dd[0-9a-f]{32})', p['secret']):
                raise ValueError('قالب secret نامعتبر است.')
        rendered_profiles = render_profiles(new_state)
        needs_restart = rendered_profiles != old_profiles
        atomic_write(STATE_PATH, json.dumps(new_state, separators=(',', ':')).encode()+b'\n', 0o600)
        atomic_write(PROFILE_PATH, rendered_profiles, 0o400, group=__import__('grp').getgrnam('tproxy').gr_gid)
        if needs_restart:
            try:
                wait_for_backends(new_state)
                reload_relay(rendered_profiles)
            except Exception as exc:
                atomic_write(STATE_PATH, old_state, 0o600)
                atomic_write(PROFILE_PATH, old_profiles, 0o400, group=__import__('grp').getgrnam('tproxy').gr_gid)
                try:
                    old_state_data = json.loads(old_state)
                    wait_for_backends(old_state_data)
                    reload_relay(old_profiles)
                except Exception:
                    pass
                raise RuntimeError('تغییر اعمال نشد؛ تنظیم قبلی بازگردانده شد.') from exc


def share_link(state, proxy):
    address = state['hostname'] + ('/' + state['base_path'] if state.get('base_path') else '')
    raw = bytes.fromhex(proxy['secret'].removeprefix('dd'))
    if proxy['secret'].startswith('dd'):
        raw = b'\xdd' + raw
    if state.get('base_path'):
        raw = b'\x70' + raw
        secret = base64.urlsafe_b64encode(raw).rstrip(b'=').decode()
    else:
        secret = proxy['secret']
    return 'tg://webproxy?server=' + quote(address, safe='') + '&secret=' + secret


def live_sessions():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8081/profile-sessions', timeout=2) as response:
            return json.loads(response.read())
    except Exception:
        return {}

def public_proxies(state, sessions):
    out = []
    for p in state['proxies']:
        address = state['hostname'] + ('/' + state['base_path'] if state.get('base_path') else '')
        out.append({'name': p['name'], 'enabled': p['enabled'], 'server': address,
                    'manual_secret': p['secret'], 'share_link': share_link(state, p),
                    'online': bool(p['enabled'] and sessions.get(p['name'], 0) > 0)})
    return out


def purge_sessions():
    now = time.time()
    for token, entry in list(SESSIONS.items()):
        if entry['expires'] < now:
            SESSIONS.pop(token, None)


class Handler(BaseHTTPRequestHandler):
    server_version = 'WebProxyPanel/1.0'

    def log_message(self, fmt, *args):
        # Never place credentials, URLs, or request bodies in logs.
        return

    def send_json(self, status, data, cookie=None):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'DENY')
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get('Content-Length', '0'))
        if length < 0 or length > 4096:
            raise ValueError('درخواست بیش از حد بزرگ است.')
        return json.loads(self.rfile.read(length) or b'{}')

    def session(self):
        cookie = http.cookies.SimpleCookie(self.headers.get('Cookie', ''))
        morsel = cookie.get('panel_session')
        token = morsel.value if morsel else ''
        with LOCK:
            purge_sessions()
            return token, SESSIONS.get(token)

    def authorized(self, require_csrf=False):
        token, entry = self.session()
        if not entry:
            self.send_json(401, {'error': 'ابتدا وارد پنل شو.'})
            return None
        if require_csrf and not secrets.compare_digest(entry['csrf'], self.headers.get('X-CSRF-Token', '')):
            self.send_json(403, {'error': 'درخواست معتبر نیست؛ صفحه را تازه‌سازی کن.'})
            return None
        return entry

    def do_GET(self):
        if self.headers.get('Host') not in ('127.0.0.1:8765', 'localhost:8765'):
            self.send_json(421, {'error': 'هاست نامعتبر است.'})
            return
        if self.path == '/font.ttf':
            try:
                body = FONT_PATH.read_bytes()
            except OSError:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'font/ttf')
            self.send_header('Cache-Control', 'public, max-age=86400')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == '/':
            body = PAGE.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; font-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Frame-Options', 'DENY')
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == '/api/me':
            entry = self.authorized()
            if entry:
                self.send_json(200, {'csrf': entry['csrf']})
            return
        if self.path == '/api/proxies':
            entry = self.authorized()
            if entry:
                with LOCK:
                    state = read_state()
                self.send_json(200, {'csrf': entry['csrf'], 'proxies': public_proxies(state, live_sessions())})
            return
        self.send_json(404, {'error': 'یافت نشد.'})

    def do_POST(self):
        try:
            if self.headers.get('Host') not in ('127.0.0.1:8765', 'localhost:8765'):
                self.send_json(421, {'error': 'هاست نامعتبر است.'})
                return
            origin = self.headers.get('Origin')
            if origin and origin not in ('http://127.0.0.1:8765', 'http://localhost:8765'):
                self.send_json(403, {'error': 'مبدأ درخواست مجاز نیست.'})
                return
            if self.path == '/api/login':
                data = self.read_json()
                if not secrets.compare_digest(str(data.get('password', '')), PASSWORD):
                    now = time.time()
                    attempts = [t for t in LOGIN_FAILURES.get(self.client_address[0], []) if now - t < 600]
                    attempts.append(now)
                    LOGIN_FAILURES[self.client_address[0]] = attempts
                    if len(attempts) >= 5:
                        self.send_json(429, {'error': 'تلاش زیاد بود؛ ده دقیقه بعد دوباره امتحان کن.'})
                        return
                    self.send_json(401, {'error': 'رمز پنل درست نیست.'})
                    return
                LOGIN_FAILURES.pop(self.client_address[0], None)
                token = secrets.token_urlsafe(32)
                csrf = secrets.token_urlsafe(24)
                with LOCK:
                    purge_sessions()
                    SESSIONS[token] = {'csrf': csrf, 'expires': time.time() + SESSION_TTL}
                self.send_json(200, {'csrf': csrf},
                    'panel_session=' + token + '; Path=/; HttpOnly; SameSite=Strict; Max-Age=' + str(SESSION_TTL))
                return
            if self.path == '/api/logout':
                token, entry = self.session()
                if not self.authorized(require_csrf=True):
                    return
                with LOCK:
                    SESSIONS.pop(token, None)
                self.send_json(200, {'ok': True}, 'panel_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0')
                return
            if not self.authorized(require_csrf=True):
                return
            data = self.read_json()
            if self.path == '/api/proxies':
                name = str(data.get('name', '')).strip()
                if not valid_name(name):
                    raise ValueError('نام باید ۱ تا ۶۴ نویسه باشد و / یا نویسه کنترلی نداشته باشد.')
                with LOCK:
                    state = read_state()
                    if any(p['name'] == name for p in state['proxies']):
                        raise ValueError('این نام قبلاً استفاده شده است.')
                    used_ports = {p.get('mtproxy_port') for p in state['proxies']}
                    port = next((candidate for candidate in range(2398, 2430) if candidate not in used_ports), None)
                    if port is None:
                        raise ValueError('ظرفیت ۳۲ پروکسی تکمیل شده است.')
                    state['proxies'].append({'name': name, 'secret': secrets.token_hex(16), 'backend': f'127.0.0.1:{port}', 'mtproxy_port': port, 'carrier_mode': 'https', 'enabled': True})
                    commit_state(state)
                self.send_json(200, {'ok': True})
                return
            if self.path == '/api/proxies/rename':
                old_name, new_name = str(data.get('old_name', '')), str(data.get('new_name', '')).strip()
                if not valid_name(new_name):
                    raise ValueError('نام باید ۱ تا ۶۴ نویسه باشد و / یا نویسه کنترلی نداشته باشد.')
                with LOCK:
                    state = read_state()
                    proxy = next((p for p in state['proxies'] if p['name'] == old_name), None)
                    if not proxy:
                        raise ValueError('پروفایل پیدا نشد.')
                    if any(p['name'] == new_name for p in state['proxies']):
                        raise ValueError('این نام قبلاً استفاده شده است.')
                    proxy['name'] = new_name
                    commit_state(state)
                self.send_json(200, {'ok': True})
                return
            match = re.fullmatch(r'/api/proxies/([^/]{1,768})/(toggle|delete)', self.path)
            if not match:
                self.send_json(404, {'error': 'یافت نشد.'})
                return
            name, action = match.groups()
            from urllib.parse import unquote
            name = unquote(name)
            if not valid_name(name):
                self.send_json(400, {'error': 'نام پروفایل نامعتبر است.'})
                return
            with LOCK:
                state = read_state()
                proxy = next((p for p in state['proxies'] if p['name'] == name), None)
                if not proxy:
                    self.send_json(404, {'error': 'پروفایل پیدا نشد.'})
                    return
                if action == 'toggle':
                    proxy['enabled'] = not proxy['enabled']
                    if not active_profiles(state):
                        self.send_json(400, {'error': 'حداقل یک پروفایل باید روشن بماند.'})
                        return
                elif action == 'delete':
                    if proxy['enabled'] and sum(1 for p in state['proxies'] if p['enabled']) <= 1:
                        self.send_json(400, {'error': 'آخرین پروفایل فعال را نمی‌توان حذف کرد.'})
                        return
                    state['proxies'] = [p for p in state['proxies'] if p['name'] != name]
                commit_state(state)
            self.send_json(200, {'ok': True})
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json(400, {'error': str(exc)})
        except Exception:
            self.send_json(500, {'error': 'خطا هنگام اعمال تغییر؛ وضعیت سرویس را بررسی کن.'})

    def do_OPTIONS(self):
        self.send_json(405, {'error': 'متد پشتیبانی نمی‌شود.'})


if not PASSWORD:
    raise SystemExit('PANEL_PASSWORD is required')
server = ThreadingHTTPServer(('127.0.0.1', 8765), Handler)
server.daemon_threads = True
server.serve_forever()
