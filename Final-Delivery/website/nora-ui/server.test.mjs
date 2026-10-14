import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
let child;
let base;
let logs = '';

before(async () => {
  child = spawn(process.execPath, ['server.mjs'], {
    cwd: ROOT,
    env: {
      ...process.env,
      HOST: '127.0.0.1',
      PORT: '0',
      NORA_PUBLIC_BASE_URL: 'https://www.nora.example.org',
      NORA_BALE_BOT_TOKEN: 'test-secret-must-never-leak'
    },
    stdio: ['ignore', 'pipe', 'pipe']
  });
  child.stdout.setEncoding('utf8');
  child.stderr.setEncoding('utf8');
  const collect = chunk => { logs += chunk; };
  child.stdout.on('data', collect);
  child.stderr.on('data', collect);
  const started = new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`server startup timed out: ${logs}`)), 5000);
    const check = chunk => {
      const match = (logs + chunk).match(/listening on http:\/\/127\.0\.0\.1:(\d+)/);
      if (match) {
        clearTimeout(timer);
        child.stdout.off('data', check);
        resolve(Number(match[1]));
      }
    };
    child.stdout.on('data', check);
    child.once('error', error => { clearTimeout(timer); reject(error); });
    child.once('exit', code => { clearTimeout(timer); reject(new Error(`server exited ${code}: ${logs}`)); });
  });
  const port = await started;
  base = `http://127.0.0.1:${port}`;
});

after(async () => {
  if (child && child.exitCode === null) {
    child.kill('SIGTERM');
    await Promise.race([once(child, 'exit'), new Promise(resolve => setTimeout(resolve, 2000))]);
  }
});

test('serves the local app and excludes server implementation files', async () => {
  const home = await fetch(`${base}/home.html`);
  assert.equal(home.status, 200);
  assert.match(home.headers.get('content-type') || '', /text\/html/);
  assert.equal(home.headers.get('x-content-type-options'), 'nosniff');
  const homeHtml = await home.text();
  assert.match(homeHtml, /Nora|نورا/);
  assert.match(homeHtml, /<link rel="canonical" href="\/"\/>/);
  assert.match(homeHtml, /<h1/);
  const schema = homeHtml.match(/<script id="nora-structured-data" type="application\/ld\+json">([\s\S]*?)<\/script>/);
  assert.ok(schema, 'homepage includes static JSON-LD');
  const graph = JSON.parse(schema[1])['@graph'];
  assert.ok(graph.some(item => item['@type'] === 'Organization'));
  assert.ok(graph.some(item => item['@type'] === 'WebSite'));

  for (const [asset, contentType] of [
    ['favicon.svg', /image\/svg\+xml/], ['favicon.ico', /image\/x-icon/], ['icon-192.png', /image\/png/],
    ['nora-mark-mini.svg', /image\/svg\+xml/], ['404-art.png', /image\/png/],
    ['fonts/Vazirmatn-UI-FD-Regular.woff2', /font\/woff2/], ['fonts/Estedad-Variable.woff2', /font\/woff2/]
  ]) {
    const icon = await fetch(`${base}/${asset}`);
    assert.equal(icon.status, 200);
    assert.match(icon.headers.get('content-type') || '', contentType);
  }

  assert.equal((await fetch(`${base}/server.mjs`)).status, 404);
  assert.equal((await fetch(`${base}/integrations.mjs`)).status, 404);
  assert.equal((await fetch(`${base}/missing.js`)).status, 404);
});

test('uses only the configured HTTPS origin for canonical tags and crawl metadata', async () => {
  const origin = 'https://www.nora.seo-test-domain';
  const configured = spawn(process.execPath, ['server.mjs'], {
    cwd: ROOT,
    env: { ...process.env, HOST: '127.0.0.1', PORT: '0', NORA_PUBLIC_BASE_URL: origin },
    stdio: ['ignore', 'pipe', 'pipe']
  });
  let configuredLogs = '';
  configured.stdout.setEncoding('utf8');
  configured.stderr.setEncoding('utf8');
  const onStdout = chunk => { configuredLogs += chunk; };
  const onStderr = chunk => { configuredLogs += chunk; };
  configured.stdout.on('data', onStdout);
  configured.stderr.on('data', onStderr);
  const port = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`configured server startup timed out: ${configuredLogs}`)), 5000);
    const check = chunk => {
      configuredLogs += chunk;
      const match = configuredLogs.match(/listening on http:\/\/127\.0\.0\.1:(\d+)/);
      if (match) {
        clearTimeout(timer);
        configured.stdout.off('data', check);
        resolve(Number(match[1]));
      }
    };
    configured.stdout.off('data', onStdout);
    configured.stdout.on('data', check);
    configured.once('error', error => { clearTimeout(timer); reject(error); });
    configured.once('exit', code => { clearTimeout(timer); reject(new Error(`configured server exited ${code}: ${configuredLogs}`)); });
  });

  try {
    const configuredBase = `http://127.0.0.1:${port}`;
    const home = await fetch(`${configuredBase}/home.html`, { headers: { host: 'attacker.example' } });
    assert.equal(home.status, 200);
    const homeHtml = await home.text();
    assert.ok(homeHtml.includes(`<link rel="canonical" href="${origin}/"/>`));
    assert.doesNotMatch(homeHtml, /attacker\.example/);

    const events = await fetch(`${configuredBase}/events.html`, { headers: { host: 'attacker.example' } });
    const eventsHtml = await events.text();
    assert.equal(events.status, 200);
    assert.ok(eventsHtml.includes(`<link rel="canonical" href="${origin}/events.html"/>`));
    assert.doesNotMatch(eventsHtml, /attacker\.example/);

    const robots = await fetch(`${configuredBase}/robots.txt`);
    assert.ok((await robots.text()).includes(`Sitemap: ${origin}/sitemap.xml`));
    const sitemap = await fetch(`${configuredBase}/sitemap.xml`);
    const sitemapText = await sitemap.text();
    assert.equal(sitemap.status, 200);
    assert.ok(sitemapText.includes(`${origin}/`));
    assert.ok(sitemapText.includes(`${origin}/events.html`));
    assert.doesNotMatch(sitemapText, /attacker\.example/);
  } finally {
    if (configured.exitCode === null) {
      configured.kill('SIGTERM');
      await Promise.race([once(configured, 'exit'), new Promise(resolve => setTimeout(resolve, 2000))]);
      if (configured.exitCode === null) configured.kill('SIGKILL');
    }
  }
});

test('rejects a reserved sample origin and serves robots, llms, and a fail-closed sitemap', async () => {
  const robots = await fetch(`${base}/robots.txt`);
  assert.equal(robots.status, 200);
  const robotsText = await robots.text();
  assert.match(robotsText, /Disallow: \/api\//);
  assert.doesNotMatch(robotsText, /Disallow: \/form\.html/);
  assert.doesNotMatch(robotsText, /^Sitemap:/m);

  const llms = await fetch(`${base}/llms.txt`);
  assert.equal(llms.status, 200);
  assert.match(await llms.text(), /رویدادها/);

  const sitemap = await fetch(`${base}/sitemap.xml`);
  assert.equal(sitemap.status, 503);
  assert.match(sitemap.headers.get('content-type') || '', /text\/plain/);
  assert.doesNotMatch(await sitemap.text(), /https:\/\//);

  const missing = await fetch(`${base}/not-a-real-page.html`);
  assert.equal(missing.status, 404);
  assert.match(missing.headers.get('content-type') || '', /text\/html/);
  assert.equal(missing.headers.get('x-robots-tag'), 'noindex, nofollow');
  assert.match(await missing.text(), /<h1 id="page-title" class="art-title">صفحه پیدا نشد<\/h1>/);
});

test('compresses static code, revalidates pages, and keeps APIs uncacheable', async () => {
  const assetUrl = `${base}/admin.js?v=98`;
  const asset = await fetch(assetUrl, { headers: { 'accept-encoding': 'br' } });
  assert.equal(asset.status, 200);
  assert.equal(asset.headers.get('content-encoding'), 'br');
  assert.match(asset.headers.get('cache-control') || '', /immutable/);
  assert.match(asset.headers.get('vary') || '', /Accept-Encoding/i);
  assert.match(await asset.text(), /NORA/);

  const etag = asset.headers.get('etag');
  const cached = await fetch(assetUrl, { headers: { 'if-none-match': etag, 'accept-encoding': 'br' } });
  assert.equal(cached.status, 304);

  const page = await fetch(`${base}/home.html`);
  assert.match(page.headers.get('cache-control') || '', /no-cache/);
  const health = await fetch(`${base}/api/health`);
  assert.equal(health.headers.get('cache-control'), 'no-store');
});

test('publishes safe integration state and a fixed channel policy, never secrets', async () => {
  const response = await fetch(`${base}/api/integrations/status`);
  assert.equal(response.status, 200);
  const text = await response.text();
  const status = JSON.parse(text);
  assert.equal(status.deliveryEnabled, false);
  assert.equal(status.queueEnabled, false);
  assert.equal(status.sendAttempted, false);
  assert.deepEqual(status.policy.certificate, ['bale']);
  assert.deepEqual(status.policy.ticket, ['bale']);
  assert.deepEqual(status.policy.notification, ['bale', 'eitaa']);
  assert.equal(status.serverScope, 'same-application');
  const bale = status.providers.find(provider => provider.id === 'bale');
  const eitaa = status.providers.find(provider => provider.id === 'eitaa');
  assert.equal(bale.connectionModel, 'bot-token-plus-mini-app');
  assert.equal(bale.credentialScope, 'same-application-server');
  assert.equal(eitaa.connectionModel, 'mini-app-only');
  assert.equal(eitaa.credentialScope, 'none-in-this-scaffold');
  assert.equal(eitaa.connected, false);
  assert.doesNotMatch(text, /test-secret-must-never-leak|NORA_(?:BALE|EITAA)_BOT_TOKEN|apiKey/i);
});

test('accepts valid policy-shaped drafts only as disabled, unqueued outbox attempts', async () => {
  const response = await fetch(`${base}/api/outbox`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ kind: 'certificate', channel: 'bale', format: 'jpg', ownerApproved: true })
  });
  assert.equal(response.status, 409);
  const result = await response.json();
  assert.equal(result.accepted, false);
  assert.equal(result.queued, false);
  assert.equal(result.dispatched, false);
  assert.equal(result.sendAttempted, false);

  const eitaaNotice = await fetch(`${base}/api/outbox`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ kind: 'notification', channel: 'eitaa' })
  });
  assert.equal(eitaaNotice.status, 409);
  const miniAppResult = await eitaaNotice.json();
  assert.equal(miniAppResult.queued, false);
  assert.equal(miniAppResult.dispatched, false);
  assert.equal(miniAppResult.sendAttempted, false);
});

test('rejects disallowed channels and all browser-supplied credential fields', async () => {
  const wrongChannel = await fetch(`${base}/api/outbox`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ kind: 'ticket', channel: 'eitaa', format: 'pdf' })
  });
  assert.equal(wrongChannel.status, 400);
  assert.equal((await wrongChannel.json()).error, 'channel_not_allowed');

  const credential = await fetch(`${base}/api/outbox`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ kind: 'notification', channel: 'bale', token: 'do-not-accept' })
  });
  assert.equal(credential.status, 400);
  assert.equal((await credential.json()).error, 'credentials_not_accepted');
});

test('requires JSON and rejects malformed payloads', async () => {
  const type = await fetch(`${base}/api/outbox`, { method: 'POST', body: 'plain text' });
  assert.equal(type.status, 415);
  const badJson = await fetch(`${base}/api/outbox`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: '{'
  });
  assert.equal(badJson.status, 400);
});
