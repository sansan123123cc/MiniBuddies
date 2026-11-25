"""Settings dialog layout, search and application of options."""

import os
import random
import re
from PyQt5.QtCore import QPoint, QTimer, Qt
from PyQt5.QtGui import QPainter, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from minibuddies.catalog import ALARMS, APP_NAME, BUBBLE_PX, TICK
from minibuddies.desktop import CHAR_SCREEN, target_screen
from minibuddies.runtime import BASE
from minibuddies.ui.dialogs.settings.activities import ActivityTabs
from minibuddies.ui.dialogs.settings.appearance import AppearanceTabs
from minibuddies.ui.dialogs.settings.characters import CharacterTabs
from minibuddies.ui.dialogs.settings.integrations import IntegrationTabs
from minibuddies.ui.widgets import Bubble


def settings_qss():
    """환경설정 창 분홍 테마 (체크 표시 그림은 처음 한 번 임시 폴더에 그려 둠)"""
    import tempfile
    tmp = tempfile.gettempdir()
    ck = os.path.join(tmp, "minibuddies_check.png")
    up, dn = os.path.join(tmp, "minibuddies_up.png"), os.path.join(tmp, "minibuddies_dn.png")
    for path, pts in ((up, ((2, 10), (8, 3), (14, 10))), (dn, ((2, 3), (8, 10), (14, 3)))):
        if not os.path.exists(path):
            try:
                from PyQt5.QtGui import QColor, QPolygon
                pm = QPixmap(16, 13); pm.fill(Qt.transparent)
                pa = QPainter(pm); pa.setRenderHint(QPainter.Antialiasing)
                pa.setPen(Qt.NoPen); pa.setBrush(QColor("#d0588a"))
                pa.drawPolygon(QPolygon([QPoint(x, y) for x, y in pts])); pa.end()
                pm.save(path)
            except Exception:
                pass
    if not os.path.exists(ck):
        try:
            from PyQt5.QtGui import QPen, QColor
            pm = QPixmap(32, 32); pm.fill(Qt.transparent)
            pa = QPainter(pm); pa.setRenderHint(QPainter.Antialiasing)
            pa.setPen(QPen(QColor("white"), 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            pa.drawPolyline(QPoint(7, 17), QPoint(13, 23), QPoint(25, 9)); pa.end()
            pm.save(ck)
        except Exception:
            pass
    ck, up, dn = (x.replace("\\", "/") for x in (ck, up, dn))
    return """
QDialog{background:#fff4f8;}
QDialog QWidget{font-family:'Malgun Gothic','맑은 고딕',sans-serif;font-size:10pt;color:#4a3a44;}
QTabWidget::pane{border:1px solid #f3c6d8;border-radius:12px;background:#fffafc;top:-1px;}
QTabBar::tab{background:#fbe3ee;color:#9a4d6e;border:1px solid #f3c6d8;border-bottom:none;padding:7px 18px;margin-right:3px;
  border-top-left-radius:10px;border-top-right-radius:10px;}
QTabBar::tab:selected{background:#fffafc;color:#d0588a;font-weight:bold;}
QTabBar::tab:hover:!selected{background:#f7d3e3;}
QGroupBox{border:1px solid #f3c6d8;border-radius:12px;margin-top:16px;padding:12px 8px 8px;background:#ffffff;}
QGroupBox QGroupBox{background:#fff8fb;}
QGroupBox::title{subcontrol-origin:margin;left:14px;padding:0 6px;color:#d0588a;font-weight:bold;}
QPushButton{background:#fbe3ee;color:#b0476f;border:1px solid #f3c6d8;border-radius:9px;padding:5px 14px;min-height:20px;}
QPushButton:hover{background:#f7cfe0;}
QPushButton:pressed{background:#f0b7cf;}
QPushButton:default{background:#e86a9b;color:white;border-color:#e86a9b;font-weight:bold;}
QPushButton:disabled{color:#c9a9b8;background:#f8eef3;}
QCheckBox{spacing:8px;}
QCheckBox::indicator{width:17px;height:17px;border:1px solid #e3a3bf;border-radius:5px;background:white;}
QCheckBox::indicator:hover{border-color:#e86a9b;}
QCheckBox::indicator:checked{background:#e86a9b;border-color:#e86a9b;image:url(%(ck)s);}
QComboBox,QSpinBox,QTimeEdit,QLineEdit{background:white;border:1px solid #f0c3d6;border-radius:8px;padding:3px 8px;min-height:22px;}
QComboBox:focus,QSpinBox:focus,QLineEdit:focus,QTimeEdit:focus{border-color:#e86a9b;}
QComboBox::drop-down{border:none;width:22px;}
QComboBox::down-arrow{image:url(%(dn)s);width:12px;height:9px;margin-right:8px;}
QAbstractSpinBox::up-button,QAbstractSpinBox::down-button{width:16px;border:none;background:transparent;}
QAbstractSpinBox::up-arrow{image:url(%(up)s);width:10px;height:7px;}
QAbstractSpinBox::down-arrow{image:url(%(dn)s);width:10px;height:7px;}
QComboBox QAbstractItemView{background:white;border:1px solid #f0c3d6;selection-background-color:#fbe3ee;selection-color:#b0476f;}
QSlider::groove:horizontal{height:6px;background:#f3d9e5;border-radius:3px;}
QSlider::sub-page:horizontal{background:#e86a9b;border-radius:3px;}
QSlider::handle:horizontal{background:white;border:2px solid #e86a9b;width:14px;margin:-6px 0;border-radius:9px;}
QScrollArea{background:transparent;border:none;}
QScrollArea > QWidget > QWidget{background:transparent;}
QScrollBar:vertical{background:transparent;width:10px;margin:2px;}
QScrollBar::handle:vertical{background:#f0c3d6;border-radius:4px;min-height:30px;}
QScrollBar:horizontal{background:transparent;height:10px;margin:2px;}
QScrollBar::handle:horizontal{background:#f0c3d6;border-radius:4px;min-width:30px;}
QScrollBar::add-line,QScrollBar::sub-line{height:0;width:0;}
QListWidget,QTableWidget,QTextBrowser{background:white;border:1px solid #f0c3d6;border-radius:8px;}
QHeaderView::section{background:#fbe3ee;color:#9a4d6e;border:none;padding:4px;}
""" % {"ck": ck, "up": up, "dn": dn}


class SettingsDialog(CharacterTabs, AppearanceTabs, ActivityTabs, IntegrationTabs, QDialog):
    """환경설정 창 — 고른 값은 [확인]/[적용]을 눌러야 반영되고 settings.json 에 저장됨"""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle(f"환경설정 — {APP_NAME}")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint)   # 항상 위 X (보고 있을 때만 펫보다 위)
        self.setMinimumWidth(640)
        self.setStyleSheet(settings_qss())
        tabs = QTabWidget()
        self.picks = {}
        self.group_btns = []
        self.group_scr = []
        self.outfit_box = {}
        # 탭 5개: 캐릭터 · 화면·움직임 · 알림·노래 · Claude · 업데이트 (예전 8개 탭을 묶음)
        etc_w = self.tab_etc()                 # AI 연결 탭 (여기서 만든 자동 실행·자리 비움 마중은 '화면·움직임'으로)
        parts = []
        if app.one_each and len(app.roster) >= 2:
            parts.append(("부를 친구", self.tab_chars()))
        if app.outfits:
            parts.append(("의상", self.tab_outfit()))
        if parts:
            tabs.addTab(self._stack(parts), "캐릭터")
        tabs.addTab(self._stack([("화면", self.tab_screen()), ("움직임", self.tab_play()),
                                 ("그 밖에", self.tab_more())]), "화면·움직임")
        tabs.addTab(self._stack([("알림 시각", self.tab_alarm()), ("노래 목록", self.tab_music())]), "알림·노래")
        self.tabs = tabs
        tabs.addTab(etc_w, "AI 연결")
        tabs.addTab(self._stack([("", self.tab_update()),
                                 ("", QLabel("설정은 프로그램 폴더의 settings.json 에 저장돼요."))]), "업데이트")
        # 탭 내용이 길어도 창이 모니터 밖으로 넘치지 않게 — 탭마다 스크롤 영역으로 감싸기
        from PyQt5.QtWidgets import QScrollArea, QFrame
        _nat = tabs.sizeHint()
        for _i in range(tabs.count()):
            _w = tabs.widget(_i)
            if isinstance(_w, QScrollArea):
                continue
            _t = tabs.tabText(_i)
            tabs.removeTab(_i)
            _sa = QScrollArea(); _sa.setWidgetResizable(True); _sa.setFrameShape(QFrame.NoFrame)
            _sa.setWidget(_w)
            tabs.insertTab(_i, _sa, _t)
        tabs.setCurrentIndex(0)
        ok, cancel, apply_ = QPushButton("확인"), QPushButton("취소"), QPushButton("적용")
        ok.setDefault(True)
        ok.clicked.connect(lambda: (self.apply(), self.close()))
        cancel.clicked.connect(self.close)
        apply_.clicked.connect(self.apply)
        bot = QHBoxLayout(); bot.addStretch(1)
        for bt in (ok, cancel, apply_):
            bot.addWidget(bt)
        lay = QVBoxLayout(self)
        _bn = os.path.join(BASE, "settings_banner.png")      # 위쪽 분홍 배너 (그림 파일이 있을 때만)
        if os.path.exists(_bn):
            self.banner = QLabel(); self.banner.setMinimumHeight(10)
            self.banner_pix = QPixmap(_bn)
            self.banner.setAlignment(Qt.AlignCenter)
            self.banner.setStyleSheet("border-radius:10px;")
            lay.addWidget(self.banner)
        lay.addLayout(self.search_bar(tabs))
        lay.addWidget(tabs); lay.addLayout(bot)
        self.adjustSize()
        cur = target_screen().availableGeometry()
        # 모니터 해상도·배율에 맞춰 창 크기를 화면 안으로 제한 (넘치는 부분은 스크롤)
        _w = min(max(self.width(), _nat.width() + 40), cur.width() - 40)
        _h = min(max(self.height(), _nat.height() + 90), cur.height() - 70)
        self.resize(_w, _h)
        self.move(max(cur.left() + 10, cur.center().x() - _w // 2), max(cur.top() + 30, cur.center().y() - _h // 2))

    # 움직임: 흔들림 · 자동 단체 놀이 · 말풍선
    def search_bar(self, tabs):
        """설정 검색: 글자(초성도 OK)로 항목을 찾아 그 탭으로 데려가고 반짝 표시"""
        from PyQt5.QtWidgets import QLineEdit, QListWidget, QListWidgetItem, QCheckBox, QRadioButton, QScrollArea
        box = QVBoxLayout()
        self.set_q = QLineEdit(); self.set_q.setClearButtonEnabled(True)
        self.set_q.setPlaceholderText("설정 찾기 — 예: 크기, 알림, 검색, Gemini, 자동 실행 (초성 ㅋㄱ 도 돼요)")
        self.set_res = QListWidget(); self.set_res.setMaximumHeight(170); self.set_res.hide()
        box.addWidget(self.set_q); box.addWidget(self.set_res)
        idx = []
        for i in range(tabs.count()):
            page, tname = tabs.widget(i), tabs.tabText(i)
            for w in page.findChildren(QWidget):
                if isinstance(w, QGroupBox):
                    t = w.title()
                elif isinstance(w, (QCheckBox, QRadioButton, QPushButton, QLabel)):
                    t = w.text()
                elif isinstance(w, QComboBox):
                    t = " / ".join(w.itemText(k) for k in range(w.count()))
                else:
                    continue
                t = re.sub(r"<[^>]+>", "", t or "").replace("&", "").strip()
                if len(t) < 2:
                    continue
                tip = (w.toolTip() or "").strip()
                if isinstance(w, QLabel) and w.buddy() is None and len(t) > 120:
                    t = t[:120]
                idx.append((i, tname, w, t, tip))
        def norm(x):
            return x.lower().replace(" ", "")
        def find(text):
            q = norm(text)
            self.set_res.clear()
            if not q:
                self.set_res.hide(); return
            cq = self._cho(q)
            n = 0
            for i, tname, w, t, tip in idx:
                if w.isHidden():
                    continue
                hay = norm(t + " " + tip + " " + tname)
                if q in hay or (all("ㄱ" <= ch <= "ㅎ" for ch in q) and cq in self._cho(hay)):
                    one = t.splitlines()[0]
                    it = QListWidgetItem(f"{tname}  ›  {one[:70]}" + ("…" if len(one) > 70 else ""))
                    it.setData(Qt.UserRole, (i, w))
                    self.set_res.addItem(it); n += 1
                    if n >= 40:
                        break
            if not n:
                self.set_res.addItem("찾는 설정이 없어요 — 다른 말로 찾아봐 주세요")
            self.set_res.show()
        def go(item):
            d = item.data(Qt.UserRole)
            if not d:
                return
            i, w = d
            tabs.setCurrentIndex(i)
            sa = tabs.widget(i)
            if isinstance(sa, QScrollArea):
                QTimer.singleShot(50, lambda: sa.ensureWidgetVisible(w, 40, 80))
            old = w.styleSheet()
            w.setStyleSheet(old + ";background:#ffe36e;border-radius:4px;")
            QTimer.singleShot(1800, lambda: w.setStyleSheet(old))
            try:
                w.setFocus()
            except Exception:
                pass
        self.set_q.textChanged.connect(find)
        self.set_q.returnPressed.connect(lambda: self.set_res.count() and go(self.set_res.item(0)))
        self.set_res.itemClicked.connect(go)
        self.set_res.itemActivated.connect(go)
        return box

    def _stack(self, parts):
        """여러 탭 내용을 제목 상자로 묶어 한 탭에 위아래로"""
        w = QWidget(); v = QVBoxLayout(w)
        for title, wid in parts:
            if wid is None:
                continue
            if title:
                g = QGroupBox(title); gl = QVBoxLayout(g); gl.setContentsMargins(8, 6, 8, 6)
                gl.addWidget(wid); v.addWidget(g)
            else:
                v.addWidget(wid)
        v.addStretch(1)
        return w

    def resizeEvent(self, e):
        super().resizeEvent(e)
        bn = getattr(self, "banner", None)
        if bn is None or self.banner_pix.isNull():
            return
        w = max(200, self.width() - 24)
        h = max(70, min(130, w // 5))
        src = self.banner_pix
        pic = src.scaledToHeight(h, Qt.SmoothTransformation)
        canvas = QPixmap(w, h)
        pa = QPainter(canvas)
        col = src.copy(int(src.width() * 0.3), 0, 1, src.height())       # 빈 하늘 한 줄을 늘려서 왼쪽을 채움
        pa.drawPixmap(0, 0, w, h, col)
        from PyQt5.QtGui import QLinearGradient, QColor
        fade = QPixmap(pic.size()); fade.fill(Qt.transparent)              # 그림 왼쪽 끝을 부드럽게 흐려서 이음매 없애기
        p2 = QPainter(fade); p2.drawPixmap(0, 0, pic)
        p2.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        g = QLinearGradient(0, 0, pic.width() * 0.4, 0)
        g.setColorAt(0, QColor(0, 0, 0, 0)); g.setColorAt(1, QColor(0, 0, 0, 255))
        p2.fillRect(fade.rect(), g); p2.end()
        pa.drawPixmap(w - pic.width(), 0, fade)                           # 그림은 오른쪽에 맞춤
        pa.end()
        bn.setPixmap(canvas)
        bn.setFixedHeight(h)

    def apply(self):
        app, cfg = self.app, self.app.cfg
        self.save_update_cfg()
        try:
            t = self.music_tbl
            lst = []
            for r in range(t.rowCount()):
                nm = (t.item(r, 0).text() if t.item(r, 0) else "").strip()
                u = (t.item(r, 1).text() if t.item(r, 1) else "").strip()
                if u.startswith("http") and u.rstrip("/") not in ("https://www.youtube.com", "https://youtube.com"):
                    old = next((x for x in app.music_list() if x.get("url") == u and x.get("songs")), None)
                    lst.append({"name": nm or f"노래 {len(lst) + 1}", "url": u, **({"songs": old["songs"]} if old else {})})
            cfg["music"] = lst
            cfg["music_dance"] = self.music_dance.isChecked()
            cfg["music_min"] = int(self.music_min.value())
            cfg["music_player"] = self.music_player.currentData() or "hidden"
        except Exception:
            pass
        # 그룹별 모니터
        moved = []
        for mem, mc in self.group_scr:
            want = mc.currentData() or ""
            for c in mem:
                if CHAR_SCREEN.get(c, "") != want:
                    moved.append(c)
                    if want:
                        CHAR_SCREEN[c] = want
                    else:
                        CHAR_SCREEN.pop(c, None)
        if moved:
            cfg["char_screen"] = dict(CHAR_SCREEN)
            if app.group:
                app.group_break()
            if app.scene:
                app.scene_end()
            app.scan()
            for i, b in enumerate([b for b in app.buddies if b.char in moved]):
                scr = b.scr()
                b.fx = float(random.uniform(scr.left() + 50, scr.right() - b.S - 50))
                b.fy = float(scr.top() - b.S - i * 40); b.vy = 0
                b.drop_rope(); b.fall(vx=0)
        # 캐릭터 (한 명도 안 고르면 그대로 둠)
        if self.picks:
            sel = [c for c in app.roster if self.picks[c].isChecked()]
            if not sel:
                self.pick_note.setText("한 명 이상 골라 주세요 (캐릭터는 그대로 뒀어요)")
                self.pick_set(app.team)
            elif set(sel) != set(app.team):
                self.pick_note.setText("")
                app.set_team(sel)
        # 의상
        for base, cb in self.outfit_box.items():
            app.set_outfit(base, cb.currentData())
        if getattr(self, "oauto", None) is not None:
            cfg["outfit_auto"] = self.oauto.isChecked()
        if getattr(self, "doro_mo", None) is not None and self.doro_mo.isChecked() != bool(cfg.get("doro_motion", False)):
            cfg["doro_motion"] = self.doro_mo.isChecked()
            if app.outfit.get("dorothy") == "doro":          # 지금 도로롱이면 바로 바꿔 입기
                app.apply_outfit("dorothy", "doro")
                for b in app.buddies:
                    if b.char == "dorothy":
                        b.update()
        # 움직임·알림·기타 (값만 바꾸면 되는 것들)
        app.set_shake(self.sh.currentData())
        if self.fps.currentData() != app.substeps:
            app.substeps = cfg["fps"] = self.fps.currentData()
            app.t.setInterval(TICK * app.substeps)
        cfg["auto_group"] = self.ag.isChecked()
        cfg["bubbles"] = self.bb.isChecked()
        if hasattr(self, "cav"):
            cfg["cursor_avoid"] = self.cav.isChecked()
        if hasattr(self, "wx_cb"):
            cfg["weather"] = self.wx_cb.isChecked()
        if self.bpx.currentData() != BUBBLE_PX["px"]:
            BUBBLE_PX["px"] = cfg["bubble_px"] = int(self.bpx.currentData())
            for b in app.buddies:                        # 지금 떠 있는 말풍선도 새 크기로
                if b.bubble:
                    old = b.bubble
                    b.bubble = Bubble(old.text, old.sticky, old.on_close)
                    old.on_close = None; old.close()
                    b.place_bubble(); b.bubble.show()
        app.climb_windows = cfg["climb"] = self.climb.isChecked()
        if self.ontop.isChecked() != app.on_top:
            app.set_on_top(self.ontop.isChecked())
        cfg["alarms"] = {k: te.time().toString("HH:mm") for k, (on, te) in self.al.items()
                         if te.time().toString("HH:mm") != ALARMS[k]}
        cfg["alarms_off"] = sorted(k for k, (on, te) in self.al.items() if not on.isChecked())
        cfg["ask_dbl"] = self.ask_dbl.isChecked()
        cfg["ask_where"] = self.ask_where.currentData()
        cfg["ask_mode"] = self.ask_mode.currentData()
        cfg["ask_engine"] = self.ask_engine.currentData() or "claude"
        cfg["gemini_key"] = self.gemini_key.text().strip()
        cfg["ask_control"] = self.ask_ctl.isChecked()
        cfg["ask_web"] = self.ask_web.isChecked()
        cfg["ask_power"] = self.ask_power.currentData() or "none"
        cfg["ask_screen"] = self.ask_screen.currentData() or "auto"
        cfg["ai_chat"] = self.ai_chat.isChecked()
        cfg["ai_chat_max"] = int(self.ai_chat_max.value())
        cfg["ai_chat_gap"] = int(self.ai_chat_gap.value())
        cfg["brief_on"] = self.brief_on.isChecked()
        cfg["brief_keys"] = [k.text().strip() for k in self.brief_keys if k.text().strip()][:5]
        bt = self.brief_time.text().strip()
        if re.fullmatch(r"\d{1,2}:\d{2}", bt) and int(bt.split(":")[0]) < 24 and int(bt.split(":")[1]) < 60:
            cfg["brief_time"] = f"{int(bt.split(':')[0]):02d}:{bt.split(':')[1]}"
        cfg["idle_welcome"] = self.idle_welcome.isChecked()
        cfg["idle_min"] = int(self.idle_min.value())
        cfg["ask_dirs"] = [self.ask_dirs.item(i).text() for i in range(self.ask_dirs.count())]
        if self.ask_room.currentData() != cfg.get("ask_room", "one"):
            cfg["ask_room"] = self.ask_room.currentData()
        if self.my_name.text().strip() != cfg.get("my_name", ""):
            cfg["my_name"] = self.my_name.text().strip()
            cfg.pop("ask_sessions", None)                 # 호칭이 바뀌면 대화를 새로 시작
        cfg["ask_send"] = self.ask_send.isChecked()
        if self.mcp_on.isChecked() != bool(cfg.get("mcp", True)):
            cfg["mcp"] = self.mcp_on.isChecked()
            app.start_bridge() if cfg["mcp"] else app.stop_bridge()
        if self.au.isChecked() != self.au_start:
            app.set_autostart(self.au.isChecked()); self.au_start = self.au.isChecked()
        # 크기
        if self.varied.isChecked() != bool(cfg.get("varied", False)):
            cfg["varied"] = self.varied.isChecked()
            for b in app.buddies:
                b.scale = random.uniform(0.8, 1.15) if cfg["varied"] else 1.0
            app.set_size(self.sl.value())
        elif self.sl.value() != app.size:
            app.set_size(self.sl.value())
        if hasattr(self, "cs_vals") and self.cs_vals != {k: int(v) for k, v in dict(cfg.get("char_scale") or {}).items()}:
            cfg["char_scale"] = dict(self.cs_vals)
            app.set_size(self.sl.value())
        if hasattr(self, "stay_cb"):
            _on = self.stay_cb.isChecked(); _side = self.stay_side.currentData()
            if _on and (not cfg.get("stay", False) or _side != cfg.get("stay_side", "right")):
                for b in app.buddies:
                    b._home = b.cx
            cfg["stay"] = _on; cfg["stay_side"] = _side; cfg["stay_x"] = self.stay_x.value()
            cfg["no_sky"] = self.nosky_cb.isChecked()
            if _on:
                for b in app.buddies:
                    b.goal = None
        if hasattr(self, "maxon_sp") and self.maxon_sp.value() != app.cap():
            cfg["max_on"] = self.maxon_sp.value()
            app.max_changed()
        if hasattr(self, "cp_cb"):
            cfg["cursor_play"] = self.cp_cb.isChecked()
            cfg["sys_react"] = self.sy_cb.isChecked()
            if self.slp_cb.isChecked() != bool(cfg.get("sleep_mode", False)):
                app.set_sleep(self.slp_cb.isChecked())
            if self.rst_cb.isChecked() != bool(cfg.get("rest_mode", False)):
                app.set_rest(self.rst_cb.isChecked())
        if hasattr(self, "ua_cb"):
            cfg["usage_alert"] = self.ua_cb.isChecked()
        app.save_cfg()
        # 모니터 (바뀌었을 때만 이사)
        i = self.mon.currentIndex()
        if i != self.mon_start and i < len(self.scs) and self.scs[i] in QApplication.screens():
            self.mon_start = i
            app.set_screen(self.scs[i])
