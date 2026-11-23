# -*- coding: utf-8 -*-
"""Экран загрузки, вход и регистрация DCODE."""
import re, threading, webbrowser
from PIL import Image
from .ui import asset, radial, Bar, Button, Link, Check, SUB, DIM, BAD, GOOD, V2
from .license import LicenseError, NetError

TELEGRAM_URL = "https://t.me/sweetielauncher"


class Gate:
    def __init__(self, host, lic, on_ok, note="", mode="login"):
        h = self.h = host
        h.clear()
        self.lic, self.on_ok, self.busy, self.alive = lic, on_ok, False, True
        self.res, self.pg, self.adv, self.mode, self.note = None, 0.0, False, "welcome", note
        W, S = h.W, h.S
        for p in ("welcome", "login", "reg", "banned"):
            h.pages.add(p)

        def head(p, d, y):
            h.image(W / 2 - 150, y + d / 2 - 150, radial(int(300 * S), V2, 0.45), p)
            h.image(W / 2 - d / 2, y, asset("icon.png").resize((int(d * S),) * 2, Image.LANCZOS), p)

        head("welcome", 130, 56)
        h.text("welcome", W / 2, 214, "DCODE", 34, True, "#ffffff", "n")
        h.text("welcome", W / 2, 258, "M I N E C R A F T   L A U N C H E R", 10, False, DIM, "n")
        self.bar = Bar(h, "welcome", W / 2 - 170, 330, 340, 8)
        self.t_load = h.text("welcome", W / 2, 354, "Загрузка…", 11, False, SUB, "n")

        X0, X1 = W / 2 - 150, W / 2 + 150
        self.F = {"login": {}, "reg": {}}

        def fld(pg, key, y, label, secret=False):
            h.text(pg, X0 + 4, y - 4, label, 8, True, DIM, "sw")
            self.F[pg][key] = h.field(pg, (X0, y, X1, y + 40), secret)

        head("login", 64, 22)
        h.text("login", W / 2, 96, "Вход в аккаунт", 22, True, "#ffffff", "n")
        fld("login", "u", 152, "НИКНЕЙМ")
        fld("login", "p", 214, "ПАРОЛЬ", True)
        Button(h, "login", (X0, 278, X1, 330), "Войти", self.submit, "primary", 15, lambda: not self.busy)
        self.st_login = h.text("login", W / 2, 346, "", 11, False, SUB, "n", width=300, justify="center")
        h.text("login", W / 2 - 4, 408, "Нет аккаунта?", 11, False, SUB, "e")
        Link(h, "login", W / 2 + 4, 408, "Регистрация", lambda: self.show("reg"), 11, "w")

        head("reg", 56, 16)
        h.text("reg", W / 2, 82, "Регистрация", 22, True, "#ffffff", "n")
        fld("reg", "u", 132, "НИКНЕЙМ")
        fld("reg", "p", 188, "ПАРОЛЬ (МИН. 6)", True)
        fld("reg", "k", 244, "КОД ЛИЦЕНЗИИ")
        self.agree = Check(h, "reg", X0, 304, "Согласен с условиями использования", True, 10)
        Button(h, "reg", (X0, 326, X1, 372), "Создать аккаунт", self.submit, "primary", 14, lambda: not self.busy)
        self.st_reg = h.text("reg", W / 2, 386, "", 11, False, SUB, "n", width=300, justify="center")
        Link(h, "reg", W / 2, 432, "‹  Назад ко входу", lambda: self.show("login"), 11)

        head("banned", 90, 50)
        h.text("banned", W / 2, 160, "Вы заблокированы", 24, True, "#ffffff", "n")
        self.t_ban = h.text("banned", W / 2, 204, "", 12, False, SUB, "n", width=340, justify="center")
        Button(h, "banned", (X0 - 20, 270, X1 + 20, 322), "Обжаловать в Telegram", lambda: webbrowser.open(TELEGRAM_URL), "primary", 14)
        Link(h, "banned", W / 2, 350, "Выйти из аккаунта", self._ban_out, 11)

        for p in ("login", "reg"):
            for e in self.F[p].values():
                e.bind("<Return>", lambda ev: self.submit())
        h.show("welcome", False)
        h.every(self._tick)
        threading.Thread(target=self._startup, daemon=True).start()

    def _startup(self):
        try:
            self.res = self.lic.startup_check()
        except Exception as e:
            self.res = ("none", str(e))

    def _tick(self, now, dt):
        if not self.alive or self.adv:
            return
        tgt = 1.0 if self.res else 0.88
        self.pg = min(tgt, self.pg + dt * (1.3 if self.res else 0.3))
        self.bar.set(self.pg)
        if self.pg >= 0.999:
            self.adv = True
            self.h.set_text(self.t_load, "Готово")
            self.h.after(200, self._advance)

    def _advance(self):
        if not self.alive:
            return
        st, msg = self.res
        if st == "ok":
            self.alive = False
            self.on_ok()
        elif st == "banned":
            self.ban(msg)
        else:
            self.show("login")
            m = msg or self.note
            self._st("login", m, BAD if m else SUB)

    def show(self, mode):
        self.mode = mode
        self.h.show(mode)
        if mode in self.F:
            e = self.F[mode]["u"] if not self.F[mode]["u"].get() else self.F[mode]["p"]
            try:
                e.focus_set()
            except Exception:
                pass

    def ban(self, msg=""):
        self.h.set_text(self.t_ban, msg or "Доступ к аккаунту ограничен.")
        self.show("banned")

    def _ban_out(self):
        self.lic.logout()
        self.show("login")

    def _st(self, pg, text, col=SUB):
        self.h.set_text(self.st_login if pg == "login" else self.st_reg, text, col)

    def submit(self):
        if self.busy or self.mode not in self.F:
            return
        pg, f = self.mode, self.F[self.mode]
        u, p = f["u"].get().strip(), f["p"].get()
        k = f["k"].get().strip() if "k" in f else ""
        if pg == "reg" and not self.agree.val:
            return self._st(pg, "Нужно согласиться с условиями", BAD)
        if pg == "reg" and not re.match(r"^[A-Za-z0-9_]{3,20}$", u):
            return self._st(pg, "Логин: 3–20 символов, латиница, цифры и _", BAD)
        if not u or len(p) < (6 if pg == "reg" else 1):
            return self._st(pg, "Пароль: минимум 6 символов" if pg == "reg" else "Введи логин и пароль", BAD)
        if pg == "reg" and not k:
            return self._st(pg, "Введи ключ лицензии", BAD)
        self.busy = True
        self._st(pg, "Проверяю…")
        post = self.h.post

        def work():
            try:
                (self.lic.login(u, p) if pg == "login" else self.lic.register(u, p, k))
                post(self._ok)
            except LicenseError as e:
                m, c = str(e), e.code
                post(lambda: self._fail(m, c))
            except NetError as e:
                m = str(e)
                post(lambda: self._fail(m, "net"))
            except Exception as e:
                m = f"Ошибка: {e}"
                post(lambda: self._fail(m, "x"))
        threading.Thread(target=work, daemon=True).start()

    def _fail(self, msg, code):
        self.busy = False
        if code == "banned":
            return self.ban(msg)
        self._st(self.mode, msg, BAD)

    def _ok(self):
        self._st(self.mode, f"Добро пожаловать, {self.lic.username}!", GOOD)

        def go():
            if self.alive:
                self.alive = False
                self.on_ok()
        self.h.after(600, go)
