import test from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));

const INIT_DATA = 'auth_date=1700000000&user=%7B%22id%22%3A73421%7D&hash=' + 'a'.repeat(64);

function jsonResponse(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

/**
 * صفحه را با مینی‌اپ بله و شبکهٔ ساختگی باز می‌کند.
 * `initData` خالی یعنی صفحه داخل شیشهٔ بله باز نشده است.
 */
async function openPage({ initData = INIT_DATA, session = null, loginStatus = 200, loginBody = null } = {}) {
  const calls = [];
  // اصل مبدأ file:// opaque است و localStorage نمی‌دهد؛ همان انبار درون‌حافظه‌ی
  // بقیهٔ آزمون‌های صفحه را می‌گذاریم.
  const storeMap = new Map();
  const store = {
    getItem: key => (storeMap.has(key) ? storeMap.get(key) : null),
    setItem: (key, value) => storeMap.set(key, String(value)),
    removeItem: key => storeMap.delete(key),
    clear: () => storeMap.clear(),
    key: index => [...storeMap.keys()][index],
    get length() { return storeMap.size; },
  };
  const dom = await JSDOM.fromFile(path.join(ROOT, 'home.html'), {
    runScripts: 'dangerously',
    resources: 'usable',
    pretendToBeVisual: true,
    beforeParse(window) {
      window.__NORA_TEST_FIXTURE_MODE__ = false;
      window.scrollTo = () => {};
      Object.defineProperty(window, 'localStorage', { configurable: true, value: store });
      window.Bale = { WebApp: { initData } };
      window.fetch = (url, options) => {
        const target = String(url);
        calls.push({ url: target, options: options || {} });
        if (target === '/api/auth/bale-mini-app') {
          return Promise.resolve(
            jsonResponse(loginStatus, loginBody ?? { authenticated: true, account_id: 'acct-1', provider: 'bale' })
          );
        }
        if (target === '/api/auth/me') {
          return Promise.resolve(
            session === 'owner' ? jsonResponse(200, { authenticated: true, role: 'owner' }) : jsonResponse(401, {})
          );
        }
        if (target === '/api/account/me') {
          return Promise.resolve(
            session === 'account' ? jsonResponse(200, { authenticated: true, provider: 'phone' }) : jsonResponse(401, {})
          );
        }
        return Promise.resolve(jsonResponse(404, {}));
      };
      if (!window.matchMedia) window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {} });
      window.console.error = () => {};
      window.console.warn = () => {};
    },
  });
  await new Promise(resolve => setTimeout(resolve, 900));
  const loginCalls = () => calls.filter(call => call.url === '/api/auth/bale-mini-app');
  return { dom, window: dom.window, calls, loginCalls };
}

test('a signed Bale mini app payload is exchanged for a server session', async t => {
  const page = await openPage();
  t.after(() => page.dom.window.close());
  const login = page.loginCalls();
  assert.equal(login.length, 1, 'initData باید دقیقاً یک‌بار فرستاده شود');
  assert.equal(login[0].options.method, 'POST');
  assert.equal(login[0].options.credentials, 'same-origin');
  assert.deepEqual(JSON.parse(login[0].options.body), { init_data: INIT_DATA });
});

test('an existing session is checked first so the one-time payload is not wasted', async t => {
  for (const session of ['owner', 'account']) {
    const page = await openPage({ session });
    t.after(() => page.dom.window.close());
    const sessionChecks = page.calls.filter(call => call.url === '/api/auth/me' || call.url === '/api/account/me');
    assert.ok(sessionChecks.length > 0, `${session}: باید وضعیت نشست پرسیده شود`);
    assert.equal(page.loginCalls().length, 0, `${session}: امضا نباید مصرف شود`);
  }
});

test('no payload is sent when the page is outside the Bale mini app', async t => {
  for (const initData of ['', 'user=%7B%22id%22%3A1%7D']) {
    const page = await openPage({ initData });
    t.after(() => page.dom.window.close());
    assert.equal(page.loginCalls().length, 0, `initData=${JSON.stringify(initData)}`);
  }
});

test('a rejected payload never blocks the ordinary login path', async t => {
  for (const status of [401, 409, 503]) {
    const page = await openPage({ loginStatus: status, loginBody: { detail: 'invalid_bale_init_data' } });
    t.after(() => page.dom.window.close());
    assert.equal(page.loginCalls().length, 1);
    assert.equal(typeof page.window.authSheet, 'function', `status ${status}: برگهٔ ورود باید در دسترس بماند`);
  }
});
