# -*- coding: utf-8 -*-
"""Экран «Добро пожаловать»: анимация, вход / регистрация по ключу / продление."""
import re, threading
from PIL import Image, ImageChops
from .ui import Scene
from .license import LicenseError, NetError

SUB, DIM = "#c4bff0", "#9a94d0"
BAD, GOOD = "#fb7185", "#86efac"
BG = (36, 26, 100)


def _hex(c):
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, v))) for v in c)


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


class GateScene(Scene):
    PAGES = (("login", "Вход"), ("reg", "Регистрация"), ("ext", "Продлить"))

    def __init__(self, host, lic, on_ok, note="", mode="login"):
        super().__init__(host)
        pt = self.pt
        self.lic, self.on_ok, self.mode, self.busy = lic, on_ok, mode, False
        self.alive, self.anim_done, self.check_res = True, False, None
        self.note = note
        self.F = {}

        fox = pt.asset("fox.png")
        fox = fox.resize((210, int(fox.height * 210 / fox.width)), Image.LANCZOS)
        fox.putalpha(ImageChops.multiply(fox.getchannel("A"), pt.mask(fox.width, fox.height, 24)))
        ic = pt.icon(56)

        # ---------- приветствие ----------
        self.tag = "welcome"
        self.under.append(("welcome", lambda ov: pt.image(ov, fox, (335, 70))))
        self.w_items = [
            (self.text("w1", 440, 330, "Добро пожаловать", 42, True, "#ffffff", "n"), "#ffffff", 330),
            (self.text("w2", 440, 392, "в sweetie fox", 30, True, "#c4b5fd", "n"), "#c4b5fd", 392),
            (self.text("w3", 440, 448, "Войди или зарегистрируйся, чтобы продолжить", 15, False, SUB, "n"), SUB, 448),
        ]
        for it, col, y in self.w_items:
            self.c.itemconfig(it, fill=_hex(BG))

        # ---------- формы ----------
        for pg, title in self.PAGES:
            self.tag = pg
            self.under.append((pg, lambda ov: pt.glass(ov, (240, 108, 640, 556), 28, 105, 16)))
            self.under.append((pg, lambda ov: pt.image(ov, ic, (412, 122))))
            self.text("tt_" + pg, 440, 184, {"login": "С возвращением!", "reg": "Создай аккаунт", "ext": "Продление лицензии"}[pg],
                      24, True, "#ffffff", "n")
            for i, (p2, t2) in enumerate(self.PAGES):
                x0 = 262 + i * 120
                self.button(f"tab_{pg}_{p2}", (x0, 224, x0 + 112, 256), t2, (lambda p2=p2: self.show(p2)), "nav", 13,
                            sel=(lambda p2=p2: self.mode == p2))
            fields = [("u", "ЛОГИН", False), ("p", "ПАРОЛЬ", True)] + ([("k", "КЛЮЧ ЛИЦЕНЗИИ", False)] if pg != "login" else [])
            y = 272
            self.F[pg] = {}
            for key, lab, secret in fields:
                self.text(f"lb_{pg}_{key}", 266, y, lab, 11, True, SUB)
                e = self.entry((266, y + 17, 614, y + 49), self.lic.username if key == "u" and pg != "reg" else "")
                if secret:
                    e.config(show="•")
                e.bind("<Return>", lambda ev: self.submit())
                self.F[pg][key] = e
                y += 60
            self.text("st_" + pg, 440, y + 2, "", 13, False, SUB, "n", width=340)
            self.button("go_" + pg, (266, 440, 614, 484) if pg == "login" else (266, 498, 614, 542),
                        {"login": "Войти", "reg": "Зарегистрироваться", "ext": "Продлить и войти"}[pg], self.submit,
                        "primary", 15, lambda: not self.busy)
        self.tag = None
        self.set_page("welcome")
        self._anim(0)
        threading.Thread(target=self._startup, daemon=True).start()

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
        N = 34
        for i, (it, col, y) in enumerate(self.w_items):
            p = max(0.0, min(1.0, (step - i * 10) / N))
            e = 1 - (1 - p) ** 3
            try:
                self.c.itemconfig(it, fill=_hex(_mix(BG, _rgb(col), e)))
                self.host.place(it, 440, y + (1 - e) * 22)
            except Exception:
                pass
        if step < N + 30 + 22:
            self.host.root.after(33, lambda: self._anim(step + 1))
        else:
            self.anim_done = True
            self._advance()

    def _advance(self):
        if not self.alive:
            return
        if self.check_res is None:
            self.host.root.after(100, self._advance)
            return
        st, msg = self.check_res
        if st == "ok":
            self.on_ok()
        else:
            self.show("ext" if st == "expired" else self.mode)
            self._status(self.mode, msg or self.note, BAD if (msg or self.note) else SUB)

    def show(self, mode):
        self.mode = mode
        self.set_page(mode)
        first = self.F[mode]["u"] if not self.F[mode]["u"].get() else self.F[mode]["p"]
        try:
            first.focus_set()
        except Exception:
            pass

    def _status(self, pg, text, col=SUB):
        self.set_text("st_" + pg, text, col)

    def submit(self):
        if self.busy or self.mode == "welcome":
            return
        pg = self.mode
        f = self.F[pg]
        u, p = f["u"].get().strip(), f["p"].get()
        k = f["k"].get().strip() if "k" in f else ""
        if pg == "reg" and not re.match(r"^[A-Za-z0-9_]{3,20}$", u):
            return self._status(pg, "Логин: 3–20 символов, латиница, цифры и _", BAD)
        if not u or len(p) < (6 if pg == "reg" else 1):
            return self._status(pg, "Пароль: минимум 6 символов" if pg == "reg" else "Введи логин и пароль", BAD)
        if pg != "login" and not k:
            return self._status(pg, "Введи ключ лицензии", BAD)
        self.busy = True
        self._status(pg, "Проверяю…", SUB)
        self.refresh()
        post = self.host.post

        def work():
            try:
                {"login": lambda: self.lic.login(u, p), "reg": lambda: self.lic.register(u, p, k),
                 "ext": lambda: self.lic.extend(u, p, k)}[pg]()
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
        if code == "expired" and self.mode == "login":
            self.F["ext"]["u"].delete(0, "end")
            self.F["ext"]["u"].insert(0, self.F["login"]["u"].get())
            self.show("ext")
        self._status(self.mode, msg, BAD)
        self.refresh()

    def _success(self):
        self._status(self.mode, f"Добро пожаловать, {self.lic.username}! ♡", GOOD)
        self.host.root.after(700, lambda: self.alive and self.on_ok())
