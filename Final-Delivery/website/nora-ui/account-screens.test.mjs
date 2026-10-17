// بررسی فهرست بخش‌های حساب: هر بخش باید در طراحی تأییدشده باشد و وضعیت نسخهٔ اول آن صریح باشد
// (مقصد واقعی / مرحلهٔ روند ثبت‌نام / فعلاً در ربات بله / خارج از نسخهٔ اول). هیچ بخشی دادهٔ نمونه نمی‌گیرد.
import fs from 'node:fs';
import assert from 'node:assert/strict';

const src = fs.readFileSync(new URL('./account.js', import.meta.url), 'utf8');
const block = src.slice(src.indexOf('const ACCOUNT_SCREENS=['), src.indexOf('const ACCOUNT_SCREEN_STATUS='));
const entries = [...block.matchAll(/\{n:'([^']+)'(?:,h:'([^']*)')?(?:,st:'([a-z]+)')?\}/g)]
  .map(m => ({ n: m[1], h: m[2], st: m[3] || (m[2] !== undefined ? 'page' : '') }));

assert.equal(entries.length, 54, 'فهرست باید همه‌ی ۵۴ صفحهٔ طراحی prototype-34-user را داشته باشد');
assert.equal(new Set(entries.map(e => e.n)).size, 54, 'نام بخش‌ها نباید تکراری باشد');
for (const e of entries) assert.ok(['page', 'flow', 'bot', 'later'].includes(e.st), `«${e.n}» باید وضعیت نسخهٔ اول داشته باشد`);

const by = st => entries.filter(e => e.st === st).map(e => e.n).sort();
assert.deepEqual(by('page'), [
  'اطلاعات حساب', 'اعلان‌ها', 'برگزارشده‌ها و آفلاین', 'تقویم رویدادها', 'جزئیات رویداد', 'حساب من', 'خانه', 'درباره ما',
  'رسید', 'رویدادها', 'رویدادهای من', 'سؤالات', 'فرم‌های من', 'قواعد و شرایط', 'ورود', 'پرداخت', 'پشتیبانی', 'پیام به کارشناس', 'پیام ربات'
].sort(), 'بخش‌های فعال وب فقط آن‌هایی هستند که مقصد واقعی دارند');
assert.deepEqual(by('flow'), ['تأیید', 'درگاه بله', 'فرم', 'همراه آوردن', 'پایان', 'کارت‌به‌کارت', 'یک قدم مانده'].sort(),
  'مرحله‌های روند ثبت‌نام از صفحهٔ رویداد آغاز می‌شوند');
assert.equal(by('bot').length, 17, 'بخش‌های «فعلاً در ربات بله»');
assert.equal(by('later').length, 11, 'بخش‌های مالی/محصولی خارج از نسخهٔ اول');
for (const n of ['کیف پول', 'اقساط من', 'اعتبار من', 'سررسید و صورت‌حساب', 'انتقال به دوست', 'کارت هدیه', 'افزایش و برداشت', 'امنیت و سقف‌ها', 'لینک پرداخت', 'خانهٔ نورا پی', 'خرید آفلاین'])
  assert.ok(by('later').includes(n), `«${n}» باید خارج از نسخهٔ اول باشد`);

// هر مقصد باید به صفحه‌ای موجود اشاره کند (نه نشانی بیرونی، نه صفحهٔ ناموجود)
const pages = new Set(fs.readdirSync(new URL('./', import.meta.url)).filter(f => f.endsWith('.html')));
for (const e of entries.filter(e => e.st === 'page' && e.h)) {
  const file = e.h.split(/[#?]/)[0];
  assert.ok(pages.has(file), `مقصد «${e.n}» (${e.h}) باید صفحهٔ موجودی باشد`);
}
// نماهای حساب که در مقصدها آمده‌اند باید در مسیریاب حساب شناخته شوند
const hashes = entries.filter(e => e.h && e.h.startsWith('account.html#')).map(e => e.h.slice('account.html#'.length));
for (const h of new Set(hashes)) {
  assert.ok(h === 'events' || h === 'notifications' || src.includes(`${h}:{k:'${h}'`), `نمای #${h} باید در حساب تعریف شده باشد`);
}

const protoUrl = new URL('../../../prototype-34-user.html', import.meta.url);
if (fs.existsSync(protoUrl)) {
  const proto = fs.readFileSync(protoUrl, 'utf8');
  for (const e of entries) assert.ok(proto.includes(e.n), `«${e.n}» باید در طراحی prototype-34-user باشد`);
} else {
  console.log('هشدار: prototype-34-user.html کنار این نسخه نیست؛ بررسی نام‌ها با طراحی در مخزن اصلی انجام می‌شود.');
}
console.log(`account-screens: ${entries.length} بخش، ${by('page').length} فعال، ${by('flow').length} مرحلهٔ ثبت‌نام، ${by('bot').length} در ربات بله، ${by('later').length} خارج از نسخهٔ اول`);
