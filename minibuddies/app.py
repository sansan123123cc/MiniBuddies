"""MiniBuddies composition, application lifecycle and settings."""

import json
import os
import queue
import random
import sys
from pathlib import Path
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication
from minibuddies.authoring.installed import load_content, mount_skins
from minibuddies.catalog import (
    BUBBLE_PX,
    OUTFIT_NAME,
    SCENES,
    SCENES_ABYSS,
    SCENES_GEN1,
    SCENES_UNIVERSE,
    SHAKE,
    SQUADS,
    START_COUNT,
    TICK,
    persona_of,
)
from minibuddies.controllers.activity import ActivityController
from minibuddies.controllers.assistant import AssistantController
from minibuddies.controllers.bridge import CommandBridge
from minibuddies.controllers.distribution import DistributionController
from minibuddies.controllers.groups import GroupController
from minibuddies.controllers.integrations import ExternalAppsController
from minibuddies.controllers.music import MusicController
from minibuddies.controllers.outfits import OutfitController
from minibuddies.controllers.roster import RosterController
from minibuddies.controllers.sprites import SpriteCache
from minibuddies.controllers.usage import UsageController
from minibuddies.controllers.windows import WindowController
from minibuddies.desktop import CHAR_SCREEN, SCREEN
from minibuddies.features import install_builtin
from minibuddies.pets import Buddy
from minibuddies.plugins import PluginLibrary
from minibuddies.runtime import BASE, CHARS_DIR, ENTRY_SCRIPT, _crash_write
from minibuddies.ui.menus import AppMenus


class App(
    AppMenus,
    AssistantController,
    CommandBridge,
    DistributionController,
    UsageController,
    WindowController,
    MusicController,
    ActivityController,
    OutfitController,
    GroupController,
    RosterController,
    SpriteCache,
    ExternalAppsController,
):
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
        self.content_root = Path(BASE) / "user-packs"
        custom, authored_skins = load_content(self.content_root, set(self.chars) | set(self.outfits), _crash_write)
        self.chars.update(custom)
        for base, skins in authored_skins.items():
            mount_skins(self.chars, self.outfits, base, skins)
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
        if custom:
            if not self.team:
                self.team = [arg if arg in self.chars else next((c for c in ("elysia", "bingha") if c in self.chars), next(iter(self.chars)))]
            self.one_each = True
            self.team = list(dict.fromkeys([*self.team, *custom]))
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
        self.plugins = PluginLibrary(os.path.join(BASE, "plugins"), _crash_write, self.content_root)
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

    def tick(self):
        self._tk = getattr(self, "_tk", 0) + 1
        if self._tk % 30 == 0:
            self.plugins.tick_periodic(self)
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

    def watchdog(self):
        """한 명씩 모드 안전장치: 어떤 이유로든 사라진 친구가 있으면 잠시 뒤 돌아오게"""
        if not (self.one_each and self.team) or self.scene:
            return
        for c in self.live_team():
            if c not in self.pending and not any(b.char == c for b in self.buddies):
                self.pending.add(c)
                QTimer.singleShot(random.randint(4000, 8000), lambda c=c: self.return_home(c))

    def run(self):
        sys.exit(self.qapp.exec_())


install_builtin(App, Buddy)
