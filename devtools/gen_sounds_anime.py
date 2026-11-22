"""Мягкие «анимешные» звуки: колокольчики-глокеншпиль, пузырьки, кавайные глиссандо, искорки.
Всё синтезируется с нуля (без чужих сэмплов). Подключается из gen_assets.write_sounds()."""
import numpy as np
from scipy.signal import butter, lfilter, iirpeak

SR = 44100
RNG = np.random.default_rng(11)


def T(d):
    return np.arange(int(SR * d)) / SR


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def lp(x, fc, o=2):
    b, a = butter(o, fc / (SR / 2), "low")
    return lfilter(b, a, x)


def bell(m, d=0.5, decay=7.0, amp=1.0):
    """Глокеншпиль/музыкальная шкатулка: FM-колокольчик, мягкая атака."""
    t = T(d)
    f = hz(m)
    mod = np.sin(2 * np.pi * f * 3.5 * t) * 1.6 * np.exp(-t * 14)
    y = np.sin(2 * np.pi * f * t + mod) + 0.3 * np.sin(2 * np.pi * f * 2 * t)
    env = np.minimum(1, t / 0.003) * np.exp(-t * decay)
    return y * env * amp


def put(buf, x, at=0.0, g=1.0):
    i = int(at * SR)
    n = min(len(x), len(buf) - i)
    if n > 0:
        buf[i:i + n] += x[:n] * g
    return buf


def canvas(d):
    return np.zeros(int(SR * d))


def glide(f0, f1, d, decay=10.0, wave="sin", amp=1.0, vib=0.0):
    t = T(d)
    f = np.geomspace(f0, f1, len(t))
    if vib:
        f = f * (1 + vib * np.sin(2 * np.pi * 7 * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(ph) + 0.18 * np.sin(2 * ph)
    env = np.minimum(1, t / 0.004) * np.exp(-t * decay)
    return y * env * amp


def twinkle(d=0.4, base=96, g=1.0):
    b = canvas(d)
    for k, m in enumerate([base, base + 7, base + 12, base + 4, base + 9]):
        put(b, bell(m, 0.18, 22, 0.5), 0.015 + k * 0.04, g)
    return b


def echo(x, delay=0.11, fb=0.28, n=3, tail=0.25):
    out = np.zeros(len(x) + int(SR * delay * n) + int(SR * tail))
    out[:len(x)] += x
    for k in range(1, n + 1):
        i = int(delay * SR * k)
        out[i:i + len(x)] += x * (fb ** k)
    return out


def finish(x, peak=0.7, fade=8):
    x = lp(x, 11000, 2)
    x = x / (np.abs(x).max() or 1) * peak
    n = int(SR * fade / 1000)
    x[:32] *= np.linspace(0, 1, 32)
    x[-n:] *= np.linspace(1, 0, n)
    return x


def voice_nya(d=0.34):
    """Милое «ня~»: пилообразный источник + форманты, глиссандо вверх-вниз."""
    t = T(d)
    f0 = 520 + 260 * np.sin(np.clip(t / d, 0, 1) * np.pi) ** 0.8
    f0 *= 1 + 0.01 * np.sin(2 * np.pi * 6 * t)
    ph = np.cumsum(f0) / SR
    src = 2 * (ph % 1) - 1

    def v(fs):
        y = 0
        for fc, q, g in fs:
            b, a = iirpeak(fc / (SR / 2), q)
            y = y + g * lfilter(b, a, src)
        return y
    s = lambda c, w: 1 / (1 + np.exp(-(t - c) / w))
    n_ = v([(300, 8, 1), (1100, 8, .4)])
    a_ = v([(850, 9, 1), (1400, 10, .8), (2800, 12, .3)])
    y = n_ * (1 - s(0.06, 0.01)) * 0.5 + a_ * s(0.05, 0.015)
    env = np.minimum(1, t / 0.01) * np.exp(-np.maximum(t - d * 0.4, 0) * 9)
    return y * env


def make_anime_sounds():
    S = {}
    # --- интерфейс: нежные капельки-колокольчики
    S["ui_hover"] = finish(bell(103, 0.12, 30, 0.6), 0.35)
    b = canvas(0.3)
    put(b, bell(91, 0.22, 14), 0.0)
    put(b, bell(98, 0.26, 12), 0.05)
    S["ui_click"] = finish(echo(b, 0.07, 0.25, 2, 0.1), 0.6)
    b = canvas(0.3)
    put(b, bell(95, 0.2, 14), 0.0)
    put(b, bell(88, 0.24, 12), 0.07)
    S["ui_back"] = finish(b, 0.55)
    b = canvas(0.6)
    for k, m in enumerate([84, 88, 91, 96, 100]):
        put(b, bell(m, 0.3, 11, 0.8), k * 0.045)
    put(b, twinkle(0.3, 100), 0.2, 0.5)
    S["ui_open"] = finish(echo(b, 0.1, 0.3, 2, 0.2), 0.65)
    b = canvas(0.45)
    for k, m in enumerate([100, 96, 91, 86]):
        put(b, bell(m, 0.22, 14, 0.8), k * 0.05)
    S["ui_close"] = finish(echo(b, 0.08, 0.25, 2, 0.15), 0.55)
    b = canvas(0.25)
    put(b, bell(93, 0.16, 16), 0.0)
    put(b, bell(100, 0.2, 13), 0.055)
    S["toggle_on"] = finish(b, 0.6)
    b = canvas(0.25)
    put(b, bell(98, 0.16, 16), 0.0)
    put(b, bell(91, 0.2, 13), 0.055)
    S["toggle_off"] = finish(b, 0.5)
    b = canvas(1.7)
    for k, m in enumerate([72, 76, 79, 84, 88, 91, 96]):
        put(b, bell(m, 0.7, 5, 0.8), k * 0.1)
    put(b, twinkle(0.5, 100), 0.8, 0.6)
    S["title_start"] = finish(echo(b, 0.14, 0.35, 3, 0.4), 0.75)
    # --- попадания: пузырьки, писки, кавайные звуки
    S["hit_pon"] = finish(glide(380, 900, 0.14, 26, amp=1.0), 0.65)            # пузырь «пон»
    b = canvas(0.45)
    put(b, bell(100, 0.3, 9), 0.0)
    put(b, bell(107, 0.35, 8), 0.04, 0.8)
    put(b, twinkle(0.3, 104), 0.05, 0.5)
    S["hit_kira"] = finish(echo(b, 0.09, 0.3, 2, 0.2), 0.7)
    b = canvas(0.34)
    put(b, glide(660, 990, 0.12, 12, amp=0.9), 0.0)
    put(b, glide(880, 1480, 0.2, 9, amp=1.0, vib=0.01), 0.1)
    S["hit_kyun"] = finish(b, 0.7)                                              # «кьюн» вверх
    S["hit_nya"] = finish(voice_nya(), 0.75, 10)
    b = canvas(0.2)
    put(b, glide(1700, 2300, 0.05, 40, amp=0.8), 0.0)
    put(b, glide(2000, 2900, 0.07, 32, amp=0.8), 0.06)
    S["hit_pico"] = finish(b, 0.5)                                              # пико-пико
    b = canvas(0.6)
    put(b, bell(103, 0.45, 6), 0.0)
    put(b, bell(110, 0.5, 5.5), 0.04, 0.8)
    put(b, twinkle(0.45, 108), 0.06, 0.7)
    S["hit_crit"] = finish(echo(b, 0.1, 0.3, 3, 0.25), 0.8)
    b = canvas(0.9)
    for k, m in enumerate([88, 91, 95, 100, 103, 107]):
        put(b, bell(m, 0.4, 8, 0.8), k * 0.065)
    put(b, twinkle(0.5, 104), 0.35, 0.7)
    S["kill"] = finish(echo(b, 0.12, 0.3, 3, 0.3), 0.8)
    b = canvas(0.35)
    put(b, glide(700, 420, 0.18, 10, amp=0.8), 0.0)
    put(b, glide(560, 330, 0.2, 9, amp=0.7), 0.1)
    S["hurt"] = finish(lp(b, 3500), 0.55)                                       # мягкое «ай»
    # --- ивент
    b = canvas(1.1)
    for at, m in ((0.0, 96), (0.17, 100), (0.34, 103)):
        put(b, bell(m, 0.45, 6), at)
    put(b, bell(108, 0.7, 4), 0.52)
    put(b, twinkle(0.5, 104), 0.55, 0.6)
    S["event_alert"] = finish(echo(b, 0.13, 0.32, 3, 0.35), 0.8)
    return S
