"""Pet roster, spawning and collision coordination."""

import math
import random
from PyQt5.QtCore import QTimer
from minibuddies.catalog import MAX_COUNT, SHAKE, START_COUNT, char_scale
from minibuddies.desktop import target_screen
from minibuddies.features.passthrough import PET_ALPHA
from minibuddies.pets import Buddy
from minibuddies.ui.widgets import Burst


class RosterController:
    def ground(self, bd):
        if bd.state in self.BUSY or bd.surface is None or bd.state in ("group", "gather", "tower", "train"):
            if self.group and bd in self.group.get("mem", []):
                self.group_break()
            scr = bd.scr()
            bd.drop_rope(); bd.setWindowOpacity(PET_ALPHA["a"]); bd.show()
            bd.stand_on((scr.left() - 9999, scr.bottom(), scr.right() + 9999))
            bd.fx = max(scr.left(), min(scr.right() - bd.S, bd.fx))
        bd.goal = None; bd.vx = 0; bd.after = None

    def announce_new_friends(self):
        """업데이트로 새 친구가 들어왔을 때 한 번 알려 주기"""
        names = ", ".join(self.chars[c]["label"] for c in self.new_friends if c in self.chars)
        self.save_cfg()
        if names and self.buddies:
            self.force_say(random.choice(self.buddies),
                           f"새 친구가 왔어요: {names}! 우클릭 → 멤버 부르기 또는 환경설정 → 캐릭터에서 불러 주세요♪", 14)

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

    def return_home(self, ch):
        self.pending.discard(ch)
        if self.team and ch not in (self.live_team() if self.one_each else self.team):
            return
        self.add(entrance=random.choice(["peek", "peek", "umbrella", "rope", "drop"]), char=ch)

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
