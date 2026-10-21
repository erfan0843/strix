import assert from 'node:assert/strict';
import fs from 'node:fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('./admin.html', import.meta.url), 'utf8');
const section = html.match(/<section class="owner-banner-manager[\s\S]*?<\/section>/)?.[0];
assert.ok(section, 'admin page contains the owner banner manager');
const source = fs.readFileSync(new URL('./owner-banner-manager.js', import.meta.url), 'utf8');
const countdownSource = fs.readFileSync(new URL('./countdown.js', import.meta.url), 'utf8');
const clone = value => JSON.parse(JSON.stringify(value));
let serverVersion = 3;
const updates = [];
const closesAt = new Date(Date.now() + 2 * 86_400_000).toISOString();
const serverContent = {
  events: [
    { id: 'ev-open', t: 'کارگاه باز', when: '۱۲ آبان', startsAt: new Date(Date.now() + 9 * 86_400_000).toISOString(),
      registration: { state: 'open', lifecycle: 'scheduled', closesAt, countdownTo: closesAt, startsIn: new Date(Date.now() + 9 * 86_400_000).toISOString() } },
    { id: 'ev-closed', t: 'کارگاه بسته', when: '۱۳ آبان', registration: { state: 'closed', lifecycle: 'scheduled', countdownTo: '' } }
  ],
  banners: [
    { id: 'owner-draft', status: 'draft', active: true, order: 0, t: 'پیش‌نویس مالک',
      eyebrow: 'آماده‌سازی', subtitle: 'عنوان ثانویه', s: 'متن', theme: 'teal', layout: 'split',
      align: 'right', overlay: 48, focusX: 50, focusY: 50 },
    { id: 'owner-live', status: 'published', active: true, order: 1, t: 'بنر منتشرشده', theme: 'ocean', layout: 'cover' }
  ],
  banner_settings: { enabled: true, auto_rotate: false, interval_seconds: 7, show_controls: true }
};
const api = {
  me: async () => ({ authenticated: true, role: 'owner' }),
  getOwnerSiteContent: async () => ({ version: serverVersion, content: clone(serverContent) }),
  updateSiteContent: async (content, expectedVersion) => {
    assert.equal(expectedVersion, serverVersion, 'writes use the latest owner content version');
    updates.push({ content: clone(content), expectedVersion });
    serverVersion += 1;
    serverContent.banners = clone(content.banners);
    serverContent.banner_settings = clone(content.banner_settings);
    return { version: serverVersion, content: clone(serverContent) };
  }
};
const dom = new JSDOM(`<!doctype html><html><body>${section}</body></html>`, {
  url: 'https://nora.test/admin.html', runScripts: 'dangerously',
  beforeParse(window) {
    window.__NORA_TEST_FIXTURE_MODE__ = false;
    window.NORA_SERVER_API = api;
    window.NORA_UI = { toast() {} };
    window.confirm = () => true;
    window.localStorage.setItem('nora-public-banners', JSON.stringify([{ id: 'must-not-load-local-banner' }]));
  }
});
Object.defineProperty(dom.window.document, 'readyState', { configurable: true, value: 'complete' });
dom.window.eval(countdownSource);
dom.window.eval(source);
const manager = dom.window.NORA_OWNER_BANNER_MANAGER;
for (let attempt = 0; attempt < 20 && !manager.state.loaded; attempt += 1)
  await new Promise(resolve => setTimeout(resolve, 0));
assert.equal(manager.state.loaded, true, 'owner content loads from the server');
assert.deepEqual(manager.state.rows.map(row => row.id), ['owner-draft', 'owner-live'],
  'the manager includes server drafts and published banners, never browser-local banner data');
assert.match(dom.window.document.querySelector('#ownerBannerList').textContent, /پیش‌نویس مالک/);

const form = dom.window.document.querySelector('#ownerBannerForm');
const title = form.elements.namedItem('title');
title.value = 'عنوان <b>امن</b>';
title.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
assert.equal(dom.window.document.querySelector('#ownerBannerPreview h4').textContent, 'عنوان <b>امن</b>',
  'preview treats owner text as text rather than markup');
assert.equal(dom.window.document.querySelector('#ownerBannerPreview h4 b'), null);

form.elements.namedItem('status').value = 'published';
form.elements.namedItem('primaryLabel').value = 'جزئیات برنامه';
form.elements.namedItem('primaryHref').value = 'javascript:alert(1)';
form.elements.namedItem('primaryHref').dispatchEvent(new dom.window.Event('input', { bubbles: true }));
assert.equal(await manager.save(), false, 'unsafe CTA links do not reach the owner API');
assert.equal(updates.length, 0);
assert.match(dom.window.document.querySelector('#ownerBannerState').textContent, /پیوند/);

form.elements.namedItem('primaryHref').value = '/events.html#upcoming';
form.elements.namedItem('primaryHref').dispatchEvent(new dom.window.Event('input', { bubbles: true }));
form.elements.namedItem('kind').value = 'sponsored';
form.elements.namedItem('kind').dispatchEvent(new dom.window.Event('change', { bubbles: true }));
assert.equal(dom.window.document.querySelector('#ownerBannerPreview .obm-preview-kind')?.textContent, 'تبلیغ',
  'the preview shows the public «تبلیغ» label so the owner sees what visitors will see');
form.elements.namedItem('autoRotate').checked = true;
form.elements.namedItem('autoRotate').dispatchEvent(new dom.window.Event('change', { bubbles: true }));
form.elements.namedItem('rotateInterval').value = '12';
form.elements.namedItem('rotateInterval').dispatchEvent(new dom.window.Event('input', { bubbles: true }));
assert.equal(await manager.save(), true, `valid banner and global rotation settings save successfully: ${dom.window.document.querySelector('#ownerBannerState').textContent}`);
assert.equal(updates.length, 1);
assert.equal(updates[0].expectedVersion, 3);
assert.equal(updates[0].content.banners[0].status, 'published');
assert.equal(updates[0].content.banners[0].href, '/events.html#upcoming');
assert.equal(updates[0].content.banners[0].countdown, '', 'banners without a countdown stay plain');
assert.equal(updates[0].content.banners[0].kind, 'sponsored', 'banner kind round-trips to the owner API');
assert.equal(updates[0].content.banners[1].kind, 'notice', 'existing banners without a kind stay plain notices');
assert.equal(updates[0].content.banner_settings.auto_rotate, true);
assert.equal(updates[0].content.banner_settings.interval_seconds, 12);
assert.equal(manager.state.version, 4);
assert.match(dom.window.document.querySelector('#ownerBannerState').textContent, /نسخهٔ ۴/);

/* فاز ۷: پیوند به رویداد، شمارشگر از خود رویداد، قاعده‌های اعتبارسنجی و پیش‌نمایش موبایل */
const eventSelect = form.elements.namedItem('eventId');
assert.deepEqual([...eventSelect.options].map(o => o.value), ['', 'ev-open', 'ev-closed'],
  'the event picker lists only published events from the server snapshot');
form.elements.namedItem('countdown').value = 'reg_close';
form.elements.namedItem('countdown').dispatchEvent(new dom.window.Event('change', { bubbles: true }));
assert.equal(await manager.save(), false, 'an event countdown without an event is rejected before the API');
assert.equal(updates.length, 1);
eventSelect.value = 'ev-open';
eventSelect.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
assert.match(dom.window.document.querySelector('#ownerBannerEventState').textContent, /ثبت‌نام باز/);
assert.match(dom.window.document.querySelector('#ownerBannerPreview .obm-preview-countdown').textContent, /تا پایان ثبت‌نام: ۱ روز/,
  'the preview countdown is computed from the event deadline, not from banner input');
eventSelect.value = 'ev-closed';
eventSelect.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
form.elements.namedItem('afterEndText').value = 'مهلت تمام شد';
form.elements.namedItem('afterEndText').dispatchEvent(new dom.window.Event('input', { bubbles: true }));
assert.ok(dom.window.document.querySelector('#ownerBannerPreview .obm-preview-countdown.is-ended'), 'closed registration previews as ended');
assert.match(dom.window.document.querySelector('#ownerBannerPreview .obm-preview-countdown').textContent, /مهلت تمام شد/);
form.elements.namedItem('countdown').value = 'campaign_end';
form.elements.namedItem('countdown').dispatchEvent(new dom.window.Event('change', { bubbles: true }));
assert.equal(await manager.save(), false, 'a campaign countdown needs its own end time');
assert.equal(updates.length, 1);
form.elements.namedItem('campaignEndsAt').value = '2030-01-01T10:00';
form.elements.namedItem('campaignEndsAt').dispatchEvent(new dom.window.Event('input', { bubbles: true }));
eventSelect.value = 'ev-open';
eventSelect.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
dom.window.document.querySelector('[data-obm-preview-mode="mobile"]').click();
assert.equal(dom.window.document.querySelector('#ownerBannerPreview').dataset.previewMode, 'mobile');
assert.equal(dom.window.document.querySelector('[data-obm-preview-mode="mobile"]').getAttribute('aria-pressed'), 'true');
assert.equal(await manager.save(), true, `event-linked banner with a campaign deadline saves: ${dom.window.document.querySelector('#ownerBannerState').textContent}`);
assert.equal(updates.length, 2);
const savedRow = updates[1].content.banners[0];
assert.equal(savedRow.eventId, 'ev-open');
assert.equal(savedRow.countdown, 'campaign_end');
assert.equal(savedRow.campaignEndsAt, new Date('2030-01-01T10:00').toISOString());
assert.equal(savedRow.afterEndText, 'مهلت تمام شد');
assert.equal(savedRow.afterEnd, 'hide');
assert.equal(updates[1].content.banners[1].eventId, '', 'untouched banners keep an empty event link');
assert.ok(!('regClosesAt' in savedRow) && !('startsAtEvent' in savedRow), 'no event date is duplicated into the banner payload');
dom.window.document.querySelector('[data-obm-preview-mode="desktop"]').click();

api.updateSiteContent = async () => { throw { status: 409, code: 'site_content_version_conflict' }; };
title.value = 'ویرایش هم‌زمان';
title.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
assert.equal(await manager.save(), false, 'the manager never overwrites a concurrent owner update');
assert.equal(manager.state.version, 5);
assert.match(dom.window.document.querySelector('#ownerBannerState').textContent, /هم‌زمان تغییر کرده/);

api.me = async () => ({ authenticated: true, role: 'manager' });
assert.equal(await manager.reload(), false, 'a non-owner cannot reload owner banner data');
assert.equal(manager.state.loaded, false);
assert.equal(manager.state.rows.length, 0, 'a failed owner check clears stale server drafts from the UI');
assert.equal(dom.window.document.querySelector('#ownerBannerList').textContent.trim(), '');

dom.window.close();
console.log('owner-banner-manager: server-only drafts, safe preview/CTA, versioned save, and conflict handling passed');
