// بررسی فهرست بخش‌های حساب: هر بخش باید در طراحی تأییدشده باشد، و فقط بخش‌های دارای endpoint فعال باشند.
import fs from 'node:fs';
import assert from 'node:assert/strict';

const src = fs.readFileSync(new URL('./account.js', import.meta.url), 'utf8');
const block = src.slice(src.indexOf('const ACCOUNT_SCREENS=['), src.indexOf('function accountScreensCard'));
const entries = [...block.matchAll(/\{n:'([^']+)'(?:,h:'([^']*)')?\}/g)].map(m => ({ n: m[1], h: m[2] || '' }));

assert.equal(entries.length, 54, 'فهرست باید همه‌ی ۵۴ صفحهٔ طراحی prototype-34-user را داشته باشد');
const names = new Set(entries.map(e => e.n));
assert.equal(names.size, entries.length, 'نام بخش‌ها نباید تکراری باشد');
const live = entries.filter(e => e.h).map(e => e.n).sort();
assert.deepEqual(live, ['اعلان‌ها', 'حساب من', 'رویدادهای من'], 'فقط بخش‌های دارای endpoint واقعی باید فعال باشند');
assert.equal(new Set(entries.map(e=>e.n)).size, 54, 'هر صفحهٔ طراحی یک بار');
const protoUrl = new URL('../../../prototype-34-user.html', import.meta.url);
if (fs.existsSync(protoUrl)) {
  const proto = fs.readFileSync(protoUrl, 'utf8');
  for (const e of entries) assert.ok(proto.includes(e.n), `«${e.n}» باید در طراحی prototype-34-user باشد`);
} else {
  console.log('هشدار: prototype-34-user.html کنار این نسخه نیست؛ بررسی نام‌ها با طراحی در مخزن اصلی انجام می‌شود.');
}
console.log(`account-screens: ${entries.length} بخش، ${live.length} فعال، ${entries.length - live.length} در دست ساخت`);
