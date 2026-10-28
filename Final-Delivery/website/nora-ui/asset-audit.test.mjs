import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { gzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const read = name => fs.readFileSync(path.join(root, name), 'utf8');

test('university snapshot is fetched only when a university picker needs it', () => {
  const form = read('form.html');
  const ui = read('ui.js');
  const builder = read('builder.html');
  const serviceWorker = read('sw.js');
  const snapshot = fs.readFileSync(path.join(root, 'universities-data.js'));

  assert.doesNotMatch(form, /<script\b[^>]*\bsrc=["']universities-data\.js/i,
    'the large snapshot must not block every form page load');
  for (const page of ['home.html', 'events.html', 'event.html', 'person.html', 'partner.html', 'post.html']) {
    const html = read(page);
    const staticMarkup = html.replace(/<script\b(?![^>]*\bsrc=)[^>]*>[\s\S]*?<\/script\s*>/gi, '');
    assert.doesNotMatch(staticMarkup, /<script\b[^>]*\bsrc=["']data\.js/i,
      `${page} must not download local sample fixtures for public traffic`);
    assert.match(html, /__NORA_TEST_FIXTURE_MODE__===true[\s\S]*data\.js\?v=99/,
      `${page} should retain the fixture script for explicit tests`);
  }
  assert.doesNotMatch(serviceWorker, /'data\.js'/,
    'the service-worker shell must not prefetch local sample fixtures');
  assert.match(ui, /script\.dataset\.noraUniversities='1'/,
    'the shared UI should mark its on-demand script request');
  /* نسخهٔ بستهٔ مشترک باید در همهٔ صفحه‌ها یکی و رو به جلو باشد.
     پیش‌تر عدد ثابتی (v=118) اینجا سنجیده می‌شد؛ با هر به‌روزرسانیِ بسته،
     سه فایل آزمون بی‌دلیل می‌شکست و در عوض اگر صفحه‌ای عقب می‌ماند ولی
     همان عدد ثابت را داشت، چیزی گرفته نمی‌شد. یکنواختی + سقفِ پایین همان
     قصد را برآورده می‌کند و عقب‌ماندن یک صفحه را واقعاً می‌گیرد. */
  const bundleVersions = new Map();
  for (const name of fs.readdirSync(root).filter(entry => entry.endsWith('.html'))) {
    const found = read(name).match(/<script src="ui\.js\?v=(\d+)"><\/script>/);
    if (found) bundleVersions.set(name, Number(found[1]));
  }
  assert.ok(bundleVersions.size >= 6,
    'the six public pages and every other page loading the shared bundle must be found');
  assert.equal(new Set(bundleVersions.values()).size, 1,
    `every page must request the same shared UI bundle version, got ${
      [...bundleVersions].map(([page, version]) => `${page}=v${version}`).join(', ')}`);
  assert.ok([...bundleVersions.values()][0] >= 122,
    'the shared UI bundle version must never go backwards');
  assert.match(ui, /loadUniversities\(\)\.then\(\(\)=>\{delete el\.dataset\.universitiesFailed;render\(\)\}\)/,
    'the picker must redraw after the asynchronous snapshot arrives');
  assert.doesNotMatch(serviceWorker, /'universities-data\.js'/,
    'the service-worker shell must not download the snapshot before it is needed');
  assert.match(builder, /__NORA_TEST_FIXTURE_MODE__===true\)document\.write\(/,
    'the builder should load sample data only when the explicit test-fixture flag is set');
  const builderScripts = [...builder.matchAll(/^[ \t]*<script\b[^>]*\bsrc=["']([^"']+)/gmi)].map(match => match[1]);
  assert.ok(!builderScripts.some(src => /^(?:data\.js|cert-font\.js)/i.test(src)),
    'the builder must not eagerly download test fixtures or certificate-only font payloads');
  assert.ok(Buffer.byteLength(ui) < 225_000, 'the shared UI bundle should stay under its raw-size budget');
  assert.ok(gzipSync(ui, { level: 9 }).length < 70_000,
    'the shared UI bundle should stay under its compressed transfer-size budget');
  assert.ok(snapshot.length < 260_000, 'the community snapshot should remain within its raw-size budget');
  assert.ok(gzipSync(snapshot, { level: 9 }).length < 35_000,
    'the compressed snapshot should remain within its transfer-size budget');
});

test('the custom 404 page gives visitors a direct, same-origin login route', () => {
  const notFound = read('404.html');
  assert.match(notFound, /href="\/login\.html\?mode=server&amp;next=account\.html">ورود\/ثبت‌نام<\/a>/,
    'the 404 page should link directly to the existing secure login flow');
  assert.match(notFound, /href="\/events\.html"/);
  assert.match(notFound, /href="\/support\.html"/);
});

test('rendered image templates all declare an alt attribute', () => {
  const files = fs.readdirSync(root).filter(name => /\.(?:html|js)$/.test(name) && !/\.test\./.test(name));
  const missing = [];
  let count = 0;
  for (const name of files) {
    const source = read(name);
    for (const match of source.matchAll(/<img\b([^>]*)>/gi)) {
      count++;
      if (!/\balt\s*=\s*(?:"[^"]*"|'[^']*')/i.test(match[1])) {
        missing.push(`${name}: ${match[0].slice(0, 140)}`);
      }
    }
  }
  assert.ok(count > 0, 'the audit should inspect image templates');
  assert.deepEqual(missing, [], `every image needs meaningful alt text or alt="" when decorative`);
});
