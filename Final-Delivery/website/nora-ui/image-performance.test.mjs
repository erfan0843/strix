import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const UI_SOURCE = fs.readFileSync(path.join(ROOT, 'ui.js'), 'utf8');

function makeGif(frames = 2) {
  const bytes = [71, 73, 70, 56, 57, 97, 1, 0, 1, 0, 0, 0, 0];
  for (let frame = 0; frame < frames; frame++) {
    bytes.push(0x2c, 0, 0, 0, 0, 1, 0, 1, 0, 0, 2, 1, frame, 0);
  }
  bytes.push(0x3b);
  return new Uint8Array(bytes);
}

function boot({ outputType = 'image/webp', width = 2400, height = 1200 } = {}) {
  const dom = new JSDOM('<!doctype html><html><body><main id="page"></main></body></html>', {
    url: 'https://nora.test/admin.html',
    pretendToBeVisual: true,
    runScripts: 'dangerously'
  });
  const { window } = dom;
  Object.defineProperty(window.document, 'readyState', { configurable: true, value: 'complete' });
  window.scrollTo = () => {};
  window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {} });
  window.NORA = {};

  let canvasOptions = null;
  let requestedType = '';
  let requestedQuality = null;
  let bitmapClosed = false;
  window.createImageBitmap = async () => ({ width, height, close() { bitmapClosed = true; } });
  window.HTMLCanvasElement.prototype.getContext = function getContext(_type, options) {
    canvasOptions = options;
    return { drawImage() {} };
  };
  window.HTMLCanvasElement.prototype.toBlob = function toBlob(callback, type, quality) {
    requestedType = type;
    requestedQuality = quality;
    callback(new window.Blob(['webp-image'], { type: outputType }));
  };
  window.eval(UI_SOURCE);

  return {
    dom,
    window,
    ui: window.NORA_UI,
    getCanvasOptions: () => canvasOptions,
    getRequestedType: () => requestedType,
    getRequestedQuality: () => requestedQuality,
    getBitmapClosed: () => bitmapClosed
  };
}

function imageFile(window, name, type, bytes = new Uint8Array([1, 2, 3, 4])) {
  const file = new window.File([bytes], name, { type });
  Object.defineProperty(file, 'arrayBuffer', {
    configurable: true,
    value: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength)
  });
  return file;
}

test('static image uploads are resized to verified WebP and preserve transparent canvas output', async () => {
  const env = boot();
  try {
    const png = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 0]);
    const file = imageFile(env.window, 'portrait.png', 'image/png', png);
    const result = await env.ui.imageToWebPDataURL(file, { maxEdge: 1200, quality: 0.88 });

    assert.equal(result.type, 'image/webp');
    assert.equal(result.name, 'portrait.webp');
    assert.equal(result.width, 1200);
    assert.equal(result.height, 600);
    assert.match(result.dataUrl, /^data:image\/webp;base64,/);
    assert.equal(env.getRequestedType(), 'image/webp');
    assert.equal(env.getRequestedQuality(), 0.88);
    assert.equal(env.getCanvasOptions().alpha, true);
    assert.equal(env.getBitmapClosed(), true);
    assert.equal(env.ui.imageOptimizationStats().count, 1);
  } finally {
    env.dom.window.close();
  }
});

test('animated GIF, APNG, WebP, AVIF, HEIC, JPEG XL, and SVG inputs are rejected instead of losing motion', async () => {
  const env = boot();
  try {
    const apng = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 8, 97, 99, 84, 76, 0, 0, 0, 0]);
    const webp = new Uint8Array([82, 73, 70, 70, 12, 0, 0, 0, 87, 69, 66, 80, 65, 78, 73, 77, 0, 0, 0, 0]);
    const avif = new Uint8Array([0, 0, 0, 20, 102, 116, 121, 112, 97, 118, 105, 115, 0, 0, 0, 0, 97, 118, 105, 102]);
    const heic = new Uint8Array([0, 0, 0, 20, 102, 116, 121, 112, 104, 101, 118, 99, 0, 0, 0, 0, 104, 101, 105, 99]);
    const jxl = new TextEncoder().encode('JXL container jxli animation frames');
    const svg = new TextEncoder().encode('<svg><style>@keyframes spin{to{transform:rotate(360deg)}}</style></svg>');
    const svgInline = new TextEncoder().encode('<svg><g style="animation: spin 2s infinite"/></svg>');
    const fixtures = [
      imageFile(env.window, 'animation.gif', 'image/gif', makeGif(2)),
      imageFile(env.window, 'animation.png', 'image/png', apng),
      imageFile(env.window, 'animation.webp', 'image/webp', webp),
      imageFile(env.window, 'animation.avif', 'image/avif', avif),
      imageFile(env.window, 'animation.heic', 'image/heic', heic),
      imageFile(env.window, 'animation.jxl', 'image/jxl', jxl),
      imageFile(env.window, 'animation.svg', 'image/svg+xml', svg),
      imageFile(env.window, 'animation-inline.svg', 'image/svg+xml', svgInline)
    ];
    for (const file of fixtures)
      await assert.rejects(env.ui.imageToWebP(file), error => error.code === 'animated_image_not_supported', file.name);
    assert.equal(env.ui.imageOptimizationStats().count, 0);
  } finally {
    env.dom.window.close();
  }
});

test('browser PNG fallback is not mistaken for a successful WebP conversion', async () => {
  const env = boot({ outputType: 'image/png' });
  try {
    const file = imageFile(env.window, 'source.png', 'image/png', new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]));
    await assert.rejects(env.ui.imageToWebP(file), error => error.code === 'webp_unsupported');
    assert.equal(env.ui.imageOptimizationStats().count, 0);
  } finally {
    env.dom.window.close();
  }
});

test('the global loader waits only while navigation is pending and warns at ten real seconds', () => {
  const env = boot();
  try {
    const { window } = env;
    let now = 0;
    let nextId = 1;
    const timers = new Map();
    Object.defineProperty(window.performance, 'now', { configurable: true, value: () => now });
    window.setTimeout = (callback, delay = 0) => {
      const id = nextId++;
      timers.set(id, { id, callback, at: now + Math.max(0, Number(delay) || 0), interval: 0 });
      return id;
    };
    window.setInterval = (callback, delay = 0) => {
      const id = nextId++;
      const interval = Math.max(1, Number(delay) || 1);
      timers.set(id, { id, callback, at: now + interval, interval });
      return id;
    };
    window.clearTimeout = id => timers.delete(id);
    window.clearInterval = id => timers.delete(id);
    const advance = amount => {
      const target = now + amount;
      while (true) {
        const due = [...timers.values()].filter(timer => timer.at <= target).sort((a, b) => a.at - b.at || a.id - b.id)[0];
        if (!due) break;
        now = due.at;
        if (due.interval) due.at += due.interval;
        else timers.delete(due.id);
        due.callback();
      }
      now = target;
    };

    Object.defineProperty(window.document, 'readyState', { configurable: true, value: 'loading' });
    env.ui.initPageLoader();
    const loader = window.document.getElementById('noraPageLoader');
    advance(199);
    assert.equal(loader.hidden, true);
    advance(1);
    assert.equal(loader.hidden, false);
    assert.equal(window.document.body.getAttribute('aria-busy'), 'true');
    advance(9_799);
    assert.equal(loader.querySelector('[data-loader-warning]').hidden, true);
    advance(1);
    assert.equal(loader.querySelector('[data-loader-warning]').hidden, false);
    assert.equal(loader.querySelector('[data-loader-seconds]').textContent, '۰۰:۱۰');
    env.ui.savePerformanceSettings({ loaderEnabled: false });
    assert.equal(loader.hidden, true);
    assert.equal(window.document.body.hasAttribute('aria-busy'), false);
    env.ui.savePerformanceSettings({ loaderEnabled: true });
    advance(0);
    assert.equal(loader.hidden, false);
    window.dispatchEvent(new window.Event('load'));
    assert.equal(loader.hidden, true);
    assert.equal(window.document.body.hasAttribute('aria-busy'), false);
  } finally {
    env.dom.window.close();
  }
});

test('performance settings persist safely and the shared loader makes the page inert', () => {
  const env = boot();
  try {
    const snapshot = env.ui.performanceSnapshot();
    assert.equal(snapshot.lcp, null);
    assert.equal(snapshot.cls, null);
    assert.equal(snapshot.inp, null);
    assert.equal(snapshot.longTaskCount, null);
    assert.equal(snapshot.longTaskMs, null);
    const settings = env.ui.savePerformanceSettings({ loaderDelayMs: 500, imageQuality: 87, maxImageEdge: 1200 });
    assert.deepEqual(JSON.parse(JSON.stringify(settings)), { loaderEnabled: true, loaderDelayMs: 500, imageQuality: 87, maxImageEdge: 1200 });
    assert.deepEqual(JSON.parse(JSON.stringify(env.ui.performanceSettings())), JSON.parse(JSON.stringify(settings)));

    const page = env.window.document.getElementById('page');
    page.innerHTML = '<button id="focusTarget">بازگشت</button>';
    const focusTarget = env.window.document.getElementById('focusTarget');
    const loader = env.window.document.getElementById('noraPageLoader');
    assert.ok(loader);
    assert.equal(loader.hidden, true);
    focusTarget.focus();
    env.ui.showPageLoader();
    assert.equal(loader.hidden, false);
    assert.equal(env.window.document.body.getAttribute('aria-busy'), 'true');
    assert.equal(page.hasAttribute('inert'), true);
    assert.equal(env.window.document.activeElement, loader);
    assert.ok(loader.querySelector('[data-loader-warning]').hidden);
    env.ui.hidePageLoader();
    assert.equal(loader.hidden, true);
    assert.equal(env.window.document.body.hasAttribute('aria-busy'), false);
    assert.equal(page.hasAttribute('inert'), false);
    assert.equal(env.window.document.activeElement, focusTarget);
  } finally {
    env.dom.window.close();
  }
});
