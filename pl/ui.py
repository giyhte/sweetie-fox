# -*- coding: utf-8 -*-
"""Градиентный интерфейс: Pillow рисует фон и стекло, Tk — текст и ввод."""
import math, os, time, queue, traceback
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageFont

VIOLET, PINK, CYAN, BLUE = (104, 66, 240), (170, 130, 255), (150, 118, 255), (80, 70, 220)

BLOBS = [  # cx, cy, ax, ay, fx, fy, phase, radius, color, gain
    (0.12, 0.18, 0.10, 0.08, 0.21, 0.17, 0.0, 0.36, VIOLET, 1.00),
    (0.88, 0.22, 0.08, 0.10, 0.17, 0.23, 1.7, 0.30, PINK, 0.80),
    (0.62, 0.95, 0.14, 0.06, 0.19, 0.13, 3.1, 0.40, CYAN, 0.70),
    (0.08, 0.88, 0.07, 0.09, 0.15, 0.25, 4.4, 0.30, BLUE, 0.85),
]
BASE = (8, 6, 22)
FONTS = ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Helvetica.ttc"]


def pil_font(size):
    for p in FONTS:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default(size)


class Painter:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.mw = 28
        self.mh = max(6, int(28 * h / w))
        self._m, self._g, self._glow, self._logo, self._sheen = {}, {}, {}, {}, {}
        self._tg = {}

    # ----- фон -----
    def mesh(self, t):
        mw, mh, asp = self.mw, self.mh, self.w / self.h
        pts = []
        for cx, cy, ax, ay, fx, fy, ph, rad, col, gain in BLOBS:
            pts.append((cx + ax * math.sin(fx * t + ph), cy + ay * math.cos(fy * t + ph),
                        rad * rad, col, gain))
        data = []
        for j in range(mh):
            y = (j + 0.5) / mh
            for i in range(mw):
                x = (i + 0.5) / mw
                r, g, b = BASE
                for bx, by, r2, col, gain in pts:
                    dx = (x - bx) * asp
                    dy = y - by
                    k = math.exp(-(dx * dx + dy * dy) / r2) * gain
                    r += col[0] * k; g += col[1] * k; b += col[2] * k
                data.append((min(255, int(r)), min(255, int(g)), min(255, int(b))))
        im = Image.new("RGB", (mw, mh))
        im.putdata(data)
        return im.resize((self.w, self.h), Image.BILINEAR)

    # ----- примитивы -----
    def mask(self, w, h, r, ring=0):
        key = (w, h, r, ring)
        if key not in self._m:
            S = 4 if w * h < 30000 else 2
            m = Image.new("L", (w * S, h * S), 0)
            d = ImageDraw.Draw(m)
            d.rounded_rectangle((0, 0, w * S - 1, h * S - 1), r * S, fill=255)
            if ring:
                d.rounded_rectangle((ring * S, ring * S, w * S - 1 - ring * S, h * S - 1 - ring * S),
                                    max(r - ring, 1) * S, fill=0)
            self._m[key] = m.resize((w, h), Image.LANCZOS)
        return self._m[key]

    def _comp(self, ov, layer, x, y):
        W, H = ov.size
        lw, lh = layer.size
        sx, sy = max(0, -x), max(0, -y)
        ex, ey = min(lw, W - x), min(lh, H - y)
        if ex <= sx or ey <= sy:
            return
        ov.alpha_composite(layer.crop((sx, sy, ex, ey)), (x + sx, y + sy))

    def _fill(self, ov, box, color, mask):
        x0, y0, x1, y1 = box
        layer = Image.new("RGBA", (x1 - x0, y1 - y0), color)
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
        self._comp(ov, layer, x0, y0)

    def grad(self, w, h, c1, c2):
        key = (w, h, c1, c2)
        if key not in self._g:
            g = Image.new("L", (w, 1))
            g.putdata([int(255 * i / max(w - 1, 1)) for i in range(w)])
            g = g.resize((w, h))
            self._g[key] = Image.composite(Image.new("RGB", (w, h), c2), Image.new("RGB", (w, h), c1), g)
        return self._g[key]

    def _grad_fill(self, ov, box, c1, c2, r, hover=False, alpha=255):
        x0, y0, x1, y1 = box
        w, h = x1 - x0, y1 - y0
        g = self.grad(w, h, c1, c2)
        if hover:
            g = Image.blend(g, Image.new("RGB", (w, h), (255, 255, 255)), 0.16)
        layer = g.convert("RGBA")
        layer.putalpha(self.mask(w, h, r).point(lambda v: v * alpha // 255))
        self._comp(ov, layer, x0, y0)

    def sheen(self, ov, box, r, strength=40):
        x0, y0, x1, y1 = box
        w, h = x1 - x0, y1 - y0
        key = (w, h, r, strength)
        if key not in self._sheen:
            g = Image.new("L", (1, h))
            g.putdata([int(strength * max(0.0, 1 - j / (h * 0.55))) for j in range(h)])
            g = g.resize((w, h))
            layer = Image.new("RGBA", (w, h), (255, 255, 255, 0))
            layer.putalpha(ImageChops.multiply(g, self.mask(w, h, r)))
            self._sheen[key] = layer
        self._comp(ov, self._sheen[key], x0, y0)

    # ----- виджеты -----
    def glass(self, ov, box, r=22, dark=95, light=20, border=48):
        w, h = box[2] - box[0], box[3] - box[1]
        m = self.mask(w, h, r)
        self._fill(ov, box, (8, 8, 30, dark), m)
        self._fill(ov, box, (255, 255, 255, light), m)
        self.sheen(ov, box, r, 26)
        self._fill(ov, box, (255, 255, 255, border), self.mask(w, h, r, 1))

    def inset(self, ov, box, r=14):
        w, h = box[2] - box[0], box[3] - box[1]
        self._fill(ov, box, (5, 5, 22, 120), self.mask(w, h, r))
        self._fill(ov, box, (255, 255, 255, 22), self.mask(w, h, r, 1))

    def glow(self, ov, box, color, r):
        x0, y0, x1, y1 = box
        w, h = x1 - x0, y1 - y0
        key = (w, h, color)
        if key not in self._glow:
            pad = 46
            im = Image.new("RGBA", (w + pad * 2, h + pad * 2), color + (0,))
            d = ImageDraw.Draw(im)
            d.rounded_rectangle((pad, pad + 6, pad + w, pad + h), r, fill=color + (120,))
            self._glow[key] = im.filter(ImageFilter.GaussianBlur(18))
        self._comp(ov, self._glow[key], x0 - 46, y0 - 46)

    def pill(self, ov, box, c1=VIOLET, c2=CYAN, hover=False, enabled=True):
        w, h = box[2] - box[0], box[3] - box[1]
        r = h // 2
        if not enabled:
            c1, c2 = (62, 64, 100), (78, 82, 120)
        else:
            self.glow(ov, box, c2 if hover else c1, r)
        self._grad_fill(ov, box, c1, c2, r, hover and enabled)
        self.sheen(ov, box, r, 55 if enabled else 20)

    def ghost(self, ov, box, hover=False, enabled=True):
        w, h = box[2] - box[0], box[3] - box[1]
        r = min(14, h // 2)
        self._fill(ov, box, (255, 255, 255, 46 if hover and enabled else 24), self.mask(w, h, r))
        self._fill(ov, box, (255, 255, 255, 70 if hover and enabled else 44), self.mask(w, h, r, 1))

    def glassbtn(self, ov, box, hv=0.0, enabled=True, accent=False, r=None):
        """Единая полупрозрачная кнопка для всего лаунчера. hv — 0..1 (анимированная наводка)."""
        w, h = box[2] - box[0], box[3] - box[1]
        r = (min(16, h // 2)) if r is None else r
        hv = hv if enabled else 0.0
        base = 30 + int(26 * hv)
        if accent and enabled:
            self.glow(ov, box, VIOLET if hv < 0.5 else (170, 140, 255), r)
            c1 = tuple(int(a + (b - a) * hv * 0.35) for a, b in zip((70, 44, 190), VIOLET))
            c2 = tuple(int(a + (b - a) * hv * 0.35) for a, b in zip((118, 90, 250), CYAN))
            self._grad_fill(ov, box, c1, c2, r, False)
            self._fill(ov, box, (255, 255, 255, int(8 + 26 * hv)), self.mask(w, h, r))
            if w > 120:
                self.stripes(ov, box, r)
        else:
            self._fill(ov, box, (255, 255, 255, base if enabled else 16), self.mask(w, h, r))
        border = 48 + int(40 * hv) if enabled else 30
        self._fill(ov, box, (255, 255, 255, border), self.mask(w, h, r, 1))
        self.sheen(ov, box, r, int(30 + 35 * hv) if enabled else 14)

    def stripes(self, ov, box, r):
        """Две косые полосы справа, как на кнопках из макета."""
        x0, y0, x1, y1 = box
        w, h = x1 - x0, y1 - y0
        key = ("st", w, h, r)
        if key not in self._sheen:
            S = 3
            m = Image.new("L", (w * S, h * S), 0)
            d = ImageDraw.Draw(m)
            for off, wd in ((0, 7), (14, 3)):
                xr = w - 26 - off
                d.polygon([((xr + h * 0.45) * S, 0), ((xr + h * 0.45 + wd) * S, 0),
                           ((xr - h * 0.45 + wd) * S, h * S), ((xr - h * 0.45) * S, h * S)], fill=70)
            m = m.resize((w, h), Image.LANCZOS)
            layer = Image.new("RGBA", (w, h), (255, 255, 255, 0))
            layer.putalpha(ImageChops.multiply(m, self.mask(w, h, r)))
            self._sheen[key] = layer
        self._comp(ov, self._sheen[key], x0, y0)

    def switch(self, ov, box, on, hover=False):
        x0, y0, x1, y1 = box
        w, h = x1 - x0, y1 - y0
        if on:
            self._grad_fill(ov, box, VIOLET, CYAN, h // 2, hover)
        else:
            self._fill(ov, box, (255, 255, 255, 50 if hover else 36), self.mask(w, h, h // 2))
        d = h - 6
        kx = x1 - 3 - d if on else x0 + 3
        self._fill(ov, (kx, y0 + 3, kx + d, y0 + 3 + d), (255, 255, 255, 255), self.mask(d, d, d // 2))

    def slider(self, ov, box, frac):
        x0, y0, x1, y1 = box
        cy = (y0 + y1) // 2
        tr = (x0, cy - 3, x1, cy + 3)
        self._fill(ov, tr, (255, 255, 255, 40), self.mask(x1 - x0, 6, 3))
        fx = x0 + int((x1 - x0) * frac)
        if fx - x0 > 6:
            self._grad_fill(ov, (x0, cy - 3, fx, cy + 3), VIOLET, CYAN, 3)
        k = 20
        self.glow(ov, (fx - 8, cy - 8, fx + 8, cy + 8), CYAN, 8)
        self._fill(ov, (fx - k // 2, cy - k // 2, fx + k // 2, cy + k // 2), (255, 255, 255, 255),
                   self.mask(k, k, k // 2))

    def bar(self, ov, box, frac):
        x0, y0, x1, y1 = box
        w, h = x1 - x0, y1 - y0
        self._fill(ov, box, (255, 255, 255, 34), self.mask(w, h, h // 2))
        fw = int(w * max(0.0, min(1.0, frac)))
        if fw >= h:
            b = (x0, y0, x0 + fw, y1)
            self._grad_fill(ov, b, VIOLET, CYAN, h // 2)
            self.sheen(ov, b, h // 2, 70)

    def dot(self, ov, cx, cy, color, r=5):
        self._fill(ov, (cx - r, cy - r, cx + r, cy + r), color + (255,), self.mask(2 * r, 2 * r, r))

    def logo(self, ov, xy, text, size, c1=(196, 181, 253), c2=(103, 232, 249)):
        key = (text, size)
        if key not in self._logo:
            f = pil_font(size)
            l, t, r, b = f.getbbox(text)
            w, h = r - l + 4, b - t + 8
            m = Image.new("L", (w, h), 0)
            ImageDraw.Draw(m).text((2 - l, 2 - t), text, font=f, fill=255)
            layer = self.grad(w, h, c1, c2).convert("RGBA")
            layer.putalpha(m)
            self._logo[key] = layer
        self._comp(ov, self._logo[key], xy[0], xy[1])

    def asset(self, name):
        from .common import RES
        return Image.open(os.path.join(RES, "assets", name)).convert("RGBA")

    def background(self):
        if getattr(self, "_bg", None) is None:
            sw, sh = 200, max(40, int(200 * self.h / self.w))
            im = Image.new("RGB", (sw, sh), BASE)
            d = ImageDraw.Draw(im)
            d.ellipse((-60, -50, 90, 70), fill=(46, 24, 120))
            d.ellipse((120, sh - 50, 270, sh + 70), fill=(36, 20, 100))
            d.ellipse((70, sh // 2 - 20, 150, sh // 2 + 40), fill=(20, 12, 56))
            im = im.filter(ImageFilter.GaussianBlur(26)).resize((self.w, self.h), Image.BILINEAR)
            self._bg = im
        return self._bg

    def image(self, ov, img, xy):
        self._comp(ov, img, xy[0], xy[1])

    def telegram_icon(self, s=36, hover=False):
        return self.glyph("plane", s, (255, 255, 255, 255) if hover else (176, 160, 255, 255))

    def glyph(self, name, size, color=(255, 255, 255, 255)):
        """Простые векторные иконки (24x24 сетка), рисуются маской и красятся в нужный цвет."""
        key = ("gl", name, size, color)
        if key in self._tg:
            return self._tg[key]
        S = 4
        n = size * S
        u = n / 24.0
        m = Image.new("L", (n, n), 0)
        d = ImageDraw.Draw(m)
        P = lambda pts: [(x * u, y * u) for x, y in pts]
        E = lambda a, b, c, e, f=255: d.ellipse((a * u, b * u, c * u, e * u), fill=f)
        R = lambda a, b, c, e, r=0, f=255: d.rounded_rectangle((a * u, b * u, c * u, e * u), r * u, fill=f)
        L = lambda pts, w=3: d.line(P(pts), fill=255, width=max(1, int(w * u)), joint="curve")
        if name == "home":
            d.polygon(P([(3, 12), (12, 3), (21, 12), (18, 12), (18, 21), (14, 21), (14, 14), (10, 14), (10, 21), (6, 21), (6, 12)]), fill=255)
        elif name == "gear":
            import math
            for k in range(8):
                a = k * math.pi / 4
                c, sn = math.cos(a), math.sin(a)
                pts = [(12 + c * dx - sn * dy, 12 + sn * dx + c * dy) for dx, dy in ((-2, -10), (2, -10), (2, 0), (-2, 0))]
                d.polygon(P(pts), fill=255)
            E(5, 5, 19, 19); E(9, 9, 15, 15, 0)
        elif name == "user":
            E(8, 3, 16, 11); E(4, 14, 20, 30)
        elif name == "puzzle":
            R(4, 8, 20, 21, 3); E(9, 3, 15, 9); E(17, 11, 23, 17)
        elif name == "bolt":
            d.polygon(P([(13, 2), (5, 13), (11, 13), (10, 22), (19, 10), (13, 10)]), fill=255)
        elif name == "play":
            d.polygon(P([(6, 3), (20, 12), (6, 21)]), fill=255)
        elif name == "megaphone":
            d.polygon(P([(3, 9), (8, 9), (18, 4), (18, 20), (8, 15), (3, 15)]), fill=255); R(8, 15, 11.5, 21, 1)
        elif name == "clock":
            E(3, 3, 21, 21); E(5, 5, 19, 19, 0); L([(12, 7), (12, 12), (16, 14)], 2)
        elif name == "chev":
            L([(6, 9), (12, 15), (18, 9)], 3)
        elif name == "chevr":
            L([(9, 5), (16, 12), (9, 19)], 3)
        elif name == "arrow":
            L([(3, 12), (20, 12)], 3); L([(14, 6), (20, 12), (14, 18)], 3)
        elif name == "back":
            L([(21, 12), (5, 12)], 3); L([(11, 6), (5, 12), (11, 18)], 3)
        elif name == "download":
            L([(12, 3), (12, 14)], 3); d.polygon(P([(6, 11), (18, 11), (12, 18)]), fill=255); R(4, 20, 20, 22.5, 1)
        elif name == "exit":
            R(3, 3, 13, 21, 2); R(5, 5, 13, 19, 0, 0); L([(10, 12), (20, 12)], 3); d.polygon(P([(17, 7), (23, 12), (17, 17)]), fill=255)
        elif name == "check":
            L([(5, 12.5), (10, 17), (19, 7)], 3.4)
        elif name == "plane":
            d.polygon(P([(2, 11), (22, 3), (19, 20), (12, 15), (9, 20), (9, 14)]), fill=255)
            d.line(P([(9, 14), (17, 8)]), fill=0, width=max(1, int(1.2 * u)))
        elif name == "lock":
            R(5, 10, 19, 22, 3); d.arc((7.5 * u, 2 * u, 16.5 * u, 15 * u), 180, 360, fill=255, width=max(1, int(2.6 * u)))
        elif name == "key":
            E(3, 6, 13, 16); E(6, 9, 10, 13, 0); R(12, 10, 22, 12.6, 1); R(18, 12, 20.4, 16, 0.5)
        elif name == "eye":
            E(1.5, 6, 22.5, 18); E(7.5, 7.5, 16.5, 16.5, 0); E(9.5, 9.5, 14.5, 14.5)
        elif name == "eyeoff":
            E(1.5, 6, 22.5, 18); E(7.5, 7.5, 16.5, 16.5, 0); E(9.5, 9.5, 14.5, 14.5); L([(4, 21), (20, 3)], 2.6)
        m = m.resize((size, size), Image.LANCZOS)
        layer = Image.new("RGBA", (size, size), color)
        layer.putalpha(ImageChops.multiply(m, Image.new("L", (size, size), color[3])))
        self._tg[key] = layer
        return layer

    def gl(self, ov, name, cx, cy, size, color=(255, 255, 255, 255)):
        self._comp(ov, self.glyph(name, size, color), int(cx - size / 2), int(cy - size / 2))

    def checkbox(self, ov, box, on, hover=False):
        x0, y0, x1, y1 = box
        w, h = x1 - x0, y1 - y0
        if on:
            self._grad_fill(ov, box, VIOLET, CYAN, 5, hover)
            self.gl(ov, "check", x0 + w / 2, y0 + h / 2, int(h * 0.8), (255, 255, 255, 255))
        else:
            self._fill(ov, box, (255, 255, 255, 30 if hover else 16), self.mask(w, h, 5))
            self._fill(ov, box, (255, 255, 255, 80), self.mask(w, h, 5, 1))

    def icon(self, s=64):
        try:
            from .common import RES
            return Image.open(os.path.join(RES, "assets", "icon.png")).convert("RGBA").resize((s, s), Image.LANCZOS)
        except Exception:
            pass
        im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        g = self.grad(s, s, VIOLET, CYAN).convert("RGBA")
        g.putalpha(self.mask(s, s, s // 4))
        im.alpha_composite(g)
        f = pil_font(int(s * 0.62))
        d = ImageDraw.Draw(im)
        l, t, r, b = f.getbbox("P")
        d.text(((s - (r - l)) / 2 - l, (s - (b - t)) / 2 - t), "P", font=f, fill=(255, 255, 255, 255))
        return im


# =====================================================================
class Scene:
    """Описание экрана: тексты (canvas), регионы (кнопки/переключатели/ползунки), панели."""
    def __init__(self, host):
        self.host, self.c, self.pt = host, host.canvas, host.painter
        self.regions, self.texts, self.items, self.widgets = [], {}, [], []
        self.under = []
        self.pages, self.tag, self.cur = {}, None, None
        self.dirty = True
        self.hover = None
        self.drag = None
        self._anim_t = time.perf_counter()

    def tick_anim(self):
        now = time.perf_counter()
        dt = now - self._anim_t
        self._anim_t = now
        moving = False
        for r in self.regions:
            if r["kind"] not in ("button", "img"):
                continue
            en = r["en"]() if r["kind"] == "button" else True
            tgt = 1.0 if (r is self.hover and en) else 0.0
            hv = r.get("hv", 0.0)
            nh = hv + (tgt - hv) * min(1.0, dt * 10.0)
            if abs(nh - hv) > 0.0015:
                moving = True
            else:
                nh = tgt
            r["hv"] = nh
        if moving:
            self.refresh()

    # --- тексты ---
    def text(self, key, x, y, s, size=13, bold=False, fill="#e8eaff", anchor="nw", width=None):
        S = self.host.S
        kw = {"width": int(width * S)} if width else {}
        it = self.c.create_text(x * S, y * S, text=s, fill=fill, anchor=anchor,
                                font=("Segoe UI", -max(1, round(size * S)), "bold" if bold else "normal"), **kw)
        self.host.logic[it] = [x, y, size, bold, width]
        self.texts[key] = it
        self.items.append(it)
        self.pages.setdefault(self.tag, []).append(it)
        return it

    def set_text(self, key, s=None, fill=None):
        kw = {}
        if s is not None: kw["text"] = s
        if fill is not None: kw["fill"] = fill
        self.c.itemconfig(self.texts[key], **kw)

    # --- виджеты ---
    def button(self, key, box, label, cb, style="primary", size=14, enabled=None, colors=None, sel=None):
        r = {"kind": "button", "box": box, "cb": cb, "style": style, "en": enabled or (lambda: True),
             "colors": colors or (VIOLET, CYAN), "sel": sel or (lambda: False)}
        r['page'] = self.tag; self.regions.append(r)
        cx, cy = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
        self.text(key, cx, cy, label, size, True, "#ffffff", "center")
        return r

    def switch(self, box, get, set_):
        r = {"kind": "switch", "box": box, "get": get, "set": set_}
        r['page'] = self.tag; self.regions.append(r)
        return r

    def slider(self, box, get, set_, lo, hi, step):
        r = {"kind": "slider", "box": box, "get": get, "set": set_, "lo": lo, "hi": hi, "step": step}
        r['page'] = self.tag; self.regions.append(r)
        return r

    def bar(self, box, get):
        self.regions.append({"kind": "bar", "box": box, "get": get, "page": self.tag})

    def dot(self, cx, cy, color_fn, r=5):
        self.regions.append({"kind": "dot", "c": (cx, cy), "col": color_fn, "r": r, "page": self.tag})

    def imgbtn(self, box, img, hover, cb, sel=None):
        r = {"kind": "img", "box": box, "img": img, "hover": hover, "cb": cb, "sel": sel or (lambda: False),
             "style": "img", "en": lambda: True, "page": self.tag}
        self.regions.append(r)

    def check(self, box, get, set_):
        r = {"kind": "check", "box": box, "get": get, "set": set_, "page": self.tag}
        self.regions.append(r)
        return r

    def link(self, box, cb):
        r = {"kind": "link", "box": box, "cb": cb, "page": self.tag}
        self.regions.append(r)
        return r

    def glyph(self, name, cx, cy, size, col=(255, 255, 255, 255)):
        """col — кортеж RGBA или функция, возвращающая его (для состояний)."""
        self.regions.append({"kind": "glyph", "name": name, "c": (cx, cy), "size": size, "col": col, "page": self.tag})

    def entry(self, box, text):
        e = self.host.entry(box, text)
        self.widgets.append(e)
        self.pages.setdefault(self.tag, []).append(e._win)
        return e

    def set_page(self, name):
        self.cur = name
        for tg, its in self.pages.items():
            for i in its:
                self.c.itemconfig(i, state="normal" if tg in (None, name) else "hidden")
        self.refresh()

    def _vis(self, r):
        return r.get("page") in (None, self.cur)

    # --- рисование ---
    def paint(self):
        cache = self.__dict__.setdefault("_under_cache", {})
        base = cache.get(self.cur)
        if base is None:
            base = Image.new("RGBA", (self.pt.w, self.pt.h), (0, 0, 0, 0))
            for f in self.under:
                if isinstance(f, tuple):
                    if f[0] in (None, self.cur):
                        f[1](base)
                else:
                    f(base)
            cache[self.cur] = base
        ov = base.copy()
        for r in self.regions:
            if not self._vis(r):
                continue
            k, hv = r["kind"], r.get("hv", 0.0)
            if k == "button":
                en = r["en"]()
                accent = r["style"] == "primary" or (r["style"] == "nav" and r["sel"]())
                if r["style"] == "nav" and not accent:
                    x0, y0, x1, y1 = r["box"]
                    if hv > 0.02:
                        self.pt._fill(ov, r["box"], (255, 255, 255, int(22 * hv)), self.pt.mask(x1 - x0, y1 - y0, 12))
                else:
                    self.pt.glassbtn(ov, r["box"], hv, en, accent)
            elif k == "switch":
                self.pt.switch(ov, r["box"], r["get"](), hv)
            elif k == "slider":
                self.pt.slider(ov, r["box"], (r["get"]() - r["lo"]) / (r["hi"] - r["lo"]))
            elif k == "bar":
                self.pt.bar(ov, r["box"], r["get"]())
            elif k == "dot":
                self.pt.dot(ov, r["c"][0], r["c"][1], r["col"](), r.get("r", 5))
            elif k == "check":
                self.pt.checkbox(ov, r["box"], r["get"](), r is self.hover)
            elif k == "glyph":
                col = r["col"]() if callable(r["col"]) else r["col"]
                self.pt.gl(ov, r["name"], r["c"][0], r["c"][1], r["size"], col)
            elif k == "img":
                b = r["box"]
                self.pt.image(ov, r["img"], (b[0], b[1]))
                if hv > 0.01:
                    layer = r["hover"].copy()
                    a = layer.getchannel("A").point(lambda v, hv=hv: int(v * hv))
                    layer.putalpha(a)
                    self.pt.image(ov, layer, (b[0], b[1]))
                if r["sel"]():
                    self.pt._fill(ov, b, (255, 255, 255, 70), self.pt.mask(b[2] - b[0], b[3] - b[1], 10, 2))
        return ov

    def refresh(self):
        self.dirty = True

    def destroy(self):
        for i in self.items:
            self.host.logic.pop(i, None)
            self.c.delete(i)
        for w in self.widgets:
            try: w.destroy()
            except Exception: pass

    # --- события ---
    def _hit(self, x, y):
        for r in reversed(self.regions):
            if not self._vis(r):
                continue
            if "box" not in r or r["kind"] in ("bar",):
                continue
            x0, y0, x1, y1 = r["box"]
            pad = 8 if r["kind"] == "slider" else 0
            if x0 <= x <= x1 and y0 - pad <= y <= y1 + pad:
                if r["kind"] == "button" and not r["en"]():
                    continue
                return r
        return None

    def _slide(self, r, x):
        x0, _, x1, _ = r["box"]
        f = max(0.0, min(1.0, (x - x0) / (x1 - x0)))
        v = r["lo"] + f * (r["hi"] - r["lo"])
        v = int(round(v / r["step"]) * r["step"])
        r["set"](max(r["lo"], min(r["hi"], v)))
        self.refresh()

    def motion(self, x, y):
        h = self._hit(x, y)
        if h is not self.hover:
            self.hover = h
            self.refresh()
        self.c.config(cursor="hand2" if h else "")

    def press(self, x, y):
        r = self._hit(x, y)
        if not r:
            return
        if r["kind"] in ("button", "img", "link"):
            r["cb"]()
        elif r["kind"] == "check":
            r["set"](not r["get"]())
        elif r["kind"] == "switch":
            r["set"](not r["get"]())
        elif r["kind"] == "slider":
            self.drag = r
            self._slide(r, x)
        self.refresh()

    def move(self, x, y):
        if self.drag:
            self._slide(self.drag, x)

    def release(self, x, y):
        self.drag = None


# =====================================================================
class Host:
    def __init__(self, title, w, h):
        import tkinter as tk
        from PIL import ImageTk
        self.tk, self.ImageTk = tk, ImageTk
        try:   # чёткая картинка при масштабе Windows 125–200%
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
        self.root = tk.Tk()
        self.root.title(title)
        self.W, self.H = w, h
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        # стартовый масштаб по разрешению экрана: окно занимает ~80% экрана, пропорции сохраняются
        self.S = round(max(1.0, min(sw * 0.80 / w, sh * 0.82 / h, 2.5)), 3)
        cw, ch = int(w * self.S), int(h * self.S)
        self.logic, self.entries, self._force, self._rs = {}, [], True, None
        self.root.configure(bg="#08061a")
        self.root.minsize(w, h)
        self.root.geometry(f"{cw}x{ch}+{max(0, (sw-cw)//2)}+{max(0, (sh-ch)//3)}")
        try:
            self.root.aspect(w, h, w, h)   # держим пропорции при растягивании окна
        except Exception:
            pass
        self.painter = Painter(w, h)
        self.canvas = tk.Canvas(self.root, width=cw, height=ch, highlightthickness=0, bd=0, bg="#08061a")
        self.canvas.pack(expand=True)
        self.bg = self.canvas.create_image(0, 0, anchor="nw")
        import random
        self.rnd = random
        self.flakes = []
        for i in range(22):
            x, y, r = random.uniform(0, w), random.uniform(0, h), random.choice((1, 1.5, 2))
            it = self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=random.choice(("#9d85ff", "#7c5cff", "#c9bcff")), width=0)
            self.flakes.append([it, x, y, random.uniform(0.2, 0.6) * (r / 2 + 0.4), random.uniform(0, 6.28), random.uniform(0.01, 0.03), r])
        for i in range(5):
            x, y = random.uniform(0, w), random.uniform(0, h)
            it = self.canvas.create_text(x, y, text="✦", fill="#6d4df0", font=("Segoe UI Symbol", -random.choice((10, 12, 14))))
            self.flakes.append([it, x, y, random.uniform(0.2, 0.5), random.uniform(0, 6.28), random.uniform(0.01, 0.025), 0])
        self.scene = None
        self.q = queue.Queue()
        self.t0 = time.time()
        self.overlay = None
        try:
            self._icon = ImageTk.PhotoImage(self.painter.icon(64))
            self.root.iconphoto(True, self._icon)
        except Exception:
            pass
        c = self.canvas
        c.bind("<Motion>", lambda e: self.scene and self.scene.motion(e.x / self.S, e.y / self.S))
        c.bind("<Button-1>", lambda e: self.scene and self.scene.press(e.x / self.S, e.y / self.S))
        c.bind("<B1-Motion>", lambda e: self.scene and self.scene.move(e.x / self.S, e.y / self.S))
        c.bind("<ButtonRelease-1>", lambda e: self.scene and self.scene.release(e.x / self.S, e.y / self.S))
        self.root.bind("<Configure>", self._on_cfg)

    # ---------- масштабирование ----------
    def _on_cfg(self, e):
        if e.widget is not self.root:
            return
        if self._rs:
            self.root.after_cancel(self._rs)
        self._rs = self.root.after(40, self._apply_size)

    def _apply_size(self):
        self._rs = None
        try:
            ns = max(1.0, min(self.root.winfo_width() / self.W, self.root.winfo_height() / self.H, 4.0))
        except Exception:
            return
        if abs(ns - self.S) > 0.004:
            self.rescale(ns)

    def rescale(self, S):
        self.S = S
        cw, ch = int(self.W * S), int(self.H * S)
        c = self.canvas
        c.config(width=cw, height=ch)
        for it, (x, y, size, bold, width) in list(self.logic.items()):
            try:
                c.coords(it, x * S, y * S)
                kw = {"font": ("Segoe UI", -max(1, round(size * S)), "bold" if bold else "normal")}
                if width:
                    kw["width"] = int(width * S)
                c.itemconfig(it, **kw)
            except Exception:
                self.logic.pop(it, None)
        for e, box in list(self.entries):
            try:
                c.coords(e._win, box[0] * S, box[1] * S)
                c.itemconfig(e._win, width=int((box[2] - box[0]) * S), height=int((box[3] - box[1]) * S))
                e.config(font=("Segoe UI", -max(1, round(15 * S))))
            except Exception:
                self.entries.remove((e, box))
        self._force = True

    def place(self, it, x, y):
        """Двигает canvas-элемент в логических координатах (880x620 и т.п.)."""
        if it in self.logic:
            self.logic[it][0], self.logic[it][1] = x, y
        self.canvas.coords(it, x * self.S, y * self.S)

    def entry(self, box, text):
        tk = self.tk
        e = tk.Entry(self.root, bd=0, relief="flat", bg="#0f0c2a", fg="#ffffff", insertbackground="#ffffff",
                     font=("Segoe UI", -max(1, round(15 * self.S))), highlightthickness=1, highlightbackground="#0f0c2a",
                     highlightcolor="#0f0c2a", disabledbackground="#0f0c2a")
        e.insert(0, text)
        S = self.S
        e._win = self.canvas.create_window(box[0] * S, box[1] * S, anchor="nw", window=e,
                                           width=int((box[2] - box[0]) * S), height=int((box[3] - box[1]) * S))
        self.entries.append((e, tuple(box)))
        return e

    def set_scene(self, scene):
        if self.scene:
            self.scene.destroy()
        self.scene = scene
        self.overlay = None

    def post(self, fn):
        self.q.put(fn)

    def _tick(self):
        t0 = time.perf_counter()
        try:
            while True:
                self.q.get_nowait()()
        except queue.Empty:
            pass
        except Exception:
            traceback.print_exc()
        try:
            if self.scene and self.root.state() != "iconic":
                self.scene.tick_anim()
                if self.scene.dirty or self.overlay is None or self._force:
                    if self.scene.dirty or self.overlay is None:
                        self.overlay = self.scene.paint()
                        self.scene.dirty = False
                    self._force = False
                    frame = self.painter.background().copy()
                    frame.paste(self.overlay, (0, 0), self.overlay)
                    if abs(self.S - 1.0) > 0.001:
                        frame = frame.resize((int(self.W * self.S), int(self.H * self.S)), Image.BILINEAR)
                    self._photo = self.ImageTk.PhotoImage(frame)
                    self.canvas.itemconfig(self.bg, image=self._photo)
                self._snow()
        except Exception:
            traceback.print_exc()
        dt = (time.perf_counter() - t0) * 1000
        self.root.after(max(20, int(40 - dt)), self._tick)

    def _snow(self):
        import math
        c = self.canvas
        for f in self.flakes:
            it, x, y, v, ph, dph, r = f
            y += v
            ph += dph
            x += math.sin(ph) * 0.6
            if y > self.H + 10:
                y, x = -10, self.rnd.uniform(0, self.W)
            f[1], f[2], f[4] = x, y, ph
            S = self.S
            if r:
                c.coords(it, (x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S)
            else:
                c.coords(it, x * S, y * S)

    def run(self):
        self._tick()
        self.root.mainloop()
