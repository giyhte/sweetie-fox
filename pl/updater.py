# -*- coding: utf-8 -*-
"""Автообновление SweetieFox.exe через GitHub Releases."""
import os, sys, re, subprocess
from .common import *

REPO = "giyhte/swetie"


def _ver(t):
    return tuple(int(x) for x in re.findall(r"\d+", t)[:4]) or (0,)


def cleanup():
    """Удаляем старый exe, оставшийся после обновления."""
    try:
        old = sys.executable + ".old"
        if os.path.exists(old):
            os.remove(old)
    except Exception:
        pass


def check():
    """Возвращает (tag, url) если на GitHub есть версия новее, иначе None."""
    if not getattr(sys, "frozen", False):
        return None
    try:
        r = http_json(f"https://api.github.com/repos/{REPO}/releases/latest")
        tag = r.get("tag_name", "")
        if _ver(tag) <= _ver(VERSION):
            return None
        for a in r.get("assets", []):
            if a["name"].lower() == "sweetiefox.exe":
                return tag, a["browser_download_url"]
    except Exception:
        pass
    return None


def apply(url, progress=None):
    exe = sys.executable
    new = exe + ".new"
    download(url, new, progress, timeout=120)
    old = exe + ".old"
    if os.path.exists(old):
        os.remove(old)
    os.replace(exe, old)      # запущенный exe можно переименовать, но не перезаписать
    os.replace(new, exe)
    subprocess.Popen([exe], cwd=os.path.dirname(exe))
    os._exit(0)
