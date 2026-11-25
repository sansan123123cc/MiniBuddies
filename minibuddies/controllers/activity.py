"""Alarms, reminders, affinity and cursor interactions."""

import datetime
import random
import sys
import threading
import time
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QApplication
from minibuddies.catalog import (
    AFF_LV,
    AFF_NAME,
    ALARMS,
    ALARM_ACT,
    ALARM_DEFAULT,
    ALARM_LINES,
    AWAY_LINES,
    BIRTHDAY_FRIEND,
    BIRTHDAY_SELF,
    CASUAL_CHARS,
    CHAR_BIRTHDAY,
    CURSOR_LINES,
    CURSOR_LINES_P,
    HOLIDAYS,
    SYS_LINES,
    TOUCH_LINES,
    WELCOME_LINES,
)
from minibuddies.desktop import CURSOR
from minibuddies.features.passthrough import PET_ALPHA
from minibuddies.features.rest import _rest_on
from minibuddies.runtime import _crash_write


class ActivityController:
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
