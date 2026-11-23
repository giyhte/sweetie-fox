# -*- coding: utf-8 -*-
"""Самоустановка DCODE.exe: копирует себя в папку программы и кладёт ярлык на рабочий стол."""
import os, sys, shutil, subprocess, threading
from PIL import Image
from .common import *
from .ui import Host, Button, Check, asset, radial, DIM, V2

W, H = 560, 380
SUB = "#b8b4e6"


def install_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "DCODE")
    try:
        d.encode("ascii")
    except UnicodeEncodeError:
        d = r"C:\DCODE"  # Gradle не любит кириллицу в пути
    return d


def is_installed():
    return os.path.normcase(os.path.abspath(os.path.dirname(sys.executable))) == \
        os.path.normcase(os.path.abspath(install_dir()))


def ico_path(dst):
    """Кладём icon.ico рядом с exe, чтобы ярлык не зависел от иконки внутри exe и кэша Windows."""
    try:
        src = os.path.join(RES, "assets", "icon.ico")
        out = os.path.join(dst, "DCODE.ico")
        if os.path.exists(src):
            shutil.copy2(src, out)
            return out
    except Exception:
        pass
    return None


def make_shortcut(exe, desktop=True):
    q = lambda s: s.replace("'", "''")
    ico = ico_path(os.path.dirname(exe)) or exe
    ps = ("$d=[Environment]::GetFolderPath('Desktop');"
          "$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'DCODE.lnk'));"
          f"$s.TargetPath='{q(exe)}';$s.WorkingDirectory='{q(os.path.dirname(exe))}';"
          f"$s.IconLocation='{q(ico)},0';$s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps], timeout=60, **hidden())


def refresh_shortcut_icon():
    """Уже установленным: обновить иконку существующего ярлыка на рабочем столе."""
    if not (WIN and getattr(sys, "frozen", False)):
        return
    try:
        ico = ico_path(os.path.dirname(sys.executable))
        if not ico:
            return
        q = lambda s: s.replace("'", "''")
        ps = ("$p=Join-Path ([Environment]::GetFolderPath('Desktop')) 'DCODE.lnk';"
              "if(Test-Path $p){$w=New-Object -ComObject WScript.Shell;$s=$w.CreateShortcut($p);"
              f"$s.IconLocation='{q(ico)},0';$s.Save()" + "}")
        subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps], timeout=60, **hidden())
    except Exception:
        pass


class Installer:
    def __init__(self, host):
        h = self.h = host
        S = h.S
        self.dst, self.state = install_dir(), "ask"
        h.pages.add("main")
        h.image(W / 2 - 130, 0, radial(int(260 * S), V2, 0.45), "main")
        h.image(W / 2 - 50, 36, asset("icon.png").resize((int(100 * S),) * 2, Image.LANCZOS), "main")
        h.text("main", W / 2, 150, "Установка DCODE", 22, True, "#ffffff", "n")
        h.text("main", W / 2, 188, "Папка: " + self.dst, 10, False, DIM, "n", width=480, justify="center")
        self.chk = Check(h, "main", W / 2 - 110, 236, "Ярлык на рабочем столе", True, 12)
        self.msg = h.text("main", W / 2, 262, "", 11, False, SUB, "n", width=480, justify="center")
        self.btn = Button(h, "main", (W / 2 - 150, 292, W / 2 + 150, 342), "Установить", self.go, "primary", 15)
        h.show("main", False)

    def go(self):
        if self.state == "done":
            subprocess.Popen([os.path.join(self.dst, "DCODE.exe")], cwd=self.dst)
            return self.h.close()
        if self.state == "work":
            return
        self.state = "work"
        self.btn.set_text("Устанавливаю…")
        self.h.set_text(self.msg, "Копирую файлы…")
        sc, post = self.chk.val, self.h.post

        def work():
            try:
                os.makedirs(self.dst, exist_ok=True)
                exe = os.path.join(self.dst, "DCODE.exe")
                shutil.copy2(sys.executable, exe)
                if sc:
                    make_shortcut(exe)
                self.state = "done"
                post(lambda: (self.btn.set_text("Запустить"), self.h.set_text(self.msg, "Готово! Ярлык DCODE на рабочем столе." if sc else "Готово!")))
            except Exception as e:
                self.state = "ask"
                err = f"Ошибка: {e}"
                post(lambda: (self.btn.set_text("Установить"), self.h.set_text(self.msg, err)))
        threading.Thread(target=work, daemon=True).start()


def main():
    host = Host("Установка DCODE", W, H)
    Installer(host)
    host.run()
