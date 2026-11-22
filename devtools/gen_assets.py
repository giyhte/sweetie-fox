# -*- coding: utf-8 -*-
"""Генератор ассетов PulseLite (звуки, фоны, панорама, спрайты кнопок, иконки).
Запуск:  python devtools/gen_assets.py   (нужны numpy, scipy, Pillow, ffmpeg с libvorbis)
Любой файл можно заменить своим — просто положи в modsrc/src/main/resources/assets/... с тем же именем."""
import os, math, json, subprocess, tempfile, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "modsrc", "src", "main", "resources", "assets")
PL = os.path.join(RES, "pulselite")
MC = os.path.join(RES, "minecraft")


def out(*p):
    path = os.path.join(*p)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


# =====================================================================  ЗВУКИ
SR = 44100
RNG = np.random.default_rng(7)


def T(d):
    return np.arange(int(SR * d)) / SR


def mid(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def tone(f, d, att=0.004, dec=7.0, partials=((1, 1.0), (2.76, .38), (5.4, .18), (8.9, .07)), vib=0.0, glide=None):
    t = T(d)
    if glide:
        fr = f + (glide - f) * np.clip(t / d, 0, 1)
        ph = 2 * np.pi * np.cumsum(fr) / SR
    else:
        ph = 2 * np.pi * f * t
    if vib:
        ph = ph + vib * np.sin(2 * np.pi * 5.5 * t)
    y = sum(a * np.sin(ph * m) for m, a in partials)
    return y * (1 - np.exp(-t / att)) * np.exp(-t * dec)


def pluck(f, d=0.5, dec=6.0):
    return tone(f, d, 0.002, dec, ((1, 1), (2, .5), (3, .25), (4, .12)))


def mbox(f, d=0.8, dec=5.0):
    return tone(f, d, 0.002, dec, ((1, 1), (2, .12), (4.02, .06), (6.1, .03)))


def put(buf, sig, at, gain=1.0):
    i = int(at * SR)
    if i >= len(buf):
        return
    n = min(len(sig), len(buf) - i)
    buf[i:i + n] += sig[:n] * gain


def canvas(d):
    return np.zeros(int(SR * d))


def noise(d):
    return RNG.standard_normal(int(SR * d))


def lowpass(x, fc, order=2):
    from scipy.signal import butter, lfilter
    b, a = butter(order, fc / (SR / 2), "low")
    return lfilter(b, a, x)


def highpass(x, fc, order=2):
    from scipy.signal import butter, lfilter
    b, a = butter(order, fc / (SR / 2), "high")
    return lfilter(b, a, x)


def reverb(x, wet=0.25, rt=0.6):
    from scipy.signal import fftconvolve
    n = int(SR * rt)
    ir = RNG.standard_normal(n) * np.exp(-np.arange(n) / SR * (5.0 / rt))
    ir = lowpass(ir, 6000)
    ir /= np.abs(ir).sum() / 6
    y = fftconvolve(x, ir)[: len(x)]
    return x * (1 - wet * 0.5) + y * wet


def finish(x, peak=0.85, fade_ms=12):
    x = np.asarray(x, dtype=np.float64)
    m = np.abs(x).max() or 1.0
    x = x / m * peak
    n = int(SR * fade_ms / 1000)
    x[:min(n, 64)] *= np.linspace(0, 1, min(n, 64))
    x[-n:] *= np.linspace(1, 0, n)
    return x


def sparkle(d=0.5, gain=1.0):
    """«кира-кира»: быстрые высокие звоночки"""
    b = canvas(d)
    for k in range(7):
        put(b, tone(mid(96 + int(RNG.integers(0, 12))), 0.2, 0.001, 18), 0.02 + k * 0.045, 0.5 * gain)
    return b


def formant_voice(kind="nya", f0a=430, f0b=560, d=0.42):
    """Очень простой синтез «ня~» формантами (экспериментально; заменяется любым своим сэмплом)."""
    from scipy.signal import iirpeak, lfilter
    t = T(d)
    f0 = f0a + (f0b - f0a) * np.sin(np.clip(t / d, 0, 1) * np.pi * 0.8)
    f0 = f0 * (1 + 0.012 * np.sin(2 * np.pi * 6 * t))
    ph = np.cumsum(f0) / SR
    src = 2 * (ph % 1.0) - 1.0
    src = src + 0.5 * np.sin(2 * np.pi * ph)

    def vowel(fs):
        y = np.zeros_like(src)
        for (fc, q, g) in fs:
            b, a = iirpeak(fc / (SR / 2), q)
            y += g * lfilter(b, a, src)
        return y

    n_ = vowel([(280, 8, 1.0), (1000, 8, 0.4)])
    i_ = vowel([(320, 9, 1.0), (2400, 12, 0.9), (3200, 12, 0.3)])
    a_ = vowel([(850, 9, 1.0), (1350, 10, 0.8), (2800, 12, 0.3)])
    u_ = vowel([(330, 9, 1.0), (900, 9, 0.5)])
    s = lambda c, w: 1 / (1 + np.exp(-(t - c) / w))
    if kind == "nya":
        w_n = 1 - s(0.07, 0.012)
        w_i = s(0.05, 0.012) * (1 - s(0.15, 0.02))
        w_a = s(0.12, 0.02)
    else:  # kyun
        w_n = s(d * 0.62, 0.02)
        w_i = (1 - s(0.07, 0.012))
        w_a = np.zeros_like(t)
        u_ = u_ * s(0.05, 0.015) * (1 - s(d * 0.65, 0.02))
    y = n_ * w_n * 0.45 + i_ * w_i + a_ * w_a + u_
    env = (1 - np.exp(-t / 0.012)) * np.exp(-np.maximum(t - d * 0.55, 0) * 7.0)
    return y * env


def make_sounds():
    S = {}
    # --- интерфейс
    S["ui_hover"] = finish(tone(mid(100), 0.11, 0.001, 30) + 0.5 * tone(mid(107), 0.11, 0.001, 36), 0.5, 6)
    b = canvas(0.34)
    put(b, tone(mid(96), 0.25, 0.001, 12), 0.0)
    put(b, tone(mid(103), 0.3, 0.001, 10), 0.075)
    put(b, tone(mid(108), 0.3, 0.001, 9), 0.15, 0.7)
    S["ui_click"] = finish(reverb(b, 0.18, 0.3), 0.8)
    b = canvas(0.34)
    put(b, tone(mid(99), 0.22, 0.001, 12), 0.0)
    put(b, tone(mid(91), 0.28, 0.001, 10), 0.08)
    S["ui_back"] = finish(reverb(b, 0.15, 0.3), 0.75)
    b = canvas(0.7)
    for k, n in enumerate([84, 88, 91, 95, 98, 103, 107]):
        put(b, tone(mid(n), 0.3, 0.001, 12), k * 0.045, 0.7)
    S["ui_open"] = finish(reverb(b, 0.3, 0.5), 0.8)
    b = canvas(0.5)
    for k, n in enumerate([103, 98, 94, 89]):
        put(b, tone(mid(n), 0.25, 0.001, 14), k * 0.05, 0.7)
    S["ui_close"] = finish(reverb(b, 0.2, 0.3), 0.75)
    b = canvas(0.3)
    put(b, tone(mid(91), 0.2, 0.001, 14), 0.0)
    put(b, tone(mid(98), 0.25, 0.001, 10), 0.06)
    S["toggle_on"] = finish(b, 0.8)
    b = canvas(0.3)
    put(b, tone(mid(96), 0.2, 0.001, 16), 0.0, 0.8)
    put(b, tone(mid(89), 0.22, 0.001, 14), 0.06, 0.8)
    S["toggle_off"] = finish(b, 0.7)
    b = canvas(1.6)
    for k, n in enumerate([72, 76, 79, 83, 84, 88, 91, 96]):
        put(b, mbox(mid(n), 0.9, 4.5), k * 0.11, 0.8)
    put(b, sparkle(0.6), 0.85, 0.6)
    S["title_start"] = finish(reverb(b, 0.35, 0.9), 0.85)
    # --- попадания
    t = T(0.18)
    pon = np.sin(2 * np.pi * np.cumsum(np.linspace(620, 170, len(t))) / SR) * np.exp(-t * 24)
    pon += 0.35 * lowpass(noise(0.18), 3000) * np.exp(-t * 90)
    S["hit_pon"] = finish(pon, 0.9, 6)
    b = canvas(0.55)
    put(b, tone(mid(100), 0.35, 0.001, 9), 0.0)
    put(b, tone(mid(107), 0.4, 0.001, 8), 0.05, 0.8)
    put(b, sparkle(0.35), 0.06, 0.5)
    S["hit_kira"] = finish(reverb(b, 0.25, 0.4), 0.85)
    t = T(0.3)
    kyun = tone(mid(79), 0.3, 0.004, 5.5, ((1, 1), (2, .25), (3, .1)), vib=0.6, glide=mid(93))
    S["hit_kyun"] = finish(kyun, 0.85, 8)
    S["hit_nya"] = finish(formant_voice("nya"), 0.9, 10)
    t = T(0.14)
    sq = np.sign(np.sin(2 * np.pi * np.cumsum(np.linspace(1500, 520, len(t))) / SR)) * 0.5
    sq += np.sin(2 * np.pi * np.cumsum(np.linspace(1500, 520, len(t))) / SR) * 0.6
    S["hit_pico"] = finish(sq * np.exp(-t * 17), 0.8, 5)
    b = canvas(0.65)
    put(b, tone(mid(105), 0.5, 0.001, 6), 0.0)
    put(b, tone(mid(112), 0.55, 0.001, 5.5), 0.03, 0.7)
    put(b, sparkle(0.5), 0.05, 0.6)
    S["hit_crit"] = finish(reverb(b, 0.3, 0.5), 0.9)
    b = canvas(0.95)
    for k, n in enumerate([88, 91, 95, 100, 103, 107, 112]):
        put(b, tone(mid(n), 0.4, 0.001, 8), k * 0.07, 0.75)
    put(b, sparkle(0.45), 0.35, 0.7)
    S["kill"] = finish(reverb(b, 0.3, 0.6), 0.9)
    b = canvas(0.4)
    put(b, tone(mid(86), 0.25, 0.001, 10), 0.0)
    put(b, tone(mid(79), 0.3, 0.001, 9), 0.09)
    S["hurt"] = finish(b, 0.7)
    # --- ивент
    b = canvas(1.5)
    for at, n in ((0.0, 93), (0.2, 96), (0.4, 100)):
        put(b, tone(mid(n), 0.5, 0.001, 5), at)
    put(b, tone(mid(105), 0.9, 0.001, 3.8), 0.62)
    put(b, sparkle(0.6), 0.65, 0.5)
    S["event_alert"] = finish(reverb(b, 0.32, 0.8), 0.9)
    # --- небо
    b = canvas(1.5)
    for k, n in enumerate([84, 88, 91, 96, 100]):
        put(b, tone(mid(n), 0.6, 0.002, 5), k * 0.09)
    put(b, sparkle(0.6), 0.4, 0.5)
    S["sky_day"] = finish(reverb(b, 0.3, 0.8), 0.85)
    b = canvas(1.9)
    for k, n in enumerate([81, 76, 72, 69, 64]):
        put(b, tone(mid(n), 0.9, 0.003, 3.4), k * 0.2, 0.8)
    S["sky_sunset"] = finish(reverb(b, 0.45, 1.2), 0.85)
    b = canvas(2.0)
    for at, n in ((0.0, 88), (0.22, 83), (0.5, 91), (0.72, 88), (1.0, 95), (1.3, 91)):
        put(b, mbox(mid(n), 0.9, 4), at, 0.8)
    pad = np.sin(2 * np.pi * 220 * T(2.0)) * 0.12 * np.sin(np.pi * T(2.0) / 2.0)
    S["sky_night"] = finish(reverb(b + pad, 0.4, 1.2), 0.8)
    b = canvas(1.7)
    for k, n in enumerate([79, 83, 86, 91, 95]):
        put(b, tone(mid(n), 0.8, 0.02, 3.8, ((1, 1), (2, .3), (3, .12))), k * 0.16, 0.8)
    S["sky_dawn"] = finish(reverb(b, 0.4, 1.0), 0.85)
    b = canvas(1.8)
    for k, n in enumerate([72, 74, 76, 79, 81, 84, 86, 88, 91, 93, 96]):
        put(b, pluck(mid(n), 0.7, 5), k * 0.05, 0.7)
    put(b, tone(mid(100), 1.0, 0.002, 3.5), 0.6, 0.6)
    put(b, sparkle(0.7), 0.7, 0.5)
    S["sky_sakura"] = finish(reverb(b, 0.4, 1.1), 0.85)
    t = T(2.0)
    b = np.zeros_like(t)
    for f in (523, 659, 784, 1047):
        for dt in (-1.6, 1.6):
            b += np.sin(2 * np.pi * (f + dt) * t)
    b *= np.sin(np.pi * t / 2.0) ** 1.4 * (0.6 + 0.4 * np.sin(2 * np.pi * 5.0 * t)) * 0.14
    b += sparkle(2.0) * 0.5
    S["sky_aurora"] = finish(reverb(b, 0.4, 1.3), 0.8)
    t = T(1.6)
    rum = lowpass(noise(1.6), 140, 3) * np.sin(np.pi * np.clip(t / 1.6, 0, 1)) ** 0.8 * 5
    zap = np.sin(2 * np.pi * np.cumsum(np.linspace(2600, 140, len(t))) / SR) * np.exp(-t * 14) * (t < 0.5)
    zap += highpass(noise(1.6), 2000) * np.exp(-t * 30) * 0.5
    b = rum * 0.5 + zap * 0.5
    put(b, tone(mid(52), 1.0, 0.002, 3.5), 0.1, 0.5)
    S["sky_storm"] = finish(reverb(b, 0.35, 1.0), 0.85)
    t = T(2.0)
    drone = (np.sin(2 * np.pi * 55 * t) + 0.6 * np.sin(2 * np.pi * 82.4 * t)) * np.exp(-t * 1.4) * 0.5
    gl = np.sin(2 * np.pi * np.cumsum(np.linspace(900, 90, len(t))) / SR) * np.exp(-t * 2.2) * 0.25
    S["sky_void"] = finish(reverb(drone + gl, 0.5, 1.4), 0.8)
    return S


def write_sounds():
    S = make_sounds()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from gen_sounds_anime import make_anime_sounds
    S.update(make_anime_sounds())   # мягкие анимешные звуки вместо старых
    d = out(PL, "sounds", "x")
    d = os.path.dirname(d)
    from scipy.io import wavfile
    sj = {}
    for name, x in S.items():
        with tempfile.TemporaryDirectory() as tmp:
            wav = os.path.join(tmp, name + ".wav")
            wavfile.write(wav, SR, (np.clip(x, -1, 1) * 32767).astype(np.int16))
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "libvorbis", "-q:a", "5",
                            "-ac", "1", os.path.join(d, name + ".ogg")], check=True)
        sj[name] = {"sounds": [{"name": "pulselite:" + name, "stream": False}]}
    with open(out(PL, "sounds.json"), "w", encoding="utf-8") as f:
        json.dump(sj, f, indent=1)
    print("sounds:", len(S))


# =====================================================================  КАРТИНКИ
SKIES = [  # зенит, середина, горизонт, свечение
    ((12, 10, 48), (88, 52, 200), (60, 190, 230), (190, 240, 255)),
    ((30, 14, 70), (200, 60, 150), (255, 150, 70), (255, 220, 170)),
    ((6, 14, 48), (26, 80, 190), (90, 190, 255), (220, 245, 255)),
    ((14, 4, 50), (150, 20, 170), (255, 70, 160), (255, 190, 230)),
    ((4, 24, 26), (10, 110, 80), (110, 230, 170), (220, 255, 220)),
    ((22, 4, 8), (150, 22, 30), (255, 110, 50), (255, 210, 150)),
    ((14, 20, 70), (60, 170, 200), (170, 250, 225), (235, 255, 250)),
    ((4, 4, 18), (36, 34, 120), (100, 90, 210), (210, 205, 255)),
]


def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def sky_color(e, sk):
    """e: 0 у горизонта … 1 в зените -> RGB (float 0..255)"""
    z, m, h, _ = [np.array(c, dtype=np.float64) for c in sk]
    e = np.clip(e, 0, 1)[..., None]
    a = smooth(e / 0.55)
    low = h + (m - h) * a
    b = smooth((e - 0.35) / 0.65)
    return low + (z - low) * b


def fbm1(n, seed, octs=4):
    r = np.random.default_rng(seed)
    x = np.zeros(n)
    for o in range(octs):
        k = 2 ** (o + 2)
        pts = r.random(k + 1)
        xs = np.linspace(0, k, n)
        i = np.minimum(xs.astype(int), k - 1)
        f = smooth(xs - i)
        x += (pts[i] * (1 - f) + pts[i + 1] * f) / 2 ** o
    return x / sum(1 / 2 ** o for o in range(octs))


def make_scene(idx, W=1920, H=1080):
    sk = SKIES[idx]
    rng = np.random.default_rng(100 + idx)
    y0 = int(H * 0.62)
    yy = np.arange(H)[:, None] * np.ones((1, W))
    img = np.zeros((H, W, 3))
    # небо
    e = 1 - yy[:y0] / y0
    img[:y0] = sky_color(e ** 0.9, sk)
    glow = np.array(sk[3], dtype=np.float64)
    # солнце/луна
    cx, cy, R = int(W * 0.68), int(H * 0.34), 92
    xx = np.arange(W)[None, :] * np.ones((H, 1))
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    halo = np.exp(-(d / (R * 3.2)) ** 2)[..., None] * 0.55 + np.exp(-(d / (R * 1.5)) ** 2)[..., None] * 0.35
    sky_mask = (yy < y0)[..., None]
    img = img + np.where(sky_mask, halo * glow, 0)
    disc = smooth((R - d) / 3)[..., None]
    disc_col = np.array([255, 250, 240]) * 0.85 + glow * 0.15
    img = img * (1 - disc * sky_mask) + disc_col * disc * sky_mask
    # кратеры луны
    for (dx, dy, r) in ((-28, -18, 20), (22, 20, 15), (-10, 34, 10), (34, -26, 9)):
        dd = np.sqrt((xx - cx - dx) ** 2 + (yy - cy - dy) ** 2)
        cr = (smooth((r - dd) / 4) * 0.10)[..., None]
        img = img * (1 - cr * sky_mask * disc) 
    # звёзды
    st = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(st)
    for _ in range(420):
        x = rng.integers(0, W)
        y = int(rng.random() ** 1.6 * y0 * 0.85)
        b = int(rng.integers(90, 255) * (1 - y / y0))
        r = rng.choice([1, 1, 1, 2])
        sd.ellipse((x - r, y - r, x + r, y + r), fill=b)
    for _ in range(16):
        x, y = rng.integers(40, W - 40), int(rng.random() * y0 * 0.6)
        L = int(rng.integers(8, 20))
        sd.line((x - L, y, x + L, y), fill=170, width=1)
        sd.line((x, y - L, x, y + L), fill=170, width=1)
        sd.ellipse((x - 2, y - 2, x + 2, y + 2), fill=255)
    st = np.asarray(st.filter(ImageFilter.GaussianBlur(0.8)), dtype=np.float64)[..., None] / 255
    img[:y0] += (st[:y0] * (1 - e[..., None] * 0.0)) * 255 * 0.85 * np.clip(1 - np.asarray(yy[:y0, :1] / y0)[..., None] * 0.0, 0, 1) \
        * np.clip((0.75 - (1 - e[..., None])) / 0.75 + 0.2, 0, 1) * (np.clip(e[..., None] * 1.8, 0, 1))
    # облака
    cl = Image.new("L", (W, H), 0)
    cd = ImageDraw.Draw(cl)
    for _ in range(26):
        x, y = rng.integers(-200, W), int(y0 * rng.uniform(0.35, 0.95))
        w, h = rng.integers(260, 720), rng.integers(10, 30)
        cd.ellipse((x, y, x + w, y + h), fill=int(rng.integers(70, 160)))
    cl = np.asarray(cl.filter(ImageFilter.GaussianBlur(14)), dtype=np.float64)[..., None] / 255
    cloud_col = (np.array(sk[2]) * 0.75 + np.array(sk[1]) * 0.25)
    img[:y0] = img[:y0] * (1 - cl[:y0] * 0.5) + cloud_col * cl[:y0] * 0.5
    # горы
    xs = np.arange(W)
    base_col = np.array(sk[2], dtype=np.float64)
    deep = np.array(sk[0], dtype=np.float64) * 0.7
    for li, (amp, k, seed) in enumerate(((260, 0.35, 1), (190, 0.6, 2), (120, 0.82, 3))):
        prof = fbm1(W, seed + idx * 10, 5)
        top = y0 - (np.clip(prof - 0.25, 0, 1) * amp * 2.0 + amp * 0.12)
        col = base_col * (1 - k) * 0.55 + deep * k + np.array(sk[1]) * 0.15 * (1 - k)
        mask = (yy[:y0] >= top[None, :]).astype(np.float64)
        # мягкий край
        mk = smooth((yy[:y0] - top[None, :]) / 2.5)[..., None]
        # туман у основания
        fog = np.clip(1 - (y0 - yy[:y0]) / (amp * 0.8), 0, 1)[..., None] ** 2
        c = col * (1 - fog * (1 - k) * 0.6) + base_col * fog * (1 - k) * 0.6
        img[:y0] = img[:y0] * (1 - mk) + c * mk
    # вода
    wy = np.arange(H - y0)
    refl_src = np.clip(y0 - 1 - wy * 1.0, 0, y0 - 1).astype(int)
    refl = img[refl_src].copy()
    depth = (wy / (H - y0))[:, None, None]
    deepw = np.array(sk[0], dtype=np.float64) * 0.55
    refl = refl * (0.78 - 0.45 * depth) + deepw * (0.22 + 0.45 * depth)
    for j in range(len(wy)):
        amp = 1 + wy[j] * 0.035
        sh = int(np.sin(wy[j] * 0.21 + np.sin(wy[j] * 0.043) * 3) * amp)
        refl[j] = np.roll(refl[j], sh, axis=0)
    rip = (np.sin(wy[:, None] * 1.1 + xs[None, :] * 0.011 * (1 + depth[:, :, 0] * 3) ) + np.sin(xs[None, :] * 0.037 + wy[:, None] * 0.31)) * 0.5
    rip = np.clip(rip - 0.55, 0, 1)[..., None] * 90 * (0.25 + depth)
    refl = refl + rip * (glow * 0.004 + 0.1)
    img[y0:] = refl
    # линия горизонта: лёгкое свечение
    hz = np.exp(-((yy - y0) / 10.0) ** 2)[..., None] * glow * 0.35
    img += hz
    # тории
    tor = Image.new("L", (W * 2, H * 2), 0)
    td = ImageDraw.Draw(tor)
    tx, tb, th, tw = int(W * 0.27) * 2, int(y0 + 120) * 2, 330 * 2, 250 * 2
    pw = 26 * 2
    for sx in (tx - tw // 2 + 30, tx + tw // 2 - 30 - pw):
        td.polygon([(sx, tb), (sx + pw, tb), (sx + pw - 4, tb - th), (sx + 4, tb - th)], fill=255)
    top_y = tb - th
    td.polygon([(tx - tw // 2 - 60, top_y - 20), (tx + tw // 2 + 60, top_y - 20), (tx + tw // 2 + 100, top_y - 60),
                (tx + tw // 2 + 30, top_y - 38), (tx - tw // 2 - 30, top_y - 38), (tx - tw // 2 - 100, top_y - 60)], fill=255)
    td.rectangle((tx - tw // 2 + 10, top_y + 56, tx + tw // 2 - 10, top_y + 56 + 30), fill=255)
    td.rectangle((tx - 18, top_y - 38, tx + 18, top_y + 56), fill=255)
    tor = tor.resize((W, H), Image.LANCZOS)
    tm = np.asarray(tor, dtype=np.float64)[..., None] / 255
    tcol = np.array(sk[0], dtype=np.float64) * 0.35 + np.array([6, 4, 14])
    # зеркальное отражение
    base_y = int(tb / 2)
    flip = tor.transpose(Image.FLIP_TOP_BOTTOM)
    shift = base_y * 2 - H
    fl = Image.new("L", (W, H), 0)
    fl.paste(flip, (0, shift))
    fl = fl.filter(ImageFilter.GaussianBlur(3))
    fm = np.asarray(fl, dtype=np.float64)[..., None] / 255
    fm[:base_y] = 0
    img = img * (1 - fm * 0.55) + tcol * fm * 0.55
    img = img * (1 - tm) + tcol * tm
    # лёгкий ободок света на тории
    rim = np.asarray(tor.filter(ImageFilter.GaussianBlur(2)), dtype=np.float64)[..., None] / 255
    img += np.clip(rim - tm, 0, 1) * glow * 0.0
    # блум
    bright = np.clip(img - 170, 0, 255)
    bl = Image.fromarray(np.clip(bright, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(26))
    img = img + np.asarray(bl, dtype=np.float64) * 0.55
    # виньетка и зерно
    vx = (np.arange(W) - W / 2) / (W / 2)
    vy = (np.arange(H) - H / 2) / (H / 2)
    vg = 1 - 0.38 * (vx[None, :] ** 2 * 0.7 + vy[:, None] ** 2 * 0.9)
    img = img * np.clip(vg, 0, 1)[..., None]
    img += rng.normal(0, 1.6, img.shape)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def make_panorama(sk, N=512):
    """Кубическая панорама: фон зависит только от высоты (бесшовно в любом порядке граней)."""
    rng = np.random.default_rng(5)
    glow = np.array(sk[3], dtype=np.float64)
    deepw = np.array(sk[0], dtype=np.float64) * 0.6

    def color_el(el_deg):
        # el_deg: -90..90
        up = np.clip(el_deg / 75.0, 0, 1)
        c = sky_color(up ** 0.8, sk)
        low = np.clip(-el_deg / 75.0, 0, 1)
        r = sky_color(np.clip(low ** 0.8, 0, 1) * 0.85, sk) * (0.62 - 0.32 * low[..., None]) + deepw * (0.15 + 0.3 * low[..., None])
        out_ = np.where((el_deg >= 0)[..., None], c, r)
        out_ += np.exp(-(el_deg / 2.5) ** 2)[..., None] * glow * 0.4
        return out_

    faces = []
    ii, jj = np.meshgrid((np.arange(N) + .5) / N * 2 - 1, (np.arange(N) + .5) / N * 2 - 1)
    for k in range(6):
        if k < 4:
            u, v = ii, -jj
            el = np.degrees(np.arctan2(v, np.sqrt(u * u + 1)))
            au = np.arctan(u) / (np.pi / 4)  # -1..1
        elif k == 4:
            el = np.degrees(np.arctan2(1.0, np.sqrt(ii * ii + jj * jj)))
            au = None
        else:
            el = -np.degrees(np.arctan2(1.0, np.sqrt(ii * ii + jj * jj)))
            au = None
        img = color_el(el)
        if au is not None:
            win = np.clip(np.cos(au * np.pi / 2), 0, 1) ** 0.6
            prof = fbm1(N, 40 + k, 4)[None, :]
            h = (np.clip(prof - 0.3, 0, 1) * 16 + 1.2)
            hh = h * np.ones((N, 1)) * win
            mountain = (el > 0) & (el < hh)
            mref = (el < 0) & (el > -hh * 0.9)
            mcol = np.array(sk[0], dtype=np.float64) * 0.55 + np.array(sk[1], dtype=np.float64) * 0.18
            mk = smooth((hh - el) / 0.6) * (el > 0) + smooth((hh * 0.9 + el) / 0.8) * 0.6 * (el < 0)
            mk = np.where((el > -hh * 0.95) & (el < hh), mk, 0)[..., None]
            img = img * (1 - mk) + mcol * mk
            if k == 0:  # луна/солнце в центре одной грани
                mu, me, mr = 0.28, 18.0, 4.2
                dist = np.sqrt(((au - mu) * 45) ** 2 + (el - me) ** 2)
                img += (np.exp(-(dist / (mr * 3.5)) ** 2)[..., None] * 0.5) * glow
                dk = smooth((mr - dist) / 0.5)[..., None]
                img = img * (1 - dk) + np.array([255, 250, 240]) * dk
                dist2 = np.sqrt(((au - mu) * 45 * 1.8) ** 2 + ((el + me) * 0.28) ** 2)
                img += np.exp(-(dist2 / 6.0) ** 2)[..., None] * glow * 0.45 * (el < 0)[..., None]
            # звёзды
            for _ in range(36):
                sx = rng.integers(int(N * 0.08), int(N * 0.92))
                sy = rng.integers(int(N * 0.04), int(N * 0.40))
                img[sy:sy + 2, sx:sx + 2] += 160
        else:
            if k == 4:
                for _ in range(60):
                    sx, sy = rng.integers(int(N * .1), int(N * .9), 2)
                    img[sy:sy + 2, sx:sx + 2] += 150
        img = img + rng.normal(0, 1.3, img.shape)
        faces.append(Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)))
    return faces


# =====================================================================  СПРАЙТЫ GUI
S8 = 8


def rr_sprite(w, h, r, top, bot, border, hl=None, bw=1):
    W, H = w * S8, h * S8
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, W - 1, H - 1), r * S8, fill=255)
    inner = Image.new("L", (W, H), 0)
    ImageDraw.Draw(inner).rounded_rectangle((bw * S8, bw * S8, W - 1 - bw * S8, H - 1 - bw * S8),
                                            max(r - bw, 1) * S8, fill=255)
    g = np.zeros((H, W, 4), dtype=np.float64)
    t = np.linspace(0, 1, H)[:, None, None]
    top, bot = np.array(top, dtype=np.float64), np.array(bot, dtype=np.float64)
    g[:] = (top * (1 - t) + bot * t)
    im = Image.fromarray(g.astype(np.uint8), "RGBA")
    border_im = Image.new("RGBA", (W, H), tuple(border))
    ring = Image.composite(Image.new("L", (W, H), 255), Image.new("L", (W, H), 0), m)
    base = Image.composite(im, border_im, inner)
    if hl:
        hi = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(hi).rounded_rectangle((bw * S8 + 2, bw * S8 + 1, W - 1 - bw * S8 - 2, bw * S8 + 1 * S8),
                                             S8, fill=tuple(hl))
        hi.putalpha(ImageChops_mul(hi.getchannel("A"), inner))
        base = Image.alpha_composite(base, hi)
    a = np.asarray(base.getchannel("A"), dtype=np.float64) * (np.asarray(m, dtype=np.float64) / 255)
    base.putalpha(Image.fromarray(a.astype(np.uint8)))
    return base.resize((w, h), Image.LANCZOS)


def ImageChops_mul(a, b):
    from PIL import ImageChops
    return ImageChops.multiply(a, b)


def save_sprite(name, im, scaling=None):
    p = out(MC, "textures", "gui", "sprites", *name.split("/")) + ".png"
    im.save(p)
    if scaling:
        with open(p + ".mcmeta", "w") as f:
            json.dump({"gui": {"scaling": scaling}}, f)


def nine(w, h, b):
    return {"type": "nine_slice", "width": w, "height": h, "border": b}


def make_gui_sprites():
    N_TOP, N_BOT, N_BORDER = (74, 56, 158, 238), (40, 30, 96, 238), (132, 112, 240, 255)
    H_TOP, H_BOT, H_BORDER = (240, 92, 176, 245), (132, 66, 235, 245), (255, 196, 238, 255)
    D_TOP, D_BOT, D_BORDER = (46, 44, 70, 200), (34, 32, 54, 200), (82, 80, 112, 220)
    save_sprite("widget/button", rr_sprite(200, 20, 5, N_TOP, N_BOT, N_BORDER, (255, 255, 255, 55)), nine(200, 20, 5))
    save_sprite("widget/button_highlighted", rr_sprite(200, 20, 5, H_TOP, H_BOT, H_BORDER, (255, 255, 255, 90)), nine(200, 20, 5))
    save_sprite("widget/button_disabled", rr_sprite(200, 20, 5, D_TOP, D_BOT, D_BORDER, None), nine(200, 20, 5))
    save_sprite("widget/slider", rr_sprite(200, 20, 5, (24, 20, 58, 235), (16, 13, 40, 235), (96, 82, 200, 255)), nine(200, 20, 5))
    save_sprite("widget/slider_highlighted", rr_sprite(200, 20, 5, (36, 30, 84, 240), (22, 18, 56, 240), (255, 160, 225, 255)), nine(200, 20, 5))
    save_sprite("widget/slider_handle", rr_sprite(8, 20, 3, (236, 228, 255, 255), (170, 150, 245, 255), (255, 255, 255, 255)), nine(8, 20, 3))
    save_sprite("widget/slider_handle_highlighted", rr_sprite(8, 20, 3, (255, 214, 240, 255), (240, 110, 190, 255), (255, 255, 255, 255)), nine(8, 20, 3))
    save_sprite("widget/text_field", rr_sprite(200, 20, 4, (14, 12, 36, 235), (10, 8, 28, 235), (92, 78, 190, 255)), nine(200, 20, 4))
    save_sprite("widget/text_field_highlighted", rr_sprite(200, 20, 4, (20, 16, 48, 240), (12, 10, 34, 240), (255, 150, 224, 255)), nine(200, 20, 4))
    for nm, (a, b, c) in {"tab_selected": (H_TOP, H_BOT, H_BORDER), "tab_selected_highlighted": (H_TOP, H_BOT, H_BORDER),
                          "tab_unselected": (N_TOP, N_BOT, N_BORDER), "tab_unselected_highlighted": ((96, 74, 190, 240), (56, 42, 130, 240), (190, 160, 255, 255))}.items():
        save_sprite("tab/" + nm, rr_sprite(130, 24, 6, a, b, c, (255, 255, 255, 50)), nine(130, 24, 6))


def tile_pattern(n, base, accent, alpha):
    im = np.zeros((n, n, 4), dtype=np.float64)
    im[:] = (*base, alpha)
    yy, xx = np.mgrid[0:n, 0:n]
    d = (np.abs(((xx / n) * 4 % 1) - 0.5) + np.abs(((yy / n) * 4 % 1) - 0.5))
    k = np.clip(1 - d * 6, 0, 1) * 0.5
    for c in range(3):
        im[..., c] += k * accent[c] * 0.35
    return Image.fromarray(np.clip(im, 0, 255).astype(np.uint8), "RGBA")


def make_gui_tiles():
    g = lambda *p: out(MC, "textures", "gui", *p)
    tile_pattern(64, (18, 14, 44), (160, 120, 255), 255).save(g("menu_background.png"))
    tile_pattern(64, (14, 10, 36), (160, 120, 255), 190).save(g("inworld_menu_background.png"))
    tile_pattern(64, (16, 12, 40), (160, 120, 255), 150).save(g("menu_list_background.png"))
    tile_pattern(64, (10, 8, 28), (160, 120, 255), 120).save(g("inworld_menu_list_background.png"))
    for nm in ("header_separator", "footer_separator", "inworld_header_separator", "inworld_footer_separator"):
        im = Image.new("RGBA", (32, 2), (0, 0, 0, 0))
        px = im.load()
        for x in range(32):
            px[x, 0] = (236, 110, 190, 255)
            px[x, 1] = (90, 60, 190, 255)
        im.save(g(nm + ".png"))


# =====================================================================  ИКОНКИ / ЛОГО / ЧАСТИЦЫ
def icon_canvas():
    im = Image.new("L", (512, 512), 0)
    return im, ImageDraw.Draw(im)


def ic_eye(d):
    d.ellipse((60, 150, 452, 362), outline=255, width=34)
    d.ellipse((196, 196, 316, 316), fill=255)


def ic_bolt(d):
    d.polygon([(300, 40), (110, 290), (240, 290), (200, 470), (402, 200), (272, 200)], fill=255)


def ic_sword(d):
    d.polygon([(450, 50), (462, 150), (200, 380), (130, 310)], fill=255)
    d.line((90, 250, 260, 420), fill=255, width=52)
    d.line((120, 390, 60, 452), fill=255, width=46)


def ic_sky(d):
    d.ellipse((90, 70, 250, 230), fill=255)
    for a in range(0, 360, 45):
        x, y = 170 + 120 * math.cos(math.radians(a)), 150 + 120 * math.sin(math.radians(a))
        d.ellipse((x - 14, y - 14, x + 14, y + 14), fill=255)
    d.ellipse((150, 250, 300, 400), fill=255)
    d.ellipse((250, 200, 430, 380), fill=255)
    d.ellipse((90, 300, 230, 420), fill=255)
    d.rounded_rectangle((110, 300, 420, 420), 60, fill=255)


def ic_pin(d):
    d.ellipse((130, 50, 382, 302), fill=255)
    d.polygon([(150, 250), (362, 250), (256, 470)], fill=255)
    d.ellipse((206, 126, 306, 226), fill=0)


def ic_palette(d):
    d.ellipse((50, 60, 462, 452), fill=255)
    for (x, y, c) in ((150, 190, 0), (250, 130, 0), (350, 190, 0), (150, 310, 0)):
        d.ellipse((x - 36, y - 36, x + 36, y + 36), fill=0)
    d.ellipse((290, 300, 440, 440), fill=0)


def ic_info(d):
    d.ellipse((40, 40, 472, 472), fill=255)
    d.ellipse((226, 110, 286, 170), fill=0)
    d.rounded_rectangle((226, 210, 286, 400), 20, fill=0)


def ic_speaker(d):
    d.polygon([(40, 190), (150, 190), (270, 90), (270, 420), (150, 320), (40, 320)], fill=255)
    for r in (90, 160):
        d.arc((270 - r, 255 - r, 270 + r, 255 + r), -45, 45, fill=255, width=32)


def ic_run(d):
    for dx in (0, 150):
        d.line((90 + dx, 100, 230 + dx, 256), fill=255, width=60)
        d.line((230 + dx, 256, 90 + dx, 412), fill=255, width=60)


def ic_play(d):
    d.polygon([(120, 60), (430, 256), (120, 452)], fill=255)


def ic_globe(d):
    d.ellipse((50, 50, 462, 462), outline=255, width=32)
    d.ellipse((160, 50, 352, 462), outline=255, width=28)
    d.line((50, 256, 462, 256), fill=255, width=28)
    d.arc((90, 100, 422, 220), 200, 340, fill=255, width=24)
    d.arc((90, 292, 422, 412), 20, 160, fill=255, width=24)


def ic_gear(d):
    for a in range(0, 360, 45):
        x, y = 256 + 190 * math.cos(math.radians(a)), 256 + 190 * math.sin(math.radians(a))
        d.ellipse((x - 46, y - 46, x + 46, y + 46), fill=255)
    d.ellipse((90, 90, 422, 422), fill=255)
    d.ellipse((186, 186, 326, 326), fill=0)


def ic_power(d):
    d.arc((80, 90, 432, 442), -60, 240, fill=255, width=40)
    d.line((256, 40, 256, 250), fill=255, width=44)


def ic_play_ring(d):
    d.polygon([(170, 120), (390, 256), (170, 392)], fill=255)


def ic_star(d):
    pts = []
    for i in range(10):
        r = 220 if i % 2 == 0 else 90
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((256 + r * math.cos(a), 270 + r * math.sin(a)))
    d.polygon(pts, fill=255)


ICONS = {"visual": ic_eye, "perf": ic_bolt, "combat": ic_sword, "sky": ic_sky, "event": ic_pin, "theme": ic_palette,
         "info": ic_info, "sound": ic_speaker, "game": ic_run, "play": ic_play, "globe": ic_globe, "bolt": ic_bolt,
         "gear": ic_gear, "power": ic_power, "preview": ic_play_ring, "star": ic_star}


def make_icons():
    for name, fn in ICONS.items():
        im, d = icon_canvas()
        fn(d)
        im = im.resize((64, 64), Image.LANCZOS)
        rgba = Image.new("RGBA", (64, 64), (255, 255, 255, 0))
        rgba.putalpha(im)
        rgba.save(out(PL, "textures", "gui", "icons", name + ".png"))


def font(sz):
    for p in ("/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            pass
    return ImageFont.load_default()


def make_logo():
    W, H = 768, 192
    S = 2
    f = font(96 * S)
    base = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    ta, tb = "SWEETIE", "FOX"
    wa = d.textlength(ta, font=f)
    wb = d.textlength(tb, font=f)
    total = wa + wb + 14 * S
    x0 = (W * S - total) / 2
    y0 = 18 * S
    m1 = Image.new("L", base.size, 0)
    ImageDraw.Draw(m1).text((x0, y0), ta, font=f, fill=255)
    m2 = Image.new("L", base.size, 0)
    ImageDraw.Draw(m2).text((x0 + wa + 14 * S, y0), tb, font=f, fill=255)
    gy = np.linspace(0, 1, H * S)[:, None]
    gx = np.linspace(0, 1, W * S)[None, :]

    def grad(c1, c2, axis):
        t = (gy * np.ones((1, W * S))) if axis == "y" else (gx * np.ones((H * S, 1)))
        a = np.zeros((H * S, W * S, 4), dtype=np.uint8)
        for c in range(3):
            a[..., c] = (c1[c] + (c2[c] - c1[c]) * t).astype(np.uint8)
        a[..., 3] = 255
        return Image.fromarray(a, "RGBA")

    g1 = grad((255, 255, 255), (206, 190, 255), "y")
    gxl = np.clip((gx - (x0 + wa + 14 * S) / (W * S)) / (wb / (W * S)), 0, 1) * np.ones((H * S, 1))
    a2 = np.zeros((H * S, W * S, 4), dtype=np.uint8)
    for c in range(3):
        a2[..., c] = ((255, 140, 210)[c] + ((110, 230, 255)[c] - (255, 140, 210)[c]) * gxl).astype(np.uint8)
    a2[..., 3] = 255
    g2 = Image.fromarray(a2, "RGBA")
    glow_src = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ga = Image.new("RGBA", base.size, (200, 120, 255, 255))
    gb = Image.new("RGBA", base.size, (120, 220, 255, 255))
    glow_src = Image.composite(ga, glow_src, m1)
    glow_src = Image.alpha_composite(glow_src, Image.composite(gb, Image.new("RGBA", base.size, (0, 0, 0, 0)), m2))
    glow = glow_src.filter(ImageFilter.GaussianBlur(14 * S))
    a = np.asarray(glow.getchannel("A"), dtype=np.float64) * 0.9
    glow.putalpha(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)))
    base = Image.alpha_composite(base, glow)
    # тень
    sh = Image.new("RGBA", base.size, (10, 6, 30, 0))
    shm = Image.new("L", base.size, 0)
    shm.paste(m1, (0, 5 * S), m1)
    shm.paste(m2, (0, 5 * S), m2)
    sh.putalpha(shm.point(lambda v: int(v * 0.55)).filter(ImageFilter.GaussianBlur(3 * S)))
    base = Image.alpha_composite(base, sh)
    base = Image.alpha_composite(base, Image.composite(g1, Image.new("RGBA", base.size, (0, 0, 0, 0)), m1))
    base = Image.alpha_composite(base, Image.composite(g2, Image.new("RGBA", base.size, (0, 0, 0, 0)), m2))
    # линия пульса
    ld = ImageDraw.Draw(base)
    ly = 176 * S
    pts = [(x0, ly), (x0 + total * 0.22, ly), (x0 + total * 0.28, ly - 7 * S), (x0 + total * 0.33, ly + 6 * S),
           (x0 + total * 0.38, ly - 13 * S), (x0 + total * 0.44, ly + 5 * S), (x0 + total * 0.5, ly), (x0 + total, ly)]
    ld.line(pts, fill=(255, 255, 255, 210), width=3 * S, joint="curve")
    base.resize((W, H), Image.LANCZOS).save(out(PL, "textures", "gui", "logo.png"))


def make_particles():
    S = 8
    N = 32
    im = Image.new("RGBA", (N * S, N * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # лепесток сакуры: два лепестка со вырезом
    pts = []
    for i in range(0, 361, 6):
        a = math.radians(i)
        r = 11 * S * (1 - 0.35 * math.cos(2 * a) ** 2) * (0.55 + 0.45 * abs(math.sin(a)))
        pts.append((N * S / 2 + r * math.sin(a) * 0.75, N * S / 2 - r * math.cos(a)))
    d.polygon(pts, fill=(255, 183, 213, 235))
    d.polygon([(N * S / 2, N * S / 2 + 8 * S), (N * S / 2 - 3 * S, N * S / 2 + 12 * S), (N * S / 2 + 3 * S, N * S / 2 + 12 * S)], fill=(0, 0, 0, 0))
    d.ellipse((N * S / 2 - 2 * S, N * S / 2 - 3 * S, N * S / 2 + 2 * S, N * S / 2 + 1 * S), fill=(255, 120, 170, 200))
    im.resize((N, N), Image.LANCZOS).save(out(PL, "textures", "gui", "petal.png"))
    # искра
    s = Image.new("RGBA", (N * S, N * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    c = N * S / 2
    d.polygon([(c, 1 * S), (c + 3 * S, c - 3 * S), (N * S - 1 * S, c), (c + 3 * S, c + 3 * S), (c, N * S - 1 * S),
               (c - 3 * S, c + 3 * S), (1 * S, c), (c - 3 * S, c - 3 * S)], fill=(255, 255, 255, 255))
    s = s.filter(ImageFilter.GaussianBlur(S * 0.6))
    s.resize((N, N), Image.LANCZOS).save(out(PL, "textures", "gui", "sparkle.png"))


def make_scenes():
    for i in range(len(SKIES)):
        im = make_scene(i).resize((1600, 900), Image.LANCZOS)
        g = np.random.default_rng(i).normal(0, 0.5, (900, 1600, 1))  # лёгкое яркостное зерно против полос
        im = Image.fromarray(np.clip(np.asarray(im).astype(np.float64) + g, 0, 255).astype(np.uint8))
        im.save(out(PL, "textures", "gui", "bg", f"scene_{i}.png"), optimize=True)
        print("scene", i)


def make_panoramas():
    faces = make_panorama(SKIES[0])
    for i, f in enumerate(faces):
        f.save(out(MC, "textures", "gui", "title", "background", f"panorama_{i}.png"), optimize=True)
    print("panorama ok")


if __name__ == "__main__":
    what = sys.argv[1:] or ["sounds", "scenes", "panorama", "gui", "icons", "logo", "particles"]
    if "sounds" in what: write_sounds()
    if "scenes" in what: make_scenes()
    if "panorama" in what: make_panoramas()
    if "gui" in what: make_gui_sprites(); make_gui_tiles()
    if "icons" in what: make_icons()
    if "logo" in what: make_logo()
    if "particles" in what: make_particles()
    print("done")
