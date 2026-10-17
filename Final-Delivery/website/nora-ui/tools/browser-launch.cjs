// Shared headless-Chromium launcher for the optional browser QA scripts
// (development-only; never part of the application boot path).
//
// Resolution order:
//   NORA_QA_BROWSER=sparticuz            -> @sparticuz/chromium binary (Linux, no network needed)
//   NORA_QA_CHROMIUM_EXECUTABLE=/path    -> an existing Chromium/Chrome executable
//   NORA_QA_BROWSER_CHANNEL=chrome|msedge -> a locally installed channel
//   otherwise                            -> Playwright-managed Chromium
// Dependencies (playwright-core, @sparticuz/chromium) are resolved from
// NORA_QA_DEPENDENCIES or the repository root, exactly like browser-audit.cjs.
const path = require('node:path');
const os = require('node:os');
const fs = require('node:fs');
const { createRequire } = require('node:module');

const repoRoot = path.resolve(__dirname, '../../../..');
const dependencyRequire = process.env.NORA_QA_DEPENDENCIES
  ? createRequire(path.join(path.resolve(process.env.NORA_QA_DEPENDENCIES), 'package.json'))
  : createRequire(path.join(repoRoot, 'package.json'));
const { chromium: pw } = dependencyRequire('playwright-core');

function localOrigin(value) {
  const url = new URL(value);
  if (!['http:', 'https:'].includes(url.protocol) || !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)
      || url.username || url.password || url.search || url.hash || url.pathname !== '/') {
    throw new Error('Browser QA requires a loopback origin, never a live external target.');
  }
  return url.origin;
}

async function launchBrowser() {
  if (process.env.NORA_QA_BROWSER === 'sparticuz') {
    const mod = dependencyRequire('@sparticuz/chromium');
    const chromium = mod.default || mod;
    if (process.platform !== 'linux') throw new Error('Sparticuz fallback is Linux-only; use managed Chromium or a local Chrome executable.');
    const moduleRoot = path.resolve(path.dirname(dependencyRequire.resolve('@sparticuz/chromium')), '..');
    const { inflate } = await import(require('node:url').pathToFileURL(path.join(moduleRoot, 'build/lambdafs.js')).href);
    await inflate(path.join(moduleRoot, 'bin/al2023.tar.br'));
    const executablePath = await chromium.executablePath();
    const env = { ...process.env };
    const libraries = path.join(os.tmpdir(), 'al2023/lib');
    if (fs.existsSync(libraries)) env.LD_LIBRARY_PATH = [libraries, env.LD_LIBRARY_PATH].filter(Boolean).join(path.delimiter);
    const fonts = path.join(os.tmpdir(), 'fonts');
    if (fs.existsSync(fonts)) env.FONTCONFIG_PATH = fonts;
    // --single-process: closing a context would take the whole browser down; keep one context per browser instead.
    return pw.launch({ executablePath, headless: true, env,
      args: chromium.args.filter(arg => !['--disable-web-security', '--allow-running-insecure-content'].includes(arg)) });
  }
  return pw.launch({ headless: true,
    ...(process.env.NORA_QA_CHROMIUM_EXECUTABLE ? { executablePath: process.env.NORA_QA_CHROMIUM_EXECUTABLE } : {}),
    ...(process.env.NORA_QA_BROWSER_CHANNEL ? { channel: process.env.NORA_QA_BROWSER_CHANNEL } : {}) });
}

module.exports = { launchBrowser, localOrigin, dependencyRequire, repoRoot };
