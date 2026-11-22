# -*- coding: utf-8 -*-
"""Установка игры, модов, сборка Sweetie Fox Menu, запуск."""
import os, sys, shutil, subprocess, uuid, zipfile, urllib.parse, time
from .common import *

GRADLE_VER = "9.2.1"
JDK_URL = "https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jdk/hotspot/normal/eclipse"
GRADLE_URL = f"https://services.gradle.org/distributions/gradle-{GRADLE_VER}-bin.zip"


# ---------- состояние ----------
def find_version(P):
    vd = os.path.join(P.game, "versions")
    if not os.path.isdir(vd):
        return None
    c = [d for d in os.listdir(vd) if d.startswith("fabric-loader-") and d.endswith("-" + MC_VERSION)
         and os.path.exists(os.path.join(vd, d, d + ".json"))]
    c.sort(key=lambda d: os.path.getmtime(os.path.join(vd, d)), reverse=True)
    return c[0] if c else None


def prebuilt():
    """Готовый jar меню, вшитый в exe (собирается на GitHub). -> (путь, хэш) или None."""
    d = os.path.join(RES, "modjar")
    j, h = os.path.join(d, OWN_JAR), os.path.join(d, "mod.hash")
    try:
        if os.path.exists(j) and os.path.exists(h):
            return j, open(h).read().strip()
    except Exception:
        pass
    return None


_HC = {}


def want_hash(P):
    pb = prebuilt()
    if pb:
        return pb[1]
    if os.path.isdir(P.modsrc):
        if "h" not in _HC:
            _HC["h"] = tree_hash(P.modsrc)
        return _HC["h"]
    return None


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


def state(P):
    n = 0
    if os.path.isdir(P.mods):
        n = len([f for f in os.listdir(P.mods) if f.endswith(".jar") and f != OWN_JAR])
    # меню хранится скрыто (не в папке mods) и подставляется только на время запуска,
    # поэтому "установлено" определяем по наличию скрытой копии, а не файла в mods
    menu = os.path.exists(os.path.join(P.bundle, OWN_JAR))
    old = False
    try:
        hf = os.path.join(P.bundle, "mod.hash")
        w = want_hash(P)
        if menu and w is not None:
            old = not os.path.exists(hf) or open(hf).read().strip() != w
    except Exception:
        pass
    return {"game": find_version(P) is not None, "mods": n, "menu": menu, "menu_old": old}


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


def json_s(o):
    import json
    return json.dumps(o)


# ---------- свой мод ----------
def _unzip(zpath, dest, ctx, label):
    ctx.status(label)
    tmp = dest + "_tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(tmp)
    child = os.path.join(tmp, os.listdir(tmp)[0])
    shutil.rmtree(dest, ignore_errors=True)
    shutil.move(child, dest)
    shutil.rmtree(tmp, ignore_errors=True)
    os.remove(zpath)


def _force_rm(path):
    """Удаляет файл/папку; снимает read-only, 4 попытки (антивирус/индексатор в Windows). True если удалено."""
    import stat
    for i in range(4):
        try:
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path, onerror=lambda f, p, e: (os.chmod(p, stat.S_IWRITE), f(p)))
            elif os.path.lexists(path):
                try:
                    os.remove(path)
                except PermissionError:
                    os.chmod(path, stat.S_IWRITE)
                    os.remove(path)
            if not os.path.lexists(path):
                return True
        except Exception:
            pass
        time.sleep(0.3 * (i + 1))
    return not os.path.lexists(path)


def _sync_tree(src, dst):
    """Делает dst точной копией src: копирует новое/изменённое, удаляет «сирот» (старые файлы вроде PulseSky.java).
    Если сироту удалить не удалось — собираем в новой чистой папке, чтобы мусор не попал в компиляцию."""
    stale = False
    if os.path.isdir(dst):
        want = set()
        for root, dirs, files in os.walk(src):
            rel = os.path.relpath(root, src)
            want.add(os.path.normpath(rel))
            for fn in files:
                want.add(os.path.normpath(os.path.join(rel, fn)))
        for root, dirs, files in os.walk(dst, topdown=False):
            rel = os.path.relpath(root, dst)
            for fn in files:
                if os.path.normpath(os.path.join(rel, fn)) not in want:
                    if not _force_rm(os.path.join(root, fn)):
                        stale = True
            if os.path.normpath(rel) not in want and rel != ".":
                _force_rm(root)
    if stale:
        # не смогли удалить — уводим папку в сторону и копируем начисто
        bad = dst + ".old-" + uuid.uuid4().hex[:6]
        try:
            os.replace(dst, bad)
        except Exception:
            raise RuntimeError("Не удалось очистить старые исходники в " + dst +
                               ". Закройте антивирус/Java-процессы или удалите папку tools\\build вручную.")
        _force_rm(bad)
    for root, dirs, files in os.walk(src):
        out = os.path.join(dst, os.path.relpath(root, src))
        os.makedirs(out, exist_ok=True)
        for fn in files:
            a, b = os.path.join(root, fn), os.path.join(out, fn)
            if not os.path.exists(b) or os.path.getsize(a) != os.path.getsize(b) or open(a, "rb").read() != open(b, "rb").read():
                shutil.copy2(a, b)
    # старые скомпилированные классы тоже могут держать удалённые файлы
    _force_rm(os.path.join(os.path.dirname(dst), "build", "classes"))


def build_mod(P, ctx):
    """Сам скачивает JDK 21 и Gradle (один раз), собирает мод из modsrc. Возвращает путь к jar."""
    if not WIN:
        raise RuntimeError("Автосборка работает только в Windows (см. README — GitHub Actions)")
    import minecraft_launcher_lib as mll
    jdk = os.path.join(P.tools, "jdk")
    gradle = os.path.join(P.tools, "gradle")
    os.makedirs(P.tools, exist_ok=True)
    if not os.path.exists(os.path.join(jdk, "bin", "javac.exe")):
        ctx.log("Скачиваю JDK 21 (≈200 МБ, один раз)…")
        z = os.path.join(P.tools, "jdk.zip")
        download(JDK_URL, z, lambda f: ctx.frac(f * 0.25), timeout=120)
        _unzip(z, jdk, ctx, "Распаковка JDK…")
    if not os.path.exists(os.path.join(gradle, "bin", "gradle.bat")):
        ctx.log("Скачиваю Gradle (≈130 МБ, один раз)…")
        z = os.path.join(P.tools, "gradle.zip")
        download(GRADLE_URL, z, lambda f: ctx.frac(0.25 + f * 0.15), timeout=120)
        _unzip(z, gradle, ctx, "Распаковка Gradle…")

    work = os.path.join(P.tools, "build")
    os.makedirs(work, exist_ok=True)
    # обновляем только исходники; .gradle и build остаются (кэш → повторная сборка в разы быстрее)
    _sync_tree(os.path.join(P.modsrc, "src"), os.path.join(work, "src"))
    for fn in os.listdir(P.modsrc):
        if os.path.isfile(os.path.join(P.modsrc, fn)):
            shutil.copy2(os.path.join(P.modsrc, fn), os.path.join(work, fn))
    import json as _j
    stf = os.path.join(P.tools, "build_state.json")
    try:
        bs = _j.load(open(stf))
    except Exception:
        bs = {}
    loader, fabric_api = bs.get("loader"), bs.get("fabric_api")
    if not (loader and fabric_api):
        try:
            loader = mll.fabric.get_latest_loader_version()
        except Exception:
            loader = "0.18.4"
        fabric_api = "0.141.1+1.21.11"
        try:
            q = urllib.parse.urlencode({"loaders": json_s(["fabric"]), "game_versions": json_s([MC_VERSION])})
            fabric_api = http_json(f"https://api.modrinth.com/v2/project/fabric-api/version?{q}")[0]["version_number"]
        except Exception:
            pass
    with open(os.path.join(work, "gradle.properties"), "w", encoding="utf-8") as f:
        f.write("org.gradle.jvmargs=-Xmx1536M\norg.gradle.caching=true\norg.gradle.parallel=true\n"
                f"minecraft_version={MC_VERSION}\nloader_version={loader}\nfabric_version={fabric_api}\n"
                "loom_version=1.14-SNAPSHOT\nmod_version=1.0.0\n")

    warm = os.path.exists(stf) and os.path.isdir(os.path.join(P.tools, "gradle-home", "caches"))
    ctx.log("Обновляю Sweetie Fox Menu (быстро, кэш)…" if warm else "Собираю Sweetie Fox Menu (первый раз 3–6 минут)…")
    env = dict(os.environ)
    env["JAVA_HOME"] = jdk
    env["GRADLE_USER_HOME"] = os.path.join(P.tools, "gradle-home")
    env["PATH"] = os.path.join(jdk, "bin") + os.pathsep + env.get("PATH", "")
    logf = os.path.join(P.tools, "build.log")

    def run(extra):
        cmd = [os.path.join(gradle, "bin", "gradle.bat"), "build", "--no-daemon", "--console=plain"] + extra
        n = 0
        with open(logf, "a", encoding="utf-8", errors="replace") as lf:
            lf.write("\n=== " + " ".join(extra) + " ===\n")
            p = subprocess.Popen(cmd, cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace", **hidden())
            for line in p.stdout:
                lf.write(line)
                n += 1
                line = line.strip()
                if line:
                    ctx.status(line[:90])
                ctx.frac(0.4 + min(0.55, n / (200 if warm else 700)))
            p.wait()
        return p.returncode

    open(logf, "w").close()
    rc = run(["--offline"]) if warm else 1
    if rc != 0:
        rc = run([])
    if rc != 0:
        raise RuntimeError("Сборка не удалась. Лог: tools\\build.log")
    try:
        _j.dump({"loader": loader, "fabric_api": fabric_api}, open(stf, "w"))
    except Exception:
        pass
    libs = os.path.join(work, "build", "libs")
    jars = [x for x in os.listdir(libs) if x.endswith(".jar") and "sources" not in x and "dev" not in x]
    if not jars:
        raise RuntimeError("jar не найден после сборки")
    os.makedirs(P.bundle, exist_ok=True)
    out = os.path.join(P.bundle, OWN_JAR)
    shutil.copy2(os.path.join(libs, jars[0]), out)
    with open(os.path.join(P.bundle, "mod.hash"), "w") as f:
        f.write(want_hash(P) or tree_hash(P.modsrc))
    ctx.frac(1)
    return out


def ensure_menu_mod(P, ctx, allow_build=True):
    jar = os.path.join(P.bundle, OWN_JAR)
    hf = os.path.join(P.bundle, "mod.hash")
    want, pb = want_hash(P), prebuilt()
    if want is None and not os.path.exists(jar):
        ctx.log("Меню не найдено (нет готовой сборки и папки modsrc) — пропущено")
        return False
    have = ""
    if os.path.exists(hf):
        with open(hf) as f:
            have = f.read().strip()
    fresh = os.path.exists(jar) and (want is None or have == want)
    if not fresh:
        if pb:
            os.makedirs(P.bundle, exist_ok=True)
            shutil.copy2(pb[0], jar)
            with open(hf, "w") as f:
                f.write(want)
            ctx.log("Меню обновлено — готовая сборка, без пересборки ✓")
        else:
            if not allow_build:
                return False
            try:
                jar = build_mod(P, ctx)
            except Exception as e:
                ctx.log(f"! Sweetie Fox Menu не собран: {e}")
                return False
    else:
        ctx.log("Меню актуально ✓")
    # jar хранится только в скрытом bundle; наружу (в mods) кладём лишь на время запуска игры
    hide_own_mod(P)
    ctx.log("Sweetie Fox Menu готов — в игре жми Right Shift")
    return True


def reveal_own_mod(P):
    """Положить jar меню в mods перед запуском игры."""
    src = os.path.join(P.bundle, OWN_JAR)
    if not os.path.exists(src):
        return False
    os.makedirs(P.mods, exist_ok=True)
    shutil.copy2(src, os.path.join(P.mods, OWN_JAR))
    return True


def hide_own_mod(P):
    """Убрать jar меню из mods, чтобы его нельзя было просто скопировать из папки игры."""
    dst = os.path.join(P.mods, OWN_JAR)
    try:
        if os.path.exists(dst):
            os.remove(dst)
    except Exception:
        pass


def install_all(P, cfg, ctx, force=False):
    own = cfg.get("own_mod", True)
    ctx.step(0.0, 0.35 if own else 0.7); install_game(P, ctx, force)
    ctx.step(0.35 if own else 0.7, 0.45 if own else 0.95); download_mods(P, ctx)
    write_options(P, cfg.get("low_mode", True))
    if own:
        ctx.step(0.45, 1.0); ensure_menu_mod(P, ctx)
    ctx.step(1.0, 1.0)
    ctx.log("Готово!")


# ---------- запуск ----------
def launch(P, cfg, lic=None):
    import threading
    import minecraft_launcher_lib as mll
    from . import license as lic_mod
    vid = find_version(P)
    if not vid:
        raise RuntimeError("Игра не установлена")
    revealed = cfg.get("own_mod", True) and reveal_own_mod(P)
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
    cmd = mll.command.get_minecraft_command(vid, P.game, opts)
    env = dict(os.environ)
    # передаём собственному меню-моду токен лицензии — без него (например, если jar утащат
    # в другой лаунчер) меню просто не включится, см. PulseLicense.java
    if lic is not None and lic.d.get("token"):
        env["SF_TOKEN"] = lic.d["token"]
        env["SF_HWID"] = lic_mod.hwid()
        env["SF_LIC_URL"] = lic.url
    proc = subprocess.Popen(cmd, cwd=P.game, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, creationflags=NOWIN, env=env)
    if revealed:
        def _rehide():
            # ждём, пока JVM точно прогрузит классы мода, и убираем файл из mods
            end = time.time() + 25
            while time.time() < end and proc.poll() is None:
                time.sleep(1)
            hide_own_mod(P)
        threading.Thread(target=_rehide, daemon=True).start()
    return proc
