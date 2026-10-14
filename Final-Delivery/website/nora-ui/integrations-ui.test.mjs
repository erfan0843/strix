import test from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));

async function openAdmin(seed = {}) {
  const storeMap = new Map(Object.entries(seed));
  const store = {
    getItem: key => storeMap.has(key) ? storeMap.get(key) : null,
    setItem: (key, value) => storeMap.set(key, String(value)),
    removeItem: key => storeMap.delete(key),
    clear: () => storeMap.clear(),
    key: index => [...storeMap.keys()][index],
    get length() { return storeMap.size; }
  };
  const errors = [];
  const network = [];
  const dom = await JSDOM.fromFile(path.join(ROOT, 'admin.html'), {
    runScripts: 'dangerously', resources: 'usable', pretendToBeVisual: true,
    beforeParse(window) {
      window.__NORA_TEST_FIXTURE_MODE__ = true;
      window.scrollTo = () => {};
      window.fetch = (...args) => { network.push(args); return Promise.reject(new Error('offline test fetch')); };
      Object.defineProperty(window, 'localStorage', { configurable: true, value: store });
      if (!window.matchMedia) window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {} });
      window.addEventListener('error', event => errors.push(event.message));
      window.console.error = (...args) => errors.push(args.join(' '));
    }
  });
  await new Promise(resolve => setTimeout(resolve, 1000));
  const { window } = dom;
  const click = selector => {
    const element = window.document.querySelector(selector);
    assert.ok(element, `missing UI element: ${selector}`);
    element.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
    return element;
  };
  const select = (selector, value) => {
    const element = window.document.querySelector(selector);
    assert.ok(element, `missing UI element: ${selector}`);
    element.value = value;
    element.dispatchEvent(new window.Event('change', { bubbles: true }));
  };
  return { dom, window, store, errors, network, click, select };
}

test('certificate and ticket settings save local preview preferences and generate no real output', async t => {
  const page = await openAdmin();
  t.after(() => page.dom.window.close());
  const { window, store, click, select } = page;
  click('#admNav [data-sec="users"]');
  click('[data-uv="cert"]');
  assert.equal(window.document.querySelectorAll('[data-cstep]').length, 4);
  assert.ok(window.document.querySelector('[data-cert-format]'));
  assert.ok(window.document.querySelectorAll('[data-cert-field]').length >= 7);
  select('[data-cert-format]', 'jpg');
  click('[data-cert-field="qr"]');
  let state = JSON.parse(store.getItem('nora-admin'));
  assert.equal(state.cert.format, 'jpg');
  assert.equal(state.cert.include.qr, true);
  assert.equal(store.getItem('nora-issued-certificates'), null);

  click('#admNav [data-sec="settings"]');
  click('[data-setg="ticket"]');
  assert.equal(window.document.querySelectorAll('[data-ticket-field]').length, 8);
  select('[data-ticket-format]', 'jpg');
  click('[data-ticket-test]');
  assert.ok(window.document.querySelector('.ticket-engine-preview svg'));
  assert.match(window.document.querySelector('.ticket-engine-preview').textContent, /فاقد اعتبار ورود/);
  state = JSON.parse(store.getItem('nora-admin'));
  assert.equal(state.ticket.format, 'jpg');
  assert.equal(state.ticket.testOk, true);
  assert.equal(store.getItem('nora-issued-tickets'), null);
  assert.deepEqual(page.errors, []);
  assert.ok(page.network.length >= 1);
  assert.ok(page.network.every(([url, options]) => url === '/api/auth/me' && options.method === 'GET'),
    'the admin page only checks the same-origin owner session');
});

test('certificate records preserve owner approval, JPG choice and Bale-only policy while remaining unsent', async t => {
  const seeded = {
    v: 78, who: 'p1', sec: 'users', uV: 'cert',
    cert: { step: 3, picked: ['u1'], format: 'jpg', include: { name: true, title: true, kind: true, date: true, hours: true, serial: true, qr: false } }
  };
  const page = await openAdmin({ 'nora-admin': JSON.stringify(seeded) });
  t.after(() => page.dom.window.close());
  const { window, store, click } = page;
  const ui = window.NORA_UI;
  const before = ui.issuedCertificates().length;
  click('[data-cqueue]');
  const request = ui.ownerApprovals().find(row => row && row.type === 'cert-batch' && row.status === 'pending');
  assert.ok(request);
  assert.equal(request.outputFormat, 'jpg');
  assert.equal(request.deliveryChannel, 'bale');
  assert.equal(request.deliveryEnabled, false);
  assert.equal(ui.issuedCertificates().length, before);

  click(`[data-certapprove="${request.id}"]`);
  const record = ui.issuedCertificates().find(row => row && row.ownerApprovalId === request.id);
  assert.ok(record);
  assert.equal(record.outputFormat, 'jpg');
  assert.equal(record.deliveryChannel, 'bale');
  assert.equal(record.deliveryEnabled, false);
  assert.equal(record.sent, false);
  assert.equal(record.include.qr, false);
  assert.equal(record.approvedById, 'p1');
  assert.equal(store.getItem('nora-outbox'), null);
  assert.ok(page.network.length >= 1);
  assert.ok(page.network.every(([url, options]) => url === '/api/auth/me' && options.method === 'GET'),
    'certificate actions do not send anything beyond the same-origin owner-session check');
});

test('bot and notification settings expose Bale/Eitaa channels without any browser credential field', async t => {
  const page = await openAdmin();
  t.after(() => page.dom.window.close());
  const { window, click, network } = page;
  click('#admNav [data-sec="settings"]');
  click('[data-setg="bots"]');
  const body = window.document.querySelector('#admBody');
  assert.match(body.textContent, /ارسال خاموش/);
  assert.ok(!body.querySelector('input[name*="token"],input[id*="token"],input[type="password"]'));
  assert.match(body.textContent, /بله · ربات \+ Mini App/);
  assert.match(body.textContent, /ایتا · Mini App/);
  assert.match(body.textContent, /سرور جدا لازم نیست/);
  assert.doesNotMatch(body.textContent, /NORA_EITAA_BOT_TOKEN/);
  click('[data-bot-refresh]');
  assert.match(window.document.querySelector('#toast').textContent, /دوباره بررسی شد/);
  assert.ok(network.some(([url, options]) => url === '/api/integrations/status' && options.method === 'GET'));
  assert.ok(network.every(([url, options]) =>
    (url === '/api/integrations/status' || url === '/api/auth/me') && options.method === 'GET'),
    'status refresh and owner-session checks are the only same-origin requests');

  click('[data-setg="notify"]');
  assert.ok(window.document.querySelector('[data-ntfch="reg_ok:bale"]'));
  assert.ok(window.document.querySelector('[data-ntfch="reg_ok:eitaa"]'));
  assert.ok(window.document.querySelector('[data-ntfch="reg_ok:acc"]'));
  assert.deepEqual(page.errors, []);
});

test('migrates legacy payment gateway state and strips old browser key fields', async t => {
  const adminState = {
    v: 78, who: 'p1', sec: 'settings', setG: 'money',
    fin: { gates: [{ k: 'decent', key: 'old-local-key' }, { k: 'bale', key: 'old-local-key', on: 0 }] }
  };
  const finance = { gates: [{ k: 'decent', key: 'old-local-key' }, { k: 'bale', key: 'old-local-key', on: 0 }], cards: [] };
  const page = await openAdmin({ 'nora-admin': JSON.stringify(adminState), 'nora-finance': JSON.stringify(finance) });
  t.after(() => page.dom.window.close());
  const state = JSON.parse(page.store.getItem('nora-admin'));
  const financeStore = JSON.parse(page.store.getItem('nora-finance'));
  assert.deepEqual(state.fin.gates.map(g => g.k), ['bale']);
  assert.ok(!('key' in state.fin.gates[0]));
  assert.deepEqual(financeStore.gates.map(g => g.k), ['bale']);
  assert.ok(!('key' in financeStore.gates[0]));
  assert.ok(!page.dom.window.document.querySelector('[data-finkey]'));
  assert.deepEqual(page.errors, []);
});

test('strips legacy finance keys even when the admin state takes the version-reset path', async t => {
  const finance = { gates: [{ k: 'decent', key: 'old-local-key' }, { k: 'card', token: 'old-local-token', secret: 'old-local-secret' }], cards: [] };
  const page = await openAdmin({
    'nora-admin': JSON.stringify({ v: 77, who: 'p1', sec: 'settings' }),
    'nora-finance': JSON.stringify(finance)
  });
  t.after(() => page.dom.window.close());
  const financeStore = JSON.parse(page.store.getItem('nora-finance'));
  assert.deepEqual(financeStore.gates.map(g => g.k), ['card']);
  assert.ok(!('key' in financeStore.gates[0]));
  assert.ok(!('token' in financeStore.gates[0]));
  assert.ok(!('secret' in financeStore.gates[0]));
  assert.deepEqual(page.errors, []);
});
