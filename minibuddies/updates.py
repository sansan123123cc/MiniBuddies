"""Download and apply application and character updates."""

import json
import os
import shutil
import time
from minibuddies.catalog import SQUADS
from minibuddies.runtime import BASE


# ── 자동 업데이트: GitHub 비공개 저장소의 manifest.json 과 비교해 바뀐 파일만 받아 옴 ──
#   manifest.json : 올리는 쪽(tools/publish.py)이 만듦 {"build", "version", "repo", "branch", "files": {경로: sha256}}
#   update.json   : 이 컴퓨터 전용 {"token": 읽기 전용 토큰, "auto": true} — 저장소에는 안 올라감
UPD_KEEP = {"settings.json", "update.json", "ask.log", "대화기록.txt", "manifest.json", "crash.log", "crash.log.old"}

def upd_path(name):
    return os.path.join(BASE, name)

def upd_load(name):
    try:
        with open(upd_path(name), encoding="utf-8") as source:
            return json.load(source)
    except Exception:
        return {}

def upd_save_cfg(d):
    tmp = upd_path("update.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, upd_path("update.json"))

def upd_sha(path):
    import hashlib
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for blk in iter(lambda: f.read(1 << 20), b""):
                h.update(blk)
    except OSError:
        return None
    return h.hexdigest()

def upd_get(repo, rel, token, ref="main", timeout=30):
    """저장소 파일 1개를 그대로(raw) 받아 옴 — 토큰 있으면 비공개 저장소(API), 없으면 공개 배포 저장소(raw)"""
    import urllib.request, urllib.parse
    if token:
        url = "https://api.github.com/repos/%s/contents/%s?ref=%s" % (repo, urllib.parse.quote(rel, safe="/"),
                                                                     urllib.parse.quote(ref))
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.raw",
                                                   "User-Agent": "stellive-pet",
                                                   "X-GitHub-Api-Version": "2022-11-28"})
        req.add_header("Authorization", "Bearer " + token)
    else:
        url = "https://raw.githubusercontent.com/%s/%s/%s" % (repo, urllib.parse.quote(ref, safe=""),
                                                              urllib.parse.quote(rel, safe="/"))
        req = urllib.request.Request(url, headers={"User-Agent": "stellive-pet", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

# ── 캐릭터 골라 받기: update.json 의 "chars" (없으면 = 전부 받는 예전 방식) ──
def upd_group(rel):
    """파일 → 어느 캐릭터 것인지 (chars/ 밖이면 None = 늘 받는 본체, '@squad:<그룹>' = 합동 장면)"""
    if not rel.startswith("chars/"):
        return None
    p = rel.split("/")
    if len(p) < 3:
        return None
    d = p[1]
    if d.startswith("_scenes_"):
        return "@squad:" + d[8:]
    if d == "_doro_motion":
        return "dorothy"
    if d.startswith("_"):
        return None
    return d.split("@")[0]

def upd_selected():
    """None = 전부, 아니면 받을 캐릭터 이름 set"""
    v = upd_load("update.json").get("chars")
    return None if v is None else set(v)

def upd_wanted(rel, sel):
    if sel is None:
        return True
    g = upd_group(rel)
    if g is None:
        return True
    if g.startswith("@squad:"):                      # 합동 장면은 그 그룹 멤버를 다 골랐을 때만
        mem = SQUADS.get(g[7:], [])
        return bool(mem) and all(m in sel for m in mem)
    return g in sel

def upd_all_chars(files):
    return sorted({g for g in map(upd_group, files) if g and not g.startswith("@")})

def upd_installed():
    """지금 깔려 있는 캐릭터 (그림 0.png 가 있는 폴더 기준)"""
    out = set()
    try:
        for d in os.listdir(upd_path("chars")):
            if not d.startswith("_") and os.path.exists(os.path.join(upd_path("chars"), d, "0.png")):
                out.add(d.split("@")[0])
    except OSError:
        pass
    return out

def upd_fetch_manifest():
    """저장소의 최신 manifest (버전 비교 없이). 못 받으면 내 manifest"""
    local, cfg = upd_load("manifest.json"), upd_load("update.json")
    repo = cfg.get("repo") or local.get("repo")
    branch = cfg.get("branch") or local.get("branch") or "main"
    try:
        remote = json.loads(upd_get(repo, "manifest.json", cfg.get("token"), branch).decode("utf-8"))
        remote.setdefault("repo", repo); remote.setdefault("branch", branch)
        return remote
    except Exception:
        return local if local.get("files") else None

def upd_check():
    """(새 manifest 또는 None, 안내 문구)"""
    import urllib.error
    local, cfg = upd_load("manifest.json"), upd_load("update.json")
    repo = cfg.get("repo") or local.get("repo")
    branch = cfg.get("branch") or local.get("branch") or "main"
    if not repo:
        return None, "저장소 정보가 없어요 (설치 프로그램으로 깔면 자동으로 채워져요)"
    try:
        remote = json.loads(upd_get(repo, "manifest.json", cfg.get("token"), branch).decode("utf-8"))
    except urllib.error.HTTPError as e:
        h = e.headers or {}
        if e.code in (403, 429) and (h.get("x-ratelimit-remaining") == "0" or h.get("retry-after")):
            try:
                mins = max(1, int((int(h.get("x-ratelimit-reset") or 0) - time.time()) / 60) + 1)
            except Exception:
                mins = 60
            return None, "GitHub 요청 한도에 걸렸어요 — 약 %d분 뒤에 다시 해 주세요 (토큰 문제 아님)" % mins
        if e.code in (401, 403):
            return None, "토큰이 틀렸거나 만료됐어요 (환경설정 → 업데이트에서 새 토큰 넣기)"
        if e.code == 404:
            return None, "저장소를 못 찾았어요 (이름 또는 토큰 권한 확인)"
        return None, f"업데이트 확인 실패 (HTTP {e.code})"
    except Exception as e:
        return None, f"업데이트 확인 실패 ({type(e).__name__})"
    remote.setdefault("repo", repo); remote.setdefault("branch", branch)
    if int(remote.get("build", 0)) <= int(local.get("build", 0)):
        return None, "최신 버전이에요 (v%s)" % (local.get("version") or local.get("build") or "?")
    return remote, "새 버전 v%s 있음" % remote.get("version", remote.get("build"))

def upd_apply(remote, progress=None):
    """바뀐 파일만 받아서 교체. 받기를 전부 끝낸 뒤에 한꺼번에 바꿔서, 중간에 끊겨도 펫이 망가지지 않음"""
    from concurrent.futures import ThreadPoolExecutor
    token = upd_load("update.json").get("token")
    files = remote.get("files", {})
    sel = upd_selected()
    need = []
    for rel, sha in files.items():
        if rel in UPD_KEEP or rel.startswith("..") or os.path.isabs(rel):
            continue
        if not upd_wanted(rel, sel):                   # 고르지 않은 캐릭터는 안 받음
            continue
        if upd_sha(upd_path(rel)) != sha:
            need.append(rel)
    stage = upd_path("_update_tmp")          # 지난번에 받다 만 파일은 그대로 두고 이어 받기 (처음부터 다시 받으면 GitHub 요청 한도에 걸림)
    done = [0]
    import threading as _th, urllib.error as _ue
    stop = _th.Event()

    def fetch(rel):
        out = os.path.join(stage, rel)
        if upd_sha(out) == files[rel]:                 # 이미 받아 둔 파일
            done[0] += 1
            if progress:
                progress(done[0], len(need))
            return
        if stop.is_set():
            raise RuntimeError("중단")
        data, why = None, ""
        for wait in (0, 2, 5, 12, 25):
            if wait:
                time.sleep(wait)
            try:
                data = upd_get(remote["repo"], rel, token, remote.get("branch", "main"), timeout=60)
                break
            except _ue.HTTPError as e:
                why = "HTTP %s" % e.code
                left = e.headers.get("x-ratelimit-remaining") if e.headers else None
                if e.code in (403, 429) and (left == "0" or e.headers.get("retry-after")):
                    try:
                        mins = max(1, int((int(e.headers.get("x-ratelimit-reset") or 0) - time.time()) / 60) + 1)
                    except Exception:
                        mins = 60
                    stop.set()
                    raise RuntimeError("GitHub 요청 한도에 걸렸어요 — 약 %d분 뒤 다시 하면 받던 데서 이어 받아요" % mins)
                if e.code in (401, 404):
                    break
            except Exception as e:
                why = type(e).__name__
            data = None
        if data is None:
            raise RuntimeError("받기 실패 (%s): %s" % (why or "?", rel))
        import hashlib
        if hashlib.sha256(data).hexdigest() != files[rel]:
            raise RuntimeError("파일이 손상됨: " + rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(data)
        done[0] += 1
        if progress:
            progress(done[0], len(need))

    with ThreadPoolExecutor(4) as ex:
        list(ex.map(fetch, need))
    for rel in need:                                   # 다 받았으면 한꺼번에 교체
        dst = upd_path(rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.replace(os.path.join(stage, rel), dst)
    old = upd_load("manifest.json").get("files", {})
    for rel in old:                                    # 새 버전에서 빠진 파일 정리
        if rel not in files and rel not in UPD_KEEP and not rel.startswith(".."):
            try:
                os.remove(upd_path(rel))
            except OSError:
                pass
    if sel is not None:                                # 고르기에서 뺀 캐릭터는 폴더째 지움
        try:
            for d in os.listdir(upd_path("chars")):
                g = upd_group("chars/%s/x" % d)
                if g and not upd_wanted("chars/%s/x" % d, sel):
                    shutil.rmtree(os.path.join(upd_path("chars"), d), ignore_errors=True)
        except OSError:
            pass
    shutil.rmtree(stage, ignore_errors=True)
    tmp = upd_path("manifest.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(remote, f, ensure_ascii=False, indent=0)
    os.replace(tmp, upd_path("manifest.json"))
    return len(need)
