"""Pet input callbacks."""

import random
from PyQt5.QtCore import QPoint, QTimer, Qt
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QApplication
from minibuddies.catalog import DROP_LINES


class PetInput:
    def check_pat(self):
        """커서를 머리 위에 가만히 올려두면 쓰담쓰담"""
        if self.state in ("sleep", "nap", "air", "dig", "balloon", "walk", "run", "roll", "crawl", "hang", "climb",
                          "rope", "rope_pause", "wallclimb", "push") \
                or getattr(self, "goal", None) is not None or abs(self.vx) > 0.5 or QApplication.mouseButtons():
            self.pat = 0; return                         # 도망·쫓기·이동 중엔 쓰담 안 됨 (지나가다 커서에 닿아도 X)
        c = QCursor.pos()
        if self.geometry().contains(c):
            self.pat += 1
            if self.pat == 45:
                self.vx = 0; self.cool = 300
                self.set("happy", 150)
                self.app.touch(self, "pat")
            elif self.pat > 45 and self.state == "happy":
                self.t = max(self.t, 30)          # 계속 쓰다듬으면 계속 행복
        else:
            self.pat = 0

    # ── 파일 던지기 ────────────────────────────
    def _drop_paths(self, e):
        md = e.mimeData()
        if not md.hasUrls():
            return []
        return [u.toLocalFile() for u in md.urls() if u.isLocalFile() and u.toLocalFile()]

    def dragEnterEvent(self, e):
        if self._drop_paths(e):
            e.acceptProposedAction()
            if self.surface and self.state not in ("sleep", "nap"):
                self.vx = 0; self.set("surprise", 60)
            self.say(random.choice(DROP_LINES["hover"]), 80)
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        e.acceptProposedAction() if self._drop_paths(e) else e.ignore()

    def dropEvent(self, e):
        paths = self._drop_paths(e)
        if not paths:
            return
        e.acceptProposedAction()
        QTimer.singleShot(50, lambda: self.app.file_drop(self, paths))

    # ── 마우스 ────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and getattr(self, "hiding", False):   # 숨바꼭질: 찾았다!
            self.app.hs_found(self)
            return
        if e.button() == Qt.LeftButton:
            self.drag = e.globalPos() - QPoint(int(self.fx), int(self.fy))
            self.stop_plugin_action()
            self.drop_rope()
            if self.state in ("group", "gather", "tower", "train"):
                self.app.group_break()
            self.moved = False
            self.trail = [e.globalPos()]
            self.angle = 0
            self.update()

    def mouseMoveEvent(self, e):
        if self.drag is None:
            return
        if not self.moved and (e.globalPos() - self.trail[0]).manhattanLength() < 6:
            return                                   # 손 떨림 정도는 '클릭'으로 봄
        self.moved = True
        p = e.globalPos() - self.drag
        self.fx, self.fy = float(p.x()), float(p.y())
        self.trail = (self.trail + [e.globalPos()])[-5:]
        self.move(p)

    def mouseReleaseEvent(self, e):
        if self.drag is None or e.button() != Qt.LeftButton:
            return
        self.drag = None
        if not (self.moved and len(self.trail) >= 2):
            # 톡! → 따닥(더블클릭)일 수도 있으니 잠깐 기다렸다가 폴짝 (그 사이 제자리에 가만히)
            self.vx = 0; self.goal = None
            tok = object(); self._click = tok
            QTimer.singleShot(QApplication.doubleClickInterval() + 40,
                              lambda: self._single_click() if getattr(self, "_click", None) is tok else None)
            return
        self.surface = None
        self.fall_from = self.fy
        if self.moved and len(self.trail) >= 2:
            d = self.trail[-1] - self.trail[0]
            n = len(self.trail)
            self.vx = max(-25, min(25, d.x() / n))
            self.vy = max(-25, min(25, d.y() / n))
            self.air_kind = "thrown" if abs(self.vx) + abs(self.vy) > 7 else "fall"
            if self.air_kind == "thrown":
                self.app.add_aff(self, -1)
            self.set("air")
        else:   # 톡! → 폴짝 + 만세
            self.hop(11)
            self.after = None

    def _single_click(self):
        self._click = None
        if self.drag is not None or self not in self.app.buddies:
            return
        if self.surface is None or self.state in self.app.BUSY:   # 공중·매달린 중이면 예전처럼 폴짝
            self.app.touch(self, "poke")
            self.surface = None
            self.fall_from = self.fy
            self.hop(11)
            self.after = None
            return
        # 땅 위에서 톡: 폴짝 뛰지 않고 제자리에서 반응 (낯가리면 깜짝, 친하면 반가워함) — 삐짐은 touch 가 처리
        if self.state == "pout":                       # 삐진 중엔 계속 찔러도 흥! 하고 고개 돌린 채
            self.set("pout", 120)
            self.say("흥!", 60)
            return
        lv = self.app.aff_level(self.app.aff(self.char))
        self.vx = 0; self.goal = None
        self.set(("surprise", "surprise", "wave", "happy", "happy")[lv], 70)
        self.app.touch(self, "poke")

    def mouseDoubleClickEvent(self, e):
        self._click = None                            # 첫 번째 '톡' 폴짝은 취소
        self.drag = None
        self.vx = 0
        if self.surface is None:
            self.stand_on(self.find_floor(self.cx, self.feet()) or self.surfaces()[-1])
        self.set("cheer", 90)
        if self.app.cfg.get("ask_dbl", True):          # 따닥 → 이 아이에게 Claude 로 물어보기
            QTimer.singleShot(250, lambda: self.app.ask_claude(self))

    def contextMenuEvent(self, e):
        self.app.menu(e.globalPos(), self)
