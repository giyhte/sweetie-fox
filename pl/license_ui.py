# -*- coding: utf-8 -*-
"""Экран «Добро пожаловать»: анимация, вход / регистрация по ключу / продление."""
import re, threading, webbrowser
from PIL import Image
from .ui import Scene
from .license import LicenseError, NetError

SUB, DIM = "#c4bff0", "#9a94d0"
BAD, GOOD = "#fb7185", "#86efac"
BG = (8, 6, 22)
TELEGRAM_URL = "https://t.me/sweetielauncher"


def _hex(c):
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, v))) for v in c)


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


class GateScene(Scene):
    """Загрузка → вход / регистрация (без продления лицензии)."""

    def __init__(self, host, lic, on_ok, note="", mode="login"):
        super().__init__(host)
        pt = self.pt
        self.lic, self.on_ok, self.busy = lic, on_ok, False
        self.mode = "login"
        self.alive, self.anim_done, self.check_res = True, False, None
        self.note = note
        self.F = {}
        self.pgprog = 0.0
        self.remember, self.agree, self.show_pw = True, True, False
        side = pt.asset("auth_side.png")
        splash = pt.asset("splash.png")
        glass_f = lambda ov, b: pt.inset(ov, b, 12)

        # ---------- загрузка ----------
        self.tag = "welcome"
        self.under.append(("welcome", lambda ov: pt.image(ov, splash, (0, 0))))
        self.text("sp0", 44, 28, "Инициализация...", 10, False, "#e8e4ff", "w")
        self.text("sp1", 500, 372, "SWEETIE FOX", 40, True, "#ffffff", "center")
        self.text("sp2", 500, 412, "M I N E C R A F T    L A U N C H E R", 10, False, "#a78bfa", "center")
        self.bar((190, 456, 770, 464), lambda: self.pgprog)
        self.text("sp_pct", 790, 460, "0%", 15, True, "#ffffff", "w")
        self.text("sp3", 480, 492, "Загрузка лаунчера...", 11, False, SUB, "center")

        # ---------- общий каркас форм ----------
        for pg in ("login", "reg"):
            self.tag = pg
            self.under.append((pg, lambda ov: pt.image(ov, side, (0, 0))))
            self.under.append((pg, lambda ov: pt._fill(ov, (330, 0, 331, 563), (255, 255, 255, 28), Image.new("L", (1, 563), 255))))
            self.under.append((pg, lambda ov: pt.glass(ov, (331, 0, 1000, 563), 0, 70, 6, 0)))
        X0, X1 = 485, 845
        CX = (X0 + X1) // 2

        def field(pg, key, y, icon, secret=False, label=""):
            box = (X0, y, X1, y + 40)
            self.text(f"lb_{pg}_{key}", X0 + 2, y - 15, label, 9, True, SUB)
            self.under.append((pg, lambda ov, b=box: pt.inset(ov, b, 12)))
            self.glyph(icon, X0 + 22, y + 20, 16, (190, 175, 255, 255))
            e = self.entry((X0 + 44, y + 7, X1 - (44 if secret else 10), y + 33), "")
            if secret:
                e.config(show="\u2022")
            e.bind("<Return>", lambda ev: self.submit())
            self.F[pg][key] = e
            return e

        # ---------- вход ----------
        pg = "login"
        self.tag = pg
        self.F[pg] = {}
        self.text("tt_login", X0, 52, "Вход в аккаунт", 24, True, "#ffffff")
        self.text("sub_login", X0, 90, "Добро пожаловать обратно!", 12, False, SUB)
        field(pg, "u", 146, "user", False, "НИКНЕЙМ")
        field(pg, "p", 206, "lock", True, "ПАРОЛЬ")
        self.glyph("eye", X1 - 22, 226, 16, (190, 175, 255, 255))
        self.link((X1 - 36, 210, X1, 242), self._toggle_pw)
        self.check((X0, 266, X0 + 18, 284), lambda: self.remember, lambda v: setattr(self, "remember", v))
        self.text("rem", X0 + 26, 275, "Запомнить меня", 10, False, "#e8e4ff", "w")
        self.text("forg", X1, 275, "Забыли пароль?", 10, False, "#a78bfa", "e")
        self.link((X1 - 100, 266, X1, 284), lambda: webbrowser.open(TELEGRAM_URL))
        self.button("go_login", (X0, 298, X1, 342), "Войти  \u203a", self.submit, "primary", 14, lambda: not self.busy)
        self.text("or", CX, 366, "или", 10, False, DIM, "center")
        self.under.append((pg, lambda ov: pt._fill(ov, (X0, 366, CX - 22, 367), (255, 255, 255, 30), Image.new("L", (CX - 22 - X0, 1), 255))))
        self.under.append((pg, lambda ov: pt._fill(ov, (CX + 22, 366, X1, 367), (255, 255, 255, 30), Image.new("L", (X1 - CX - 22, 1), 255))))
        self.button("tg_login", (X0, 384, X1, 424), "Войти через Telegram", lambda: self._soon("login"), "ghost", 12)
        self.glyph("plane", CX - 88, 404, 16, (225, 215, 255, 255))
        self.text("st_login", CX, 444, "", 11, False, SUB, "center", width=340)
        self.text("noacc", CX - 4, 488, "Нет аккаунта?", 10, False, SUB, "e")
        self.text("goreg", CX + 2, 488, "Зарегистрироваться", 10, False, "#a78bfa", "w")
        self.link((CX, 478, CX + 130, 498), lambda: self.show("reg"))

        # ---------- регистрация ----------
        pg = "reg"
        self.tag = pg
        self.F[pg] = {}
        self.text("tt_reg", X0, 52, "Регистрация", 24, True, "#ffffff")
        self.text("sub_reg", X0, 90, "Создай свой аккаунт!", 12, False, SUB)
        field(pg, "u", 136, "user", False, "НИКНЕЙМ")
        field(pg, "p", 192, "lock", True, "ПАРОЛЬ")
        field(pg, "k", 248, "key", False, "КОД ЛИЦЕНЗИИ")
        self.check((X0, 308, X0 + 18, 326), lambda: self.agree, lambda v: setattr(self, "agree", v))
        self.text("agr", X0 + 26, 317, "Я согласен с", 10, False, "#e8e4ff", "w")
        self.text("agr2", X0 + 26 + 76, 317, "условиями использования", 10, False, "#a78bfa", "w")
        self.link((X0 + 100, 308, X0 + 250, 326), lambda: webbrowser.open(TELEGRAM_URL))
        self.button("go_reg", (X0, 342, X1, 386), "Зарегистрироваться  \u203a", self.submit, "primary", 14, lambda: not self.busy)
        self.text("st_reg", CX, 404, "", 11, False, SUB, "center", width=340)
        self.button("back_reg", (X0, 440, X0 + 150, 478), "Назад", lambda: self.show("login"), "ghost", 12)
        self.glyph("back", X0 + 30, 459, 14, (225, 215, 255, 255))

        # ---------- блокировка ----------
        self.tag = "banned"
        self.under.append(("banned", lambda ov: pt.image(ov, splash, (0, 0))))
        self.under.append(("banned", lambda ov: pt.glass(ov, (330, 150, 670, 410), 24, 120, 16)))
        self.text("ban_t", 500, 190, "Вы заблокированы", 24, True, "#ffffff", "n")
        self.text("ban_m", 500, 232, "", 12, False, SUB, "n", width=300)
        self.button("ban_tg", (360, 300, 640, 344), "Обжаловать в Telegram",
                    lambda: webbrowser.open(TELEGRAM_URL), "primary", 13)
        self.text("ban_u", 500, 354, TELEGRAM_URL, 10, False, DIM, "n")
        self.button("ban_out", (360, 372, 640, 402), "Выйти из аккаунта", self._ban_logout, "ghost", 11)

        self.tag = None
        self.set_page("welcome")
        self._anim(0)
        threading.Thread(target=self._startup, daemon=True).start()

    def _toggle_pw(self):
        self.show_pw = not self.show_pw
        for pg in ("login", "reg"):
            if "p" in self.F.get(pg, {}):
                self.F[pg]["p"].config(show="" if self.show_pw else "\u2022")
        for r in self.regions:
            if r.get("kind") == "glyph" and r["name"] in ("eye", "eyeoff"):
                r["name"] = "eyeoff" if self.show_pw else "eye"
        self.refresh()

    def _soon(self, pg):
        self._status(pg, "Вход через Telegram — скоро", "#a78bfa")

    # ---------- логика ----------
    def _startup(self):
        try:
            self.check_res = self.lic.startup_check()
        except Exception as e:
            self.check_res = ("none", str(e))

    def destroy(self):
        self.alive = False
        super().destroy()

    def _anim(self, step):
        if not self.alive:
            return
        target = 1.0 if self.check_res is not None else 0.9
        self.pgprog = min(target, self.pgprog + (0.035 if self.check_res is not None else 0.012))
        self.set_text("sp_pct", f"{int(self.pgprog * 100)}%")
        self.set_text("sp3", "Загрузка лаунчера..." if self.pgprog < 1 else "Готово")
        self.refresh()
        if self.pgprog >= 0.999:
            self.anim_done = True
            self.host.root.after(250, self._advance)
        else:
            self.host.root.after(33, lambda: self._anim(step + 1))

    def _advance(self):
        if not self.alive:
            return
        if self.check_res is None:
            self.host.root.after(100, self._advance)
            return
        st, msg = self.check_res
        if st == "ok":
            self.on_ok()
        elif st == "banned":
            self.show_banned(msg)
        else:
            self.show("login")
            self._status("login", msg or self.note, BAD if (msg or self.note) else SUB)

    def show(self, mode):
        self.mode = mode
        self.set_page(mode)
        if mode not in self.F:
            return
        for e in self.F[mode].values():
            try:
                e.sync()
            except Exception:
                pass
        first = self.F[mode]["u"] if not self.F[mode]["u"].get() else self.F[mode]["p"]
        try:
            first.focus_set()
        except Exception:
            pass

    def show_banned(self, msg=""):
        self.mode = "banned"
        self.set_text("ban_m", msg or "Доступ к аккаунту ограничен.")
        self.show("banned")

    def _ban_logout(self):
        self.lic.logout()
        self.show("login")

    def _status(self, pg, text, col=SUB):
        self.set_text("st_" + pg, text, col)

    def submit(self):
        if self.busy or self.mode == "welcome":
            return
        pg = self.mode
        f = self.F[pg]
        u, p = f["u"].get().strip(), f["p"].get()
        k = f["k"].get().strip() if "k" in f else ""
        if pg == "reg" and not self.agree:
            return self._status(pg, "Нужно согласиться с условиями использования", BAD)
        if pg == "reg" and not re.match(r"^[A-Za-z0-9_]{3,20}$", u):
            return self._status(pg, "Логин: 3–20 символов, латиница, цифры и _", BAD)
        if not u or len(p) < (6 if pg == "reg" else 1):
            return self._status(pg, "Пароль: минимум 6 символов" if pg == "reg" else "Введи логин и пароль", BAD)
        if pg == "reg" and not k:
            return self._status(pg, "Введи ключ лицензии", BAD)
        self.busy = True
        self._status(pg, "Проверяю…", SUB)
        self.refresh()
        post = self.host.post

        def work():
            try:
                {"login": lambda: self.lic.login(u, p), "reg": lambda: self.lic.register(u, p, k)}[pg]()
                post(self._success)
            except LicenseError as e:
                msg, code = str(e), e.code
                post(lambda: self._fail(msg, code))
            except NetError as e:
                msg = str(e)
                post(lambda: self._fail(msg, "net"))
            except Exception as e:
                msg = f"Ошибка: {e}"
                post(lambda: self._fail(msg, "x"))
        threading.Thread(target=work, daemon=True).start()

    def _fail(self, msg, code):
        self.busy = False
        if code == "banned":
            return self.show_banned(msg)
        self._status(self.mode, msg, BAD)
        self.refresh()

    def _success(self):
        self._status(self.mode, f"Добро пожаловать, {self.lic.username}! ♡", GOOD)
        self.host.root.after(700, lambda: self.alive and self.on_ok())
