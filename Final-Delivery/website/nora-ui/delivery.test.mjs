/* آزمون مسیر تحویل فایل‌ها از بات بله و پخش بدون دانلود رسانهٔ ضبط‌شده. */
import {fileURLToPath,pathToFileURL} from 'node:url';
import jsdom from 'jsdom';
import fs from 'node:fs';
import path from 'node:path';
import { strict as assert } from 'node:assert';

const { JSDOM } = jsdom;
const DIR = fileURLToPath(new URL('./',import.meta.url));
const PDF = 'data:application/pdf;base64,JVBERi0xLjcKZmlsZQ==';
const AUDIO = 'data:audio/mpeg;base64,AAECAwQFBgc=';
const FILE_IDS = {
  event: 'a'.repeat(32), article: 'b'.repeat(32), book: 'c'.repeat(32)
};
const snapshot = {
  events: [{
    id: 'delivery-event', t: 'آرشیو رویداد', past: true, privacy: 'public',
    media: [
      { id: 'event-pdf', k: 'pdf', t: 'جزوهٔ جلسه', file_name: 'session.pdf',
        mime: 'application/pdf', src: PDF, available: true, delivery_id: FILE_IDS.event },
      { id: 'event-audio', k: 'audio', t: 'ضبط صوتی', mime: 'audio/mpeg', src: AUDIO },
      { id: 'event-join', k: 'link', t: 'پیوند ورود آنلاین', src: 'https://meet.example.org/room' }
    ]
  }],
  people: [], partners: [], banners: [], cooperation: [],
  articles: [{
    id: 'delivery-article', t: 'مطلب پیوست‌دار', cat: 'راهنما', who: 'تحریریه', pub: true,
    blocks: [
      { ty: 'file', t: 'راهنمای PDF', file_name: 'guide.pdf', content_type: 'application/pdf',
        content_size: 12, available: true, delivery_id: FILE_IDS.article, file_data: PDF },
      { ty: 'aud', cap: 'صدای داخل مطلب', src: AUDIO }
    ]
  }],
  library: [
    { id: 'delivery-book', t: 'کتاب باشگاه', kind: 'کتاب', file_name: 'book.pdf',
      content_type: 'application/pdf', content_size: 12, available: true,
      delivery_id: FILE_IDS.book, file_data: PDF },
    { id: 'delivery-audio', t: 'صدای باشگاه', kind: 'صدا', mime: 'audio/mpeg', src: AUDIO }
  ]
};
const response = payload => ({ ok: true, status: 200, json: async () => payload });
const serverPayload = { content: snapshot, delivery_bot_url: 'https://ble.ir/nora_test_bot' };
const store = () => {
  const values = new Map();
  return {
    getItem: key => values.has(key) ? values.get(key) : null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: key => values.delete(key), clear: () => values.clear(),
    key: index => [...values.keys()][index], get length() { return values.size; }
  };
};

const HOST_ORIGIN = 'http://nora.test';
async function load(file, query = '', hosted = false) {
  const errors = [];
  const pageUrl = (hosted ? HOST_ORIGIN + '/' + file : pathToFileURL(DIR + file).href) + query;
  const dom = await JSDOM.fromFile(DIR + file, {
    runScripts: 'dangerously', resources: {
      interceptors: [jsdom.requestInterceptor(request => {
        const requestUrl = new URL(request.url);
        if (hosted && requestUrl.origin === HOST_ORIGIN) {
          const localPath = path.join(DIR, decodeURIComponent(requestUrl.pathname.slice(1)));
          if (fs.existsSync(localPath) && fs.statSync(localPath).isFile()) {
            const type = ({ '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
              '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg' })[path.extname(localPath)]
              || 'application/octet-stream';
            return new Response(fs.readFileSync(localPath), { status: 200, headers: { 'content-type': type } });
          }
          return new Response('', { status: 404, headers: { 'content-type': 'text/plain' } });
        }
        return /^https?:/i.test(request.url)
          ? new Response('', { status: 200, headers: { 'content-type': 'text/html;charset=utf-8' } }) : undefined;
      })]
    },
    pretendToBeVisual: true,
    url: pageUrl,
    beforeParse(window) {
      window.scrollTo = () => {};
      if (!window.matchMedia) window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {} });
      Object.defineProperty(window, 'localStorage', { configurable: true, value: store() });
      window.fetch = async requestPath => String(requestPath) === '/api/public/site-content'
        ? response(serverPayload) : { ok: false, status: 404, json: async () => ({}) };
      window.addEventListener('error', event => errors.push(event.message || 'script error'));
      window.console.error = (...args) => errors.push(args.join(' '));
      window.onerror = message => errors.push(String(message));
    }
  });
  const { window } = dom;
  if (window.document.readyState !== 'complete') {
    await new Promise(resolve => {
      const timer = setTimeout(resolve, 5000);
      window.addEventListener('load', () => { clearTimeout(timer); resolve(); }, { once: true });
    });
  }
  await window.NORA_PUBLIC_READY;
  await new Promise(resolve => setTimeout(resolve, 20));
  if (file === 'home.html') {
    for (let attempt = 0; attempt < 100 && !window.NORA_HOME; attempt++)
      await new Promise(resolve => setTimeout(resolve, 10));
  }
  return { dom, window, document: window.document, errors };
}

const eventPage = await load('event.html', '?id=delivery-event');
assert.deepEqual(eventPage.errors, []);
assert.equal(eventPage.window.NORA.BALE_BOT_URL, 'https://ble.ir/nora_test_bot');
assert.equal(eventPage.window.NORA.PAST[0].media[0].src, '');
assert.equal(eventPage.window.NORA.PAST[0].media[0].file_data, undefined);
const eventDownload = [...eventPage.document.querySelectorAll('a.local-disabled-link')]
  .find(link => link.textContent.includes('جزوهٔ جلسه'));
assert.ok(eventDownload && !eventDownload.hasAttribute('href'), 'file:// preview keeps the bot link visibly inactive');
assert.equal(eventPage.window.NORA_UI.baleStartHref('file_' + FILE_IDS.event),
  'https://ble.ir/nora_test_bot?start=file_' + FILE_IDS.event, 'event file address is built for direct Bale delivery');
const localJoin = [...eventPage.document.querySelectorAll('a.local-disabled-link')]
  .find(link => link.textContent.includes('پیوند ورود آنلاین'));
assert.ok(localJoin && !localJoin.hasAttribute('href'), 'file:// preview never activates a published external entry link');
assert.ok(!eventPage.document.querySelector('a[download],a[href^="data:application/"]'));
assert.equal(eventPage.document.querySelector('.event-media-player audio')?.getAttribute('controlsList'), 'nodownload');
assert.ok(eventPage.document.querySelector('.event-media-player audio')?.getAttribute('src').startsWith('data:audio/'));
eventPage.dom.window.close();

const hostedEventPage = await load('event.html', '?id=delivery-event', true);
assert.deepEqual(hostedEventPage.errors, []);
assert.equal(hostedEventPage.window.location.protocol, 'http:');
assert.equal(hostedEventPage.window.NORA_PUBLIC_SOURCE, 'server');
assert.ok(hostedEventPage.document.querySelector('a[href="https://ble.ir/nora_test_bot?start=file_' + FILE_IDS.event + '"]'),
  'on the hosted HTTP origin, an attachment opens the Bale bot');
const hostedJoin = hostedEventPage.document.querySelector('a[href="https://meet.example.org/room"]');
assert.ok(hostedJoin && !hostedJoin.classList.contains('local-disabled-link'),
  'on the hosted HTTP origin, the published online entry link stays active');
hostedEventPage.dom.window.close();

const postPage = await load('post.html', '?id=delivery-article');
assert.deepEqual(postPage.errors, []);
const articleDownload = postPage.document.querySelector('.pb-file.local-disabled-link');
assert.ok(articleDownload && !articleDownload.hasAttribute('href'), 'file:// preview guards the article bot link too');
assert.equal(postPage.window.NORA_UI.baleStartHref('file_' + FILE_IDS.article),
  'https://ble.ir/nora_test_bot?start=file_' + FILE_IDS.article);
assert.ok(!postPage.document.querySelector('a[download],a[href^="data:application/"]'));
assert.equal(postPage.document.querySelector('.pb-aud audio')?.getAttribute('controlsList'), 'nodownload');
assert.ok(postPage.document.querySelector('.pb-aud audio')?.getAttribute('src').startsWith('data:audio/'));
postPage.dom.window.close();

const homePage = await load('home.html');
assert.deepEqual(homePage.errors, []);
assert.equal(typeof homePage.window.NORA_HOME?.clubLib, 'function');
const libraryHtml = homePage.window.NORA_HOME.clubLib();
assert.ok(libraryHtml.includes('https://ble.ir/nora_test_bot?start=file_' + FILE_IDS.book));
assert.ok(libraryHtml.includes('دریافت در بات بله'));
assert.ok(libraryHtml.includes('controlsList="nodownload"'));
assert.ok(!libraryHtml.includes('download=') && !libraryHtml.includes(PDF));
assert.ok(libraryHtml.includes(AUDIO), 'published club audio stays playable');
homePage.dom.window.close();

console.log('✓ event, article, and library files route to Bale; recordings remain playable without a download action.');
