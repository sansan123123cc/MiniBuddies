"""Desktop overlays for pets and group scenes."""

import math
from PyQt5.QtCore import QPoint, QTimer, Qt
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QWidget
from minibuddies.catalog import BUBBLE_PX, SCENE_ART_DIR, SCENE_MOTION, SHAKE, SQUADS
from minibuddies.desktop import screen_for, target_screen


class Rope(QWidget):
    """밧줄 타고 내려올 때 화면 위에서 이어지는 줄"""
    def __init__(self, rgb=(154, 106, 76)):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                            | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.rgb = rgb
        self.w = 4

    def place(self, x, y0, y1, w=4):
        self.w = max(2, int(round(w)))
        h = max(1, int(y1 - y0))
        self.setGeometry(int(round(x - self.w / 2)), int(y0), self.w, h)
        if not self.isVisible():
            self.show()

    def paintEvent(self, e):
        from PyQt5.QtGui import QColor
        p = QPainter(self)
        r, g, b = self.rgb
        p.fillRect(0, 0, self.w, self.height(), QColor(int(r * 0.7), int(g * 0.7), int(b * 0.7)))
        if self.w > 2:
            p.fillRect(1, 0, self.w - 2, self.height(), QColor(r, g, b))


class Burst(QWidget):
    """부딪힐 때 '팍!' 하고 터지는 별"""
    def __init__(self, x, y, size):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                            | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.n = 0
        s = max(40, int(size))
        self.setGeometry(int(x - s / 2), int(y - s / 2), s, s)
        self.tm = QTimer(self, timeout=self.tick); self.tm.start(30)
        self.show()

    def tick(self):
        self.n += 1
        if self.n > 13:
            self.tm.stop(); self.close(); return
        self.update()

    def paintEvent(self, e):
        from PyQt5.QtGui import QColor, QPolygonF, QPen
        from PyQt5.QtCore import QPointF
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width() / 2
        k = min(1.0, self.n / 3) * max(0.0, 1 - max(0, self.n - 8) / 5)
        p.translate(w, w)
        for col, sc in ((QColor(45, 30, 45), 1.0), (QColor(255, 232, 90), 0.78)):
            pts = []
            for i in range(16):
                r = w * k * sc * (0.95 if i % 2 == 0 else 0.42)
                a = math.pi * 2 * i / 16 + 0.2
                pts.append(QPointF(math.cos(a) * r, math.sin(a) * r))
            p.setPen(QPen(col, 0)); p.setBrush(col)
            p.drawPolygon(QPolygonF(pts))

class Bubble(QWidget):
    """머리 위 말풍선 — 글자 크기를 픽셀로 고정해서 모니터 배율이 달라도 안 잘림. 길면 여러 줄"""
    MAXW = 230

    def __init__(self, text, sticky=False, on_close=None):
        super().__init__()
        from PyQt5.QtGui import QFont
        self.sticky, self.on_close = sticky, on_close
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        if not sticky:
            flags |= Qt.WindowTransparentForInput      # 평소 말풍선은 클릭이 통과
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        k = BUBBLE_PX["px"] / 14
        self.MAXW = int((280 if sticky else 230) * max(1.0, k))
        if sticky:
            self.setCursor(Qt.PointingHandCursor)
            self.setToolTip("클릭하면 닫혀요")
        self.text = text
        self.font = QFont("Malgun Gothic")
        self.font.setPixelSize(int(BUBBLE_PX["px"])); self.font.setBold(True)
        self.fit()

    def measure(self, fm):
        from PyQt5.QtCore import QRect
        one = fm.horizontalAdvance(self.text) if hasattr(fm, "horizontalAdvance") else fm.width(self.text)
        tw = min(one + 6, self.MAXW)
        r = fm.boundingRect(QRect(0, 0, tw, 4000), int(Qt.TextWordWrap | Qt.AlignHCenter), self.text)
        return max(tw, r.width() + 4), r.height() + 4

    def fit(self, fm=None):
        from PyQt5.QtGui import QFontMetrics
        self.tw, self.th = self.measure(fm or QFontMetrics(self.font))
        self.setFixedSize(self.tw + 24, self.th + 22)

    def paintEvent(self, e):
        from PyQt5.QtGui import QColor, QPen, QPolygon
        p = QPainter(self)
        p.setFont(self.font)
        tw, th = self.measure(p.fontMetrics())        # 그리는 순간의 실제 글자 크기로 다시 재기
        if tw > self.tw or th > self.th:              # 모자라면 키우고 다시 그림
            p.end()
            self.tw, self.th = max(tw, self.tw), max(th, self.th)
            self.setFixedSize(self.tw + 24, self.th + 22)
            self.update()
            return
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QPen(QColor(40, 30, 45), 2))
        p.setBrush(QColor(255, 255, 255, 240))
        p.drawRoundedRect(1, 1, w - 2, h - 9, 9, 9)
        p.drawPolygon(QPolygon([QPoint(w // 2 - 6, h - 9), QPoint(w // 2 + 6, h - 9), QPoint(w // 2, h - 1)]))
        p.setPen(QColor(255, 255, 255)); p.drawLine(w // 2 - 5, h - 9, w // 2 + 5, h - 9)
        p.setPen(QColor(40, 30, 45))
        p.drawText(12, 6, w - 24, h - 16, int(Qt.AlignCenter | Qt.TextWordWrap), self.text)
        if self.sticky:                                   # 클릭해서 닫는 말풍선: 오른쪽 위 작은 ×
            p.setPen(QPen(QColor(150, 120, 150), 1.6))
            p.drawLine(w - 13, 6, w - 7, 12); p.drawLine(w - 7, 6, w - 13, 12)

    def mousePressEvent(self, e):
        if self.sticky:
            cb, self.on_close = self.on_close, None
            self.close()
            if cb:
                cb()


class Flash(QWidget):
    """단체사진 '찰칵' 플래시"""
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                            | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setGeometry(target_screen().geometry())
        self.a = 200
        self.tm = QTimer(self, timeout=self.tick); self.tm.start(30)
        self.show()

    def tick(self):
        self.a -= 25
        if self.a <= 0:
            self.tm.stop(); self.close(); return
        self.update()

    def paintEvent(self, e):
        from PyQt5.QtGui import QColor
        QPainter(self).fillRect(self.rect(), QColor(255, 255, 255, max(0, self.a)))

class Scene(QWidget):
    """여러 명이 한 그림으로 함께 나오는 장면 창"""
    def __init__(self, app, sq, name, cx, floor_y):
        super().__init__()
        self.app, self.name, self.sq = app, name, sq
        self.screen = screen_for(SQUADS[sq][0]) if sq in SQUADS else target_screen()
        ss = app.scene_sets[sq]
        meta = ss["meta"]
        self.frames, self.speed, self.t, self.vx, line, self.after = ss["scenes"][name]
        have = [f for f in self.frames if f in meta]      # 아직 없는 프레임은 건너뜀
        if not have:
            have = {"karaoke": [10, 11]}.get(name, [])
        self.frames = have or [f for f in range(16) if f in meta][:1]
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.pix = [app.scene_pix(sq, f) for f in self.frames]
        m = meta.get(self.frames[0], {"w": 3, "h": 1})
        S = app.size
        self.iw, self.ih = int(S * m["w"]), int(S * m["h"])     # 그림 크기
        self.mx, self.my = int(S * 0.1), int(S * 0.35)            # 흔들림·점프용 여유 공간
        self.w, self.h = self.iw + self.mx * 2, self.ih + self.my
        self.setFixedSize(self.w, self.h)
        self.motion = SCENE_MOTION.get(name, "")
        self.S = S
        self.fx = cx - self.w / 2
        self.floor = floor_y
        self.art = SCENE_ART_DIR.get(name, 1)
        self.face = self.art
        self.anim = 0
        self.shake = name == "brawl"
        self.bubble = Bubble(line); self.bubble_t = 160
        self.place(); self.show(); self.bubble.show(); self.place()

    def place(self):
        scr = self.screen.availableGeometry()
        self.fx = max(scr.left() - self.w * 0.1, min(scr.right() - self.w * 0.9, self.fx))
        k = SHAKE["k"]
        dx = round(math.sin(self.anim * 0.9) * 2) if self.shake and k >= 0.99 else 0   # 창 자체 떨림은 '세게'에서만
        dy = 0
        self.move(int(self.fx + dx), int(self.floor - self.h + dy))
        if self.bubble:
            self.bubble.move(int(self.fx + self.w / 2 - self.bubble.width() / 2), int(self.floor - self.ih - self.bubble.height() - 2))

    def step(self):
        self.anim += 1
        self.t -= 1
        if self.vx:
            scr = self.screen.availableGeometry()
            self.fx += self.vx * self.face
            # 끝에 닿으면 '그쪽으로 가고 있을 때만' 한 번 뒤돌기 (예전엔 매 프레임 뒤집혀 번쩍번쩍했음)
            lo, hi = scr.left() - self.w * 0.1, scr.right() - self.w * 0.9
            if self.fx <= lo and self.vx * self.face < 0:
                self.fx = lo; self.face = -self.face
            elif self.fx >= hi and self.vx * self.face > 0:
                self.fx = hi; self.face = -self.face
        if self.bubble:
            if not self.bubble.sticky:
                self.bubble_t -= 1
            if self.bubble_t <= 0 and not self.bubble.sticky:
                self.bubble.close(); self.bubble = None
        self.place(); self.update()
        return self.t > 0

    def pose(self):
        """장면별 몸짓: (위로 뜨는 높이, 회전각, 가로배율, 세로배율) — SHAKE 로 세기 조절, 그림이 잘 보이게 부드럽게"""
        t, S, m, k = self.anim, self.S, self.motion, SHAKE["k"]
        up, rot, sx, sy = 0.0, 0.0, 1.0, 1.0
        if k <= 0:
            return up, rot, sx, sy
        if m == "rock":                                   # 어깨동무 좌우로 흔들흔들
            rot = math.sin(t / 30 * math.pi) * 3.0
        elif m == "squeeze":                              # 꼬옥 끌어안기
            q = (math.sin(t / 18) + 1) / 2
            sx, sy = 1 - 0.035 * q * k, 1 + 0.025 * q * k
            return up, rot, sx, sy
        elif m == "breathe":                              # 새근새근 숨쉬기
            return up, rot, sx, 1 + 0.025 * k * math.sin(t / 40)
        elif m == "wobble":                               # 피라미드 위태위태 (조금씩 심해짐)
            rot = math.sin(t / 12) * min(4.0, 1 + t / 90)
        elif m == "bob":                                  # 냠냠 들썩들썩
            up = abs(math.sin(t / 16)) * S * 0.03
        elif m == "brawl":                                # 투닥투닥: 막 떨지 않고 통통 튀는 정도
            rot = math.sin(t / 4.5) * 2.5
            up = abs(math.sin(t / 6)) * S * 0.04
        elif m == "hop":                                  # 다 같이 깡충깡충
            ph = (t % 60) / 60
            if ph < 0.25:
                sy, sx = 1 - 0.1 * k * (ph / 0.25), 1 + 0.05 * k * (ph / 0.25)
                return up, rot, sx, sy
            q = (ph - 0.25) / 0.75
            up = math.sin(q * math.pi) * S * 0.22
        elif m == "march":                                # 발맞춰 통통
            up = abs(math.sin(t / 12)) * S * 0.035
        elif m == "beat":                                 # 박자 맞춰 콩콩
            up = abs(math.sin(t / 11)) * S * 0.03
            sy = 1 + 0.015 * k * math.sin(t / 6)
        elif m == "nag":                                  # 잔소리하며 씰룩
            rot = math.sin(t / 8) * 1.2
        elif m == "tiptoe":                               # 까치발 살금살금
            up = abs(math.sin(t / 18)) * S * 0.025
        elif m == "pose":                                 # 찰칵 전에 꼼지락
            sy = 1 + 0.02 * k * math.sin(t / 12)
        return up * k, rot * k, sx, sy

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        pm = self.pix[(self.anim // self.speed) % len(self.pix)]
        up, rot, sx, sy = self.pose()
        p.translate(self.w / 2, self.h - up)               # 발밑 가운데를 기준으로
        if rot:
            p.rotate(rot)
        p.scale(sx * (-1 if self.face != self.art else 1), sy)
        p.drawPixmap(int(-self.iw / 2), int(-self.ih), self.iw, self.ih, pm)

    def mousePressEvent(self, e):
        self.t = 0                      # 클릭하면 장면 끝

    def end(self):
        if self.bubble:
            self.bubble.close()
        self.close()
