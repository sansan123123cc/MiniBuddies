"""Qt pet window and shared state."""

import random
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget
from minibuddies.catalog import CRY_LINES, F, char_scale
from minibuddies.pets.animation import PetAnimation
from minibuddies.pets.input import PetInput
from minibuddies.pets.movement import PetMovement
from minibuddies.ui.widgets import Rope


class Buddy(PetMovement, PetAnimation, PetInput, QWidget):
    def __init__(self, app, size, x=None, entrance=None, char=None):
        super().__init__()
        self.app = app
        self.char = char or app.pick_char()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAcceptDrops(True)    # 파일 던지기: 파일을 캐릭터 위에 놓으면 요약·정리·변환
        # 기본은 모두 같은 크기. 메뉴에서 '크기 제각각'을 켜면 살짝씩 달라짐
        self.scale = random.uniform(0.8, 1.15) if app.cfg.get("varied", False) else 1.0
        self.S = int(size * self.scale * char_scale(app.cfg, self.char))
        self.setFixedSize(self.S, self.S)
        size = self.S
        self.rope = None
        self.pat = 0
        self.react_next = None       # 부딪힌 뒤 착지해서 할 리액션
        self.grudge = None           # 나를 맞힌 친구
        self.knock_t = 0
        self.goal = None             # 친구에게 다가가기/쫓기/도망
        self.bubble = None; self.bubble_t = 0
        self.pframes, self.pspeed, self.pvx = [0], 10, 0.0
        self.gx = None               # 단체 동작: 모일 위치
        self.gframe = [0]            # 단체 동작: 보여줄 프레임
        self.target_y = 0
        self.face = random.choice([-1, 1])
        self.angle = 0.0
        self.anim = 0
        self.vx = self.vy = 0.0
        self.surface = None          # (left, top, right) 지금 서 있는 곳
        self.edge = 0                # 매달리기/걸터앉기 중인 모서리 방향 (-1 왼쪽, 1 오른쪽)
        self.state, self.t = "air", 0
        self.air_kind = "fall"
        self.fall_from = 0.0
        self.cool = 0                # 마우스·친구 반응 쿨타임
        self.edge_cool = 0
        self.drag = None
        self.after = None            # 상태 끝나고 할 일
        scr = self.scr()
        cx = x if x is not None else random.randint(scr.left() + size, scr.right() - size)
        self.fx = float(cx - size / 2)
        ent = entrance or random.choice(["drop", "drop", "peek", "umbrella", "umbrella", "rope"])
        if app.quiet() and ent in ("drop", "umbrella", "rope"):   # 한 자리에 있기: 하늘에서 안 떨어지고 바닥에서 빼꼼
            ent = "peek"
        if ent == "peek":
            self.fy = float(scr.bottom() - self.S * self.fbottom(F["peek"]))
            self.set("peek", random.randint(90, 160))
        elif ent == "umbrella":
            self.fy = float(scr.top() - size)
            self.set("umbrella")
        elif ent == "rope":
            self.fy = float(scr.top() - size)
            self.rope = Rope(tuple(app.chars[self.char]["rope"].get("rgb", (154, 106, 76))))
            self.set("rope", random.randint(0, 2))   # t = 중간에 멈칫할 횟수
        else:
            self.fy = float(scr.top() - size)
            self.fall_from = self.fy
            self.vx = random.uniform(-1, 1)
        self.move(int(self.fx), int(self.fy))
        self.show()

    @property
    def cx(self):
        return self.fx + self.S / 2

    def feet(self, f=0):
        return self.fy + self.S * self.fbottom(f)

    def set(self, st, t=0, after=None):
        prev = self.state
        self.align_sequence = False
        self.state, self.t, self.after = st, t, after
        if st not in ("roll",):
            self.angle = 0
        if st == "cry" and prev != "cry" and self.char in CRY_LINES:   # 울 때 캐릭터별 대사
            self.say(random.choice(CRY_LINES[self.char]), 160)

    def stand_on(self, surf):
        self.surface = surf
        self.fy = surf[1] - self.S * self.fbottom(0)

    def closeEvent(self, e):
        """펫이 화면에서 빠질 때(환경설정에서 빼기·퇴장 등) 말풍선도 같이 정리 — 안 하면 말풍선만 허공에 남음"""
        try:
            if self.bubble:
                bb, self.bubble = self.bubble, None
                bb.close()
            self.drop_rope()
        except Exception:
            pass
        super().closeEvent(e)
