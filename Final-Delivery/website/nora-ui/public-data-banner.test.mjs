import assert from 'node:assert/strict';
import fs from 'node:fs';
import { JSDOM } from 'jsdom';

const source = fs.readFileSync(new URL('./public-data.js', import.meta.url), 'utf8');
const future = new Date(Date.now() + 60_000).toISOString();
const past = new Date(Date.now() - 60_000).toISOString();
const payload = {
  content: {
    events: [], people: [], articles: [], partners: [], library: [], cooperation: [],
    banner_settings: { enabled: false, auto_rotate: true, interval_seconds: 45, show_controls: false },
    banners: [
      { id: 'live-banner', status: 'published', active: true, order: 2,
        t: 'اعلام برنامه', eyebrow: 'تازه', subtitle: 'زیرعنوان', s: 'جزئیات کوتاه',
        img: 'https://nora.test/banner.webp', href: 'javascript:alert(1)', primaryLabel: 'پیوند ناامن',
        secondaryHref: '/events.html#upcoming', secondaryLabel: 'فهرست برنامه‌ها',
        theme: 'unknown', layout: 'broken', align: 'center', overlay: 110, focusX: -5, focusY: 112 },
      { id: 'draft-banner', status: 'draft', t: 'پیش‌نویس خصوصی' },
      { id: 'statusless-banner', t: 'بدون وضعیت انتشار' },
      { id: 'paused-banner', status: 'paused', t: 'بنر متوقف' },
      { id: 'future-banner', status: 'published', startsAt: future, t: 'هنوز فعال نشده' },
      { id: 'expired-banner', status: 'published', endsAt: past, t: 'زمانش گذشته' },
      { id: 'unsafe-link-banner', status: 'published', t: 'پیوند ناامن', href: '//outside.test/path', primaryLabel: 'بیرونی' }
    ]
  }
};
const dom = new JSDOM('<!doctype html><html><body></body></html>', {
  url: 'https://nora.test/home.html',
  runScripts: 'dangerously',
  beforeParse(window) {
    window.fetch = async path => {
      assert.equal(path, '/api/public/site-content');
      return { ok: true, json: async () => payload };
    };
  }
});
Object.defineProperty(dom.window.document, 'readyState', { configurable: true, value: 'complete' });
dom.window.eval(source);
await dom.window.NORA_PUBLIC_READY;

assert.equal(dom.window.NORA_PUBLIC_SOURCE, 'server');
assert.deepEqual(Array.from(dom.window.NORA_PUBLIC.banners, banner => banner.id), ['unsafe-link-banner', 'live-banner'],
  'the explicit order field is applied before title tie-breaking');
const live = dom.window.NORA_PUBLIC.banners.find(banner => banner.id === 'live-banner');
assert.equal(live.t, 'اعلام برنامه');
assert.equal(live.s, 'جزئیات کوتاه');
assert.equal(live.href, '');
assert.equal(live.primaryLabel, '');
assert.equal(live.secondaryHref, '/events.html#upcoming');
assert.equal(live.theme, 'ocean');
assert.equal(live.layout, 'cover');
assert.equal(live.align, 'center');
assert.equal(live.overlay, 90);
assert.equal(live.focusX, 0);
assert.equal(live.focusY, 100);
assert.deepEqual(JSON.parse(JSON.stringify(dom.window.NORA_PUBLIC.bannerSettings)), {
  enabled: false, auto_rotate: true, interval_seconds: 20, show_controls: false
});
assert.equal(dom.window.NORA.BANNERS.length, 2);

dom.window.close();
console.log('public-data-banner: publication filtering, schedules, safe CTAs, and rotation settings passed');
