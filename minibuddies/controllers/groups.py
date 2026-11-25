"""Multi-pet interactions and group scenes."""

import math
import os
import random
import time
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPixmap
from minibuddies.catalog import (
    F,
    GROUP_TEXT,
    HIDE_LINES,
    KANI_JOIN,
    KANI_NEAR,
    LAUGHER,
    SHAKE,
    SQUADS,
    TICK,
)
from minibuddies.desktop import screen_for, target_screen
from minibuddies.features import touhou
from minibuddies.features.costumes import _ev_bdir
from minibuddies.features.passthrough import PET_ALPHA
from minibuddies.ui.widgets import Burst, Flash, Scene


class GroupController:
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
            self.plugins.interactions.try_automatic(self)
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
        if self.plugins.interactions.try_automatic(self) or touhou.try_automatic(self):
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
        hooks = g.get("hooks")
        if hooks:
            hooks.close(g)
        for b in g["mem"]:
            if b in self.buddies and b.state in ("group", "gather", "tower", "train"):
                if b.state == "tower":
                    b.fall(vx=random.uniform(-2, 2))
                else:
                    if hooks:
                        hooks.restore(g, b)
                    b.set("idle", 30)

    def group_step(self):
        g = self.group
        g["t"] += 1
        mem = [b for b in g["mem"] if b in self.buddies]
        hooks = g.get("hooks")
        if hooks and hooks.should_break(self, g, mem):
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
        hooks = g.get("hooks")
        if hooks:
            hooks.start(self, g, mem)
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
        hooks = g.get("hooks")
        if hooks:
            hooks.advance(self, g, mem, t)
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

    touhou_members = touhou.touhou_members

    touhou_play = touhou.touhou_play

    touhou_duel_tick = touhou.touhou_duel_tick
