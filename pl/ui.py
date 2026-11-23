# -*- coding: utf-8 -*-
"""Лёгкий интерфейс DCODE.

Все формы (кнопки, поля, ползунок, фон) Pillow рисует ОДИН раз с антиалиасингом,
дальше Tk только двигает готовые картинки — никакой покадровой перерисовки, поэтому нет лагов.
Окно — настоящий top-level без системной рамки (стили Win32): скруглённая форма,
кнопка в панели задач, Alt+Tab и сворачивание остаются штатными.
"""
import math, os, sys, time, queue, traceback
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageFont

WIN = sys.platform.startswith("win")
BASE = (7, 4, 16)
V1, V2, V3 = (109, 40, 217), (168, 85, 247), (232, 121, 249)
TXT, SUB, DIM = "#ffffff", "#cdbdf7", "#8b7bb8"
BAD, GOOD = "#fb7185", "#86efac"
FIELD = (14, 10, 32)
FONTS = ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Helvetica.ttc"]


def hexc(c):
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, v))) for v in c[:3])


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def ease(t):
    return 1 - (1 - t) ** 3


def ease_io(t):
    return t * t * (3 - 2 * t)


@lru_cache(maxsize=16)
def pil_font(size):
    for p in FONTS:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default(size)


def asset(name):
    from .common import RES
    return Image.open(os.path.join(RES, "assets", name)).convert("RGBA")


# ---------- формы (Pillow, один раз) ----------
def _mask(w, h, r, ss=3):
    m = Image.new("L", (max(1, w * ss), max(1, h * ss)), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), radius=r * ss, fill=255)
    return m.resize((max(1, w), max(1, h)), Image.LANCZOS)


def _grad(w, h, c1, c2):
    g = Image.new("RGBA", (max(1, w), 1))
    px = g.load()
    for x in range(g.width):
        c = mix(c1, c2, x / max(1, g.width - 1))
        px[x, 0] = (int(c[0]), int(c[1]), int(c[2]), 255)
    return g.resize((max(1, w), max(1, h)))


@lru_cache(maxsize=256)
def shape(w, h, r, fill=None, outline=None, ow=2, grad=None):
    w, h = max(2, w), max(2, h)
    r = min(r, h // 2, w // 2)
    m = _mask(w, h, r)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    src = _grad(w, h, grad[0], grad[1]) if grad else (Image.new("RGBA", (w, h), fill) if fill else None)
    if src is not None:
        src.putalpha(ImageChops.multiply(m, src.getchannel("A")))
        out.alpha_composite(src)
    if outline:
        ow = max(1, ow)
        inner = Image.new("L", (w, h), 0)
        if w - 2 * ow > 2 and h - 2 * ow > 2:
            inner.paste(_mask(w - 2 * ow, h - 2 * ow, max(1, r - ow)), (ow, ow))
        ring = ImageChops.subtract(m, inner)
        o = Image.new("RGBA", (w, h), outline)
        o.putalpha(ImageChops.multiply(ring, o.getchannel("A")))
        out.alpha_composite(o)
    return out


@lru_cache(maxsize=32)
def glow(w, h, r, color, blur, pad, alpha=0.4):
    m = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    ImageDraw.Draw(m).rounded_rectangle((pad, pad, pad + w, pad + h), radius=r, fill=int(255 * alpha))
    m = m.filter(ImageFilter.GaussianBlur(blur))
    o = Image.new("RGBA", m.size, color + (255,))
    o.putalpha(m)
    return o


@lru_cache(maxsize=8)
def radial(d, color, alpha=0.5):
    m = Image.new("L", (d, d), 0)
    ImageDraw.Draw(m).ellipse((d * 0.22, d * 0.22, d * 0.78, d * 0.78), fill=int(255 * alpha))
    m = m.filter(ImageFilter.GaussianBlur(d * 0.14))
    o = Image.new("RGBA", (d, d), color + (255,))
    o.putalpha(m)
    return o


def knob_img(d):
    ss = 4
    n = d * ss
    g = Image.new("RGBA", (n, 1))
    px = g.load()
    for y in range(n):
        c = mix(V2, V3, y / n)
        px[y, 0] = (int(c[0]), int(c[1]), int(c[2]), 255)
    g = g.resize((n, n))
    big = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    mk = Image.new("L", (n, n), 0)
    ImageDraw.Draw(mk).ellipse((0, 0, n - 1, n - 1), fill=255)
    big.paste(g.transpose(Image.ROTATE_270), (0, 0), mk)
    dr = ImageDraw.Draw(big)
    pts = [(n * .43, n * .30), (n * .62, n * .5), (n * .43, n * .70)]
    lw = int(n * .085)
    dr.line(pts, fill=(255, 255, 255, 255), width=lw, joint="curve")
    for p in (pts[0], pts[2]):
        dr.ellipse((p[0] - lw / 2, p[1] - lw / 2, p[0] + lw / 2, p[1] + lw / 2), fill=(255, 255, 255, 255))
    return big.resize((d, d), Image.LANCZOS)


def make_bg(W, H, S, radius):
    pw, ph = int(W * S), int(H * S)
    sw, sh = max(40, W // 3), max(30, H // 3)
    im = Image.new("RGB", (sw, sh), BASE)
    d = ImageDraw.Draw(im)
    d.ellipse((sw * 0.08, -sh * 0.55, sw * 0.80, sh * 0.55), fill=(62, 24, 138))
    d.ellipse((sw * 0.55, sh * 0.62, sw * 1.30, sh * 1.55), fill=(84, 30, 160))
    d.ellipse((-sw * 0.25, sh * 0.70, sw * 0.38, sh * 1.35), fill=(36, 16, 90))
    im = im.filter(ImageFilter.GaussianBlur(sw * 0.11)).resize((pw, ph), Image.BICUBIC)
    n = Image.effect_noise((pw, ph), 40).point(lambda x: (x - 118) // 22 if x > 118 else 0)
    im = ImageChops.add(im, Image.merge("RGB", (n, n, n)))
    rr = shape(pw, ph, int(radius * S), outline=(139, 92, 246, 110), ow=max(1, round(1.5 * S)))
    im.paste(rr, (0, 0), rr)
    return im


# ---------- виджеты ----------
class Widget:
    page = None
    box = (0, 0, 0, 0)

    def hit(self, x, y):
        x0, y0, x1, y1 = self.box
        return x0 <= x <= x1 and y0 <= y <= y1 and self.page in (None, self.host.page)

    def hover(self, on): pass
    def press(self, x, y): pass
    def drag(self, x, y): pass
    def release(self, x, y): pass


class Button(Widget):
    def __init__(self, host, page, box, text, cb, style="primary", size=14, enabled=None):
        self.host, self.page, self.box, self.cb = host, page, box, cb
        self.enabled = enabled or (lambda: True)
        S = host.S
        w, h = int((box[2] - box[0]) * S), int((box[3] - box[1]) * S)
        if style == "primary":
            r = h // 2
            n, hv = shape(w, h, r, grad=(V1, V2)), shape(w, h, r, grad=(V2, V3))
            host.image(box[0] - 18, box[1] - 14, glow(w, h, r, V2, int(10 * S), int(18 * S), 0.45), page)
        else:
            r, o = int(12 * S), max(1, round(S))
            n = shape(w, h, r, fill=(255, 255, 255, 14), outline=(255, 255, 255, 40), ow=o)
            hv = shape(w, h, r, fill=(255, 255, 255, 30), outline=(190, 150, 255, 120), ow=o)
        self.ph_n, self.ph_h = host.photo(n), host.photo(hv)
        self.it = host.canvas.create_image(box[0] * S, box[1] * S, image=self.ph_n, anchor="nw", tags=(page,))
        host._items.append(self.it)
        self.t = host.text(page, (box[0] + box[2]) / 2, (box[1] + box[3]) / 2, text, size, True, TXT, "center")
        self.on = False
        host.widgets.append(self)

    def set_text(self, s):
        self.host.set_text(self.t, s)

    def hover(self, on):
        if on != self.on:
            self.on = on
            self.host.canvas.itemconfig(self.it, image=self.ph_h if on else self.ph_n)

    def press(self, x, y):
        self.cb()

    def hit(self, x, y):
        return self.enabled() and super().hit(x, y)


class Link(Widget):
    def __init__(self, host, page, x, y, text, cb, size=11, anchor="center", color="#a78bfa"):
        self.host, self.page, self.cb, self.color = host, page, cb, color
        self.t = host.text(page, x, y, text, size, False, color, anchor)
        b = host.canvas.bbox(self.t)
        S = host.S
        self.box = (b[0] / S - 8, b[1] / S - 6, b[2] / S + 8, b[3] / S + 6)
        host.widgets.append(self)

    def hit(self, x, y):
        return self.host.canvas.itemcget(self.t, "state") != "hidden" and super().hit(x, y)

    def hover(self, on):
        self.host.canvas.itemconfig(self.t, fill="#ffffff" if on else self.color)

    def press(self, x, y):
        self.cb()


class Check(Widget):
    def __init__(self, host, page, x, y, text, value=True, size=11):
        self.host, self.page, self.val = host, page, value
        S = host.S
        d = int(20 * S)
        off = shape(d, d, int(6 * S), fill=FIELD + (255,), outline=(255, 255, 255, 60), ow=max(1, round(S)))
        on = shape(d, d, int(6 * S), grad=(V1, V3)).copy()
        ImageDraw.Draw(on).line([(d * .26, d * .52), (d * .44, d * .70), (d * .76, d * .32)],
                                fill=(255, 255, 255, 255), width=max(2, int(2 * S)), joint="curve")
        self.ph_off, self.ph_on = host.photo(off), host.photo(on)
        self.it = host.canvas.create_image(x * S, y * S, image=self.ph_on if value else self.ph_off, anchor="w", tags=(page,))
        host._items.append(self.it)
        self.t = host.text(page, x + 28, y, text, size, False, "#e8e0ff", "w")
        b = host.canvas.bbox(self.t)
        self.box = (x - 4, y - 14, b[2] / S + 6, y + 14)
        host.widgets.append(self)

    def press(self, x, y):
        self.val = not self.val
        self.host.canvas.itemconfig(self.it, image=self.ph_on if self.val else self.ph_off)


class Bar:
    def __init__(self, host, page, x, y, w, h=8):
        self.host = host
        S = host.S
        self.w, self.h = int(w * S), int(h * S)
        self.tr = host.canvas.create_image(x * S, y * S, anchor="nw", tags=(page,),
                                           image=host.photo(shape(self.w, self.h, self.h // 2, fill=(255, 255, 255, 22))))
        self.fi = host.canvas.create_image(x * S, y * S, anchor="nw", tags=(page,), state="hidden")
        host._items += [self.tr, self.fi]
        self._last, self._ph = -1, None

    def set(self, f):
        px = int(self.w * max(0.0, min(1.0, f)))
        if px == self._last:
            return
        self._last = px
        if px < self.h:
            return self.host.canvas.itemconfig(self.fi, state="hidden")
        self._ph = self.host.photo(shape(px, self.h, self.h // 2, grad=(V1, V3)))
        self.host.canvas.itemconfig(self.fi, image=self._ph, state="normal")


class Pull(Widget):
    """«Потяните, чтобы запустить». В режиме busy превращается в полосу прогресса."""
    PAD = 6

    def __init__(self, host, page, cx, y, w=440, h=64, text="Потяните, чтобы запустить", on_trigger=None):
        self.host, self.page, self.on_trigger, self.text0 = host, page, on_trigger, text
        S = host.S
        self.w, self.h, self.x0, self.y0 = w, h, cx - w / 2, y
        self.box = (self.x0, y - 6, self.x0 + w, y + h + 6)
        self.kd = h - 2 * self.PAD
        self.span = w - 2 * self.PAD - self.kd
        self.v, self.mode, self.prog, self.ind, self.dragging, self._spring = 0.0, "idle", 0.0, False, False, None
        P = lambda a: int(round(a * S))
        c = host.canvas
        host.image(self.x0 - 30, y - 24, glow(P(w), P(h), P(h / 2), V2, P(16), P(30), 0.34), page)
        host.image(self.x0, y, shape(P(w), P(h), P(h / 2), fill=(18, 12, 40, 235), outline=(168, 85, 247, 90), ow=max(1, round(1.5 * S))), page)
        self.fill_it = c.create_image(0, 0, anchor="nw", tags=(page,), state="hidden")
        self.sweep_w = P(w * 0.28)
        hh = P(h - 2 * self.PAD)
        self.sweep_ph = host.photo(shape(self.sweep_w, hh, hh // 2, grad=(V1, V3)))
        self.sweep_it = c.create_image(0, 0, anchor="nw", tags=(page,), state="hidden", image=self.sweep_ph)
        self.label = host.text(page, self.x0 + (w + self.kd) / 2, y + h / 2, text, 14, True, SUB, "center")
        self.pct = host.text(page, self.x0 + w - 24, y + h / 2, "", 12, True, TXT, "e")
        self.knob_ph = host.photo(knob_img(P(self.kd)))
        self.knob = c.create_image(0, 0, anchor="nw", image=self.knob_ph, tags=(page,))
        host._items += [self.fill_it, self.sweep_it, self.knob]
        self._fill_ph, self._fill_px = None, -1
        self._layout()
        host.widgets.append(self)

    def _fill(self, px):
        S, c = self.host.S, self.host.canvas
        px = int(px)
        if px != self._fill_px:
            self._fill_px = px
            hh = int((self.h - 2 * self.PAD) * S)
            if px < hh:
                c.itemconfig(self.fill_it, state="hidden")
            else:
                self._fill_ph = self.host.photo(shape(px, hh, hh // 2, grad=(V1, V3)))
                c.itemconfig(self.fill_it, image=self._fill_ph, state="normal")
        c.coords(self.fill_it, (self.x0 + self.PAD) * S, (self.y0 + self.PAD) * S)

    def _layout(self, wob=0.0):
        S, c = self.host.S, self.host.canvas
        if self.mode == "idle":
            kx = self.x0 + self.PAD + self.v * self.span + wob
            c.coords(self.knob, kx * S, (self.y0 + self.PAD) * S)
            c.itemconfig(self.knob, state="normal")
            c.itemconfig(self.sweep_it, state="hidden")
            self._fill((self.v * self.span + self.kd) * S if self.v > 0.004 else 0)
            if self.dragging:
                c.itemconfig(self.label, fill=hexc(mix(rgb(SUB), (30, 20, 70), min(1.0, self.v * 2.4))))
        else:
            c.itemconfig(self.knob, state="hidden")
            if self.ind:
                self._fill(0)
            else:
                self._fill(max(self.kd, self.prog * (self.w - 2 * self.PAD)) * S)
                c.itemconfig(self.sweep_it, state="hidden")

    def set_busy(self, on, label=None):
        self.mode = "busy" if on else "idle"
        self._spring, self.v, self.prog, self.ind, self._fill_px = None, 0.0, 0.0, False, -1
        c, S = self.host.canvas, self.host.S
        cx = self.x0 + (self.w if on else self.w + self.kd) / 2
        c.coords(self.label, cx * S, (self.y0 + self.h / 2) * S)
        c.itemconfig(self.label, text=label if label is not None else ("" if on else self.text0), fill=TXT if on else SUB)
        c.itemconfig(self.pct, text="")
        self._layout()

    def set_label(self, s):
        self.host.canvas.itemconfig(self.label, text=s)

    def set_progress(self, f):
        """f: 0..1 или None — неопределённый прогресс (бегущая вставка)."""
        self.ind = f is None
        c = self.host.canvas
        if f is None:
            c.itemconfig(self.pct, text="")
        else:
            self.prog = max(0.0, min(1.0, f))
            c.itemconfig(self.pct, text="%d%%" % int(self.prog * 100))
            c.itemconfig(self.sweep_it, state="hidden")
        self._layout()

    def hit(self, x, y):
        return self.mode == "idle" and super().hit(x, y)

    def press(self, x, y):
        self._spring, self.dragging = None, True
        self.drag(x, y)

    def drag(self, x, y):
        if self.dragging:
            self.v = max(0.0, min(1.0, (x - self.x0 - self.PAD - self.kd / 2) / self.span))
            self._layout()

    def release(self, x, y):
        if not self.dragging:
            return
        self.dragging = False
        if self.v >= 0.92:
            self.v = 1.0
            self._layout()
            self.host.after(90, lambda: self.on_trigger and self.on_trigger())
        else:
            self._spring = (self.v, time.perf_counter())

    def tick(self, now):
        c = self.host.canvas
        if self.mode == "idle":
            if self._spring:
                v0, t0 = self._spring
                e = min(1.0, (now - t0) / 0.30)
                self.v = v0 * (1 - ease(e))
                if e >= 1.0:
                    self.v, self._spring = 0.0, None
                self._layout()
            elif not self.dragging and self.v == 0.0:
                self._layout(wob=(math.sin(now * 2.6) + 1) / 2 * 5)
                c.itemconfig(self.label, fill=hexc(mix(rgb(DIM), rgb("#e9ddff"), (math.sin(now * 2.0 - 1) + 1) / 2)))
        elif self.ind:
            S = self.host.S
            ph = (now * 0.9) % 2.0
            ph = ph if ph < 1 else 2 - ph
            span = (self.w - 2 * self.PAD) * S - self.sweep_w
            c.coords(self.sweep_it, (self.x0 + self.PAD) * S + ease_io(ph) * span, (self.y0 + self.PAD) * S)
            c.itemconfig(self.sweep_it, state="normal")


# ---------- окно ----------
class Host:
    def __init__(self, title, W, H, radius=22):
        import tkinter as tk
        from PIL import ImageTk
        self.tk, self.ImageTk = tk, ImageTk
        if WIN:
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DCODE.Launcher")
                try:
                    ctypes.windll.shcore.SetProcessDpiAwareness(1)
                except Exception:
                    ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
        self.root = tk.Tk()
        self.root.title(title)
        self.root.configure(bg=hexc(BASE))
        try:
            self.root.attributes("-alpha", 0.0)
        except Exception:
            pass
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        try:
            dpi = self.root.winfo_fpixels("1i") / 96.0
        except Exception:
            dpi = 1.0
        S = max(1.0, min(round(dpi * 4) / 4, 3.0))
        while H * S > sh * 0.94 and S > 1.0:
            S = max(1.0, S - 0.25)
        self.S, self.W, self.H, self.R = S, W, H, radius
        self.cw, self.ch = int(W * S), int(H * S)
        self.root.geometry(f"{self.cw}x{self.ch}+{max(0, (sw - self.cw) // 2)}+{max(0, (sh - self.ch) // 3)}")
        self.root.resizable(False, False)
        self.canvas = tk.Canvas(self.root, width=self.cw, height=self.ch, highlightthickness=0, bd=0, bg=hexc(BASE))
        self.canvas.place(x=0, y=0)
        self._keep, self._items, self.widgets, self.entries, self._pin = [], [], [], [], {}
        self.pages, self.page, self.anims, self.ticks = set(), None, [], []
        self.q = queue.Queue()
        self.hover_w, self.capture, self._wdrag, self._top = None, None, None, None
        self._bgph = ImageTk.PhotoImage(make_bg(W, H, S, radius))
        self.canvas.create_image(0, 0, anchor="nw", image=self._bgph)
        self._icon()
        self._decor()
        self._chrome()
        c = self.canvas
        c.bind("<Motion>", self._motion)
        c.bind("<ButtonPress-1>", self._press)
        c.bind("<B1-Motion>", self._move)
        c.bind("<ButtonRelease-1>", self._release)
        c.bind("<Leave>", lambda e: self._set_hover(None))
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(30, self._win32)

    def _icon(self):
        try:
            from .common import RES
            self.root.iconbitmap(default=os.path.join(RES, "assets", "icon.ico"))
        except Exception:
            pass
        try:
            self._ic = self.ImageTk.PhotoImage(asset("icon.png").resize((64, 64), Image.LANCZOS))
            self.root.iconphoto(True, self._ic)
        except Exception:
            pass

    def photo(self, im):
        p = self.ImageTk.PhotoImage(im)
        self._keep.append(p)
        if len(self._keep) > 400:
            del self._keep[:150]
        return p

    def image(self, x, y, im, page=None, anchor="nw"):
        p = self.ImageTk.PhotoImage(im)
        it = self.canvas.create_image(x * self.S, y * self.S, image=p, anchor=anchor, tags=(page,) if page else ())
        self._pin[it] = p
        self._items.append(it)
        return it

    def text(self, page, x, y, s, size=13, bold=False, fill=TXT, anchor="nw", width=None, justify="left"):
        kw = {"width": int(width * self.S)} if width else {}
        it = self.canvas.create_text(x * self.S, y * self.S, text=s, fill=fill, anchor=anchor, justify=justify,
                                     font=("Segoe UI", -max(1, round(size * self.S)), "bold" if bold else "normal"),
                                     tags=(page,) if page else (), **kw)
        self._items.append(it)
        return it

    def set_text(self, it, s=None, fill=None):
        kw = {}
        if s is not None:
            kw["text"] = s
        if fill is not None:
            kw["fill"] = fill
        self.canvas.itemconfig(it, **kw)

    def field(self, page, box, secret=False, text=""):
        tk, S, c = self.tk, self.S, self.canvas
        w, h = int((box[2] - box[0]) * S), int((box[3] - box[1]) * S)
        pn = self.photo(shape(w, h, int(12 * S), fill=FIELD + (255,), outline=(255, 255, 255, 30), ow=max(1, round(S))))
        pf = self.photo(shape(w, h, int(12 * S), fill=FIELD + (255,), outline=V2 + (200,), ow=max(1, round(1.5 * S))))
        it = c.create_image(box[0] * S, box[1] * S, image=pn, anchor="nw", tags=(page,))
        e = tk.Entry(self.root, bd=0, relief="flat", bg=hexc(FIELD), fg="#ffffff", insertbackground="#ffffff",
                     selectbackground="#6d28d9", selectforeground="#ffffff", highlightthickness=0,
                     font=("Segoe UI", -max(1, round(14 * S))), show="\u2022" if secret else "")
        e.insert(0, text)
        win = c.create_window((box[0] + 14) * S, (box[1] + 6) * S, anchor="nw", window=e, tags=(page,),
                              width=int((box[2] - box[0] - 28) * S), height=int((box[3] - box[1] - 12) * S))
        e.bind("<FocusIn>", lambda ev: c.itemconfig(it, image=pf))
        e.bind("<FocusOut>", lambda ev: c.itemconfig(it, image=pn))
        self._items += [it, win]
        self.entries.append(e)
        return e

    def _decor(self):
        import random
        self._rnd = random
        c, S = self.canvas, self.S
        self.sq = []
        for i in range(14):
            x, y = random.uniform(10, self.W - 10), random.uniform(10, self.H - 10)
            s = random.choice((5, 6, 8, 10)) * S
            it = c.create_rectangle(x * S, y * S, x * S + s, y * S + s, width=0, fill=hexc(BASE))
            self.sq.append([it, x, y, random.uniform(3, 9), random.uniform(0, 6.28), random.uniform(0.5, 1.4), s, random.choice((V1, V2, V3))])

    def _tick_decor(self, now, dt):
        c, S = self.canvas, self.S
        for sq in self.sq:
            it, x, y, v, ph, f, s, col = sq
            y -= v * dt
            if y < -12:
                y, x = self.H + 8, self._rnd.uniform(10, self.W - 10)
            sq[1], sq[2] = x, y
            c.coords(it, x * S, y * S, x * S + s, y * S + s)
            c.itemconfig(it, fill=hexc(mix(BASE, col, 0.10 + 0.30 * (math.sin(now * f + ph) + 1) / 2)))

    def _chrome(self):
        c, S, W = self.canvas, self.S, self.W
        self.cb = {}
        for key, (x0, x1) in (("min", (W - 84, W - 52)), ("close", (W - 48, W - 16))):
            y0, y1 = 12, 40
            col = (235, 60, 90, 200) if key == "close" else (255, 255, 255, 36)
            hv = c.create_image(x0 * S, y0 * S, anchor="nw", image=self.photo(shape(int(32 * S), int(28 * S), int(10 * S), fill=col)), state="hidden", tags=("chrome",))
            cx, cy, lw = (x0 + x1) / 2, (y0 + y1) / 2, max(1, round(1.6 * S))
            ln = lambda a, b, d, e: c.create_line((cx + a) * S, (cy + b) * S, (cx + d) * S, (cy + e) * S, fill="#e9ddff", width=lw, capstyle="round", tags=("chrome",))
            if key == "min":
                ln(-6, 2, 6, 2)
            else:
                ln(-5, -5, 5, 5); ln(-5, 5, 5, -5)
            self.cb[key] = (x0, y0, x1, y1, hv)

    def _chrome_at(self, x, y):
        for k, (x0, y0, x1, y1, hv) in self.cb.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return k

    def _win32(self):
        if not WIN:
            return self._fade_in()
        try:
            import ctypes
            u, g = ctypes.windll.user32, ctypes.windll.gdi32
            self.root.update_idletasks()
            hwnd = self.root.winfo_id()
            top = self._top = u.GetParent(hwnd) or hwnd
            st = u.GetWindowLongW(top, -16)
            u.SetWindowLongW(top, -16, (st & ~(0x00C00000 | 0x00040000 | 0x00010000)) | 0x00020000 | 0x00080000)
            ex = u.GetWindowLongW(top, -20)
            u.SetWindowLongW(top, -20, (ex & ~0x80) | 0x40000)          # кнопка в панели задач
            u.SetWindowPos(top, 0, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0004 | 0x0010 | 0x0020)
            try:
                dw = ctypes.windll.dwmapi
                dw.DwmSetWindowAttribute(top, 34, ctypes.byref(ctypes.c_uint(0xFFFFFFFE)), 4)   # без системной обводки
            except Exception:
                pass
            x, y = self.root.winfo_x(), self.root.winfo_y()
            self.root.geometry(f"{self.cw}x{self.ch}+{x}+{y}")
            self.root.update_idletasks()
            r = int(self.R * self.S) * 2
            u.SetWindowRgn(top, g.CreateRoundRectRgn(0, 0, self.cw + 1, self.ch + 1, r, r), True)
        except Exception:
            traceback.print_exc()
        self._fade_in()

    def _fade_in(self):
        t0 = time.perf_counter()

        def step():
            e = min(1.0, (time.perf_counter() - t0) / 0.30)
            try:
                self.root.attributes("-alpha", ease(e))
            except Exception:
                return
            if e < 1.0:
                self.root.after(15, step)
        step()

    def _move_window(self, x, y):
        if WIN and self._top:
            import ctypes
            ctypes.windll.user32.SetWindowPos(self._top, 0, int(x), int(y), 0, 0, 0x0001 | 0x0004 | 0x0010)
        else:
            self.root.geometry(f"+{int(x)}+{int(y)}")

    def clear(self):
        for it in self._items:
            try:
                self.canvas.delete(it)
            except Exception:
                pass
        for e in self.entries:
            try:
                e.destroy()
            except Exception:
                pass
        self._items, self.widgets, self.entries, self.ticks = [], [], [], []
        self.pages, self.page, self.capture, self.hover_w = set(), None, None, None
        self._keep, self._pin, self.anims = [], {}, []

    def show(self, page, animate=True):
        c = self.canvas
        self.pages.add(page)
        for p in self.pages:
            c.itemconfig(p, state="hidden")
        c.itemconfig(page, state="normal")
        self.page = page
        c.tag_raise("chrome")
        if animate:
            off = 16 * self.S
            c.move(page, 0, off)
            st = {"p": off}

            def fn(e):
                n = off * (1 - e)
                c.move(page, 0, n - st["p"])
                st["p"] = n
            self.tween(0.30, fn)
        for w in self.widgets:
            w.hover(False)

    def after(self, ms, fn):
        self.root.after(ms, fn)

    def post(self, fn):
        self.q.put(fn)

    def tween(self, dur, fn, done=None):
        self.anims.append([time.perf_counter(), dur, fn, done])

    def every(self, fn):
        self.ticks.append(fn)

    def _lp(self, e):
        return e.x / self.S, e.y / self.S

    def _set_hover(self, w):
        if w is self.hover_w:
            return
        if self.hover_w:
            self.hover_w.hover(False)
        self.hover_w = w
        if w:
            w.hover(True)
        self.canvas.config(cursor="hand2" if w else "")

    def _find(self, x, y):
        return next((w for w in reversed(self.widgets) if w.hit(x, y)), None)

    def _motion(self, e):
        x, y = self._lp(e)
        k = self._chrome_at(x, y)
        for kk, v in self.cb.items():
            self.canvas.itemconfig(v[4], state="normal" if kk == k else "hidden")
        if k:
            self._set_hover(None)
            return self.canvas.config(cursor="hand2")
        self._set_hover(self._find(x, y))

    def _press(self, e):
        x, y = self._lp(e)
        k = self._chrome_at(x, y)
        if k:
            return self.close() if k == "close" else self.root.iconify()
        w = self._find(x, y)
        if w:
            self.capture = w
            return w.press(x, y)
        self.root.focus_set()
        self._wdrag = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y(), e.x_root, e.y_root)

    def _move(self, e):
        if self.capture:
            return self.capture.drag(*self._lp(e))
        if self._wdrag:
            ox, oy, bx, by = self._wdrag
            self._move_window(e.x_root - ox, e.y_root - oy)

    def _release(self, e):
        if self.capture:
            w, self.capture = self.capture, None
            w.release(*self._lp(e))
        self._wdrag = None

    def close(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _loop(self):
        t0 = time.perf_counter()
        try:
            while True:
                self.q.get_nowait()()
        except queue.Empty:
            pass
        except Exception:
            traceback.print_exc()
        try:
            if self.root.state() == "iconic":
                return self.root.after(250, self._loop)
            now = time.perf_counter()
            dt = min(0.1, now - self._last)
            self._last = now
            self._tick_decor(now, dt)
            keep = []
            for a in self.anims:
                e = min(1.0, (now - a[0]) / a[1])
                a[2](ease(e))
                if e >= 1.0:
                    a[3] and a[3]()
                else:
                    keep.append(a)
            self.anims = keep
            for w in self.widgets:
                if hasattr(w, "tick") and w.page in (None, self.page):
                    w.tick(now)
            for fn in list(self.ticks):
                fn(now, dt)
        except Exception:
            traceback.print_exc()
        self.root.after(max(1, int(16 - (time.perf_counter() - t0) * 1000)), self._loop)

    def run(self):
        self._last = time.perf_counter()
        self._loop()
        self.root.mainloop()
