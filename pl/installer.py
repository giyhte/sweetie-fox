# -*- coding: utf-8 -*-
"""Самоустановка SweetieFox.exe: копирует себя в папку программы и кладёт ярлык на рабочий стол."""
import os, sys, shutil, subprocess, threading
from PIL import Image
from .common import *
from .ui import Host, Scene

W, H = 640, 420
SUB = "#b8b4e6"


def install_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "SweetieFox")
    try:
        d.encode("ascii")
    except UnicodeEncodeError:
        d = r"C:\SweetieFox"  # Gradle не любит кириллицу в пути
    return d


def is_installed():
    return os.path.normcase(os.path.abspath(os.path.dirname(sys.executable))) == \
        os.path.normcase(os.path.abspath(install_dir()))


def ico_path(dst):
    """Кладём icon.ico рядом с exe, чтобы ярлык не зависел от иконки внутри exe и кэша Windows."""
    try:
        src = os.path.join(RES, "assets", "icon.ico")
        out = os.path.join(dst, "SweetieFox.ico")
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
          "$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'Sweetie Fox.lnk'));"
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
        ps = ("$p=Join-Path ([Environment]::GetFolderPath('Desktop')) 'Sweetie Fox.lnk';"
              "if(Test-Path $p){$w=New-Object -ComObject WScript.Shell;$s=$w.CreateShortcut($p);"
              f"$s.IconLocation='{q(ico)},0';$s.Save()" + "}")
        subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps], timeout=60, **hidden())
    except Exception:
        pass


class InstallScene(Scene):
    def __init__(self, host):
        super().__init__(host)
        pt = self.pt
        self.dst = install_dir()
        self.state = "ask"   # ask / work / done / fail
        self.shortcut = True
        try:
            ic = Image.open(os.path.join(RES, "assets", "icon.png")).convert("RGBA").resize((110, 110), Image.LANCZOS)
        except Exception:
            ic = pt.icon(110)
        self.under.append(lambda ov: pt.glass(ov, (20, 20, 620, 400), 28, 110, 18))
        self.under.append(lambda ov: pt.image(ov, ic, (52, 56)))
        self.text("t", 190, 66, "sweetie fox", 36, True, "#ffffff")
        self.text("s", 192, 118, "Установка лаунчера Minecraft", 16, False, SUB)
        self.text("path", 56, 202, "Папка: " + self.dst, 13, False, "#e9e4ff", width=530)
        self.text("sc", 56, 252, "Ярлык на рабочем столе", 16, True, "#ffffff")
        self.switch((532, 250, 588, 276), lambda: self.shortcut, lambda v: setattr(self, "shortcut", v))
        self.text("msg", 56, 296, "", 13, False, SUB, width=530)
        self.main = self.button("go", (56, 326, 588, 374), "УСТАНОВИТЬ", self.go, "primary", 18)

    def go(self):
        if self.state == "done":
            subprocess.Popen([os.path.join(self.dst, "SweetieFox.exe")], cwd=self.dst)
            self.host.root.destroy()
            return
        if self.state == "work":
            return
        self.state = "work"
        self.set_text("go", "УСТАНАВЛИВАЮ…")
        self.set_text("msg", "Копирую файлы…")
        threading.Thread(target=self.work, daemon=True).start()

    def work(self):
        post = self.host.post
        try:
            os.makedirs(self.dst, exist_ok=True)
            exe = os.path.join(self.dst, "SweetieFox.exe")
            shutil.copy2(sys.executable, exe)
            if self.shortcut:
                make_shortcut(exe)
            self.state = "done"
            post(lambda: (self.set_text("go", "ЗАПУСТИТЬ"),
                          self.set_text("msg", "Готово! Ярлык «Sweetie Fox» лежит на рабочем столе." if self.shortcut
                                        else "Готово!")))
        except Exception as e:
            self.state = "ask"
            err = f"Ошибка: {e}"
            post(lambda: (self.set_text("go", "УСТАНОВИТЬ"), self.set_text("msg", err)))


def main():
    host = Host("Установка Sweetie Fox", W, H)
    host.set_scene(InstallScene(host))
    host.run()
