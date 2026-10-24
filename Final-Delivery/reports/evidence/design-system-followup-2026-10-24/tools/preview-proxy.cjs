// Test-only preview proxy: keeps a server-side staff session (the Arena iframe stores no cookies)
// and forwards every request to the local test backend. Never logs credentials or cookies.
// Env: PORT, BIND, BACKEND_PORT, PREVIEW_ROLE (owner|manager), CREDS_FILE, PREVIEW_HOME
const http = require('http');
const fs = require('fs');

const PORT = Number(process.env.PORT || 8000);
const BIND = process.env.BIND || '0.0.0.0';
const BACKEND_PORT = Number(process.env.BACKEND_PORT || 8001);
const ROLE = process.env.PREVIEW_ROLE || 'owner';
const CREDS_FILE = process.env.CREDS_FILE;
const HOME = process.env.PREVIEW_HOME || '/admin.html#dash';
const LOGIN_PATH = ROLE === 'manager' ? '/api/auth/manager-login' : ROLE === 'member' ? '/api/auth/bale-mini-app' : '/api/auth/login';
const MEMBER_UID = process.env.PREVIEW_MEMBER_UID || '91001';

function readCreds() {
  const txt = fs.readFileSync(CREDS_FILE, 'utf8');
  const label = ROLE === 'manager' ? 'مدیر:' : 'مالک:';
  const line = txt.split('\n').find((l) => l.includes(label));
  if (!line) throw new Error('creds line missing for role ' + ROLE);
  const m = line.match(/`([^`]+)`\s*\/\s*`([^`]+)`/);
  if (!m) throw new Error('creds format');
  return { username: m[1], password: m[2] };
}

const jar = new Map(); // cookie name -> value
let loginPromise = null;

function backendRequest(opts, body) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: '127.0.0.1', port: BACKEND_PORT, ...opts }, (res) => {
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks) }));
    });
    req.on('error', reject);
    if (body) req.write(body);
    req.end();
  });
}

function absorbCookies(setCookie) {
  for (const sc of setCookie || []) {
    const [pair] = sc.split(';');
    const i = pair.indexOf('=');
    if (i > 0) {
      const name = pair.slice(0, i).trim();
      const value = pair.slice(i + 1).trim();
      if (value === '' || /max-age=0/i.test(sc)) jar.delete(name); else jar.set(name, value);
    }
  }
}

async function login() {
  if (loginPromise) return loginPromise;
  loginPromise = (async () => {
    const creds = ROLE === 'member'
      ? { init_data: require('child_process').execFileSync('python3', [__dirname + '/signed-init.py', MEMBER_UID]).toString().trim() }
      : readCreds();
    const body = Buffer.from(JSON.stringify(creds));
    const origin = `http://127.0.0.1:${BACKEND_PORT}`;
    const r = await backendRequest({
      method: 'POST', path: LOGIN_PATH,
      headers: { 'content-type': 'application/json', 'content-length': body.length, origin, host: `127.0.0.1:${BACKEND_PORT}` },
    }, body);
    if (r.status !== 200) throw new Error('login failed status ' + r.status);
    jar.clear();
    absorbCookies(r.headers['set-cookie']);
    console.log(new Date().toISOString(), `[${ROLE}] login ok (cookies: ${jar.size})`);
  })();
  try { await loginPromise; } finally { loginPromise = null; }
}

function cookieHeader() {
  return [...jar.entries()].map(([k, v]) => `${k}=${v}`).join('; ');
}

function csrfValue() {
  return jar.get('nora_csrf') || jar.get('nora_account_csrf') || '';
}

async function forward(req, res, bodyBuf, retried) {
  const method = req.method;
  const headers = { ...req.headers };
  delete headers['content-length'];
  delete headers['cookie'];
  delete headers['accept-encoding'];
  headers.host = `127.0.0.1:${BACKEND_PORT}`;
  headers.origin = `http://127.0.0.1:${BACKEND_PORT}`;
  if (headers.referer) headers.referer = `http://127.0.0.1:${BACKEND_PORT}/`;
  const ck = cookieHeader();
  if (ck) headers.cookie = ck;
  if (!/^(GET|HEAD|OPTIONS)$/.test(method) && req.url.startsWith('/api/') && !headers['x-csrf-token'] && csrfValue()) {
    headers['x-csrf-token'] = csrfValue();
  }
  if (bodyBuf && bodyBuf.length) headers['content-length'] = bodyBuf.length;
  const r = await backendRequest({ method, path: req.url, headers }, bodyBuf);
  if (r.status === 401 && req.url.startsWith('/api/') && !retried) {
    try { await login(); return forward(req, res, bodyBuf, true); } catch (e) { console.log('re-login failed:', e.message); }
  }
  absorbCookies(r.headers['set-cookie']);
  const out = { ...r.headers };
  delete out['set-cookie'];
  delete out['content-length'];
  out['content-length'] = r.body.length;
  res.writeHead(r.status, out);
  res.end(r.body);
}

const server = http.createServer((req, res) => {
  if (req.url === '/' || req.url.startsWith('/login.html')) {
    res.writeHead(302, { location: HOME });
    return res.end();
  }
  const chunks = [];
  req.on('data', (c) => chunks.push(c));
  req.on('end', async () => {
    try {
      if (!jar.size) await login();
      await forward(req, res, Buffer.concat(chunks), false);
    } catch (e) {
      console.log('proxy error:', e.message);
      if (!res.headersSent) res.writeHead(502, { 'content-type': 'text/plain; charset=utf-8' });
      res.end('preview proxy error');
    }
  });
});

server.listen(PORT, BIND, () => console.log(`[${ROLE}] preview proxy on ${BIND}:${PORT} -> backend ${BACKEND_PORT}`));
