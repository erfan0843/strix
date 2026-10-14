import { createServer } from 'node:http';
import { createHash } from 'node:crypto';
import { readFile, realpath, stat } from 'node:fs/promises';
import path from 'node:path';
import { isIP } from 'node:net';
import { brotliCompressSync, constants as zlibConstants, gzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import { dispatchOutbox, publicIntegrationStatus, validateOutboxRequest } from './integrations.mjs';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const HOST = process.env.HOST || '0.0.0.0';
const PORT = Number.parseInt(process.env.PORT || '4173', 10);
const MAX_BODY_BYTES = 64 * 1024;
const MAX_COMPRESSED_CACHE_BYTES = 32 * 1024 * 1024;
const compressedCache = new Map();
let compressedCacheBytes = 0;
const PUBLIC_EXTENSIONS = new Set([
  '.html', '.css', '.js', '.svg', '.png', '.jpg', '.jpeg', '.webp', '.ico',
  '.woff', '.woff2', '.ttf', '.otf', '.webmanifest', '.mp3', '.mp4', '.xml', '.txt'
]);
const COMPRESSIBLE_EXTENSIONS = new Set(['.html', '.css', '.js', '.svg', '.webmanifest']);
const VERSIONED_EXTENSIONS = new Set(['.css', '.js', '.svg', '.png', '.jpg', '.jpeg', '.webp', '.ico', '.woff', '.woff2']);
const MIME = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.webp': 'image/webp', '.ico': 'image/x-icon', '.woff': 'font/woff',
  '.woff2': 'font/woff2', '.ttf': 'font/ttf', '.otf': 'font/otf',
  '.webmanifest': 'application/manifest+json', '.mp3': 'audio/mpeg', '.mp4': 'video/mp4',
  '.xml': 'application/xml; charset=utf-8', '.txt': 'text/plain; charset=utf-8'
};

function securityHeaders(res) {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Referrer-Policy', 'no-referrer');
  res.setHeader('X-Frame-Options', 'SAMEORIGIN');
  res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
  res.setHeader('Cache-Control', 'no-store');
}

function sendJson(res, status, body) {
  securityHeaders(res);
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.end(JSON.stringify(body));
}

async function readJson(req) {
  const declared = Number(req.headers['content-length'] || 0);
  if (declared > MAX_BODY_BYTES) {
    const err = new Error('request_too_large');
    err.status = 413;
    throw err;
  }
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) {
      const err = new Error('request_too_large');
      err.status = 413;
      throw err;
    }
    chunks.push(chunk);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString('utf8'));
  } catch {
    const err = new Error('invalid_json');
    err.status = 400;
    throw err;
  }
}

function configuredPublicBase() {
  const raw = String(process.env.NORA_PUBLIC_BASE_URL || '').trim();
  if (!raw || raw.length > 512 || /\s|\\/.test(raw)) return '';
  let url;
  try { url = new URL(raw); } catch { return ''; }
  const host = url.hostname.replace(/^\[|\]$/g, '').toLowerCase().replace(/\.$/, '');
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash
      || !['', '/'].includes(url.pathname)) return '';
  const exampleDomains = ['example.com', 'example.net', 'example.org'];
  if (exampleDomains.some(domain => host === domain || host.endsWith(`.${domain}`))) return '';
  const reserved = new Set(['example', 'invalid', 'localhost', 'local', 'internal', 'lan', 'test', 'onion']);
  const labels = host.split('.');
  if (isIP(host)) {
    if (isIP(host) === 4) {
      const octets = host.split('.').map(Number);
      const [a, b, c] = octets;
      if (a === 0 || a === 10 || a === 127 || a >= 224 || (a === 100 && b >= 64 && b <= 127)
          || (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31)
          || (a === 192 && b === 168) || (a === 192 && b === 0 && c === 0)
          || (a === 192 && b === 0 && c === 2) || (a === 198 && (b === 18 || b === 19))
          || (a === 198 && b === 51 && c === 100) || (a === 203 && b === 0 && c === 113)) return '';
    } else if (!/^2[0-9a-f]{3}:/.test(host) || /^2001:db8:/i.test(host)) {
      return '';
    }
  } else if (host.length > 253 || labels.length < 2 || reserved.has(labels.at(-1))
      || !labels.every(label => /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label))) {
    return '';
  }
  return url.origin.replace(/\/$/, '');
}

function robotsText() {
  const lines = ['User-agent: *', 'Allow: /', 'Disallow: /api/'];
  const base = configuredPublicBase();
  if (base) lines.push(`Sitemap: ${base}/sitemap.xml`);
  return `${lines.join('\n')}\n`;
}

function sitemapXml(base) {
  if (!base) return '';
  const urls = ['/', '/events.html'].map(route => `${base}${route}`);
  const entries = urls.map(url => `  <url><loc>${url.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</loc></url>`).join('\n');
  return `<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n${entries}\n</urlset>\n`;
}

function configuredLocalBusiness(base) {
  const fields = {
    name: String(process.env.NORA_SEO_BUSINESS_NAME || '').trim(),
    streetAddress: String(process.env.NORA_SEO_BUSINESS_STREET_ADDRESS || '').trim(),
    addressLocality: String(process.env.NORA_SEO_BUSINESS_LOCALITY || '').trim(),
    postalCode: String(process.env.NORA_SEO_BUSINESS_POSTAL_CODE || '').trim(),
    addressCountry: String(process.env.NORA_SEO_BUSINESS_COUNTRY_CODE || '').trim().toUpperCase(),
    telephone: String(process.env.NORA_SEO_BUSINESS_TELEPHONE || '').trim(),
    description: String(process.env.NORA_SEO_BUSINESS_DESCRIPTION || '').trim()
  };
  if (!Object.values(fields).some(Boolean)) return null;
  if (!fields.name || !fields.streetAddress || !fields.addressLocality || !fields.postalCode
      || !/^[A-Z]{2}$/.test(fields.addressCountry) || !/^\+?[0-9][0-9 .()/-]{5,30}$/.test(fields.telephone)) return null;
  const limits = { name: 160, streetAddress: 180, addressLocality: 120, postalCode: 32, addressCountry: 2, telephone: 32, description: 500 };
  if (Object.entries(fields).some(([key, value]) => value.length > limits[key] || /[\u0000-\u001f\u007f]/.test(value))) return null;
  return {
    '@type': 'LocalBusiness',
    '@id': base ? `${base}/#localbusiness` : undefined,
    name: fields.name,
    telephone: fields.telephone,
    address: {
      '@type': 'PostalAddress', streetAddress: fields.streetAddress,
      addressLocality: fields.addressLocality, postalCode: fields.postalCode,
      addressCountry: fields.addressCountry
    },
    ...(fields.description ? { description: fields.description } : {}),
    ...(base ? { url: base } : {})
  };
}

function applyStaticStructuredData(html, pathname) {
  if (!['/', '/home.html', '/index.html', '/events.html'].includes(pathname)) return html;
  const pageName = pathname === '/events.html' ? 'events' : 'home';
  const base = configuredPublicBase();
  const route = pageName === 'events' ? '/events.html' : '/';
  const canonical = base ? `${base}${route}` : route;
  const canonicalPattern = /<link\b(?=[^>]*\brel\s*=\s*(['"])canonical\1)[^>]*>/i;
  const canonicalTag = `<link rel="canonical" href="${canonical}"/>`;
  if (canonicalPattern.test(html)) {
    html = html.replace(canonicalPattern, canonicalTag);
  } else {
    const headEnd = html.toLowerCase().indexOf('</head>');
    if (headEnd >= 0) html = `${html.slice(0, headEnd)}${canonicalTag}\n${html.slice(headEnd)}`;
  }
  if (!html.includes('<!--nora-seo-jsonld-->')) return html;
  const titleMatch = html.match(/<title\b[^>]*>([\s\S]*?)<\/title\s*>/i);
  const descriptionMatch = html.match(/<meta\b(?=[^>]*\bname\s*=\s*(['"])description\1)[^>]*\bcontent\s*=\s*(['"])(.*?)\2[^>]*>/i);
  const decode = value => String(value || '').replace(/&amp;/g, '&').replace(/&quot;/g, '\"').replace(/&#39;|&#x27;/gi, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>');
  const title = decode(titleMatch && titleMatch[1]).replace(/<[^>]*>/g, '').trim() || 'نورا';
  const description = decode(descriptionMatch && descriptionMatch[3]).trim();
  const pageUrl = base ? canonical : '';
  const organization = {
    '@type': 'Organization', name: 'گروه فرهنگی خط زندگی', alternateName: 'نورا',
    description: 'رویدادها، مطالب و پروفایل‌های عمومی منتشرشده در نورا.',
    ...(base ? { '@id': `${base}/#organization`, url: base } : {})
  };
  const website = {
    '@type': 'WebSite', name: 'نورا', inLanguage: 'fa',
    ...(base ? { '@id': `${base}/#website`, url: base, publisher: { '@id': `${base}/#organization` } } : {})
  };
  const page = {
    '@type': 'WebPage', name: title, description, inLanguage: 'fa',
    ...(pageUrl ? { '@id': `${pageUrl}#webpage`, url: pageUrl, isPartOf: { '@id': `${base}/#website` }, publisher: { '@id': `${base}/#organization` } } : {})
  };
  const graph = [organization, website];
  const business = configuredLocalBusiness(base);
  if (business) graph.push(business);
  graph.push(page);
  if (base && pageName === 'events') {
    graph.push({
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'خانه', item: `${base}/` },
        { '@type': 'ListItem', position: 2, name: 'رویدادها', item: `${base}/events.html` }
      ]
    });
  }
  const json = JSON.stringify({ '@context': 'https://schema.org', '@graph': graph })
    .replace(/</g, '\\u003c').replace(/>/g, '\\u003e').replace(/&/g, '\\u0026');
  const script = `<script id="nora-structured-data" type="application/ld+json">${json}</script>`;
  return html.replace('<!--nora-seo-jsonld-->', script);
}

function htmlEtag(data) {
  return `W/"${createHash('sha256').update(data).digest('hex')}"`;
}

function sendText(req, res, status, contentType, body) {
  securityHeaders(res);
  res.statusCode = status;
  res.setHeader('Content-Type', contentType);
  res.setHeader('Content-Length', Buffer.byteLength(body));
  if (req.method === 'HEAD') return res.end();
  return res.end(body);
}

async function serveNotFound(req, res) {
  let body;
  try { body = await readFile(path.join(ROOT, '404.html')); }
  catch {
    body = Buffer.from('<!doctype html><html lang=\"fa\" dir=\"rtl\"><meta charset=\"utf-8\"><title>صفحه پیدا نشد | نورا</title><meta name=\"robots\" content=\"noindex,nofollow\"><h1 id=\"page-title\">صفحه پیدا نشد</h1><a href=\"/\">خانه</a>');
  }
  securityHeaders(res);
  res.statusCode = 404;
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.setHeader('X-Robots-Tag', 'noindex, nofollow');
  res.setHeader('Content-Length', body.length);
  if (req.method === 'HEAD') return res.end();
  return res.end(body);
}

function safePath(urlPath) {
  let decoded;
  try { decoded = decodeURIComponent(urlPath); } catch { return null; }
  if (decoded.includes('\0') || decoded.split('/').some(part => part.startsWith('.'))) return null;
  const relative = decoded === '/' ? 'home.html' : decoded.replace(/^\/+/, '');
  const candidate = path.resolve(ROOT, relative);
  if (candidate !== ROOT && !candidate.startsWith(ROOT + path.sep)) return null;
  if (!PUBLIC_EXTENSIONS.has(path.extname(candidate).toLowerCase())) return null;
  const basename = path.basename(candidate).toLowerCase();
  if (basename === 'server.mjs' || basename === 'integrations.mjs' || basename.endsWith('.test.mjs')) return null;
  return candidate;
}

function staticEtag(fileStat) {
  return `W/"${Number(fileStat.size).toString(16)}-${Math.trunc(fileStat.mtimeMs).toString(16)}"`;
}

function etagMatches(header, etag) {
  if (!header) return false;
  const normalized = etag.replace(/^W\//, '');
  return String(header).split(',').some(value => {
    const tag = value.trim();
    return tag === '*' || tag === etag || tag.replace(/^W\//, '') === normalized;
  });
}

function acceptedEncoding(header, encoding) {
  return String(header || '').split(',').some(value => {
    const [name, ...params] = value.trim().toLowerCase().split(';');
    return name === encoding && !params.some(param => /^\s*q\s*=\s*0(?:\.0*)?\s*$/.test(param));
  });
}

function compressedAsset(actual, etag, data, encoding) {
  const key = `${actual}:${etag}:${encoding}`;
  const cached = compressedCache.get(key);
  if (cached) {
    compressedCache.delete(key);
    compressedCache.set(key, cached);
    return cached;
  }
  const output = encoding === 'br'
    ? brotliCompressSync(data, { params: { [zlibConstants.BROTLI_PARAM_QUALITY]: 4 } })
    : gzipSync(data, { level: 5, mtime: 0 });
  if (output.length < data.length && output.length <= MAX_COMPRESSED_CACHE_BYTES) {
    compressedCache.set(key, output);
    compressedCacheBytes += output.length;
    while (compressedCacheBytes > MAX_COMPRESSED_CACHE_BYTES && compressedCache.size) {
      const [oldKey, oldValue] = compressedCache.entries().next().value;
      compressedCache.delete(oldKey);
      compressedCacheBytes -= oldValue.length;
    }
    return output;
  }
  return data;
}

async function serveStatic(req, res, url) {
  if (url.pathname === '/404.html') return serveNotFound(req, res);
  const candidate = safePath(url.pathname);
  if (!candidate) return serveNotFound(req, res);
  try {
    const actual = await realpath(candidate);
    if (actual !== ROOT && !actual.startsWith(ROOT + path.sep)) return sendJson(res, 404, { error: 'not_found' });
    const fileStat = await stat(actual);
    if (!fileStat.isFile()) return serveNotFound(req, res);
    const extension = path.extname(actual).toLowerCase();
    let data = await readFile(actual);
    if (extension === '.html') {
      data = Buffer.from(applyStaticStructuredData(data.toString('utf8'), url.pathname));
    }
    const etag = extension === '.html' ? htmlEtag(data) : staticEtag(fileStat);
    securityHeaders(res);
    res.setHeader('Content-Type', MIME[extension] || 'application/octet-stream');
    res.setHeader('ETag', etag);
    res.setHeader('Cache-Control', extension === '.html'
      ? 'no-cache, max-age=0, must-revalidate'
      : (VERSIONED_EXTENSIONS.has(extension) && url.searchParams.has('v')
        ? 'public, max-age=31536000, immutable'
        : 'no-cache, max-age=0, must-revalidate'));
    if (COMPRESSIBLE_EXTENSIONS.has(extension)) res.setHeader('Vary', 'Accept-Encoding');
    if (etagMatches(req.headers['if-none-match'], etag)) {
      res.statusCode = 304;
      return res.end();
    }
    if (data.length >= 1024 && COMPRESSIBLE_EXTENSIONS.has(extension)) {
      const accept = req.headers['accept-encoding'];
      const encoding = acceptedEncoding(accept, 'br') ? 'br' : acceptedEncoding(accept, 'gzip') ? 'gzip' : '';
      if (encoding) {
        const packed = compressedAsset(actual, etag, data, encoding);
        if (packed !== data) {
          data = packed;
          res.setHeader('Content-Encoding', encoding);
        }
      }
    }
    res.statusCode = 200;
    res.setHeader('Content-Length', data.length);
    if (req.method === 'HEAD') return res.end();
    return res.end(data);
  } catch {
    return serveNotFound(req, res);
  }
}

const server = createServer(async (req, res) => {
  let url;
  try { url = new URL(req.url || '/', 'http://nora.local'); }
  catch { return sendJson(res, 400, { error: 'bad_request' }); }

  if (url.pathname.startsWith('/api/')) {
    if (url.pathname === '/api/health') {
      if (req.method !== 'GET') return sendJson(res, 405, { error: 'method_not_allowed' });
      return sendJson(res, 200, { ok: true, mode: 'server-scaffold', deliveryEnabled: false });
    }
    if (url.pathname === '/api/integrations/status') {
      if (req.method !== 'GET') return sendJson(res, 405, { error: 'method_not_allowed' });
      return sendJson(res, 200, publicIntegrationStatus());
    }
    if (url.pathname === '/api/outbox') {
      if (req.method !== 'POST') return sendJson(res, 405, { error: 'method_not_allowed' });
      if (!String(req.headers['content-type'] || '').toLowerCase().startsWith('application/json')) {
        return sendJson(res, 415, { error: 'application_json_required' });
      }
      let body;
      try { body = await readJson(req); }
      catch (err) { return sendJson(res, err.status || 400, { error: err.message || 'invalid_request' }); }
      const checked = validateOutboxRequest(body);
      if (!checked.ok) return sendJson(res, checked.status, { error: checked.code });
      return sendJson(res, 409, dispatchOutbox(checked.request));
    }
    return sendJson(res, 404, { error: 'not_found' });
  }

  if (req.method !== 'GET' && req.method !== 'HEAD') return sendJson(res, 405, { error: 'method_not_allowed' });
  if (url.pathname === '/robots.txt') {
    return sendText(req, res, 200, 'text/plain; charset=utf-8', robotsText());
  }
  if (url.pathname === '/sitemap.xml') {
    const base = configuredPublicBase();
    if (!base) {
      res.setHeader('Retry-After', '3600');
      return sendText(req, res, 503, 'text/plain; charset=utf-8', 'Set NORA_PUBLIC_BASE_URL to an official HTTPS origin before publishing the sitemap.\n');
    }
    return sendText(req, res, 200, 'application/xml; charset=utf-8', sitemapXml(base));
  }
  return serveStatic(req, res, url);
});

server.requestTimeout = 10_000;
server.headersTimeout = 12_000;
server.listen(PORT, HOST, () => {
  const address = server.address();
  console.log(`Nora UI server listening on http://${HOST}:${address && address.port}`);
});

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => server.close(() => process.exit(0)));
}
