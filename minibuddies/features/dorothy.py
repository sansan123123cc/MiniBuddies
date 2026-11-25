"""Dorothy transformation and visual effects."""

import math
import random
import time
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPainter
from minibuddies.catalog import TICK


# ── 도로시 모드 변신 (피나 전개 / 일반 모드): 빛이 모여 변신 → 특수 동작 몇 개 → 빛이 흩어지며 원래대로 ──
# 그림: 116 변신 순간(빛) / 117~122 모드 동작 / 123 원래대로 돌아가는 중 (meta_weather.json 에 위치 정보)
DMODE = {
    "dorothy@basic": {
        "menu": "피나 전개!",
        "start": ["피나, 전개.", "날개를 펼칠 시간이군요."],
        "acts": [([117], 170, ["후후, 이 날개가 마음에 드시나요?", "에덴의 날개랍니다."]),
                 ([118], 170, ["귀하는 그저 올려다보기만 하면 돼요.", "…아름답죠?"]),
                 ([119], 150, ["귀하를 낙원으로 안내하겠습니다.", "이쪽이에요, 귀하."]),
                 ([120, 121], 0, ["엄폐.", "…조준 완료. 의미 없는 저항은 지루할 뿐인데."]),
                 ([122], 120, ["깃털 하나 정도는 선물로 드리죠.", "후후."])],
        "end": ["…이 정도면 충분하겠죠.", "날개는 다시 접어 두죠."],
    },
    "dorothy@liberated": {
        "menu": "일반 모드로 쉬기",
        "start": ["잠시… 날개를 내려놓을게요.", "오늘은 그냥 저로 있을게요."],
        "acts": [([117], 170, ["이 옷, 어색하지 않나요?", "…몸이 가벼워요."]),
                 ([118], 140, ["안녕하세요, 귀하. 정식으로 인사드릴게요.", "후후, 오늘은 숙녀처럼."]),
                 ([119], 120, ["빙글~ 드레스가 예쁘죠?", "후후, 어지러워요."]),
                 ([120], 160, ["이런 평범한 하루가 좋아요.", "행복이라는 건 이런 거군요."]),
                 ([121], 180, ["꽃 향기가 좋아요.", "귀하도 맡아 보실래요?"]),
                 ([122], 130, ["다녀왔어요, 귀하.", "손 흔들어 주실래요?"])],
        "end": ["다시, 지키러 갈 시간이네요.", "…빛이여, 돌아와요."],
    },
}


def _dm_key(app, b):
    return f"{b.char}@{app.outfit.get(b.char)}"


def _dm_fx(b, t_in, t_out, t_end):
    """빛 효과: 0~t_in 빛 입자가 모여듦 → 번쩍 → t_out~t_end 빛 입자가 흩어짐 (초 단위)"""
    old = getattr(b, "_dm_timer", None)
    if old is not None:
        try:
            old.stop()
        except Exception:
            pass
    b._dm = {"t0": time.time(), "in": t_in, "out": t_out, "end": t_end}
    tm = QTimer(b)
    tm.setInterval(33)

    def tick():
        d = getattr(b, "_dm", None)
        if d is None or time.time() - d["t0"] > d["end"] + 0.6 or b.state != "seq" or b.drag is not None:
            b._dm = None
            tm.stop()
        try:
            b.update()
        except Exception:
            tm.stop()
    tm.timeout.connect(tick)
    tm.start()
    b._dm_timer = tm


def _dm_paint(b):
    from PyQt5.QtGui import QColor, QRadialGradient, QBrush
    from PyQt5.QtCore import QPointF
    d = b._dm
    now = time.time() - d["t0"]
    S = float(b.S)
    try:
        f = b.frame()
        cy = S * (b.ftop(f) + b.fbottom(f)) / 2
    except Exception:
        cy = S * 0.62
    c = QPointF(S / 2, cy)
    p = QPainter(b)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)

    def glow(a, r):
        g = QRadialGradient(c, r)
        g.setColorAt(0.0, QColor(255, 255, 245, int(max(0, min(255, a)))))
        g.setColorAt(0.45, QColor(255, 240, 210, int(max(0, min(255, a * 0.55)))))
        g.setColorAt(1.0, QColor(255, 230, 200, 0))
        p.setBrush(QBrush(g))
        p.drawEllipse(c, r, r)

    def dots(rad, a, spin, n=18):
        for i in range(n):
            ang = i * 2 * math.pi / n + spin + (i % 3) * 0.4
            rr = rad * (0.75 + 0.25 * ((i * 7) % 5) / 4)
            x, y = c.x() + math.cos(ang) * rr, c.y() + math.sin(ang) * rr * 0.9
            s = S * (0.012 + 0.01 * ((i * 3) % 4) / 3)
            p.setBrush(QColor(255, 248, 215, int(max(0, min(255, a)))))
            p.drawEllipse(QPointF(x, y), s, s)
            p.setBrush(QColor(255, 255, 255, int(max(0, min(255, a * 0.5)))))
            p.drawEllipse(QPointF(x, y), s * 2.1, s * 2.1)

    if now < d["in"]:  # 빛이 모여듦
        k = now / d["in"]
        glow(60 + 150 * k, S * (0.3 + 0.2 * k))
        dots(S * (0.5 * (1 - k) + 0.06), 230, now * 4.0)
    elif now < d["in"] + 0.45:  # 번쩍
        k = (now - d["in"]) / 0.45
        glow(240 * (1 - k), S * 0.5)
    elif d["out"] <= now < d["end"]:  # 다시 빛으로 → 흩어짐
        k = (now - d["out"]) / max(0.01, d["end"] - d["out"])
        if k < 0.35:
            glow(220 * (1 - k / 0.35), S * 0.5)
        dots(S * (0.08 + 0.42 * k), 230 * (1 - k), -now * 3.0)
    p.end()


def dmode_play(self, b, force=False):
    """도로시 모드 변신 특수 동작 (피나 전개 / 일반 모드)"""
    d = DMODE.get(_dm_key(self, b))
    if not d or b not in self.buddies or b.drag is not None or not b.has_frame(116):
        return False
    if not b.surface:
        if not force:
            return False
        self.ground(b)
    b.goal = None
    b.vx = 0
    acts = d["acts"][:]
    rest = acts[1:]
    random.shuffle(rest)
    chosen = [acts[0]] + rest[:2]
    t_in = 95
    seq = [(116, t_in)]
    t = t_in
    for fr, dur, lines in chosen:
        part = [(fr[0], 50), (fr[1], 110), (fr[0], 40)] if len(fr) > 1 else [(fr[0], dur)]
        QTimer.singleShot(int((t + 12) * TICK), lambda L=lines: b in self.buddies and b.state == "seq"
                          and b.say(random.choice(L), 140))
        seq += part
        t += sum(x for _, x in part)
    t_out = t
    seq.append((123, 85))
    total = t + 85
    b.say(random.choice(d["start"]), 90)
    QTimer.singleShot(int((t_out + 10) * TICK), lambda: b in self.buddies and b.say(random.choice(d["end"]), 120))
    b.play_seq(seq)
    _dm_fx(b, t_in * TICK / 1000.0, t_out * TICK / 1000.0, total * TICK / 1000.0)
    b._dm_last = time.time()
    return True






# ── 노스텔지어 스킨: 소름 끼치게 깜빡이다 검은 모습으로 물들었다가 아무 일 없었다는 듯 돌아옴 ──
# 그림: 116 멈칫(텅 빈 눈) / 117 반쯤 검게 물든 글리치 / 118 검은 모습 / 119~121 검은 모습 동작 / 122 돌아오는 중 / 123 다시 분홍(생긋)
DMODE["dorothy@nosskin"] = {
    "menu": "…검게 물들기",
    "fx": "dark",
    "start": ["……", "…귀하, 뒤를 돌아보지 마세요."],
    "acts": [([118], 150, ["후후… 이쪽이 진짜 저일지도 모르죠.", "…낙원은, 이미 무너졌어요."]),
             ([119], 130, ["어디로 도망치시려고요?", "…날개가 검게 물들었네요."]),
             ([120], 130, ["쉿. 아무에게도 말하지 마세요.", "…비밀이에요, 귀하."]),
             ([121], 130, ["……왜 그렇게 보세요?", "후후후…"])],
    "end": ["…방금 뭐 보셨어요? 후후.", "어머, 차가 다 식었네요."],
}


def _dm_dark_play(self, b, force=False):
    d = DMODE.get(_dm_key(self, b))
    if not b.surface:
        if not force:
            return False
        self.ground(b)
    b.goal = None
    b.vx = 0
    seq = [(116, 70)]
    fl = [(117, 5), (116, 4), (118, 3), (116, 6), (117, 4), (118, 5), (116, 3), (117, 7), (118, 4), (117, 5)]
    w1 = (70, 70 + sum(x for _, x in fl))
    seq += fl
    t = w1[1]
    acts = d["acts"][:]
    rest = acts[1:]
    random.shuffle(rest)
    for fr, dur, lines in [acts[0]] + rest[:random.randint(1, 2)]:
        QTimer.singleShot(int((t + 12) * TICK), lambda L=lines: b in self.buddies and b.state == "seq"
                          and b.say(random.choice(L), 130))
        seq.append((fr[0], dur))
        t += dur
    back = [(122, 6), (118, 4), (122, 5), (117, 3), (118, 3), (122, 9)]
    w2 = (t, t + sum(x for _, x in back))
    seq += back
    t = w2[1]
    seq.append((123, 110))
    QTimer.singleShot(int((t + 10) * TICK), lambda: b in self.buddies and b.say(random.choice(d["end"]), 130))
    total = t + 110
    b.say(random.choice(d["start"]), 60)
    b.play_seq(seq)
    _dm_fx(b, 0.01, total * TICK / 1000.0, total * TICK / 1000.0)
    b._dm["kind"] = "dark"
    b._dm["win"] = [(w1[0] * TICK / 1000.0, w1[1] * TICK / 1000.0), (w2[0] * TICK / 1000.0, w2[1] * TICK / 1000.0)]
    b._dm["black"] = (w1[1] * TICK / 1000.0, w2[0] * TICK / 1000.0)
    b._dm_last = time.time()
    return True


def _dm_paint_dark(b):
    from PyQt5.QtGui import QColor, QRadialGradient, QBrush
    from PyQt5.QtCore import QPointF, QRectF
    d = b._dm
    now = time.time() - d["t0"]
    S = float(b.S)
    try:
        f = b.frame()
        top, bot = b.ftop(f), b.fbottom(f)
    except Exception:
        top, bot = 0.3, 0.97
    c = QPointF(S / 2, S * (top + bot) / 2)
    p = QPainter(b)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)

    def aura(col, a, r):
        g = QRadialGradient(c, r)
        g.setColorAt(0.0, QColor(col[0], col[1], col[2], int(max(0, min(255, a)))))
        g.setColorAt(0.6, QColor(col[0], col[1], col[2], int(max(0, min(255, a * 0.5)))))
        g.setColorAt(1.0, QColor(col[0], col[1], col[2], 0))
        p.setBrush(QBrush(g))
        p.drawEllipse(c, r, r)

    flick = any(a <= now < z for a, z in d.get("win", []))
    if flick:
        if random.random() < 0.6:  # 번쩍: 검정 / 핏빛
            aura(random.choice(((0, 0, 0), (120, 0, 10), (20, 0, 0))), random.randint(120, 230), S * 0.55)
        for _ in range(random.randint(2, 5)):  # 지직거리는 가로줄
            y = S * random.uniform(top, bot)
            h = S * random.uniform(0.012, 0.045)
            x0 = S * random.uniform(0.08, 0.35)
            w = S * random.uniform(0.3, 0.7)
            p.setBrush(QColor(*random.choice(((10, 0, 0), (150, 0, 20), (255, 255, 255))), random.randint(110, 200)))
            p.drawRect(QRectF(x0, y, w, h))
    else:
        a0, z0 = d.get("black", (0, 0))
        if a0 <= now < z0:  # 검은 모습일 땐 핏빛 기운이 천천히 일렁임
            aura((90, 0, 15), 45 + 30 * math.sin(now * 3.0), S * 0.5)
            if random.random() < 0.025:
                aura((0, 0, 0), 170, S * 0.55)
    p.end()

def install(App, Buddy):
    """Attach the dorothy behavior to the application."""
    global _dm_paint
    try:
        _dm_orig_paint = Buddy.paintEvent

        def _dm_paint_event(self, e):
            _dm_orig_paint(self, e)
            if getattr(self, "_dm", None):
                try:
                    _dm_paint(self)
                except Exception:
                    pass
        Buddy.paintEvent = _dm_paint_event
        App.dmode_play = dmode_play
        _dm_orig_minute = App.minute_tick

        def _dm_minute(self):
            _dm_orig_minute(self)
            try:  # 가끔 저절로 (한 번 하면 최소 15분 쉼)
                if self.quiet() or self.group or self.scene or random.random() > 0.12:
                    return
                now = time.time()
                cand = [b for b in self.buddies if _dm_key(self, b) in DMODE and b.surface and b.drag is None
                        and b.state not in self.BUSY and now - getattr(b, "_dm_last", 0) > 900 and b.has_frame(116)]
                if cand:
                    self.dmode_play(random.choice(cand))
            except Exception:
                pass
        App.minute_tick = _dm_minute
    except Exception as _e:
        print("dorothy mode hook failed:", _e)
    try:
        _dm_light_play = App.dmode_play
        _dm_paint_light = _dm_paint

        def _dm_play_any(self, b, force=False):
            d = DMODE.get(_dm_key(self, b))
            if d and d.get("fx") == "dark":
                if b not in self.buddies or b.drag is not None or not b.has_frame(116):
                    return False
                return _dm_dark_play(self, b, force)
            return _dm_light_play(self, b, force)

        def _dm_paint(b):  # 이름을 바꿔 끼워서 기존 paint 훅이 그대로 부름
            if (b._dm or {}).get("kind") == "dark":
                return _dm_paint_dark(b)
            return _dm_paint_light(b)
        App.dmode_play = _dm_play_any
    except Exception as _e:
        print("nosskin dark hook failed:", _e)
