"""Pet movement callbacks."""

import datetime
import math
import random
import time
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QApplication
from minibuddies.catalog import AVOID_STATES, F, FLEE_DEFAULT, FLEE_LINES, GRAVITY, SIT_HIP
from minibuddies.desktop import CURSOR, screen_for
from minibuddies.features.rest import _rest_on


def hour():
    return datetime.datetime.now().hour


class PetMovement:
    # ── 도우미 ─────────────────────────────
    def scr(self):
        return screen_for(self.char).availableGeometry()

    def surfaces(self):
        scr = self.scr()
        floor = (scr.left() - 9999, scr.bottom(), scr.right() + 9999)
        if not self.app.climb_windows or self.app.quiet():   # 한 자리에 있기: 창 위로 안 올라감
            return [floor]
        return [w for w in self.app.windows if w[1] > scr.top() + 40] + [floor]

    def find_floor(self, cx, feet):
        best = None
        for s in self.surfaces():
            if s[0] + 6 < cx < s[2] - 6 and s[1] >= feet - 14:
                if best is None or s[1] < best[1]:
                    best = s
        return best

    def surface_alive(self):
        if self.surface is None:
            return False
        l, t, r = self.surface
        for s in self.surfaces():
            if abs(s[1] - t) <= 3 and abs(s[0] - l) <= 3 and abs(s[2] - r) <= 3:
                return True
            if abs(s[1] - t) <= 3 and s[0] - 3 <= l and r <= s[2] + 3:
                return True
        return False

    def fall(self, vx=None):
        self.surface = None
        self.air_kind = "fall"
        self.fall_from = self.fy
        if vx is not None:
            self.vx = vx
        self.set("air")

    # ── 매 틱 ─────────────────────────────
    def step(self):
        self.tick_bubble()
        if self.plugin_action is not None and (self.state != "seq" or not self.isVisible()):
            self.stop_plugin_action()
        if self.drag is not None:
            return
        if self.state == "tower":               # 인간 탑: 앱이 위치를 정함
            self.anim += 1
            return
        self.cool = max(0, self.cool - 1)
        self.edge_cool = max(0, self.edge_cool - 1)
        self.anim += 1
        st = self.state
        scr = self.scr()

        if st == "air":
            self.vy += GRAVITY
            self.fx += self.vx
            self.fy += self.vy
            if self.air_kind == "thrown":
                self.angle += self.vx * 4
            elif self.air_kind == "knocked":
                if self.knock_t > 0:
                    self.knock_t -= 1                # 처음엔 '헉!' 맞는 모습
                else:
                    self.angle -= self.face * 9      # 그다음 뒤로 빙글빙글
            floor = self.find_floor(self.cx, self.feet() - self.vy)
            if floor and self.vy > 0 and self.feet() >= floor[1]:
                self.stand_on(floor)
                if self.air_kind in ("thrown", "knocked") and self.vy > 6:
                    self.vy *= -0.45; self.vx *= 0.75; self.surface = None
                else:
                    drop = self.fy - self.fall_from
                    self.vy = 0; self.angle = 0
                    if self.air_kind == "hop":
                        self.vx = 0
                        self.set("idle", 20)
                    else:
                        self.vx *= 0.3
                        nxt = None
                        if self.react_next:
                            nxt, self.react_next = self.react_next, None
                        elif drop > 450 and random.random() < 0.4:
                            nxt = "cry"
                        elif self.air_kind == "thrown":
                            nxt = random.choice(["cry", "pout", "pout", None])
                        self.set("land", 22, after=nxt)
                        self.app.landed_near(self)
        elif st == "umbrella":
            self.vy = 1.4
            self.vx = math.sin(self.anim / 25) * 1.2
            self.fx += self.vx
            self.fy += self.vy
            floor = self.find_floor(self.cx, self.feet() - 2)
            if floor and self.feet() >= floor[1]:
                self.stand_on(floor); self.vx = 0
                self.set("cheer" if random.random() < 0.4 else "idle", 60)
        elif st == "rope":
            self.update_rope()
            if self.t > 0 and random.random() < 0.004:
                self.t -= 1
                self.set("rope_pause", random.randint(60, 150), after=self.t)
            else:
                self.fy += 2.2
                floor = self.find_floor(self.cx, self.feet(F["rope"]) - 3)
                if floor and self.feet(F["rope"]) >= floor[1]:
                    self.drop_rope()
                    self.stand_on(floor)
                    self.set("wave" if random.random() < 0.5 else "idle", 70)
        elif st == "rope_pause":
            self.update_rope()
            self.t -= 1
            if self.t <= 0:
                left = self.after
                self.set("rope", left)
        elif st in ("wallclimb", "wallslide"):
            self.wall_step(scr)
        elif st == "balloon":          # 풍선 타고 퇴장
            self.vx = math.sin(self.anim / 30) * 0.8
            self.fx += self.vx
            self.fy -= 1.6
            if self.fy + self.S < scr.top():
                self.app.finished(self)
                return
        elif st == "dig":              # 땅속으로 쏙
            self.fy += 0.7
            self.t -= 1
            if self.t <= 0:
                self.app.finished(self)
                return
        elif st in ("hang", "sit_edge"):
            if not self.surface_alive():
                self.fall(vx=0)
            else:
                self.t -= 1
                if self.t <= 0:
                    self.finish_edge()
        elif st == "climb":
            if not self.surface_alive():
                self.fall(vx=0)
                self.move(int(self.fx), int(self.fy)); return
            self.t -= 1
            if self.t <= 0:
                l, t, r = self.surface
                inside = (r - self.S * 0.45) if self.edge > 0 else (l + self.S * 0.45)
                self.fx = inside - self.S / 2
                self.stand_on(self.surface)
                self.face = -self.edge
                self.edge_cool = 200
                self.set("idle", 30, after="walk_away")
        elif st == "peek":
            self.t -= 1
            if self.t <= 0:
                self.surface = None
                self.air_kind = "hop"; self.fall_from = self.fy
                self.vy = -13; self.vx = random.uniform(-1.5, 1.5)
                self.fy -= self.S * 0.3
                self.set("air")
        else:   # 땅 위 상태
            if not self.surface_alive():
                self.fall()
            else:
                self.ground_step(st, scr)

        # 화면 벽
        if self.state not in ("wallclimb", "wallslide"):
            hit = 0
            if self.fx + self.S * 0.2 < scr.left():
                self.fx = scr.left() - self.S * 0.2; self.vx = abs(self.vx); hit = -1
            if self.fx + self.S * 0.8 > scr.right():
                self.fx = scr.right() - self.S * 0.8; self.vx = -abs(self.vx); hit = 1
            if hit and self.state in ("walk", "run") and self.goal is None and random.random() < 0.35:
                self.start_wall(hit, scr)
        if self.state in ("walk", "run", "roll", "air", "umbrella", "crawl", "balloon", "persona") and abs(self.vx) > 0.2 \
                and not (self.state == "air" and self.air_kind in ("thrown", "knocked")):
            self.face = 1 if self.vx > 0 else -1

    def ground_step(self, st, scr):
        self.t -= 1
        l, t, r = self.surface
        if not (l < self.cx < r):          # 밀려서 모서리 밖으로!
            self.fall(vx=self.vx)
            return
        if self.app.quiet() and self.app.stay_gate(self):
            return
        if self.goal is not None and self.steer():
            return
        if st == "group":                       # 단체 동작 중: 앱이 조종
            return
        if st == "gather":                      # 단체 동작 자리로 이동
            dx = self.gx - self.cx
            if abs(dx) < 4:
                self.vx = 0; self.state = "group"; self.gframe = [F["walk"][0]]
                return
            self.vx = max(-2.6, min(2.6, dx * 0.08)) or (1 if dx > 0 else -1)
            if abs(self.vx) < 1.0:
                self.vx = 1.0 if dx > 0 else -1.0
            self.face = 1 if dx > 0 else -1
            self.fx += self.vx
            return
        if st == "train":                       # 기차놀이: 앞사람 따라가기
            lead, k = self.gx
            if lead not in self.app.buddies or lead.surface != self.surface:
                self.set("idle", 30); return
            tx = lead.cx - lead.face * self.S * 0.55 * k
            dx = tx - self.cx
            self.vx = max(-2.4, min(2.4, dx * 0.1))
            self.face = lead.face
            l2, t2, r2 = self.surface
            if l2 + 6 < self.cx + self.vx < r2 - 6:
                self.fx += self.vx
            if self.t <= 0:
                self.set("cheer", 60)
            return
        if st == "persona" and self.pvx:        # 움직이는 개성 동작(청소·잠입 등)
            nx = self.cx + self.vx
            if not (l + 6 < nx < r - 6):
                self.vx = -self.vx
            else:
                self.fx += self.vx
        if st == "push":
            other = self.app.ahead(self)
            if other is None:
                self.t = min(self.t, 0)
            else:
                other.fx += self.vx
                other.face = self.face
                if other.state != "pushed":
                    other.vx = 0
                    other.set("pushed", 30)
                other.t = 30
            nx = self.cx + self.vx
            if l + 6 < nx < r - 6:
                self.fx += self.vx
        if st in ("walk", "run", "roll", "crawl"):
            if st == "walk" and self.goal is None and random.random() < 0.02:
                other = self.app.ahead(self)
                if other and other.state in ("idle", "sleep", "nap", "read", "milk", "pout", "eat", "wiggle"):
                    self.vx = self.face * 0.6
                    self.set("push", random.randint(80, 200))
                    return
            nx = self.cx + self.vx
            l, t, r = self.surface
            if not (l + 6 < nx < r - 6):          # 모서리 도착!
                if self.goal is not None:          # 놀이 중엔 모서리에서 그냥 돌아서기
                    self.vx = -self.vx
                    return
                self.at_edge(1 if self.vx > 0 else -1)
                return
            self.fx += self.vx
            if st == "run" and self.goal is None and random.random() < 0.004:      # 꽈당!
                self.vx = 0
                self.set("trip", 70, after=random.choice(["cry", "pout", None, None]))
                return
            if st == "roll":
                self.angle += self.vx * 360 / (math.pi * self.S * 0.75)
        if st == "seq" and self.t > 0:
            frame = self.frame()
            if self.align_sequence:
                self.fy = self.surface[1] - self.S * self.fbottom(frame)
            if self.plugin_action is not None:
                self.plugin_action.advance(self.seq_total - self.t)
        if self.t <= 0:
            nxt, self.after = self.after, None
            if callable(nxt):
                try:
                    nxt()
                except Exception:
                    pass
                if self.state == "seq" and self.t <= 0:
                    self.choose()
                return
            if nxt == "cry":
                self.set("cry", random.randint(90, 160))
            elif nxt == "sleep":
                self.set("sleep", random.randint(400, 1200))
            elif nxt == "walk_away":
                self.vx = self.face * random.uniform(0.8, 1.3)
                self.set("walk", random.randint(80, 200))
            elif nxt == "hop":
                self.hop()
            elif nxt == "nap":
                self.set(random.choice(["sleep", "nap"]), random.randint(400, 1200))
            elif nxt == "pout":
                self.set("pout", random.randint(100, 200))
            elif nxt in ("bump", "dizzy", "faint", "rub"):
                self.vx = 0
                t = {"bump": 100, "dizzy": 160, "faint": 230, "rub": 130}[nxt]
                follow = {"faint": "dizzy", "dizzy": "grumble", "bump": "grumble", "rub": "grumble"}[nxt]
                self.set(nxt, t, after=follow)
            elif nxt == "grumble":            # 화내며 쫓아가거나, 울거나, 삐지거나
                g = self.grudge
                if g in self.app.buddies and g.surface == self.surface and random.random() < 0.55:
                    self.face = 1 if g.cx > self.cx else -1
                    self.vx = 0
                    self.set("angry", 110, after="chase")
                else:
                    self.grudge = None
                    self.set(random.choice(["cry", "pout", "pout"]), random.randint(90, 150))
            elif nxt == "chase":
                g, self.grudge = self.grudge, None
                if g in self.app.buddies and g.surface == self.surface:
                    self.face = 1 if g.cx > self.cx else -1
                    self.vx = self.face * 3.8
                    self.set("run", 80)
                else:
                    self.choose()
            elif nxt == "caught":
                self.set("cheer", 80)
            elif nxt == "bigjump":
                self.hop(17)
            else:
                self.choose()
        if self.goal is None and st not in ("group", "gather", "train", "seq"):   # 놀이 중엔 커서 반응으로 끊기지 않게
            self.near_cursor()
            self.check_pat()
        if st == "pushed" and self.t <= 0:
            self.set("pout", 60)

    def go_to(self, who, mode="approach", arrive=None, ticks=600, speed=None):
        """친구에게 다가가기(approach) / 쫓기(chase) / 도망치기(flee)"""
        if self.app.quiet():     # 한 자리에 있기: 다가가기·쫓기·도망 안 함
            return
        sp = speed or {"approach": 1.4, "chase": 3.6, "flee": 3.3}[mode]
        self.goal = {"who": who, "mode": mode, "arrive": arrive, "until": ticks, "speed": sp}
        d = 1 if who.cx > self.cx else -1
        if mode == "flee":
            d = -d
        self.vx = d * sp
        self.set("run" if sp > 2.5 else "walk", ticks)

    def steer(self):
        g = self.goal
        o = g["who"]
        g["until"] -= 1
        cur = o is CURSOR
        if (not cur and (o not in self.app.buddies or o.surface != self.surface)) or g["until"] <= 0 \
                or self.state not in ("walk", "run"):
            self.goal = None
            return False
        dx = o.cx - self.cx
        d = 1 if dx > 0 else -1
        if g["mode"] == "flee":
            self.vx = -d * g["speed"]
        else:
            self.vx = d * g["speed"]
            if abs(dx) < (self.S + o.S) * (0.22 if g["mode"] == "chase" else 0.35):
                self.goal = None
                self.vx = 0
                self.face = d
                if g["arrive"]:
                    g["arrive"](self, o)
                else:
                    self.set("idle", 40)
                return True
        return False

    # ── 밧줄 ─────────────────────────────
    def update_rope(self):
        if self.rope:
            info = self.app.chars[self.char]["rope"]
            rx = info.get("x", 0.5)                       # 그림 속 밧줄 위치 (좌우 반전 반영)
            x = self.fx + self.S / 2 + self.face * (self.S * rx - self.S / 2)
            top_y = self.fy + self.S * self.ftop(F["rope"]) + 3
            self.rope.place(x, self.scr().top() - 5, top_y, self.S * info.get("w", 0.03))

    def drop_rope(self):
        if self.rope:
            self.rope.close(); self.rope = None

    # ── 화면 벽 타기 ──────────────────────
    def start_wall(self, side, scr):
        self.edge = side
        self.face = side
        m = self.app.chars[self.char]["meta"].get(F["wallclimb"][0], {})
        right = m.get("right", 0.95)
        if side > 0:
            self.fx = scr.right() - self.S * right
        else:
            self.fx = scr.left() - self.S * (1 - right)
        self.surface = None
        self.vx = 0
        self.target_y = self.fy - random.randint(80, 600)
        self.set("wallclimb", 0)

    def wall_step(self, scr):
        if self.state == "wallclimb":
            if self.t > 0:            # 잠깐 쉬는 중
                self.t -= 1
                return
            self.fy -= 1.3
            if random.random() < 0.006:
                self.t = random.randint(40, 100)
            if self.fy <= max(self.target_y, scr.top() + 10):
                r = random.random()
                if r < 0.55:
                    self.set("wallslide")
                elif r < 0.8:
                    self.fall(vx=-self.edge * 2)
                else:
                    self.t = random.randint(80, 200)
                    self.target_y = self.fy - random.randint(50, 200)
        else:   # 미끄러져 내려오기
            self.fy += 3.0
            floor = self.find_floor(self.cx, self.feet() - 4)
            if floor and self.feet() >= floor[1]:
                self.stand_on(floor)
                self.fx -= self.edge * self.S * 0.3
                self.face = -self.edge
                self.set("idle", 40, after="walk_away")

    # ── 모서리 행동: 매달리기 / 걸터앉기 / 돌아서기 / 떨어지기 ──
    def at_edge(self, d):
        l, t, r = self.surface
        is_floor = r - l > 5000
        if is_floor or self.edge_cool > 0:
            self.vx = -self.vx
            return
        r_ = random.random()
        if self.state == "roll" or r_ < 0.2:
            self.fx += self.vx * 3
            self.fall()
        elif r_ < 0.55:
            self.edge = d
            ex = r if d > 0 else l
            self.fx = ex + d * self.S * 0.12 - self.S / 2
            self.fy = t - self.S * self.ftop(F["hang"]) - 4
            self.face = -d
            self.vx = 0
            self.set("hang", random.randint(120, 320))
        elif r_ < 0.8:
            self.edge = d
            ex = r if d > 0 else l
            self.fx = ex - self.S / 2
            top, bot = self.ftop(F["sit_edge"]), self.fbottom(F["sit_edge"])
            self.fy = t - self.S * (top + (bot - top) * SIT_HIP)
            self.face = d
            self.vx = 0
            self.set("sit_edge", random.randint(250, 700))
        else:
            self.vx = -self.vx
            self.edge_cool = 60

    def finish_edge(self):
        if self.state == "hang":
            if random.random() < 0.6:
                top, bot = self.ftop(F["climb"]), self.fbottom(F["climb"])
                self.fy = self.surface[1] - self.S * (top + (bot - top) * 0.45)
                self.set("climb", 40)
            else:
                self.fall(vx=self.edge * 0.5)
        else:   # 걸터앉기 끝 → 돌아서 들어가기
            l, t, r = self.surface
            self.fx = (r - self.S * 0.45 if self.edge > 0 else l + self.S * 0.45) - self.S / 2
            self.stand_on(self.surface)
            self.face = -self.edge
            self.edge_cool = 200
            self.vx = self.face * 1.0
            self.set("walk", random.randint(80, 200))

    # ── 다음 행동 고르기 ─────────────────────
    def choose(self):
        if self.app.cfg.get("sleep_mode", False) and self.surface:   # 수면 모드: 구석에서 깨울 때까지 쿨쿨
            hx = self.app.stay_home(self)
            if hx is not None:
                self.fx = float(hx - self.S / 2)
                self.move(int(self.fx), int(self.fy))
            self.vx = 0
            self.set("sleep", 600)
            return
        if self.app.quiet() and self.surface:
            hx = self.app.stay_home(self)
            if hx is not None and abs(self.cx - hx) > max(20, self.S * 0.2):
                self.fx = float(hx - self.S / 2); self.vx = 0       # 걷지 않고 자리로 쏙
                self.move(int(self.fx), int(self.fy))
                self.set("idle", random.randint(60, 160))
                return
        if self.state == "idle" and self.app.plugins.play_idle(self):
            return
        h = hour()
        night = h >= 23 or h < 6
        lunch = 12 <= h < 13
        w = {
            "walk": 30, "run": 8, "roll": 10, "idle": 10, "hop": 6,
            "cheer": 5, "wave": 4, "eat": 12 if lunch else 4,
            "yawn": 10 if night else 3, "sleep": 14 if night else 4,
            "dance": 5, "pout": 2,
            "crawl": 6, "wiggle": 4, "read": 4, "sing": 3, "kiss": 2,
            "milk": 8 if 7 <= h < 10 else 3, "exit": 1.2,
            "persona": 22 if self.app.chars[self.char].get("persona") else 0,
            "shoot": 7 if self.has_frame(F["shoot_ready"]) else 0,
        }
        if self.app.quiet():
            for _k in ("walk", "run", "roll", "hop", "crawl", "exit"):
                w[_k] = 0
            w["idle"] = 30
        pick = random.choices(list(w), weights=list(w.values()))[0]
        d = random.choice([-1, 1])
        if pick == "walk":
            self.vx = d * random.uniform(0.8, 1.4); self.set("walk", random.randint(120, 400))
        elif pick == "run":
            self.vx = d * random.uniform(3.0, 4.0); self.set("run", random.randint(50, 120))
        elif pick == "roll":
            self.vx = d * random.uniform(2.5, 4.5); self.set("roll", random.randint(60, 180))
        elif pick == "hop":
            self.hop()
        elif pick == "yawn":
            self.vx = 0; self.set("yawn", 90, after="nap")
        elif pick == "persona":
            self.do_persona()
        elif pick == "shoot":
            self.do_shoot()
        elif pick == "crawl":
            self.vx = d * 0.55; self.set("crawl", random.randint(150, 400))
        elif pick == "exit":
            self.app.leave(self, travel=True)
        else:
            self.vx = 0
            t = {"idle": (60, 180), "cheer": (60, 110), "wave": (70, 130),
                 "eat": (200, 400), "sleep": (400, 1200), "dance": (150, 400),
                 "pout": (100, 200), "wiggle": (100, 250), "read": (300, 700),
                 "sing": (200, 400), "kiss": (60, 100), "milk": (150, 300)}[pick]
            self.set(pick, random.randint(*t))

    def hop(self, power=10):
        self.air_kind = "hop"
        self.fall_from = self.fy
        self.vy = -power
        self.vx = self.face * random.uniform(0, 1.5)
        self.surface = None
        self.set("air")

    def near_cursor(self):
        if _rest_on(self.app):
            return  # 제자리 모드: 커서 따라 뛰어가거나 비켜 달아나지 않고 하던 놀이 계속
        if self.app.cfg.get("cursor_avoid", True):
            # 커서 피해 다니기: 움직이는 커서가 가까이 오면 반대쪽으로 비켜 줌 (가만히 둔 커서 위에선 쓰담쓰담 그대로)
            if self.drag is not None or not self.surface or self.state not in AVOID_STATES:
                return
            if QApplication.keyboardModifiers() & (Qt.ControlModifier | Qt.ShiftModifier):
                return  # Ctrl/Shift 누른 채면 안 도망감 → 머리에 올려서 쓰담쓰담 가능
            c = QCursor.pos(); now = time.time()
            if getattr(self.app, "_av_pos", None) != c:
                self.app._av_pos = c; self.app._av_t = now
            if now - getattr(self.app, "_av_t", 0) > 1.0:
                return
            dx = c.x() - self.cx
            r = max(120, self.S * 0.9)
            if abs(dx) < r and abs(c.y() - (self.fy + self.S / 2)) < r:
                d = -1 if dx > 0 else 1
                self.face = d; self.vx = d * 3.6
                self.set("run", 30)
                _now = time.time()
                if _now - getattr(self, "_flee_t", 0) > 5 and random.random() < 0.45:
                    self._flee_t = _now
                    _base = self.char.split("@")[0]
                    self.say(random.choice(FLEE_LINES.get(_base) or FLEE_DEFAULT), 80)
            return
        if self.cool or self.state in ("sleep", "nap", "cry", "eat", "push", "pushed", "dig", "balloon",
                                       "bump", "dizzy", "faint", "rub", "angry", "catch"):
            return
        c = QCursor.pos()
        dx = c.x() - self.cx
        if abs(dx) < 170 and abs(c.y() - (self.fy + self.S / 2)) < 170:
            self.cool = 500
            self.face = 1 if dx > 0 else -1
            r = random.random()
            if r < 0.45:
                self.vx = 0; self.set("wave", 90)
            elif r < 0.7:
                self.vx = self.face * 3.5; self.set("run", 40)     # 쪼르르 다가오기
            elif r < 0.8:
                self.vx = 0; self.set("cheer", 70)
            elif r < 0.92:
                self.vx = 0; self.set("kiss", 70)

    def greet(self, other_dir):
        if self.cool or self.state not in ("walk", "idle"):
            return
        self.cool = 600
        self.face = other_dir
        self.vx = 0
        self.set(random.choice(["wave", "cheer", "kiss"]), 90)
