"""Local pet command bridge and dispatch."""

import datetime
import http.server
import json
import os
import queue
import random
import shutil
import threading
from PyQt5.QtCore import QTimer
from minibuddies.catalog import (
    AFF_NAME,
    ALARMS,
    OUTFIT_NAME,
    SCENE_MENU,
    SQUADS,
    SQUAD_NAME,
    TICK,
    TRANSFORM,
    doro_only,
    usagi_only,
)
from minibuddies.runtime import BASE, MCP_HOME


MCP_PORTS = range(47851, 47871)

MCP_ACTIONS = {"cheer": 90, "wave": 90, "dance": 300, "sing": 300, "sleep": 600, "cry": 160, "pout": 120,
               "happy": 120, "surprise": 60, "yawn": 90, "eat": 200, "read": 300, "kiss": 90, "milk": 200,
               "angry": 120, "dizzy": 160, "nap": 600}

class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:
            req = {}
        box = {"ev": threading.Event(), "res": None}
        self.server.app.cmdq.put((req, box))
        box["ev"].wait(4)
        body = json.dumps(box["res"] if box["res"] is not None else {"ok": False, "error": "timeout"},
                          ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class CommandBridge:
    # ── Claude 연결(MCP) ─────────────────────────
    def app_name(self):
        return os.path.basename(BASE) or "desktop_pet"

    def start_bridge(self):
        if self.mcp_srv:
            return True
        try:                                     # Claude 가 쓰는 연결 서버 파일도 늘 최신으로 (다음에 Claude 켤 때 반영)
            dst, src = os.path.join(MCP_HOME, "pet_mcp.py"), os.path.join(BASE, "pet_mcp.py")
            if os.path.exists(src) and (not os.path.exists(dst) or open(dst, "rb").read() != open(src, "rb").read()):
                os.makedirs(MCP_HOME, exist_ok=True)
                shutil.copy(src, dst)
        except Exception:
            pass
        for port in MCP_PORTS:
            try:
                srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), _Handler)
            except OSError:
                continue
            srv.app = self
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            self.mcp_srv = srv
            try:
                d = os.path.join(MCP_HOME, "instances")
                os.makedirs(d, exist_ok=True)
                self.mcp_file = os.path.join(d, f"{port}.json")
                json.dump({"app": self.app_name(), "port": port, "pid": os.getpid(),
                           "chars": {c: self.chars[c]["label"] for c in (self.roster or [self.mode])}},
                          open(self.mcp_file, "w", encoding="utf-8"), ensure_ascii=False)
            except Exception:
                pass
            return True
        return False

    def stop_bridge(self):
        if self.mcp_srv:
            try:
                self.mcp_srv.shutdown(); self.mcp_srv.server_close()
            except Exception:
                pass
            self.mcp_srv = None
        if self.mcp_file:
            try:
                os.remove(self.mcp_file)
            except Exception:
                pass
            self.mcp_file = None

    def pump_cmds(self):
        while True:                                   # 숨겨서 물어본 대답 도착
            try:
                fn = self.uiq.get_nowait()
            except (queue.Empty, AttributeError):
                break
            try:
                fn()
            except Exception as e:
                self.ask_log(f"ui error {e}")
        while True:
            try:
                req, box = self.cmdq.get_nowait()
            except queue.Empty:
                return
            if box is None:                                   # 뒤에서 확인한 결과 (인터넷 등)
                if req.get("op") == "_net":
                    self.net_result(bool(req.get("ok")))
                continue
            try:
                box["res"] = self.handle_cmd(req)
            except Exception as e:
                box["res"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            box["ev"].set()

    def find_buddies(self, who):
        """who: 캐릭터 id 또는 이름(예: '리제', 'lize'). 비우면 화면 전원"""
        if not who:
            return list(self.buddies)
        w = str(who).strip().lower()
        def names(c):                       # 지금 모습 이름 + 다른 모습(의상) 이름도 (도로롱 상태인 도로시도 '도로시'로 찾게)
            out = [self.chars[c]["label"].lower()]
            out += [d.get("label", "").lower() for d in self.outfits.get(c, {}).values()]
            return [n for n in out if n]
        ids = [c for c in self.chars if c.lower() == w or w in names(c) or any(w in n for n in names(c))]
        return [b for b in self.buddies if b.char in ids]

    def force_say(self, b, text, secs=None, raw=False):
        """Claude 가 띄우는 말풍선: secs 가 없으면 사용자가 클릭해서 닫을 때까지 유지"""
        if not raw and f"{b.char}@{self.outfit.get(b.char)}" == "dorothy@doro":
            text = doro_only(text)          # 도로롱은 대답도 도로롱 소리만
        elif not raw and b.char == "usagi":
            text = usagi_only(text)         # 우사기도 대답·검색 결과를 우사기 소리로만
        if secs:
            t = int(max(1.0, min(120.0, float(secs))) * 1000 / TICK)
            b.say(str(text)[:300], t, force=True)
            b.say_lock = t
        else:
            b.say(str(text)[:300], 10 ** 9, force=True, sticky=True)
        self.claude_log = (getattr(self, "claude_log", []) + [f"{self.chars[b.char]['label']}: {text}"])[-20:]

    def handle_cmd(self, d):
        op = d.get("op", "status")
        who = d.get("who") or d.get("character")
        lab = lambda c: self.chars[c]["label"]
        if op == "ping":
            return {"ok": True, "app": self.app_name()}
        if op == "hello":                                # Claude 쪽 연결 서버가 켜질 때 인사
            self.mcp_seen = datetime.datetime.now().strftime("%m/%d %H:%M")
            for b in self.buddies[:1]:
                self.force_say(b, "Claude 랑 연결됐어요!", 6)
            return {"ok": True, "app": self.app_name()}
        if op == "status":
            scene_list = {SQUAD_NAME.get(sq, sq): [k for _, k in SCENE_MENU.get(sq, [])] for sq in self.scene_sets}
            return {"ok": True, "app": self.app_name(),
                    "members": {c: lab(c) for c in (self.roster or [self.mode])},
                    "active_team": [lab(c) for c in (self.team or [self.mode])],
                    "groups": {SQUAD_NAME.get(sq, sq): [lab(c) for c in m] for sq, m in SQUADS.items()
                               if all(c in self.chars for c in m) and (not self.roster or all(c in self.roster for c in m))},
                    "on_screen": [{"id": b.char, "name": lab(b.char), "state": b.state} for b in self.buddies],
                    "scenes": scene_list,
                    "group_play": ["train", "tower", "photo", "hands", "chat", "karaoke"],
                    "actions": sorted(MCP_ACTIONS),
                    "music": [x.get("name") for x in self.music_list()], "music_playing": getattr(self, "music_on", None),
                    "affinity": {lab(c): AFF_NAME[self.aff_level(self.aff(c))] for c in {b.char for b in self.buddies}},
                    "persona": {lab(c): [it[5][0] for it in (self.chars[c].get("persona") or [])]
                                for c in {b.char for b in self.buddies}},
                    "outfits": {lab(b): {"now": OUTFIT_NAME.get(self.outfit.get(b), self.outfit.get(b)),
                                         "all": {o: OUTFIT_NAME.get(o, o) for o in ofs}}
                                for b, ofs in self.outfits.items()}}
        bs = self.find_buddies(who)
        if op in ("say", "notify", "action", "persona", "outfit") and who and not bs:
            return {"ok": False, "error": f"화면에 '{who}' 이(가) 없어요", "on_screen": [lab(b.char) for b in self.buddies]}
        if op == "say":
            if not bs:
                return {"ok": False, "error": "화면에 캐릭터가 없어요"}
            b = bs[0] if who else random.choice([x for x in bs if x.surface] or bs)
            self.force_say(b, d.get("text", ""), d.get("seconds"))
            return {"ok": True, "who": lab(b.char)}
        if op == "notify":
            for i, b in enumerate(bs):
                def go(b=b):
                    if b in self.buddies:
                        self.ground(b); b.set("cheer", 120)
                        self.force_say(b, d.get("text", "다 됐어요!"), d.get("seconds"))
                QTimer.singleShot(i * 400, go)
            return {"ok": True, "who": [lab(b.char) for b in bs]}
        if op == "action":
            act = d.get("action", "cheer")
            if act == "shoot":                       # 니케: 뒷모습 사격
                done = [lab(b.char) for b in bs if (self.ground(b) or True) and b.do_shoot()]
                return {"ok": bool(done), "who": done, "action": act}
            if act == "transform":                   # 마리안↔모더니아, 도로시↔도로롱
                done = [lab(b.char) for b in bs if b.char in TRANSFORM and self.transform(b.char)]
                return {"ok": bool(done), "who": done, "action": act}
            if act not in MCP_ACTIONS:
                return {"ok": False, "error": f"action 은 {sorted(MCP_ACTIONS) + ['shoot', 'transform']} 중 하나"}
            for b in bs:
                self.ground(b); b.set(act, int(MCP_ACTIONS[act]))
            return {"ok": True, "who": [lab(b.char) for b in bs], "action": act}
        if op == "persona":
            out = []
            for b in bs[:1] if who else bs:
                lst = self.chars[b.char].get("persona") or []
                if not lst:
                    continue
                i = d.get("index")
                name = d.get("name")
                if name:
                    i = next((k for k, it in enumerate(lst) if name in " ".join(it[5])), None)
                if i is None or not (0 <= int(i) < len(lst)):
                    i = random.randrange(len(lst))
                self.force_persona(b, int(i)); out.append(lab(b.char))
            return {"ok": bool(out), "who": out}
        if op == "group":
            kind = d.get("kind", "")
            if kind.startswith("scene:") or kind in ("train", "tower", "photo", "hands", "chat", "karaoke"):
                self.group_event(kind, force=True)
            elif kind in ("tag", "snack", "dance", "nap", "greet"):
                self.duo_event(kind, force=True)
            else:
                return {"ok": False, "error": "kind 는 train/tower/photo/hands/chat/karaoke, tag/snack/dance/nap/greet, scene:<그룹>:<장면>"}
            return {"ok": True, "kind": kind}
        if op == "scene":
            g = str(d.get("group", "")).lower()
            sq = next((k for k in self.scene_sets if k == g or SQUAD_NAME.get(k, "").lower() == g), None)
            if not sq:
                return {"ok": False, "error": f"그룹은 {[SQUAD_NAME.get(k, k) for k in self.scene_sets]} 중 하나"}
            sc = d.get("scene") or random.choice([k for _, k in SCENE_MENU[sq]])
            self.group_event(f"scene:{sq}:{sc}", force=True)
            return {"ok": True, "group": SQUAD_NAME.get(sq, sq), "scene": sc}
        if op == "team":
            if not self.one_each or len(self.roster) < 2:
                return {"ok": False, "error": "멤버를 고를 수 있는 합본이 아니에요"}
            g = d.get("group")
            sq = next((k for k in SQUADS if g and (k == g or SQUAD_NAME.get(k) == g)), None)
            mem = [str(m).strip() for m in d.get("members", [])]
            want = [c for c in self.roster if (sq and c in SQUADS[sq]) or c in mem or lab(c) in mem]
            if not want:
                return {"ok": False, "error": "멤버를 못 찾았어요", "members": [lab(c) for c in self.roster]}
            self.set_team(want)
            return {"ok": True, "team": [lab(c) for c in want]}
        if op == "outfit":
            base = next((b for b in self.outfits if not who or b == who or lab(b) == who), None)
            if not base:
                return {"ok": False, "error": "의상을 바꿀 수 있는 캐릭터가 없어요"}
            o = d.get("outfit", "")
            of = next((k for k in self.outfits[base] if k == o or OUTFIT_NAME.get(k) == o or o in OUTFIT_NAME.get(k, "")), None)
            if not of:
                of = random.choice([k for k in self.outfits[base] if k != self.outfit.get(base)] or list(self.outfits[base]))
            self.set_outfit(base, of)
            return {"ok": True, "outfit": OUTFIT_NAME.get(of, of)}
        if op == "remind":
            if d.get("list"):
                return {"ok": True, "reminders": [f"{r['label']} {r['text']}" for r in self.cfg.get("reminders", [])]}
            if d.get("cancel") is not None:
                self.cancel_reminder(int(d["cancel"]))
                return {"ok": True}
            r = self.add_reminder(d.get("text", ""), d.get("time"), d.get("minutes"), d.get("who"))
            if not r:
                return {"ok": False, "error": "time 은 'HH:MM' 또는 'YYYY-MM-DD HH:MM', 아니면 minutes(몇 분 뒤)로 주세요"}
            return {"ok": True, "at": r["label"], "text": r["text"]}
        if op == "music":
            if d.get("stop"):
                self.stop_music()
                return {"ok": True, "stopped": True}
            if d.get("songs"):                                  # 추천 리스트 저장(+재생)
                it = self.save_playlist(d.get("name") or "추천 리스트", d.get("songs") or [], play=d.get("play", True) is not False)
                if not it:
                    return {"ok": False, "error": "유튜브 영상 링크(watch?v=… 또는 youtu.be/…)가 하나도 없어요. 검색해서 실제 링크를 넣어 주세요."}
                return {"ok": True, "saved_as": it["name"], "count": len(it["songs"]), "playing": self.music_on}
            lst = self.music_list()
            q = str(d.get("name") or "").strip()
            url = str(d.get("url") or "").strip()
            item = ({"name": q or "노래", "url": url} if url.startswith("http") else
                    next((x for x in lst if q and (q == x.get("name") or q in x.get("name", ""))), None))
            if not item and not lst:
                return {"ok": False, "error": "저장된 노래가 없어요. 환경설정 → 노래에서 유튜브 링크를 넣어 주세요."}
            ok = self.play_music(item)
            return {"ok": ok, "playing": self.music_on, "saved": [x.get("name") for x in lst]}
        if op == "alarm":
            k = d.get("kind", "snack")
            if k not in ALARMS:
                return {"ok": False, "error": f"kind 는 {list(ALARMS)}"}
            self.alarm(k)
            return {"ok": True}
        return {"ok": False, "error": f"모르는 op: {op}"}
