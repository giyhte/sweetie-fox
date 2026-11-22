# -*- coding: utf-8 -*-
import os, threading, time, webbrowser
from PIL import Image, ImageChops
from .common import *
from . import engine, updater
from .ui import Host, Scene
from . import license as lic_mod
from .license_ui import GateScene

W, H = 1000, 563
SUB = "#c4bff0"
DIM = "#8f88c8"
OK, BAD = (134, 239, 172), (251, 113, 133)
PAGES = ["home", "versions", "set", "acc", "mods"]
NAV = [("home", "Главная", "home"), ("set", "Настройки", "gear"),
       ("acc", "Аккаунты", "user"), ("mods", "Моды", "puzzle")]
TELEGRAM_URL = "https://t.me/sweetielauncher"
LIGHT, MUTED = (225, 215, 255, 255), (150, 140, 205, 255)


def cover(im, w, h, align_right=False):
    sc = max(w / im.width, h / im.height)
    im = im.resize((int(im.width * sc) + 1, int(im.height * sc) + 1), Image.LANCZOS)
    l = (im.width - w) if align_right else (im.width - w) // 2
    t = (im.height - h) // 2
    return im.crop((l, t, l + w, t + h))


def text_w(txt, size):
    try:
        from .ui import pil_font
        return pil_font(size).getlength(txt)
    except Exception:
        return len(txt) * size * 0.6


class LauncherScene(Scene):
    def __init__(self, host, P, lic=None):
        super().__init__(host)
        self.P = P
        self.lic = lic
        self._alive = True
        self.cfg = load_cfg(P)
        self.busy, self.prog = False, 0.0
        self.t0, self.eta, self.guess = None, None, 240.0
        self.proc = None
        self.launch_pending = False
        self.launch_cancel = False
        self.game_running = False
        engine.hide_own_mod(P)  # подчистить, если осталось с прошлого запуска
        self.st = engine.state(P)
        self.nav = "home"
        pt = self.pt

        # ---- картинки ----
        logo = pt.asset("logo_d.png")
        side_logo = logo.resize((104, int(logo.height * 104 / logo.width)), Image.LANCZOS)
        av = logo.resize((74, int(logo.height * 74 / logo.width)), Image.LANCZOS)
        hero = cover(pt.asset("hero.png"), 625, 254, True)
        fade = Image.new("L", hero.size, 255)
        fp = fade.load()
        for yy in range(hero.height):
            for xx in range(hero.width):
                a = 255
                if yy > hero.height * 0.55:
                    a = int(255 * (1 - (yy - hero.height * 0.55) / (hero.height * 0.45)))
                if xx < 90:
                    a = a * xx // 90
                fp[xx, yy] = a
        hero.putalpha(ImageChops.multiply(fade, pt.mask(hero.width, hero.height, 20)))
        thumb = Image.new("RGBA", (155, 80), (14, 10, 40, 255))
        tl = logo.resize((96, int(logo.height * 96 / logo.width)), Image.LANCZOS)
        thumb.alpha_composite(tl, ((155 - tl.width) // 2, (80 - tl.height) // 2))
        thumb.putalpha(pt.mask(155, 80, 12))
        grass = Image.new("RGBA", (26, 26), (0, 0, 0, 0))
        from PIL import ImageDraw
        gd = ImageDraw.Draw(grass)
        gd.rectangle((0, 0, 25, 25), fill=(120, 84, 52, 255))
        gd.rectangle((0, 0, 25, 8), fill=(86, 160, 56, 255))
        gd.rectangle((4, 8, 8, 11), fill=(86, 160, 56, 255))
        gd.rectangle((16, 8, 21, 12), fill=(86, 160, 56, 255))
        grass.putalpha(pt.mask(26, 26, 4))

        # ---- каркас окна ----
        self.under.append(lambda ov: pt._fill(ov, (6, 6, W - 6, H - 6), (255, 255, 255, 34), pt.mask(W - 12, H - 12, 24, 1)))
        self.under.append(lambda ov: pt.glass(ov, (12, 12, 178, H - 12), 22, 110, 10, 30))
        self.under.append(lambda ov: pt.image(ov, side_logo, (24 + (154 - side_logo.width) // 2 + 1, 40)))
        for i, (k, label, gl) in enumerate(NAV):
            cy = 224 + i * 41
            self.button("nav_" + k, (30, cy - 19, 176, cy + 19), "", (lambda k=k: self.go(k)), "nav", 13,
                        sel=(lambda k=k: self.nav == k))
            self.glyph(gl, 55, cy, 18, (lambda k=k: LIGHT if self.nav == k else MUTED))
            self.text("navt_" + k, 78, cy, label, 12, False, "#e8e4ff", "w")
        tg, tgh = pt.telegram_icon(24), pt.telegram_icon(24, hover=True)
        self.imgbtn((89, 432, 113, 456), tg, tgh, lambda: webbrowser.open(TELEGRAM_URL))
        self.text("side_name", 95, 488, "Sweetie Fox Launcher \u2665", 9, False, DIM, "center")
        self.text("side_ver", 95, 504, "v" + VERSION, 9, False, DIM, "center")

        # ---- Главная ----
        self.tag = "home"
        self.under.append(("home", lambda ov: pt.image(ov, hero, (177, 8))))
        self.under.append(("home", lambda ov: pt._grad_fill(ov, (206, 231, 277, 233), (140, 100, 255), (60, 40, 140), 1)))
        self.text("w1", 206, 126, "Добро пожаловать", 23, True, "#ffffff")
        wv = text_w("в ", 23)
        w2 = text_w("Sweetie Fox", 23)
        self.text("w2a", 206, 152, "в ", 23, True, "#ffffff")
        self.text("w2b", 206 + wv, 152, "Sweetie Fox", 23, True, "#a78bfa")
        self.text("w2c", 206 + wv + w2 + 6, 152, "Launcher!", 23, True, "#ffffff")
        self.text("w3", 207, 188, "Погружайся в мир Minecraft\nс максимальным комфортом.", 13, False, SUB)

        # новости
        self.under.append(("home", lambda ov: pt.glass(ov, (199, 262, 780, 402), 18, 100, 12, 34)))
        self.glyph("megaphone", 221, 284, 17, (160, 130, 255, 255))
        self.text("nh", 238, 284, "Новости", 14, True, "#ffffff", "w")
        self.text("nall", 746, 284, "Все новости", 10, False, SUB, "e")
        self.glyph("arrow", 757, 284, 11, (200, 190, 255, 255))
        self.link((650, 274, 770, 294), lambda: webbrowser.open(TELEGRAM_URL))
        self.under.append(("home", lambda ov: pt._fill(ov, (213, 302, 766, 303), (255, 255, 255, 22), Image.new("L", (553, 1), 255))))
        self.under.append(("home", lambda ov: pt.image(ov, thumb, (213, 310))))
        self.text("n1", 388, 316, "Скоро выйдет обновление!", 13, True, "#ffffff")
        self.text("n2", 388, 340, "Мы готовим для вас ещё больше возможностей,\nоптимизации и крутых функций. Следите за новостями!", 10, False, "#9a94d0", width=360)
        self.glyph("clock", 394, 380, 12, (160, 150, 215, 255))
        self.text("n3", 406, 380, "25.11.2026", 10, False, DIM, "w")

        # выбор версии + запуск
        self.under.append(("home", lambda ov: pt.glass(ov, (192, 414, 780, 548), 18, 100, 12, 34)))
        self.glyph("play", 212, 436, 14, (160, 130, 255, 255))
        self.text("vh", 228, 436, "Выбор версии", 13, True, "#ffffff", "w")
        self.under.append(("home", lambda ov: pt.inset(ov, (206, 452, 366, 490), 12)))
        self.under.append(("home", lambda ov: pt.image(ov, grass, (214, 458))))
        self.text("ver", 250, 471, MC_VERSION, 13, False, "#ffffff", "w")
        self.glyph("chev", 346, 471, 12, (200, 190, 255, 255))
        self.link((206, 452, 366, 490), lambda: self.go("versions"))
        self.button("b_more", (378, 452, 540, 490), "Скачать другие версии", lambda: self.go("versions"), "ghost", 10)
        self.glyph("download", 524, 471, 12, (225, 215, 255, 255))
        self.button("b_main", (556, 438, 770, 494), "", self.on_main, "primary", 17, lambda: not self.busy)
        self.text("verst", 206, 500, "", 10, False, SUB)
        self.text("status", 206, 515, "", 10, False, SUB, width=430)
        self.text("pinfo", 766, 500, "", 10, True, "#ffffff", "ne")
        self.bar((206, 534, 766, 540), lambda: self.prog)

        # оптимизация
        self.under.append(("home", lambda ov: pt.glass(ov, (800, 428, 962, 494), 16, 100, 12, 34)))
        self.glyph("bolt", 817, 451, 14, (160, 130, 255, 255))
        self.text("opt", 833, 451, "Оптимизация", 11, True, "#ffffff", "w")
        self.text("opt2", 833, 474, "Для слабых ПК", 9, False, DIM, "w")
        self.switch((926, 442, 952, 460), lambda: self.cfg["low_mode"], lambda v: self._set("low_mode", v))

        # профиль
        self.under.append(("home", lambda ov: pt.glass(ov, (800, 74, 962, 360), 20, 105, 14, 36)))
        self.under.append(("home", lambda ov: pt._fill(ov, (836, 120, 938, 222), (120, 90, 255, 70), pt.mask(102, 102, 51))))
        self.under.append(("home", lambda ov: pt._fill(ov, (836, 120, 938, 222), (255, 255, 255, 70), pt.mask(102, 102, 51, 2))))
        self.under.append(("home", lambda ov: pt._fill(ov, (837, 121, 937, 221), (10, 8, 30, 235), pt.mask(100, 100, 50))))
        self.under.append(("home", lambda ov: pt.image(ov, av, (887 - av.width // 2, 171 - av.height // 2))))
        self.dot(926, 211, lambda: OK, 5)
        uname = (lic.username if lic else self.cfg["nick"]) or "Player"
        self.text("pname", 881, 244, uname, 15, True, "#ffffff", "center")
        self.dot(851, 268, lambda: OK, 3)
        self.text("ponl", 859, 268, "Онлайн", 10, False, SUB, "w")
        self.text("lic_left", 881, 286, "", 9, False, SUB, "center")
        if lic:
            self.button("b_logout", (815, 306, 947, 342), "Выйти", self._logout, "ghost", 12)
            self.glyph("exit", 838, 324, 15, (225, 215, 255, 255))

        # ---- общий вид «карточных» страниц ----
        def card(page, title):
            self.tag = page
            self.under.append((page, lambda ov: pt.glass(ov, (192, 14, 962, 548), 20, 100, 12, 34)))
            self.text("h_" + page, 222, 36, title, 20, True, "#ffffff")

        # ---- Версии ----
        card("versions", "Версии Minecraft")
        self.text("vv1", 222, 92, "Minecraft " + MC_VERSION + "  \u2022  Fabric", 18, True, "#ffffff")
        self.text("vv2", 222, 128, "Поддерживается одна версия — под неё подобраны моды на FPS\n"
                  "(Sodium, Lithium, FerriteCore и др.) и меню Sweetie Fox.", 12, False, SUB, width=640)
        self.button("b_inst", (222, 200, 500, 242), "Переустановить / обновить", lambda: self.on_install(force=True), "ghost", 13,
                    lambda: not self.busy)

        # ---- Настройки ----
        card("set", "Настройки")
        self.text("t_ram", 222, 92, "ПАМЯТЬ", 10, True, SUB)
        self.text("v_ram", 928, 90, "", 13, True, "#ffffff", "ne")
        self.slider((222, 118, 928, 138), lambda: self.cfg["ram"], self._set_ram, 1024, 8192, 256)
        for i, (k, name, hint) in enumerate([
                ("low_mode", "Режим для слабого ПК", "минимум графики: дальность 6, без частиц и теней"),
                ("own_mod", "Sweetie Fox Menu в игре", "меню на Right Shift: основное, визуалы (звуки, ивенты), буст FPS")]):
            y = 170 + i * 56
            self.text("o_" + k, 222, y, name, 14, True, "#ffffff")
            self.text("h_" + k, 222, y + 22, hint, 11, False, DIM)
            self.switch((872, y + 4, 928, y + 30), (lambda k=k: self.cfg[k]), (lambda v, k=k: self._set(k, v)))
        self.button("b_dir", (222, 300, 500, 342), "Папка игры", lambda: open_folder(P.game), "ghost", 13)
        self.text("a3", 222, 372, "Sweetie Fox Launcher  \u2022  версия " + VERSION + "\nАвтообновление лаунчера работает через GitHub.", 11, False, DIM)

        # ---- Аккаунты ----
        card("acc", "Аккаунт")
        self.text("t_nick", 222, 92, "НИК", 10, True, SUB)
        self.text("t_srv", 510, 92, "СЕРВЕР", 10, True, SUB)
        self.nick = self.entry((222, 114, 490, 150), self.cfg["nick"])
        self.srv = self.entry((510, 114, 928, 150), self.cfg["server"])
        self.text("o_aj", 222, 184, "Автовход на сервер", 14, True, "#ffffff")
        self.text("h_aj", 222, 206, "сразу подключаться к серверу из поля выше", 11, False, DIM)
        self.switch((872, 188, 928, 214), lambda: self.cfg["autojoin"], lambda v: self._set("autojoin", v))
        self.text("acc_note", 222, 260, "Вход по нику (оффлайн). Серверы с лицензионной защитой не пустят.", 12, False, DIM, width=700)

        # ---- Моды ----
        card("mods", "Моды")
        self.text("modlist", 222, 92, "", 12, False, SUB, width=700)
        self.button("b_mods", (222, 480, 500, 522), "Папка модов", lambda: open_folder(P.mods), "ghost", 13)
        self.button("b_res", (520, 480, 798, 522), "Папка ресурспаков",
                    lambda: open_folder(os.path.join(P.game, "resourcepacks")), "ghost", 13)

        self.tag = None
        self.refresh_state()
        self.set_page("home")
        updater.cleanup()
        threading.Thread(target=self._update_check, daemon=True).start()
        if lic:
            self._lic_tick()
            self._lic_recheck()

    # --- обновление лаунчера ---
    def _update_check(self):
        post = self.host.post
        found = updater.check()
        if not found:
            return
        tag, url = found
        post(lambda: (setattr(self, "busy", True), self._prog_start(60.0), self.set_text("b_main", "Обновление…"),
                      self.set_text("status", f"Найдена версия {tag} — обновляю лаунчер…"), self.refresh()))
        try:
            updater.apply(url, lambda f: post(lambda: self._progress(f)))
        except Exception as e:
            err = f"Обновление не удалось: {e}"
            post(lambda: (setattr(self, "busy", False), self.set_text("pinfo", ""), self.refresh_state(),
                          self.set_text("status", err)))

    # --- состояние ---
    def go(self, k):
        self.nav = k
        self.set_page(k)

    def _set(self, k, v):
        self.cfg[k] = v
        if k == "own_mod":
            self.refresh_state()

    def _set_ram(self, v):
        self.cfg["ram"] = v
        self.set_text("v_ram", f"{v} МБ")

    def refresh_state(self):
        self.st = engine.state(self.P)
        need_menu = self.st["game"] and self.cfg["own_mod"] and (not self.st["menu"] or self.st["menu_old"])
        if not self.st["game"]:
            self.set_text("verst", "игра не установлена")
        else:
            self.set_text("verst", "Fabric • моды: %d%s" % (self.st["mods"], " • меню ✓" if self.st["menu"] else ""))
        self.set_text("v_ram", f"{self.cfg['ram']} МБ")
        names = sorted(f[:-4] for f in os.listdir(self.P.mods) if f.endswith(".jar")) if os.path.isdir(self.P.mods) else []
        self.set_text("modlist", ("Установлено: %d\n\n" % len(names)) + "\n".join("• " + n for n in names[:14])
                      if names else "Модов пока нет — нажми «Установить» на главной.")
        if not self.launch_pending and not self.game_running:
            self.set_text("b_main", ("Обновить меню" if self.st["menu"] else "Установить меню") if need_menu else ("▶  Играть" if self.st["game"] else "Установить"))
        self.refresh()

    def save(self):
        self.cfg["nick"] = self.nick.get().strip() or "Player"
        self.cfg["server"] = self.srv.get().strip()
        save_cfg(self.P, self.cfg)

    # --- действия ---
    # --- лицензия ---
    def _lic_tick(self):
        if not self._alive:
            return
        l = self.lic.left()
        col = SUB if (l is None or l > 3 * 86400) else ("#fbbf24" if l > 86400 else "#fb7185")
        self.set_text("lic_left", "Лицензия: " + lic_mod.fmt_left(l), col)
        if l is not None and l <= 0:
            return self._gate("Срок лицензии истёк", "login")
        self.host.root.after(1000, self._lic_tick)

    def _lic_recheck(self):
        if not self._alive:
            return

        def work():
            try:
                self.lic.check()
            except lic_mod.LicenseError as e:
                code, msg = e.code, str(e)
                if code in ("banned", "session"):
                    # бан удаляет сессии на сервере, поэтому «session» тоже значит «выбить»
                    self.host.post(self._kick_banned if code == "banned" else
                                   (lambda: self._kick_session(msg)))
                else:
                    self.host.post(lambda: self._gate(msg, "login"))
            except Exception:
                pass   # нет связи с сервером — играем дальше (офлайн-запас)
        threading.Thread(target=work, daemon=True).start()
        # проверяем часто и в лаунчере, и во время игры — бан должен сработать почти сразу
        self.host.root.after(15 * 1000, self._lic_recheck)

    def _kill_game(self):
        self.game_running = False
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass
            self.proc = None

    def _kick_banned(self):
        self._kill_game()
        self._gate("Вы получили блокировку", "banned")

    def _kick_session(self, msg):
        self._kill_game()
        self._gate(msg or "Сессия завершена — войди заново", "login")

    def _gate(self, note="", mode="login"):
        if not self._alive:
            return
        if mode != "login" or "истёк" not in note:
            self.lic.logout()
        show_gate(self.host, self.P, self.lic, note, mode)

    def _logout(self):
        self.lic.logout()
        show_gate(self.host, self.P, self.lic, "Ты вышел из аккаунта", "login")

    def destroy(self):
        self._alive = False
        super().destroy()

    def on_main(self):
        if self.launch_pending:
            return self.cancel_launch()
        if self.game_running:
            return self.stop_game()
        if self.lic and not self.lic.valid():
            return self._gate("Нужна действующая лицензия", "login")
        if self.busy:
            return
        if self.st["game"] and self.cfg["own_mod"] and (not self.st["menu"] or self.st["menu_old"]):
            self.on_install(menu_only=True)
        elif self.st["game"]:
            self.start_launch()
        else:
            self.on_install()

    def start_launch(self):
        self.save()
        self.launch_pending, self.launch_cancel, self.proc, self.game_running = True, False, None, False
        self.set_text("b_main", "Отмена запуска")
        self.set_text("status", "Подготовка запуска… можно нажать ещё раз, чтобы отменить")
        self.refresh()
        post = self.host.post

        def work():
            try:
                proc = engine.launch(self.P, self.cfg, self.lic)
            except Exception as e:
                err = str(e)
                return post(lambda: self._launch_failed(err))
            post(lambda: self._launch_started(proc))
        threading.Thread(target=work, daemon=True).start()

    def _launch_started(self, proc):
        if self.launch_cancel:
            try:
                proc.terminate()
            except Exception:
                pass
            self.set_text("status", "Запуск отменён")
            engine.hide_own_mod(self.P)
            self.launch_pending = False
            self.refresh_state()
            return
        self.proc = proc
        self.game_running = True
        self.launch_pending = False
        self.set_text("b_main", "Закрыть игру")
        self.set_text("status", "Игра запускается — окно появится через несколько секунд "
                                 "(можно нажать «Закрыть игру», чтобы остановить)")
        self.refresh()
        self._game_poll()

    def _game_poll(self):
        if not self._alive or not self.game_running:
            return
        if self.proc is None or self.proc.poll() is not None:
            # процесс сам завершился (игрок вышел/вылет) — не трогаем мод, его уже убирает engine.launch
            self.proc, self.game_running = None, False
            self.set_text("status", "Игра закрыта")
            self.refresh_state()
            return
        self.host.root.after(1000, self._game_poll)

    def stop_game(self):
        self.game_running = False
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass
            self.proc = None
        self.set_text("status", "Игра закрыта")
        self.refresh_state()

    def _launch_failed(self, msg):
        self.launch_pending = False
        self.set_text("status", f"Ошибка: {msg}")
        engine.hide_own_mod(self.P)
        self.refresh_state()

    def cancel_launch(self):
        self.launch_cancel = True
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass
            self.proc = None
        self.set_text("status", "Отменяю запуск…")
        self.refresh()

    def on_install(self, menu_only=False, force=False):
        if self.busy:
            return
        self.save()
        self.busy, self.prog = True, 0.0
        self._prog_start()
        self.set_text("b_main", "Установка…")
        self.go("home")
        post = self.host.post
        ctx = Ctx(lambda m: post(lambda: self.set_text("status", m)),
                  lambda f: post(lambda: self._progress(f)),
                  lambda s: post(lambda: self.set_text("status", s)))

        def work():
            try:
                if menu_only:
                    ctx.step(0.0, 1.0)
                    engine.ensure_menu_mod(self.P, ctx)
                else:
                    engine.install_all(self.P, self.cfg, ctx, force)
            except Exception as e:
                ctx.log(f"ОШИБКА: {e}")
            post(self._done)
        threading.Thread(target=work, daemon=True).start()

    def _prog_start(self, guess=240.0):
        self.t0, self.eta, self.prog, self.guess = time.time(), None, 0.0, guess
        self._progress(0.0)

    @staticmethod
    def _fmt_eta(sec):
        m = int(round(sec / 60.0))
        return "<1 мин" if m < 1 else f"~{m} мин"

    def _progress(self, f):
        self.prog = f
        if self.t0 is None:
            self.t0, self.guess = time.time(), 240.0
        el = time.time() - self.t0
        if f >= 0.995:
            self.set_text("pinfo", "100%")
        else:
            w = min(1.0, f / 0.15)                       # чем дальше, тем больше верим измерению
            total = (1 - w) * self.guess + w * (el / f if f > 0 else self.guess)
            raw = total * (1 - f)
            self.eta = raw if self.eta is None else self.eta * 0.85 + raw * 0.15
            self.set_text("pinfo", f"{int(f * 100)}% • {self._fmt_eta(self.eta)}")
        self.refresh()

    def _done(self):
        self.busy, self.prog = False, 1.0
        self.t0, self.eta = None, None
        self.set_text("pinfo", "")
        self.refresh_state()


def show_launcher(host, P, lic):
    host.set_scene(LauncherScene(host, P, lic))


def show_gate(host, P, lic, note="", mode="login"):
    host.set_scene(GateScene(host, lic, lambda: show_launcher(host, P, lic), note, mode))


def main(root):
    P = Paths(root)
    host = Host("Sweetie Fox Launcher", W, H)
    lic = lic_mod.Lic(root)
    show_gate(host, P, lic)
    host.run()
