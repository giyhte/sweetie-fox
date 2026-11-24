# -*- coding: utf-8 -*-
"""DCODE Admin — панель управления: аккаунты, роли, баланс, ключи, игроки онлайн. Дизайн как у лаунчера."""
import os, sys, json, time, queue, threading, urllib.request, urllib.error
import tkinter as tk
from tkinter import ttk

HERE = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
CFG = os.path.join(HERE, "admin_config.json")
DEFAULT = {"url": "https://kikisds.pythonanywhere.com", "username": "", "password": "", "auto": False}

BG, CARD, CARD2, LINE, FIELD = "#070410", "#0e0a20", "#171039", "#2a1f55", "#0b0819"
V1, V2, V3 = "#6d28d9", "#a855f7", "#e879f9"
TXT, SUB, DIM, BAD, GOOD, WARN = "#ffffff", "#cdbdf7", "#8b7bb8", "#fb7185", "#86efac", "#fcd34d"
FONT = "Segoe UI"
ROLE_RU = {"owner": "Владелец", "admin": "Админ", "seller": "Продавец"}
ROLE_LVL = {"seller": 1, "admin": 2, "owner": 3}


def fmt_dt(t):
    return "—" if not t else time.strftime("%d.%m.%Y %H:%M", time.localtime(t))


def fmt_exp(t):
    return "навсегда" if not t else time.strftime("%d.%m.%Y %H:%M", time.localtime(t))


def fmt_left(exp, now):
    if not exp:
        return "навсегда"
    s = exp - now
    if s <= 0:
        return "истекла"
    d, r = divmod(int(s), 86400)
    return f"{d}д {r // 3600}ч"


def fmt_ago(t, now):
    if not t:
        return "—"
    s = max(0, int(now - t))
    return f"{s} с" if s < 60 else f"{s // 60} мин" if s < 3600 else f"{s // 3600} ч" if s < 86400 else f"{s // 86400} д"


def mix(a, b, t):
    t = max(0, min(1, t))
    a, b = [int(a[i:i + 2], 16) for i in (1, 3, 5)], [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(x + (y - x) * t) for x, y in zip(a, b))


class ApiError(Exception):
    def __init__(self, msg, code="error"):
        super().__init__(msg)
        self.code = code


class Api:
    def __init__(self, cfg):
        self.cfg, self.tok = cfg, ""

    def raw(self, path, data):
        req = urllib.request.Request(self.cfg["url"].rstrip("/") + path, data=json.dumps(data).encode(),
                                     headers={"Content-Type": "application/json", "X-Panel-Token": self.tok, "User-Agent": "DCODE-Admin"})
        try:
            with urllib.request.urlopen(req, timeout=12) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            try:
                j = json.loads(e.read().decode())
            except Exception:
                raise ApiError(f"Сервер ответил {e.code}")
            raise ApiError(j.get("error", str(e)), j.get("code", "error"))
        except ApiError:
            raise
        except Exception as e:
            raise ApiError(f"Нет связи с сервером: {e}", "net")

    def call(self, path, **data):
        try:
            return self.raw(path, data)
        except ApiError as e:
            if e.code == "session" and self.cfg.get("password"):
                self.login(self.cfg["username"], self.cfg["password"])
                return self.raw(path, data)
            raise

    def login(self, u, p):
        r = self.raw("/api/panel/login", {"username": u, "password": p})
        self.tok = r["token"]
        return r

    def register(self, u, p, ref):
        r = self.raw("/api/panel/register", {"username": u, "password": p, "ref": ref})
        self.tok = r["token"]
        return r


class Btn(tk.Label):
    KINDS = {"primary": (V1, V2, TXT), "ghost": (CARD2, LINE, SUB), "danger": ("#4c1228", "#7f1d3a", BAD), "good": ("#12362a", "#1c5a43", GOOD)}

    def __init__(self, parent, text, cmd=None, kind="primary", w=None, size=10, **kw):
        self.bg, self.hv, fg = self.KINDS[kind]
        super().__init__(parent, text=text, bg=self.bg, fg=fg, font=(FONT, size, "bold"), cursor="hand2", padx=14, pady=7, width=w or 0, **kw)
        self.cmd = cmd
        self.bind("<Enter>", lambda e: self.config(bg=self.hv))
        self.bind("<Leave>", lambda e: self.config(bg=self.bg))
        self.bind("<Button-1>", lambda e: self.cmd and self.cmd())


class Field(tk.Frame):
    def __init__(self, parent, var=None, width=24, show=""):
        super().__init__(parent, bg=LINE, padx=1, pady=1)
        self.e = tk.Entry(self, textvariable=var, width=width, show=show, bg=FIELD, fg=TXT, insertbackground=TXT, relief="flat", font=(FONT, 11))
        self.e.pack(fill="x", ipady=6, ipadx=6)
        self.e.bind("<FocusIn>", lambda e: self.config(bg=V2))
        self.e.bind("<FocusOut>", lambda e: self.config(bg=LINE))


def lab(parent, text, color=SUB, size=10, bold=False, **kw):
    return tk.Label(parent, text=text, bg=kw.pop("bg", parent["bg"]), fg=color, font=(FONT, size, "bold" if bold else "normal"), **kw)


def card(parent, **kw):
    return tk.Frame(parent, bg=CARD, highlightbackground=LINE, highlightthickness=1, **kw)


class Chips(tk.Frame):
    def __init__(self, parent, items, value, cmd):
        super().__init__(parent, bg=parent["bg"])
        self.cmd, self.val, self.b = cmd, value, {}
        for k, t in items:
            b = tk.Label(self, text=t, font=(FONT, 10, "bold"), padx=12, pady=5, cursor="hand2")
            b.pack(side="left", padx=(0, 6))
            b.bind("<Button-1>", lambda e, k=k: self.set(k, True))
            self.b[k] = b
        self.set(value, False)

    def set(self, k, fire):
        self.val = k
        for kk, b in self.b.items():
            b.config(bg=V1 if kk == k else CARD2, fg=TXT if kk == k else SUB)
        if fire:
            self.cmd(k)


class Table(tk.Frame):
    def __init__(self, parent, app, cols, height=12):
        super().__init__(parent, bg=CARD, highlightbackground=LINE, highlightthickness=1)
        self.app, self.cols = app, cols
        self.t = ttk.Treeview(self, columns=[c[0] for c in cols], show="headings", height=height)
        for cid, title, w in cols:
            self.t.heading(cid, text=title)
            self.t.column(cid, width=w, minwidth=40, anchor="w")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.t.yview)
        self.t.configure(yscrollcommand=sb.set)
        self.t.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for tag, col in (("game", GOOD), ("on", "#bde7ff"), ("ban", BAD), ("off", DIM), ("warn", WARN), ("ok", TXT)):
            self.t.tag_configure(tag, foreground=col)
        m = tk.Menu(app.root, tearoff=0, bg=CARD2, fg=TXT, activebackground=V1, activeforeground=TXT, bd=0)
        m.add_command(label="Копировать строку", command=self.copy_row)
        m.add_command(label="Копировать ячейку", command=self.copy_cell)
        m.add_command(label="Копировать всю таблицу", command=self.copy_all)
        self.last_col = "#1"

        def pop(e):
            i = self.t.identify_row(e.y)
            if i and i not in self.t.selection():
                self.t.selection_set(i)
            self.last_col = self.t.identify_column(e.x)
            m.tk_popup(e.x_root, e.y_root)
        self.t.bind("<Button-3>", pop)
        self.t.bind("<Control-c>", lambda e: self.copy_row())

    def fill(self, rows):
        keep = set(self.t.selection())
        self.t.delete(*self.t.get_children())
        for iid, vals, tag in rows:
            self.t.insert("", "end", iid=iid, values=vals, tags=(tag,))
        ok = [i for i in keep if self.t.exists(i)]
        if ok:
            self.t.selection_set(ok)

    def sel(self):
        return list(self.t.selection())

    def vals(self, iid):
        return self.t.item(iid)["values"]

    def copy_row(self):
        self.app.clip("\n".join("\t".join(str(v) for v in self.vals(i)) for i in self.sel()))

    def copy_cell(self):
        s = self.sel()
        if s:
            try:
                self.app.clip(str(self.vals(s[0])[int(self.last_col[1:]) - 1]))
            except Exception:
                self.copy_row()

    def copy_all(self):
        rows = ["\t".join(c[1] for c in self.cols)] + ["\t".join(str(v) for v in self.vals(i)) for i in self.t.get_children()]
        self.app.clip("\n".join(rows))


class App:
    def __init__(self):
        try:
            with open(CFG, encoding="utf-8") as f:
                self.cfg = {**DEFAULT, **json.load(f)}
        except Exception:
            self.cfg = dict(DEFAULT)
        self.cfg.pop("token", None)
        self.cfg["url"] = self.cfg["url"].rstrip("/")
        self.api = Api(self.cfg)
        self.me, self.off, self.q = None, 0, queue.Queue()
        self.users, self.pl_filter = [], "all"
        self.root = tk.Tk()
        self.root.title("DCODE Admin")
        self.root.geometry("1200x740")
        self.root.minsize(1060, 660)
        self.root.configure(bg=BG)
        for ic in (os.path.join(HERE, "icon.ico"), os.path.join(HERE, "..", "assets", "icon.ico")):
            try:
                if os.path.exists(ic):
                    self.root.iconbitmap(ic)
                    break
            except Exception:
                pass
        self.logo = None
        try:
            from PIL import Image, ImageTk
            p = next(x for x in (os.path.join(HERE, "icon.png"), os.path.join(HERE, "..", "assets", "icon.png")) if os.path.exists(x))
            self.logo = ImageTk.PhotoImage(Image.open(p).convert("RGBA").resize((40, 40)))
        except Exception:
            pass
        self.style()
        self.pages, self.cur, self.timer = {}, None, None
        self.root.after(40, self.pump)
        self.login_screen(auto=bool(self.cfg.get("auto") and self.cfg.get("username") and self.cfg.get("password")))
        self.root.mainloop()

    def style(self):
        st = ttk.Style()
        st.theme_use("clam")
        st.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=TXT, rowheight=30, borderwidth=0, font=(FONT, 10))
        st.configure("Treeview.Heading", background=CARD2, foreground=SUB, relief="flat", font=(FONT, 10, "bold"), padding=(8, 7))
        st.map("Treeview", background=[("selected", V1)], foreground=[("selected", TXT)])
        st.map("Treeview.Heading", background=[("active", LINE)])
        st.configure("Vertical.TScrollbar", background=LINE, troughcolor=CARD, bordercolor=CARD, arrowcolor=SUB, relief="flat")

    def clip(self, t):
        self.root.clipboard_clear()
        self.root.clipboard_append(t)
        self.toast("Скопировано", GOOD)

    def pump(self):
        try:
            while True:
                self.q.get_nowait()()
        except queue.Empty:
            pass
        self.root.after(40, self.pump)

    def bg(self, work, ok=None, err=None):
        def run():
            try:
                r = work()
                self.q.put(lambda: ok and ok(r))
            except ApiError as e:
                self.q.put(lambda e=e: (err or self.fail)(e))
            except Exception as e:
                self.q.put(lambda e=e: (err or self.fail)(ApiError(str(e))))
        threading.Thread(target=run, daemon=True).start()

    def fail(self, e):
        if getattr(e, "code", "") == "session":
            return self.login_screen()
        self.toast(str(e), BAD)

    def toast(self, text, color=SUB):
        t = getattr(self, "toast_l", None)
        try:
            if not t or not t.winfo_exists():
                return
            t.config(text=text, fg=color)
            if getattr(self, "toast_id", None):
                self.root.after_cancel(self.toast_id)
            self.toast_id = self.root.after(4500, lambda: t.winfo_exists() and t.config(text=""))
        except Exception:
            pass

    def clear(self):
        if self.timer:
            self.root.after_cancel(self.timer)
            self.timer = None
        for w in self.root.winfo_children():
            w.destroy()
        self.pages, self.cur = {}, None

    def gradient(self, parent, h=3):
        c = tk.Canvas(parent, height=h, bg=BG, highlightthickness=0)

        def draw(e):
            c.delete("all")
            for x in range(0, e.width, 4):
                t = x / max(1, e.width)
                c.create_rectangle(x, 0, x + 4, h, fill=mix(V1, V3, t * 2) if t < .5 else mix(V3, V2, (t - .5) * 2), width=0)
        c.bind("<Configure>", draw)
        return c

    def ask(self, title, fields=(), text="", ok="Готово", kind="primary"):
        d = tk.Toplevel(self.root)
        d.title(title)
        d.configure(bg=BG)
        d.transient(self.root)
        d.resizable(False, False)
        box = card(d)
        box.pack(padx=14, pady=14)
        body = tk.Frame(box, bg=CARD)
        body.pack(padx=22, pady=18)
        lab(body, title, TXT, 14, True).pack(anchor="w")
        if text:
            lab(body, text, SUB, 10, wraplength=360, justify="left").pack(anchor="w", pady=(6, 0))
        vars_, first = {}, None
        for key, label, default, typ in fields:
            lab(body, label, DIM, 9).pack(anchor="w", pady=(12, 3))
            if typ.startswith("choice:"):
                opts = [(o, ROLE_RU.get(o, o)) for o in typ[7:].split("|")]
                v = tk.StringVar(value=default or opts[0][0])
                Chips(body, opts, v.get(), v.set).pack(anchor="w")
            else:
                v = tk.StringVar(value=str(default))
                f = Field(body, v, 34, "•" if typ == "pass" else "")
                f.pack(fill="x")
                first = first or f.e
            vars_[key] = (v, typ)
        res = {}
        err = lab(body, "", BAD, 9)
        err.pack(anchor="w", pady=(8, 0))

        def done(_=None):
            out = {}
            for k, (v, typ) in vars_.items():
                s = v.get() if typ == "pass" else v.get().strip()
                if typ == "int":
                    try:
                        s = int(s)
                    except ValueError:
                        return err.config(text="Нужно число")
                out[k] = s
            res["v"] = out
            d.destroy()
        row = tk.Frame(body, bg=CARD)
        row.pack(fill="x", pady=(10, 0))
        Btn(row, ok, done, kind).pack(side="right")
        Btn(row, "Отмена", d.destroy, "ghost").pack(side="right", padx=8)
        d.bind("<Return>", done)
        d.bind("<Escape>", lambda e: d.destroy())
        d.update_idletasks()
        d.geometry(f"+{self.root.winfo_x() + (self.root.winfo_width() - d.winfo_width()) // 2}+{self.root.winfo_y() + 140}")
        d.grab_set()
        (first or d).focus_set()
        self.root.wait_window(d)
        return res.get("v")

    def login_screen(self, auto=False):
        self.clear()
        self.gradient(self.root, 4).pack(fill="x")
        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(expand=True)
        box = card(wrap)
        box.pack()
        f = tk.Frame(box, bg=CARD)
        f.pack(padx=34, pady=28)
        if self.logo:
            tk.Label(f, image=self.logo, bg=CARD).pack()
        lab(f, "DCODE ADMIN", TXT, 20, True).pack(pady=(6, 0))
        lab(f, "панель управления лицензиями", DIM, 10).pack(pady=(0, 14))
        mode = tk.StringVar(value="login")
        u, p, p2, ref = tk.StringVar(value=self.cfg.get("username", "")), tk.StringVar(value=self.cfg.get("password", "")), tk.StringVar(), tk.StringVar()
        srv = tk.StringVar(value=self.cfg["url"])
        form = tk.Frame(f, bg=CARD)
        msg = lab(f, "", BAD, 10, wraplength=320)
        btn_holder = tk.Frame(f, bg=CARD)

        def go(_=None):
            self.cfg["url"] = srv.get().strip().rstrip("/") or DEFAULT["url"]
            un, pw = u.get().strip(), p.get()
            if not un or not pw:
                return msg.config(text="Введи логин и пароль", fg=BAD)
            if mode.get() == "reg":
                if pw != p2.get():
                    return msg.config(text="Пароли не совпадают", fg=BAD)
                if not ref.get().strip():
                    return msg.config(text="Нужен реф-код от того, кто тебя приглашает", fg=BAD)
            msg.config(text="Подключение…", fg=SUB)
            fn = (lambda: self.api.register(un, pw, ref.get().strip())) if mode.get() == "reg" else (lambda: self.api.login(un, pw))

            def ok(r):
                self.cfg.update(username=un, password=pw, auto=True)
                self.save()
                self.me = r
                self.off = r["server_time"] - time.time()
                self.main_screen()
            self.bg(fn, ok, lambda e: msg.config(text=str(e), fg=BAD))

        def build(m):
            for w in form.winfo_children():
                w.destroy()
            rows = [("Логин", u, ""), ("Пароль", p, "•")]
            if m == "reg":
                rows += [("Повтори пароль", p2, "•"), ("Реф-код приглашения", ref, "")]
            for t, v, s in rows:
                lab(form, t, DIM, 9).pack(anchor="w", pady=(10, 3))
                Field(form, v, 34, s).pack(fill="x")
            lab(form, "Сервер", DIM, 9).pack(anchor="w", pady=(10, 3))
            Field(form, srv, 34).pack(fill="x")
            for w in btn_holder.winfo_children():
                w.destroy()
            Btn(btn_holder, "Войти" if m == "login" else "Создать аккаунт", go, w=30).pack(fill="x")

        Chips(f, [("login", "Вход"), ("reg", "Регистрация")], "login", lambda k: (mode.set(k), build(k), msg.config(text=""))).pack(anchor="w")
        form.pack(fill="x")
        msg.pack(anchor="w", pady=(10, 0))
        btn_holder.pack(fill="x", pady=(12, 0))
        build("login")
        self.root.bind("<Return>", go)
        if auto:
            go()

    def save(self):
        try:
            with open(CFG, "w", encoding="utf-8") as f:
                json.dump({k: self.cfg[k] for k in ("url", "username", "password", "auto") if k in self.cfg}, f, ensure_ascii=False)
        except Exception:
            pass

    def logout(self):
        self.cfg.update(password="", auto=False)
        self.save()
        self.api.tok = ""
        self.login_screen()

    def lvl(self):
        return ROLE_LVL[self.me["role"]]

    def main_screen(self):
        self.clear()
        self.root.unbind("<Return>")
        lvl = self.lvl()
        side = tk.Frame(self.root, bg=CARD, width=210, highlightbackground=LINE, highlightthickness=1)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        head = tk.Frame(side, bg=CARD)
        head.pack(fill="x", padx=16, pady=(18, 14))
        if self.logo:
            tk.Label(head, image=self.logo, bg=CARD).pack(side="left")
        t = tk.Frame(head, bg=CARD)
        t.pack(side="left", padx=10)
        lab(t, "DCODE", TXT, 15, True).pack(anchor="w")
        lab(t, "admin panel", DIM, 9).pack(anchor="w")
        self.nav = {}
        for k, title, need in (("keys", "Ключи", 1), ("players", "Игроки", 1), ("staff", "Персонал", 3), ("tx", "Баланс и история", 1),
                               ("profile", "Профиль и рефка", 1), ("settings", "Настройки", 3)):
            if lvl < need:
                continue
            r = tk.Frame(side, bg=CARD, cursor="hand2")
            r.pack(fill="x", padx=10, pady=2)
            bar = tk.Frame(r, bg=CARD, width=3)
            bar.pack(side="left", fill="y")
            l = tk.Label(r, text=title, bg=CARD, fg=SUB, font=(FONT, 11, "bold"), anchor="w", padx=12, pady=9)
            l.pack(side="left", fill="x", expand=True)
            for w in (r, l):
                w.bind("<Button-1>", lambda e, k=k: self.show(k))
            self.nav[k] = (r, bar, l)
        foot = tk.Frame(side, bg=CARD)
        foot.pack(side="bottom", fill="x", padx=16, pady=16)
        self.u_name = lab(foot, "", TXT, 11, True)
        self.u_name.pack(anchor="w")
        self.u_role = lab(foot, "", V3, 9, True)
        self.u_role.pack(anchor="w")
        Btn(foot, "Выйти", self.logout, "ghost").pack(fill="x", pady=(10, 0))
        right = tk.Frame(self.root, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        self.gradient(right, 3).pack(fill="x")
        top = tk.Frame(right, bg=BG)
        top.pack(fill="x", padx=22, pady=(14, 4))
        self.title_l = lab(top, "", TXT, 18, True)
        self.title_l.pack(side="left")
        self.bal_l = tk.Label(top, bg=CARD2, fg=GOOD, font=(FONT, 11, "bold"), padx=14, pady=6)
        self.bal_l.pack(side="right")
        self.dot = lab(top, "● подключено", GOOD, 10)
        self.dot.pack(side="right", padx=14)
        self.toast_l = lab(right, "", SUB, 10)
        self.toast_l.pack(anchor="w", padx=22)
        self.body = tk.Frame(right, bg=BG)
        self.body.pack(fill="both", expand=True, padx=22, pady=(6, 18))
        self.header()
        self.show("keys")
        self.tick()

    def header(self):
        m = self.me
        self.u_name.config(text=m["username"])
        self.u_role.config(text=ROLE_RU.get(m["role"], m["role"]).upper())
        self.bal_l.config(text="∞ безлимит" if m["role"] == "owner" else f"💰 {m['balance']}")

    def tick(self):
        def ok(r):
            self.me.update(r)
            self.header()
            self.dot.config(text="● подключено", fg=GOOD)

        def err(e):
            if e.code == "session":
                return self.login_screen()
            self.dot.config(text="● нет связи", fg=BAD)
        self.bg(lambda: self.api.call("/api/panel/me"), ok, err)
        if self.cur == "players" and self.pl_auto.get():
            self.pl_load(True)
        self.timer = self.root.after(8000, self.tick)

    def show(self, k):
        if self.cur:
            self.pages[self.cur].pack_forget()
            r, bar, l = self.nav[self.cur]
            r.config(bg=CARD), bar.config(bg=CARD), l.config(bg=CARD, fg=SUB)
        if k not in self.pages:
            f = tk.Frame(self.body, bg=BG)
            self.pages[k] = f
            getattr(self, "build_" + k)(f)
        self.cur = k
        self.pages[k].pack(fill="both", expand=True)
        r, bar, l = self.nav[k]
        r.config(bg=CARD2), bar.config(bg=V2), l.config(bg=CARD2, fg=TXT)
        self.title_l.config(text={"keys": "Ключи лицензий", "players": "Игроки", "staff": "Персонал", "tx": "Баланс и история",
                                  "profile": "Профиль и реф-код", "settings": "Настройки"}[k])
        getattr(self, "load_" + k)()

    # ---------------- КЛЮЧИ
    def build_keys(self, f):
        box = card(f)
        box.pack(fill="x")
        b = tk.Frame(box, bg=CARD)
        b.pack(fill="x", padx=18, pady=14)
        self.k_days, self.k_uses, self.k_cnt, self.k_note = tk.StringVar(value="30"), tk.StringVar(value="1"), tk.StringVar(value="1"), tk.StringVar()
        lab(b, "Срок", DIM, 9).grid(row=0, column=0, sticky="w")
        self.k_chips = Chips(b, [("1", "1 д"), ("7", "7 д"), ("30", "30 д"), ("90", "90 д"), ("0", "Навсегда")], "30", lambda k: self.k_days.set(k))
        self.k_chips.grid(row=1, column=0, sticky="w", padx=(0, 18))
        for i, (t, v, w) in enumerate((("Дней (0 = навсегда)", self.k_days, 9), ("Активаций на ключ", self.k_uses, 7),
                                       ("Сколько ключей", self.k_cnt, 7), ("Заметка", self.k_note, 20)), 1):
            lab(b, t, DIM, 9).grid(row=0, column=i, sticky="w", padx=(0, 10))
            Field(b, v, w).grid(row=1, column=i, padx=(0, 10), sticky="w")
        self.cost_l = lab(b, "", SUB, 10, bold=True)
        self.cost_l.grid(row=2, column=0, columnspan=3, sticky="w", pady=(12, 0))
        Btn(b, "Создать ключи", self.k_create).grid(row=2, column=3, columnspan=2, sticky="e", pady=(12, 0))
        for v in (self.k_days, self.k_uses, self.k_cnt):
            v.trace_add("write", lambda *a: self.k_cost())
        self.k_cost()
        out = tk.Frame(f, bg=BG)
        out.pack(fill="x", pady=10)
        self.k_out = tk.Text(out, height=3, bg=FIELD, fg=GOOD, relief="flat", font=("Consolas", 11), highlightbackground=LINE, highlightthickness=1, insertbackground=TXT)
        self.k_out.pack(side="left", fill="x", expand=True)
        Btn(out, "Копировать новые", lambda: self.clip(self.k_out.get("1.0", "end").strip()), "ghost").pack(side="left", padx=(10, 0), fill="y")
        bar = tk.Frame(f, bg=BG)
        bar.pack(fill="x", pady=(0, 8))
        for t, fn, kd in (("Копировать выбранные", self.k_copy, "ghost"), ("Отозвать", lambda: self.k_act("/api/panel/revoke"), "ghost"),
                          ("Вернуть", lambda: self.k_act("/api/panel/revoke", undo=True), "ghost"), ("Удалить", self.k_del, "danger")):
            Btn(bar, t, fn, kd).pack(side="left", padx=(0, 8))
        Btn(bar, "Обновить", self.load_keys, "ghost").pack(side="right")
        self.k_tbl = Table(f, self, [("key", "Ключ", 210), ("days", "Срок", 80), ("uses", "Использовано", 100), ("state", "Статус", 90),
                                     ("owner", "Создал", 120), ("note", "Заметка", 200), ("created", "Создан", 130)])
        self.k_tbl.pack(fill="both", expand=True)

    def k_days_val(self):
        try:
            return max(0, int(self.k_days.get() or 0))
        except ValueError:
            return 0

    def k_cost(self):
        m = self.me
        try:
            n, mu = max(1, int(self.k_cnt.get() or 1)), max(1, int(self.k_uses.get() or 1))
        except ValueError:
            return
        d = self.k_days_val()
        if m["role"] == "owner":
            return self.cost_l.config(text="Владелец создаёт ключи бесплатно", fg=GOOD)
        cost = n * mu * (m["price_forever"] if d == 0 else d * m["price_day"])
        ok = m["balance"] >= cost
        self.cost_l.config(text=f"Стоимость: {cost}   •   на балансе: {m['balance']}" + ("" if ok else "   — не хватает"), fg=GOOD if ok else BAD)

    def k_create(self):
        try:
            cnt, uses = int(self.k_cnt.get() or 1), int(self.k_uses.get() or 1)
        except ValueError:
            return self.toast("Числа введены неверно", BAD)
        days, note = self.k_days_val(), self.k_note.get()

        def ok(r):
            self.k_out.delete("1.0", "end")
            self.k_out.insert("end", "\n".join(r["keys"]))
            self.me["balance"] = r["balance"]
            self.header(), self.k_cost(), self.load_keys()
            self.toast(f"Создано ключей: {len(r['keys'])}" + (f" · списано {r['cost']}" if r["cost"] else ""), GOOD)
        self.bg(lambda: self.api.call("/api/panel/create", count=cnt, days=days, max_uses=uses, note=note), ok)

    def k_sel(self):
        return [self.k_tbl.vals(i)[0] for i in self.k_tbl.sel()]

    def k_copy(self):
        if self.k_sel():
            self.clip("\n".join(self.k_sel()))

    def k_act(self, path, **kw):
        ks = self.k_sel()
        if ks:
            self.bg(lambda: [self.api.call(path, key=k, **kw) for k in ks], lambda r: self.load_keys())

    def k_del(self):
        if self.k_sel() and self.ask("Удалить ключи?", text=f"Будет удалено ключей: {len(self.k_sel())}. Деньги не возвращаются.", ok="Удалить", kind="danger") is not None:
            self.k_act("/api/panel/delkey")

    def load_keys(self):
        def ok(r):
            rows = []
            for k in r["keys"]:
                st = "отозван" if k["revoked"] else ("исчерпан" if k["max_uses"] and k["uses"] >= k["max_uses"] else "активен")
                rows.append((k["key"], (k["key"], "навсегда" if k["days"] == 0 else f'{k["days"]} дн.', f'{k["uses"]}/{k["max_uses"] or "∞"}',
                                        st, k.get("owner") or "—", k["note"], fmt_dt(k["created"])), "ok" if st == "активен" else "off"))
            self.k_tbl.fill(rows)
        self.bg(lambda: self.api.call("/api/panel/keys"), ok)

    # ---------------- ИГРОКИ
    def build_players(self, f):
        self.pl_q, self.pl_auto = tk.StringVar(), tk.BooleanVar(value=True)
        top = tk.Frame(f, bg=BG)
        top.pack(fill="x")
        Field(top, self.pl_q, 26).pack(side="left")
        self.pl_q.trace_add("write", lambda *a: self.pl_render())
        Chips(top, [("all", "Все"), ("game", "В игре"), ("on", "Онлайн"), ("ban", "Баны")], "all",
              lambda k: (setattr(self, "pl_filter", k), self.pl_render())).pack(side="left", padx=14)
        self.pl_cnt = lab(top, "", DIM, 10)
        self.pl_cnt.pack(side="left")
        Btn(top, "Обновить", self.pl_load, "ghost").pack(side="right")
        tk.Checkbutton(top, text="авто (8 с)", variable=self.pl_auto, bg=BG, fg=SUB, selectcolor=CARD2, activebackground=BG,
                       activeforeground=TXT, font=(FONT, 10), bd=0, highlightthickness=0).pack(side="right", padx=12)
        if self.lvl() >= 2:
            act = card(f)
            act.pack(fill="x", pady=10)
            a = tk.Frame(act, bg=CARD)
            a.pack(fill="x", padx=12, pady=10)
            lab(a, "Действия над выбранными (работают и в игре):", DIM, 9).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 6))
            acts = [("✉ Сообщение", self.pl_msg, "primary"), ("⏏ Кик из игры", self.pl_kick, "danger"), ("⛔ Бан", self.pl_ban, "danger"),
                    ("Разбан", self.pl_unban, "good"), ("+ Дни", self.pl_extend, "ghost"), ("∞ Навсегда", self.pl_forever, "ghost"),
                    ("Сброс привязки", self.pl_reset, "ghost"), ("Выкинуть из аккаунта", self.pl_logout, "ghost"),
                    ("Заметка", self.pl_note, "ghost"), ("Сменить пароль", self.pl_pw, "ghost"), ("Удалить", self.pl_del, "danger"),
                    ("📢 Всем онлайн", self.pl_broadcast, "primary"), ("⏏ Кикнуть всех в игре", self.pl_kick_all, "danger"),
                    ("⛔ Бан + кик", self.pl_ban_kick, "danger")]
            for i, (t, fn, kd) in enumerate(acts):
                Btn(a, t, fn, kd, size=9).grid(row=1 + i // 6, column=i % 6, padx=(0, 8), pady=3, sticky="ew")
        else:
            lab(f, "Режим просмотра: управление игроками доступно админам и владельцу.", DIM, 10).pack(anchor="w", pady=8)
        self.pl_tbl = Table(f, self, [("st", "Статус", 90), ("user", "Логин", 110), ("nick", "Ник в игре", 110), ("left", "Осталось", 80),
                                      ("until", "До", 120), ("seen", "Сеть", 80), ("pc", "ПК", 70), ("ph", "Телефон", 70),
                                      ("key", "Ключ", 150), ("note", "Заметка", 150)], height=10)
        self.pl_tbl.pack(fill="both", expand=True)
        self.pl_tbl.t.bind("<<TreeviewSelect>>", lambda e: self.pl_detail())
        self.pl_det = lab(f, "", SUB, 10, wraplength=900, justify="left")
        self.pl_det.pack(anchor="w", pady=(8, 0))

    def load_players(self):
        self.pl_load()

    def pl_load(self, quiet=False):
        def ok(r):
            self.users, self.off = r["users"], r["server_time"] - time.time()
            self.pl_render()
        self.bg(lambda: self.api.call("/api/panel/users"), ok, (lambda e: None) if quiet else None)

    def u_state(self, u, now):
        on = u.get("last_seen") and now - u["last_seen"] <= 45
        return "ban" if u["banned"] else ("game" if on and u.get("playing") else ("on" if on else "off"))

    def pl_render(self):
        if self.cur != "players":
            return
        now, q = time.time() + self.off, self.pl_q.get().strip().lower()
        rank, names = {"game": 0, "on": 1, "off": 2, "ban": 3}, {"game": "В ИГРЕ", "on": "в лаунчере", "off": "офлайн", "ban": "БАН"}
        rows, cnt = [], {"game": 0, "on": 0}
        for u in self.users:
            st = self.u_state(u, now)
            if st in cnt:
                cnt[st] += 1
            if (self.pl_filter == "game" and st != "game") or (self.pl_filter == "on" and st not in ("game", "on")) or (self.pl_filter == "ban" and st != "ban"):
                continue
            if q and q not in " ".join(str(u.get(k) or "") for k in ("username", "game_nick", "key_used", "note", "last_ip")).lower():
                continue
            rows.append((rank[st], u["username"].lower(), (u["username"], (names[st], u["username"], u.get("game_nick") or "—", fmt_left(u["expires"], now),
                         fmt_exp(u["expires"]), fmt_ago(u.get("last_seen"), now) if st in ("game", "on") else fmt_dt(u["last_login"]),
                         (u["hwid"] or "—")[:8], (u.get("hwid_android") or "—")[:8], u["key_used"], u.get("note") or ""), st)))
        rows.sort(key=lambda r: (r[0], r[1]))
        self.pl_tbl.fill([r[2] for r in rows])
        self.pl_cnt.config(text=f"всего {len(self.users)}  ·  в игре {cnt['game']}  ·  онлайн {cnt['game'] + cnt['on']}")
        self.pl_detail()

    def pl_detail(self):
        s = self.pl_tbl.sel()
        if not s:
            return self.pl_det.config(text="Выбери игрока, чтобы увидеть детали. Правая кнопка мыши — копирование. Ctrl/Shift — выбрать несколько.")
        u = next((x for x in self.users if x["username"] == s[0]), None)
        if u:
            self.pl_det.config(text=f"{u['username']}  ·  IP: {u.get('last_ip') or '—'}  ·  ключ: {u['key_used']}  ·  регистрация: {fmt_dt(u['created'])}  ·  "
                                    f"ПК: {u['hwid'] or '—'}  ·  телефон: {u.get('hwid_android') or '—'}"
                                    + (f"  ·  причина бана: {u['ban_reason']}" if u.get("ban_reason") else "") + (f"  ·  заметка: {u['note']}" if u.get("note") else ""))

    def pl_do(self, path, label="Готово", names=None, **kw):
        names = names or self.pl_tbl.sel()
        if not names:
            return self.toast("Сначала выбери игроков в таблице", WARN)
        self.bg(lambda: [self.api.call(path, username=n, **kw) for n in names],
                lambda r: (self.toast(f"{label}: {len(names)}", GOOD), self.pl_load(True)))

    def pl_need(self):
        if not self.pl_tbl.sel():
            self.toast("Сначала выбери игроков в таблице", WARN)
            return False
        return True

    def live(self, game_only=False):
        now = time.time() + self.off
        return [u["username"] for u in self.users if self.u_state(u, now) in (("game",) if game_only else ("game", "on"))]

    def pl_msg(self):
        if self.pl_need() and (r := self.ask("Сообщение игроку", [("m", "Текст (увидит в лаунчере и в чате игры)", "", "text")], ok="Отправить")) and r["m"]:
            self.pl_do("/api/panel/message", "Сообщение отправлено", message=r["m"])

    def pl_kick(self):
        if self.pl_need() and (r := self.ask("Кик из игры", [("m", "Причина (покажем игроку)", "", "text")], ok="Кикнуть", kind="danger")) is not None:
            self.pl_do("/api/panel/kick", "Кикнуто", message=r["m"])

    def pl_kick_all(self):
        live = self.live(True)
        if not live:
            return self.toast("Сейчас никого нет в игре", WARN)
        r = self.ask("Кикнуть всех в игре", [("m", "Причина", "Технические работы", "text")], text=f"Будет закрыта игра у {len(live)} чел.", ok="Кикнуть", kind="danger")
        if r is not None:
            self.pl_do("/api/panel/kick", "Кикнуто", names=live, message=r["m"])

    def pl_ban(self):
        if self.pl_need() and (r := self.ask("Бан", [("m", "Причина", "Нарушение правил", "text")], text="Лаунчер закроет игру, вход будет закрыт.", ok="Забанить", kind="danger")) is not None:
            self.pl_do("/api/panel/ban", "Забанено", banned=True, reason=r["m"])

    def pl_ban_kick(self):
        if self.pl_need() and (r := self.ask("Бан + мгновенный кик", [("m", "Причина", "Нарушение правил", "text")], ok="Забанить", kind="danger")) is not None:
            names = self.pl_tbl.sel()
            self.bg(lambda: [(self.api.call("/api/panel/kick", username=n, message=r["m"]), self.api.call("/api/panel/ban", username=n, banned=True, reason=r["m"])) for n in names],
                    lambda _: (self.toast(f"Забанено и кикнуто: {len(names)}", GOOD), self.pl_load(True)))

    def pl_unban(self):
        if self.pl_need():
            self.pl_do("/api/panel/ban", "Разбанено", banned=False)

    def pl_extend(self):
        if self.pl_need() and (r := self.ask("Продлить лицензию", [("d", "Сколько дней добавить", 30, "int")], ok="Продлить")):
            self.pl_do("/api/panel/extend", "Продлено", days=r["d"])

    def pl_forever(self):
        if self.pl_need() and self.ask("Лицензия навсегда?", text="Выбранным игрокам будет выдан бессрочный доступ.", ok="Выдать") is not None:
            self.pl_do("/api/panel/extend", "Выдано навсегда", forever=True)

    def pl_reset(self):
        if self.pl_need() and self.ask("Сбросить привязку?", text="Сбросятся привязки к ПК и телефону — игрок сможет войти с нового устройства.", ok="Сбросить") is not None:
            self.pl_do("/api/panel/reset_hwid", "Привязка сброшена")

    def pl_logout(self):
        if self.pl_need() and self.ask("Выкинуть из аккаунта?", text="Сессия закроется, лаунчер потребует войти заново.", ok="Выкинуть") is not None:
            self.pl_do("/api/panel/logout", "Сессия закрыта")

    def pl_note(self):
        s = self.pl_tbl.sel()
        if not s:
            return self.toast("Сначала выбери игрока", WARN)
        old = next((u.get("note") or "" for u in self.users if u["username"] == s[0]), "")
        if (r := self.ask("Заметка", [("n", "Текст заметки", old, "text")])) is not None:
            self.pl_do("/api/panel/note", "Заметка сохранена", note=r["n"])

    def pl_pw(self):
        if self.pl_need() and (r := self.ask("Новый пароль игроку", [("p", "Пароль (6–64 символа)", "", "pass")], ok="Сменить")):
            self.pl_do("/api/panel/setuserpw", "Пароль изменён", password=r["p"])

    def pl_del(self):
        if self.pl_need() and self.ask("Удалить игроков?", text="Аккаунты будут удалены безвозвратно.", ok="Удалить", kind="danger") is not None:
            self.pl_do("/api/panel/deluser", "Удалено")

    def pl_broadcast(self):
        live = self.live()
        if not live:
            return self.toast("Сейчас никого нет в сети", WARN)
        r = self.ask("Сообщение всем онлайн", [("m", "Текст", "", "text")], text=f"Получат: {len(live)} чел. (в игре и в лаунчере)", ok="Отправить")
        if r and r["m"]:
            self.pl_do("/api/panel/message", "Отправлено", names=live, message=r["m"])

    # ---------------- ПЕРСОНАЛ
    def build_staff(self, f):
        bar = tk.Frame(f, bg=BG)
        bar.pack(fill="x", pady=(0, 10))
        for t, fn, kd in (("Роль", self.st_role, "primary"), ("+/− Баланс", self.st_bal, "good"), ("Задать баланс", self.st_setbal, "ghost"),
                          ("Бан / разбан", self.st_ban, "danger"), ("Пароль", self.st_pw, "ghost"), ("Копировать реф-код", self.st_copyref, "ghost"),
                          ("Удалить", self.st_del, "danger")):
            Btn(bar, t, fn, kd, size=9).pack(side="left", padx=(0, 8))
        Btn(bar, "Обновить", self.load_staff, "ghost").pack(side="right")
        self.st_tbl = Table(f, self, [("u", "Логин", 130), ("role", "Роль", 90), ("bal", "Баланс", 80), ("keys", "Ключей", 70), ("inv", "Пригласил", 110),
                                      ("ref", "Реф-код", 110), ("state", "Статус", 70), ("login", "Последний вход", 130), ("created", "Регистрация", 130)])
        self.st_tbl.pack(fill="both", expand=True)
        lab(f, "Реф-код даёт право зарегистрироваться в панели. Новые сотрудники получают роль «Продавец» и стартовый баланс из настроек.", DIM, 10).pack(anchor="w", pady=8)

    def load_staff(self):
        def ok(r):
            self.st_tbl.fill([(s["username"], (s["username"], ROLE_RU.get(s["role"], s["role"]), s["balance"], s["keys_made"], s["inviter"], s["ref_code"],
                                              "БАН" if s["banned"] else "ок", fmt_dt(s["last_login"]), fmt_dt(s["created"])), "ban" if s["banned"] else "ok")
                              for s in r["staff"]])
        self.bg(lambda: self.api.call("/api/panel/staff"), ok)

    def st_one(self):
        s = self.st_tbl.sel()
        if not s:
            self.toast("Выбери сотрудника", WARN)
            return None
        return s[0]

    def st_do(self, path, label, **kw):
        self.bg(lambda: self.api.call(path, **kw), lambda r: (self.toast(label, GOOD), self.load_staff()))

    def st_role(self):
        n = self.st_one()
        if n and (r := self.ask(f"Роль: {n}", [("r", "Новая роль", "seller", "choice:seller|admin|owner")], text="Продавец — свои ключи за баланс. Админ — ещё и управление игроками. Владелец — всё.")):
            self.st_do("/api/panel/staff_role", "Роль изменена", username=n, role=r["r"])

    def st_bal(self):
        n = self.st_one()
        if n and (r := self.ask(f"Баланс: {n}", [("a", "Изменение (минус — списать)", 100, "int"), ("w", "Причина", "Пополнение", "text")], ok="Применить")):
            self.st_do("/api/panel/staff_balance", "Баланс обновлён", username=n, amount=r["a"], reason=r["w"])

    def st_setbal(self):
        n = self.st_one()
        if n and (r := self.ask(f"Задать баланс: {n}", [("a", "Новый баланс", 0, "int")], ok="Задать")):
            self.st_do("/api/panel/staff_balance", "Баланс задан", username=n, amount=r["a"], mode="set", reason="Установлено владельцем")

    def st_ban(self):
        n = self.st_one()
        if n:
            banned = self.st_tbl.vals(n)[6] != "БАН"
            self.st_do("/api/panel/staff_ban", "Заблокирован" if banned else "Разблокирован", username=n, banned=banned)

    def st_pw(self):
        n = self.st_one()
        if n and (r := self.ask(f"Пароль: {n}", [("p", "Новый пароль", "", "pass")], ok="Сменить")):
            self.st_do("/api/panel/staff_setpw", "Пароль изменён", username=n, password=r["p"])

    def st_copyref(self):
        n = self.st_one()
        if n:
            self.clip(str(self.st_tbl.vals(n)[5]))

    def st_del(self):
        n = self.st_one()
        if n and self.ask(f"Удалить {n}?", text="Аккаунт сотрудника будет удалён (ключи останутся).", ok="Удалить", kind="danger") is not None:
            self.st_do("/api/panel/staff_delete", "Удалён", username=n)

    # ---------------- ИСТОРИЯ
    def build_tx(self, f):
        bar = tk.Frame(f, bg=BG)
        bar.pack(fill="x", pady=(0, 10))
        lab(bar, "Пополнения и списания", DIM, 10).pack(side="left")
        Btn(bar, "Обновить", self.load_tx, "ghost").pack(side="right")
        self.tx_tbl = Table(f, self, [("t", "Время", 140), ("w", "Кто", 120), ("d", "Изменение", 90), ("b", "Баланс", 80), ("r", "Причина", 320), ("by", "Кем", 120)])
        self.tx_tbl.pack(fill="both", expand=True)

    def load_tx(self):
        def ok(r):
            self.tx_tbl.fill([(str(t["id"]), (fmt_dt(t["ts"]), t["who"], f"{t['delta']:+d}", t["balance"], t["reason"], t["by_name"]), "game" if t["delta"] > 0 else "ban")
                              for t in r["tx"]])
        self.bg(lambda: self.api.call("/api/panel/tx"), ok)

    # ---------------- ПРОФИЛЬ
    def build_profile(self, f):
        c = card(f)
        c.pack(fill="x")
        b = tk.Frame(c, bg=CARD)
        b.pack(fill="x", padx=22, pady=18)
        lab(b, "Твой реф-код", DIM, 9).pack(anchor="w")
        self.ref_l = lab(b, "", V3, 26, True)
        self.ref_l.pack(anchor="w", pady=(2, 6))
        lab(b, "Отправь код тому, кого хочешь пригласить: он вводит его на вкладке «Регистрация». Баланс и ключи у каждого сотрудника свои.", SUB, 10, wraplength=700, justify="left").pack(anchor="w")
        r = tk.Frame(b, bg=CARD)
        r.pack(anchor="w", pady=(12, 0))
        Btn(r, "Копировать", lambda: self.clip(self.me["ref_code"])).pack(side="left")
        Btn(r, "Сгенерировать новый", self.new_ref, "ghost").pack(side="left", padx=8)
        c2 = card(f)
        c2.pack(fill="x", pady=14)
        b2 = tk.Frame(c2, bg=CARD)
        b2.pack(fill="x", padx=22, pady=18)
        lab(b2, "Смена пароля", TXT, 12, True).pack(anchor="w")
        self.pw_old, self.pw_new = tk.StringVar(), tk.StringVar()
        row = tk.Frame(b2, bg=CARD)
        row.pack(anchor="w", pady=(10, 0))
        for t, v in (("Старый пароль", self.pw_old), ("Новый пароль", self.pw_new)):
            col = tk.Frame(row, bg=CARD)
            col.pack(side="left", padx=(0, 12))
            lab(col, t, DIM, 9).pack(anchor="w", pady=(0, 3))
            Field(col, v, 24, "•").pack()
        Btn(row, "Сменить", self.change_pw).pack(side="left", pady=(18, 0))

    def load_profile(self):
        self.ref_l.config(text=self.me["ref_code"])

    def new_ref(self):
        if self.ask("Новый реф-код?", text="Старый код перестанет работать.", ok="Сгенерировать") is not None:
            def ok(r):
                self.me["ref_code"] = r["ref_code"]
                self.load_profile()
                self.toast("Новый реф-код создан", GOOD)
            self.bg(lambda: self.api.call("/api/panel/newref"), ok)

    def change_pw(self):
        old, new = self.pw_old.get(), self.pw_new.get()

        def ok(r):
            self.cfg["password"] = new
            self.save()
            self.pw_old.set(""), self.pw_new.set("")
            self.toast("Пароль изменён", GOOD)
        self.bg(lambda: self.api.call("/api/panel/setpw", old=old, password=new), ok)

    # ---------------- НАСТРОЙКИ
    def build_settings(self, f):
        c = card(f)
        c.pack(fill="x")
        b = tk.Frame(c, bg=CARD)
        b.pack(fill="x", padx=22, pady=18)
        self.s_vars = {k: tk.StringVar() for k in ("price_day", "price_forever", "start_balance")}
        for i, (k, t, h) in enumerate((("price_day", "Цена 1 дня ключа", "за день × активаций"), ("price_forever", "Цена ключа «навсегда»", "за активацию"),
                                       ("start_balance", "Стартовый баланс", "новым сотрудникам"))):
            col = tk.Frame(b, bg=CARD)
            col.grid(row=0, column=i, padx=(0, 18), sticky="w")
            lab(col, t, TXT, 10, True).pack(anchor="w")
            lab(col, h, DIM, 9).pack(anchor="w", pady=(0, 4))
            Field(col, self.s_vars[k], 12).pack(anchor="w")
        Btn(b, "Сохранить", self.save_settings).grid(row=1, column=0, pady=(18, 0), sticky="w")
        lab(f, "Цены действуют на продавцов и админов (владелец создаёт бесплатно). Баланс выдаётся на вкладке «Персонал».", DIM, 10).pack(anchor="w", pady=12)

    def load_settings(self):
        def ok(r):
            for k, v in self.s_vars.items():
                v.set(str(r[k]))
        self.bg(lambda: self.api.call("/api/panel/getsettings"), ok)

    def save_settings(self):
        try:
            d = {k: int(v.get() or 0) for k, v in self.s_vars.items()}
        except ValueError:
            return self.toast("Нужны целые числа", BAD)
        self.bg(lambda: self.api.call("/api/panel/settings", **d),
                lambda r: (self.me.update(price_day=d["price_day"], price_forever=d["price_forever"]), self.toast("Сохранено", GOOD)))


if __name__ == "__main__":
    App()
