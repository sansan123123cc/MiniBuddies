"""Click-through, opacity and their desktop control."""

import sys
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QApplication, QMenu, QWidget
from minibuddies.catalog import APP_NAME
from minibuddies.ui.widgets import Bubble


# ── 터치 OFF(클릭 통과) 모드 · 펫 투명도 · 떠 있는 '터치/투명도' 버튼 (폰의 터치 ON/OFF 버튼과 같은 것) ──
PET_ALPHA = {"a": 1.0}


def _pt_set_click_through(w, on):
    """창이 마우스를 막지 않게(뒤의 창이 클릭됨) — 윈도우는 WS_EX_TRANSPARENT, 그 밖은 Qt 플래그"""
    try:
        if sys.platform.startswith("win"):
            import ctypes
            hwnd = int(w.winId())
            u = ctypes.windll.user32
            st = u.GetWindowLongW(hwnd, -20)                    # GWL_EXSTYLE
            ns = (st | 0x20 | 0x80000) if on else (st & ~0x20)  # WS_EX_TRANSPARENT | WS_EX_LAYERED
            if ns != st:
                u.SetWindowLongW(hwnd, -20, ns)
        else:
            h = w.windowHandle()
            if h is not None and bool(h.flags() & Qt.WindowTransparentForInput) != bool(on):
                h.setFlag(Qt.WindowTransparentForInput, on)
    except Exception:
        pass


class PassBar(QWidget):
    """화면에 떠 있는 작은 버튼: [터치 ON/OFF] [투명도 %] — 끌어서 옮기기, 휠로 투명도, 우클릭 메뉴"""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(176, 32)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("왼쪽: 터치 ON/OFF (OFF면 펫이 클릭을 막지 않아요)\n오른쪽: 누르거나 휠을 굴려 투명도 조절\n끌어서 옮기기 · 우클릭: 숨기기")
        self._press = None
        self._moved = False
        pos = app.cfg.get("pass_btn_pos")
        sc = QApplication.primaryScreen().availableGeometry()
        if pos and any(s.availableGeometry().contains(pos[0] + 10, pos[1] + 10) for s in QApplication.screens()):
            self.move(pos[0], pos[1])
        else:
            self.move(sc.left() + 8, sc.top() + 8)

    def paintEvent(self, e):
        from PyQt5.QtGui import QPainter, QColor, QFont
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        off = bool(self.app.cfg.get("passthru", False))
        w, h = self.width(), self.height()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 225))
        p.drawRoundedRect(0, 0, w - 1, h - 1, h / 2, h / 2)
        lw = 104
        p.setBrush(QColor(150, 150, 160) if off else QColor(226, 104, 160))
        p.drawRoundedRect(3, 3, lw - 3, h - 7, (h - 7) / 2, (h - 7) / 2)
        f = QFont(); f.setPixelSize(12); f.setBold(True); p.setFont(f)
        p.setPen(QColor(255, 255, 255))
        p.drawText(3, 3, lw - 3, h - 7, Qt.AlignCenter, "터치 OFF" if off else "터치 ON")
        p.setPen(QColor(140, 70, 105))
        p.drawText(lw, 0, w - lw - 4, h, Qt.AlignCenter, f"◐ {int(round(PET_ALPHA['a'] * 100))}%")
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press = (e.globalPos(), self.pos())
            self._moved = False

    def mouseMoveEvent(self, e):
        if self._press is None:
            return
        d = e.globalPos() - self._press[0]
        if abs(d.x()) + abs(d.y()) > 5:
            self._moved = True
        if self._moved:
            self.move(self._press[1] + d)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.RightButton:
            self.menu(e.globalPos())
            return
        if self._press is None:
            return
        self._press = None
        if self._moved:
            self.app.cfg["pass_btn_pos"] = [self.x(), self.y()]
            self.app.save_cfg()
            return
        if e.pos().x() < 104:
            self.app.set_passthru(not self.app.cfg.get("passthru", False))
        else:
            steps = [1.0, 0.85, 0.7, 0.55, 0.4, 0.25]
            cur = PET_ALPHA["a"]
            nxt = next((s for s in steps if s < cur - 0.01), steps[0])
            self.app.set_pet_alpha(nxt)

    def wheelEvent(self, e):
        d = 0.05 if e.angleDelta().y() > 0 else -0.05
        self.app.set_pet_alpha(PET_ALPHA["a"] + d)

    def menu(self, gp):
        m = QMenu()
        m.addAction("터치 ON (펫 만지기)" if self.app.cfg.get("passthru") else "터치 OFF (클릭 통과)",
                    lambda: self.app.set_passthru(not self.app.cfg.get("passthru", False)))
        om = m.addMenu("투명도")
        for pc in (100, 85, 70, 55, 40, 25):
            a = om.addAction(f"{pc}%", lambda pc=pc: self.app.set_pet_alpha(pc / 100))
            a.setCheckable(True); a.setChecked(abs(PET_ALPHA["a"] * 100 - pc) < 1)
        m.addSeparator()
        m.addAction("5분 동안 이 버튼 숨기기", lambda: (self.hide(), QTimer.singleShot(5 * 60 * 1000, self.app.passbar_update)))
        m.addAction("이 버튼 끄기 (트레이 아이콘에서 다시 켜기)", lambda: self.app.set_pass_btn(False))
        m.exec_(gp)


def _pt_start(self):
    PET_ALPHA["a"] = max(0.2, min(1.0, float(self.cfg.get("pet_alpha", 1.0))))
    self.passbar = None
    self._pt_timer = QTimer()
    self._pt_timer.timeout.connect(self.passthru_apply)
    self._pt_timer.start(600)
    self.passbar_update()
    self.passthru_apply()


def _pt_apply(self):
    """모든 펫 창에 지금 설정(클릭 통과 · 투명도)을 맞춤 — 새로 나온 아이도 자동으로"""
    on = bool(self.cfg.get("passthru", False))
    a = PET_ALPHA["a"]
    for b in list(getattr(self, "buddies", [])):
        try:
            if not b.isVisible():
                continue
            if getattr(b, "_pt_on", None) != on or getattr(b, "_pt_wid", None) != int(b.winId()):
                _pt_set_click_through(b, on)
                b._pt_on = on; b._pt_wid = int(b.winId())
            elif on and sys.platform.startswith("win"):
                _pt_set_click_through(b, True)            # 창 스타일이 다시 바뀌어도 계속 통과되게
            if abs(b.windowOpacity() - a) > 0.01:
                b.setWindowOpacity(a)
        except Exception:
            pass
    try:   # 말풍선도 펫과 같은 투명도로
        for w in QApplication.topLevelWidgets():
            if isinstance(w, Bubble) and abs(w.windowOpacity() - a) > 0.01:
                w.setWindowOpacity(a)
    except Exception:
        pass


def _pt_set(self, on):
    self.cfg["passthru"] = bool(on)
    self.save_cfg()
    for b in list(getattr(self, "buddies", [])):
        b._pt_on = None
    self.passthru_apply()
    self.passbar_update()
    try:
        if on and getattr(self, "tray", None) is not None:
            self.tray.showMessage(APP_NAME, "터치 OFF — 펫이 클릭을 막지 않아요.\n다시 만지려면 '터치' 버튼이나 트레이 아이콘 메뉴를 누르세요.")
    except Exception:
        pass


def _pt_set_alpha(self, a):
    a = max(0.2, min(1.0, round(float(a), 2)))
    PET_ALPHA["a"] = a
    self.cfg["pet_alpha"] = a
    self.save_cfg()
    self.passthru_apply()
    self.passbar_update()


def _pt_set_btn(self, on):
    self.cfg["pass_btn"] = bool(on)
    self.save_cfg()
    self.passbar_update()


def _pt_bar_update(self):
    want = bool(self.cfg.get("pass_btn", True))
    if not want:
        if getattr(self, "passbar", None) is not None:
            self.passbar.hide()
        return
    if getattr(self, "passbar", None) is None:
        self.passbar = PassBar(self)
    self.passbar.show(); self.passbar.raise_(); self.passbar.update()


def _pt_tray(self, tm):
    """트레이 메뉴에: 터치 OFF · 투명도 · 버튼 보이기"""
    a = tm.addAction("터치 OFF (클릭 통과 — 펫 뒤의 창을 클릭할 수 있어요)")
    a.setCheckable(True)
    a.triggered.connect(lambda on: self.set_passthru(on))
    om = tm.addMenu("펫 투명도")
    acts = []
    for pc in (100, 85, 70, 55, 40, 25):
        x = om.addAction(f"{pc}%", lambda pc=pc: self.set_pet_alpha(pc / 100))
        x.setCheckable(True); acts.append((pc, x))
    bt = tm.addAction("화면에 '터치·투명도' 버튼 보이기")
    bt.setCheckable(True)
    bt.triggered.connect(lambda on: self.set_pass_btn(on))

    def sync():
        a.setChecked(bool(self.cfg.get("passthru", False)))
        bt.setChecked(bool(self.cfg.get("pass_btn", True)))
        for pc, x in acts:
            x.setChecked(abs(PET_ALPHA["a"] * 100 - pc) < 1)
    tm.aboutToShow.connect(sync)
    tm.addSeparator()


def _pt_menu(self, top):
    """펫 우클릭 메뉴 맨 위에: 터치 OFF · 투명도"""
    top.addAction("터치 OFF로 바꾸기 (펫이 클릭을 막지 않게)", lambda: self.set_passthru(True))
    om = top.addMenu(f"펫 투명도 ({int(round(PET_ALPHA['a'] * 100))}%)")
    for pc in (100, 85, 70, 55, 40, 25):
        x = om.addAction(f"{pc}%", lambda pc=pc: self.set_pet_alpha(pc / 100))
        x.setCheckable(True); x.setChecked(abs(PET_ALPHA["a"] * 100 - pc) < 1)
    top.addSeparator()

def install(App):
    """Attach the passthrough behavior to the application."""
    App.passthru_start = _pt_start
    App.passthru_apply = _pt_apply
    App.set_passthru = _pt_set
    App.set_pet_alpha = _pt_set_alpha
    App.set_pass_btn = _pt_set_btn
    App.passbar_update = _pt_bar_update
    App.passthru_tray = _pt_tray
    App.passthru_menu = _pt_menu

    # 말풍선도 처음 뜰 때부터 펫 투명도를 따라감
    _pt_bubble_init = Bubble.__init__
    def _pt_bubble_init2(self, *a, **k):
        _pt_bubble_init(self, *a, **k)
        try:
            self.setWindowOpacity(PET_ALPHA["a"])
        except Exception:
            pass
    Bubble.__init__ = _pt_bubble_init2
