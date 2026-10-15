// بررسی فهرست بخش‌های حساب: هر بخش باید در طراحی تأییدشده باشد، و فقط بخش‌های دارای endpoint فعال باشند.
import fs from 'node:fs';
import assert from 'node:assert/strict';

const src = fs.readFileSync(new URL('./account.js', import.meta.url), 'utf8');
const block = src.slice(src.indexOf('const ACCOUNT_SCREENS=['), src.indexOf('function accountScreensCard'));
const entries = [...block.matchAll(/\{n:'([^']+)'(?:,h:'([^']*)')?\}/g)].map(m => ({ n: m[1], h: m[2] || '' }));

assert.equal(entries.length, 37, 'فهرست بخش‌های حساب باید ۳۷ مورد از بخش‌های حساب طراحی باشد');
const names = new Set(entries.map(e => e.n));
assert.equal(names.size, entries.length, 'نام بخش‌ها نباید تکراری باشد');
const live = entries.filter(e => e.h).map(e => e.n).sort();
assert.deepEqual(live, ['اعلان‌ها', 'رویدادهای من'], 'فقط بخش‌های دارای endpoint واقعی باید فعال باشند');
const proto = fs.readFileSync(new URL('../../../prototype-34-user.html', import.meta.url), 'utf8');
for (const e of entries) assert.ok(proto.includes(e.n), `«${e.n}» باید در طراحی prototype-34-user باشد`);
console.log(`account-screens: ${entries.length} بخش، ${live.length} فعال، ${entries.length - live.length} در دست ساخت`);
