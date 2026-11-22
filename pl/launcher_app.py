# -*- coding: utf-8 -*-
import os, threading
from PIL import Image, ImageChops
from .common import *
from . import engine, updater
from .ui import Host, Scene
from . import license as lic_mod
from .license_ui import GateScene

W, H = 880, 620
SUB = "#c4bff0"
DIM = "#9a94d0"
OK, BAD = (134, 239, 172), (251, 113, 133)
PAGES = ["home", "versions", "set", "acc", "mods", "res", "about"]
NAV_LABELS = {
    "home": "Главная", "versions": "Версии Minecraft", "set": "Настройки",
    "acc": "Аккаунты", "mods": "Моды", "res": "Ресурспаки", "about": "О лаунчере",
}


def cover(im, w, h):
    sc = max(w / im.width, h / im.height)
    im = im.resize((int(im.width * sc) + 1, int(im.height * sc) + 1), Image.LANCZOS)
    l, t = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((l, t, l + w, t + h))


class LauncherScene(Scene):
    def __init__(self, host, P, lic=None):
        super().__init__(host)
        self.P = P
        self.lic = lic
        self._alive = True
        self.cfg = load_cfg(P)
        self.busy, self.prog = False, 0.0
        self.proc = None
        self.launch_pending = False
        self.launch_cancel = False
        engine.hide_own_mod(P)  # подчистить, если осталось с прошлого запуска
        self.st = engine.state(P)
        self.nav = "home"
        pt = self.pt

        # ---- картинки ----
        ic = pt.icon(56)
        fox = pt.asset("fox.png")
        fox = fox.resize((112, int(fox.height * 112 / fox.width)), Image.LANCZOS)
        fox.putalpha(ImageChops.multiply(fox.getchannel("A"), pt.mask(fox.width, fox.height, 18)))
        banner = cover(pt.asset("banner.png"), 612, 150)
        banner.putalpha(ImageChops.multiply(banner.getchannel("A"), pt.mask(612, 150, 20)))

        # ---- каркас ----
        self.under.append(lambda ov: pt.glass(ov, (16, 16, 864, 604), 30, 105, 16))
        self.under.append(lambda ov: pt.image(ov, ic, (40, 34)))
        self.under.append(lambda ov: pt.glass(ov, (36, 112, 212, 584), 20, 85, 12))
        self.under.append(lambda ov: pt.image(ov, fox, (68, 456)))
        self.text("brand", 108, 38, "sweetie fox", 28, True, "#ffffff")
        self.text("welcome", 110, 76, "Добро пожаловать!", 14, False, SUB)
        if lic:
            self.text("lic_user", 848, 32, "", 14, True, "#ffffff", "ne")
            self.text("lic_left", 848, 54, "", 13, False, SUB, "ne")
            self.button("b_logout", (768, 80, 848, 104), "Выйти", self._logout, "ghost", 12)
        for i, k in enumerate(PAGES):
            y = 124 + i * 46
            self.button("nav_" + k, (44, y, 204, y + 38), NAV_LABELS[k], (lambda k=k: self.go(k)),
                       "nav", 13, sel=(lambda k=k: self.nav == k))

        # ---- Главная ----
        self.tag = "home"
        self.under.append(("home", lambda ov: pt.image(ov, banner, (236, 112))))
        self.under.append(("home", lambda ov: pt.inset(ov, (236, 278, 560, 344), 18)))
        self.under.append(("home", lambda ov: pt.glass(ov, (236, 392, 848, 584), 20, 85, 12)))
        self.dot(262, 311, lambda: OK if self.st["game"] else BAD)
        self.text("ver", 282, 294, "Minecraft " + MC_VERSION, 17, True, "#ffffff")
        self.text("verst", 282, 318, "", 12, False, SUB)
        self.button("b_main", (580, 278, 848, 344), "", self.on_main, "primary", 22, lambda: not self.busy)
        self.text("status", 236, 354, "", 12, False, SUB, width=612)
        self.bar((236, 374, 848, 382), lambda: self.prog)
        self.text("nh", 258, 408, "Последние новости", 17, True, "#ffffff")
        self.text("n1", 258, 448, "Добро пожаловать в sweetie fox!", 16, True, "#ffffff")
        self.text("n2", 258, 476, "Спасибо, что выбрали наш лаунчер.\nИграйте с удовольствием ♡", 14, False, SUB, width=560)
        self.text("n3", 258, 540, "Меню в игре: Right Shift", 12, False, DIM)

        # ---- Версии ----
        self.card("versions", "Версии Minecraft")
        self.text("vv1", 262, 190, "Minecraft " + MC_VERSION + "  •  Fabric", 20, True, "#ffffff")
        self.text("vv2", 262, 226, "Поддерживается одна версия — под неё подобраны моды на FPS\n"
                  "(Sodium, Lithium, FerriteCore и др.) и меню Sweetie Fox.", 14, False, SUB, width=560)
        self.button("b_inst", (262, 330, 540, 376), "Переустановить / обновить", lambda: self.on_install(force=True), "ghost", 14,
                    lambda: not self.busy)

        # ---- Настройки ----
        self.card("set", "Настройки")
        self.text("t_ram", 262, 186, "ПАМЯТЬ", 11, True, SUB)
        self.text("v_ram", 822, 184, "", 14, True, "#ffffff", "ne")
        self.slider((262, 214, 822, 234), lambda: self.cfg["ram"], self._set_ram, 1024, 8192, 256)
        for i, (k, name, hint) in enumerate([
                ("low_mode", "Режим для слабого ПК", "минимум графики: дальность 6, без частиц и теней"),
                ("own_mod", "Sweetie Fox Menu в игре", "меню на Right Shift: основное, визуалы (звуки, ивенты), буст FPS")]):
            y = 268 + i * 56
            self.text("o_" + k, 262, y, name, 15, True, "#ffffff")
            self.text("h_" + k, 262, y + 22, hint, 12, False, DIM)
            self.switch((766, y + 4, 822, y + 30), (lambda k=k: self.cfg[k]), (lambda v, k=k: self._set(k, v)))
        self.button("b_dir", (262, 400, 540, 446), "Папка игры", lambda: open_folder(P.game), "ghost", 14)

        # ---- Аккаунты ----
        self.card("acc", "Аккаунт")
        self.text("t_nick", 262, 186, "НИК", 11, True, SUB)
        self.text("t_srv", 556, 186, "СЕРВЕР", 11, True, SUB)
        self.nick = self.entry((262, 208, 536, 246), self.cfg["nick"])
        self.srv = self.entry((556, 208, 822, 246), self.cfg["server"])
        self.text("o_aj", 262, 282, "Автовход на сервер", 15, True, "#ffffff")
        self.text("h_aj", 262, 304, "сразу подключаться к серверу из поля выше", 12, False, DIM)
        self.switch((766, 286, 822, 312), lambda: self.cfg["autojoin"], lambda v: self._set("autojoin", v))
        self.text("acc_note", 262, 360, "Вход по нику (оффлайн). Серверы с лицензионной защитой не пустят.", 13, False, DIM, width=560)

        # ---- Моды ----
        self.card("mods", "Моды")
        self.text("modlist", 262, 186, "", 13, False, SUB, width=560)
        self.button("b_mods", (262, 500, 540, 546), "Папка модов", lambda: open_folder(P.mods), "ghost", 14)

        # ---- Ресурспаки ----
        self.card("res", "Ресурспаки")
        self.text("r1", 262, 190, "Кидай ресурспаки (.zip) в папку resourcepacks —\nони появятся в настройках Minecraft.", 15, False, SUB, width=560)
        self.button("b_res", (262, 270, 540, 316), "Папка ресурспаков", lambda: open_folder(os.path.join(P.game, "resourcepacks")), "ghost", 14)

        # ---- О лаунчере ----
        self.card("about", "О лаунчере")
        self.text("a2", 262, 186, "sweetie fox launcher\n\n"
                  "• сам проверяет игру и моды: нет — скачивает, есть — не трогает\n"
                  "• моды на FPS: Sodium, Lithium, FerriteCore и другие\n"
                  "• меню в игре (Right Shift): визуал, буст FPS, градиентное меню\n"
                  "• автообновление лаунчера через GitHub", 15, False, SUB, width=560)
        self.text("a3", 262, 540, "Версия " + VERSION, 12, False, DIM)

        self.tag = None
        self.refresh_state()
        self.set_page("home")
        updater.cleanup()
        threading.Thread(target=self._update_check, daemon=True).start()
        if lic:
            self._lic_tick()
            self._lic_recheck()

    def card(self, page, title):
        self.tag = page
        pt = self.pt
        self.under.append((page, lambda ov: pt.glass(ov, (236, 112, 848, 584), 20, 85, 12)))
        self.text("h_" + page, 262, 132, title, 22, True, "#ffffff")

    # --- обновление лаунчера ---
    def _update_check(self):
        post = self.host.post
        found = updater.check()
        if not found:
            return
        tag, url = found
        post(lambda: (setattr(self, "busy", True), self.set_text("b_main", "ОБНОВЛЕНИЕ…"),
                      self.set_text("status", f"Найдена версия {tag} — обновляю лаунчер…"), self.refresh()))
        try:
            updater.apply(url, lambda f: post(lambda: self._progress(f)))
        except Exception as e:
            post(lambda: (setattr(self, "busy", False), self.refresh_state(),
                          self.set_text("status", f"Обновление не удалось: {e}")))

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
                      if names else "Модов пока нет — нажми «УСТАНОВИТЬ» на главной.")
        if not self.launch_pending:
            self.set_text("b_main", ("ОБНОВИТЬ МЕНЮ" if self.st["menu"] else "УСТАНОВИТЬ МЕНЮ") if need_menu else ("▶  ИГРАТЬ" if self.st["game"] else "УСТАНОВИТЬ"))
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
        self.set_text("lic_user", self.lic.username)
        col = SUB if (l is None or l > 3 * 86400) else ("#fbbf24" if l > 86400 else "#fb7185")
        self.set_text("lic_left", "Лицензия: " + lic_mod.fmt_left(l), col)
        if l is not None and l <= 0:
            return self._gate("Срок лицензии истёк — продли её новым ключом", "ext")
        self.host.root.after(1000, self._lic_tick)

    def _lic_recheck(self):
        if not self._alive:
            return

        def work():
            try:
                self.lic.check()
            except lic_mod.LicenseError as e:
                code = e.code
                if code == "banned":
                    self.host.post(self._kick_banned)
                else:
                    self.host.post(lambda: self._gate(str(e), "ext" if code == "expired" else "login"))
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()
        # проверяем часто и в лаунчере, и во время игры — бан должен сработать почти сразу
        self.host.root.after(15 * 1000, self._lic_recheck)

    def _kick_banned(self):
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass
            self.proc = None
        self._gate("Вы получили блокировку", "login")

    def _gate(self, note="", mode="login"):
        if not self._alive:
            return
        if mode != "ext":
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
        if self.lic and not self.lic.valid():
            return self._gate("Нужна действующая лицензия", "ext")
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
        self.launch_pending, self.launch_cancel, self.proc = True, False, None
        self.set_text("b_main", "ОТМЕНА ЗАПУСКА")
        self.set_text("status", "Подготовка запуска… можно нажать ещё раз, чтобы отменить")
        self.refresh()
        post = self.host.post

        def work():
            try:
                proc = engine.launch(self.P, self.cfg)
            except Exception as e:
                return post(lambda: self._launch_failed(str(e)))
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
        else:
            self.proc = proc
            self.set_text("status", "Игра запускается — окно появится через несколько секунд")
        self.launch_pending = False
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
        self.set_text("b_main", "УСТАНОВКА…")
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

    def _progress(self, f):
        self.prog = f
        self.refresh()

    def _done(self):
        self.busy, self.prog = False, 1.0
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
