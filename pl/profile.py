# -*- coding: utf-8 -*-
"""Профиль лаунчера: аватар (файл avatar.png в папке данных) и ник."""
import os
from PIL import Image, ImageDraw
from .ui import pil_font, shape, V1, V2


def _circle(im, size):
    im = im.convert("RGBA").resize((size, size), Image.LANCZOS)
    m = Image.new("L", (size * 3, size * 3), 0)
    ImageDraw.Draw(m).ellipse((0, 0, size * 3 - 1, size * 3 - 1), fill=255)
    m = m.resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), m)
    return out


def avatar_path(P):
    return os.path.join(P.root, "avatar.png")


def make_avatar(P, nick, size):
    """Круглый аватар: загруженная картинка или буква ника на градиенте."""
    path = avatar_path(P)
    try:
        if os.path.exists(path):
            return _circle(Image.open(path), size)
    except Exception:
        pass
    g = shape(size, size, size // 2, grad=(V1, V2))
    d = ImageDraw.Draw(g)
    f = pil_font(int(size * 0.5))
    ch = (nick or "D")[:1].upper()
    bb = d.textbbox((0, 0), ch, font=f)
    d.text(((size - (bb[2] - bb[0])) / 2 - bb[0], (size - (bb[3] - bb[1])) / 2 - bb[1]), ch, font=f, fill=(255, 255, 255, 255))
    return g


def save_avatar(P, src):
    """Центрирует и обрезает выбранную картинку до квадрата 256x256."""
    im = Image.open(src).convert("RGBA")
    s = min(im.size)
    l, t = (im.width - s) // 2, (im.height - s) // 2
    im.crop((l, t, l + s, t + s)).resize((256, 256), Image.LANCZOS).save(avatar_path(P))


def remove_avatar(P):
    try:
        os.remove(avatar_path(P))
    except Exception:
        pass
