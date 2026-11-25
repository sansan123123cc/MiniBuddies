"""Pet animation callbacks."""

import os
import random
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPainter
from minibuddies.catalog import F, SHOOT_LINES, SUMMON, TICK, voice_filter
from minibuddies.ui.widgets import Bubble


class PetAnimation:
    def fbottom(self, f):
        return self.app.frame_bounds(self.char, f).get("bottom", 0.977)

    def ftop(self, f):
        return self.app.frame_bounds(self.char, f).get("top", 0.1)

    def flush(self):
        """틱마다 한 번: 위치·그림이 실제로 바뀐 경우에만 창을 옮기고 다시 그림 (렉 줄이기)"""
        pos = (int(self.fx), int(self.fy))
        if pos != getattr(self, "_lpos", None):
            self._lpos = pos
            self.move(*pos)
        f = F["fall"] if self.drag is not None else self.frame()
        key = (f, self.face, int(self.angle) if self.angle else 0, self.S, self.app.chars[self.char]["dir"])
        if key != getattr(self, "_lkey", None):
            self._lkey = key
            self.update()

    def say(self, text, ticks=150, force=False, sticky=False):
        if not force and ((self.bubble and self.bubble.sticky) or getattr(self, "say_lock", 0) > 0):
            return                                   # Claude 가 띄운 말풍선은 사용자가 닫을 때까지 그대로
        if not force and not self.app.cfg.get("bubbles", True):
            return
        if not sticky:
            text = voice_filter(f"{self.char}@{self.app.outfit.get(self.char)}", text)
        if self.bubble:
            self.bubble.close()
        self.bubble = Bubble(text, sticky, on_close=self.bubble_closed if sticky else None)
        self.bubble_t = ticks
        self.place_bubble()
        self.bubble.show()

    def bubble_closed(self):
        self.bubble = None; self.bubble_t = 0; self.say_lock = 0

    def place_bubble(self):
        if not self.bubble:
            return
        top = self.fy + self.S * self.ftop(self.frame()) - self.bubble.height() + 4
        self.bubble.move(int(self.cx - self.bubble.width() / 2), int(top))

    def tick_bubble(self):
        if getattr(self, "say_lock", 0) > 0:
            self.say_lock -= 1
        if self.bubble:
            if not self.bubble.sticky:
                self.bubble_t -= 1
            if self.bubble_t <= 0 and not self.bubble.sticky:
                self.bubble.close(); self.bubble = None
            else:
                self.place_bubble()

    def do_persona(self, idx=None):
        """캐릭터 고유 동작 (6번 시트)"""
        lst = self.app.chars[self.char].get("persona") or []
        if not lst:
            return False
        if idx is None:
            item = random.choices(lst, weights=[x[3] for x in lst])[0]
        else:
            item = lst[idx % len(lst)]
        frames, speed, dur, _, vx, lines = item
        self.pframes, self.pspeed = frames, speed
        self.pvx = vx
        self.vx = (self.face or 1) * vx
        self.set("persona", random.randint(*dur))
        self.say(random.choice(lines))
        # 시부키가 "다들 모여!" 하면 단체 놀이 시작
        if (self.char, frames[0]) in SUMMON and self.app.team:
            QTimer.singleShot(1500, lambda: self.app.group_event(leader=self))
        if self.char == "toa" and frames[0] in (52, 58):      # 퇴마 드립: 유령·저주인형은 도망!
            for o in self.app.buddies:
                if o.char in ("hiyori", "mary") and o.surface == self.surface and o.surface \
                        and abs(o.cx - self.cx) < self.S * 4 and o.state in ("idle", "walk", "read", "milk", "cheer") \
                        and o.goal is None:
                    o.say("히익! 퇴마당한다!" if o.char == "hiyori" else "냐악! 저리 가 냐!", 90)
                    o.go_to(self, "flee", ticks=110)
        if self.char in ("hiyori", "rang") and frames[0] in ((52,) if self.char == "hiyori" else (58,)):
            for o in self.app.buddies:                         # 뿌! / 어흥! 에 깜짝
                if o is not self and o.surface == self.surface and o.surface \
                        and abs(o.cx - self.cx) < self.S * 2.5 and o.state in ("idle", "walk", "read", "milk") \
                        and o.goal is None:
                    o.vx = 0; o.set("surprise", 50)
        if self.char == "riko" and frames == [56]:      # 점프킹: 웅크렸다가 크게 점프
            self.after = "bigjump"
        return True

    def has_frame(self, f):
        try:
            return os.path.exists(os.path.join(self.app.chars[self.char]["dir"], f"{f}.png"))
        except Exception:
            return False

    def play_seq(self, seq, after=None):
        """[(프레임, 틱), ...] 을 한 번 재생하고 after(함수 또는 다음 상태)"""
        self.vx = 0
        self.seqf = [(f, max(1, int(d))) for f, d in seq]
        self.seq_total = sum(d for _, d in self.seqf)
        self.set("seq", self.seq_total, after=after)

    def say_later(self, ticks, text):
        QTimer.singleShot(int(ticks * TICK), lambda: self.say(text, 110) if self in self.app.buddies else None)

    def do_shoot(self):
        """니케: 뒷모습으로 총 쏘기 (대기 → 조준 → 연사 → 장전 → 연사 → 버스트 → 뒤돌아 브이)"""
        if not self.has_frame(F["shoot_ready"]):
            return False
        a, b = F["shoot_fire"]
        fire = lambda n, sp=6: [(a, sp), (b, sp)] * n
        seq = [(F["shoot_ready"], 30), (F["shoot_aim"], 26)] + fire(random.randint(8, 14)) \
            + [(F["shoot_reload"], 45)] + fire(random.randint(6, 10))
        if random.random() < 0.35:
            seq += [(F["shoot_cover"], 50)] + fire(5)
        t_burst = sum(d for _, d in seq)
        seq += [(F["burst"], 70), (F["shoot_end"], 70)]
        key = f"{self.char}@{self.app.outfit.get(self.char)}"
        lines = SHOOT_LINES.get(key) or SHOOT_LINES.get(self.char) or ("사격 개시!", "장전!", "버스트!", "클리어!")
        self.say(lines[0], 90)
        reload_t = 56 + 2 * 6 * 8
        self.say_later(reload_t, lines[1])
        self.say_later(t_burst, lines[2])
        self.say_later(t_burst + 70, lines[3])
        self.play_seq(seq)
        return True

    # ── 그리기 ────────────────────────────
    def frame(self):
        st = self.state
        if st == "air":
            if self.air_kind == "thrown":
                return F["ball"]
            if self.air_kind == "knocked":
                return F["hit"] if self.knock_t > 0 else F["knocked"]
            return F["jump"] if self.air_kind == "hop" else F["fall"]
        if st == "walk":
            return F["walk"][(self.anim // 8) % 4]
        if st == "run":
            return F["run"][(self.anim // 5) % 2]
        if st == "roll":
            return F["ball"]
        if st == "idle":
            return F["walk"][0]
        if st == "umbrella":
            return F["umbrella"][(self.anim // 20) % 2]
        if st in ("rope", "rope_pause"):
            return F["rope"]
        if st == "wallclimb":
            return F["wallclimb"][(self.anim // 14) % 2] if self.t <= 0 else F["wallclimb"][0]
        if st == "dance":
            return F["dance"][(self.anim // 12) % 2]
        if st == "crawl":
            return F["crawl"][(self.anim // 14) % 2]
        if st == "persona":
            return self.pframes[(self.anim // self.pspeed) % len(self.pframes)]
        if st == "seq":                          # 정해진 순서대로 한 번 재생(사격·변신)
            k, acc = self.seq_total - max(self.t, 0), 0
            for f, d in self.seqf:
                acc += d
                if k < acc:
                    return f
            return self.seqf[-1][0]
        if st in ("group", "tower"):
            return self.gframe[(self.anim // 12) % len(self.gframe)]
        if st == "gather":
            return F["walk"][(self.anim // 8) % 4]
        if st == "train":
            return F["train"][(self.anim // 9) % 2] if abs(self.vx) > 0.3 else F["train"][0]
        if st == "wiggle":
            return F["wiggle"][(self.anim // 10) % 2]
        v = F.get(st, 0)
        return v[0] if isinstance(v, list) else v

    def paintEvent(self, e):
        f = self.frame()
        if self.drag is not None:
            f = F["fall"]
        p = QPainter(self)
        ball = f == F["ball"] or (f == F["knocked"] and self.state == "air")
        if ball and self.angle:                       # 굴러갈 때만 회전 (그 외에는 미리 줄여 둔 그림을 그대로)
            pm = self.app.pix(f, self.char)
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            cy = self.S * (self.ftop(f) + self.fbottom(f)) / 2
            p.translate(self.S / 2, cy)
            p.rotate(self.angle)
            p.scale(self.face, 1)
            p.drawPixmap(int(-self.S / 2), int(-cy), self.S, self.S, pm)
        else:
            p.drawPixmap(0, 0, self.app.spix(f, self.char, self.S, self.face, self.devicePixelRatioF()))
