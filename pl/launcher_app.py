# -*- coding: utf-8 -*-
"""Главный экран DCODE: только «Потяните, чтобы запустить» и отмена."""
import re, threading, webbrowser
from PIL import Image
from .common import *
from . import engine
from . import license as lic_mod
from .ui import Host, Pull, Link, Button, asset, radial, shape, SUB, DIM, V2, GOOD, BAD
from . import news as news_mod, profile as prof
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
        self.badge = h.text("home", W / 2, 280, "●  Проверяю…", 12, True, DIM, "n")
        self.status = h.text("home", W / 2, 304, "", 11, False, SUB, "n", width=520, justify="center")
        self.pull = Pull(h, "home", W / 2, 336, 440, 64, "Потяните, чтобы запустить", self.trigger)
        self.cancel_l = Link(h, "home", W / 2, 424, "Отменить", self.on_cancel, 12)
        h.canvas.itemconfig(self.cancel_l.t, state="hidden")
        self.lic_t = h.text("home", 28, H - 26, "", 10, False, SUB, "w")
        Link(h, "home", W - 28, H - 26, "Выйти", self.logout, 10, "e")
        self.gstate = "missing"
        self.tab_links = {}
        for key, label, x in (("home", "Игра", 28), ("news", "Новости", 84), ("profile", "Профиль", 164)):
            self.tab_links[key] = Link(h, None, x, 24, label, lambda k=key: self.tab(k), 12, "w",
                                       "#ffffff" if key == "home" else DIM)
        self.build_news()
        self.build_profile()
        h.show("home", False)
        self.refresh_status()
        self._lic_tick()
        self._recheck()

    def _lic_tick(self):
        if not self.alive:
            return
        l = self.lic.left()
        col = SUB if (l is None or l > 3 * 86400) else ("#fbbf24" if l > 86400 else "#fb7185")
        self.h.set_text(self.lic_t, "Лицензия: " + lic_mod.fmt_left(l), col)
        self.h.set_text(self.prof_info, "Аккаунт: %s\nЛицензия: %s" % (self.lic.username or "—", lic_mod.fmt_left(l)))
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

    COL = {"ready": "#86efac", "update": "#fbbf24", "missing": "#fb7185"}
    LBL = {"ready": "Потяните, чтобы запустить", "update": "Потяните, чтобы обновить",
           "missing": "Потяните, чтобы скачать"}

    def refresh_status(self):
        def work():
            try:
                st = engine.game_status(self.P, self.cfg)
            except Exception:
                st = ("missing", "Игра не скачана")
            self.h.post(lambda: self.alive and self._apply_status(st))
        threading.Thread(target=work, daemon=True).start()

    def _apply_status(self, st):
        self.gstate = st[0]
        self.h.set_text(self.badge, "●  " + st[1], self.COL[st[0]])
        self.pull.text0 = self.LBL[st[0]]
        if not self.busy and not self.running:
            self.pull.set_label(self.LBL[st[0]])

    def tab(self, key):
        self.h.show({"home": "home", "news": "news0", "profile": "profile"}[key], True)
        for k, lk in self.tab_links.items():
            lk.color = "#ffffff" if k == key else DIM
            self.h.canvas.itemconfig(lk.t, fill=lk.color)

    def build_news(self):
        h, S = self.h, self.h.S
        items, per = news_mod.NEWS, 3
        n = max(1, -(-len(items) // per))
        for pi in range(n):
            pg = "news%d" % pi
            h.pages.add(pg)
            h.text(pg, W / 2, 52, "Новости", 20, True, "#ffffff", "n")
            for j, it in enumerate(items[pi * per:(pi + 1) * per]):
                y = 94 + j * 104
                h.image(46, y, shape(int(628 * S), int(94 * S), int(14 * S), fill=(255, 255, 255, 14),
                                     outline=(190, 150, 255, 60), ow=max(1, round(S))), pg)
                h.text(pg, 68, y + 14, it["title"], 14, True, "#ffffff", "nw")
                h.text(pg, 652, y + 17, it.get("date", ""), 9, False, DIM, "ne")
                h.text(pg, 68, y + 42, it.get("text", ""), 11, False, SUB, "nw", width=430)
                if it.get("url"):
                    Button(h, pg, (516, y + 46, 650, y + 80), it.get("btn") or "Открыть",
                           lambda u=it["url"]: webbrowser.open(u), "secondary", 12)
            if n > 1:
                h.text(pg, W / 2, 412, "%d / %d" % (pi + 1, n), 10, False, DIM, "n")
                if pi > 0:
                    Link(h, pg, W / 2 - 70, 436, "‹  Новее", lambda p=pi - 1: h.show("news%d" % p, True), 11)
                if pi < n - 1:
                    Link(h, pg, W / 2 + 70, 436, "Старее  ›", lambda p=pi + 1: h.show("news%d" % p, True), 11)

    def build_profile(self):
        h, S = self.h, self.h.S
        pg = "profile"
        h.pages.add(pg)
        X0, X1 = W / 2 - 150, W / 2 + 150
        nick = self.cfg.get("nick") if self.cfg.get("nick") not in (None, "", "Player") else (self.lic.username or "Player")
        h.text(pg, W / 2, 46, "Профиль", 20, True, "#ffffff", "n")
        self.av_it = h.image(W / 2 - 48, 84, prof.make_avatar(self.P, nick, int(96 * S)), pg)
        Link(h, pg, W / 2 - 8, 194, "Сменить аватар", self.pick_avatar, 11, "e")
        Link(h, pg, W / 2 + 8, 194, "Убрать", self.drop_avatar, 11, "w")
        h.text(pg, X0 + 4, 232, "НИК В ИГРЕ", 8, True, DIM, "sw")
        self.nick_e = h.field(pg, (X0, 238, X1, 278), False, nick)
        Button(h, pg, (X0, 292, X1, 338), "Сохранить профиль", self.save_profile, "primary", 14)
        self.prof_st = h.text(pg, W / 2, 348, "", 11, False, SUB, "n", width=320, justify="center")
        self.prof_info = h.text(pg, W / 2, 384, "", 11, False, SUB, "n", width=400, justify="center")

    def prof_say(self, t, col=SUB):
        self.h.set_text(self.prof_st, t, col)

    def _set_avatar(self):
        S = self.h.S
        nick = self.cfg.get("nick") if self.cfg.get("nick") not in (None, "", "Player") else (self.lic.username or "Player")
        p = self.h.ImageTk.PhotoImage(prof.make_avatar(self.P, nick, int(96 * S)))
        self.h.canvas.itemconfig(self.av_it, image=p)
        self.h._pin[self.av_it] = p

    def pick_avatar(self):
        try:
            from tkinter import filedialog
            f = filedialog.askopenfilename(parent=self.h.root, title="Выберите аватар",
                                           filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp *.webp"), ("Все файлы", "*.*")])
            if not f:
                return
            prof.save_avatar(self.P, f)
            self._set_avatar()
            self.prof_say("Аватар обновлён", GOOD)
        except Exception:
            self.prof_say("Не удалось загрузить картинку", BAD)

    def drop_avatar(self):
        prof.remove_avatar(self.P)
        self._set_avatar()
        self.prof_say("Аватар убран", SUB)

    def save_profile(self):
        n = self.nick_e.get().strip()
        if not re.fullmatch(r"[A-Za-z0-9_]{3,16}", n):
            return self.prof_say("Ник: 3–16 символов, A–Z, 0–9, _", BAD)
        self.cfg["nick"] = n
        save_cfg(self.P, self.cfg)
        self._set_avatar()
        self.prof_say("Профиль сохранён. Ник применится при запуске игры", GOOD)

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
        self.refresh_status()

    def trigger(self):
        if self.busy:
            return
        if not self.lic.valid():
            return self.gate("Нужна действующая лицензия")
        self.busy, self.cancel = True, False
        st = engine.game_status(self.P, self.cfg)[0]
        need = st != "ready"
        self.pull.set_busy(True, {"missing": "Установка…", "update": "Обновление…"}.get(st, "Запуск…"))
        self.pull.set_progress(0.0 if need else None)
        self.h.set_text(self.cancel_l.t, "Отменить")
        self.h.canvas.itemconfig(self.cancel_l.t, state="normal")
        self.say({"missing": "Скачиваю игру — это один раз", "update": "Обновляю игру…"}.get(st, "Готовлю запуск…"))
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
        self.refresh_status()
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
