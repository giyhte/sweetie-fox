# -*- coding: utf-8 -*-
"""Сервер лицензий Sweetie Fox. Без внешних зависимостей (только стандартная библиотека Python 3.8+).

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
        raise Err("Аккаунт заблокирован", "banned", 403)
    return u


def bind_hwid(c, u, hwid):
    if not hwid:
        raise Err("Нет идентификатора ПК", "bad_request")
    if not u["hwid"]:
        c.execute("UPDATE users SET hwid=? WHERE id=?", (hwid, u["id"]))
    elif u["hwid"] != hwid:
        raise Err("Аккаунт привязан к другому ПК. Напиши владельцу — он сбросит привязку.", "hwid", 403)


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
        c.execute("INSERT INTO users(username,salt,pw,hwid,expires,created,last_login,key_used) VALUES(?,?,?,?,?,?,?,?)",
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
    bind_hwid(c, u, d["hwid"])
    now = int(time.time())
    if u["expires"] and u["expires"] <= now:
        raise Err("Срок лицензии истёк. Продли её новым ключом.", "expired", 403)
    c.execute("UPDATE users SET last_login=? WHERE id=?", (now, u["id"]))
    return public(u, new_session(c, u["id"]))


def api_extend(c, d, ip):
    need(d, "username", "password", "key", "hwid")
    u = auth_user(c, d["username"].strip(), d["password"])
    bind_hwid(c, u, d["hwid"])
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
        raise Err("Аккаунт заблокирован", "banned", 403)
    if u["hwid"] and u["hwid"] != d["hwid"]:
        raise Err("Аккаунт привязан к другому ПК", "hwid", 403)
    if u["expires"] and u["expires"] <= int(time.time()):
        raise Err("Срок лицензии истёк", "expired", 403)
    return public(u)


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
    rows = c.execute("SELECT id,username,hwid,expires,banned,created,last_login,key_used FROM users ORDER BY created DESC").fetchall()
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
    c.execute("UPDATE users SET hwid='' WHERE username=?", (d.get("username"),))
    return {"ok": True}


def adm_deluser(c, d):
    c.execute("DELETE FROM sessions WHERE user_id=(SELECT id FROM users WHERE username=?)", (d.get("username"),))
    c.execute("DELETE FROM users WHERE username=?", (d.get("username"),))
    return {"ok": True}


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
        return reply(500, {"ok": False, "error": "Внутренняя ошибка сервера", "code": "server"})


class Quiet(WSGIRequestHandler):
    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("SF_PORT", "8787"))
    ADMIN = admin_token()
    init_db()
    print(f"Sweetie Fox license server: http://0.0.0.0:{port}   (БД: {DB_PATH})")
    make_server("0.0.0.0", port, application, handler_class=Quiet).serve_forever()
