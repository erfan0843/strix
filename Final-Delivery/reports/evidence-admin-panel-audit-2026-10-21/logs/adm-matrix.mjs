// API access-matrix probe on the test server (test data only). Creates/uses test accounts:
// manager (phone 09120000777) + role-less member (09120000778). Prints a matrix of status codes.
import fs from 'node:fs';
import { execSync } from 'node:child_process';
const BASE = 'http://127.0.0.1:8000';
const OWNER_PW = fs.readFileSync('/tmp/nora-preview/owner-pw.txt', 'utf8').trim();
const envText = fs.readFileSync('/tmp/nora-preview/env.sh', 'utf8');
const env = {}; for (const m of envText.matchAll(/^export ([A-Z_]+)=(.*)$/gm)) env[m[1]] = m[2].replace(/^'(.*)'$/, '$1');
const PY = '/home/user/venvs/nora/bin/python';
const mk = (phone, extra = '') => JSON.parse(execSync(`bash -c "source /tmp/nora-preview/env.sh; ${PY} /tmp/nora-preview/mk_phone_session.py ${phone} ${extra}"`, { encoding: 'utf8' }).trim().split('\n').pop());
const parseSetCookie = (res, jar) => { for (const c of (res.headers.getSetCookie ? res.headers.getSetCookie() : [])) { const [kv] = c.split(';'); const i = kv.indexOf('='); jar[kv.slice(0, i).trim()] = kv.slice(i + 1).trim(); } };
function client(jar, csrfName) {
  return async (path, init = {}) => {
    const headers = { Origin: BASE, 'Content-Type': 'application/json', Cookie: Object.entries(jar).map(([k, v]) => k + '=' + v).join('; '), ...(init.headers || {}) };
    if (init.method && init.method !== 'GET') { headers['X-CSRF-Token'] = jar[csrfName] || ''; headers['Idempotency-Key'] = 'm-' + Math.random().toString(36).slice(2); }
    const res = await fetch(BASE + path, { method: init.method || 'GET', headers, body: init.body ? JSON.stringify(init.body) : undefined });
    parseSetCookie(res, jar); let body = null; try { body = await res.json(); } catch (e) { }
    return { status: res.status, body };
  };
}
const ownerJar = {}; const owner = client(ownerJar, 'nora_csrf');
const login = await owner('/api/auth/login', { method: 'POST', body: { username: env.NORA_OWNER_USERNAME, password: OWNER_PW } });
console.log('owner login', login.status);
const mgrSeed = mk('09120000777', 'profile'); const memSeed = mk('09120000778');
console.log('manager account', mgrSeed.account_id, 'member account', memSeed.account_id);
const MGR_USER = 'qa-manager-' + Date.now().toString(36); const MGR_PW = process.env.QA_MANAGER_PW /* test-only, redacted */;
let r = await owner(`/api/owner/accounts/${mgrSeed.account_id}/role`, { method: 'PUT', body: { role: 'manager' } }); console.log('set role', r.status, JSON.stringify(r.body));
r = await owner(`/api/owner/accounts/${mgrSeed.account_id}/manager-credentials`, { method: 'PUT', body: { username: MGR_USER, password: MGR_PW } }); console.log('set creds', r.status, JSON.stringify(r.body));
fs.writeFileSync('/tmp/qa/adm/manager.json', JSON.stringify({ user: MGR_USER, pw: MGR_PW, account_id: mgrSeed.account_id, member_account_id: memSeed.account_id }));
// manager session via staff login
const mgrJar = {}; const mgr = client(mgrJar, 'nora_account_csrf');
r = await mgr('/api/auth/staff-login', { method: 'POST', body: { username: MGR_USER, password: MGR_PW } }); console.log('manager staff-login', r.status, JSON.stringify(r.body).slice(0, 200), Object.keys(mgrJar));
// role-less member session via DB-minted phone session
const memJar = { nora_account_session: memSeed.session, nora_account_csrf: memSeed.csrf }; const mem = client(memJar, 'nora_account_csrf');
const anon = client({}, 'x');
const forms = await owner('/api/forms?limit=1'); const formId = forms.body && forms.body.items && forms.body.items[0] && forms.body.items[0].id;
console.log('sample form', formId);
const probes = [
  ['GET', '/api/auth/me'], ['GET', '/api/account/me'],
  ['GET', '/api/admin/inbox'], ['GET', '/api/admin/reports/summary'],
  ['GET', '/api/forms?limit=1'], ['GET', `/api/forms/${formId}`], ['GET', `/api/forms/${formId}/responses?limit=1`],
  ['POST', `/api/forms/${formId}/publish`, { expected_version: 999 }], ['POST', `/api/forms/${formId}/pause`, { expected_version: 999 }],
  ['GET', '/api/owner/accounts'], ['PUT', `/api/owner/accounts/${memSeed.account_id}/role`, { role: 'manager' }],
  ['PUT', `/api/owner/accounts/${memSeed.account_id}/manager-credentials`, { username: 'x-esc-' + Date.now().toString(36), password: process.env.QA_ESC_PW /* test-only, redacted */ }],
  ['GET', '/api/owner/service-settings'], ['GET', '/api/owner/data/status'], ['GET', '/api/owner/site-content'],
  ['GET', '/api/cooperation-requests'], ['GET', '/api/integrations/status'], ['GET', '/api/health'],
  ['POST', '/api/outbox', { channel: 'sms', to: '0', text: 'x' }],
  ['PATCH', '/api/owner/site-content', { content: {} }],
];
const who = { owner, manager: mgr, member: mem, anonymous: anon };
const out = [];
for (const [method, path, body] of probes) {
  const row = { method, path };
  for (const [name, c] of Object.entries(who)) { const res = await c(path, { method, body }); row[name] = res.status + (res.body && res.body.detail ? ':' + (typeof res.body.detail === 'string' ? res.body.detail : (res.body.detail.code || JSON.stringify(res.body.detail))).slice(0, 40) : ''); }
  out.push(row); console.log(method.padEnd(5), path.padEnd(62), 'owner=' + row.owner, 'manager=' + row.manager, 'member=' + row.member, 'anon=' + row.anonymous);
}
fs.writeFileSync('/tmp/qa/adm/matrix.json', JSON.stringify(out, null, 1));
// revocation: owner removes manager role -> manager session must stop working immediately
r = await owner(`/api/owner/accounts/${mgrSeed.account_id}/role`, { method: 'PUT', body: { role: null } }); console.log('revoke role', r.status, JSON.stringify(r.body));
r = await mgr('/api/admin/inbox'); console.log('manager inbox after revoke', r.status, JSON.stringify(r.body).slice(0, 120));
r = await mgr('/api/account/me'); console.log('manager me after revoke', r.status, JSON.stringify(r.body).slice(0, 160));
// restore role + creds for browser run
r = await owner(`/api/owner/accounts/${mgrSeed.account_id}/role`, { method: 'PUT', body: { role: 'manager' } }); console.log('restore role', r.status);
r = await owner(`/api/owner/accounts/${mgrSeed.account_id}/manager-credentials`, { method: 'PUT', body: { username: MGR_USER, password: MGR_PW } }); console.log('restore creds', r.status);
// owner logout -> owner endpoints must 401
r = await owner('/api/auth/logout', { method: 'POST' }); console.log('owner logout', r.status);
r = await owner('/api/owner/accounts'); console.log('owner accounts after logout', r.status);
