# -*- coding: utf-8 -*-
"""Градиентный интерфейс: Pillow рисует фон и стекло, Tk — текст и ввод."""
import math, os, time, queue, traceback
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageFont

VIOLET, PINK, CYAN, BLUE = (139, 92, 246), (192, 132, 252), (186, 200, 255), (99, 102, 241)

BLOBS = [  # cx, cy, ax, ay, fx, fy, phase, radius, color, gain
    (0.12, 0.18, 0.10, 0.08, 0.21, 0.17, 0.0, 0.36, VIOLET, 1.00),
    (0.88, 0.22, 0.08, 0.10, 0.17, 0.23, 1.7, 0.30, PINK, 0.80),
    (0.62, 0.95, 0.14, 0.06, 0.19, 0.13, 3.1, 0.40, CYAN, 0.70),
    (0.08, 0.88, 0.07, 0.09, 0.15, 0.25, 4.4, 0.30, BLUE, 0.85),
]
BASE = (12, 9, 36)
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
            c1 = tuple(int(a + (b - a) * hv * 0.35) for a, b in zip((70, 50, 150), VIOLET))
            c2 = tuple(int(a + (b - a) * hv * 0.35) for a, b in zip((60, 44, 130), CYAN))
            self._grad_fill(ov, box, c1, c2, r, False)
            self._fill(ov, box, (255, 255, 255, int(10 + 28 * hv)), self.mask(w, h, r))
        else:
            self._fill(ov, box, (255, 255, 255, base if enabled else 16), self.mask(w, h, r))
        border = 48 + int(40 * hv) if enabled else 30
        self._fill(ov, box, (255, 255, 255, border), self.mask(w, h, r, 1))
        self.sheen(ov, box, r, int(30 + 35 * hv) if enabled else 14)

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
            try:
                im = self.asset("scene.png").convert("RGB")
                sc = max(self.w / im.width, self.h / im.height)
                im = im.resize((int(im.width * sc) + 1, int(im.height * sc) + 1), Image.LANCZOS)
                l, t = (im.width - self.w) // 2, (im.height - self.h) // 2
                im = im.crop((l, t, l + self.w, t + self.h)).filter(ImageFilter.GaussianBlur(5))
                im = Image.blend(im, Image.new("RGB", im.size, (22, 12, 64)), 0.45)
            except Exception:
                im = self.mesh(0)
            self._bg = im
        return self._bg

    def image(self, ov, img, xy):
        self._comp(ov, img, xy[0], xy[1])

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
        kw = {"width": width} if width else {}
        it = self.c.create_text(x, y, text=s, fill=fill, anchor=anchor,
                                font=("Segoe UI", -size, "bold" if bold else "normal"), **kw)
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

    def dot(self, cx, cy, color_fn):
        self.regions.append({"kind": "dot", "c": (cx, cy), "col": color_fn, "page": self.tag})

    def imgbtn(self, box, img, hover, cb, sel=None):
        r = {"kind": "img", "box": box, "img": img, "hover": hover, "cb": cb, "sel": sel or (lambda: False),
             "style": "img", "en": lambda: True, "page": self.tag}
        self.regions.append(r)

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
                self.pt.glassbtn(ov, r["box"], hv, en, accent)
            elif k == "switch":
                self.pt.switch(ov, r["box"], r["get"](), hv)
            elif k == "slider":
                self.pt.slider(ov, r["box"], (r["get"]() - r["lo"]) / (r["hi"] - r["lo"]))
            elif k == "bar":
                self.pt.bar(ov, r["box"], r["get"]())
            elif k == "dot":
                self.pt.dot(ov, r["c"][0], r["c"][1], r["col"]())
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
        if r["kind"] in ("button", "img"):
            r["cb"]()
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
        self.root = tk.Tk()
        self.root.title(title)
        self.root.resizable(False, False)
        self.root.geometry(f"{w}x{h}+{(self.root.winfo_screenwidth()-w)//2}+{(self.root.winfo_screenheight()-h)//3}")
        self.painter = Painter(w, h)
        self.canvas = tk.Canvas(self.root, width=w, height=h, highlightthickness=0, bd=0, bg="#09081c")
        self.canvas.pack()
        self.bg = self.canvas.create_image(0, 0, anchor="nw")
        import random
        self.rnd = random
        self.flakes = []
        for i in range(34):
            x, y, r = random.uniform(0, w), random.uniform(0, h), random.choice((1.5, 2, 2, 3))
            it = self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=random.choice(("#ffffff", "#e6e0ff", "#cfd8ff")), width=0)
            self.flakes.append([it, x, y, random.uniform(0.6, 1.6) * (r / 2 + 0.4), random.uniform(0, 6.28), random.uniform(0.01, 0.03), r])
        for i in range(9):
            x, y = random.uniform(0, w), random.uniform(0, h)
            it = self.canvas.create_text(x, y, text=random.choice("❄✦❅"), fill="#e8e2ff", font=("Segoe UI Symbol", -random.choice((12, 14, 17))))
            self.flakes.append([it, x, y, random.uniform(0.5, 1.1), random.uniform(0, 6.28), random.uniform(0.01, 0.025), 0])
        self.W, self.H = w, h
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
        c.bind("<Motion>", lambda e: self.scene and self.scene.motion(e.x, e.y))
        c.bind("<Button-1>", lambda e: self.scene and self.scene.press(e.x, e.y))
        c.bind("<B1-Motion>", lambda e: self.scene and self.scene.move(e.x, e.y))
        c.bind("<ButtonRelease-1>", lambda e: self.scene and self.scene.release(e.x, e.y))

    def entry(self, box, text):
        tk = self.tk
        e = tk.Entry(self.root, bd=0, relief="flat", bg="#15183a", fg="#ffffff", insertbackground="#ffffff",
                     font=("Segoe UI", -15), highlightthickness=1, highlightbackground="#3b4080",
                     highlightcolor="#8b7cff", disabledbackground="#15183a")
        e.insert(0, text)
        e._win = self.canvas.create_window(box[0], box[1], anchor="nw", window=e, width=box[2] - box[0],
                                  height=box[3] - box[1])
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
                if self.scene.dirty or self.overlay is None:
                    self.overlay = self.scene.paint()
                    self.scene.dirty = False
                    frame = self.painter.background().copy()
                    frame.paste(self.overlay, (0, 0), self.overlay)
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
            if r:
                c.coords(it, x - r, y - r, x + r, y + r)
            else:
                c.coords(it, x, y)

    def run(self):
        self._tick()
        self.root.mainloop()
