# -*- coding: utf-8 -*-
"""Установка игры, модов, сборка DCODE Menu, запуск."""
import os, sys, shutil, subprocess, uuid, zipfile, urllib.parse, time
from .common import *



# ---------- состояние ----------
def find_version(P):
    vd = os.path.join(P.game, "versions")
    if not os.path.isdir(vd):
        return None
    c = [d for d in os.listdir(vd) if d.startswith("fabric-loader-") and d.endswith("-" + MC_VERSION)
         and os.path.exists(os.path.join(vd, d, d + ".json"))]
    c.sort(key=lambda d: os.path.getmtime(os.path.join(vd, d)), reverse=True)
    return c[0] if c else None


def game_ok(P):
    """Игра целиком на месте — переустанавливать не нужно."""
    v = find_version(P)
    if not v:
        return False
    vd = os.path.join(P.game, "versions")
    ok = os.path.exists(os.path.join(vd, MC_VERSION, MC_VERSION + ".jar"))
    for d in ("libraries", os.path.join("assets", "indexes"), os.path.join("assets", "objects")):
        p = os.path.join(P.game, d)
        ok = ok and os.path.isdir(p) and bool(os.listdir(p))
    return ok


def _sha(path):
    import hashlib
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def game_status(P, cfg):
    """('ready' | 'update' | 'missing', подпись) — состояние игры для главного экрана."""
    import json as _j
    if not find_version(P):
        return "missing", "Игра не скачана"
    if not game_ok(P):
        return "update", "Нужно обновление"
    _dest = os.path.join(P.mods, OWN_JAR)
    if not (cfg.get("client_url") or CLIENT_URL) and not os.path.exists(os.path.join(RES, "client", OWN_JAR)) \
            and not os.path.exists(_dest):
        return "noclient", "Нет клиента DCODE (меню)"
    try:
        done = open(os.path.join(P.mods, ".pl_done"), encoding="utf-8").read().strip()
    except Exception:
        done = ""
    if done != MC_VERSION:
        return "update", "Нужно обновление"
    dest = os.path.join(P.mods, OWN_JAR)
    local = os.path.join(RES, "client", OWN_JAR)
    has_url = bool(cfg.get("client_url") or CLIENT_URL)
    if (has_url or os.path.exists(local)) and not os.path.exists(dest):
        return "update", "Нужно обновление"
    if not has_url and os.path.exists(local) and os.path.exists(dest):
        try:
            if _sha(local) != _sha(dest):
                return "update", "Нужно обновление"
        except Exception:
            pass
    return "ready", "Готов к запуску"


def state(P):
    n = 0
    if os.path.isdir(P.mods):
        n = len([f for f in os.listdir(P.mods) if f.endswith(".jar")])
    return {"game": find_version(P) is not None, "mods": n}


# ---------- options.txt ----------
def write_options(P, low):
    path = os.path.join(P.game, "options.txt")
    wanted = {"lang": "ru_ru", "onboardAccessibility": "false", "skipMultiplayerWarning": "true", "joinedFirstServer": "true", "tutorialStep": "none"}
    if low:
        wanted.update({"renderDistance": "6", "simulationDistance": "5", "particles": "2",
                       "entityShadows": "false", "biomeBlendRadius": "0", "mipmapLevels": "0",
                       "maxFps": "120", "enableVsync": "false", "ao": "false", "bobView": "false",
                       "entityDistanceScaling": "0.75"})
    lines, seen = [], set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for ln in f.read().splitlines():
                k = ln.split(":", 1)[0]
                if k in wanted:
                    ln = f"{k}:{wanted[k]}"
                if k == "resourcePacks" and "PulseLite.zip" in ln:  # старый ресурспак больше не нужен
                    ln = 'resourcePacks:["vanilla"]'
                seen.add(k)
                lines.append(ln)
    for k, v in wanted.items():
        if k not in seen:
            lines.append(f"{k}:{v}")
    os.makedirs(P.game, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------- игра ----------
def install_game(P, ctx, force=False):
    if not force and game_ok(P):
        ctx.log("Игра уже установлена — пропускаю загрузку ✓")
        ctx.frac(1)
        return
    import minecraft_launcher_lib as mll
    os.makedirs(P.game, exist_ok=True)
    mx = [1]
    cb = {"setStatus": ctx.status,
          "setProgress": lambda v: ctx.frac(v / mx[0]),
          "setMax": lambda m: mx.__setitem__(0, max(int(m), 1))}
    ctx.log(f"Minecraft {MC_VERSION} + Fabric…")
    mll.fabric.install_fabric(MC_VERSION, P.game, callback=cb)
    ctx.log("Java для игры…")
    try:
        info = mll.runtime.get_version_runtime_information(MC_VERSION, P.game)
        if info:
            mll.runtime.install_jvm_runtime(info["name"], P.game, callback=cb)
    except Exception as e:
        ctx.log(f"  Java: будет системная ({e})")


def download_mods(P, ctx):
    os.makedirs(P.mods, exist_ok=True)
    ctx.log("Моды оптимизации (Modrinth)…")
    import json as _j
    reg_p = os.path.join(P.mods, ".pl_mods.json")
    try:
        reg = _j.load(open(reg_p, encoding="utf-8"))
    except Exception:
        reg = {}
    todo = [m for m in MODS if not (m in reg and os.path.exists(os.path.join(P.mods, reg[m])))]
    if not todo:
        ctx.log("  моды уже установлены")
        ctx.frac(1)
        return
    from concurrent.futures import ThreadPoolExecutor
    done = [0]

    def one(slug):
        try:
            q = urllib.parse.urlencode({"loaders": json_s(["fabric"]), "game_versions": json_s([MC_VERSION])})
            vs = http_json(f"https://api.modrinth.com/v2/project/{slug}/version?{q}")
            if not vs:
                ctx.log(f"  ! {slug}: нет версии под {MC_VERSION}")
                return
            files = vs[0]["files"]
            f = next((x for x in files if x.get("primary")), files[0])
            dest = os.path.join(P.mods, f["filename"])
            if not os.path.exists(dest):
                download(f["url"], dest, timeout=120)
            reg[slug] = f["filename"]
            ctx.log(f"  + {slug}")
        except Exception as e:
            ctx.log(f"  ! {slug}: {e}")
        done[0] += 1
        ctx.frac(done[0] / len(todo))

    with ThreadPoolExecutor(4) as ex:
        list(ex.map(one, todo))
    try:
        _j.dump(reg, open(reg_p, "w", encoding="utf-8"))
    except Exception:
        pass
    ctx.frac(1)


NOCLIENT = "Клиент DCODE не найден: в лаунчер не вшит client/dcode-client.jar (собери через GitHub Actions) и не задан client_url"


def install_client(P, cfg, ctx):
    """Кладёт jar клиента DCODE в mods: из client/dcode-client.jar или по ссылке client_url."""
    from .common import CLIENT_URL
    os.makedirs(P.mods, exist_ok=True)
    dest = os.path.join(P.mods, OWN_JAR)
    local = os.path.join(RES, "client", OWN_JAR)
    url = cfg.get("client_url") or CLIENT_URL
    try:
        if url:
            ctx.log("Загрузка клиента DCODE…")
            download(url, dest, timeout=120)
        elif os.path.exists(local):
            shutil.copyfile(local, dest)
        else:
            ctx.log("! client/dcode-client.jar не найден и client_url не задан")
            return os.path.exists(dest)
        ctx.log("  + DCODE client")
        return True
    except Exception as e:
        ctx.log(f"  ! DCODE client: {e}")
        return os.path.exists(dest)


def json_s(o):
    import json
    return json.dumps(o)


def install_all(P, cfg, ctx, force=False):
    ctx.step(0.0, 0.75); install_game(P, ctx, force)
    ctx.step(0.75, 0.97); download_mods(P, ctx)
    if not install_client(P, cfg, ctx):
        raise RuntimeError(NOCLIENT)
    write_options(P, cfg.get("low_mode", True))
    try:  # отметка «установка/обновление завершены» — чтобы статус не зависал на «нужно обновление»
        with open(os.path.join(P.mods, ".pl_done"), "w", encoding="utf-8") as _f:
            _f.write(MC_VERSION)
    except Exception:
        pass
    ctx.step(1.0, 1.0)
    ctx.log("Готово!")


# ---------- запуск ----------
def launch(P, cfg, lic=None):
    import threading
    import minecraft_launcher_lib as mll
    vid = find_version(P)
    if not vid:
        raise RuntimeError("Игра не установлена")
    nick = cfg["nick"] or "Player"
    opts = {"username": nick,
            "uuid": str(uuid.uuid3(uuid.NAMESPACE_DNS, "OfflinePlayer:" + nick)),
            "token": "",
            "jvmArguments": [f"-Xmx{cfg['ram']}M", f"-Xms{min(1024, cfg['ram'])}M",
                             "-XX:+UseG1GC", "-XX:MaxGCPauseMillis=50", "-XX:+ParallelRefProcEnabled", "-XX:+DisableExplicitGC", "-XX:InitiatingHeapOccupancyPercent=15", "-Dfabric.log.level=warn"],
            "gameDirectory": P.game}
    if cfg.get("autojoin") and cfg.get("server"):
        opts["quickPlayMultiplayer"] = cfg["server"]
    try:
        info = mll.runtime.get_version_runtime_information(MC_VERSION, P.game)
        if info:
            exe = mll.runtime.get_executable_path(info["name"], P.game)
            if exe:
                w = exe[:-8] + "javaw.exe" if exe.lower().endswith("java.exe") else None
                opts["executablePath"] = w if w and os.path.exists(w) else exe
    except Exception:
        pass
    class _Q:  # тихий ctx для проверки клиента перед запуском
        def log(self, *a): pass
    if not install_client(P, cfg, _Q()):
        raise RuntimeError(NOCLIENT)
    try:  # профиль для меню клиента: ник, аккаунт, срок лицензии
        import json as _j
        left = lic.left() if lic else -1
        exp = 0 if left is None else (int(time.time() + left) if left > 0 else -1)
        with open(os.path.join(P.game, "dcode_profile.json"), "w", encoding="utf-8") as _f:
            _j.dump({"nick": nick, "account": (lic.username if lic else ""), "expires_at": exp}, _f)
    except Exception:
        pass
    cmd = mll.command.get_minecraft_command(vid, P.game, opts)
    env = dict(os.environ)
    proc = subprocess.Popen(cmd, cwd=P.game, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, creationflags=NOWIN, env=env)
    return proc
