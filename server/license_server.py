# -*- coding: utf-8 -*-
"""Сервер лицензий DCODE. Без внешних зависимостей (только стандартная библиотека Python 3.8+).

Запуск:   python license_server.py            (порт 8787, переменные: SF_PORT, SF_DB, SF_ADMIN_TOKEN)
Хостинг:  любой VPS / PythonAnywhere (WSGI: объект `application`) / Render и т.п.
При первом запуске создаётся admin_token.txt — этот токен вводится в админ-программе.
ВАЖНО: на боевом сервере ставь HTTPS (nginx/Caddy/Cloudflare), иначе пароли ходят открытым текстом.
"""
import os, re, json, time, hmac, secrets, sqlite3, hashlib, threading
from wsgiref.simple_server import make_server, WSGIRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("SF_DB", os.path.join(HERE, "licenses.db"))
ALPHA = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
USER_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
LOCK = threading.Lock()
FAILS = {}  # ip -> [timestamps]


def admin_token():
    t = os.environ.get("SF_ADMIN_TOKEN")
    if t:
        return t
    p = os.path.join(HERE, "admin_token.txt")
    if not os.path.exists(p):
        with open(p, "w") as f:
            f.write(secrets.token_urlsafe(24))
        print("Создан admin_token.txt — токен для админ-программы:", open(p).read())
    return open(p).read().strip()


ADMIN = None


def db():
    c = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS keys(
        key TEXT PRIMARY KEY, days INTEGER NOT NULL, max_uses INTEGER NOT NULL, uses INTEGER NOT NULL DEFAULT 0,
        note TEXT DEFAULT '', created INTEGER, revoked INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE COLLATE NOCASE, salt TEXT, pw TEXT,
        hwid TEXT DEFAULT '', expires INTEGER NOT NULL, banned INTEGER NOT NULL DEFAULT 0,
        created INTEGER, last_login INTEGER DEFAULT 0, key_used TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER, created INTEGER);
    """)
    # миграция: отдельная привязка для Android (ПК и телефон работают независимо)
    cols = [r["name"] for r in c.execute("PRAGMA table_info(users)")]
    if "hwid_android" not in cols:
        c.execute("ALTER TABLE users ADD COLUMN hwid_android TEXT DEFAULT ''")
    for col, ddl in (("note", "TEXT DEFAULT ''"), ("ban_reason", "TEXT DEFAULT ''"), ("last_seen", "INTEGER DEFAULT 0"),
                     ("playing", "INTEGER DEFAULT 0"), ("game_nick", "TEXT DEFAULT ''"), ("last_ip", "TEXT DEFAULT ''")):
        if col not in cols:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {ddl}")
    if "owner" not in [r["name"] for r in c.execute("PRAGMA table_info(keys)")]:
        c.execute("ALTER TABLE keys ADD COLUMN owner TEXT DEFAULT ''")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS staff(
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE COLLATE NOCASE, salt TEXT, pw TEXT, role TEXT NOT NULL DEFAULT 'seller',
        balance INTEGER NOT NULL DEFAULT 0, ref_code TEXT UNIQUE, inviter TEXT DEFAULT '', banned INTEGER NOT NULL DEFAULT 0,
        created INTEGER, last_login INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS psessions(token TEXT PRIMARY KEY, staff_id INTEGER, created INTEGER);
    CREATE TABLE IF NOT EXISTS tx(id INTEGER PRIMARY KEY AUTOINCREMENT, staff_id INTEGER, delta INTEGER, balance INTEGER,
        reason TEXT, by_name TEXT, ts INTEGER);
    CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT);
    CREATE TABLE IF NOT EXISTS msgs(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, kind TEXT, text TEXT, ts INTEGER);
    """)
    if not c.execute("SELECT 1 FROM staff LIMIT 1").fetchone():
        un, pw = os.environ.get("SF_OWNER_USER", "AnimeFox555"), os.environ.get("SF_OWNER_PASS", "qwerty123")
        salt = secrets.token_hex(16)
        c.execute("INSERT INTO staff(username,salt,pw,role,ref_code,created) VALUES(?,?,?,?,?,?)",
                  (un, salt, hash_pw(pw, salt), "owner", gen_ref(), int(time.time())))
    c.close()


# ------------------------------------------------------------ утилиты
class Err(Exception):
    def __init__(self, msg, code="error", status=400):
        super().__init__(msg)
        self.msg, self.code, self.status = msg, code, status


def hash_pw(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()


def norm_key(k):
    return re.sub(r"[^A-Z0-9-]", "", (k or "").upper())


def gen_key():
    g = lambda: "".join(secrets.choice(ALPHA) for _ in range(4))
    return f"SFOX-{g()}-{g()}-{g()}"


def gen_ref():
    return "".join(secrets.choice(ALPHA) for _ in range(8))


def rate_check(ip, add=False):
    now = time.time()
    lst = [t for t in FAILS.get(ip, []) if now - t < 600]
    if add:
        lst.append(now)
    FAILS[ip] = lst
    if len(lst) >= 12 and not add:
        raise Err("Слишком много попыток. Подожди несколько минут.", "rate", 429)


def need(d, *names):
    for n in names:
        if not isinstance(d.get(n), (str, int)) or d.get(n) == "":
            raise Err("Заполни все поля", "bad_request")


def public(u, token=None):
    r = {"ok": True, "username": u["username"], "expires": u["expires"], "server_time": int(time.time())}
    if token:
        r["token"] = token
    return r


def new_session(c, uid):
    c.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
    t = secrets.token_urlsafe(32)
    c.execute("INSERT INTO sessions VALUES(?,?,?)", (t, uid, int(time.time())))
    return t


def take_key(c, key, now):
    k = c.execute("SELECT * FROM keys WHERE key=?", (norm_key(key),)).fetchone()
    if not k or k["revoked"]:
        raise Err("Ключ недействителен", "bad_key")
    if k["max_uses"] and k["uses"] >= k["max_uses"]:
        raise Err("Ключ уже использован максимальное число раз", "key_used")
    c.execute("UPDATE keys SET uses=uses+1 WHERE key=?", (k["key"],))
    return k


def auth_user(c, username, password):
    u = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not u or not hmac.compare_digest(u["pw"], hash_pw(password, u["salt"])):
        raise Err("Неверный логин или пароль", "bad_creds", 401)
    if u["banned"]:
        raise Err("Аккаунт заблокирован" + (": " + u["ban_reason"] if u["ban_reason"] else ""), "banned", 403)
    return u


def hw_col(d):
    """Платформа клиента: "pc" (по умолчанию, старые клиенты) или "android"."""
    p = d.get("platform", "pc")
    if p not in ("pc", "android"):
        raise Err("Неизвестная платформа", "bad_request")
    return ("hwid_android", "телефону") if p == "android" else ("hwid", "ПК")


def bind_hwid(c, u, d):
    col, name = hw_col(d)
    hw = d.get("hwid")
    if not hw:
        raise Err("Нет идентификатора устройства", "bad_request")
    if not u[col]:
        c.execute(f"UPDATE users SET {col}=? WHERE id=?", (hw, u["id"]))
    elif u[col] != hw:
        raise Err(f"Аккаунт привязан к другому {'телефону' if col == 'hwid_android' else 'ПК'}. "
                  "Напиши владельцу — он сбросит привязку.", "hwid", 403)


# ------------------------------------------------------------ клиентские методы
def api_register(c, d, ip):
    need(d, "username", "password", "key", "hwid")
    un, pw = d["username"].strip(), d["password"]
    if not USER_RE.match(un):
        raise Err("Логин: 3–20 символов, латиница, цифры и _", "bad_request")
    if not 6 <= len(pw) <= 64:
        raise Err("Пароль: от 6 до 64 символов", "bad_request")
    now = int(time.time())
    c.execute("BEGIN IMMEDIATE")
    try:
        if c.execute("SELECT 1 FROM users WHERE username=?", (un,)).fetchone():
            raise Err("Этот логин уже занят", "exists")
        k = take_key(c, d["key"], now)
        salt = secrets.token_hex(16)
        exp = 0 if k["days"] == 0 else now + k["days"] * 86400
        col, _ = hw_col(d)
        c.execute(f"INSERT INTO users(username,salt,pw,{col},expires,created,last_login,key_used) VALUES(?,?,?,?,?,?,?,?)",
                  (un, salt, hash_pw(pw, salt), d["hwid"], exp, now, now, k["key"]))
        u = c.execute("SELECT * FROM users WHERE username=?", (un,)).fetchone()
        tok = new_session(c, u["id"])
        c.execute("COMMIT")
    except BaseException:
        c.execute("ROLLBACK")
        raise
    return public(u, tok)


def api_login(c, d, ip):
    need(d, "username", "password", "hwid")
    u = auth_user(c, d["username"].strip(), d["password"])
    bind_hwid(c, u, d)
    now = int(time.time())
    if u["expires"] and u["expires"] <= now:
        raise Err("Срок лицензии истёк. Продли её новым ключом.", "expired", 403)
    c.execute("UPDATE users SET last_login=? WHERE id=?", (now, u["id"]))
    return public(u, new_session(c, u["id"]))


def api_extend(c, d, ip):
    need(d, "username", "password", "key", "hwid")
    u = auth_user(c, d["username"].strip(), d["password"])
    bind_hwid(c, u, d)
    now = int(time.time())
    c.execute("BEGIN IMMEDIATE")
    try:
        k = take_key(c, d["key"], now)
        if u["expires"] == 0:
            exp = 0
        elif k["days"] == 0:
            exp = 0
        else:
            exp = max(now, u["expires"]) + k["days"] * 86400
        c.execute("UPDATE users SET expires=?, last_login=? WHERE id=?", (exp, now, u["id"]))
        u = c.execute("SELECT * FROM users WHERE id=?", (u["id"],)).fetchone()
        tok = new_session(c, u["id"])
        c.execute("COMMIT")
    except BaseException:
        c.execute("ROLLBACK")
        raise
    return public(u, tok)


def api_check(c, d, ip):
    need(d, "token", "hwid")
    s = c.execute("SELECT * FROM sessions WHERE token=?", (d["token"],)).fetchone()
    if not s:
        raise Err("Сессия недействительна — войди заново", "session", 401)
    u = c.execute("SELECT * FROM users WHERE id=?", (s["user_id"],)).fetchone()
    if not u or u["banned"]:
        raise Err("Аккаунт заблокирован" + (": " + u["ban_reason"] if u and u["ban_reason"] else ""), "banned", 403)
    col, _ = hw_col(d)
    if u[col] and u[col] != d["hwid"]:
        raise Err("Аккаунт привязан к другому устройству", "hwid", 403)
    if u["expires"] and u["expires"] <= int(time.time()):
        raise Err("Срок лицензии истёк", "expired", 403)
    now = int(time.time())
    nick = str(d.get("nick") or "")[:20]
    c.execute("UPDATE users SET last_seen=?, playing=?, game_nick=CASE WHEN ?!='' THEN ? ELSE game_nick END, last_ip=? WHERE id=?",
              (now, 1 if d.get("playing") else 0, nick, nick, ip, u["id"]))
    r = public(u)
    ms = c.execute("SELECT * FROM msgs WHERE user_id=? ORDER BY id", (u["id"],)).fetchall()
    if ms:
        c.execute("DELETE FROM msgs WHERE user_id=?", (u["id"],))
        r["msgs"] = [m["text"] for m in ms if m["kind"] == "msg"]
        kk = [m["text"] for m in ms if m["kind"] == "kick"]
        if kk:
            r["kick"] = kk[-1] or "Вас выкинули из игры"
    return r


# ------------------------------------------------------------ админ-методы
def adm_create(c, d):
    n = max(1, min(500, int(d.get("count", 1))))
    days = max(0, int(d.get("days", 30)))
    mu = max(0, int(d.get("max_uses", 1)))
    note = str(d.get("note", ""))[:80]
    now, out = int(time.time()), []
    for _ in range(n):
        k = gen_key()
        c.execute("INSERT INTO keys(key,days,max_uses,note,created) VALUES(?,?,?,?,?)", (k, days, mu, note, now))
        out.append(k)
    return {"ok": True, "keys": out}


def adm_keys(c, d):
    return {"ok": True, "keys": [dict(r) for r in c.execute("SELECT * FROM keys ORDER BY created DESC LIMIT 2000")]}


def adm_users(c, d):
    rows = c.execute("SELECT id,username,hwid,hwid_android,expires,banned,created,last_login,key_used FROM users ORDER BY created DESC").fetchall()
    return {"ok": True, "users": [dict(r) for r in rows], "server_time": int(time.time())}


def adm_revoke(c, d):
    c.execute("UPDATE keys SET revoked=? WHERE key=?", (0 if d.get("undo") else 1, norm_key(d.get("key"))))
    return {"ok": True}


def adm_delkey(c, d):
    c.execute("DELETE FROM keys WHERE key=?", (norm_key(d.get("key")),))
    return {"ok": True}


def adm_ban(c, d):
    c.execute("UPDATE users SET banned=? WHERE username=?", (1 if d.get("banned", True) else 0, d.get("username")))
    # сессии НЕ удаляем: api_check/login и так отвечают code="banned", и клиент показывает причину
    return {"ok": True}


def adm_extend(c, d):
    u = c.execute("SELECT * FROM users WHERE username=?", (d.get("username"),)).fetchone()
    if not u:
        raise Err("Нет такого пользователя", "no_user", 404)
    days, now = int(d.get("days", 0)), int(time.time())
    exp = 0 if d.get("forever") else (0 if u["expires"] == 0 else max(now, u["expires"]) + days * 86400)
    if d.get("set_from_now"):
        exp = now + days * 86400
    c.execute("UPDATE users SET expires=? WHERE id=?", (exp, u["id"]))
    return {"ok": True, "expires": exp}


def adm_reset_hwid(c, d):
    pl = d.get("platform")   # "pc" / "android" / не задано = сбросить обе привязки
    if pl == "pc":
        c.execute("UPDATE users SET hwid='' WHERE username=?", (d.get("username"),))
    elif pl == "android":
        c.execute("UPDATE users SET hwid_android='' WHERE username=?", (d.get("username"),))
    else:
        c.execute("UPDATE users SET hwid='', hwid_android='' WHERE username=?", (d.get("username"),))
    return {"ok": True}


def adm_deluser(c, d):
    c.execute("DELETE FROM sessions WHERE user_id=(SELECT id FROM users WHERE username=?)", (d.get("username"),))
    c.execute("DELETE FROM users WHERE username=?", (d.get("username"),))
    return {"ok": True}


LVL = {"seller": 1, "admin": 2, "owner": 3}


def cfg_get(c, k, dflt=0):
    r = c.execute("SELECT v FROM settings WHERE k=?", (k,)).fetchone()
    return int(r["v"]) if r else dflt


def p_pub(c, s, token=None):
    r = {"ok": True, "username": s["username"], "role": s["role"], "balance": s["balance"], "ref_code": s["ref_code"],
         "price_day": cfg_get(c, "price_day", 1), "price_forever": cfg_get(c, "price_forever", 100), "server_time": int(time.time())}
    if token:
        r["token"] = token
    return r


def p_session(c, s):
    t = secrets.token_urlsafe(32)
    c.execute("DELETE FROM psessions WHERE created<?", (int(time.time()) - 30 * 86400,))
    c.execute("INSERT INTO psessions VALUES(?,?,?)", (t, s["id"], int(time.time())))
    return t


def p_login(c, d, ip):
    need(d, "username", "password")
    s = c.execute("SELECT * FROM staff WHERE username=?", (d["username"].strip(),)).fetchone()
    if not s or not hmac.compare_digest(s["pw"], hash_pw(d["password"], s["salt"])):
        raise Err("Неверный логин или пароль", "bad_creds", 401)
    if s["banned"]:
        raise Err("Аккаунт заблокирован", "banned", 403)
    c.execute("UPDATE staff SET last_login=? WHERE id=?", (int(time.time()), s["id"]))
    return p_pub(c, s, p_session(c, s))


def p_register(c, d, ip):
    need(d, "username", "password", "ref")
    un, pw = d["username"].strip(), d["password"]
    if not USER_RE.match(un):
        raise Err("Логин: 3–20 символов, латиница, цифры и _", "bad_request")
    if not 6 <= len(pw) <= 64:
        raise Err("Пароль: от 6 до 64 символов", "bad_request")
    inv = c.execute("SELECT * FROM staff WHERE ref_code=? AND banned=0", (d["ref"].strip().upper(),)).fetchone()
    if not inv:
        raise Err("Неверный реф-код", "bad_key")
    if c.execute("SELECT 1 FROM staff WHERE username=?", (un,)).fetchone():
        raise Err("Этот логин уже занят", "exists")
    salt, now = secrets.token_hex(16), int(time.time())
    bal = cfg_get(c, "start_balance", 0)
    c.execute("INSERT INTO staff(username,salt,pw,role,balance,ref_code,inviter,created,last_login) VALUES(?,?,?,?,?,?,?,?,?)",
              (un, salt, hash_pw(pw, salt), "seller", bal, gen_ref(), inv["username"], now, now))
    s = c.execute("SELECT * FROM staff WHERE username=?", (un,)).fetchone()
    if bal:
        c.execute("INSERT INTO tx(staff_id,delta,balance,reason,by_name,ts) VALUES(?,?,?,?,?,?)", (s["id"], bal, bal, "Стартовый баланс", "система", now))
    return p_pub(c, s, p_session(c, s))


def tx_add(c, sid, delta, bal, reason, by):
    c.execute("INSERT INTO tx(staff_id,delta,balance,reason,by_name,ts) VALUES(?,?,?,?,?,?)", (sid, delta, bal, reason, by, int(time.time())))


def p_me(c, d, s):
    return p_pub(c, s)


def p_create(c, d, s):
    n, days = max(1, min(500, int(d.get("count", 1)))), max(0, int(d.get("days", 30)))
    mu, note = max(0, int(d.get("max_uses", 1))), str(d.get("note", ""))[:80]
    cost = 0
    if s["role"] != "owner":
        if mu < 1:
            raise Err("Безлимитные ключи может создавать только владелец", "forbidden", 403)
        cost = n * mu * (cfg_get(c, "price_forever", 100) if days == 0 else days * cfg_get(c, "price_day", 1))
        if s["balance"] < cost:
            raise Err(f"Не хватает баланса: нужно {cost}, у тебя {s['balance']}", "balance")
    now, out = int(time.time()), []
    for _ in range(n):
        k = gen_key()
        c.execute("INSERT INTO keys(key,days,max_uses,note,created,owner) VALUES(?,?,?,?,?,?)", (k, days, mu, note, now, s["username"]))
        out.append(k)
    bal = s["balance"] - cost
    if cost:
        c.execute("UPDATE staff SET balance=? WHERE id=?", (bal, s["id"]))
        tx_add(c, s["id"], -cost, bal, f"Ключи ×{n} ({'навсегда' if days == 0 else str(days) + ' дн.'})", s["username"])
    return {"ok": True, "keys": out, "cost": cost, "balance": bal}


def p_keys(c, d, s):
    if s["role"] == "seller":
        rows = c.execute("SELECT * FROM keys WHERE owner=? ORDER BY created DESC LIMIT 2000", (s["username"],))
    else:
        rows = c.execute("SELECT * FROM keys ORDER BY created DESC LIMIT 2000")
    return {"ok": True, "keys": [dict(r) for r in rows]}


def own_key(c, s, key):
    k = c.execute("SELECT * FROM keys WHERE key=?", (norm_key(key),)).fetchone()
    if not k or (s["role"] == "seller" and k["owner"] != s["username"]):
        raise Err("Это не твой ключ", "forbidden", 403)
    return k


def p_revoke(c, d, s):
    k = own_key(c, s, d.get("key"))
    c.execute("UPDATE keys SET revoked=? WHERE key=?", (0 if d.get("undo") else 1, k["key"]))
    return {"ok": True}


def p_delkey(c, d, s):
    k = own_key(c, s, d.get("key"))
    c.execute("DELETE FROM keys WHERE key=?", (k["key"],))
    return {"ok": True}


def p_users(c, d, s):
    rows = c.execute("SELECT id,username,hwid,hwid_android,expires,banned,ban_reason,created,last_login,key_used,note,last_seen,playing,game_nick,last_ip "
                     "FROM users ORDER BY created DESC").fetchall()
    return {"ok": True, "users": [dict(r) for r in rows], "server_time": int(time.time())}


def uget(c, d):
    u = c.execute("SELECT * FROM users WHERE username=?", (d.get("username"),)).fetchone()
    if not u:
        raise Err("Нет такого игрока", "no_user", 404)
    return u


def p_message(c, d, s):
    u, t = uget(c, d), str(d.get("message", "")).strip()[:200]
    if not t:
        raise Err("Пустое сообщение", "bad_request")
    c.execute("INSERT INTO msgs(user_id,kind,text,ts) VALUES(?,?,?,?)", (u["id"], "msg", f"[{s['username']}] {t}", int(time.time())))
    return {"ok": True}


def p_kick(c, d, s):
    u = uget(c, d)
    c.execute("INSERT INTO msgs(user_id,kind,text,ts) VALUES(?,?,?,?)", (u["id"], "kick", str(d.get("message", ""))[:200], int(time.time())))
    return {"ok": True}


def p_ban(c, d, s):
    u, b = uget(c, d), 1 if d.get("banned", True) else 0
    c.execute("UPDATE users SET banned=?, ban_reason=? WHERE id=?", (b, str(d.get("reason", ""))[:120] if b else "", u["id"]))
    return {"ok": True}


def p_extend(c, d, s):
    return adm_extend(c, d)


def p_reset_hwid(c, d, s):
    return adm_reset_hwid(c, d)


def p_logout(c, d, s):
    u = uget(c, d)
    c.execute("DELETE FROM sessions WHERE user_id=?", (u["id"],))
    return {"ok": True}


def p_note(c, d, s):
    u = uget(c, d)
    c.execute("UPDATE users SET note=? WHERE id=?", (str(d.get("note", ""))[:120], u["id"]))
    return {"ok": True}


def p_setuserpw(c, d, s):
    u, pw = uget(c, d), str(d.get("password", ""))
    if not 6 <= len(pw) <= 64:
        raise Err("Пароль: от 6 до 64 символов", "bad_request")
    salt = secrets.token_hex(16)
    c.execute("UPDATE users SET salt=?, pw=? WHERE id=?", (salt, hash_pw(pw, salt), u["id"]))
    c.execute("DELETE FROM sessions WHERE user_id=?", (u["id"],))
    return {"ok": True}


def p_deluser(c, d, s):
    return adm_deluser(c, d)


def sget(c, d):
    t = c.execute("SELECT * FROM staff WHERE username=?", (d.get("username"),)).fetchone()
    if not t:
        raise Err("Нет такого сотрудника", "no_user", 404)
    return t


def p_staff(c, d, s):
    out = []
    for r in c.execute("SELECT * FROM staff ORDER BY created").fetchall():
        n = c.execute("SELECT COUNT(*) FROM keys WHERE owner=?", (r["username"],)).fetchone()[0]
        out.append({"username": r["username"], "role": r["role"], "balance": r["balance"], "keys_made": n, "inviter": r["inviter"] or "—",
                    "ref_code": r["ref_code"], "banned": r["banned"], "last_login": r["last_login"], "created": r["created"]})
    return {"ok": True, "staff": out}


def p_staff_role(c, d, s):
    t = sget(c, d)
    if d.get("role") not in LVL:
        raise Err("Неизвестная роль", "bad_request")
    if t["id"] == s["id"]:
        raise Err("Свою роль менять нельзя", "forbidden", 403)
    c.execute("UPDATE staff SET role=? WHERE id=?", (d["role"], t["id"]))
    return {"ok": True}


def p_staff_balance(c, d, s):
    t, a = sget(c, d), int(d.get("amount", 0))
    nb = a if d.get("mode") == "set" else t["balance"] + a
    c.execute("UPDATE staff SET balance=? WHERE id=?", (nb, t["id"]))
    tx_add(c, t["id"], nb - t["balance"], nb, str(d.get("reason", ""))[:80] or "Изменение баланса", s["username"])
    return {"ok": True, "balance": nb}


def p_staff_ban(c, d, s):
    t = sget(c, d)
    if t["id"] == s["id"]:
        raise Err("Себя банить нельзя", "forbidden", 403)
    c.execute("UPDATE staff SET banned=? WHERE id=?", (1 if d.get("banned", True) else 0, t["id"]))
    if d.get("banned", True):
        c.execute("DELETE FROM psessions WHERE staff_id=?", (t["id"],))
    return {"ok": True}


def p_staff_setpw(c, d, s):
    t, pw = sget(c, d), str(d.get("password", ""))
    if not 6 <= len(pw) <= 64:
        raise Err("Пароль: от 6 до 64 символов", "bad_request")
    salt = secrets.token_hex(16)
    c.execute("UPDATE staff SET salt=?, pw=? WHERE id=?", (salt, hash_pw(pw, salt), t["id"]))
    c.execute("DELETE FROM psessions WHERE staff_id=?", (t["id"],))
    return {"ok": True}


def p_staff_delete(c, d, s):
    t = sget(c, d)
    if t["id"] == s["id"]:
        raise Err("Себя удалять нельзя", "forbidden", 403)
    c.execute("DELETE FROM psessions WHERE staff_id=?", (t["id"],))
    c.execute("DELETE FROM staff WHERE id=?", (t["id"],))
    return {"ok": True}


def p_tx(c, d, s):
    q = "SELECT tx.*, staff.username AS who FROM tx LEFT JOIN staff ON staff.id=tx.staff_id "
    rows = c.execute(q + ("" if s["role"] == "owner" else "WHERE tx.staff_id=? ") + "ORDER BY tx.id DESC LIMIT 500",
                     () if s["role"] == "owner" else (s["id"],)).fetchall()
    return {"ok": True, "tx": [{"id": r["id"], "ts": r["ts"], "who": r["who"] or "?", "delta": r["delta"], "balance": r["balance"],
                                "reason": r["reason"], "by_name": r["by_name"]} for r in rows]}


def p_newref(c, d, s):
    r = gen_ref()
    c.execute("UPDATE staff SET ref_code=? WHERE id=?", (r, s["id"]))
    return {"ok": True, "ref_code": r}


def p_setpw(c, d, s):
    if not hmac.compare_digest(s["pw"], hash_pw(str(d.get("old", "")), s["salt"])):
        raise Err("Старый пароль неверный", "bad_creds")
    pw = str(d.get("password", ""))
    if not 6 <= len(pw) <= 64:
        raise Err("Пароль: от 6 до 64 символов", "bad_request")
    salt = secrets.token_hex(16)
    c.execute("UPDATE staff SET salt=?, pw=? WHERE id=?", (salt, hash_pw(pw, salt), s["id"]))
    return {"ok": True}


def p_getsettings(c, d, s):
    return {"ok": True, "price_day": cfg_get(c, "price_day", 1), "price_forever": cfg_get(c, "price_forever", 100), "start_balance": cfg_get(c, "start_balance", 0)}


def p_settings(c, d, s):
    for k in ("price_day", "price_forever", "start_balance"):
        if k in d:
            c.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (k, str(max(0, int(d[k])))))
    return {"ok": True}


PANEL_OPEN = {"/api/panel/login": p_login, "/api/panel/register": p_register}
PANEL = {"/api/panel/me": (p_me, 1), "/api/panel/create": (p_create, 1), "/api/panel/keys": (p_keys, 1), "/api/panel/revoke": (p_revoke, 1),
         "/api/panel/delkey": (p_delkey, 1), "/api/panel/users": (p_users, 1), "/api/panel/message": (p_message, 2), "/api/panel/kick": (p_kick, 2),
         "/api/panel/ban": (p_ban, 2), "/api/panel/extend": (p_extend, 2), "/api/panel/reset_hwid": (p_reset_hwid, 2), "/api/panel/logout": (p_logout, 2),
         "/api/panel/note": (p_note, 2), "/api/panel/setuserpw": (p_setuserpw, 2), "/api/panel/deluser": (p_deluser, 2),
         "/api/panel/staff": (p_staff, 3), "/api/panel/staff_role": (p_staff_role, 3), "/api/panel/staff_balance": (p_staff_balance, 3),
         "/api/panel/staff_ban": (p_staff_ban, 3), "/api/panel/staff_setpw": (p_staff_setpw, 3), "/api/panel/staff_delete": (p_staff_delete, 3),
         "/api/panel/tx": (p_tx, 1), "/api/panel/newref": (p_newref, 1), "/api/panel/setpw": (p_setpw, 1),
         "/api/panel/getsettings": (p_getsettings, 3), "/api/panel/settings": (p_settings, 3)}


def panel_dispatch(c, path, data, environ, ip):
    rate_check(ip)
    if path in PANEL_OPEN:
        try:
            c.execute("BEGIN IMMEDIATE")
            try:
                r = PANEL_OPEN[path](c, data, ip)
                c.execute("COMMIT")
                return r
            except BaseException:
                c.execute("ROLLBACK")
                raise
        except Err as e:
            if e.code in ("bad_creds", "bad_key"):
                rate_check(ip, add=True)
            raise
    fn, lvl = PANEL[path]
    row = c.execute("SELECT staff.* FROM psessions JOIN staff ON staff.id=psessions.staff_id WHERE token=?",
                    (environ.get("HTTP_X_PANEL_TOKEN", ""),)).fetchone()
    if not row:
        rate_check(ip, add=True)
        raise Err("Сессия недействительна — войди заново", "session", 401)
    if row["banned"]:
        raise Err("Аккаунт заблокирован", "banned", 403)
    if LVL[row["role"]] < lvl:
        raise Err("Недостаточно прав", "forbidden", 403)
    c.execute("BEGIN IMMEDIATE")
    try:
        r = fn(c, data, row)
        c.execute("COMMIT")
        return r
    except BaseException:
        c.execute("ROLLBACK")
        raise


CLIENT = {"/api/register": api_register, "/api/login": api_login, "/api/extend": api_extend, "/api/check": api_check}
ADMINS = {"/api/admin/create": adm_create, "/api/admin/keys": adm_keys, "/api/admin/users": adm_users,
          "/api/admin/revoke": adm_revoke, "/api/admin/delkey": adm_delkey, "/api/admin/ban": adm_ban,
          "/api/admin/extend": adm_extend, "/api/admin/reset_hwid": adm_reset_hwid, "/api/admin/deluser": adm_deluser}


# ------------------------------------------------------------ WSGI
def application(environ, start_response):
    global ADMIN
    if ADMIN is None:
        ADMIN = admin_token()
        init_db()

    def reply(status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        start_response(f"{status} X", [("Content-Type", "application/json; charset=utf-8"),
                                       ("Content-Length", str(len(body))), ("Cache-Control", "no-store")])
        return [body]

    path = environ.get("PATH_INFO", "/")
    ip = environ.get("REMOTE_ADDR", "?")
    if os.environ.get("SF_TRUST_PROXY"):
        ip = environ.get("HTTP_X_FORWARDED_FOR", ip).split(",")[0].strip()
    if environ["REQUEST_METHOD"] != "POST":
        return reply(200, {"ok": True, "service": "sweetie-fox-license"})
    try:
        n = min(int(environ.get("CONTENT_LENGTH") or 0), 65536)
        data = json.loads(environ["wsgi.input"].read(n) or b"{}")
        if not isinstance(data, dict):
            raise ValueError
    except Exception:
        return reply(400, {"ok": False, "error": "Некорректный запрос", "code": "bad_request"})
    try:
        with LOCK:
            c = db()
            try:
                if path in PANEL or path in PANEL_OPEN:
                    return reply(200, panel_dispatch(c, path, data, environ, ip))
                if path in ADMINS:
                    tok = environ.get("HTTP_X_ADMIN_TOKEN", "")
                    rate_check(ip)
                    if not hmac.compare_digest(tok, ADMIN):
                        rate_check(ip, add=True)
                        raise Err("Нет доступа", "forbidden", 403)
                    return reply(200, ADMINS[path](c, data))
                if path in CLIENT:
                    rate_check(ip)
                    try:
                        return reply(200, CLIENT[path](c, data, ip))
                    except Err as e:
                        if e.code in ("bad_creds", "bad_key", "key_used", "session"):
                            rate_check(ip, add=True)
                        raise
                raise Err("Не найдено", "not_found", 404)
            finally:
                c.close()
    except Err as e:
        return reply(e.status, {"ok": False, "error": e.msg, "code": e.code})
    except sqlite3.IntegrityError:
        return reply(400, {"ok": False, "error": "Конфликт данных", "code": "conflict"})
    except Exception as e:  # noqa
        import traceback; traceback.print_exc()
        return reply(500, {"ok": False, "error": "Внутренняя ошибка сервера", "code": "server"})


class Quiet(WSGIRequestHandler):
    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("SF_PORT", "8787"))
    ADMIN = admin_token()
    init_db()
    print(f"DCODE license server: http://0.0.0.0:{port}   (БД: {DB_PATH})")
    make_server("0.0.0.0", port, application, handler_class=Quiet).serve_forever()
