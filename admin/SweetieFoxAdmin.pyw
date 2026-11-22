# -*- coding: utf-8 -*-
"""Sweetie Fox Admin — создание ключей лицензий и управление пользователями."""
import os, sys, json, time, urllib.request, urllib.error
import tkinter as tk
from tkinter import ttk, messagebox

HERE = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
CFG = os.path.join(HERE, "admin_config.json")
BG, PANEL, FG, SUB, ACC = "#0f0d2a", "#1a1745", "#ffffff", "#b9b3f0", "#8b5cf6"


def fmt_ts(t):
    return "навсегда" if not t else time.strftime("%d.%m.%Y %H:%M", time.localtime(t))


def fmt_left(exp, now):
    if not exp:
        return "навсегда"
    s = exp - now
    if s <= 0:
        return "истекла"
    d, r = divmod(int(s), 86400)
    return f"{d}д {r // 3600}ч"


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Sweetie Fox Admin")
        self.root.geometry("900x620")
        self.root.configure(bg=BG)
        st = ttk.Style()
        st.theme_use("clam")
        st.configure(".", background=BG, foreground=FG, fieldbackground=PANEL, font=("Segoe UI", 10))
        st.configure("TNotebook", background=BG, borderwidth=0)
        st.configure("TNotebook.Tab", background=PANEL, foreground=SUB, padding=(16, 8))
        st.map("TNotebook.Tab", background=[("selected", ACC)], foreground=[("selected", "#fff")])
        st.configure("TButton", background=ACC, foreground="#fff", padding=(12, 6), borderwidth=0)
        st.map("TButton", background=[("active", "#a78bfa")])
        st.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG, rowheight=24, borderwidth=0)
        st.configure("Treeview.Heading", background="#26225f", foreground="#fff")
        st.map("Treeview", background=[("selected", ACC)])
        st.configure("TEntry", insertcolor="#fff")
        st.configure("TCheckbutton", background=BG, foreground=FG)
        try:
            self.cfg = json.load(open(CFG, encoding="utf-8"))
        except Exception:
            self.cfg = {"url": "http://127.0.0.1:8787", "token": ""}
        top = ttk.Frame(self.root)
        top.pack(fill="x", padx=12, pady=10)
        ttk.Label(top, text="Сервер:").pack(side="left")
        self.url = ttk.Entry(top, width=34)
        self.url.insert(0, self.cfg["url"])
        self.url.pack(side="left", padx=6)
        ttk.Label(top, text="Токен:").pack(side="left")
        self.tok = ttk.Entry(top, width=30, show="•")
        self.tok.insert(0, self.cfg["token"])
        self.tok.pack(side="left", padx=6)
        ttk.Button(top, text="Подключиться", command=self.connect).pack(side="left", padx=6)
        self.status = ttk.Label(top, text="", foreground=SUB)
        self.status.pack(side="left", padx=8)
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.tk_keys, self.tk_users = ttk.Frame(nb), ttk.Frame(nb)
        nb.add(self.tk_keys, text="  Ключи  ")
        nb.add(self.tk_users, text="  Пользователи  ")
        self.build_keys()
        self.build_users()
        self.root.after(200, self.connect)
        self.root.mainloop()

    # ---- сеть ----
    def call(self, path, **data):
        req = urllib.request.Request(self.url.get().rstrip("/") + path, data=json.dumps(data).encode(),
                                     headers={"Content-Type": "application/json", "X-Admin-Token": self.tok.get().strip()})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read().decode()).get("error", str(e))
            except Exception:
                msg = str(e)
            raise RuntimeError(msg)
        except Exception as e:
            raise RuntimeError(f"Нет связи: {e}")

    def safe(self, fn):
        try:
            return fn()
        except Exception as e:
            messagebox.showerror("Sweetie Fox Admin", str(e))

    def connect(self):
        json.dump({"url": self.url.get().strip(), "token": self.tok.get().strip()}, open(CFG, "w", encoding="utf-8"))
        try:
            self.refresh()
            self.status.config(text="● подключено", foreground="#86efac")
        except Exception as e:
            self.status.config(text="● " + str(e)[:50], foreground="#fb7185")

    def refresh(self):
        self.load_keys()
        self.load_users()

    # ---- ключи ----
    def build_keys(self):
        f = self.tk_keys
        box = ttk.LabelFrame(f, text=" Создать ключи ")
        box.pack(fill="x", padx=8, pady=8)
        self.days, self.uses, self.count, self.note = tk.StringVar(value="30"), tk.StringVar(value="1"), tk.StringVar(value="1"), tk.StringVar()
        self.forever = tk.BooleanVar()
        r = ttk.Frame(box)
        r.pack(fill="x", padx=8, pady=8)
        for lab, var, w in (("Срок (дней):", self.days, 6), ("Активаций:", self.uses, 5), ("Сколько ключей:", self.count, 5), ("Заметка:", self.note, 22)):
            ttk.Label(r, text=lab).pack(side="left", padx=(8, 2))
            ttk.Entry(r, textvariable=var, width=w).pack(side="left")
        ttk.Checkbutton(r, text="Навсегда", variable=self.forever).pack(side="left", padx=10)
        ttk.Button(r, text="Создать", command=lambda: self.safe(self.create)).pack(side="left", padx=8)
        ttk.Label(box, text="Срок отсчитывается с момента активации. Активаций 0 = без ограничения.", foreground=SUB).pack(anchor="w", padx=12, pady=(0, 8))
        self.out = tk.Text(f, height=5, bg=PANEL, fg="#86efac", relief="flat", font=("Consolas", 11))
        self.out.pack(fill="x", padx=8)
        bt = ttk.Frame(f)
        bt.pack(fill="x", padx=8, pady=6)
        ttk.Button(bt, text="Скопировать новые ключи", style="Ghost.TButton", command=self.copy_out).pack(side="left")
        ttk.Button(bt, text="Копировать выбранный", style="Ghost.TButton", command=self.copy_sel).pack(side="left", padx=6)
        ttk.Button(bt, text="Отозвать", style="Ghost.TButton", command=lambda: self.safe(lambda: self.key_act("/api/admin/revoke"))).pack(side="left", padx=6)
        ttk.Button(bt, text="Вернуть", style="Ghost.TButton", command=lambda: self.safe(lambda: self.key_act("/api/admin/revoke", undo=True))).pack(side="left")
        ttk.Button(bt, text="Удалить", style="Danger.TButton", command=lambda: self.safe(lambda: self.key_act("/api/admin/delkey"))).pack(side="left", padx=6)
        ttk.Button(bt, text="Обновить", command=lambda: self.safe(self.refresh)).pack(side="right")
        ttk.Label(f, text=self._copy_hint, style="Sub.TLabel").pack(anchor="w", padx=10, pady=(0, 4))
        cols = ("key", "days", "uses", "state", "note", "created")
        self.kt = ttk.Treeview(f, columns=cols, show="headings", height=10)
        self._mk_copy_menu(self.kt)
        for c, t, w in (("key", "Ключ", 200), ("days", "Срок", 90), ("uses", "Использовано", 100), ("state", "Статус", 100), ("note", "Заметка", 220), ("created", "Создан", 140)):
            self.kt.heading(c, text=t)
            self.kt.column(c, width=w)
        self.kt.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def create(self):
        days = 0 if self.forever.get() else int(self.days.get() or 0)
        r = self.call("/api/admin/create", count=int(self.count.get() or 1), days=days,
                      max_uses=int(self.uses.get() or 0), note=self.note.get())
        self.out.delete("1.0", "end")
        self.out.insert("end", "\n".join(r["keys"]))
        self.load_keys()

    def copy_out(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.out.get("1.0", "end").strip())

    def copy_sel(self):
        s = self.kt.selection()
        if s:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.kt.item(s[0])["values"][0])

    def key_act(self, path, **kw):
        for i in self.kt.selection():
            self.call(path, key=self.kt.item(i)["values"][0], **kw)
        self.load_keys()

    def load_keys(self):
        self.kt.delete(*self.kt.get_children())
        for k in self.call("/api/admin/keys")["keys"]:
            st = "отозван" if k["revoked"] else ("исчерпан" if k["max_uses"] and k["uses"] >= k["max_uses"] else "активен")
            self.kt.insert("", "end", values=(k["key"], "навсегда" if k["days"] == 0 else f'{k["days"]} дн.',
                                              f'{k["uses"]}/{k["max_uses"] or "∞"}', st, k["note"], fmt_ts(k["created"])))

    # ---- пользователи ----
    def build_users(self):
        f = self.tk_users
        bt = ttk.Frame(f)
        bt.pack(fill="x", padx=8, pady=8)
        self.add_days = tk.StringVar(value="30")
        ttk.Button(bt, text="Бан / разбан", style="Danger.TButton", command=lambda: self.safe(self.ban)).pack(side="left")
        ttk.Button(bt, text="Сбросить привязку к ПК", style="Ghost.TButton", command=lambda: self.safe(lambda: self.user_act("/api/admin/reset_hwid"))).pack(side="left", padx=6)
        ttk.Label(bt, text="  Добавить дней:").pack(side="left")
        ttk.Entry(bt, textvariable=self.add_days, width=6).pack(side="left", padx=4)
        ttk.Button(bt, text="Продлить", style="Ghost.TButton", command=lambda: self.safe(lambda: self.user_act("/api/admin/extend", days=int(self.add_days.get() or 0)))).pack(side="left")
        ttk.Button(bt, text="Навсегда", style="Ghost.TButton", command=lambda: self.safe(lambda: self.user_act("/api/admin/extend", forever=True))).pack(side="left", padx=6)
        ttk.Button(bt, text="Удалить", style="Danger.TButton", command=lambda: self.safe(self.delete)).pack(side="left", padx=6)
        ttk.Button(bt, text="Обновить", command=lambda: self.safe(self.refresh)).pack(side="right")
        cols = ("user", "left", "until", "state", "hwid", "key", "last")
        self.ut = ttk.Treeview(f, columns=cols, show="headings")
        self._mk_copy_menu(self.ut)
        for c, t, w in (("user", "Логин", 130), ("left", "Осталось", 90), ("until", "До", 130), ("state", "Статус", 80), ("hwid", "ПК", 110), ("key", "Ключ", 170), ("last", "Последний вход", 130)):
            self.ut.heading(c, text=t)
            self.ut.column(c, width=w)
        self.ut.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def load_users(self):
        r = self.call("/api/admin/users")
        self.ut.delete(*self.ut.get_children())
        for u in r["users"]:
            self.ut.insert("", "end", values=(u["username"], fmt_left(u["expires"], r["server_time"]), fmt_ts(u["expires"]),
                                              "БАН" if u["banned"] else "ок", (u["hwid"] or "—")[:10], u["key_used"], fmt_ts(u["last_login"])))

    def sel_users(self):
        return [self.ut.item(i)["values"][0] for i in self.ut.selection()]

    def user_act(self, path, **kw):
        for n in self.sel_users():
            self.call(path, username=n, **kw)
        self.load_users()

    def ban(self):
        for i in self.ut.selection():
            v = self.ut.item(i)["values"]
            self.call("/api/admin/ban", username=v[0], banned=(v[3] != "БАН"))
        self.load_users()

    def delete(self):
        if self.sel_users() and messagebox.askyesno("Удалить", "Удалить выбранных пользователей?"):
            self.user_act("/api/admin/deluser")


    # ---- копирование из таблиц ----
    def _mk_copy_menu(self, tree):
        m = tk.Menu(self.root, tearoff=0, bg=PANEL2, fg=FG, activebackground=ACC, activeforeground="#fff", bd=0)
        m.add_command(label="Копировать строку", command=lambda: self._copy_row(tree))
        m.add_command(label="Копировать ячейку", command=lambda: self._copy_cell(tree))
        m.add_command(label="Копировать всю таблицу", command=lambda: self._copy_table(tree))

        def show(e):
            iid = tree.identify_row(e.y)
            if iid and iid not in tree.selection():
                tree.selection_set(iid)
            tree._last_col = tree.identify_column(e.x)
            m.tk_popup(e.x_root, e.y_root)
        tree.bind("<Button-3>", show)
        tree.bind("<Control-c>", lambda e: self._copy_row(tree))

    def _clip(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def _copy_row(self, tree):
        rows = ["\t".join(str(v) for v in tree.item(i)["values"]) for i in tree.selection()]
        if rows:
            self._clip("\n".join(rows))

    def _copy_cell(self, tree):
        sel = tree.selection()
        if not sel:
            return
        col = getattr(tree, "_last_col", "#1")
        try:
            idx = int(col.replace("#", "")) - 1
            self._clip(str(tree.item(sel[0])["values"][idx]))
        except Exception:
            self._copy_row(tree)

    def _copy_table(self, tree):
        cols = tree["columns"]
        rows = ["\t".join(tree.heading(c)["text"] for c in cols)]
        for i in tree.get_children():
            rows.append("\t".join(str(v) for v in tree.item(i)["values"]))
        self._clip("\n".join(rows))


if __name__ == "__main__":
    App()
