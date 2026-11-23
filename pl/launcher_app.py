# -*- coding: utf-8 -*-
"""Главный экран DCODE: только «Потяните, чтобы запустить» и отмена."""
import threading
from PIL import Image
from .common import *
from . import engine
from . import license as lic_mod
from .ui import Host, Pull, Link, asset, radial, SUB, DIM, V2
from .license_ui import Gate

W, H = 720, 470


class Cancelled(Exception):
    pass


class Launcher:
    def __init__(self, host, P, lic):
        h = self.h = host
        h.clear()
        self.P, self.lic, self.cfg = P, lic, load_cfg(P)
        self.alive, self.busy, self.cancel, self.running, self.proc = True, False, False, False, None
        S = h.S
        h.pages.add("home")
        h.image(W / 2 - 170, 30, radial(int(340 * S), V2, 0.5), "home")
        h.image(W / 2 - 70, 64, asset("icon.png").resize((int(140 * S),) * 2, Image.LANCZOS), "home")
        h.text("home", W / 2, 222, "DCODE", 32, True, "#ffffff", "n")
        h.text("home", W / 2, 262, "M I N E C R A F T   L A U N C H E R", 10, False, DIM, "n")
        self.status = h.text("home", W / 2, 300, "", 12, False, SUB, "n", width=520, justify="center")
        self.pull = Pull(h, "home", W / 2, 336, 440, 64, "Потяните, чтобы запустить", self.trigger)
        self.cancel_l = Link(h, "home", W / 2, 424, "Отменить", self.on_cancel, 12)
        h.canvas.itemconfig(self.cancel_l.t, state="hidden")
        self.lic_t = h.text("home", 28, H - 26, "", 10, False, SUB, "w")
        Link(h, "home", W - 28, H - 26, "Выйти", self.logout, 10, "e")
        h.show("home", False)
        self._lic_tick()
        self._recheck()

    def _lic_tick(self):
        if not self.alive:
            return
        l = self.lic.left()
        col = SUB if (l is None or l > 3 * 86400) else ("#fbbf24" if l > 86400 else "#fb7185")
        self.h.set_text(self.lic_t, "Лицензия: " + lic_mod.fmt_left(l), col)
        if l is not None and l <= 0:
            return self.gate("Срок лицензии истёк")
        self.h.after(1000, self._lic_tick)

    def _recheck(self):
        if not self.alive:
            return

        def work():
            try:
                self.lic.check()
            except lic_mod.LicenseError as e:
                m = "Вы получили блокировку" if e.code == "banned" else (str(e) or "Сессия завершена")
                self.h.post(lambda: self.gate(m))
            except Exception:
                pass   # нет связи — играем дальше
        threading.Thread(target=work, daemon=True).start()
        self.h.after(15000, self._recheck)

    def gate(self, note):
        if not self.alive:
            return
        self.kill()
        self.alive = False
        self.lic.logout()
        show_gate(self.h, self.P, self.lic, note)

    def logout(self):
        self.kill()
        self.alive = False
        self.lic.logout()
        show_gate(self.h, self.P, self.lic, "Ты вышел из аккаунта")

    def say(self, s):
        self.h.set_text(self.status, s)

    def kill(self):
        self.cancel = True
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass
            self.proc = None

    def reset(self, msg=""):
        self.busy = self.running = self.cancel = False
        self.proc = None
        self.pull.set_busy(False)
        self.h.canvas.itemconfig(self.cancel_l.t, state="hidden")
        self.say(msg)

    def trigger(self):
        if self.busy:
            return
        if not self.lic.valid():
            return self.gate("Нужна действующая лицензия")
        self.busy, self.cancel = True, False
        need = not engine.state(self.P)["game"]
        self.pull.set_busy(True, "Установка…" if need else "Запуск…")
        self.pull.set_progress(0.0 if need else None)
        self.h.set_text(self.cancel_l.t, "Отменить")
        self.h.canvas.itemconfig(self.cancel_l.t, state="normal")
        self.say("Скачиваю игру — это один раз" if need else "Готовлю запуск…")
        post = self.h.post

        def chk():
            if self.cancel:
                raise Cancelled()

        def prog(f):
            chk()
            post(lambda: self.alive and self.pull.set_progress(f))

        def log(m):
            chk()
            post(lambda: self.alive and self.say(m))
        ctx = Ctx(log, prog, log)

        def work():
            try:
                if need:
                    engine.install_all(self.P, self.cfg, ctx)
                chk()
                post(lambda: self.alive and (self.pull.set_label("Запуск…"), self.pull.set_progress(None), self.say("Запускаю игру…")))
                if not self.cfg.get("nick") or self.cfg["nick"] == "Player":
                    self.cfg["nick"] = self.lic.username or "Player"
                save_cfg(self.P, self.cfg)
                proc = engine.launch(self.P, self.cfg, self.lic)
            except Cancelled:
                return post(lambda: self.alive and self.reset("Отменено"))
            except Exception as e:
                m = str(e)
                return post(lambda: self.alive and self.reset("Ошибка: " + m))
            post(lambda: self.alive and self.started(proc))
        threading.Thread(target=work, daemon=True).start()

    def started(self, proc):
        if self.cancel:
            try:
                proc.terminate()
            except Exception:
                pass
            return self.reset("Отменено")
        self.proc, self.running = proc, True
        self.pull.set_label("Игра запущена")
        self.h.set_text(self.cancel_l.t, "Закрыть игру")
        self.say("Окно появится через несколько секунд")
        self.poll()

    def poll(self):
        if not self.alive or not self.running:
            return
        if self.proc is None or self.proc.poll() is not None:
            return self.reset("Игра закрыта")
        self.h.after(1000, self.poll)

    def on_cancel(self):
        if self.running:
            self.kill()
            return self.reset("Игра закрыта")
        if self.busy:
            self.kill()
            self.say("Отменяю…")


def show_launcher(host, P, lic):
    host.launcher = Launcher(host, P, lic)


def show_gate(host, P, lic, note="", mode="login"):
    host.gate = Gate(host, lic, lambda: show_launcher(host, P, lic), note, mode)


def main(root):
    P = Paths(root)
    try:
        from . import installer
        threading.Thread(target=installer.refresh_shortcut_icon, daemon=True).start()
    except Exception:
        pass
    host = Host("DCODE", W, H)
    lic = lic_mod.Lic(root)
    show_gate(host, P, lic)
    host.run()
