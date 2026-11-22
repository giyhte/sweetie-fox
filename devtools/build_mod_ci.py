# -*- coding: utf-8 -*-
"""Собирает jar меню на GitHub Actions и кладёт в modjar/ (вшивается в exe). Запуск из корня репозитория."""
import os, sys, json, shutil, subprocess, urllib.request, urllib.parse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from pl.common import tree_hash, MC_VERSION, OWN_JAR

OUT = os.path.join(ROOT, "modjar")
os.makedirs(OUT, exist_ok=True)


def get(url):
    r = urllib.request.Request(url, headers={"User-Agent": "SweetieFox-CI"})
    return json.loads(urllib.request.urlopen(r, timeout=30).read().decode())


loader = "0.18.4"
try:
    loader = [v for v in get("https://meta.fabricmc.net/v2/versions/loader") if v.get("stable")][0]["version"]
except Exception as e:
    print("loader fallback:", e)
fapi = "0.141.1+1.21.11"
try:
    q = urllib.parse.urlencode({"loaders": json.dumps(["fabric"]), "game_versions": json.dumps([MC_VERSION])})
    fapi = get(f"https://api.modrinth.com/v2/project/fabric-api/version?{q}")[0]["version_number"]
except Exception as e:
    print("fabric-api fallback:", e)

work = os.path.join(ROOT, "_modbuild")
shutil.rmtree(work, ignore_errors=True)
shutil.copytree(os.path.join(ROOT, "modsrc"), work, ignore=shutil.ignore_patterns("build", ".gradle"))
with open(os.path.join(work, "gradle.properties"), "w", encoding="utf-8") as f:
    f.write(f"org.gradle.jvmargs=-Xmx2g\nminecraft_version={MC_VERSION}\nloader_version={loader}\nfabric_version={fapi}\n"
            "loom_version=1.14-SNAPSHOT\nmod_version=1.0.0\n")
subprocess.run("gradle build --no-daemon --console=plain", cwd=work, shell=True, check=True)
libs = os.path.join(work, "build", "libs")
jars = [x for x in os.listdir(libs) if x.endswith(".jar") and "sources" not in x and "dev" not in x]
shutil.copy2(os.path.join(libs, jars[0]), os.path.join(OUT, OWN_JAR))
with open(os.path.join(OUT, "mod.hash"), "w") as f:
    f.write(tree_hash(os.path.join(ROOT, "modsrc")))
print("OK:", jars[0], "hash", open(os.path.join(OUT, "mod.hash")).read())
