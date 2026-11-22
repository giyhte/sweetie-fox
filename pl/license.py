# -*- coding: utf-8 -*-
"""Клиент лицензий: вход/регистрация по ключу, сессия, таймер срока, офлайн-запас."""
import os, json, time, uuid, hashlib, platform, urllib.request, urllib.error

# ↓↓↓ АДРЕС ТВОЕГО СЕРВЕРА ЛИЦЕНЗИЙ (можно переопределить файлом license_server.txt рядом с лаунчером)
SERVER = "https://kikisds.pythonanywhere.com"
OFFLINE_GRACE = 3 * 86400  # сколько можно играть без связи с сервером после последней успешной проверки


class LicenseError(Exception):
    def __init__(self, msg, code="error"):
        super().__init__(msg)
        self.code = code


class NetError(Exception):
    pass


def hwid():
    raw = f"{uuid.getnode()}|{platform.node()}|{platform.machine()}|{os.environ.get('PROCESSOR_IDENTIFIER', '')}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def fmt_left(sec):
    """None = навсегда."""
    if sec is None:
        return "Навсегда"
    if sec <= 0:
        return "Истекла"
    d, r = divmod(int(sec), 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    return (f"{d}д " if d else "") + f"{h:02d}:{m:02d}:{s:02d}"


class Lic:
    def __init__(self, root):
        self.root = root
        self.file = os.path.join(root, "license.json")
        self.url = SERVER
        try:
            with open(os.path.join(root, "license_server.txt"), encoding="utf-8") as f:
                u = f.read().strip()
                if u:
                    self.url = u
        except Exception:
            self.url = os.environ.get("SF_LICENSE_URL", SERVER)
        self.url = self.url.rstrip("/")
        self.d = {}
        try:
            with open(self.file, encoding="utf-8") as f:
                self.d = json.load(f)
        except Exception:
            pass

    # --- хранилище ---
    def _save(self):
        try:
            os.makedirs(self.root, exist_ok=True)
            with open(self.file, "w", encoding="utf-8") as f:
                json.dump(self.d, f)
        except Exception:
            pass

    @property
    def username(self):
        return self.d.get("username", "")

    def logout(self):
        self.d = {"username": self.username}
        self._save()

    # --- сеть ---
    def api(self, path, payload):
        req = urllib.request.Request(self.url + path, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json", "User-Agent": "SweetieFox-Launcher"})
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            try:
                j = json.loads(e.read().decode())
            except Exception:
                raise NetError("Сервер лицензий вернул ошибку")
            raise LicenseError(j.get("error", "Ошибка"), j.get("code", "error"))
        except (urllib.error.URLError, OSError, ValueError):
            raise NetError("Нет связи с сервером лицензий")

    def _apply(self, r):
        self.d.update({"username": r["username"], "expires": r["expires"],
                       "offset": r["server_time"] - time.time(), "last_ok": time.time()})
        if r.get("token"):
            self.d["token"] = r["token"]
        self._save()

    def login(self, user, pw):
        self._apply(self.api("/api/login", {"username": user, "password": pw, "hwid": hwid()}))

    def register(self, user, pw, key):
        self._apply(self.api("/api/register", {"username": user, "password": pw, "key": key, "hwid": hwid()}))

    def extend(self, user, pw, key):
        self._apply(self.api("/api/extend", {"username": user, "password": pw, "key": key, "hwid": hwid()}))

    def check(self):
        self._apply(self.api("/api/check", {"token": self.d.get("token", ""), "hwid": hwid()}))

    # --- состояние ---
    def left(self):
        """Секунд до конца; None = навсегда; <=0 = истекла."""
        exp = self.d.get("expires")
        if exp is None:
            return -1
        if exp == 0:
            return None
        return exp - (time.time() + self.d.get("offset", 0))

    def valid(self):
        if not self.d.get("token"):
            return False
        l = self.left()
        return l is None or l > 0

    def startup_check(self):
        """-> (status, note): ok | none | expired"""
        if not self.d.get("token"):
            return "none", ""
        try:
            self.check()
            return "ok", ""
        except LicenseError as e:
            self.logout()
            return ("expired" if e.code == "expired" else "none"), str(e)
        except NetError as e:
            if self.valid() and time.time() - self.d.get("last_ok", 0) < OFFLINE_GRACE:
                return "ok", ""
            return "none", str(e)
