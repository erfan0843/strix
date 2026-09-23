#!/usr/bin/env python3
"""صفحه‌های خالی بلیت و رسید + هندسهٔ اندازه‌گیری‌شده.

از تصویرهای مرجع خودِ کاربر (tickets/*.png) صفحه‌های خالی می‌سازد
(tickets/<name>-plate.png) و tickets/geo.json را می‌نویسد: تراز دقیق هر متن،
رنگ جوهر و رنگ متن کم‌رنگ هر پوسته.

اجرا (از همین پوشه):  python3 tools-make-plates.py
"""
from PIL import Image, ImageDraw, ImageFilter
import numpy as np
import os, json

HERE = os.path.dirname(os.path.abspath(__file__))
TICKETS = ['tk-clear', 'tk-forest', 'tk-gold', 'tk-ocean', 'tk-night']
RECEIPTS = ['rc-clear', 'rc-night']

# ناحیه‌های متن نمونه در مرجع بلیت (۸۸۰×۴۱۰) — با حاشیهٔ اطمینان
TICKET_ERASE = [
    (470, 112, 818, 172),      # عنوان
    (380, 178, 818, 214),      # خط روز/تاریخ/ساعت/نشانی
    (730, 268, 818, 294),      # برچسب «شرکت‌کننده»
    (630, 294, 818, 336),      # نام
    (105, 268, 180, 294),      # برچسب «کد بلیت»
    (35, 292, 248, 328),       # کد
]
TICKET_QR = (74, 78, 209, 213)

# ناحیه‌های متن نمونه در مرجع رسید (۶۲۰×۵۸۷)
RECEIPT_ERASE = [
    (48, 38, 165, 74),         # چیپ وضعیت
    (380, 86, 575, 111),       # عنوان رسید (خط زیرش در y=113 بماند)
    (265, 132, 360, 158),      # «مبلغ»
    (185, 160, 445, 208),      # عدد مبلغ
    (235, 209, 395, 232),      # تخفیف
    (48, 226, 572, 424),       # ردیف‌های اطلاعات (خط جداکننده در ۴۳۳ می‌ماند)
    (470, 448, 575, 512),      # کد پیگیری
]
RECEIPT_QR = (66, 452, 162, 548)


def inpaint(im, areas, margin=2, bounds=None):
    """نمونه‌برداری فقط از داخل کارت انجام می‌شود تا لبه‌های تیره قاطی نشوند."""
    a = np.asarray(im).astype(np.float32)
    h, w, _ = a.shape
    bx0, by0, bx1, by1 = bounds or (0, 0, w, h)
    for (x0, y0, x1, y1) in areas:
        x0, y0 = max(bx0 + 2, x0 - margin), max(by0 + 2, y0 - margin)
        x1, y1 = min(bx1 - 2, x1 + margin), min(by1 - 2, y1 + margin)
        lx0, lx1 = max(bx0 + 2, x0 - 26), x0
        rx0, rx1 = x1, min(bx1 - 2, x1 + 26)
        left = a[y0:y1, lx0:lx1].mean(1) if lx1 > lx0 + 3 else None
        right = a[y0:y1, rx0:rx1].mean(1) if rx1 > rx0 + 3 else None
        if left is None:
            left = right
        if right is None:
            right = left
        span = x1 - x0
        for i in range(span):
            t = i / max(1, span - 1)
            a[y0:y1, x0 + i] = left * (1 - t) + right * t
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))


def white_card(im, box, radius=20, pad=6):
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad],
                        radius=radius, fill=(255, 255, 255))
    return im


def palette(src, areas):
    """رنگ جوهر و متن کم‌رنگ را از خودِ تصویر مرجع برمی‌دارد (روشن یا تیره)."""
    a = np.asarray(Image.open(src).convert('RGB')).astype(int)
    b = a.sum(2)
    # کارت تیره است؟ میانگین روشنایی ناحیهٔ کارت را می‌سنجیم (نه یک نقطه)
    inner = a[110:210, 470:800].reshape(-1, 3).mean(0).sum()
    dark_skin = inner < 560

    def pick(x0, x1, y0, y1, frac):
        s = a[y0:y1, x0:x1].reshape(-1, 3)
        sb = s.sum(1)
        k = max(1, int(len(s) * frac))
        idx = np.argsort(sb)[:k] if not dark_skin else np.argsort(sb)[-k:]
        return '#%02X%02X%02X' % tuple(int(v) for v in np.median(s[idx], 0))

    ink = pick(*areas['title'], 0.05)
    muted = pick(*areas['meta'], 0.10)
    return ink, muted


def bands(path, areas):
    a = np.asarray(Image.open(path).convert('RGB')).astype(int)
    b = a.sum(2)
    bg = (b > 690) if path.endswith('clear.png') else (b < 400)
    ink = ~bg if path.endswith('clear.png') else (b > 560)
    out = {}
    for name, (x0, x1, y0, y1) in areas.items():
        s = ink[y0:y1, x0:x1]
        c = np.where(s.sum(0) > 0)[0]
        r = np.where(s.sum(1) > 0)[0]
        out[name] = None if len(c) == 0 else [int(x0 + c.min()), int(y0 + r.min()), int(x0 + c.max()), int(y0 + r.max())]
    return out


if __name__ == '__main__':
    # ── صفحه‌ها ──
    for n in TICKETS:
        im = Image.open(f'{HERE}/tickets/{n}.png').convert('RGB')
        im = white_card(im, TICKET_QR)
        im = inpaint(im, TICKET_ERASE, bounds=(30, 29, 850, 380))
        im = white_card(im, TICKET_QR)
        im.save(f'{HERE}/tickets/{n}-plate.png', optimize=True)
        print(f'  {n}-plate.png {os.path.getsize(f"{HERE}/tickets/{n}-plate.png")//1024} KB')
    for n in RECEIPTS:
        im = Image.open(f'{HERE}/tickets/{n}.png').convert('RGB')
        im = white_card(im, RECEIPT_QR, radius=18, pad=5)
        im = inpaint(im, RECEIPT_ERASE, bounds=(30, 26, 590, 558))
        im = white_card(im, RECEIPT_QR, radius=18, pad=5)
        im.save(f'{HERE}/tickets/{n}-plate.png', optimize=True)
        print(f'  {n}-plate.png {os.path.getsize(f"{HERE}/tickets/{n}-plate.png")//1024} KB')

    # ── هندسه (از صفحهٔ شفاف سنجیده می‌شود؛ همهٔ پوسته‌ها یک قالب‌اند) ──
    t = bands(f'{HERE}/tickets/tk-clear.png', {
        'title': (370, 812, 112, 172), 'meta': (370, 812, 178, 214),
        'nameLabel': (700, 811, 268, 294), 'name': (600, 811, 294, 336),
        'codeLabel': (100, 190, 268, 294), 'code': (30, 250, 292, 328)})
    r = bands(f'{HERE}/tickets/rc-clear.png', {
        'pill': (40, 220, 34, 78), 'title': (380, 575, 80, 120),
        'amountCap': (250, 380, 134, 160), 'amount': (150, 470, 160, 210),
        'discount': (200, 440, 210, 240), 'track': (470, 575, 448, 520)})

    geo = dict(
        ticket=dict(
            size=[880, 410], card=[30, 29, 850, 380],
            perf=254, tx=809,
            title=dict(x=t['title'][2], base=t['title'][3] - 6, size=36),
            meta=dict(x=t['meta'][2], base=t['meta'][3] - 5, size=20),
            nameLabel=dict(x=t['nameLabel'][2], base=t['nameLabel'][3] - 3, size=14),
            name=dict(x=t['name'][2], base=t['name'][3] - 6, size=27),
            codeLabel=dict(cx=(t['codeLabel'][0] + t['codeLabel'][2]) // 2, base=t['codeLabel'][3] - 3, size=13.5),
            code=dict(cx=(t['code'][0] + t['code'][2]) // 2, base=t['code'][3], size=29, track=7),
            qr=dict(x0=TICKET_QR[0], y0=TICKET_QR[1] + 13, size=TICKET_QR[2] - TICKET_QR[0] - 26),
        ),
        receipt=dict(
            size=[620, 587], card=[30, 26, 590, 558],
            pill=dict(x=r['pill'][0] - 32, y=r['pill'][1] - 10, h=32),
            title=dict(x=r['title'][2], base=r['title'][3] - 5, size=22),
            amountCap=dict(cx=(r['amountCap'][0] + r['amountCap'][2]) // 2, base=r['amountCap'][3], size=13.5),
            amount=dict(cx=(r['amount'][0] + r['amount'][2]) // 2, base=r['amount'][3] - 4, size=38),
            discount=dict(cx=(r['discount'][0] + r['discount'][2]) // 2, base=r['discount'][3], size=13.5),
            rows=dict(first=281, gap=32, labelX=559, valueX=60, size=15),
            track=dict(x=r['track'][2], base=r['track'][3] - 4, size=30),
            qr=dict(x0=RECEIPT_QR[0], y0=RECEIPT_QR[1], size=RECEIPT_QR[2] - RECEIPT_QR[0]),
        ),
    )

    pal = {}
    for n in TICKETS:
        ink, muted = palette(f'{HERE}/tickets/{n}.png',
                             {'title': (490, 815, 118, 168), 'meta': (400, 815, 182, 208)})
        pal[n.replace('tk-', '')] = dict(ink=ink, muted=muted)
    for n in RECEIPTS:
        a = np.asarray(Image.open(f'{HERE}/tickets/{n}.png').convert('RGB')).astype(int)
        # کارت تیره است؟ میانگین روشنایی ناحیهٔ ردیف‌ها (نه یک نقطه)
        dark_skin = a[285:345, 60:520].reshape(-1, 3).mean(0).sum() < 560
        def pick(box, k):
            x0, x1, y0, y1 = box
            s = a[y0:y1, x0:x1].reshape(-1, 3)
            idx = np.argsort(s.sum(1))[:k] if not dark_skin else np.argsort(s.sum(1))[-k:]
            return '#%02X%02X%02X' % tuple(int(v) for v in np.median(s[idx], 0))
        pal[n] = dict(ink=pick((60, 300, 268, 282), 40), muted=pick((470, 562, 268, 282), 16))

    json.dump(dict(geo=geo, palette=pal), open(f'{HERE}/tickets/geo.json', 'w'), ensure_ascii=False, indent=1)
    # ── plates.js: همان دو جدول تصویری که صفحه‌ها (و ربات) لود می‌کنند ──
    import base64, io as _io
    lines = ['/* صفحه‌های خودِ مرجع: بلیت و رسید — با متن و کیوآر پاک‌شده تا متن زنده رویشان بنشیند',
             '   ساخته‌شده با tools-make-plates.py از tickets/*.png  */',
             'const TK_PLATES={']
    for n in [x.replace('tk-', '') for x in TICKETS]:
        im = Image.open(f'{HERE}/tickets/tk-{n}-plate.png').convert('RGB')
        buf = _io.BytesIO(); im.save(buf, 'JPEG', quality=92, optimize=True, subsampling=0)
        lines.append(f"  {n}:'data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}',")
    lines.append('};')
    lines.append('const RC_PLATES={')
    for n in [x.replace('rc-', '') for x in RECEIPTS]:
        im = Image.open(f'{HERE}/tickets/rc-{n}-plate.png').convert('RGB')
        buf = _io.BytesIO(); im.save(buf, 'JPEG', quality=92, optimize=True, subsampling=0)
        lines.append(f"  {n}:'data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}',")
    lines.append('};')
    lines.append('const TK_GEO=' + json.dumps(dict(geo=geo, palette=pal), ensure_ascii=False, separators=(',', ':')) + ';')
    lines.append("if(typeof module!=='undefined'&&module.exports) module.exports={TK_PLATES,RC_PLATES,TK_GEO};")
    open(f'{HERE}/tickets/plates.js', 'w').write('\n'.join(lines) + '\n')
    print('plates.js نوشته شد:', os.path.getsize(f'{HERE}/tickets/plates.js') // 1024, 'KB')

    print('geo.json نوشته شد')
    print(json.dumps(pal, ensure_ascii=False))
    print(json.dumps(geo['ticket'], ensure_ascii=False)[:400])
    print(json.dumps(geo['receipt'], ensure_ascii=False)[:400])
