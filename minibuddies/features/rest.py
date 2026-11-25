"""Stationary pet activities."""

import math
import os
import random
import time
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPainter
from minibuddies.catalog import F, FALLBACK, TICK


# ── 제자리 모드: 돌아다니지 않고 지금 그 자리에서 책 읽기·게임·뒹굴뒹굴 (수면 모드와 별개) ──────────
REST_LINES = {"read": ["이 책 재밌다~", "다음 장, 다음 장…", "책 읽는 중이야~ 쉿!"],
              "game": ["한 판만 더!", "보스까지 왔다…!", "앗 졌어! 다시!", "이겼다~!"],
              "roll": ["뒹굴뒹굴~", "아무것도 안 하고 싶다~", "바닥 시원해~"],
              "nap": ["쿨…", "잠깐만 눈 붙일게…"],
              "snack": ["간식 타임~", "냠냠"],
              "sing": ["흥얼흥얼~♪", "라라라~"]}
_REST_COLORS = [(255, 170, 200), (150, 205, 255), (255, 214, 120), (180, 230, 170)]


def _rest_on(app):
    return bool(app.cfg.get("rest_mode", False)) and not app.cfg.get("sleep_mode", False)


def _rest_set_game(b, on):
    b._rest_game = bool(on)
    try:
        b.update()
    except Exception:
        pass


REST_GAME_END = {112: ["이겼다~!", "클리어~!", "신기록이야!"], 113: ["앗 졌어! 다시!", "으앙 한 판만 더…", "이건 게임이 이상한 거야!"],
                 115: ["쿨… 게임하다 잠들었어…", "졸려…"]}


def _rest_has_game(app, b):
    try:
        c = app.chars.get(b.char) or {}
        if "_game" not in c:
            c["_game"] = os.path.exists(os.path.join(c.get("dir", ""), "108.png"))
        return c["_game"]
    except Exception:
        return False


def _rest_game_seq():
    """앉아서·엎드려서·서서 게임하다가 이기거나 지거나 졸기"""
    a, c = random.choice(((108, 109), (108, 109), (110, 111), (114, 114)))
    seq = []
    for _ in range(random.randint(8, 16)):
        seq += [(a, random.randint(20, 40)), (c, random.randint(10, 24))]
    end = random.choices([112, 113, 115], weights=[45, 35, 20])[0]
    seq.append((end, 160 if end == 115 else 90))
    return seq, end


def _rest_play(app, b):
    """제자리 모드에서 다음 할 일 하나 (걷지 않음)"""
    b.vx = 0; b.goal = None
    w = {"read": 26, "game": 26, "roll": 20, "nap": 8, "snack": 8, "sing": 6, "persona": 6}
    per = app.chars.get(b.char, {}).get("persona")
    if not per:
        w["persona"] = 0
    k = random.choices(list(w), weights=list(w.values()))[0]
    if k == "persona":
        try:
            it = random.choice(per)
            fr = it[0]
            b.play_seq([(fr[i % len(fr)], max(6, it[1])) for i in range(len(fr) * 3)])
            return
        except Exception:
            k = "read"
    if random.random() < 0.25:
        b.say(random.choice(REST_LINES.get(k, ["~"])), 150)
    if k == "read":
        b.play_seq([(F["read"], random.randint(300, 700))])
    elif k == "game" and _rest_has_game(app, b):            # 게임기 그림(108~115)이 있는 의상
        seq, end = _rest_game_seq()
        b.play_seq(seq, after=lambda: b.say(random.choice(REST_GAME_END[end]), 120) if random.random() < 0.6 else None)
    elif k == "game":
        _rest_set_game(b, True)
        t = random.randint(300, 650)
        b.play_seq([(F["hands"], t)], after=lambda: _rest_set_game(b, False))
        QTimer.singleShot(int((t + 10) * TICK), lambda: _rest_set_game(b, False))
    elif k == "roll":
        a, c = F["wiggle"]
        b.play_seq([(a, 14), (c, 14)] * random.randint(6, 14))
    elif k == "nap":
        b.play_seq([(F["nap"], random.randint(300, 600)), (F["yawn"], 50)])
    elif k == "snack":
        b.play_seq([(random.choice((F["eat"], F["milk"])), random.randint(160, 280))])
    else:
        b.play_seq([(F["sing"], random.randint(150, 260))])


def _rest_paint(b):
    """게임할 때 손에 든 휴대용 게임기 (모든 캐릭터·의상 공통으로 코드로 그림)"""
    from PyQt5.QtGui import QColor, QPen
    from PyQt5.QtCore import QRectF, QPointF
    S = float(b.S)
    f = b.frame()
    if f != F["hands"]:
        return
    top, bot = b.ftop(f), b.fbottom(f)
    fc = 1 if (b.face or 1) > 0 else -1
    w, h = S * 0.24, S * 0.12
    cx = S / 2 + fc * S * 0.25
    cy = S * (top + (bot - top) * 0.56)
    x0, y0 = cx - w / 2, cy - h / 2
    col = _REST_COLORS[hash(b.char) % len(_REST_COLORS)]
    p = QPainter(b)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(70, 60, 80), max(1.0, S * 0.008)))
    p.setBrush(QColor(*col))
    p.drawRoundedRect(QRectF(x0, y0, w, h), h * 0.35, h * 0.35)
    t = time.time()
    g = int(150 + 80 * (0.5 + 0.5 * math.sin(t * 6)))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(90, g, 200))
    p.drawRoundedRect(QRectF(cx - w * 0.21, y0 + h * 0.18, w * 0.42, h * 0.64), h * 0.08, h * 0.08)
    p.setBrush(QColor(255, 255, 255, 200))                      # 화면 속 깜빡이는 점
    p.drawEllipse(QPointF(cx - w * 0.1 + w * 0.2 * (0.5 + 0.5 * math.sin(t * 3)), cy), h * 0.07, h * 0.07)
    p.setBrush(QColor(60, 50, 70))                              # 십자키
    dx = x0 + w * 0.15
    p.drawRect(QRectF(dx - h * 0.18, cy - h * 0.06, h * 0.36, h * 0.12))
    p.drawRect(QRectF(dx - h * 0.06, cy - h * 0.18, h * 0.12, h * 0.36))
    p.setBrush(QColor(235, 80, 110))                            # 버튼 두 개
    bx = x0 + w * 0.85
    p.drawEllipse(QPointF(bx, cy - h * 0.12), h * 0.09, h * 0.09)
    p.drawEllipse(QPointF(bx - h * 0.22, cy + h * 0.1), h * 0.09, h * 0.09)
    p.end()


def set_rest(self, on):
    """제자리 모드 켜고 끄기: 켜면 수면 모드는 꺼지고, 각자 지금 자리에서 놂"""
    self.cfg["rest_mode"] = bool(on)
    if on:
        self.cfg["sleep_mode"] = False
    self.save_cfg()
    for b in list(self.buddies):
        b._home = b.cx
        b.goal = None
        _rest_set_game(b, False)
        if on and b.surface and b.drag is None:
            b.choose()

def install(App, Buddy):
    """Attach the rest behavior to the application."""
    FALLBACK.update({108: 64, 109: 64, 110: 64, 111: 64, 112: 11, 113: 16, 114: 64, 115: 41})
    try:
        _rest_orig_choose = Buddy.choose

        def _rest_choose(self):
            try:
                if _rest_on(self.app) and self.surface:
                    if self.app.cfg.get("stay", False):            # 한 자리에 있기도 켜져 있으면 먼저 그 자리로
                        hx = self.app.stay_home(self)
                        if hx is not None and abs(self.cx - hx) > max(20, self.S * 0.2):
                            return _rest_orig_choose(self)
                    _rest_play(self.app, self)
                    return
            except Exception:
                pass
            return _rest_orig_choose(self)
        Buddy.choose = _rest_choose

        _rest_orig_quiet = App.quiet

        def _rest_quiet(self):
            return _rest_orig_quiet(self) or bool(self.cfg.get("rest_mode", False))
        App.quiet = _rest_quiet

        _rest_orig_set_sleep = App.set_sleep

        def _rest_set_sleep(self, on):
            if on:
                self.cfg["rest_mode"] = False
            return _rest_orig_set_sleep(self, on)
        App.set_sleep = _rest_set_sleep
        App.set_rest = set_rest

        _rest_orig_paint = Buddy.paintEvent

        def _rest_paint_event(self, e):
            _rest_orig_paint(self, e)
            if getattr(self, "_rest_game", False):
                try:
                    _rest_paint(self)
                except Exception:
                    pass
        Buddy.paintEvent = _rest_paint_event
    except Exception as _e:
        print("rest mode hook failed:", _e)
