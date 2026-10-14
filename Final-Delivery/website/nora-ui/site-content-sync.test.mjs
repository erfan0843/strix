import assert from 'node:assert/strict';
import fs from 'node:fs';
import { JSDOM } from 'jsdom';

const source = fs.readFileSync(new URL('./site-content-sync.js', import.meta.url), 'utf8');
const updates = [];
let serverVersion = 0;
const api = {
  me: async () => ({ id: 'owner-1' }),
  getOwnerSiteContent: async () => ({
    version: serverVersion,
    content: { cooperation: [] }
  }),
  listForms: async () => ({ items: [
    { id: 'coop-published', name: 'فرم همکاری منتشرشده', status: 'published', need: 'other' },
    { id: 'reg-published', name: 'فرم ثبت‌نام', status: 'published', need: 'reg' },
    { id: 'coop-draft', name: 'فرم همکاری پیش‌نویس', status: 'draft', need: 'other' }
  ] }),
  updateSiteContent: async (content, version) => {
    assert.equal(version, serverVersion);
    updates.push(content);
    serverVersion += 1;
    return { version: serverVersion };
  }
};

const dom = new JSDOM(`<!doctype html><html><body>
  <section id="siteContentSync">
    <label><input type="checkbox" data-sync-category="events" checked><b data-sync-count="events">۰</b></label>
    <label><input type="checkbox" data-sync-category="people" checked><b data-sync-count="people">۰</b></label>
    <label><input type="checkbox" data-sync-category="articles" checked><b data-sync-count="articles">۰</b></label>
    <label><input type="checkbox" data-sync-category="partners" checked><b data-sync-count="partners">۰</b></label>
    <label><input type="checkbox" data-sync-category="banners" checked><b data-sync-count="banners">۰</b></label>
    <label><input type="checkbox" data-sync-category="cooperation"><b data-sync-count="cooperation">۰</b></label>
    <label><input type="checkbox" data-sync-category="library" checked><b data-sync-count="library">۰</b></label>
    <select id="cooperationFormSelect" disabled><option value="">برای انتخاب فرم، با حساب مالک وارد شوید</option></select>
    <p id="cooperationFormHelp"></p>
    <p id="siteContentSyncState"></p>
    <details id="siteContentOwnerLogin"><form id="siteContentOwnerLoginForm">
      <input name="username"><input name="password" type="password"><button type="submit">ورود</button>
    </form></details>
    <button type="button" id="siteContentSyncNow">همگام‌سازی</button>
  </section>
</body></html>`, {
  url: 'https://nora.test/admin.html',
  runScripts: 'dangerously',
  beforeParse(window) {
    window.__NORA_TEST_FIXTURE_MODE__ = false;
    window.NORA_SERVER_API = api;
    window.NORA_UI = {
      toast() {},
      pubEvents: () => [{ id: 'local-event', privacy: 'public', status: 'published' }],
      postsAll: () => [{ id: 'local-article', pub: 1, pend: 0 }]
    };
    window.localStorage.setItem('nora-people', JSON.stringify([{ id: 'local-person', status: 'published' }]));
    window.localStorage.setItem('nora-partners', JSON.stringify([{ id: 'local-partner', status: 'published' }]));
    window.localStorage.setItem('nora-public-banners', JSON.stringify([{ id: 'local-banner', status: 'published' }]));
    window.localStorage.setItem('nora-clublib', JSON.stringify([{ id: 'local-item', pub: 1 }]));
    window.confirm = () => true;
  }
});
Object.defineProperty(dom.window.document, 'readyState', { configurable: true, value: 'complete' });
dom.window.eval(source);
await new Promise(resolve => setTimeout(resolve, 0));

const initialSnapshot = dom.window.NORA_SITE_CONTENT_SYNC.snapshot();
for (const key of ['events', 'people', 'articles', 'partners', 'banners', 'library']) {
  assert.deepEqual(JSON.parse(JSON.stringify(initialSnapshot[key])), [], `${key} ignores stale browser data in production`);
  const checkbox = dom.window.document.querySelector(`[data-sync-category="${key}"]`);
  assert.equal(checkbox.disabled, true, `${key} stays disabled without a server editor`);
  assert.equal(checkbox.checked, false, `${key} cannot inherit a stale browser selection`);
}
const select = dom.window.document.querySelector('#cooperationFormSelect');
assert.equal(select.disabled, false, 'verified owner access enables the server form selector');
assert.deepEqual(Array.from(select.options, option => option.value), ['', 'coop-published'],
  'only published, non-registration forms are offered');

select.value = 'coop-published';
select.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
assert.deepEqual(JSON.parse(JSON.stringify(dom.window.NORA_SITE_CONTENT_SYNC.snapshot().cooperation)),
  [{ formId: 'coop-published' }], 'the selected form becomes the cooperation snapshot');
assert.equal(dom.window.document.querySelector('[data-sync-category="cooperation"]').checked, true,
  'choosing a form selects its synchronization category');

await dom.window.NORA_SITE_CONTENT_SYNC.synchronize();
assert.deepEqual(JSON.parse(JSON.stringify(updates)), [{ cooperation: [{ formId: 'coop-published' }] }],
  'sync publishes only the selected cooperation form reference');
assert.match(dom.window.document.querySelector('#siteContentSyncState').textContent, /نسخهٔ ۱/,
  'the owner sees a successful publication state');

dom.window.close();

const fixtureDom = new JSDOM('<!doctype html><html><body></body></html>', {
  url: 'https://nora.test/admin.html',
  runScripts: 'dangerously',
  beforeParse(window) {
    window.__NORA_TEST_FIXTURE_MODE__ = true;
    window.NORA_UI = {
      pubEvents: () => [{ id: 'fixture-event', privacy: 'public', status: 'published' }],
      postsAll: () => [{ id: 'fixture-article', pub: 1, pend: 0 }]
    };
    window.localStorage.setItem('nora-people', JSON.stringify([{ id: 'fixture-person' }]));
    window.localStorage.setItem('nora-partners', JSON.stringify([{ id: 'fixture-partner' }]));
    window.localStorage.setItem('nora-public-banners', JSON.stringify([{ id: 'fixture-banner' }]));
    window.localStorage.setItem('nora-clublib', JSON.stringify([{ id: 'fixture-library-item', pub: 1 }]));
  }
});
Object.defineProperty(fixtureDom.window.document, 'readyState', { configurable: true, value: 'complete' });
fixtureDom.window.eval(source);
const fixtureSnapshot = fixtureDom.window.NORA_SITE_CONTENT_SYNC.snapshot();
for (const [key, id] of Object.entries({
  events: 'fixture-event', people: 'fixture-person', articles: 'fixture-article',
  partners: 'fixture-partner', banners: 'fixture-banner', library: 'fixture-library-item'
})) {
  assert.equal(fixtureSnapshot[key][0]?.id, id, `${key} fixtures remain available in explicit test mode`);
}
fixtureDom.window.close();
console.log('site-content-sync: production server-only guard and explicit fixture mode passed');
