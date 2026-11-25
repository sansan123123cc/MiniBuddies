"""MiniBuddies application lifecycle and coordination."""

import datetime
import http.server
import json
import math
import os
import queue
import random
import re
import shutil
import sys
import threading
import time
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QCursor, QPixmap
from PyQt5.QtWidgets import QApplication, QMenu, QMessageBox
from minibuddies.catalog import (
    AFF_LV,
    AFF_NAME,
    AI_CHAT_TOPICS,
    ALARMS,
    ALARM_ACT,
    ALARM_DEFAULT,
    ALARM_LINES,
    ALT_FROM,
    ALT_TF,
    APP_NAME,
    ASK_HELLO,
    AWAY_LINES,
    BIRTHDAY_FRIEND,
    BIRTHDAY_SELF,
    BUBBLE_PX,
    CASUAL_CHARS,
    CHAR_BIO,
    CHAR_BIRTHDAY,
    CHAR_CALL,
    CURSOR_LINES,
    CURSOR_LINES_P,
    DEFAULT_CALL,
    DORO_MOTION_DIR,
    DROP_LINES,
    F,
    FALLBACK,
    FRANCHISE,
    GROUP_TEXT,
    HIDE_LINES,
    HOLIDAYS,
    IMAGE_EXT,
    KANI_JOIN,
    KANI_NEAR,
    LAUGHER,
    MAX_COUNT,
    MY_APPS,
    OUTFIT_LINES,
    OUTFIT_NAME,
    SCENES,
    SCENES_ABYSS,
    SCENES_GEN1,
    SCENES_UNIVERSE,
    SCENE_MENU,
    SHAKE,
    SQUADS,
    SQUAD_NAME,
    START_COUNT,
    SYS_LINES,
    THINK_LINES,
    TICK,
    TOUCH_LINES,
    TRANSFORM,
    VIDEO_EXT,
    WELCOME_LINES,
    char_scale,
    doro_only,
    persona_of,
    usagi_only,
)
from minibuddies.desktop import (
    CHAR_SCREEN,
    CURSOR,
    SCREEN,
    find_browser,
    screen_for,
    set_topmost,
    target_screen,
    user32,
    window_tops,
    wintypes,
)
from minibuddies.features import legacy, touhou
from minibuddies.features.legacy import PET_ALPHA, _ev_bdir, _rest_on
from minibuddies.pet import Buddy
from minibuddies.plugins import PluginLibrary
from minibuddies.runtime import BASE, CHARS_DIR, ENTRY_SCRIPT, MCP_HOME, _crash_write
from minibuddies.ui.dialogs import BriefingWindow, HistoryDialog, SettingsDialog, claude_hist_dir
from minibuddies.ui.menus import AppMenus
from minibuddies.ui.picker import CharPicker
from minibuddies.ui.widgets import Burst, Flash, Scene
from minibuddies.updates import (
    upd_apply,
    upd_check,
    upd_fetch_manifest,
    upd_installed,
    upd_load,
    upd_path,
    upd_save_cfg,
    upd_selected,
)


# ── Claude 연결(MCP) 다리: 127.0.0.1 에서만 명령을 받음 → pet_mcp.py 가 Claude 데스크톱과 이어 줌 ──

MCP_PORTS = range(47851, 47871)
# 노래 틀기: 유튜브 링크(재생목록 OK)를 브라우저로 틀고, 그동안 펫들이 춤추고 노래함 (음원을 내려받지는 않음)
DEFAULT_MUSIC = [{"name": "내 재생목록", "url": "https://www.youtube.com/watch?v=JLM7z8afU4s&list=PLehDTIsIFasA"}]
YT_ID = re.compile(r"(?:v=|youtu\.be/|/shorts/|/embed/|/live/)([A-Za-z0-9_-]{11})")

def yt_id(url):
    m = YT_ID.search(str(url or ""))
    return m.group(1) if m else None

def yt_queue_url(songs):
    """여러 곡(유튜브 링크들) → 차례로 재생되는 하나의 유튜브 링크 (watch_videos)"""
    ids = [i for i in (yt_id(x.get("url") if isinstance(x, dict) else x) for x in songs) if i]
    ids = list(dict.fromkeys(ids))[:50]
    return ("https://www.youtube.com/watch_videos?video_ids=" + ",".join(ids)) if ids else None

MUSIC_LINES = ["♪~", "♪ 라라라~", "♬ 둠칫둠칫~", "♪ 이 노래 좋다~", "♬ 같이 불러요~", "♪♪", "♬ 흥얼흥얼~", "♪ 신난다~"]
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


class App(AppMenus):
    def __init__(self):
        self.qapp = QApplication.instance() or QApplication(sys.argv)   # 처음 고르기 창이 먼저 만들었으면 그걸 씀
        try:                                   # 창 아이콘 (엘리시아)
            from PyQt5.QtGui import QIcon
            ip = os.path.join(BASE, "icon.ico")
            if os.path.exists(ip):
                self.qapp.setWindowIcon(QIcon(ip))
        except Exception:
            pass
        self.qapp.setQuitOnLastWindowClosed(False)
        self.qapp.aboutToQuit.connect(lambda: self.close_player())
        self.qapp.aboutToQuit.connect(lambda: self.usage_stop())          # 펫을 끄면 Claude 사용량 위젯도 같이 끔
        QTimer.singleShot(1500, self.setup_tray)          # 작업표시줄 알림 영역 아이콘
        QTimer.singleShot(2200, self.passthru_start)       # 터치 OFF · 투명도 · 떠 있는 버튼
        self.qapp.aboutToQuit.connect(lambda: self.ask_log("quit: 프로그램 종료"))     # 펫을 끄면 숨김 플레이어(노래)도 같이 끔
        # 같은 펫 프로그램이 두 번 켜지지 않게 (두 번째로 켠 건 바로 꺼지고, 먼저 켠 애들이 '뿅' 하고 다시 등장)
        from PyQt5.QtNetwork import QLocalServer, QLocalSocket
        self.lock_name = "desktop_pet_" + "".join(ch for ch in os.path.basename(BASE) if ch.isalnum() or ch in "_-")
        sock = QLocalSocket()
        sock.connectToServer(self.lock_name)
        if sock.waitForConnected(400):
            sock.write(b"show"); sock.flush(); sock.waitForBytesWritten(400)
            sys.exit(0)
        QLocalServer.removeServer(self.lock_name)
        self.lock = QLocalServer()
        self.lock.listen(self.lock_name)
        self.lock.newConnection.connect(self.on_lock_conn)
        self.chars = {}
        if os.path.isdir(CHARS_DIR):
            for name in sorted(os.listdir(CHARS_DIR)):
                if name.startswith("_"):
                    continue
                d = os.path.join(CHARS_DIR, name)
                if not os.path.exists(os.path.join(d, "0.png")):
                    continue
                rope = {}
                try:
                    raw = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
                    meta = {int(k): v for k, v in raw["frames"].items()}
                    rope = raw.get("rope", {})
                except Exception:
                    meta = {}
                try:
                    label = open(os.path.join(d, "name.txt"), encoding="utf-8").read().strip()
                except Exception:
                    label = name
                self.chars[name] = {"dir": d, "meta": meta, "label": label, "rope": rope,
                                    "persona": persona_of(name, d)}
        # 의상 폴더(이름@의상)는 한 캐릭터로 묶음
        self.outfits = {}
        for name in list(self.chars):
            if "@" in name:
                base, of = name.split("@", 1)
                self.outfits.setdefault(base, {})[of] = self.chars.pop(name)
        for base in self.outfits:                # 맨 폴더(이름만)는 '기본 의상'으로 묶음
            if self.chars.get(base) and "basic" not in self.outfits[base]:
                self.outfits[base]["basic"] = self.chars[base]
        for base, ofs in self.outfits.items():
            order = [o for o in OUTFIT_NAME if o in ofs] + sorted(o for o in ofs if o not in OUTFIT_NAME)
            self.outfits[base] = {o: ofs[o] for o in order}
            self.chars[base] = None                      # 설정을 읽은 뒤 채움
        self.outfit = {}
        # 한 번에 한 캐릭터만 (실행할 때 이름을 넘기면 그 캐릭터: buddies.py monkey)
        arg = sys.argv[1] if len(sys.argv) > 1 else ""
        try:                                   # roster.txt 가 있으면 그 명단이 우선 (업데이트로 새 캐릭터가 들어오면 여기만 바뀜)
            with open(os.path.join(BASE, "roster.txt"), encoding="utf-8") as roster:
                rt = roster.read().strip()
            if rt:
                arg = rt
        except Exception:
            pass
        # "bingha+rin" 처럼 + 로 이으면 그 캐릭터들이 한 화면에서 같이 놀아요 (합본)
        # 끝에 ! 가 붙으면 캐릭터마다 딱 한 명씩만 (예: "rin+riko+shibuki+nana!")
        self.one_each = arg.endswith("!")
        arg = arg.rstrip("!")
        self.team = [n for n in arg.split("+") if n in self.chars] if ("+" in arg or self.one_each) else []
        if len(self.team) < 2 and not (self.one_each and self.team):
            self.team = []
        self.roster = self.team[:]                 # 이 패키지에 들어 있는 전원
        # 그룹별 합동 장면: chars/_scenes_<그룹> (합본) 또는 chars/_scenes (그룹 하나짜리 패키지)
        self.scene_sets = {}
        for sq, mem in SQUADS.items():
            if not all(c in self.roster for c in mem):
                continue
            cands = [os.path.join(CHARS_DIR, "_scenes_" + sq)]
            if set(self.roster) <= set(mem):
                cands.append(os.path.join(CHARS_DIR, "_scenes"))
            for sd in cands:
                try:
                    meta = {int(k): v for k, v in json.load(open(os.path.join(sd, "meta.json"))).items()}
                except Exception:
                    continue
                self.scene_sets[sq] = {"dir": sd, "meta": meta,
                                       "scenes": {"abyss": SCENES_ABYSS, "universe": SCENES_UNIVERSE,
                                                  "gen1": SCENES_GEN1}.get(sq, SCENES)}
                break
        self.scene = None
        self.mode = self.team[0] if self.team else (arg if arg in self.chars else next((c for c in ("elysia", "bingha") if c in self.chars), next(iter(self.chars))))
        from collections import OrderedDict
        self._pix = OrderedDict()          # 원본 그림 (최근에 쓴 것만 기억 — 메모리 폭주 방지)
        self._spix = OrderedDict()         # 크기에 맞춰 줄인 그림
        # 설정 저장 파일 (크기 등) — 다음에 켜도 그대로
        self.cfg_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0] if sys.argv[0].endswith(".py") else ENTRY_SCRIPT)), "settings.json")
        try:
            with open(self.cfg_path, encoding="utf-8") as settings:
                self.cfg = json.load(settings)
        except Exception:
            self.cfg = {}
        self.plugins = PluginLibrary(os.path.join(BASE, "plugins"), _crash_write)
        self.size = int(self.cfg.get("size", 100))
        SCREEN["name"] = self.cfg.get("screen")
        CHAR_SCREEN.clear(); CHAR_SCREEN.update(self.cfg.get("char_screen", {}))
        SHAKE["k"] = float(self.cfg.get("shake", 0.4))
        BUBBLE_PX["px"] = int(self.cfg.get("bubble_px", 14))
        for base, ofs in self.outfits.items():
            cur = self.cfg.get("outfit", {}).get(base)
            self.apply_outfit(base, cur if cur in ofs else next(iter(ofs)))
        # 합본: 지난번에 골라 둔 멤버(그룹만/인물별)로 시작
        if self.one_each and self.roster:
            act = [c for c in self.cfg.get("active", []) if c in self.roster]
            if not act and "active" not in self.cfg:
                first = next((c for c in ("elysia", "bingha") if c in self.roster), None)
                act = [first] if first else []        # 처음 켤 때는 엘리시아만 (나머지는 환경설정 → 캐릭터에서)
            self.team = act or self.roster[:]
            seen = self.cfg.get("seen_roster")
            self.new_friends = [c for c in self.roster if seen is not None and c not in seen]
            if seen is None or self.new_friends:
                self.cfg["seen_roster"] = self.roster[:]
        self.update_squad()
        self.climb_windows = bool(self.cfg.get("climb", True))
        self.on_top = bool(self.cfg.get("on_top", True))
        self.settings_dlg = None
        self.buddies, self.windows = [], []
        self.hit_cool = {}
        if getattr(self, "new_friends", None):
            QTimer.singleShot(9000, self.announce_new_friends)
        self.scan()
        n0 = len(self.live_team()) if (self.one_each and self.team) else min(START_COUNT, self.cap())
        for i in range(n0):
            QTimer.singleShot(i * 600, self.add)
        self.group = None
        self.pending = set()
        self.substeps = max(1, min(3, int(self.cfg.get("fps", 1))))   # 1=60fps(기본) 2=30fps 3=20fps
        self.t = QTimer(timeout=self.tick); self.t.start(TICK * self.substeps)
        self.wd = QTimer(timeout=self.watchdog); self.wd.start(10000)
        self.rt = QTimer(timeout=self.rotate_live); self.rt.start(8 * 60 * 1000)   # 고른 친구가 최대 인원보다 많으면 8분마다 교대
        self.alarm_done = {}                       # 오늘 이미 울린 알림
        self.ck = QTimer(timeout=self.clock); self.ck.start(15000)
        # 4인 모드: 내버려 둬도 1~3분마다 넷이 모여 단체 놀이·합동 장면을 함
        self.gt = QTimer(timeout=self.auto_group); self.gt.setSingleShot(True)
        if self.one_each and len(self.team) >= 3:
            self.gt.start(random.randint(40000, 70000))
        self.w = QTimer(timeout=self.scan); self.w.start(400)
        self.topt = QTimer(timeout=self.keep_on_top); self.topt.start(1000)
        self.idlt = QTimer(timeout=self.idle_tick); self.idlt.start(1000)
        self.curt = QTimer(timeout=self.cursor_tick); self.curt.start(250)     # 커서 놀이 + 호감도 저장
        self.mint = QTimer(timeout=self.minute_tick); self.mint.start(30000)   # 기념일·예약 알림·컴퓨터 상태
        QTimer.singleShot(9000, lambda: self.cfg.get("usage_widget") and self.open_usage(auto=True))   # 켜 두었던 사용량 위젯 다시 띄우기
        QTimer.singleShot(12000, lambda: self.cfg.get("pole_corner") and self.pole_corner_set(True))   # 구석 폴댄스 켜 두었으면 이어서
        self.kanit = QTimer(timeout=self.kani_tick); self.kanit.start(3000)   # 카니는 모몽가 곁으로
        QTimer.singleShot(15000, self.minute_tick)
        QTimer.singleShot(5000, self.rename_shortcuts)   # 다른 '맨 위' 창에 밀려도 다시 위로
        self.r = QTimer(timeout=self.surprise); self.r.start(40000)
        self.d = QTimer(timeout=self.duo_tick); self.d.start(1500)
        # 가끔 알아서 옷 갈아입기 (설정에서 끌 수 있음)
        self.oc = QTimer(timeout=self.auto_outfit); self.oc.start(60000)
        self.outfit_t = 0
        # Claude 연결(MCP)
        self.cmdq = queue.Queue()
        self.uiq = queue.Queue()
        self.mcp_srv, self.mcp_file = None, None
        self.cq = QTimer(timeout=self.pump_cmds); self.cq.start(80)
        if self.cfg.get("mcp", True):
            self.start_bridge()
        self.qapp.aboutToQuit.connect(self.stop_bridge)
        # 자동 업데이트: 켜고 1분 뒤, 그 뒤로 3시간마다 확인
        self.upd_busy = False
        self.upd_msg = ""
        QTimer.singleShot(60000, self.update_tick)
        self.ut = QTimer(timeout=self.update_tick); self.ut.start(3 * 3600 * 1000)

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

    def char_prompt(self, char, q):
        lab = self.chars[char]["label"]
        grp = next((SQUAD_NAME.get(sq, sq) for sq, m in SQUADS.items() if char in m), "")
        alt = f"{char}@{self.outfit.get(char)}" in CHAR_BIO      # 변신·이격 모습이면 기본 모습 수다 대사는 빼기
        lines = list(dict.fromkeys([it[5][0] for it in (self.chars[char].get("persona") or [])][:8]
                                   + ([] if alt else self.CHAT.get(char, [])[:3])))
        of = OUTFIT_NAME.get(self.outfit.get(char), "") if char in self.outfits else ""
        sq = next((sq for sq, m in SQUADS.items() if char in m), "")
        fr = next((fn for fn, sqs in FRANCHISE if sq in sqs), "")
        nikke = sq in ("nikke", "honkai")          # 게임 캐릭터 (방송인 아님)
        who = f"'{lab}'" + (f"({fr}" + (f" {grp}" if grp and grp != lab and grp != fr and not nikke else "") + ")" if fr else "")
        key = f"{char}@{self.outfit.get(char)}"
        bio = CHAR_BIO.get(key) or CHAR_BIO.get(char, "")
        call = self.cfg.get("my_name") or CHAR_CALL.get(char) or DEFAULT_CALL.get(sq)
        alv = self.aff_level(self.aff(char))
        rel = ["아직 처음 만난 사이라 살짝 낯가림", "친구 사이", "친한 친구 사이라 편하게", "단짝이라 아주 다정하게", "나를 제일 좋아하는 최애 사이라 애정 듬뿍"][alv]
        return (f"너는 내 바탕화면에 사는 데스크톱 펫 {who}야." + (f" 지금 모습은 '{of}'." if of else "")
                + f" 나와의 사이: {AFF_NAME[alv]}({rel})."
                + (f" 캐릭터 설명: {bio}" if bio else "")
                + (" 평소 말버릇: " + " / ".join(lines) if lines else "") + " "
                + (f"나를 부를 때는 '{call}'(이)라고 불러 줘. " if call else
                   "나를 부를 때 함장·주인님 같은 특별한 호칭은 쓰지 말고, 그 캐릭터가 친구에게 말하듯 자연스럽게 대해 줘. ")
                + f"내 질문에 {lab}의 말투와 성격으로 대답해 줘. 다른 친구들과 말투가 겹치지 않게 {lab}만의 말버릇을 살려 줘. "
                + ("게임 캐릭터를 팬이 만든 펫으로서 귀엽게 롤플레이해 주면 돼. " if nikke else
                   "실제 방송인 본인이 아니라 팬이 만든 펫 캐릭터로서 귀엽게 롤플레이해 주면 돼. ")
                + f"그리고 대답을 마치기 전에 꼭 desktop-pet 의 pet_say 도구를 who='{lab}' 로 불러서, 대답의 핵심을 {lab} 말투로 1~3문장(150자 이내)으로 줄여 내 화면 속 {lab} 말풍선에 띄워 줘."
                f"\n\n내 질문: {q}")

    def claude_cli(self):
        """설치된 Claude Code(claude.exe) 찾기"""
        cand = [shutil.which("claude"), shutil.which("claude.exe"),
                os.path.join(os.path.expanduser("~"), ".local", "bin", "claude.exe"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "claude", "claude.exe"),
                os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd")]
        return next((c for c in cand if c and os.path.exists(c)), None)

    def codex_cli(self):
        """설치된 ChatGPT Codex CLI(codex) 찾기"""
        cand = [shutil.which("codex"), shutil.which("codex.cmd"), shutil.which("codex.exe"),
                os.path.join(os.environ.get("APPDATA", ""), "npm", "codex.cmd"),
                os.path.join(os.path.expanduser("~"), ".local", "bin", "codex.exe")]
        return next((c for c in cand if c and os.path.exists(c)), None)

    def ask_engine(self):
        """물어보기에 쓸 AI: 고른 게 있으면 그것, 없으면 깔린 것 중에서"""
        e = self.cfg.get("ask_engine")
        if e in ("claude", "codex", "gemini"):
            return e
        if self.claude_cli():
            return "claude"
        if self.codex_cli():
            return "codex"
        return "gemini" if self.cfg.get("gemini_key") else "claude"

    def ask_ready(self):
        e = self.ask_engine()
        return bool(self.claude_cli() if e == "claude" else self.codex_cli() if e == "codex" else self.cfg.get("gemini_key"))

    def plain_prompt(self, char, q, room):
        """ChatGPT·Gemini 용 프롬프트 (펫 조종 도구 없이 대답만) + 이 방에서 나눈 최근 이야기"""
        lab = self.chars[char]["label"]
        base = self.char_prompt(char, q).split("그리고 대답을 마치기 전에")[0]
        hist = self.cfg.get("ask_hist", {}).get(room, [])[-6:]
        h = ""
        if hist:
            me = self.cfg.get("my_name") or "나"
            h = "앞에서 나눈 이야기(기억해 두고 이어서 대답해 줘):\n" + "\n".join(f"{me}: {x[1]}\n{x[0]}: {x[2]}" for x in hist) + "\n\n"
        return (base + f"대답은 바탕화면 말풍선에 그대로 들어가니까, 마크다운·목록·그림 이모지 없이 {lab} 말투로 1~3문장(150자 이내)만 써 줘. "
                "♪ ♥ ~ ☆ 같은 문장 기호는 이모지가 아니니까 그 캐릭터 말버릇이면 꼭 살려서 써 줘. 파일을 읽거나 고치거나 명령을 실행하지는 마. "
                + ("최신 정보가 필요하면 인터넷 검색을 써도 돼. " if self.cfg.get("ask_web") else "")
                + f"(지금 시각: {datetime.datetime.now():%Y-%m-%d %H:%M})\n\n" + h + "내 질문: " + q)

    def run_codex(self, prompt, work):
        """ChatGPT Codex CLI 를 창 없이 실행 → (대답, 오류)"""
        import subprocess
        exe = self.codex_cli()
        if not exe:
            return "", "codex 없음"
        last = os.path.join(work, "codex_last.txt")
        try:
            os.remove(last)
        except Exception:
            pass
        args = [exe, "exec", "--skip-git-repo-check", "--sandbox", "read-only", "-o", last, "-"]
        r = subprocess.run(args, input=prompt.encode("utf-8"), capture_output=True, cwd=work, timeout=300,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        out = ""
        try:
            out = open(last, encoding="utf-8", errors="replace").read().strip()
        except Exception:
            out = r.stdout.decode("utf-8", "replace").strip()
        err = "" if out else (r.stderr.decode("utf-8", "replace").strip()[-300:] or f"exit {r.returncode}")
        return out, err

    def run_gemini(self, prompt):
        """Gemini API(구글 AI 스튜디오 키)로 대답 받기 → (대답, 오류). 무료 키는 검색이 안 되면 검색 없이 다시"""
        import urllib.request, urllib.error
        key = (self.cfg.get("gemini_key") or "").strip()
        if not key:
            return "", "Gemini API 키 없음"
        models = [m for m in [self.cfg.get("gemini_model"), "gemini-3.5-flash", "gemini-3-flash-preview", "gemini-2.5-flash"] if m]
        err = ""
        for m in models:
            for web in ([True, False] if self.cfg.get("ask_web") else [False]):
                body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
                if web:
                    body["tools"] = [{"google_search": {}}]
                req = urllib.request.Request(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                    data=json.dumps(body).encode("utf-8"),
                    headers={"Content-Type": "application/json", "x-goog-api-key": key})
                try:
                    with urllib.request.urlopen(req, timeout=120) as r:
                        j = json.loads(r.read().decode("utf-8"))
                    parts = ((j.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
                    out = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
                    if out:
                        return out, ""
                    err = "빈 대답"
                except urllib.error.HTTPError as e:
                    try:
                        msg = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
                    except Exception:
                        msg = ""
                    err = f"{e.code} {msg}"[:200]
                    if e.code in (401, 403) and "API key" in msg:
                        return "", "API 키가 맞지 않아요"
                    if e.code == 404:
                        break                                    # 없는 모델 → 다음 모델
                except Exception as e:
                    err = str(e)[:200]
        return "", err

    def hidden_prompt(self, char, q, extra=None):
        lab = self.chars[char]["label"]
        base = self.char_prompt(char, q).split("그리고 대답을 마치기 전에")[0]
        others = ", ".join(self.chars[c]["label"] for c in (self.roster or [self.mode]) if c != char)
        room = ("이 대화방은 바탕화면 친구들 모두와 함께 쓰는 방이야. 앞에서 다른 친구가 한 말도 기억하고 이어서 대답해 줘. 이번엔 네가 대답할 차례야. "
                if self.cfg.get("ask_room", "one") == "one" else "")
        return (base + room + f"대답은 바탕화면 말풍선에 그대로 들어가니까, 마크다운·목록·그림 이모지 없이 {lab} 말투로 1~3문장(150자 이내)만 써 줘. ♪ ♥ ~ ☆ 같은 문장 기호는 이모지가 아니니까 그 캐릭터 말버릇이면 꼭 살려서 써 줘. "
                + self.power_note(extra)
                + ("최신 정보가 필요하면 인터넷 검색(WebSearch/WebFetch)을 써도 돼. " if self.cfg.get("ask_web") else "")
                + (f"화면에는 친구들({others})도 있어. " if others else "")
                + "내가 다른 친구에게 말을 시키거나, 동작·춤·잠자기·합동 장면·단체 놀이·옷 갈아입기·멤버 바꾸기·노래 틀기를 원하면 "
                  "desktop-pet 도구(pet_status, pet_say, pet_action, pet_persona, pet_scene, pet_group_play, pet_outfit, pet_team, pet_notify, pet_music, pet_remind)로 실제로 시켜 줘. "
                  "'몇 시에 알려 줘', '몇 분 뒤에 알려 줘' 같은 부탁은 pet_remind 로 예약해 줘 (지금 시각: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M") + "). "
                  "노래를 추천해 달라거나 조건에 맞는 노래를 틀어 달라고 하면, 인터넷 검색으로 실제 유튜브 영상 링크를 찾아서(링크를 지어내지 말 것) "
                  "pet_music 의 songs=[{title, url}] 와 name(목록 이름)으로 넘겨 저장·재생해 줘. 검색을 못 쓰면 곡 제목만 추천하고 'AI 연결 탭에서 인터넷 검색을 켜 주면 바로 틀어 줄게'라고 말해 줘. "
                  f"단, 네({lab}) 대답 말풍선은 펫 프로그램이 알아서 띄우니까 pet_say 로 {lab} 에게는 보내지 마."
                "\n\n내 질문: " + q)

    def ask_mcp_config(self):
        """숨겨서 물을 때 Claude Code 가 펫을 조종할 수 있게 desktop-pet 연결 설정 파일을 만들어 둠"""
        try:
            dst = os.path.join(MCP_HOME, "pet_mcp.py")
            if not os.path.exists(dst):
                os.makedirs(MCP_HOME, exist_ok=True); shutil.copy(os.path.join(BASE, "pet_mcp.py"), dst)
            exe = sys.executable
            if exe.lower().endswith("pythonw.exe") and os.path.exists(exe[:-11] + "python.exe"):
                exe = exe[:-11] + "python.exe"
            path = os.path.join(MCP_HOME, "ask", "mcp.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            json.dump({"mcpServers": {"desktop-pet": {"command": exe, "args": [dst]}}},
                      open(path, "w", encoding="utf-8"), ensure_ascii=False)
            return path
        except Exception as e:
            self.ask_log(f"mcp config error {e}")
            return None

    def chat_log(self, lab, q, a):
        """나눈 대화를 펫 폴더의 '대화기록.txt' 에 차곡차곡"""
        try:
            me = self.cfg.get("my_name") or "나"
            with open(os.path.join(BASE, "대화기록.txt"), "a", encoding="utf-8-sig") as f:
                f.write(f"[{datetime.datetime.now():%m/%d %H:%M}] {me} → {lab}: {q}\n{lab}: {a}\n\n")
        except Exception:
            pass

    def merged_power(self, extra=None):
        """설정의 작업 권한 + (파일 던지기로) 이번 한 번만 허락한 폴더·권한"""
        power, dirs = self.ask_power_dirs()
        if extra:
            rank = {"none": 0, "read": 1, "files": 2, "full": 3}
            dirs = dirs + [d for d in extra.get("dirs", []) if d not in dirs]
            if rank.get(extra.get("power", "none"), 0) > rank.get(power, 0):
                power = extra["power"]
        return power, dirs

    def ask_power_dirs(self):
        power = self.cfg.get("ask_power", "none")
        dirs = [d for d in self.cfg.get("ask_dirs", []) if os.path.isdir(d)]
        if power == "files" and not dirs:
            power = "none"                               # 폴더를 안 골랐으면 파일 권한도 없음
        return power, dirs

    def power_note(self, extra=None):
        power, dirs = self.merged_power(extra)
        if power == "none":
            return "파일을 읽거나 명령을 실행하지는 마. "
        where = ", ".join(dirs)
        if power == "read":
            return f"이 폴더들 안의 파일은 읽기만 해도 돼(고치거나 새로 만들거나 명령 실행은 하지 마): {where}. "
        t = (f"내가 부탁하면 이 폴더들 안의 파일은 읽고, 고치고, 새로 만들어도 돼: {where}. " if dirs else "")
        t += ("그 폴더 밖의 파일은 건드리지 마. " if power == "files" else
              "부탁하면 명령 실행(프로그램·파일 열기, 변환 같은 작업)도 해도 돼. ")
        t += ("기존 파일을 고치거나 덮어쓰기 전에는 같은 폴더에 '원래이름.bak' 으로 백업부터 해 줘. "
              "파일·폴더 지우기, 프로그램 설치, 시스템·보안 설정 바꾸기, 돈이 드는 일, 비밀번호 입력 같은 되돌리기 어려운 일은 하지 말고 방법만 말해 줘. "
              "다 하면 무엇을 했는지 말풍선에 짧게 알려 줘. ")
        return t

    def ask_hidden(self, b, q, extra=None):
        """Claude Code 를 창 없이 실행해서 대답을 받아 말풍선에 띄움 (구독 사용량 안에서)"""
        import subprocess
        exe = self.claude_cli()
        lab = self.chars[b.char]["label"]
        engine = self.ask_engine()
        if engine == "codex" and not self.codex_cli():
            self.force_say(b, "ChatGPT(Codex)가 안 깔려 있어요… 환경설정 → AI 연결 → 'ChatGPT·Gemini 설치·연결 방법'을 봐 주세요!", raw=True)
            return
        if engine == "gemini" and not self.cfg.get("gemini_key"):
            self.force_say(b, "Gemini API 키가 없어요… 환경설정 → AI 연결에서 키를 넣어 주세요! (구글 AI 스튜디오에서 무료로 받을 수 있어요)", raw=True)
            return
        if engine == "claude" and not exe:
            self.force_say(b, "Claude Code 가 안 깔려 있어요… 환경설정 → AI 연결에서 'Claude 창 열기'로 바꾸거나 Claude Code 를 깔아 주세요!")
            return
        room = "_room" if self.cfg.get("ask_room", "one") == "one" else b.char   # 한 방(전원 공유) / 캐릭터마다 따로
        if getattr(self, "_ask_busy", {}).get(room):          # 같은 방에서 대답 중이면 차례 기다리기
            self._ask_wait = getattr(self, "_ask_wait", []) + [(b, q, extra)]
            b.say("잠깐만~ 앞에 질문 대답 중이야. 끝나면 바로 대답할게!", 10 ** 9, force=True)
            b.say_lock = 10 ** 9
            return
        self._ask_busy = {**getattr(self, "_ask_busy", {}), room: True}
        tl = THINK_LINES.get(f"{b.char}@{self.outfit.get(b.char)}") or THINK_LINES.get(b.char) or ["음… 생각 중…"]
        b.say(random.choice(tl), 10 ** 9, force=True)
        b.say_lock = 10 ** 9
        sess = self.cfg.get("ask_sessions", {}).get(room)
        work = os.path.join(MCP_HOME, "ask"); os.makedirs(work, exist_ok=True)
        prompt = self.hidden_prompt(b.char, q, extra)
        shot = None if (extra or engine != "claude") else self.grab_screen_for_ask(b, q, work)
        if shot:
            prompt += (f" 참고로 지금 내 화면을 캡처해 뒀어: {shot} (Read 도구로 열어 보고, 화면 얘기가 나오면 그걸 보고 대답해 줘."
                       " 화면에 보이는 개인 정보는 말풍선에 그대로 옮기지 마.)")
        args = [exe, "-p", prompt, "--output-format", "json"]
        mcfg = self.ask_mcp_config() if self.cfg.get("ask_control", True) else None
        tools = (["mcp__desktop-pet"] if mcfg else []) + (["WebSearch", "WebFetch"] if self.cfg.get("ask_web") else [])
        if shot:
            tools += ["Read"]
        power, dirs = self.merged_power(extra)
        if power == "read":                              # 던진 파일 읽기만
            tools += ["Read", "Glob", "Grep", "LS"]
            for d in dirs:
                args += ["--add-dir", d]
        if power in ("files", "full"):                   # 작업 권한: 고른 폴더 안 파일 읽기·고치기
            tools += ["Read", "Edit", "MultiEdit", "Write", "Glob", "Grep", "LS"]
            for d in dirs:
                args += ["--add-dir", d]
        if power == "full":                              # + 명령 실행 (프로그램 켜기 등)
            tools += ["Bash", "PowerShell"]
        if mcfg:                                         # 다른 친구들에게도 시킬 수 있게
            args += ["--mcp-config", mcfg, "--strict-mcp-config"]
        if tools:
            args += ["--allowedTools", ",".join(tools)]
        if sess:
            args += ["--resume", sess]                      # 앞에서 나눈 이야기를 기억 (한 방이면 모두의 이야기)
        self.ask_log(f"hidden ask {lab}: {q}")
        if engine != "claude":
            pprompt = self.plain_prompt(b.char, q, room)
            ename = "ChatGPT" if engine == "codex" else "Gemini"
        def work_thread():
            out, err, sid = "", "", None
            if engine != "claude":
                try:
                    out, err = self.run_codex(pprompt, work) if engine == "codex" else self.run_gemini(pprompt)
                except subprocess.TimeoutExpired:
                    err = "시간 초과"
                except Exception as e:
                    err = str(e)
                self.claude_history("물어보기(" + ename + ")", lab, q, out, err)
                def done2():
                    self._ask_busy.pop(room, None)
                    wait = [w for w in getattr(self, "_ask_wait", []) if w[0] in self.buddies]
                    if wait:
                        self._ask_wait = wait[1:]
                        QTimer.singleShot(300, lambda w=wait[0]: self.ask_hidden(*w))
                    else:
                        self._ask_wait = []
                    if out:
                        hs = self.cfg.setdefault("ask_hist", {}).setdefault(room, [])
                        hs.append([lab, q[:300], out[:400]]); del hs[:-6]
                        self.save_cfg()
                        self.chat_log(lab, q, out)
                        self.add_aff(b, 4)
                    if b not in self.buddies:
                        return
                    b.say_lock = 0
                    if not out:
                        self.ask_log(f"hidden error ({ename}): {err}")
                        low = (err or "").lower()
                        if engine == "codex" and ("login" in low or "auth" in low or "401" in low or "sign in" in low):
                            msg = "ChatGPT 로그인이 필요해요! PowerShell 에서  codex login  을 한 번 실행해 주세요."
                        elif engine == "gemini" and ("키" in err or "key" in low):
                            msg = "Gemini API 키를 확인해 주세요! (환경설정 → AI 연결)"
                        elif "429" in low or "quota" in low or "limit" in low:
                            msg = f"{ename} 사용량이 잠깐 다 찼어요… 조금 뒤에 다시 물어봐 주세요!"
                        else:
                            msg = f"앗, 대답을 못 받았어요… ({(err or '')[:60]})"
                        self.force_say(b, msg, raw=True)
                        return
                    self.ask_log(f"hidden answer {lab} ({ename}): {out[:200]}")
                    self.force_say(b, out[:300] + ("…" if len(out) > 300 else ""))
                    b.set("happy", 60) if b.surface else None
                    if extra and extra.get("done"):
                        extra["done"](out)
                self.uiq.put(done2)
                return
            try:
                r = subprocess.run(args, capture_output=True, cwd=work, timeout=(600 if power != "none" else 240),
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                txt = r.stdout.decode("utf-8", "replace").strip()
                try:
                    j = json.loads(txt)
                    out, sid = (j.get("result") or "").strip(), j.get("session_id")
                    if j.get("is_error"):
                        err = out or "error"
                except Exception:
                    out = txt
                if r.returncode != 0 and not out:
                    err = r.stderr.decode("utf-8", "replace").strip()[-300:] or f"exit {r.returncode}"
            except subprocess.TimeoutExpired:
                err = "시간 초과"
            except Exception as e:
                err = str(e)
            self.claude_history("물어보기", lab, q, out, err)
            def done():
                self._ask_busy.pop(room, None)
                wait = [w for w in getattr(self, "_ask_wait", []) if w[0] in self.buddies]
                if wait:                                         # 기다리던 다음 질문
                    self._ask_wait = wait[1:]
                    QTimer.singleShot(300, lambda w=wait[0]: self.ask_hidden(*w))
                else:
                    self._ask_wait = []
                if sid:
                    self.cfg.setdefault("ask_sessions", {})[room] = sid; self.save_cfg()
                if out:
                    self.chat_log(lab, q, out)
                    self.add_aff(b, 4)
                if b not in self.buddies:
                    return
                b.say_lock = 0
                if err and not out:
                    self.ask_log(f"hidden error: {err}")
                    if sess and "session" in err.lower():          # 예전 대화가 없어졌으면 새로 시작
                        self.cfg.get("ask_sessions", {}).pop(room, None); self.save_cfg()
                    low = err.lower()
                    msg = ("Claude Code 로그인이 필요해요! PowerShell 에서 claude 를 한 번 실행해서 로그인해 주세요."
                           if "login" in low or "auth" in low or "credit" in low else f"앗, 대답을 못 받았어요… ({err[:60]})")
                    self.force_say(b, msg, raw=True)
                    return
                self.ask_log(f"hidden answer {lab}: {out[:200]}")
                self.force_say(b, out[:300] + ("…" if len(out) > 300 else ""))
                b.set("happy", 60) if b.surface else None
                if extra and extra.get("done"):
                    extra["done"](out)
            self.uiq.put(done)
        threading.Thread(target=work_thread, daemon=True).start()

    def ask_claude(self, b):
        """캐릭터를 따닥 → 질문 입력 → Claude 새 대화를 그 캐릭터 설정으로 열기"""
        from PyQt5.QtWidgets import QInputDialog
        from PyQt5.QtGui import QDesktopServices
        from PyQt5.QtCore import QUrl
        import urllib.parse
        if b not in self.buddies or getattr(self, "_asking", False):
            return
        lab = self.chars[b.char]["label"]
        self._asking = True
        try:
            hk = f"{b.char}@{self.outfit.get(b.char)}"
            b.say(random.choice(ASK_HELLO.get(hk) or ASK_HELLO.get(b.char) or [f"{lab}한테 궁금한 거 있어?", "응? 뭐든 물어봐!"]), 200)
            dlg = QInputDialog()
            dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowStaysOnTopHint)
            dlg.setWindowTitle(f"{lab}에게 물어보기")
            eng = self.ask_engine()
            hidden = eng == "gemini" or (self.cfg.get("ask_mode") or ("hidden" if self.ask_ready() else "window")) == "hidden"
            dlg.setLabelText(f"{lab}에게 물어볼 말 " + ("(대답은 말풍선으로 와요)" if hidden else "(ChatGPT 창이 열려요)" if eng == "codex" else "(Claude 창이 열려요)"))
            dlg.resize(460, 120)
            g = b.scr()
            dlg.move(int(max(g.left(), min(g.right() - 480, b.cx - 230))), int(max(g.top(), b.fy - 160)))
            if not dlg.exec_():
                return
            q = dlg.textValue().strip()
            if not q:
                return
            if hidden:
                self.ask_hidden(b, q)
                return
            enc = urllib.parse.quote(self.char_prompt(b.char, q), safe="")
            if eng == "codex":                               # ChatGPT 창으로
                QDesktopServices.openUrl(QUrl.fromEncoded(("https://chatgpt.com/?q=" + urllib.parse.quote(self.char_prompt(b.char, q).split("그리고 대답을 마치기 전에")[0] + "\n\n내 질문: " + q, safe="")).encode("ascii")))
                if b in self.buddies:
                    b.say("ChatGPT 한테 물어보고 올게~", 150)
                return
            ok = False
            if self.cfg.get("ask_where", "app") == "app":
                ok = QDesktopServices.openUrl(QUrl.fromEncoded(("claude://claude.ai/new?q=" + enc).encode("ascii")))
            if not ok:
                QDesktopServices.openUrl(QUrl.fromEncoded(("https://claude.ai/new?q=" + enc).encode("ascii")))
            if b in self.buddies:
                b.say("Claude 한테 물어보고 올게~", 150)
            if self.cfg.get("ask_send", True):
                self._send_clicked = False
                self.ask_log(f"opened ask for {lab}")
                QTimer.singleShot(1200, self.auto_send)
        finally:
            self._asking = False

    def claude_history(self, kind, who, q, out, err=""):
        """Claude Code 에 보낸 것(인풋)과 받은 답(아웃풋)을 날짜별 파일로 남김 → 트레이 'Claude 이력 보기'"""
        if not self.cfg.get("claude_history", True):
            return
        try:
            d = os.path.join(BASE, "claude_history")
            os.makedirs(d, exist_ok=True)
            now = datetime.datetime.now()
            row = {"t": now.isoformat(timespec="seconds"), "kind": kind, "who": who,
                   "q": str(q or "").strip(), "out": str(out or "").strip(), "err": str(err or "")}
            with open(os.path.join(d, f"{now:%Y-%m-%d}.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def open_claude_history(self):
        """Claude 이력 관리 창 (검색·날짜/종류 필터·복사·삭제·내보내기)"""
        d = getattr(self, "hist_dlg", None)
        try:
            if d is not None and d.isVisible():
                d.reload(); d.raise_(); d.activateWindow()
                return
        except RuntimeError:
            pass
        try:
            self.hist_dlg = HistoryDialog(self)
            self.hist_dlg.show(); self.hist_dlg.raise_(); self.hist_dlg.activateWindow()
        except Exception:
            import traceback
            _crash_write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] 이력 창 오류\n{traceback.format_exc()}")

    def open_claude_history_dir(self):
        d = claude_hist_dir()
        try:
            os.makedirs(d, exist_ok=True)
            os.startfile(d)
        except Exception:
            pass

    def ask_log(self, t):
        try:
            with open(os.path.join(BASE, "ask.log"), "a", encoding="utf-8") as f:
                f.write(f"{datetime.datetime.now():%H:%M:%S} {t}\n")
        except Exception:
            pass

    def auto_send(self, waited=0):
        """맨 앞 창이 Claude(앱 또는 claude.ai 브라우저 탭)일 때만 입력칸을 눌러 커서를 넣고 Enter.
        다른 창이 앞에 있으면 아무것도 안 누름 (엉뚱한 곳에 Enter 가 들어가지 않게)"""
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
        except Exception:
            return
        hwnd = user32.GetForegroundWindow()
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        exe = ""
        try:
            k32 = ctypes.windll.kernel32
            h = k32.OpenProcess(0x1000, False, pid.value)
            pb = ctypes.create_unicode_buffer(520); sz = wintypes.DWORD(520)
            if h and k32.QueryFullProcessImageNameW(h, 0, pb, ctypes.byref(sz)):
                exe = os.path.basename(pb.value).lower()
            if h:
                k32.CloseHandle(h)
        except Exception:
            pass
        is_claude = exe == "claude.exe" or "Claude" in buf.value
        self.ask_log(f"try{waited} title={buf.value!r} class={cls.value} exe={exe} -> {'Claude' if is_claude else 'skip'}")
        if not is_claude:
            if waited < 20:                              # 창이 뜰 때까지 최대 10초 기다림
                QTimer.singleShot(500, lambda: self.auto_send(waited + 1))
            return
        if not getattr(self, "_send_clicked", False):
            # 입력칸에 커서 넣기: 창 가운데 아래쪽(대화 입력칸 자리)을 한 번 클릭
            r = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            self._send_clicked = True
            QTimer.singleShot(2500, lambda: self._click_send(hwnd, r))   # 페이지가 다 뜰 시간
            return

    def _click_send(self, hwnd, r):
        import ctypes
        user32 = ctypes.windll.user32
        if user32.GetForegroundWindow() != hwnd:
            self.ask_log("foreground changed, skip"); return
        # 질문이 채워진 입력칸 오른쪽 아래의 보내기 버튼 대신, 입력칸 글자 위를 눌러 커서를 넣고 Enter
        w, h = r.right - r.left, r.bottom - r.top
        from ctypes import wintypes
        pts = [None, (0.5, 0.80), (0.5, 0.62)]          # 1) 그냥 Enter  2~3) 입력칸 자리 클릭 후 Enter
        def step(i=0):
            if i >= len(pts) or user32.GetForegroundWindow() != hwnd:
                self._send_clicked = False; return
            if pts[i]:
                x, y = int(r.left + w * pts[i][0]), int(r.top + h * pts[i][1])
                old = wintypes.POINT(); user32.GetCursorPos(ctypes.byref(old))
                user32.SetCursorPos(x, y)
                user32.mouse_event(0x0002, 0, 0, 0, 0); user32.mouse_event(0x0004, 0, 0, 0, 0)
                user32.SetCursorPos(old.x, old.y)
                user32.keybd_event(0x23, 0, 0, 0); user32.keybd_event(0x23, 0, 2, 0)    # End (글자 끝으로)
            user32.keybd_event(0x0D, 0, 0, 0); user32.keybd_event(0x0D, 0, 2, 0)        # Enter
            self.ask_log(f"enter #{i} {('click ' + str(pts[i])) if pts[i] else ''} (win {w}x{h})")
            QTimer.singleShot(900, lambda: step(i + 1))   # 이미 보냈으면 빈 칸이라 Enter 해도 아무 일 없음
        step()

    def claude_cfg_paths(self):
        roam = os.environ.get("APPDATA", "")
        paths = [os.path.join(roam, "Claude", "claude_desktop_config.json")]
        pk = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Packages")
        if os.path.isdir(pk):
            for d in os.listdir(pk):
                if d.lower().startswith("claude"):
                    c = os.path.join(pk, d, "LocalCache", "Roaming", "Claude")
                    if os.path.isdir(c):
                        paths.append(os.path.join(c, "claude_desktop_config.json"))
        return paths

    def mcp_state(self):
        """'ok' (이미 연결 설정 있음) / 'missing'"""
        dst = os.path.join(MCP_HOME, "pet_mcp.py")
        for path in self.claude_cfg_paths():
            try:
                ent = json.load(open(path, encoding="utf-8")).get("mcpServers", {}).get("desktop-pet")
            except Exception:
                continue
            if ent and os.path.normcase(os.path.abspath((ent.get("args") or [""])[-1])) == os.path.normcase(os.path.abspath(dst)):
                return "ok"
        return "missing"

    def _ps(self, script, timeout=15):
        import subprocess
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                               capture_output=True, text=True, timeout=timeout,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return r.stdout
        except Exception:
            return ""

    def install_mcp(self, restart=True):
        """딸깍 연결: pet_mcp.py 를 고정 위치에 두고, Claude 를 잠깐 끄고, 설정 파일에 desktop-pet 을 넣고, 다시 켬.
        (Claude 가 켜져 있는 동안 설정 파일을 고치면 Claude 가 자기 설정으로 다시 덮어써 버림)"""
        import subprocess, time
        try:
            os.makedirs(MCP_HOME, exist_ok=True)
            dst = os.path.join(MCP_HOME, "pet_mcp.py")
            shutil.copy(os.path.join(BASE, "pet_mcp.py"), dst)       # 늘 최신 서버로
            already = self.mcp_state() == "ok"
            exe = sys.executable
            if exe.lower().endswith("pythonw.exe") and os.path.exists(exe[:-11] + "python.exe"):
                exe = exe[:-11] + "python.exe"
            # 1) Claude 위치 기억해 두고 끄기
            info = self._ps("$p=Get-Process -Name claude -ErrorAction SilentlyContinue | Select-Object -First 1;"
                            "if($p){'PATH:'+$p.Path};"
                            "$a=Get-StartApps | Where-Object {$_.Name -eq 'Claude'} | Select-Object -First 1;"
                            "if($a){'APPID:'+$a.AppID}") if restart and os.name == "nt" else ""
            was_running = "PATH:" in info
            path_exe = next((l[5:].strip() for l in info.splitlines() if l.startswith("PATH:")), "")
            appid = next((l[6:].strip() for l in info.splitlines() if l.startswith("APPID:")), "")
            if already and not restart:
                return True, "이미 연결 설정이 들어 있어요."
            if was_running:
                subprocess.run(["taskkill", "/IM", "claude.exe", "/T", "/F"], capture_output=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                for _ in range(20):                                   # 완전히 꺼질 때까지
                    time.sleep(0.4)
                    if "claude" not in self._ps("Get-Process -Name claude -ErrorAction SilentlyContinue | Select -Expand Name", 5).lower():
                        break
                time.sleep(0.8)
            # 2) 설정 넣기 (다른 내용은 그대로 두고 desktop-pet 만)
            done = []
            for path in self.claude_cfg_paths():
                if not os.path.isdir(os.path.dirname(path)) and done:
                    continue
                os.makedirs(os.path.dirname(path), exist_ok=True)
                cfg = {}
                if os.path.exists(path):
                    shutil.copy(path, path + ".bak")
                    try:
                        cfg = json.load(open(path, encoding="utf-8"))
                    except Exception:
                        continue
                old = cfg.get("mcpServers", {}).get("desktop-pet")
                if not (old and (old.get("args") or [""])[-1] == dst):
                    cfg.setdefault("mcpServers", {})["desktop-pet"] = {"command": exe, "args": [dst]}
                    json.dump(cfg, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                done.append(path)
            # 3) Claude 다시 켜기
            if was_running:
                if appid:
                    subprocess.Popen(["explorer.exe", "shell:AppsFolder\\" + appid])
                elif path_exe:
                    subprocess.Popen([path_exe])
            if not done:
                return False, "Claude 설정 파일을 찾지 못했어요. Claude 데스크톱이 설치돼 있는지 확인해 주세요."
            tail = ("Claude 를 다시 켜는 중이에요. 다 켜지면 펫이 'Claude 랑 연결됐어요!' 하고 인사해요."
                    if was_running else "Claude 데스크톱을 켜면 바로 연결돼요.")
            return True, ("이미 연결돼 있어서 최신으로 정리만 했어요!\n\n" if already else "연결 완료!\n\n") + tail
        except Exception as e:
            return False, f"실패했어요: {e}"

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

    # ── 자동 업데이트 ─────────────────────────────
    def update_tick(self):
        if not os.path.exists(upd_path("update.json")):   # 설치 프로그램으로 깐 펫만 (원본·개발용 폴더는 조용히)
            return
        if upd_load("update.json").get("auto", True):
            self.check_update(quiet=True)

    def open_char_picker(self):
        """메뉴 '캐릭터 고르기': 쓰는 캐릭터만 남기고 나머지는 지우기 / 새로 받기"""
        if not os.path.exists(upd_path("update.json")):
            QMessageBox.information(None, "캐릭터 고르기", "설치 프로그램으로 깐 펫에서만 쓸 수 있어요.")
            return
        man = upd_load("manifest.json")
        sel = upd_selected()
        cur = upd_installed() if sel is None else sel
        dlg = CharPicker(man.get("files", {}), cur)
        if not dlg.exec_():
            return
        new = dlg.chosen()
        if new == cur and sel is not None:
            return
        uc = upd_load("update.json"); uc["chars"] = sorted(new); upd_save_cfg(uc)
        if self.upd_busy:
            return
        self.upd_busy = True
        who = self.buddies[0] if self.buddies else None
        if who:
            self.force_say(who, "고른 캐릭터로 바꾸는 중이야~ 잠깐만!", 6)

        def work():
            try:
                remote = upd_fetch_manifest()
                n = upd_apply(remote)
                self.upd_msg = "캐릭터 고르기 완료 (받은 파일 %d개)" % n
                self.ask_log("chars: " + self.upd_msg)
                self.uiq.put(lambda: QTimer.singleShot(1500, self.restart_self))
            except Exception as e:
                self.upd_msg = "캐릭터 받기 실패: %s" % e
                self.uiq.put(lambda: self.buddies and self.force_say(random.choice(self.buddies), self.upd_msg, 8))
            finally:
                self.upd_busy = False
        threading.Thread(target=work, daemon=True).start()

    def check_update(self, quiet=False, done_cb=None):
        """백그라운드에서 확인 → 새 버전이면 받아서 교체 → 펫 다시 켜기"""
        if self.upd_busy:
            return
        self.upd_busy = True

        def say(text, sticky=False):
            def f():
                if self.buddies:
                    self.force_say(random.choice(self.buddies), text, None if sticky else 6)
            self.uiq.put(f)

        def work():
            ok = False
            try:
                remote, msg = upd_check()
                if remote:
                    say("새 버전이 나왔어! 받는 중이야~ (v%s)" % remote.get("version", remote.get("build")))
                    n = upd_apply(remote)
                    msg = "업데이트 완료! v%s (파일 %d개)" % (remote.get("version", remote.get("build")), n)
                    ok = True
                self.upd_msg = msg
                self.ask_log("update: " + msg)
                if ok:
                    say(msg + " 잠깐 다시 켜질게~")
                    self.uiq.put(lambda: QTimer.singleShot(2500, self.restart_self))
                elif not quiet:
                    say(msg)
                elif "토큰" in msg and not getattr(self, "upd_warned", False):   # 토큰 문제는 한 번만 알려 줌
                    self.upd_warned = True
                    say(msg)
            except Exception as e:
                self.upd_msg = f"업데이트 실패: {e}"
                self.ask_log("update error: %s" % e)
                if not quiet:
                    say(self.upd_msg)
            finally:
                self.upd_busy = False
                if done_cb:
                    self.uiq.put(lambda: done_cb(self.upd_msg))
        threading.Thread(target=work, daemon=True).start()

    # ── Claude 사용량 위젯: claude_usage.py 를 따로 띄움 (claude.ai 사용량 화면의 숫자를 작은 창에) ──
    USAGE_JSON = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "DesktopPet", "claude_usage", "usage.json")

    def usage_ready(self):
        """위젯에 필요한 작은 브라우저 부품(pywebview)이 깔려 있는지"""
        try:
            import importlib.util, site
            if importlib.util.find_spec("webview") is not None:
                return True
            return os.path.isdir(os.path.join(site.getusersitepackages(), "webview"))
        except Exception:
            return False

    def usage_note(self, text, secs=6):
        bs = [b for b in self.buddies if b.surface] or list(self.buddies)
        if bs:
            self.force_say(random.choice(bs), text, secs)

    def open_usage(self, auto=False):
        """메뉴 'Claude 사용량 보기': 위젯이 없으면 띄우고, 부품이 없으면 설치부터"""
        import subprocess
        p = getattr(self, "usage_proc", None)
        if p is not None and p.poll() is None:
            if not auto:
                self.usage_note("사용량 창은 이미 떠 있어~ 화면 어딘가에 있을 거야")
            return
        if not self.usage_ready():
            if auto:
                return
            if getattr(self, "usage_installing", False):
                self.usage_note("사용량 창 부품 설치 중이야, 조금만 기다려 줘~")
                return
            r = QMessageBox.question(None, "Claude 사용량",
                                     "사용량 창에 필요한 작은 브라우저 부품(pywebview)을 한 번 설치해야 해요.\n"
                                     "지금 설치할까요? (1분 정도, 인터넷 필요)")
            if r == QMessageBox.Yes:
                self.usage_install()
            return
        script = os.path.join(BASE, "claude_usage.py")
        if not os.path.exists(script):
            self.usage_note("사용량 위젯 파일이 아직 없어 — 업데이트를 받은 뒤 다시 해 줘")
            return
        exe = sys.executable
        if exe.lower().endswith("python.exe") and os.path.exists(exe[:-10] + "pythonw.exe"):
            exe = exe[:-10] + "pythonw.exe"
        try:
            self.usage_quitting = False
            self.usage_proc = subprocess.Popen([exe, script], cwd=BASE,
                                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.cfg["usage_widget"] = True
            self.save_cfg()
        except Exception as e:
            self.ask_log("usage widget error: %s" % e)

    def usage_install(self):
        import subprocess
        self.usage_installing = True
        self.usage_done = None
        self.usage_note("사용량 창 부품 설치 시작! 1분쯤 걸려~")
        exe = sys.executable
        if exe.lower().endswith("pythonw.exe") and os.path.exists(exe[:-11] + "python.exe"):
            exe = exe[:-11] + "python.exe"
        def run():
            try:
                r = subprocess.run([exe, "-m", "pip", "install", "--user", "pywebview"], capture_output=True, text=True,
                                   timeout=900, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.usage_done = (r.returncode == 0, (r.stderr or r.stdout or "")[-400:])
            except Exception as e:
                self.usage_done = (False, str(e))
        threading.Thread(target=run, daemon=True).start()
        self._usage_wait()

    def _usage_wait(self):
        d = getattr(self, "usage_done", None)
        if d is None:
            QTimer.singleShot(1500, self._usage_wait)
            return
        self.usage_done = None
        self.usage_installing = False
        ok, err = d
        if ok:
            import importlib
            importlib.invalidate_caches()
            self.usage_note("설치 끝! 사용량 창 띄울게♪")
            self.open_usage()
        else:
            self.ask_log("pywebview install failed: " + err)
            QMessageBox.warning(None, "Claude 사용량", "부품 설치에 실패했어요.\n\n" + err)

    def usage_stop(self):
        p = getattr(self, "usage_proc", None)
        if p is not None and p.poll() is None:
            self.usage_quitting = True          # 펫이 꺼지면서 닫는 것 → 다음에 켤 때 다시 띄움
            try:
                p.terminate()
            except Exception:
                pass

    def usage_tick(self):
        """1분마다: 위젯을 사용자가 닫았는지 확인 + 80%·95% 넘으면 말풍선으로 알림 (같은 초기화 시각엔 한 번씩만)"""
        p = getattr(self, "usage_proc", None)
        if p is not None and p.poll() is not None:
            self.usage_proc = None
            if not getattr(self, "usage_quitting", False) and self.cfg.get("usage_widget"):
                self.cfg["usage_widget"] = False
                self.save_cfg()
        if not self.cfg.get("usage_widget") or not self.cfg.get("usage_alert", True):
            return
        try:
            d = json.load(open(self.USAGE_JSON, encoding="utf-8"))
        except Exception:
            return
        if time.time() - float(d.get("ts", 0) or 0) > 900:
            return
        warned = self.__dict__.setdefault("usage_warned", set())
        for r in d.get("rows") or []:
            pct = int(r.get("pct", 0) or 0)
            lv = 95 if pct >= 95 else 80 if pct >= 80 else 0
            key = f"{r.get('label')}|{r.get('reset')}|{lv}"
            if not lv or key in warned:
                continue
            warned.add(key)
            when = f" ({r.get('reset')})" if r.get("reset") else ""
            if lv == 95:
                self.usage_note(f"Claude {r.get('label')} 사용량 {pct}%… 거의 다 썼어!{when}", 8)
            else:
                self.usage_note(f"Claude {r.get('label')} 사용량이 {pct}% 넘었어~ 조금 아껴 쓰자{when}", 8)
            break

    def restart_self(self):
        """새 파일로 펫 다시 켜기 (자리 잡고 있던 '한 번만 켜기' 잠금을 먼저 풀어 줌)"""
        import subprocess
        try:
            self.lock.close()
        except Exception:
            pass
        exe = sys.executable
        if exe.lower().endswith("python.exe"):
            w = exe[:-10] + "pythonw.exe"
            if os.path.exists(w):
                exe = w
        script = os.path.abspath(sys.argv[0]) if sys.argv[0].endswith(".py") else ENTRY_SCRIPT
        try:
            proc = subprocess.Popen([exe, script] + sys.argv[1:], cwd=os.path.dirname(script),
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0),
                                    close_fds=True)
        except Exception as e:
            self.ask_log("restart error: %s" % e)
            self.relisten()
            return
        self.ask_log("restart: 새 프로그램 켜는 중")
        self._restart_wait(proc, 0)

    def relisten(self):
        """다시 켜기 실패 → 잠금을 다시 잡고 지금 프로그램이 계속 돌기"""
        try:
            from PyQt5.QtNetwork import QLocalServer
            QLocalServer.removeServer(self.lock_name)
            self.lock = QLocalServer(); self.lock.listen(self.lock_name)
            self.lock.newConnection.connect(self.on_lock_conn)
        except Exception:
            pass

    def on_lock_conn(self):
        """두 번째로 켠 프로그램이 'show' 를 보내면 친구들 다시 등장. 다시 켜기 확인용 'ping' 은 무시"""
        c = self.lock.nextPendingConnection()
        if c is None:
            return
        def read():
            try:
                data = bytes(c.readAll())
            except Exception:
                data = b""
            if not data.startswith(b"ping"):
                self.all_drop()
        c.readyRead.connect(lambda: QTimer.singleShot(0, read))

    def _restart_wait(self, proc, waited):
        """새 프로그램이 '한 번만 켜기' 잠금을 잡으면(=제대로 켜졌으면) 그때 나는 꺼짐. 새 게 바로 죽으면 나는 안 꺼짐"""
        from PyQt5.QtNetwork import QLocalSocket
        sock = QLocalSocket(); sock.connectToServer(self.lock_name)
        if sock.waitForConnected(200):
            sock.write(b"ping"); sock.flush(); sock.waitForBytesWritten(200); sock.disconnectFromServer()
            self.ask_log("restart: 새 프로그램 켜짐 → 이전 것 종료")
            self.qapp.quit(); return
        dead = proc.poll() is not None
        if dead or waited >= 40:
            self.ask_log("restart: 새 프로그램이 안 켜짐 (%s) → 지금 것 계속 실행" % ("종료 코드 %s" % proc.returncode if dead else "시간 초과"))
            _crash_write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] 업데이트 뒤 다시 켜기 실패 — 이전 버전으로 계속 실행\n")
            if not dead:
                try: proc.kill()
                except Exception: pass
            self.relisten()
            return
        QTimer.singleShot(500, lambda: self._restart_wait(proc, waited + 1))

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

    def ground(self, bd):
        if bd.state in self.BUSY or bd.surface is None or bd.state in ("group", "gather", "tower", "train"):
            if self.group and bd in self.group.get("mem", []):
                self.group_break()
            scr = bd.scr()
            bd.drop_rope(); bd.setWindowOpacity(PET_ALPHA["a"]); bd.show()
            bd.stand_on((scr.left() - 9999, scr.bottom(), scr.right() + 9999))
            bd.fx = max(scr.left(), min(scr.right() - bd.S, bd.fx))
        bd.goal = None; bd.vx = 0; bd.after = None

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

    # ── 노래 ─────────────────────────────
    def music_list(self):
        lst = self.cfg.get("music")
        if lst is None:
            lst = [dict(x) for x in DEFAULT_MUSIC]
        return [x for x in lst if isinstance(x, dict) and str(x.get("url", "")).startswith("http")]

    def play_music(self, item=None):
        """유튜브(재생목록) 링크를 기본 브라우저로 열고, 펫들은 노래 모드로 춤추고 흥얼거림"""
        lst = self.music_list()
        if item is None:
            if not lst:
                self.open_settings(); return False
            item = random.choice(lst)
        url, name = item.get("url", ""), item.get("name") or "노래"
        if item.get("songs"):                               # 추천 리스트: 여러 곡을 이어서 재생
            url = yt_queue_url(item["songs"]) or url
        if not self.open_player(url):
            return False
        self.music_on = name
        self.music_end = time.time() + 60 * int(self.cfg.get("music_min", 60))
        if not hasattr(self, "musict"):
            self.musict = QTimer(); self.musict.timeout.connect(self.music_tick)
        self.musict.start(7000)
        live = [b for b in self.buddies if b.surface and b.drag is None]
        for i, b in enumerate(live):
            if self.cfg.get("music_dance", True) and b.state not in self.BUSY:
                b.vx = 0; b.set(random.choice(["dance", "sing"]), random.randint(200, 360))
        if live:
            self.force_say(live[0], f"♪ '{name}' 틀었어요! 같이 들어요~", 6)
        return True

    def open_player(self, url):
        """노래 재생: 기본은 '숨김 플레이어'(화면에 안 보임). 크롬/엣지가 없거나 '브라우저로' 설정이면 기본 브라우저로.
        창을 아예 숨기면(SW_HIDE·화면 밖) 크롬이 '안 보이는 창'으로 보고 재생을 미뤄서, 화면 안에 띄우되 투명·클릭 통과로 만듦"""
        mode = self.cfg.get("music_player", "hidden")
        exe = find_browser() if sys.platform == "win32" and mode in ("hidden", "mini") else None
        self.close_player()
        if exe:
            import subprocess
            prof = os.path.join(MCP_HOME, "music_player")
            os.makedirs(prof, exist_ok=True)
            g = QApplication.primaryScreen().availableGeometry()
            w, h = 420, 260
            try:
                self.yt_proc = subprocess.Popen(
                    [exe, f"--user-data-dir={prof}", f"--app={url}", "--autoplay-policy=no-user-gesture-required",
                     "--no-first-run", "--no-default-browser-check", "--disable-session-crashed-bubble",
                     "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding",
                     "--disable-background-timer-throttling", "--disable-background-media-suspend",
                     "--disable-features=CalculateNativeWinOcclusion",
                     f"--window-size={w},{h}", f"--window-position={g.right() - w - 20},{g.bottom() - h - 20}"],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.yt_shown = mode == "mini"
                if mode == "hidden":                         # 뜨자마자 투명하게 (몇 초 동안 새 창이 생기면 그것도)
                    for k in range(1, 60):
                        QTimer.singleShot(k * 150 if k < 40 else 6000 + k * 400,
                                          lambda: None if getattr(self, "yt_shown", False) else self.player_ghost(True))
                return True
            except Exception:
                self.yt_proc = None
        try:
            import webbrowser
            webbrowser.open(url)
            return True
        except Exception:
            return False

    def player_ghost(self, on):
        """플레이어 창을 투명·클릭 통과·작업표시줄 숨김으로 (on) / 원래대로 (off). 창은 '떠 있는' 상태라 소리는 계속 남"""
        p = getattr(self, "yt_proc", None)
        if not p or p.poll() is not None or sys.platform != "win32":
            return
        import ctypes
        u = ctypes.windll.user32
        for hwnd in self._player_hwnds(p.pid):
            ex = u.GetWindowLongW(hwnd, -20)
            if on:
                ex = (ex | 0x80000 | 0x20 | 0x80) & ~0x40000     # LAYERED | TRANSPARENT | TOOLWINDOW, APPWINDOW 끄기
                u.SetWindowLongW(hwnd, -20, ex)
                u.SetLayeredWindowAttributes(hwnd, 0, 0, 2)      # 완전 투명
            else:
                ex = (ex & ~0x20 & ~0x80) | 0x40000
                u.SetWindowLongW(hwnd, -20, ex)
                u.SetLayeredWindowAttributes(hwnd, 0, 255, 2)
            u.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020)   # 스타일 반영

    def player_show(self, show=True):
        p = getattr(self, "yt_proc", None)
        if not p or p.poll() is not None or sys.platform != "win32":
            return
        import ctypes
        u = ctypes.windll.user32
        self.yt_shown = bool(show)
        if show:
            self.player_ghost(False)
            g = QApplication.primaryScreen().availableGeometry()
            for hwnd in self._player_hwnds(p.pid):
                u.ShowWindow(hwnd, 9)                           # SW_RESTORE
                u.SetWindowPos(hwnd, 0, g.right() - 440, g.bottom() - 280, 420, 260, 0x0004)
                u.SetForegroundWindow(hwnd)
        else:
            self.player_ghost(True)

    def _player_hwnds(self, pid):
        """그 프로세스의 크롬 주 창들 (투명하게 만든 창 포함)"""
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        out = []
        CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def cb(h, _):
            pp = wintypes.DWORD()
            u.GetWindowThreadProcessId(h, ctypes.byref(pp))
            if pp.value == pid and not u.GetWindow(h, 4) and u.IsWindowVisible(h):
                buf = ctypes.create_unicode_buffer(64)
                u.GetClassNameW(h, buf, 64)
                if buf.value.startswith("Chrome_WidgetWin"):
                    out.append(h)
            return True
        u.EnumWindows(CB(cb), 0)
        return out

    def close_player(self):
        p = getattr(self, "yt_proc", None)
        self.yt_proc = None
        if p and p.poll() is None:
            try:
                import subprocess
                subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=8)
            except Exception:
                try:
                    p.terminate()
                except Exception:
                    pass

    def save_playlist(self, name, songs, play=True):
        """추천받은 곡들을 노래 목록에 저장 (한 줄 = 여러 곡이 이어서 나오는 링크)"""
        songs = [x for x in songs if isinstance(x, dict) and yt_id(x.get("url"))]
        url = yt_queue_url(songs)
        if not url:
            return None
        lst = self.music_list()
        name = (name or "추천 리스트").strip()[:40]
        item = {"name": name, "url": url, "songs": [{"title": str(x.get("title") or x.get("name") or "")[:80], "url": x["url"]} for x in songs]}
        lst = [x for x in lst if x.get("name") != name] + [item]
        self.cfg["music"] = lst
        self.save_cfg()
        try:
            with open(os.path.join(BASE, "추천노래.txt"), "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M}] {name}\n" +
                        "\n".join(f"  {i + 1}. {x['title']}  {x['url']}" for i, x in enumerate(item["songs"])) + "\n")
        except Exception:
            pass
        if play:
            self.play_music(item)
        return item

    def stop_music(self, say=True):
        self.close_player()
        if getattr(self, "music_on", None):
            self.music_on = None
            if hasattr(self, "musict"):
                self.musict.stop()
            live = [b for b in self.buddies if b.surface]
            if say and live:
                b = random.choice(live)
                b.vx = 0; b.set("cheer", 90)
                self.force_say(b, "노래 끝~ 즐거웠어요♪", 6)

    def music_tick(self):
        if not getattr(self, "music_on", None):
            return self.musict.stop()
        if time.time() > getattr(self, "music_end", 0):
            return self.stop_music()
        if self.group or self.scene:
            return
        live = [b for b in self.buddies if b.surface and b.drag is None and b.state not in self.BUSY
                and b.state not in ("sleep", "nap")]
        for b in random.sample(live, min(len(live), random.randint(1, 2))):
            if self.cfg.get("music_dance", True):
                b.vx = 0; b.set(random.choice(["dance", "dance", "sing"]), random.randint(160, 300))
            if self.cfg.get("bubbles", True):
                b.say(random.choice(MUSIC_LINES), 90)

    # ── 호감도 ─────────────────────────────
    def aff(self, c):
        return int(self.cfg.get("affinity", {}).get(c, 0))

    @staticmethod
    def aff_level(pts):
        return max(i for i, v in enumerate(AFF_LV) if pts >= v)

    def touch_lines(self, c):
        return TOUCH_LINES.get(f"{c}@{self.outfit.get(c)}") or TOUCH_LINES.get(c) or TOUCH_LINES["_casual" if c in CASUAL_CHARS else "_polite"]

    def add_aff(self, b, n):
        c = b.char
        old = self.aff(c)
        new = max(0, min(1000, old + n))
        if new == old:
            return
        self.cfg.setdefault("affinity", {})[c] = new
        self._aff_dirty = True
        lo, ln = self.aff_level(old), self.aff_level(new)
        if ln > lo and b in self.buddies:                # 단계 올라감: 하트 + 축하 대사
            up = self.touch_lines(c)["up"]
            line = up[min(ln - 1, len(up) - 1)]
            QTimer.singleShot(1800, lambda: (b in self.buddies) and (b.set("happy", 150) or True) and
                              self.force_say(b, f"{line}  ♥ {AFF_NAME[ln]}", 7))
            self.save_cfg(); self._aff_dirty = False

    def touch(self, b, kind):
        """쓰다듬기(pat)·톡 찌르기(poke): 호감도 단계에 맞는 대사 + 호감도 조금씩"""
        now = time.time()
        L = self.touch_lines(b.char)
        lv = self.aff_level(self.aff(b.char))
        if kind == "poke":
            hist = [t for t in getattr(b, "_pokes", []) if now - t < 10] + [now]
            b._pokes = hist
            if len(hist) >= 6:                           # 너무 찌르면 삐짐 (흥! 하고 고개 돌리기)
                b._pokes = []
                b.vx = 0; b.set("pout", 120)
                b.say(random.choice(L["annoy"]), 110)
                self.add_aff(b, -1)
                return
            if now - getattr(b, "_poke_aff", 0) > 30:
                b._poke_aff = now; self.add_aff(b, 1)
            b.say(random.choice(L["poke"][lv]), 100)
        else:
            if now - getattr(b, "_pat_aff", 0) > 20:
                b._pat_aff = now; self.add_aff(b, 3)
            b.say(random.choice(L["pat"][lv]), 120)

    def aff_text(self, c):
        pts = self.aff(c)
        lv = self.aff_level(pts)
        nxt = AFF_LV[lv + 1] if lv + 1 < len(AFF_LV) else None
        return f"호감도 {'♥' * (lv + 1)}{'♡' * (len(AFF_LV) - lv - 1)} {AFF_NAME[lv]} ({pts}" + (f"/{nxt})" if nxt else ")")

    # ── 홍북이 × 도로롱: 머리 위 사과 베기 (만화 그대로) ─────────────────────────────
    def apple_pair(self):
        hb = next((b for b in self.buddies if b.char == "scarlet" and self.outfit.get("scarlet") == "hongbuk"), None)
        dr = next((b for b in self.buddies if b.char == "dorothy" and self.outfit.get("dorothy") == "doro"), None)
        if not hb or not dr or not hb.surface or not dr.surface or not dr.has_frame(92) or not hb.has_frame(53):
            return None
        if hb.state in self.BUSY or dr.state in self.BUSY or hb.drag is not None or dr.drag is not None:
            return None
        return hb, dr

    def apple_cut(self):
        pair = self.apple_pair()
        if not pair or getattr(self, "_apple_busy", False):
            return False
        hb, dr = pair
        self._apple_busy = True
        QTimer.singleShot(20000, lambda: setattr(self, "_apple_busy", False))
        dr.goal = None; dr.vx = 0
        dr.play_seq([(92, 600)])                                   # 머리 위에 사과 올리고 대기
        dr.say("도로롱~?", 120)
        ms = lambda t: int(t * TICK)

        def start(me, o):
            if hb not in self.buddies or dr not in self.buddies:
                self._apple_busy = False; return
            hb.vx = 0; hb.goal = None
            hb.face = 1 if dr.cx > hb.cx else -1
            dr.face = -hb.face
            hb.say("가만히 있게, 도령… 아니 도로롱.", 110)
            hb.play_seq([(52, 90), (53, 14), (54, 70), (55, 150)])  # 노려보기 → 슥! → 납도 → 헤헷…
            dr.play_seq([(92, 104), (93, 50), (94, 170)])          # 사과 그대로… 쾅! → 부들부들
            QTimer.singleShot(ms(96), lambda: hb.say("슥!", 40))
            QTimer.singleShot(ms(112), lambda: dr.say("도로!!", 60))
            QTimer.singleShot(ms(170), lambda: dr.say("도로롱!!! 도로도로!!", 120))
            QTimer.singleShot(ms(178), lambda: hb.say("…헤헷. 빗나갔구먼.", 120))

            def chase():
                self._apple_busy = False
                if hb in self.buddies and dr in self.buddies and dr.surface and hb.surface:
                    dr.go_to(hb, "chase", ticks=300, arrive=lambda me, o: (o.set("dizzy", 90), me.set("pout", 90)))
                    hb.go_to(dr, "flee", ticks=300)
            QTimer.singleShot(ms(340), chase)
        gap = dr.S * 0.85
        if abs(hb.cx - dr.cx) < gap * 1.4 and abs(hb.feet() - dr.feet()) < 40:
            start(hb, dr)
        else:
            hb.say("도로롱 머리 위에 사과가 있구먼~", 100)
            hb.go_to(dr, "approach", ticks=500, arrive=start)
        return True

    # ── 블랑 × 누아르: 쌍둥이 폴댄스 쇼 (186~193, 기본 의상 폴더의 이벤트 그림) ─────────────────────────────
    POLE_LINES = [
        (("블랑과 누아르의 쇼타임이에요!", "쌍둥이 토끼들이 함께하는 쇼타임! 기대해 주세요!"),
         ("누아르와 블랑의 쇼타임이에요⋯!", "으⋯ 부끄러워⋯ 그래도 블랑이랑 같이라면⋯")),
        (("자, 한 바퀴 더~! 행운이 빙글빙글!", "점장님, 눈 떼면 안 돼요~♪", "언니, 지금이야!"),
         ("저, 점장님⋯ 너무 빤히 보지 마세요⋯!", "블랑, 같이⋯!", "으⋯ 다들 저만 보는 것 같아요⋯")),
        (("행운을 듬~뿍 받아 가세요!", "멋진 쇼였죠? 박수~!", "저랑 언니가 합쳐지면 완벽하다니까요!"),
         ("⋯감사합니다. 으⋯ 부끄러워.", "⋯이제 부끄러움이 좀 덜 수 있을까요?", "블랑이 있어서 끝까지 할 수 있었어요.")),
    ]

    def pole_pair(self):
        bl = next((b for b in self.buddies if b.char == "blanc"), None)
        nr = next((b for b in self.buddies if b.char == "noir"), None)
        if not bl or not nr or not bl.surface or not nr.surface or bl.surface != nr.surface:
            return None
        for b in (bl, nr):
            bd = _ev_bdir(self, b.char)
            if not bd or not os.path.exists(os.path.join(bd, "193.png")):
                return None
        if bl.state in self.BUSY or nr.state in self.BUSY or bl.drag is not None or nr.drag is not None:
            return None
        return bl, nr

    # ── 블랑 × 누아르: 화면 오른쪽 아래 구석에서 계속 폴댄스 (메뉴로 켜고 끔, 켜 두면 다음에도 기억) ──
    POLE_CORNER_LINES = (
        ("행운의 쇼는 쉬지 않아요~♪", "점장님, 일하다 지치면 여기 봐 주세요!", "한 바퀴 더~! 빙글빙글!",
         "구석 자리도 무대라구요♪", "언니, 박자 맞춰요~!", "코인 러시 출장 공연 중이에요~"),
        ("으⋯ 구석이라 다행이에요⋯", "저, 점장님⋯ 일 안 하시고 왜 여기 보세요⋯!", "블랑, 조금만 천천히⋯!",
         "⋯조금은 익숙해진 것 같아요.", "부끄럽지만⋯ 계속할게요.", "점장님은⋯ 일, 일 하세요⋯!"),
    )
    POLE_SPIN = [(187, 22), (188, 22), (189, 26), (190, 30), (191, 26)]

    # ── 카니는 늘 모몽가 곁에 (멀어지면 쪼르르 따라가고, 모몽가만 있으면 같이 등장) ──
    def kani_tick(self):
        if self.cfg.get("kani_follow") is False:
            return
        out = ("balloon", "dig")
        mg = next((b for b in self.buddies if b.char == "momonga" and b.state not in out), None)
        if not mg:
            return
        kn = next((b for b in self.buddies if b.char == "kani" and b.state not in out), None)
        if kn is None:
            now = time.time()
            if "kani" in self.chars and now - getattr(self, "_kani_join", 0) > 90:
                self._kani_join = now
                n0 = len(self.buddies)
                self.add(x=int(mg.cx + mg.S * 0.6), char="kani")
                if len(self.buddies) > n0:
                    k2 = self.buddies[-1]
                    QTimer.singleShot(2500, lambda: k2 in self.buddies and k2.say(random.choice(KANI_JOIN), 90))
            return
        if kn.goal or kn.drag is not None or mg.drag is not None or kn.state in self.BUSY or self.quiet():
            return
        if kn.surface is None or kn.surface != mg.surface:
            return
        if abs(kn.cx - mg.cx) > max(kn.S, mg.S) * 2.0 and random.random() < 0.7:
            kn.go_to(mg, "approach", ticks=500,
                     arrive=lambda *a: random.random() < 0.3 and kn in self.buddies and kn.say(random.choice(KANI_NEAR), 70))

    def pole_corner_set(self, on):
        self.cfg["pole_corner"] = bool(on)
        self.save_cfg()
        if not hasattr(self, "_pct"):
            self._pct = QTimer(timeout=self.pole_corner_step)
        self._pcn = 0
        bl = next((b for b in self.buddies if b.char == "blanc"), None)
        nr = next((b for b in self.buddies if b.char == "noir"), None)
        if on:
            self._pct.start(250)
            if bl: bl.say("점장님, 구석에서 계속 쇼 할게요~!", 100)
            if nr: QTimer.singleShot(int(40 * TICK), lambda: nr in self.buddies and nr.say("으⋯ 구석이라면⋯ 조금 덜 부끄러울지도⋯", 100))
        else:
            self._pct.stop()
            for b in self.buddies:
                if getattr(b, "_pole_corner", False):
                    b._pole_corner = False
                    if b.state == "seq":
                        b.set("cheer", 60)
            if bl: bl.say("쇼 끝! 박수~!", 80)

    def _pole_corner_loop(self, b):
        if self.cfg.get("pole_corner") and b in self.buddies and b.drag is None:
            b.play_seq(self.POLE_SPIN * 8, after=lambda b=b: self._pole_corner_loop(b))   # 쉬지 않고 계속 돌기
        else:
            b._pole_corner = False

    def pole_corner_step(self):
        if not self.cfg.get("pole_corner"):
            self._pct.stop()
            return
        self._pcn += 1
        dancing = []
        for c, k in (("blanc", 1.35), ("noir", 0.55)):       # 블랑 왼쪽·누아르 오른쪽, 서로 마주 보고
            b = next((x for x in self.buddies if x.char == c), None)
            if b is None or b.drag is not None:
                continue
            bd = _ev_bdir(self, c)
            if not bd or not os.path.exists(os.path.join(bd, "191.png")):
                continue
            if b.state == "seq":
                if getattr(b, "_pole_corner", False):
                    dancing.append(b)
                continue                                       # 다른 동작(사격 등) 중이면 끝날 때까지 기다림
            b._pole_corner = False
            if b.state in self.BUSY or b.surface is None:
                continue
            scr = b.scr()
            tx = scr.right() - b.S * k
            on_floor = b.surface[2] - b.surface[0] > 5000 and abs(b.surface[1] - scr.bottom()) <= 4
            if not on_floor:                                   # 창 위나 다른 화면이면 구석 바닥에서 빼꼼 다시 등장
                if self._pcn % 8 == 0:
                    self.remove(b)
                    self.add(int(tx), "peek", c)
                continue
            dx = tx - b.cx
            if abs(dx) > b.S * 0.2:
                d = 1 if dx > 0 else -1
                b.goal = None
                if b.state != "walk" or b.vx * d <= 0:
                    b.vx = d * 1.3
                    b.face = d
                    b.set("walk", 600)
                continue
            b.vx = 0
            b.goal = None
            b.face = 1 if c == "blanc" else -1
            b._pole_corner = True
            b.play_seq([(186, 50)] + self.POLE_SPIN * 8, after=lambda b=b: self._pole_corner_loop(b))
        if dancing and self._pcn % 200 == 0:                  # 50초쯤마다 한마디
            b = random.choice(dancing)
            b.say(random.choice(self.POLE_CORNER_LINES[0 if b.char == "blanc" else 1]), 110)

    def pole_show(self):
        pair = self.pole_pair()
        if not pair or getattr(self, "_pole_busy", False):
            return False
        bl, nr = pair
        self._pole_busy = True
        QTimer.singleShot(30000, lambda: setattr(self, "_pole_busy", False))
        ms = lambda t: int(t * TICK)
        L = self.POLE_LINES
        spin = [(187, 22), (188, 22), (189, 26), (190, 30), (191, 26)]
        seq = [(186, 70)] + spin * 3 + [(192, 60), (193, 90)]
        t_end = sum(d for _, d in seq)

        def start(me=None, o=None):
            if bl not in self.buddies or nr not in self.buddies:
                self._pole_busy = False; return
            for b in (bl, nr):
                b.goal = None; b.vx = 0
            bl.face = 1 if nr.cx > bl.cx else -1          # 둘이 마주 보고, 봉은 둘 사이에
            nr.face = -bl.face
            bl.play_seq(seq, after="cheer")
            nr.play_seq(seq, after="cheer")
            bl.say(random.choice(L[0][0]), 100)
            QTimer.singleShot(ms(40), lambda: nr.say(random.choice(L[0][1]), 100))
            QTimer.singleShot(ms(200), lambda: bl.say(random.choice(L[1][0]), 90))
            QTimer.singleShot(ms(330), lambda: nr.say(random.choice(L[1][1]), 90))
            QTimer.singleShot(ms(t_end - 70), lambda: bl.say(random.choice(L[2][0]), 120))
            QTimer.singleShot(ms(t_end - 30), lambda: nr.say(random.choice(L[2][1]), 120))
            QTimer.singleShot(ms(t_end + 30), lambda: setattr(self, "_pole_busy", False))
        if self.quiet() or abs(bl.cx - nr.cx) < bl.S * 0.9:
            start()
        else:
            bl.say("언니~! 쇼 시작해요!", 90)
            nr.say("으⋯ 지, 지금⋯?", 80)
            nr.go_to(bl, "approach", ticks=500, arrive=start)
        return True

    # ── 파일 던지기: 캐릭터 위에 파일을 놓으면 요약·정리·변환 ─────────────────────────────
    DROP_FORMATS = ["txt", "md", "csv", "json", "html", "xlsx", "docx", "pdf", "png", "jpg"]

    def _drop_dlg_flags(self, w):
        w.setWindowFlags(w.windowFlags() | Qt.WindowStaysOnTopHint)
        QTimer.singleShot(60, self.raise_popups)

    def file_drop(self, b, paths):
        from PyQt5.QtWidgets import QInputDialog
        if b not in self.buddies:
            return
        paths = [os.path.normpath(x) for x in paths if os.path.exists(x)][:10]
        if not paths:
            return
        vids = [x for x in paths if os.path.splitext(x)[1].lower() in VIDEO_EXT]     # 영상·음악 → 코덱무관플레이어
        imgs = [x for x in paths if os.path.splitext(x)[1].lower() in IMAGE_EXT]     # 사진 → 이름표
        def _has_imgs(d):                        # 사진이 들어 있는 폴더인지 (바로 아래 + 하위 폴더 조금만 훑기)
            try:
                subs = []
                for i, e in enumerate(os.scandir(d)):
                    if i > 800:
                        break
                    if e.is_file() and os.path.splitext(e.name)[1].lower() in IMAGE_EXT:
                        return True
                    if e.is_dir() and len(subs) < 20:
                        subs.append(e.path)
                for s in subs:
                    for i, e in enumerate(os.scandir(s)):
                        if i > 300:
                            break
                        if e.is_file() and os.path.splitext(e.name)[1].lower() in IMAGE_EXT:
                            return True
            except Exception:
                pass
            return False
        img_dirs = [x for x in paths if os.path.isdir(x) and _has_imgs(x)]   # 사진 폴더 → 이름표로 바로 열기
        cl = bool(self.claude_cli())
        busy = bool(getattr(self, "_ask_busy", {}).get("_drop"))
        if not cl and not (vids or imgs or img_dirs):
            self.force_say(b, "파일 정리는 Claude Code 가 깔려 있어야 할 수 있어요… (PowerShell 에서 claude 설치·로그인)", 10)
            return
        if busy and not (vids or imgs or img_dirs):
            self.force_say(b, "앞에 맡긴 파일 아직 하는 중이야~ 끝나면 다시 줘!", 6)
            return
        if b.surface is None:
            self.ground(b)
        b.vx = 0; b.goal = None; b.set("cheer", 60)
        b.say(random.choice(DROP_LINES["got"]), 400)
        folder = [x for x in paths if os.path.isdir(x)]
        names = ", ".join(os.path.basename(x) or x for x in paths)
        m = QMenu()
        m.setWindowFlags(m.windowFlags() | Qt.WindowStaysOnTopHint)
        m.aboutToShow.connect(lambda: QTimer.singleShot(30, self.raise_popups))
        title = m.addAction(f"{names[:40]}{'…' if len(names) > 40 else ''}"); title.setEnabled(False)
        m.addSeparator()
        a_play = m.addAction("코덱무관플레이어로 재생") if vids else None
        a_tag = m.addAction("이름표로 이 폴더 열기 (이미지 파일명 편집)" if img_dirs else "이름표로 열기 (이미지 파일명 편집)") if (imgs or img_dirs) else None
        if a_play is not None or a_tag is not None:
            m.addSeparator()
        a_sum = m.addAction("요약해 줘 (말풍선으로)")
        a_note = m.addAction("정리해서 새 파일로 만들어 줘 (원본은 그대로)")
        a_conv = m.addAction("다른 형식으로 바꿔 줘…")
        a_dir = m.addAction("폴더 정리해 줘 (종류별로 나누기)") if folder else None
        a_free = m.addAction("직접 부탁하기…")
        if not cl or busy:                       # Claude Code 가 없거나 앞의 일을 하는 중이면 정리 메뉴는 잠금
            for x in (a_sum, a_note, a_conv, a_dir, a_free):
                if x is not None:
                    x.setEnabled(False)
        m.addSeparator()
        m.addAction("그만두기")
        act = m.exec_(QCursor.pos())
        if act is not None and act is a_play:
            self.open_app("player", vids, b)
            return
        if act is not None and act is a_tag:
            self.open_app("nametag", (img_dirs or sorted({os.path.dirname(x) for x in imgs}))[:1], b)
            return
        if act is None or act not in (a_sum, a_note, a_conv, a_dir, a_free):
            b.say("응, 알겠어~", 60)
            return
        dirs = sorted({x if os.path.isdir(x) else os.path.dirname(x) for x in paths})
        plist = "\n".join(paths)
        rule = ("원본 파일은 지우거나 덮어쓰지 말고, 결과는 원본과 같은 폴더에 새 파일로 만들어 줘(이름이 겹치면 뒤에 _2 처럼 붙이기). "
                "다 하면 어떤 파일을 만들었는지 말풍선에 짧게 알려 줘. ")
        if act is a_sum:
            need, q = "read", ("이 파일(들)을 읽고 핵심만 요약해 줘. 폴더면 안에 뭐가 있는지 훑어보고 알려 줘.\n" + plist)
        elif act is a_note:
            need, q = "files", ("이 파일(들)을 읽고 내용을 보기 좋게 정리한 문서를 새로 만들어 줘(제목·소제목·핵심 요점 정리, 이름은 '원래이름_정리.md'). "
                                + rule + "\n" + plist)
        elif act is a_conv:
            dlg = QInputDialog(); self._drop_dlg_flags(dlg)
            dlg.setWindowTitle("다른 형식으로 바꾸기"); dlg.setLabelText("어떤 형식으로 바꿀까? (예: txt, md, csv, xlsx, pdf, png…)")
            dlg.setComboBoxItems(self.DROP_FORMATS); dlg.setComboBoxEditable(True)
            if not dlg.exec_() or not dlg.textValue().strip():
                return
            fmt = dlg.textValue().strip().lstrip(".")
            simple = fmt.lower() in ("txt", "md", "csv", "json", "html")
            need = "files" if simple else "full"
            q = (f"이 파일(들)을 {fmt} 형식으로 바꿔 줘. " + rule +
                 ("" if simple else "필요하면 컴퓨터에 이미 깔린 프로그램·파이썬으로 변환해도 되지만, 새 프로그램을 설치하지는 마. 못 하면 방법만 알려 줘. ")
                 + "\n" + plist)
        elif act is a_dir:
            need, q = "full", ("이 폴더 안의 파일들을 종류별(문서·이미지·영상·음악·압축·기타 등)로 하위 폴더를 만들어 옮겨서 정리해 줘. "
                               "파일은 절대 지우지 말고, 같은 이름이 있으면 덮어쓰지 말고 이름 뒤에 _2 를 붙여. 하위 폴더 안 파일은 건드리지 마. "
                               "옮긴 목록은 그 폴더에 '정리기록.txt' 로 남기고(되돌릴 수 있게), 말풍선에는 몇 개를 어디로 옮겼는지만 짧게.\n"
                               + "\n".join(folder))
        else:
            dlg = QInputDialog(); self._drop_dlg_flags(dlg)
            dlg.setWindowTitle("이 파일로 뭘 해 줄까?"); dlg.setLabelText(f"{names[:50]} 로 할 일"); dlg.resize(460, 120)
            if not dlg.exec_() or not dlg.textValue().strip():
                return
            need, q = "files", (dlg.textValue().strip() + "\n대상 파일: \n" + plist + "\n" + rule)
        if not self.drop_allowed(need, dirs):
            b.say("알겠어, 안 건드릴게~ (환경설정 → AI 연결 → 작업 권한)", 120)
            return
        b.say(random.choice(DROP_LINES["start"]), 150)
        self.ask_log(f"file drop {need}: {names}")
        self.ask_hidden(b, "[파일 던지기] " + q, extra={"dirs": dirs, "power": need})

    def drop_allowed(self, need, dirs):
        """설정한 작업 권한으로 모자라면 이번 한 번만 허락받기"""
        if need == "read":
            return True                                   # 파일을 직접 던져 준 것 = 읽어도 된다는 뜻
        power, have = self.ask_power_dirs()
        inside = all(any(os.path.normcase(d).startswith(os.path.normcase(h)) for h in have) for d in dirs)
        ok = (power == "full" and inside) if need == "full" else (power in ("files", "full") and inside)
        if ok:
            return True
        what = ("파일을 새로 만들고 옮기거나, 컴퓨터에 깔린 프로그램으로 변환하는 명령 실행" if need == "full"
                else "파일 읽기와 새 파일 만들기")
        box = QMessageBox(QMessageBox.Question, "이번 한 번만 허락",
                          f"이번 한 번만 이 폴더에서 {what}을 해도 될까요?\n\n" + "\n".join(dirs) +
                          "\n\n원본을 고칠 땐 .bak 백업을 먼저 하고, 지우기·설치는 하지 않아요.",
                          QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        self._drop_dlg_flags(box)
        return box.exec_() == QMessageBox.Yes

    # ── 자리 비움 마중: 한동안 입력이 없으면 졸다가, 돌아오면 달려와서 '어서 와~!' ─────────────────────────────
    @staticmethod
    def idle_seconds():
        try:
            import ctypes
            class LII(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
            li = LII(); li.cbSize = ctypes.sizeof(LII)
            if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)):
                return 0.0
            return ((ctypes.windll.kernel32.GetTickCount() - li.dwTime) & 0xFFFFFFFF) / 1000.0
        except Exception:
            return 0.0

    def idle_tick(self):
        if not self.cfg.get("idle_welcome", True) or not self.buddies:
            self._away = False
            return
        idle = self.idle_seconds()
        limit = max(1, int(self.cfg.get("idle_min", 5))) * 60
        if not getattr(self, "_away", False):
            if idle >= limit and not self.group and not self.scene and not getattr(self, "hs_on", False):
                self._away = True
                self._away_t = time.time() - idle
                for i, b in enumerate(self.buddies):
                    if b.surface and b.drag is None and b.state not in self.BUSY:
                        b.vx = 0; b.goal = None
                        QTimer.singleShot(i * 900, lambda b=b: b in self.buddies and b.surface and (
                            b.set("yawn", 90, after="sleep"), b.say(random.choice(AWAY_LINES), 80)))
            return
        if idle < 2:                                      # 돌아왔다!
            self._away = False
            self.welcome_back(time.time() - getattr(self, "_away_t", time.time()))
        elif random.random() < 0.004:                     # 기다리는 동안 가끔 다시 꾸벅
            sl = [b for b in self.buddies if b.surface and b.state not in ("sleep", "nap") and b.state not in self.BUSY]
            if sl:
                b = random.choice(sl); b.set("yawn", 90, after="sleep")

    def welcome_lines(self, c, long_):
        d = WELCOME_LINES.get(c) or WELCOME_LINES["_casual" if c in CASUAL_CHARS else "_polite"]
        return d["long" if long_ else "short"]

    def welcome_back(self, away):
        if self.group or self.scene:
            return
        long_ = away >= 30 * 60
        pos = QCursor.pos()
        live = [b for b in self.buddies if b.surface and b.drag is None]
        if not live:
            return
        scr = QApplication.screenAt(pos)
        near = [b for b in live if scr is None or b.scr() == scr.availableGeometry()] or live
        near.sort(key=lambda x: abs(x.cx - pos.x()))
        for i, b in enumerate(near[:4]):
            def go(b=b, first=(i == 0)):
                if b not in self.buddies or not b.surface:
                    return
                b.vx = 0; b.set("surprise", 30)
                def arrive(me, o, first=first):
                    me.set("cheer" if first else "wave", 100)
                    me.say(random.choice(self.welcome_lines(me.char, long_)), 140)
                    if first:
                        self.add_aff(me, 2)
                QTimer.singleShot(500, lambda: b in self.buddies and (arrive(b, None) if _rest_on(self)  # 제자리 모드면 그 자리에서 반기기
                                                                       else b.go_to(CURSOR, "chase", ticks=420, arrive=arrive)))
            QTimer.singleShot(i * 600, go)
        # 다른 화면에 있던 친구들은 제자리에서 손 흔들기
        for b in [x for x in live if x not in near[:4]]:
            b.set("wave", 90)

    # ── 관심사 브리핑: 키워드 5개까지, 하루 한 번 검색해서 알려 주기 ─────────────────────────────
    def brief_dir(self):
        d = os.path.join(BASE, "브리핑"); os.makedirs(d, exist_ok=True)
        return d

    def brief_due(self, now):
        if not self.cfg.get("brief_on", False) or not self.brief_keys() or getattr(self, "_brief_busy", False):
            return False
        if self.cfg.get("brief_last") == now.strftime("%Y-%m-%d"):
            return False
        try:
            hh, mm = [int(x) for x in str(self.cfg.get("brief_time", "09:00")).split(":")[:2]]
        except Exception:
            hh, mm = 9, 0
        return (now.hour, now.minute) >= (hh, mm)

    def brief_keys(self):
        return [k.strip() for k in self.cfg.get("brief_keys", []) if k and k.strip()][:5]

    def start_briefing(self, force=False):
        import subprocess
        keys = self.brief_keys()
        sp = ([b for b in self.buddies if b.surface] or self.buddies or [None])[0]
        if not keys:
            if sp:
                self.force_say(sp, "브리핑 받을 관심사 키워드를 먼저 정해 줘~ (환경설정 → AI 연결 → 관심사 브리핑)", 8)
            return
        exe = self.claude_cli()
        if not exe:
            if sp:
                self.force_say(sp, "브리핑은 Claude Code 가 깔려 있어야 할 수 있어요…", 8)
            return
        if getattr(self, "_brief_busy", False):
            return
        self._brief_busy = True
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        self.cfg["brief_last"] = today; self.save_cfg()      # 실패해도 하루에 한 번만 자동 시도
        if sp and force:
            sp.say("관심사 소식 찾아볼게~ 조금만 기다려!", 150)
        who = sp.char if sp else (self.roster or [self.mode])[0]
        lab = self.chars[who]["label"]
        style = (CHAR_BIO.get(f"{who}@{self.outfit.get(who)}") or CHAR_BIO.get(who) or "")[:400]
        past = self.brief_history(today)
        prompt = (f"오늘은 {datetime.datetime.now():%Y년 %m월 %d일}이야. 다음 관심사 키워드 각각에 대해 인터넷 검색(WebSearch, 필요하면 WebFetch)으로 "
                  "최근 1~2일 사이의 새 소식·화제를 찾아서 정리해 줘. 소식이 없으면 '새 소식 없음'이라고 써. 지어내지 말고, 검색으로 확인한 것만.\n"
                  "키워드: " + " / ".join(keys) + "\n\n"
                  + (("아래는 최근 며칠 동안 이미 전한 브리핑이야. 여기 나온 소식과 같은 내용(같은 사건·발표·기사를 다른 매체가 다시 쓴 것 포함)은 전부 빼고, "
                      "처음 나온 소식만 골라 줘. 같은 사건이라도 새 진전(결과 발표·수치 변화·공식 입장 등)이 있으면 그 진전만 '(후속)'을 붙여 써 줘. "
                      "검색할 때도 아래와 겹치지 않는 다른 각도로 찾아봐. 빼고 나니 남는 게 없으면 그 키워드는 '새 소식 없음'.\n"
                      "──── 이미 전한 브리핑 ────\n" + past + "\n──── 여기까지 ────\n\n") if past else "")
                  + "결과는 아래 두 부분으로, 다른 말 없이 정확히 이 형식으로 써 줘.\n"
                  "===SHORT===\n"
                  f"(바탕화면 캐릭터 '{lab}'가 말풍선으로 전할 한 줄 브리핑. 새로 찾은 소식만으로, {lab} 말투로 2문장, 120자 이내, 마크다운·이모지 없이. 전부 새 소식이 없으면 그렇다고 짧게. 캐릭터 설정: {style})\n"
                  "===FULL===\n"
                  "(키워드마다 '■ 키워드' 제목 아래 핵심 소식 2~4개를 '- ' 로 시작하는 한두 줄 요약으로, 각 줄 끝에 (출처: 링크). 일반 텍스트로.)")
        long_ = len(prompt) > 6000                 # 명령줄 길이 한도(특히 claude.cmd 8191자) → 길면 표준입력으로 넘김
        args = [exe, "-p"] + ([] if long_ else [prompt]) + ["--output-format", "json", "--allowedTools", "WebSearch,WebFetch"]
        stdin_data = prompt.encode("utf-8") if long_ else None
        work = os.path.join(MCP_HOME, "brief"); os.makedirs(work, exist_ok=True)
        self.ask_log("briefing start: " + ", ".join(keys))
        def worker():
            out, err = "", ""
            try:
                r = subprocess.run(args, capture_output=True, cwd=work, timeout=900, input=stdin_data,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                txt = r.stdout.decode("utf-8", "replace").strip()
                try:
                    j = json.loads(txt); out = (j.get("result") or "").strip()
                    if j.get("is_error"):
                        err = out or "error"
                except Exception:
                    out = txt
                if r.returncode != 0 and not out:
                    err = r.stderr.decode("utf-8", "replace").strip()[-200:] or f"exit {r.returncode}"
            except subprocess.TimeoutExpired:
                err = "시간 초과"
            except Exception as e:
                err = str(e)
            self.claude_history("관심사 브리핑", lab, "키워드: " + ", ".join(keys), out, err)
            self.uiq.put(lambda: self.brief_done(out, err, keys, today))
        threading.Thread(target=worker, daemon=True).start()

    def brief_history(self, today, days=3, limit=2000):
        """최근 며칠 치 브리핑 내용 (오늘 이미 받은 것도 포함 — 다시 받을 때 겹치지 않게)"""
        try:
            fs = sorted(f for f in os.listdir(self.brief_dir()) if re.match(r"\d{4}-\d{2}-\d{2}\.txt$", f))
        except Exception:
            return ""
        older = [f for f in fs if f[:10] < today][-days:]
        pick = older + [f for f in fs if f[:10] == today]
        parts = []
        for f in pick:
            try:
                t = open(os.path.join(self.brief_dir(), f), encoding="utf-8-sig").read()
            except Exception:
                continue
            body = t.split("\n\n", 1)[-1].strip()
            body = re.sub(r"\(출처:[^)]*\)", "", body)            # 링크는 빼서 짧게
            parts.append(f"[{f[:10]}]\n" + body[:limit])
        return "\n\n".join(parts)

    def brief_done(self, out, err, keys, today):
        self._brief_busy = False
        sp = ([b for b in self.buddies if b.surface] or self.buddies or [None])[0]
        if err and not out:
            self.ask_log("briefing error: " + err)
            if sp:
                self.force_say(sp, f"브리핑을 못 가져왔어… ({err[:50]}) 메뉴에서 '지금 브리핑 받기'로 다시 해 줘!", 10)
            return
        short, full = "", out
        mm = re.search(r"===SHORT===\s*(.*?)\s*===FULL===\s*(.*)", out, re.S)
        if mm:
            short, full = mm.group(1).strip(), mm.group(2).strip()
        short = re.sub(r"[*#`>]", "", short).strip() or "오늘의 관심사 브리핑이 도착했어!"
        path = os.path.join(self.brief_dir(), f"{today}.txt")
        try:
            if os.path.exists(path):                       # 같은 날 다시 받으면 덮어쓰지 않고 아래에 이어 붙이기
                with open(path, "a", encoding="utf-8") as f:
                    f.write(f"\n\n──── 추가 브리핑 {datetime.datetime.now():%H:%M} ────\n{full}\n")
            else:
                with open(path, "w", encoding="utf-8-sig") as f:
                    f.write(f"관심사 브리핑 — {today}\n키워드: {', '.join(keys)}\n\n{full}\n")
        except Exception as e:
            self.ask_log(f"briefing save error: {e}")
        self.ask_log("briefing done")
        w = getattr(self, "brief_win", None)
        if w is not None and w.isVisible():                # 보기 창이 열려 있으면 새 브리핑으로 바로 갱신
            w.reload(select=f"{today}.txt")
        if sp:
            self.ground(sp); sp.vx = 0; sp.set("wave", 120)
            self.force_say(sp, f"[브리핑] {short[:220]} (자세한 건 우클릭 → 관심사 브리핑 → 오늘 브리핑 보기)")

    def open_briefing(self):
        fs = sorted(f for f in os.listdir(self.brief_dir()) if f.endswith(".txt"))
        if not fs:
            sp = ([b for b in self.buddies if b.surface] or self.buddies or [None])[0]
            if sp:
                sp.say("아직 받은 브리핑이 없어~ '지금 브리핑 받기'를 눌러 봐!", 120)
            return
        w = getattr(self, "brief_win", None)
        if w is None:
            w = self.brief_win = BriefingWindow(self)
        w.reload(select=fs[-1])
        w.show(); w.raise_(); w.activateWindow()

    # ── 커서 놀이 ─────────────────────────────
    def cursor_tick(self):
        if not self.cfg.get("cursor_play", True) or self.group or self.scene or QApplication.mouseButtons():
            return
        now = time.time()
        pos = QCursor.pos()
        hist = [(t, p) for t, p in getattr(self, "_chist", []) if now - t < 1.2] + [(now, pos)]
        self._chist = hist
        if len(hist) >= 2 and hist[-2][1] != pos:
            self._cstill = now; self._cidle_done = False
        still = now - getattr(self, "_cstill", now)
        if getattr(self, "_aff_dirty", False) and now - getattr(self, "_aff_saved", 0) > 60:
            self._aff_saved = now; self._aff_dirty = False; self.save_cfg()
        free = [b for b in self.buddies if b.surface and b.drag is None and b.goal is None
                and b.state not in self.BUSY and b.state not in ("sleep", "nap", "dizzy", "pout")]
        if not free:
            return
        lines = lambda b: CURSOR_LINES if b.char in CASUAL_CHARS else CURSOR_LINES_P
        avoid = self.cfg.get("cursor_avoid", True)  # 커서 피해 다니기 켜면 쫓아오기·찾아오기 안 함
        # 1) 캐릭터 위에서 커서를 마구 흔들면 어지러워함
        path = sum((hist[i][1] - hist[i - 1][1]).manhattanLength() for i in range(1, len(hist)))
        if path > 2200:
            for b in free:
                if abs(pos.x() - b.cx) < b.S * 0.6 and abs(pos.y() - (b.fy + b.S / 2)) < b.S * 0.6 \
                        and now - getattr(b, "_dizzy_t", 0) > 20:
                    b._dizzy_t = now; b.vx = 0; b.set("dizzy", 140)
                    b.say(random.choice(lines(b)["dizzy"]), 100)
                    self._chist = [(now, pos)]
                    return
        # 2) 근처에서 커서가 움직이면 가끔 쫓아가서 잡기
        if not avoid and not _rest_on(self) and now - getattr(self, "_chase_t", 0) > 90 and 2 <= path < 900 and random.random() < 0.04:
            near = [b for b in free if abs(pos.x() - b.cx) < 380 and -220 < (b.fy + b.S) - pos.y() < 260]
            if near:
                b = random.choice(near)
                self._chase_t = now
                b.say(random.choice(lines(b)["chase"]), 80)
                b.go_to(CURSOR, "chase", ticks=260,
                        arrive=lambda me, o: (me.set("cheer", 90), me.say(random.choice(lines(me)["caught"]), 90)))
                return
        # 3) 커서를 오래 가만히 두면 한 명이 찾아와서 기웃
        if not avoid and not _rest_on(self) and still > 45 and not getattr(self, "_cidle_done", False):
            self._cidle_done = True
            scr = QApplication.screenAt(pos)
            cand = [b for b in free if scr is None or b.scr() == scr.availableGeometry()] or free
            b = min(cand, key=lambda x: abs(x.cx - pos.x()))
            b.go_to(CURSOR, "approach", ticks=500,
                    arrive=lambda me, o: (me.set("wave", 90), me.say(random.choice(lines(me)["idle"]), 110)))

    # ── 화면 같이 보기 (물어보기) ─────────────────────────────
    SCREEN_WORDS = ("화면", "이거", "이게", "여기", "저거", "에러", "오류", "창에", "보이는", "스크린", "캡처", "읽어")

    def grab_screen_for_ask(self, b, q, work):
        mode = self.cfg.get("ask_screen", "auto")
        if mode == "off" or (mode == "auto" and not any(w in q for w in self.SCREEN_WORDS)):
            return None
        try:
            sc = screen_for(b.char)
            pm = sc.grabWindow(0)
            if pm.width() > 1600:
                pm = pm.scaledToWidth(1600, Qt.SmoothTransformation)
            path = os.path.join(work, "screen.png")
            pm.save(path, "PNG")
            return path
        except Exception:
            return None

    # ── 매분 확인: 기념일 · 예약 알림 · 컴퓨터 상태 ─────────────────────────────
    def say_line(self, b, lines, secs=6):
        if b in self.buddies:
            self.force_say(b, random.choice(lines) if isinstance(lines, (list, tuple)) else lines, secs)

    def minute_tick(self):
        now = datetime.datetime.now()
        try:
            self.usage_tick()
        except Exception as ex:
            _crash_write(f"\nusage_tick: {ex}\n")
        live = [b for b in self.buddies if b.surface and b.state not in self.BUSY]
        # 1) 예약 알림
        due, keep = [], []
        for r in self.cfg.get("reminders", []):
            (due if r.get("at", 0) <= time.time() else keep).append(r)
        if due:
            self.cfg["reminders"] = keep; self.save_cfg()
            for r in due:
                self.fire_reminder(r)
        if not self.buddies:
            return
        # 2) 기념일 (하루 한 번 크게 + 가끔 대사)
        md = now.strftime("%m-%d")
        today = now.strftime("%Y-%m-%d")
        hol = HOLIDAYS.get(md)
        bdays = [c for c, d in CHAR_BIRTHDAY.items() if d == md and any(b.char == c for b in self.buddies)]
        if (hol or bdays) and self.cfg.get("event_day") != today and now.hour >= 7 and live:
            self.cfg["event_day"] = today; self.save_cfg()
            for i, b in enumerate(live):
                QTimer.singleShot(i * 700, lambda b=b: b in self.buddies and (b.set(random.choice(["cheer", "dance", "sing"]), 200) or True))
            if hol:
                QTimer.singleShot(400, lambda: self.say_line(random.choice(live), hol[1], 8))
            for c in bdays:
                me = next((b for b in self.buddies if b.char == c), None)
                if me:
                    QTimer.singleShot(2500, lambda me=me: self.say_line(me, BIRTHDAY_SELF.get(me.char) or BIRTHDAY_SELF["_"], 9))
                    others = [b for b in live if b is not me]
                    for k, o in enumerate(others[:3]):
                        QTimer.singleShot(5000 + k * 1800, lambda o=o, me=me: self.say_line(
                            o, random.choice(BIRTHDAY_FRIEND).format(n=self.chars[me.char]["label"]), 6))
        elif hol and live and random.random() < 0.08:
            self.say_line(random.choice(live), hol[2], 5)
        # 2.5) 관심사 브리핑 (하루 한 번)
        if self.brief_due(now):
            self.start_briefing()
        # 2.7) 홍북이·도로롱이 둘 다 있으면 가끔 사과 베기
        if random.random() < 0.06 and self.apple_pair():
            self.apple_cut()
        # 2.8) 블랑·누아르가 둘 다 있으면 가끔 쌍둥이 폴댄스 쇼
        elif random.random() < 0.05 and not self.cfg.get("pole_corner") and self.pole_pair():
            self.pole_show()
        # 3) 캐릭터끼리 수다 (켜 둔 경우만)
        if self.ai_chat_ready() and random.random() < 0.35:
            self.start_ai_chat()
        # 4) 컴퓨터 상태
        if self.cfg.get("sys_react", True) and live:
            self.check_system(live, now)

    def check_system(self, live, now):
        t = time.time()
        b = random.choice(live)
        bat = self.battery()
        if bat:
            pct, plugged = bat
            was = getattr(self, "_bat_plugged", plugged)
            self._bat_plugged = plugged
            if plugged and not was:
                b.set("cheer", 90); self.say_line(b, SYS_LINES["charging"])
            elif not plugged and pct <= 20 and t - getattr(self, "_bat_warn", 0) > 1800:
                self._bat_warn = t
                b.set("cry", 160); self.say_line(b, SYS_LINES["battery_low"], 8)
        if t - getattr(self, "_net_t", 0) > 120:              # 2분마다 인터넷 확인 (뒤에서)
            self._net_t = t
            def chk():
                import socket
                ok = False
                for host in (("1.1.1.1", 443), ("8.8.8.8", 53)):
                    try:
                        socket.create_connection(host, timeout=3).close(); ok = True; break
                    except Exception:
                        pass
                self.cmdq.put(({"op": "_net", "ok": ok}, None))
            threading.Thread(target=chk, daemon=True).start()
        if (now.hour in (0, 1, 2, 3) and (now.hour or now.minute >= 30)) and self.cfg.get("late_day") != now.strftime("%Y-%m-%d"):
            self.cfg["late_day"] = now.strftime("%Y-%m-%d"); self.save_cfg()
            b.set("yawn", 90, after="sleep"); self.say_line(b, SYS_LINES["late"], 8)

    def net_result(self, ok):
        was = getattr(self, "_net_ok", True)
        self._net_ok = ok
        live = [b for b in self.buddies if b.surface and b.state not in self.BUSY]
        if not live or ok == was:
            return
        b = random.choice(live)
        if ok:
            b.set("cheer", 90); self.say_line(b, SYS_LINES["net_up"])
        else:
            b.set("dizzy", 140); self.say_line(b, SYS_LINES["net_down"], 8)

    @staticmethod
    def battery():
        if sys.platform != "win32":
            return None
        try:
            import ctypes
            class SPS(ctypes.Structure):
                _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte), ("BatteryLifePercent", ctypes.c_ubyte),
                            ("SystemStatusFlag", ctypes.c_ubyte), ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]
            st = SPS()
            if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(st)):
                return None
            if st.BatteryFlag & 128 or st.BatteryLifePercent > 100:   # 배터리 없는 데스크톱
                return None
            return int(st.BatteryLifePercent), st.ACLineStatus == 1
        except Exception:
            return None

    # ── 예약 알림 ─────────────────────────────
    def add_reminder(self, text, at=None, minutes=None, who=None):
        now = datetime.datetime.now()
        when = None
        if minutes is not None:
            when = now + datetime.timedelta(minutes=float(minutes))
        elif at:
            a = str(at).strip()
            for fmt in ("%Y-%m-%d %H:%M", "%m-%d %H:%M", "%H:%M"):
                try:
                    d = datetime.datetime.strptime(a, fmt)
                    if fmt == "%H:%M":
                        d = now.replace(hour=d.hour, minute=d.minute, second=0, microsecond=0)
                        if d <= now:
                            d += datetime.timedelta(days=1)
                    elif fmt == "%m-%d %H:%M":
                        d = d.replace(year=now.year)
                    when = d; break
                except ValueError:
                    pass
        if not when:
            return None
        r = {"at": when.timestamp(), "text": str(text)[:200], "who": who or "", "label": when.strftime("%m/%d %H:%M")}
        self.cfg.setdefault("reminders", []).append(r)
        self.cfg["reminders"].sort(key=lambda x: x["at"])
        self.save_cfg()
        return r

    def fire_reminder(self, r):
        cand = self.find_buddies(r.get("who")) if r.get("who") else []
        b = (cand or [x for x in self.buddies if x.surface] or self.buddies or [None])[0]
        if b is None:
            return
        self.ground(b)
        b.vx = 0; b.set("wave", 120)
        self.force_say(b, f"[알림] {r.get('text', '')}")      # 사용자가 닫을 때까지 남아 있음
        for o in [x for x in self.buddies if x is not b and x.surface][:2]:
            o.set("cheer", 90)

    def cancel_reminder(self, i):
        lst = self.cfg.get("reminders", [])
        if 0 <= i < len(lst):
            lst.pop(i); self.save_cfg()

    # ── 캐릭터끼리 수다 (Claude, 켜고 끄기 + 하루 횟수 제한) ─────────────────────────────
    def ai_chat_ready(self):
        if not self.cfg.get("ai_chat", False) or getattr(self, "_ai_chat_busy", False) or self.group or self.scene:
            return False
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        st = self.cfg.get("ai_chat_count", {})
        if st.get("day") != today:
            st = {"day": today, "n": 0}; self.cfg["ai_chat_count"] = st
        if st["n"] >= int(self.cfg.get("ai_chat_max", 5)):
            return False
        gap = 60 * int(self.cfg.get("ai_chat_gap", 40))
        return time.time() - getattr(self, "_ai_chat_t", 0) > gap

    def start_ai_chat(self, force=False):
        """화면 속 두 친구가 Claude 로 짧은 수다를 나눔 (대사는 말풍선으로 번갈아)"""
        import subprocess
        exe = self.claude_cli()
        if not exe or getattr(self, "_ai_chat_busy", False):
            return False
        live = [b for b in self.buddies if b.surface and b.drag is None and b.state not in self.BUSY]
        chars = list({b.char: b for b in live}.values())
        if len(chars) < 2 and force:
            chars = list({b.char: b for b in self.buddies}.values())
        if len(chars) < 2:
            return False
        a, b = random.sample(chars, 2)
        la, lb = self.chars[a.char]["label"], self.chars[b.char]["label"]
        def bio(x):
            k = f"{x.char}@{self.outfit.get(x.char)}"
            lines = [it[5][0] for it in (self.chars[x.char].get("persona") or [])][:4]
            return (CHAR_BIO.get(k) or CHAR_BIO.get(x.char, "")) + (" 말버릇 예: " + " / ".join(lines) if lines else "")
        call = self.cfg.get("my_name") or CHAR_CALL.get(a.char) or DEFAULT_CALL.get(next((sq for sq, m in SQUADS.items() if a.char in m), ""), "") or "주인"
        topic = random.choice(AI_CHAT_TOPICS)
        prompt = (f"데스크톱 펫으로 내 바탕화면에서 같이 사는 두 친구 '{la}'와 '{lb}'의 짧은 잡담을 써 줘. "
                  f"{la}: {bio(a)}\n{lb}: {bio(b)}\n"
                  f"주제: {topic}. 지금 시각 {datetime.datetime.now():%H:%M}. 화면 주인은 '{call}'(이)라고 불러. "
                  "각자 원래 말투를 정확히 살리고, 귀엽고 다정한 분위기로. 4~6줄, 한 줄은 40자 이내, 둘이 번갈아 말하기. "
                  "도로롱은 '도로/도로롱/롱' 소리만 냄. 그림 이모지는 쓰지 말고 ♪ ~ ! 같은 기호는 괜찮아. "
                  f'다른 설명 없이 JSON 배열만 출력: [{{"who": "{la}", "line": "..."}}, {{"who": "{lb}", "line": "..."}}]')
        self._ai_chat_busy = True
        self._ai_chat_t = time.time()
        st = self.cfg.setdefault("ai_chat_count", {"day": datetime.datetime.now().strftime("%Y-%m-%d"), "n": 0})
        st["n"] = st.get("n", 0) + 1; self.save_cfg()
        work = os.path.join(MCP_HOME, "ask"); os.makedirs(work, exist_ok=True)
        def worker():
            lines = []
            try:
                r = subprocess.run([exe, "-p", prompt, "--output-format", "json"], capture_output=True, cwd=work, timeout=150,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                txt = r.stdout.decode("utf-8", "replace").strip()
                try:
                    txt = json.loads(txt).get("result") or txt
                except Exception:
                    pass
                m = re.search(r"\[.*\]", txt, re.S)
                if m:
                    lines = [x for x in json.loads(m.group(0)) if isinstance(x, dict) and x.get("line")][:6]
            except Exception as e:
                self.ask_log(f"ai chat error {e}")
            self.claude_history("친구 잡담", la + " · " + lb, prompt, "\n".join(str(x) for x in (lines or [])))
            self.uiq.put(lambda: self.play_ai_chat(a, b, la, lb, lines))
        threading.Thread(target=worker, daemon=True).start()
        return True

    def play_ai_chat(self, a, b, la, lb, lines):
        self._ai_chat_busy = False
        if not lines or a not in self.buddies or b not in self.buddies:
            return
        try:
            with open(os.path.join(BASE, "대화기록.txt"), "a", encoding="utf-8-sig") as f:
                f.write(f"[{datetime.datetime.now():%m/%d %H:%M}] (친구들 수다)\n" +
                        "\n".join(f"{x.get('who')}: {x.get('line')}" for x in lines) + "\n\n")
        except Exception:
            pass
        done = {"v": False}
        def talk(_me=None, _o=None):
            if done["v"]:
                return
            done["v"] = True
            for i, x in enumerate(lines):
                who = a if str(x.get("who", "")).strip() == la else (b if str(x.get("who", "")).strip() == lb else (a, b)[i % 2])
                other = b if who is a else a
                def say(who=who, other=other, t=str(x.get("line"))[:80]):
                    if who in self.buddies:
                        if other in self.buddies and who.surface and who.drag is None and who.state not in self.BUSY:
                            who.vx = 0; who.goal = None; who.face = 1 if other.cx > who.cx else -1
                            who.set("chat", 110)
                        who.say(t, 125, force=True)
                QTimer.singleShot(i * 3800, say)
        if a.surface and b.surface and a.surface == b.surface and abs(a.cx - b.cx) > a.S * 1.2:
            a.go_to(b, "approach", arrive=lambda me, o: talk(), ticks=400)     # 다가가서 수다
            QTimer.singleShot(9000, talk)                                    # 못 만나도 9초 뒤엔 그 자리에서 수다
        else:
            talk()

    # ── 숨바꼭질 ─────────────────────────────
    def hide_and_seek(self):
        bs = [b for b in self.buddies if b.drag is None]
        if not bs or getattr(self, "hs_on", False):
            return
        if self.group:
            self.group_break()
        if self.scene:
            self.scene_end()
        self.hs_on = True
        self.say_line(bs[0], HIDE_LINES["start"], 3)
        def hide():
            for b in [x for x in self.buddies if x.drag is None]:
                scr = b.scr()
                b.drop_rope(); b.goal = None
                b.vx = b.vy = 0
                b.surface = None
                b.fx = float(random.randint(scr.left(), max(scr.left() + 1, scr.right() - b.S)))
                b.fy = float(scr.bottom() - b.S * b.fbottom(F["peek"]) + b.S * random.uniform(0.12, 0.3))   # 머리 끝만 살짝
                b.hiding = True
                b.set("peek", 10 ** 7)
            self.hs_end = time.time() + 180
            QTimer.singleShot(180 * 1000, self.hs_timeout)
        QTimer.singleShot(2600, hide)

    def hs_found(self, b):
        b.hiding = False
        self.add_aff(b, 2)
        b.say(random.choice(HIDE_LINES["found"]), 90, force=True)
        b.t = 0                                           # peek 이 끝나면서 폴짝 튀어나옴
        if not any(getattr(x, "hiding", False) for x in self.buddies):
            self.hs_on = False
            QTimer.singleShot(1500, lambda: self.buddies and self.say_line(random.choice(self.buddies), HIDE_LINES["all"], 5))

    def hs_timeout(self):
        if not getattr(self, "hs_on", False):
            return
        self.hs_on = False
        for b in self.buddies:
            if getattr(b, "hiding", False):
                b.hiding = False
                b.say(random.choice(HIDE_LINES["timeout"]), 90, force=True)
                b.t = 0

    def announce_new_friends(self):
        """업데이트로 새 친구가 들어왔을 때 한 번 알려 주기"""
        names = ", ".join(self.chars[c]["label"] for c in self.new_friends if c in self.chars)
        self.save_cfg()
        if names and self.buddies:
            self.force_say(random.choice(self.buddies),
                           f"새 친구가 왔어요: {names}! 우클릭 → 멤버 부르기 또는 환경설정 → 캐릭터에서 불러 주세요♪", 14)

    def transform(self, base, to_alt=None):
        """마리안↔모더니아, 도로시↔도로롱: 변신 연출(9번 시트) 후 모습 바꾸기"""
        tf = TRANSFORM.get(base)
        if not tf or base not in self.outfits or tf["alt"] not in self.outfits[base]:
            return False
        cur = self.outfit.get(base)
        if to_alt is None:
            to_alt = cur != tf["alt"]
        target = tf["alt"] if to_alt else "basic"
        if cur == target:
            return False
        bs = [b for b in self.buddies if b.char == base and b.surface and b.state not in ("group", "gather", "train")]
        if not bs or not os.path.exists(os.path.join(self.chars[base]["dir"], "76.png")):
            self.set_outfit(base, target)
            return True
        go, arrive = (tf["go"], tf["arrive"]) if to_alt else (tf["back"], tf["home"])
        l0, l1, l2 = tf["lines"]

        def switched():
            self.apply_outfit(base, target)
            self.cfg.setdefault("outfit", {})[base] = target
            self.save_cfg()
            for b in bs:
                if b in self.buddies:
                    b.say(l1 if to_alt else l2, 130)
                    b.play_seq([(f, 16) for f in arrive] + [(F["walk"][0], 10)])
                    b.update()
            if base == "scarlet" and to_alt and random.random() < 0.5:   # 홍북이가 되자마자 도로롱이 있으면 가끔 사과 베기
                QTimer.singleShot(3500, self.apple_cut)
        for i, b in enumerate(bs):
            b.goal = None
            b.say(l0 if to_alt else "…", 90)
            b.play_seq([(f, 12) for f in go], after=switched if i == 0 else None)
        return True

    def has_tf(self, base, of):
        d = self.outfits.get(base, {}).get(of)
        return bool(d) and f"{base}@{of}" in ALT_TF and os.path.exists(os.path.join(d["dir"], "84.png"))

    def alt_chain(self, base, of):
        """기본에서 그 모습까지 변신 순서 (예: 도로시 해방 = 노스텔지어 → 해방)"""
        path, x = [], of
        while x and x != "basic" and x not in path and len(path) < 5:
            path.insert(0, x)
            x = ALT_FROM.get(f"{base}@{x}", "basic")
        return path

    def alt_transform(self, base, target):
        """니케 이격 변신: 정방향(84~91) / 풀 때 역방향 / 이격끼리는 거꾸로 풀었다가 다시 변신.
        ALT_FROM 이 있으면 그 모습을 거쳐서 (기본 → 노스텔지어 → 해방)"""
        cur = self.outfit.get(base)
        C, T = self.alt_chain(base, cur), self.alt_chain(base, target)
        k = 0
        while k < min(len(C), len(T)) and C[k] == T[k]:
            k += 1
        steps = [("rev", x) for x in reversed(C[k:])] + [("fwd", x) for x in T[k:]]
        if not any(self.has_tf(base, x) for _, x in steps):
            return False
        bs = [b for b in self.buddies if b.char == base and b.surface and b.state not in ("group", "gather", "train", "tower")]
        if not bs:
            return False

        def save(of):
            self.apply_outfit(base, of)
            self.cfg.setdefault("outfit", {})[base] = of
            self.save_cfg()

        def run(rest):
            live = [b for b in bs if b in self.buddies]
            if not rest or not live:
                for b in live:
                    b.play_seq([(F["walk"][0], 8)])
                return
            kind, x = rest[0]
            key = f"{base}@{x}"
            tf = self.has_tf(base, x)
            if kind == "rev":
                parent = ALT_FROM.get(key, "basic")
                if not tf:
                    save(parent); run(rest[1:]); return

                def undone():
                    save(parent)
                    if parent == "basic" and len(rest) == 1:
                        for b in live:
                            b.say(ALT_TF[key][2], 120)
                    run(rest[1:])
                for i, b in enumerate(live):
                    b.goal = None; b.vx = 0
                    b.play_seq([(f, 9) for f in range(91, 83, -1)], after=undone if i == 0 else None)
            else:
                save(x)
                if not tf:
                    for b in live:
                        b.say(random.choice(OUTFIT_LINES.get(key) or OUTFIT_LINES.get(base, ["짜잔~"])), 120)
                    run(rest[1:]); return

                def done():
                    for b in live:
                        if b in self.buddies:
                            b.say(ALT_TF[key][1], 130)
                    run(rest[1:])
                for i, b in enumerate(live):
                    b.goal = None; b.vx = 0
                    if i == 0:
                        b.say(ALT_TF[key][0], 80)
                    b.play_seq([(f, 11) for f in range(84, 90)] + [(f, 18) for f in (90, 91)],
                               after=done if i == 0 else None)
                    b.update()
        run(steps)
        return True

    def apply_outfit(self, base, of):
        data = dict(self.outfits[base][of])
        if base == "dorothy" and of == "doro" and self.cfg.get("doro_motion"):
            alt = os.path.join(CHARS_DIR, DORO_MOTION_DIR)      # 모션 버전 도로롱 (환경설정에서 켰을 때만)
            if os.path.exists(os.path.join(alt, "0.png")):
                data["dir"] = alt
                try:
                    raw = json.load(open(os.path.join(alt, "meta.json"), encoding="utf-8"))
                    data["meta"] = {int(k): v for k, v in raw["frames"].items()}
                    data["rope"] = raw.get("rope", {})
                except Exception:
                    pass
        data["persona"] = persona_of(f"{base}@{of}", data["dir"])
        self.chars[base] = data
        self.outfit[base] = of
        for k in [k for k in self._pix if k[0] == base]:
            del self._pix[k]
        for k in [k for k in self._spix if k[0] == base]:
            del self._spix[k]

    def set_outfit(self, base, of, say=True):
        """옷 갈아입기: 펑! 하고 바뀜"""
        if of not in self.outfits.get(base, {}) or self.outfit.get(base) == of:
            return
        tf = TRANSFORM.get(base)
        if say and tf and {of, self.outfit.get(base)} == {"basic", tf["alt"]} \
                and any(b.char == base and b.surface for b in self.buddies):
            self.transform(base, of == tf["alt"])         # 변신은 연출과 함께
            return
        if say and self.alt_transform(base, of):           # 니케 이격: 변신 연출(84~91)
            return
        self.apply_outfit(base, of)
        self.cfg.setdefault("outfit", {})[base] = of
        self.save_cfg()
        for b in self.buddies:
            if b.char == base:
                try:
                    Burst(b.cx, b.fy + b.S * 0.6, b.S * 0.9)
                except Exception:
                    pass
                if say and b.surface:
                    b.say(random.choice(OUTFIT_LINES.get(f"{base}@{of}") or OUTFIT_LINES.get(base, ["짜잔~"])), 120)
                b.update()

    def auto_outfit(self):
        if not self.outfits or not self.cfg.get("outfit_auto", True):
            return
        self.outfit_t += 1
        if self.outfit_t < random.randint(12, 25):          # 12~25분마다 한 번쯤
            return
        self.outfit_t = 0
        for base, ofs in self.outfits.items():
            if len(ofs) > 1 and any(b.char == base and b.surface for b in self.buddies):
                self.set_outfit(base, random.choice([o for o in ofs if o != self.outfit.get(base)]))

    def scene_pix(self, sq, f):
        key = ("_scene", sq, f)
        if key not in self._pix:
            self._pix[key] = QPixmap(os.path.join(self.scene_sets[sq]["dir"], f"{f}.png"))
        return self._pix[key]

    def update_squad(self):
        """지금 화면 멤버가 한 그룹 안이면 그 그룹 말투, 섞여 있으면 'mixed'"""
        self.squad = next((sq for sq, m in SQUADS.items() if self.team and set(self.team) <= set(m)), "mixed")

    def scene_squads(self):
        """합동 장면을 할 수 있는 그룹 (그림이 있고 그 그룹 넷이 모두 지금 멤버)"""
        return [sq for sq in self.scene_sets if all(c in self.live_team() for c in SQUADS[sq])]

    def scenes_ok(self, sq=None):
        """그 그룹 넷이 모두 화면에 있을 때만"""
        sqs = [sq] if sq else self.scene_squads()
        return any(s in self.scene_sets and all(c in self.live_team() for c in SQUADS[s])
                   and all(any(b.char == c for b in self.buddies) for c in SQUADS[s]) for s in sqs)

    def scene_kinds(self, present=True):
        return ["scene:%s:%s" % (sq, n) for sq in self.scene_squads()
                if (not present or self.scenes_ok(sq)) for n in self.scene_sets[sq]["scenes"]]

    def save_cfg(self):
        from tempfile import NamedTemporaryFile

        temp_path = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=os.path.dirname(self.cfg_path),
                                    prefix="settings-", suffix=".tmp", delete=False) as settings:
                temp_path = settings.name
                json.dump(self.cfg, settings, ensure_ascii=False)
            os.replace(temp_path, self.cfg_path)
            return True
        except (OSError, TypeError, ValueError) as error:
            _crash_write(f"[settings.json] {error}\n")
            return False
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    def set_team(self, new):
        """합본: 그룹만 / 인물별로 부르기. 빠지는 아이는 풍선·땅굴로 퇴장, 들어오는 아이는 등장"""
        new = [c for c in self.roster if c in new]
        if not new:
            return
        if self.group:
            self.group_break()
        if self.scene:
            self.scene_end()
        self._dismissed = {b.char for b in self.buddies if b.char not in new}   # 이번에 빼기로 한 아이들만 정리 대상
        added = [c for c in new if c not in (self.team or [])]
        self.team = new
        self.live = (added + [c for c in getattr(self, "live", []) if c in new])[:self.cap()]   # 새로 고른 아이 먼저 화면에
        live = self.live_team()
        self.update_squad()
        self.cfg["active"] = new
        self.save_cfg()
        self.pending = {c for c in self.pending if c in new}
        for b in list(self.buddies):
            if b.char not in live:
                if b.surface and b.drag is None and b.state not in self.BUSY:
                    self.leave(b)
                else:
                    self.remove(b)
        come = [c for c in live if not any(b.char == c and b.state not in ("balloon", "dig") for b in self.buddies)]   # 퇴장 중인 아이는 없는 걸로 보고 다시 부름
        for i, c in enumerate(come):
            QTimer.singleShot(400 + i * 600, lambda c=c: self.add(
                None, random.choice(["drop", "peek", "umbrella", "rope"]), c))
        if len(new) >= 3 and not self.gt.isActive():
            self.gt.start(random.randint(40000, 70000))

    def toggle_member(self, c):
        self.set_team([x for x in self.team if x != c] if c in self.team else self.team + [c])

    def resolve(self, char, f):
        """그림이 없는 프레임은 FALLBACK 을 따라가며 있는 그림으로 (아직 덜 그린 모습도 안 깨지게)"""
        if f in self.plugins.sprites:
            return f
        d = self.chars[char]["dir"]
        cache = self.chars[char].setdefault("_res", {})
        if f not in cache:
            g, seen = f, set()
            while not os.path.exists(os.path.join(d, f"{g}.png")) and g not in seen:
                seen.add(g)
                g = FALLBACK.get(g, 0)
            cache[f] = g
        return cache[f]

    def frame_bounds(self, char, frame):
        frame = self.resolve(char, frame)
        sprite = self.plugins.sprites.get(frame)
        return sprite.bounds if sprite else self.chars[char]["meta"].get(frame, {})

    def spix(self, f, char, S, face, dpr=1.0):
        """크기·방향에 맞춰 미리 부드럽게 줄여 둔 그림 (그릴 때마다 줄이지 않게)"""
        key = (char, f, S, face, dpr)
        pm = self._spix.get(key)
        if pm is not None:
            self._spix.move_to_end(key)
        else:
            while len(self._spix) > 700:
                self._spix.popitem(last=False)
            from PyQt5.QtGui import QTransform
            src = self.pix(f, char)
            px = max(1, int(round(S * dpr)))
            pm = src.scaled(px, px, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            if face < 0:
                pm = pm.transformed(QTransform().scale(-1, 1))
            pm.setDevicePixelRatio(dpr)
            self._spix[key] = pm
        return pm

    def pix(self, f, char):
        key = (char, f)
        pm = self._pix.get(key)
        if pm is None:
            while len(self._pix) > 400:
                self._pix.popitem(last=False)
            frame = self.resolve(char, f)
            sprite = self.plugins.sprites.get(frame)
            path = str(sprite.path) if sprite else os.path.join(self.chars[char]["dir"], f"{frame}.png")
            pm = self._pix[key] = QPixmap(path)
        else:
            self._pix.move_to_end(key)
        return pm

    def pick_char(self):
        if self.team:
            t = self.live_team() if self.one_each else self.team
            cnt = {n: sum(1 for b in self.buddies if b.char == n) for n in t}
            low = min(cnt.values())
            return random.choice([n for n in t if cnt[n] == low])
        return self.mode

    def switch_char(self, name):
        """캐릭터 바꾸기: 지금 아이들은 보내고 새 친구들이 등장"""
        if name == self.mode:
            return
        self.mode = name
        for b in list(self.buddies):
            self.remove(b)
        for i in range(min(START_COUNT, self.cap())):
            QTimer.singleShot(i * 400, self.add)

    def rename_shortcuts(self):
        """예전 이름(Stellive Pet) 바로가기를 새 이름으로 (한 번만)"""
        if self.cfg.get("renamed_v1") or os.name != "nt":
            return
        dirs = []
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
            dirs.append(os.path.expandvars(winreg.QueryValueEx(k, "Desktop")[0]))
        except Exception:
            pass
        dirs += [os.path.join(os.path.expanduser("~"), "Desktop"),
                 os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs")]
        for d in dirs:
            old, new = os.path.join(d, "Stellive Pet.lnk"), os.path.join(d, f"{APP_NAME}.lnk")
            try:
                if os.path.exists(old) and not os.path.exists(new):
                    os.replace(old, new)
            except Exception:
                pass
        self.cfg["renamed_v1"] = True
        self.save_cfg()

    def pet_windows(self):
        from PyQt5.QtWidgets import QDialog, QMenu
        return [w for w in QApplication.topLevelWidgets()
                if w.isVisible() and not isinstance(w, (QDialog, QMenu)) and w.windowFlags() & Qt.Tool]

    def keep_on_top(self, force=False):
        # 켜져 있으면 매번 다시 맨 위로: 메신저처럼 스스로 '맨 위'인 창이 활성화되면 먼저 뜬 펫 창이 그 뒤로 밀리기 때문
        from PyQt5.QtWidgets import QDialog, QMenu
        if QApplication.activePopupWidget() is not None and not force:
            return                                       # 우클릭 메뉴·드롭다운이 열려 있는 동안엔 창 순서를 건드리지 않음 (드롭다운이 닫히거나 가려짐)
        force = force or self.on_top
        for w in self.pet_windows():
            try:
                if not set_topmost(w.winId(), self.on_top, force):
                    want = bool(self.on_top)
                    if bool(w.windowFlags() & Qt.WindowStaysOnTopHint) != want:   # 윈도우가 아니면 Qt 방식으로
                        w.setWindowFlag(Qt.WindowStaysOnTopHint, want); w.show()
            except Exception:
                pass
        self.raise_popups()

    def demote(self, w):
        """맨 위 고정을 풀고 지금 보고 있는 창 바로 뒤로 (위로 튀어나오지 않게)"""
        try:
            h = wintypes.HWND(int(w.winId()))
            if not (user32.GetWindowLongW(h, -20) & 0x8):
                return
            fg = user32.GetForegroundWindow()
            user32.SetWindowPos(h, wintypes.HWND(fg) if fg else wintypes.HWND(-2), 0, 0, 0, 0,
                                0x0001 | 0x0002 | 0x0010 | 0x0200)
        except Exception:
            pass

    def raise_popups(self):
        """우클릭 메뉴·환경설정·물어보기 창은 언제나 펫(캐릭터·말풍선)보다 위에"""
        from PyQt5.QtWidgets import QDialog, QMenu
        dialogs, pops = [], []
        for w in QApplication.topLevelWidgets():
            if not w.isVisible():
                continue
            if isinstance(w, QMenu) or w.windowType() in (Qt.Popup, Qt.ToolTip):
                pops.append(w)                           # 드롭다운 목록·메뉴는 맨 마지막에 (환경설정 창이 덮지 않게)
            elif isinstance(w, QDialog):
                if isinstance(w, (SettingsDialog, HistoryDialog)) and not w.isActiveWindow():
                    self.demote(w)                   # 다른 창을 보고 있으면 환경설정은 그 창 뒤로 (항상 위 X)
                    continue
                dialogs.append(w)
        for w in dialogs + pops:
            try:
                set_topmost(w.winId(), True, True)
            except Exception:
                pass

    def set_on_top(self, on):
        self.on_top = bool(on)
        self.cfg["on_top"] = self.on_top
        self.save_cfg()
        self.keep_on_top(force=True)
        for b in self.buddies:
            if b.surface:
                b.say("맨 위에 있을게요!" if on else "창 뒤에서 놀고 있을게요~", 90)
                break

    def scan(self):
        if not self.climb_windows:
            self.windows = []
            return
        gs = {sc.name(): sc.geometry() for sc in [target_screen()] + [screen_for(c) for c in CHAR_SCREEN]}.values()
        self.windows = [w for w in window_tops()
                        if any(w[2] > g.left() and w[0] < g.right() and g.top() <= w[1] < g.bottom() for g in gs)]

    def tick(self):
        self._tk = getattr(self, "_tk", 0) + 1
        if self._tk % 90 == 0:
            try:
                self.sweep_strays()
            except Exception:
                pass
        for _ in range(self.substeps):                # 가볍게 모드: 계산은 그대로, 그리기만 덜 자주
            for b in list(self.buddies):
                b.step()
            self.collide()
            if self.group:
                self.group_step()
            if self.scene and not self.scene.step():
                self.scene_end()
        for b in list(self.buddies):
            if b.drag is None:
                b.flush()
        # 친구끼리 마주치면 인사
        for i, a in enumerate(self.buddies):
            for b in self.buddies[i + 1:]:
                if a.surface and a.surface == b.surface and abs(a.cx - b.cx) < a.S * 0.7:
                    if a.state == "walk" and b.state == "walk" and not a.cool and not b.cool \
                            and a.goal is None and b.goal is None:
                        a.greet(1 if b.cx > a.cx else -1)
                        b.greet(1 if a.cx > b.cx else -1)

    def return_home(self, ch):
        self.pending.discard(ch)
        if self.team and ch not in (self.live_team() if self.one_each else self.team):
            return
        self.add(entrance=random.choice(["peek", "peek", "umbrella", "rope", "drop"]), char=ch)

    def auto_group(self):
        if not self.group and not self.scene and self.cfg.get("auto_group", True) and not self.quiet():
            lead = next((b for b in self.buddies if b.char in ("shibuki", "rang") and b.surface), None)
            if lead and random.random() < 0.6:           # 진행 담당(시부키 / 대장 랑)이 소집하는 경우가 많음
                lead.vx = 0
                if not lead.do_persona(2 if lead.char == "shibuki" else 0):   # "자자, 다들 모여 봐!" / "대장 나가신다!"
                    self.group_event()
            else:
                self.group_event()
        self.gt.start(random.randint(60000, 180000))

    def clock(self):
        now = datetime.datetime.now()
        hm = now.strftime("%H:%M")
        alarms = dict(ALARMS); alarms.update(self.cfg.get("alarms", {}))
        off = set(self.cfg.get("alarms_off", []))
        for key, at in alarms.items():
            if key in off:
                continue
            if at == hm and self.alarm_done.get(key) != now.date():
                self.alarm_done[key] = now.date()
                self.alarm(key)

    def alarm(self, key):
        """특별 이벤트 알림: 화면에 있는 아이들이 각자 말투로 차례차례"""
        if self.group:
            self.group_break()
        if self.scene:
            self.scene_end()
        act, ticks = ALARM_ACT[key]
        order = self.buddies[:]
        random.shuffle(order)
        for i, b in enumerate(order):
            def go(b=b):
                if b not in self.buddies or b.drag is not None:
                    return
                if b.state in self.BUSY or b.surface is None:
                    scr = b.scr()
                    b.drop_rope(); b.setWindowOpacity(PET_ALPHA["a"]); b.show()
                    b.stand_on((scr.left() - 9999, scr.bottom(), scr.right() + 9999))
                b.goal = None; b.vx = 0
                b.set(act, ticks, after="sleep" if key == "night" else None)
                lines = ALARM_LINES.get(b.char, ALARM_DEFAULT)[key]
                b.say(random.choice(lines), 330)
            QTimer.singleShot(i * 1300, go)

    def watchdog(self):
        """한 명씩 모드 안전장치: 어떤 이유로든 사라진 친구가 있으면 잠시 뒤 돌아오게"""
        if not (self.one_each and self.team) or self.scene:
            return
        for c in self.live_team():
            if c not in self.pending and not any(b.char == c for b in self.buddies):
                self.pending.add(c)
                QTimer.singleShot(random.randint(4000, 8000), lambda c=c: self.return_home(c))

    def add(self, x=None, entrance=None, char=None):
        if self.one_each and self.team:
            char = char or self.pick_char()
            live = self.live_team()
            if char not in live or any(b.char == char for b in self.buddies if b.state not in ("balloon", "dig")) \
                    or sum(1 for b in self.buddies if b.char in live and b.state not in ("balloon", "dig")) >= len(live):
                return                                  # 한 명씩만! (지금 화면 멤버만, 최대 인원까지)
            lim = MAX_COUNT
        else:
            lim = self.cap()
        if sum(1 for b in self.buddies if b.state not in ("balloon", "dig")) < lim:
            self.buddies.append(Buddy(self, self.size, x, entrance, char))

    def ahead(self, me):
        """같은 바닥 위, 바로 앞에 있는 친구"""
        for b in self.buddies:
            if b is not me and b.surface == me.surface and b.surface is not None:
                dx = (b.cx - me.cx) * me.face
                if 0 < dx < me.S * 0.6:
                    return b
        return None

    def leave(self, b, travel=False):
        """풍선 타고 / 땅속으로 퇴장. travel=True면 잠시 후 다른 곳에서 다시 등장"""
        if b.surface is None or b not in self.buddies:
            return
        b.travel = travel
        b.vx = 0
        floor = b.surface[2] - b.surface[0] > 5000
        if travel and self.quiet():  # 한 자리에 있기: 산책 퇴장 안 함
            return
        no_sky = self.cfg.get("no_sky", False) or self.quiet()
        if no_sky and not floor:                    # 하늘로 안 올라가기: 창 위면 먼저 바닥으로 내려감
            b.fall(vx=0)
            return
        if floor and (no_sky or random.random() < 0.5):
            b.set("dig", 110)
        else:
            b.set("balloon")

    def finished(self, b):
        if b not in self.buddies:
            return
        travel = getattr(b, "travel", False)
        self.buddies.remove(b)
        b.drop_rope()
        b.close()
        if travel:
            # 한 명씩 모드에선 '나간 그 아이'가 돌아와야 함 (예전엔 다른 애가 대신 오려다 막혀서 사라지는 버그)
            ch = b.char if self.one_each else self.pick_char()
            self.pending.add(ch)
            QTimer.singleShot(random.randint(3000, 9000), lambda: self.return_home(ch))

    def collide(self):
        """던져진(또는 튕겨난) 빙하유가 다른 빙하유와 쾅!"""
        for k in list(self.hit_cool):
            self.hit_cool[k] -= 1
            if self.hit_cool[k] <= 0:
                del self.hit_cool[k]
        movers = [b for b in self.buddies if b.state == "air" and b.drag is None
                  and b.air_kind in ("thrown", "knocked") and abs(b.vx) + abs(b.vy) > 6]
        for a in movers:
            for b in self.buddies:
                if b is a or b.drag is not None or b.state in ("balloon", "dig", "rope", "rope_pause", "peek"):
                    continue
                key = (id(a), id(b)) if id(a) < id(b) else (id(b), id(a))
                if key in self.hit_cool:
                    continue
                ax, ay = a.cx, a.fy + a.S * 0.6
                bx, by = b.cx, b.fy + b.S * 0.6
                if math.hypot(ax - bx, ay - by) > (a.S + b.S) * 0.27:
                    continue
                self.hit_cool[key] = 45
                Burst((ax + bx) / 2, (ay + by) / 2, (a.S + b.S) * 0.4)
                d = 1 if bx > ax else -1
                speed = math.hypot(a.vx, a.vy)
                ready = b.surface is not None and b.state in ("idle", "walk", "cheer", "wave", "dance", "milk", "read")
                if ready and speed < 16 and random.random() < 0.2:
                    # 덥석! 받아내기
                    b.vx = 0; b.face = -d
                    b.set("catch", 55, after="caught")
                    a.vx = -d * 1.2; a.vy = -5; a.air_kind = "hop"; a.angle = 0
                    a.react_next = None
                    continue
                # 퍽! 맞은 아이는 뒤로 튕겨 날아가고, 던져진 아이는 반동으로 튕김
                b.drop_rope()
                b.setWindowOpacity(PET_ALPHA["a"])
                b.surface = None
                b.face = -d
                b.vx = d * max(4.0, speed * 0.65)
                b.vy = min(b.vy, 0) - random.uniform(5, 9)
                b.air_kind = "knocked"; b.fall_from = b.fy; b.angle = 0
                b.knock_t = 10
                b.set("air")
                b.grudge = a
                b.react_next = random.choice(["bump", "bump", "dizzy", "dizzy", "faint", "rub"])
                b.say({"rin": "뇨-?! What…", "riko": "으앗, 용사가 쓰러진다!", "shibuki": "아야! 누가 던졌어!", "nana": "누고!! 누가 던졌노!",
                       "toa": "아야! 누구야, 퇴마한다?!", "rang": "감히 대장을?!", "hiyori": "뿌엥… 아파…",
                       "mary": "%#@! 누가 던졌냐!!",
                       "hina": "으앗! 누구예요?!", "mashiro": "냐악! 해고야 해고!", "lize": "느엥… 미웡…",
                       "tabi": "왜 또 나만 패!!", "yuni": "아파가 와!!", "kanna": "너 죽고 싶니?!",
                       "huya": "떽!! …히잉", "bingha": "아야… 억까예요!", "chune": "아야! 누가 던졌노!!", "arisa": "아야… 믿지 않아…", "karin": "아얏! 너 뉘기야!", "eris": "흐잉… 나 안해!", "ellie": "아야! 익스플로전 맞고 싶냐!"}.get(b.char, "아야!"), 90)
                self.laugh_near(b)
                a.vx = -d * abs(a.vx) * 0.35
                a.vy = -abs(a.vy) * 0.3 - 3
                a.react_next = random.choice(["rub", "dizzy", "bump", None])

    # ── 합본 전용: 서로 다른 캐릭터끼리 노는 이벤트 ─────────────
    DUO_FREE = ("idle", "walk", "crawl", "read", "milk", "cheer", "wave")

    def pairs(self, near=900):
        out = []
        for i, a in enumerate(self.buddies):
            for b in self.buddies[i + 1:]:
                if a.char != b.char and a.surface and a.surface == b.surface and abs(a.cx - b.cx) < near \
                        and a.state in self.DUO_FREE and b.state in self.DUO_FREE and a.goal is None and b.goal is None:
                    out.append((a, b))
        random.shuffle(out)
        return out

    def duo_tick(self):
        if not self.team or not self.buddies:
            return
        for c in self.buddies:      # 우는 친구는 다른 캐릭터가 달래 주러 와요
            if c.state == "cry" and c.surface and not getattr(c, "comforted", False):
                helpers = [h for h in self.buddies if h.char != c.char and h.surface == c.surface
                           and h.goal is None and h.state in ("idle", "walk", "crawl", "read", "milk")
                           and abs(h.cx - c.cx) < 900]
                if helpers:
                    h = min(helpers, key=lambda h: abs(h.cx - c.cx))
                    c.comforted = True
                    def arrive(h, c):
                        h.set(random.choice(["kiss", "wave"]), 90)
                        if c.state == "cry":
                            c.face = 1 if h.cx > c.cx else -1
                            c.set("happy", 120)
                        c.comforted = False
                    h.go_to(c, "approach", arrive, speed=2.4)
                    return
        if touhou.try_automatic(self):
            return
        if random.random() < 0.22:
            self.duo_event(random.choice(["tag", "tag", "snack", "dance", "nap", "greet"]))

    BUSY = ("air", "hang", "sit_edge", "climb", "rope", "rope_pause", "wallclimb", "wallslide",
            "balloon", "dig", "peek", "umbrella")

    def force_pair(self, kind, retry=True):
        """메뉴에서 시킨 놀이: 하던 걸 멈추고서라도 짝을 찾아 시작. 짝이 없으면 데려옴"""
        team = self.live_team() if self.one_each else self.team
        have = {n: [b for b in self.buddies if b.char == n and b.drag is None] for n in team}
        for n in team:                         # 한쪽 캐릭터가 아예 없으면 불러오기
            if not have[n]:
                self.add(None, "drop", n)
        ground = [b for b in self.buddies if b.surface and b.state not in self.BUSY and b.drag is None]
        best = None
        for i, a in enumerate(ground):
            for b in ground[i + 1:]:
                if a.char != b.char and a.surface == b.surface:
                    d = abs(a.cx - b.cx)
                    if best is None or d < best[0]:
                        best = (d, a, b)
        if best:
            _, a, b = best
            for x in (a, b):
                x.goal = None; x.vx = 0; x.after = None; x.set("idle", 30)
            return a, b
        if retry:
            # 같은 바닥에 짝이 없으면: 한 명을 다른 캐릭터 옆으로 떨어뜨려 데려오고 잠시 뒤 다시 시도
            a = next((x for x in ground), None)
            others = [x for x in self.buddies if a and x.char != a.char and x.drag is None]
            if a and others:
                b = random.choice(others)
                b.drop_rope(); b.goal = None
                b.fx = a.fx + random.choice([-1, 1]) * a.S * 1.6
                b.fy = float(b.scr().top() - b.S)
                b.vy = 0
                b.fall(vx=0)
            QTimer.singleShot(2600, lambda: self.duo_event(kind, force=True, retry=False))
        return None

    def duo_event(self, kind, force=False, retry=True):
        if force:
            pr = self.force_pair(kind, retry)
            if not pr:
                return
            a, b = pr
        else:
            ps = self.pairs(near=900)
            if not ps:
                return
            a, b = ps[0]
        if kind == "tag":
            self.start_tag(a, b, rounds=random.randint(2, 4))
        elif kind == "snack":
            food = random.choice(["eat", "milk"])
            a.vx = 0; a.set(food, 400)
            b.go_to(a, "approach", lambda b, a: b.set(food, 300))
        elif kind == "dance":
            a.vx = 0; a.set("sing", 360)
            b.go_to(a, "approach", lambda b, a: b.set("dance", 300), speed=2.4)
        elif kind == "nap":
            a.vx = 0; a.set("yawn", 80, after="nap")
            b.go_to(a, "approach", lambda b, a: b.set("yawn", 70, after="nap"))
        elif kind == "greet":
            def arrive(b, a):
                b.set(random.choice(["wave", "kiss", "cheer"]), 80)
                a.face = 1 if b.cx > a.cx else -1
                a.vx = 0; a.set(random.choice(["wave", "cheer", "happy"]), 80)
            b.go_to(a, "approach", arrive, speed=3.2)

    def start_tag(self, it, runner, rounds):
        """술래잡기: 잡히면 술래가 바뀌어요"""
        def caught(it, runner):
            Burst((it.cx + runner.cx) / 2, runner.fy + runner.S * 0.5, runner.S * 0.5)
            runner.goal = None
            if rounds <= 1:
                for x in (it, runner):
                    x.vx = 0; x.set(random.choice(["cheer", "dance"]), 120)
                return
            runner.vx = 0; runner.set("surprise", 30)
            it.vx = 0; it.set("cheer", 30)
            QTimer.singleShot(700, lambda: (runner in self.buddies and it in self.buddies
                                            and runner.surface is not None and runner.surface == it.surface
                                            and self.start_tag(runner, it, rounds - 1)))
        it.go_to(runner, "chase", caught, ticks=700)
        runner.go_to(it, "flee", None, ticks=700)

    def force_persona(self, bd, i):
        """메뉴로 시킨 개성 동작: 공중·매달림 중이면 바닥으로 데려와서라도 실행"""
        if bd not in self.buddies or bd.drag is not None:
            return
        if bd.state in self.BUSY or bd.surface is None or bd.state in ("group", "gather", "tower", "train"):
            if self.group and bd in self.group.get("mem", []):
                self.group_break()
            scr = bd.scr()
            bd.drop_rope(); bd.setWindowOpacity(PET_ALPHA["a"]); bd.show()
            bd.stand_on((scr.left() - 9999, scr.bottom(), scr.right() + 9999))
            bd.fx = max(scr.left(), min(scr.right() - bd.S, bd.fx))
        bd.goal = None; bd.vx = 0; bd.after = None
        bd.do_persona(i)

    def scene_end(self):
        sc, self.scene = self.scene, None
        mem = [b for b in getattr(self, "scene_mem", []) if b in self.buddies]
        n = len(mem)
        cx = sc.fx + sc.w / 2
        floor_y = sc.floor
        sc.end()
        for i, b in enumerate(mem):
            b.fx = cx + (i - (n - 1) / 2) * b.S * 0.7 - b.S / 2
            if sc.face != sc.art:
                b.fx = cx - (i - (n - 1) / 2) * b.S * 0.7 - b.S / 2
            b.fy = floor_y - b.S * b.fbottom(0)
            b.show(); b.move(int(b.fx), int(b.fy))
            if b.bubble and b.bubble.sticky:
                b.bubble.show()
            b.goal = None; b.vx = 0
            a = sc.after
            if a == "tumble":                       # 피라미드 와르르
                b.surface = None; b.air_kind = "knocked"; b.knock_t = 6
                b.vx = random.uniform(-4, 4); b.vy = -random.uniform(3, 7)
                b.fall_from = b.fy; b.react_next = random.choice(["bump", "dizzy", "rub"])
                b.set("air")
            elif a == "dizzy":                      # 싸움 끝: 어질어질 / 씩씩
                b.set(random.choice(["dizzy", "angry", "rub", "bump"]), 120)
            elif a == "yawn":
                b.set("yawn", 70)
            elif a in ("cheer", "happy", "dance", "pout", "cry"):
                b.set(a, 90)
            else:
                b.set("idle", 40)

    def laugh_near(self, victim):
        """나나는 누가 맞거나 넘어지면 호탕하게 웃어요 (방송 리액션)"""
        for b in self.buddies:
            if b.char in LAUGHER and b is not victim and b.surface and b.goal is None \
                    and b.state in ("idle", "walk", "read", "milk", "persona", "crawl") \
                    and abs(b.cx - victim.cx) < 700 and random.random() < 0.7:
                b.vx = 0; b.face = 1 if victim.cx > b.cx else -1
                if not b.do_persona(LAUGHER[b.char]):            # 와하하하 / 하핫
                    b.set("cheer", 80)
                return

    # ── 4인 단체 동작 ─────────────────────────────────────────
    def group_event(self, kind=None, leader=None, force=False, _try=0):
        """force=True(메뉴에서 시킴): 외출한 친구는 불러오고, 하던 걸 멈추고서라도 모두 데려옴.
        그래도 시작 못 하면 잠시 뒤 다시 시도"""
        if self.quiet() and not force:                  # 한 자리에 있기·수면 중엔 단체 놀이 안 함 (모였다 탑 쌓고 떨어지는 것 방지)
            return
        full = bool(self.one_each and self.team)        # 4인 모드: 단체 놀이는 반드시 전원 참가
        if full:
            force = True
            if kind is None:                             # 시작할 놀이를 먼저 정해 둬야 재시도해도 같은 놀이
                kinds = ["train", "tower", "photo", "hands", "chat", "karaoke"]
                kinds += self.scene_kinds(present=False) * 2
                kind = random.choice(kinds)
            absent = [c for c in self.live_team() if not any(b.char == c for b in self.buddies)]
            for c in absent:                             # 없는 친구는 바로 다시 불러옴
                self.pending.discard(c)
                self.add(None, "drop", c)
            if absent:                                   # 도착할 시간을 주고 나서 시작
                if _try < 4:
                    QTimer.singleShot(2500, lambda: self.group_event(kind, leader, True, _try + 1))
                return
        self._group_event(kind, leader, force)
        if force and not (self.group or self.scene) and _try < 4:
            QTimer.singleShot(2500, lambda: self.group_event(kind, leader, True, _try + 1))

    def _group_event(self, kind=None, leader=None, force=False):
        if force and self.group:
            self.group_break()
        if force and self.scene:
            self.scene_end()
        if self.group or len(self.buddies) < 2:
            return
        if kind is None:
            kinds = ["train", "tower", "photo", "hands", "chat", "karaoke"]
            kinds += self.scene_kinds() * 2      # 합동 장면을 더 자주
            kind = random.choice(kinds)
        sq = kind.split(":")[1] if kind.startswith("scene:") else None
        if sq and (not self.scenes_ok(sq) or self.scene):
            return
        # 모니터가 여럿이면 한 모니터에 있는 애들끼리만 (리더/그룹 기준)
        if sq:
            gscr = screen_for(SQUADS[sq][0])
        elif leader is not None:
            gscr = screen_for(leader.char)
        else:
            cnt = {}
            for c in self.team:
                cnt.setdefault(screen_for(c).name(), []).append(c)
            gscr = screen_for(max(cnt.values(), key=len)[0]) if cnt else target_screen()
        same = lambda c: screen_for(c).name() == gscr.name()
        def mine(b):                       # 합동 장면은 그 그룹 넷만, 나머지는 하던 거 계속
            return b.char in self.live_team() and (sq is None or b.char in SQUADS[sq]) and same(b.char)   # 퇴장 중인 비멤버는 제외
        if force:
            mem = [b for b in self.buddies if b.drag is None and mine(b)]
            for b in mem:
                if b.state in ("balloon", "dig"):               # 나가려던 애도 붙잡아 옴
                    b.travel = False
                    b.state = "idle"
                    b.setWindowOpacity(PET_ALPHA["a"]); b.surface = None
                if b.state in self.BUSY or b.surface is None:
                    b.drop_rope(); b.setWindowOpacity(PET_ALPHA["a"]); b.show()
                    b.surface = None                         # 아래에서 바닥으로 뿅 이동시킴
        else:
            mem = [b for b in self.buddies if b.drag is None and b.state not in self.BUSY + ("tower",) and mine(b)]
        if len(mem) < 2:
            return
        need = len(SQUADS[sq]) if sq else sum(1 for c in self.live_team() if same(c))
        if self.one_each and self.team and len(mem) < need:
            return                                       # 한 명이라도 없으면 시작 안 함 (재시도가 처리)
        scr = gscr.availableGeometry()
        floor = None
        for b in mem:                       # 모두 화면 바닥으로 (창 위에 있으면 떨어뜨려 데려옴)
            b.goal = None; b.after = None; b.vx = 0
            if b.bubble and not b.bubble.sticky:
                b.bubble.close(); b.bubble = None
        cx = (leader.cx if leader and leader in mem else sum(b.cx for b in mem) / len(mem))
        cx = max(scr.left() + 300, min(scr.right() - 300, cx))
        floor = (scr.left() - 9999, scr.bottom(), scr.right() + 9999)
        for i, b in enumerate(mem):         # 창 위·공중에 있는 애는 바닥 모임 장소 근처로 뿅 이동
            if not b.surface or b.surface[2] - b.surface[0] < 5000:
                b.drop_rope()
                b.setWindowOpacity(PET_ALPHA["a"])
                b.fx = cx + (i - len(mem) / 2) * b.S * 0.9 - b.S / 2
                b.stand_on(floor)
                b.vx = 0; b.vy = 0; b.angle = 0
                b.set("idle", 20)
                b.say("뿅!", 40)
        if leader and leader in mem:
            mem.remove(leader); mem.insert(0, leader)
        self.group = {"kind": kind, "mem": mem, "cx": cx, "phase": "wait", "t": 0}

    def group_break(self):
        g, self.group = self.group, None
        if not g:
            return
        touhou.close_group(g)
        for b in g["mem"]:
            if b in self.buddies and b.state in ("group", "gather", "tower", "train"):
                if b.state == "tower":
                    b.fall(vx=random.uniform(-2, 2))
                else:
                    touhou.restore_pet(g, b)
                    b.set("idle", 30)

    def group_step(self):
        g = self.group
        g["t"] += 1
        mem = [b for b in g["mem"] if b in self.buddies]
        if touhou.should_break(self, g, mem):
            self.group_break()
            return
        if len(mem) < 2:
            self.group_break(); return
        g["mem"] = mem
        if g["t"] > 60 * 40:                         # 안전장치
            self.group_break(); return
        floor_ok = all(b.surface and b.surface[2] - b.surface[0] > 5000 for b in mem)
        S = max(b.S for b in mem)
        if g["phase"] == "wait":                     # 모두 바닥에 내려올 때까지
            if floor_ok and all(b.state not in ("air", "land") for b in mem):
                n = len(mem)
                gap = S * (0.62 if g["kind"] in ("hands", "photo", "karaoke", "chat", "pepero") else
                           0.3 if g["kind"].startswith("scene:") else 0.0)
                for i, b in enumerate(mem):
                    b.gx = g["cx"] + (i - (n - 1) / 2) * gap
                    b.set("gather", 99999)
                g["phase"] = "gather"; g["t0"] = g["t"]
            elif g["t"] > 60 * 8:
                self.group_break()
            return
        if g["phase"] == "gather":
            if all(b.state == "group" for b in mem) or g["t"] - g["t0"] > 60 * 8:
                for b in mem:
                    if b.state != "group":
                        b.fx = b.gx - b.S / 2; b.state = "group"
                g["phase"] = "go"; g["t0"] = g["t"]
                self.group_start(g, mem)
            return
        self.group_run(g, mem, g["t"] - g["t0"])

    def group_start(self, g, mem):
        k = g["kind"]
        if touhou.start_group(self, g, mem):
            return
        if k.startswith("scene:"):
            _, sq, name = k.split(":", 2)
            floor_y = mem[0].surface[1]
            for b in mem:
                b.hide()
                if b.bubble and b.bubble.sticky:
                    b.bubble.hide()                      # 장면 끝나면 다시 보여 줌
                elif b.bubble:
                    b.bubble.close(); b.bubble = None
            self.scene = Scene(self, sq, name, g["cx"], floor_y)
            self.scene_mem = mem
            self.group = None
            return
        lines = {"train": ("칙칙폭폭~ 다들 따라와!", "출발이다~!"), "tower": ("인간 탑 쌓자!", "영차, 영차!"),
                 "photo": ("단체사진 찍는다구!", "다들 웃어~"), "hands": ("손 잡자 손!", GROUP_TEXT.get(self.squad, GROUP_TEXT["mixed"])["hands"]),
                 "chat": ("있잖아 있잖아!", "그래서 그래서?"), "karaoke": ("노래방 타임이다!", "한 곡 뽑아 봐!")}[k]
        mem[0].say(lines[0], 120)
        for b in mem:
            b.face = 1 if g["cx"] >= b.cx else -1
        if k == "train":
            lead = mem[0]
            lead.face = random.choice([-1, 1])
            lead.vx = lead.face * 1.3
            lead.set("walk", 600)
            for i, b in enumerate(mem[1:], start=1):
                b.gx = (lead, i)
                b.set("train", 600)
            QTimer.singleShot(1200, lambda: mem[-1].say(lines[1], 100) if mem[-1] in self.buddies else None)
            self.group = None                      # 이후엔 각자 움직임으로 진행
        elif k == "tower":
            order = mem[:]
            random.shuffle(order)
            g["order"] = order
            base = order[0]
            y = base.fy
            x = base.cx
            for i, b in enumerate(order):
                b.state = "tower"; b.face = 1
                b.gframe = [F["ontop"]] if i == len(order) - 1 else [F["prop"]]
                fr = b.gframe[0]
                if i == 0:
                    feet = base.surface[1]
                b.fx = x - b.S / 2
                b.fy = feet - b.S * b.fbottom(fr)
                feet = b.fy + b.S * (b.ftop(fr) + 0.06)     # 다음 사람 발은 이 사람 손 높이
            order[-1].say("우와~ 높다!", 120)
        elif k == "photo":
            for b in mem:
                b.face = 1; b.gframe = [F["photo"]]
            QTimer.singleShot(1800, lambda: (Flash(), [b.say("찰칵!", 70) for b in mem[:1] if b in self.buddies]))
        elif k == "hands":
            for b in mem:
                b.face = 1; b.gframe = [F["hands"]]
        elif k == "chat":
            for i, b in enumerate(mem):
                b.face = 1 if i % 2 == 0 else -1
                b.gframe = [F["chat"], F["chat"], F["lol"]] if i % 2 == 0 else [F["chat"], F["lol"], F["chat"]]
        elif k == "karaoke":
            singer = next((b for b in mem if b.char == "mary"), None)
            if singer:
                mem.remove(singer); mem.insert(0, singer)
            mem[0].gframe = [F["sing"]]
            for b in mem[1:]:
                b.gframe = F["dance"]

    CHAT = {"rapi": ["다음 작전 구역으로 이동합니다.", "…귀신 얘기는 금지입니다.", "지휘관 쪽은 제가 지키겠습니다."],
            "anis": ["탄산수 한 캔씩 돌린다~", "어휴, 라피 또 진지해졌어", "샤워실 쓸 사람 손~!"],
            "marian": ["다들 다친 데 없어요?", "붕대 필요하면 말해요", "지휘관 칭찬받았어요!"],
            "dorothy": ["후후, 흥미롭네요.", "티타임에 초대할까요?", "…귀하들은 정말 시끄럽군요."],
            "elysia": ["어머~ 다들 오늘도 귀엽네♪", "역시 귀여운 소녀는 뭐든 할 수 있다니까♪", "같이 차 마실 사람~?"],
            "scarlet": ["한잔할 텐가? 안주는 달빛과 바람일세.", "허허, 다들 기운이 넘치는구먼.", "밭에 새싹이 났다네."],
            "rin": ["오늘 커버곡 하나 더 올렸어요", "치킨 시킬 사람, anyone?", "뇨… 그거 무서운 얘기예요?"],
            "riko": ["하이용사! 나 점프킹 기록 깼다?", "아하하하 진짜로?", "리코 천재 아니야?"],
            "shibuki": ["자자 다음 얘기 간다!", "구라야~ 그거 구라지?", "그래서 결론이 뭔데!"],
            "nana": ["이거 진짜 대박이제, 보쏘?", "으하하하! 미치겠다", "그거는 내가 설명해 줄게"],
            "toa": ["어제 공포게임 했는데 하나도 안 무서웠어", "…육삼 얘기 꺼낸 사람 누구야", "히요리, 오늘은 퇴마 안 할게~"],
            "rang": ["어제 경기 봤어? 완전 대박!", "그 퍼즐 대장이 30초 만에 풀었지", "쑥은 진짜 못 먹겠어…"],
            "hiyori": ["하핫, 그게 뭔데?", "기특하다구? 고마워~", "놀이공원에 그런 거 있었던 것 같아…"],
            "yuni": ["배고파가 와~", "유니는 귀여우니까 욘서~", "그거 굽 해도 돼?"],
            "bingha": ["저 청초한 토끼인데요?", "오늘도 방송 세팅 깜빡했어요…", "빙식쿤들 밥은 먹었어요?"],
            "kanna": ["레몬 1개에 레몬 4개 분량 비타민 알아요?", "그냥 느껴~", "해리포터 얘기 해도 돼요?"],
            "huya": ["에휴에요 에휴", "…네? (고장)", "후하요~ 저도 끼워 주세요"],
            "hina": ["어제 발로 다이아 각이었는데…", "명천재? 저요?", "도파민즈 합방 또 해요!"],
            "mashiro": ["흠흐밍~ 그건 좀 밍이다", "꺄르륵 그게 뭐야", "자, 지금부터 상황극이야"],
            "lize": ["느엥…", "그죠~?", "…나 지금 낯가리는 중이야"],
            "tabi": ["타비라고 불러 줘, 제대로!", "그거 내가 챙길게", "보물 지도 새로 구했다?"],
            "mary": ["어제 방송 다시 봤는데 냐…", "그거 저주 아니다 냐, 노래다 냐", "단추들한테 솜 던지기 당했다 냐"],
            "chune": ["계추!! 다들 밥은 묵었나?", "어제 홀란드 골 봤나? 미쳤다 진짜", "집 밖은 위험하다, 진짜로"],
            "arisa": ["여러분 식사는 하셨나요?", "오느른… 켠왕할 거예요", "콜라 사러 가야 되는데 나가기 싫어요"], "karin": ["어제 새 네일 했는데 봤어?", "T1 경기 같이 볼 사람~", "기습 공연 할까?"], "eris": ["앙용~ 다들 뭐해?", "근끼 또 쳐내래…", "민트초코 먹고 싶다"], "ellie": ["얄루~ 롤 한 판 할 사람?", "웰키가 또 날 무시했어", "익스플로전!! …아 그냥 해 봤어"]}

    def tower_tick(self, g, t, *, recenter=False):
        order = [b for b in g["order"] if b in self.buddies]
        if len(order) < len(g["order"]):
            self.group_break()
            return
        wob = math.sin(t / 9) * min(1.0, t / 120) * 3 * SHAKE["k"]
        for i, b in enumerate(order):
            if recenter:
                b.fx = g["cx"] - b.S / 2 + wob * i * 0.7
            else:
                b.fx += wob * i * 0.15
        if t == 60 * 3:
            order[0].say("으으… 무거워…", 90)
        if t > 60 * 5:                       # 와르르!
            self.group = None
            for i, b in enumerate(order):
                b.state = "air"; b.surface = None
                b.air_kind = "knocked" if i > 0 else "fall"
                b.vx = random.uniform(-4, 4) * (i + 1) * 0.5
                b.vy = -random.uniform(2, 6) if i > 0 else 0
                b.fall_from = b.fy; b.knock_t = 6
                b.react_next = random.choice(["bump", "dizzy", "rub"])
            Burst(order[0].cx, order[0].fy, order[0].S * 0.8)
            QTimer.singleShot(1500, lambda: [b.do_persona(LAUGHER[b.char]) for b in self.buddies if b.char in LAUGHER and b.surface])

    def group_run(self, g, mem, t):
        k = g["kind"]
        if touhou.advance_group(self, g, mem, t):
            return
        if k == "tower":
            self.tower_tick(g, t)
            return
        if k == "chat" and t % 140 == 10:
            b = random.choice(mem)
            b.say(random.choice(self.CHAT.get(b.char, ["그치그치"])), 110)
        if k == "karaoke" and t % 200 == 10:
            mem[0].say(random.choice(GROUP_TEXT.get(self.squad, GROUP_TEXT["mixed"])["song"]), 120)
        if k == "hands" and t % 30 == 0:
            for i, b in enumerate(mem):
                if b.surface and b.state == "group":
                    b.fy = b.surface[1] - b.S * b.fbottom(0) - (4 if (t // 30 + i) % 2 else 0)
        dur = {"photo": 60 * 5, "hands": 60 * 6, "chat": 60 * 11, "karaoke": 60 * 10}[k]
        if t > dur:
            self.group = None
            for b in mem:
                b.fy = b.surface[1] - b.S * b.fbottom(0) if b.surface else b.fy
                b.set(random.choice(["cheer", "dance", "idle"]), 80)

    def landed_near(self, who):
        for b in self.buddies:
            if b is not who and b.surface == who.surface and abs(b.cx - who.cx) < who.S * 1.3:
                if b.state in ("walk", "idle", "eat", "dance") and not b.cool:
                    b.vx = 0; b.cool = 200
                    b.face = 1 if who.cx > b.cx else -1
                    b.set("surprise", 45)

    def rain(self, n=8, char=None):
        """빙하유(친구들) 비가 내려요"""
        scr = target_screen().availableGeometry()
        for i in range(n):
            x = random.randint(scr.left() + 50, scr.right() - 50)
            QTimer.singleShot(i * 250, lambda x=x: self.add(x, random.choice(["drop", "umbrella", "umbrella", "rope"]), char or self.pick_char()))

    def remove(self, b=None):
        if self.buddies:
            b = b or self.buddies[-1]
            self.buddies.remove(b)
            b.drop_rope()
            b.close()

    def surprise(self):
        """가끔 깜짝 이벤트"""
        if not self.buddies or self.quiet():          # 한 자리에 있기·수면 중엔 하늘에서 뚝 같은 깜짝 이벤트 없음
            return
        r = random.random()
        b = random.choice(self.buddies)
        if b.state in ("hang", "sit_edge", "climb", "air") or b.drag is not None:
            return
        if r < 0.15:      # 다 같이 춤
            for x in self.buddies:
                if x.state in ("walk", "idle", "run") and x.surface:
                    x.vx = 0; x.set("dance", random.randint(150, 300))
        elif r < 0.35:      # 하늘에서 다시 뚝
            scr = b.scr()
            b.fx = float(random.randint(scr.left(), scr.right() - b.S))
            b.fy = float(scr.top() - b.S)
            b.fall(vx=random.uniform(-1, 1))
        elif r < 0.6:     # 다 같이 만세
            for x in self.buddies:
                if x.state in ("walk", "idle", "run") and x.surface:
                    x.vx = 0; x.set("cheer", 90)

    def all_drop(self):
        n = len(self.buddies)
        for i, b in enumerate(self.buddies):
            scr = b.scr()
            b.fx = float(scr.left() + (i + 1) * scr.width() / (n + 1) - b.S / 2)
            b.fy = float(scr.top() - b.S - i * 50)
            b.vy = 0
            b.drop_rope()
            b.fall(vx=0)

    # ── 윈도우 시작 시 자동 실행 (시작프로그램 폴더에 작은 실행 파일을 만들어 둠) ──
    def autostart_path(self):
        startup = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows",
                               "Start Menu", "Programs", "Startup")
        arg = sys.argv[1] if len(sys.argv) > 1 else self.mode
        safe = "".join(ch if ch.isalnum() else "_" for ch in arg)
        return startup, os.path.join(startup, f"RabbitPet_{safe}.vbs")

    def autostart_on(self):
        try:
            return os.path.exists(self.autostart_path()[1])
        except Exception:
            return False

    def set_autostart(self, on):
        try:
            folder, path = self.autostart_path()
            if not on:
                if os.path.exists(path):
                    os.remove(path)
                return
            if not os.path.isdir(folder):
                return
            exe = sys.executable
            if exe.lower().endswith("python.exe"):          # 창 없이 실행되는 pythonw 사용
                w = exe[:-10] + "pythonw.exe"
                if os.path.exists(w):
                    exe = w
            script = os.path.abspath(sys.argv[0]) if sys.argv[0].endswith(".py") else ENTRY_SCRIPT
            arg = sys.argv[1] if len(sys.argv) > 1 else self.mode
            q = lambda s: '""' + s + '""'
            line = ('Set sh = CreateObject("WScript.Shell")\r\n'
                    f'sh.CurrentDirectory = "{os.path.dirname(script)}"\r\n'
                    f'sh.Run "{q(exe)} {q(script)} {arg}", 0, False\r\n')
            with open(path, "w", encoding="utf-16") as f:       # 한글 경로도 OK
                f.write(line)
        except Exception:
            pass

    def set_screen(self, sc):
        """다른 모니터로 이사: 장면·단체 놀이는 끝내고 모두 새 모니터 하늘에서 뚝"""
        primary = sc is QApplication.primaryScreen()
        SCREEN["name"] = None if primary else sc.name()
        if primary:
            self.cfg.pop("screen", None)
        else:
            self.cfg["screen"] = sc.name()
        self.save_cfg()
        if self.scene:
            self.scene_end()
        if self.group:
            self.group_break()
        self.scan()
        self.all_drop()

    def set_shake(self, kv):
        SHAKE["k"] = kv
        self.cfg["shake"] = kv
        self.save_cfg()

    def set_varied(self, on):
        self.cfg["varied"] = bool(on)
        for b in self.buddies:
            b.scale = random.uniform(0.8, 1.15) if on else 1.0
        self.set_size(self.size)

    def stay_gate(self, b):
        """한 자리에 있기: 자리로 돌아가는 걸음 말고는 옆으로 못 움직이게. True면 이번 틱은 여기서 끝"""
        st = b.state
        if getattr(b, "goal", None) is not None:
            b.goal = None
        if st == "persona" and getattr(b, "pvx", 0):
            b.pvx = 0
            return False
        if st == "push":
            b.vx = 0
            b.set("idle", random.randint(60, 160))
            return True
        if st not in ("walk", "run", "roll", "crawl"):
            return False
        hx = self.stay_home(b)                       # 걷는 모션 없이 자리에 두고 얌전히 대기
        if hx is not None:
            b.fx = float(hx - b.S / 2)
            b.move(int(b.fx), int(b.fy))
        b.vx = 0
        b.set("idle", random.randint(60, 160))
        return True

    def stay_home(self, b):
        """한 자리에 있기: 각 꼬마가 돌아가 기다릴 x 좌표"""
        side = self.cfg.get("stay_side", "right")
        if self.cfg.get("sleep_mode", False) and not self.cfg.get("stay", False):
            side = "right"                          # 수면 모드: 오른쪽 아래 구석
        if side == "here":
            return getattr(b, "_home", None)
        try:
            g = b.scr()
            mates = [o for o in self.buddies if o.scr() == g]
            i = mates.index(b) if b in mates else 0
        except Exception:
            return None
        gap = b.S * 0.7
        per = max(1, int(g.width() * 0.45 / max(1, gap)))
        i = i % per
        if side == "left":
            return g.left() + b.S * 0.6 + i * gap
        if side in ("center", "custom"):
            pct = 50.0 if side == "center" else max(0.0, min(100.0, float(self.cfg.get("stay_x", 80))))
            c = g.left() + g.width() * pct / 100.0
            off = ((i + 1) // 2) * gap * (1 if i % 2 else -1)
            return max(g.left() + b.S * 0.6, min(g.right() - b.S * 0.6, c + off))
        return g.right() - b.S * 0.6 - i * gap

    def set_size(self, s):
        self.size = s
        self.cfg["size"] = s
        self.save_cfg()
        for b in self.buddies:
            bottom = b.fy + b.S
            b.S = int(s * b.scale * char_scale(self.cfg, b.char)); b.setFixedSize(b.S, b.S); b.fy = bottom - b.S

    def quiet(self):
        """한 자리에 있기 또는 수면 모드: 돌아다니지 않음"""
        return bool(self.cfg.get("stay", False) or self.cfg.get("sleep_mode", False))

    def set_sleep(self, on):
        """수면 모드: 깨울 때까지 한쪽 구석에서 쿨쿨"""
        self.cfg["sleep_mode"] = bool(on)
        self.save_cfg()
        for b in list(self.buddies):
            b.goal = None
            if on:
                if b.surface and b.drag is None:
                    b.choose()
            elif b.state == "sleep":
                b.set("yawn", 70)

    def set_stay(self, on):
        """한 자리에 있기 켜고 끄기 (트레이 메뉴)"""
        self.cfg["stay"] = bool(on)
        for b in self.buddies:
            b._home = b.cx
            b.goal = None
        self.save_cfg()

    def app_path(self, key):
        """내 앱이 깔려 있으면 exe 경로 (윈도우 프로그램 목록 → 기본 설치 폴더 순으로 찾음)"""
        a = MY_APPS[key]
        try:
            import winreg
            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for sub in (r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
                            r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"):
                    try:
                        k = winreg.OpenKey(root, sub)
                    except OSError:
                        continue
                    for i in range(winreg.QueryInfoKey(k)[0]):
                        try:
                            sk = winreg.OpenKey(k, winreg.EnumKey(k, i))
                            dn = str(winreg.QueryValueEx(sk, "DisplayName")[0]).lower()
                        except OSError:
                            continue
                        if not any(m in dn for m in a["match"]):
                            continue
                        for val in ("DisplayIcon", "InstallLocation"):
                            try:
                                v = str(winreg.QueryValueEx(sk, val)[0]).split(",")[0].strip().strip('"')
                            except OSError:
                                continue
                            cands = [v] if v.lower().endswith(".exe") else [os.path.join(v, e) for e in a["exe"]]
                            for c in cands:
                                if os.path.isfile(c) and "uninst" not in os.path.basename(c).lower():
                                    return c
        except Exception:
            pass
        base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")
        for d in a["dirs"]:
            for e in a["exe"]:
                c = os.path.join(base, d, e)
                if os.path.isfile(c):
                    return c
        return None

    def _app_say(self, who, text, secs=6):
        try:
            if who is not None and who in self.buddies:
                self.force_say(who, text, secs)
            elif getattr(self, "tray", None) is not None:
                self.tray.showMessage(APP_NAME, text)
        except Exception:
            pass

    def open_app(self, key, files=None, b=None):
        """내 앱(코덱무관플레이어·이름표) 켜기 — 안 깔려 있으면 최신 설치 파일을 받아 조용히 설치까지"""
        import subprocess
        a = MY_APPS[key]
        who = b if b is not None else (random.choice(self.buddies) if self.buddies else None)
        exe = self.app_path(key)
        if exe:
            try:
                subprocess.Popen([exe] + list(files or []), cwd=os.path.dirname(exe))
                if who is not None and who in self.buddies:
                    who.say(random.choice(a["hi"]), 120)
            except Exception as ex:
                self._app_say(who, f"{a['name']} 못 켰어… ({str(ex)[:60]})")
            return
        if getattr(self, "_app_inst", None):
            self._app_say(who, "지금 설치하는 중이야~ 조금만 기다려!")
            return
        box = QMessageBox(QMessageBox.Question, APP_NAME,
                          f"{a['name']}가 아직 안 깔려 있어요.\n펫이 최신 설치 파일을 받아서 바로 설치할까요? (1~2분)",
                          QMessageBox.Yes | QMessageBox.No)
        if box.exec_() != QMessageBox.Yes:
            return
        self.install_app(key, files, who)

    def install_app(self, key, files=None, who=None):
        import subprocess, tempfile, urllib.request
        a = MY_APPS[key]
        self._app_inst = key
        self._app_res = None
        self._app_say(who, f"{a['name']} 받아 오는 중… 잠깐만!", 8)

        def work():
            err = ""
            try:
                hdr = {"User-Agent": "minibuddies-pet"}
                req = urllib.request.Request(f"https://api.github.com/repos/{a['repo']}/releases/latest",
                                             headers=dict(hdr, Accept="application/vnd.github+json"))
                rel = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))
                asset = next(x for x in rel.get("assets", [])
                             if x["name"].startswith(a["asset"]) and x["name"].lower().endswith(".exe"))
                dst = os.path.join(tempfile.gettempdir(), asset["name"])
                with urllib.request.urlopen(urllib.request.Request(asset["browser_download_url"], headers=hdr),
                                            timeout=60) as r:
                    with open(dst, "wb") as f:
                        shutil.copyfileobj(r, f)
                subprocess.run([dst] + a["silent"], timeout=900)
            except StopIteration:
                err = "설치 파일을 못 찾았어"
            except Exception as ex:
                err = str(ex)[:80] or "알 수 없는 오류"
            self._app_res = (key, err, list(files or []), who)

        def poll():
            if self._app_res is None:
                return
            self._app_poll.stop()
            k, err, fl, w = self._app_res
            self._app_inst = None
            nm = MY_APPS[k]["name"]
            if err:
                self._app_say(w, f"{nm} 설치 실패… ({err})", 10)
            elif self.app_path(k):
                self._app_say(w, f"{nm} 설치 끝! 켤게~", 5)
                self.open_app(k, fl, w)
            else:
                self._app_say(w, f"설치는 끝났는데 {nm}를 못 찾겠어… 시작 메뉴에서 켜 줘!", 10)

        self._app_poll = QTimer(timeout=poll)
        self._app_poll.start(700)
        threading.Thread(target=work, daemon=True).start()

    def cap(self):
        """화면 최대 등장 인원 (환경설정, 기본 5명)"""
        try:
            return max(1, min(MAX_COUNT, int(self.cfg.get("max_on", 5))))
        except Exception:
            return 5

    def live_team(self):
        """지금 화면에 나와 있을 멤버 (최대 인원 안쪽). 고른 친구가 더 많으면 rotate_live 가 교대"""
        t = self.team or []
        n = self.cap()
        if len(t) <= n:
            self.live = t[:]
            return self.live
        cur = [c for c in getattr(self, "live", []) if c in t][:n]
        if len(cur) < n:
            rest = [c for c in t if c not in cur]
            random.shuffle(rest)
            cur += rest[:n - len(cur)]
        self.live = cur
        return self.live

    def rotate_live(self):
        """고른 친구가 최대 인원보다 많으면 한 명씩 교대"""
        t = self.team or []
        if not self.one_each or len(t) <= self.cap() or self.quiet() or self.group or self.scene:
            return
        live = self.live_team()
        rest = [c for c in t if c not in live]
        outs = [b for b in self.buddies if b.char in live and b.surface and b.drag is None and b.state not in self.BUSY]
        if not rest or not outs:
            return
        b = random.choice(outs)
        inn = random.choice(rest)
        self.live = [c for c in live if c != b.char] + [inn]
        try:
            b.say(random.choice(["교대할게~ 이따 봐!", "잠깐 쉬러 갈게~", "다음 친구 차례야!"]))
        except Exception:
            pass
        QTimer.singleShot(1600, lambda: None if b.state in ("balloon", "dig") else self.leave(b))
        QTimer.singleShot(4200, lambda: self.add(None, random.choice(["drop", "peek", "umbrella", "rope"]), inn))

    def max_changed(self):
        """최대 인원을 바꾸면: 넘치는 아이는 퇴장, 자리가 나면 새로 등장"""
        if self.one_each and self.team:
            self.live = getattr(self, "live", [])[:self.cap()]
            live = self.live_team()
            out = [b for b in self.buddies if b.char not in live and b.state not in ("balloon", "dig")]
            QTimer.singleShot(1500, self.watchdog)
        else:
            out = [b for b in self.buddies if b.state not in ("balloon", "dig")][self.cap():]
        for b in out:
            if b.surface and b.drag is None and b.state not in self.BUSY:
                self.leave(b)
            else:
                self.remove(b)

    def sweep_strays(self):
        """빼기로 한 아이가 퇴장 도중 붙잡혀(던져져) 화면에 남아 있으면 다시 내보냄"""
        gone = set(getattr(self, "_dismissed", None) or ())
        if self.one_each and self.team:                  # 최대 인원 밖(교대 대기) 아이도 정리
            gone |= {c for c in self.team if c not in self.live_team()}
        if not gone:
            return
        team = self.live_team() if (self.one_each and self.team) else (self.team or [])
        for b in list(self.buddies):
            if b.char not in gone or b.char in team or b.drag is not None or b.state in ("balloon", "dig"):
                continue
            if b.surface and b.state not in self.BUSY:
                self.leave(b)

    def run(self):
        sys.exit(self.qapp.exec_())

    touhou_members = touhou.touhou_members
    touhou_play = touhou.touhou_play
    touhou_duel_tick = touhou.touhou_duel_tick


legacy.install(App, Buddy)
