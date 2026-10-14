import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const root = path.dirname(fileURLToPath(import.meta.url));
const bodyFont = 'fonts/Vazirmatn-UI-FD-Regular.woff2';
const headingFont = 'fonts/Estedad-Variable.woff2';
const latinFonts = ['fonts/Nora-Latin-Regular.woff2', 'fonts/Nora-Latin-Bold.woff2'];

function filesUsingSharedStyles() {
  return fs.readdirSync(root)
    .filter(name => name.endsWith('.html'))
    .filter(name => /<link\s+rel="stylesheet"\s+href="glass\.css/.test(
      fs.readFileSync(path.join(root, name), 'utf8'),
    ));
}

test('shared typography uses local Persian and Latin fonts consistently', () => {
  for (const font of [bodyFont, headingFont, ...latinFonts]) {
    assert.ok(fs.statSync(path.join(root, font)).size > 0, `${font} must exist locally`);
  }

  const sharedCss = fs.readFileSync(path.join(root, 'glass.css'), 'utf8');
  assert.match(sharedCss, /--f:'Vazirmatn'/, 'Vazirmatn should remain the body font');
  assert.match(sharedCss, /--f-h:'Estedad',var\(--f\)/, 'Estedad should be the heading font');
  assert.match(sharedCss, /\.num,code,kbd,samp,\[dir="ltr"\]\{font-family:'Nora Latin'/,
    'Latin text and identifiers should use Nora Latin');

  const pages = filesUsingSharedStyles();
  assert.ok(pages.length > 0, 'at least one page should use the shared design system');

  for (const page of pages) {
    const html = fs.readFileSync(path.join(root, page), 'utf8');
    for (const font of [bodyFont, headingFont]) {
      const escaped = font.replaceAll('.', '\\.');
      const preload = new RegExp(
        `<link\\s+rel="preload"\\s+href="${escaped}"\\s+as="font"\\s+type="font/woff2"\\s+crossorigin\\s*/?>`,
      );
      assert.match(html, preload, `${page} should preload ${font}`);
    }
  }
});

test('account introduction keeps the supplied display/body pairing and real font weights', () => {
  const css = fs.readFileSync(path.join(root, 'account.css'), 'utf8');
  const start = css.indexOf('/* صفحهٔ معرفی حساب؛');
  const end = css.indexOf('/* ══ نورا پی:', start);
  assert.ok(start >= 0 && end > start, 'the introduction styles should remain scoped');
  const intro = css.slice(start, end);

  assert.match(intro, /\.account-promo\{[\s\S]*?font-family:var\(--f\);font-synthesis:none;/,
    'body text should use Vazirmatn without synthesized bold or italic');
  assert.match(intro, /\.account-promo h2,\.account-promo h3,\.account-promo h4,[\s\S]*?\{font-family:var\(--f-h\)\}/,
    'all introduction headings should use the supplied Estedad variable font');
  assert.match(intro, /\.account-promo-feature h4\{[^}]*font-weight:650;/,
    'feature titles should use a real weight in the Estedad variable range');
  assert.match(intro, /\.account-promo-copy>p\{[^}]*font-weight:400;/,
    'body text should use the actual regular Vazirmatn face');
  assert.doesNotMatch(intro, /@font-face|url\(["']?https?:/i,
    'the introduction should reuse the local fonts, not request a substitute from outside');
});
