// Portable runner: npm run test:nora; no shell glob or /tmp dependencies.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const uiRoot = path.resolve(__dirname, '..');
const suites = fs.readdirSync(uiRoot).filter(name => name.endsWith('.test.mjs')).sort();
if (!suites.length) {
  console.error('No Nora test suites were found.');
  process.exit(2);
}
let failed = 0;
for (const suite of suites) {
  console.log(`\n=== ${suite} ===`);
  const child = spawnSync(process.execPath, ['--max-old-space-size=3072', path.join(uiRoot, suite)], {
    cwd: uiRoot,
    stdio: 'inherit',
    env: { ...process.env, BOT_TOKEN: '', NORA_BOT_SERVICE_TOKEN: '', SAFIR_API_KEY: '' }
  });
  if (child.error || child.status !== 0) {
    failed++;
    console.error(`FAIL ${suite}${child.error ? ': could not launch Node' : ''}`);
  } else {
    console.log(`PASS ${suite}`);
  }
}
console.log(`\nNora suites: ${suites.length - failed}/${suites.length} passed; ${failed} failed.`);
process.exitCode = failed ? 1 : 0;
