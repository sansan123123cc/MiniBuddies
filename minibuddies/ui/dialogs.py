"""Settings, history, and briefing windows."""

import datetime
import json
import os
import random
import re
from PyQt5.QtCore import QPoint, QTime, QTimer, Qt
from PyQt5.QtGui import QColor, QPainter, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)
from minibuddies.catalog import (
    AI_GUIDE,
    ALARMS,
    ALARM_NAME,
    APP_NAME,
    BUBBLE_PX,
    BUBBLE_SIZES,
    DORO_MOTION_DIR,
    FRANCHISE,
    MAX_COUNT,
    SHAKE,
    SHAKE_LEVELS,
    SIZES,
    SQUADS,
    SQUAD_NAME,
    TICK,
)
from minibuddies.desktop import CHAR_SCREEN, target_screen
from minibuddies.runtime import BASE, CHARS_DIR, MCP_HOME
from minibuddies.ui.widgets import Bubble
from minibuddies.updates import upd_load, upd_path, upd_save_cfg


def claude_hist_dir():
    return os.path.join(BASE, "claude_history")


def claude_hist_load():
    """claude_history/*.jsonl → 최신순 목록 (각 줄 = 한 번 주고받은 것)"""
    rows, d = [], claude_hist_dir()
    try:
        names = sorted(x for x in os.listdir(d) if x.endswith(".jsonl"))
    except Exception:
        names = []
    for n in names:
        try:
            with open(os.path.join(d, n), encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if not line.strip():
                        continue
                    try:
                        r = json.loads(line)
                    except Exception:
                        continue
                    r["_f"], r["_i"] = n, i
                    rows.append(r)
        except Exception:
            pass
    rows.sort(key=lambda r: str(r.get("t", "")), reverse=True)
    return rows


def claude_hist_delete(keys):
    """keys = {(파일 이름, 줄 번호)} 를 지우고 파일을 다시 씀"""
    by = {}
    for f, i in keys:
        by.setdefault(f, set()).add(i)
    for f, idx in by.items():
        p = os.path.join(claude_hist_dir(), f)
        try:
            with open(p, encoding="utf-8") as fh:
                lines = fh.readlines()
            keep = [l for i, l in enumerate(lines) if i not in idx]
            if any(l.strip() for l in keep):
                with open(p, "w", encoding="utf-8") as fh:
                    fh.writelines(keep)
            else:
                os.remove(p)
        except Exception:
            pass


class HistoryDialog(QDialog):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle(f"Claude 이력 관리 — {APP_NAME}")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
        self.resize(980, 620)
        self.setStyleSheet("QDialog{background:#fff7fb;} QPushButton{padding:4px 12px;}")
        v = QVBoxLayout(self)
        top = QHBoxLayout()
        self.q = QLineEdit(); self.q.setPlaceholderText("검색 (보낸 말·받은 답·캐릭터 이름)")
        self.kind = QComboBox(); self.day = QComboBox(); self.cnt = QLabel("")
        b_ref = QPushButton("새로고침"); b_dir = QPushButton("폴더 열기")
        for w in (self.q, self.kind, self.day, self.cnt, b_ref, b_dir):
            top.addWidget(w)
        top.setStretch(0, 1)
        v.addLayout(top)
        sp = QSplitter(Qt.Horizontal)
        self.lst = QListWidget(); self.lst.setSelectionMode(QListWidget.ExtendedSelection)
        self.view = QTextBrowser(); self.view.setOpenExternalLinks(True)
        sp.addWidget(self.lst); sp.addWidget(self.view); sp.setSizes([360, 620])
        v.addWidget(sp, 1)
        bot = QHBoxLayout()
        self.onoff = QCheckBox("이력 남기기"); self.onoff.setChecked(bool(app.cfg.get("claude_history", True)))
        b_ci = QPushButton("보낸 말 복사"); b_co = QPushButton("받은 답 복사")
        b_md = QPushButton(".md로 내보내기"); b_del = QPushButton("고른 것 삭제"); b_all = QPushButton("보이는 것 전부 삭제")
        bot.addWidget(self.onoff); bot.addStretch(1)
        for w in (b_ci, b_co, b_md, b_del, b_all):
            bot.addWidget(w)
        v.addLayout(bot)
        self.q.textChanged.connect(self.fill)
        self.kind.currentIndexChanged.connect(self.fill)
        self.day.currentIndexChanged.connect(self.fill)
        b_ref.clicked.connect(self.reload)
        b_dir.clicked.connect(app.open_claude_history_dir)
        self.lst.currentRowChanged.connect(self.show_row)
        b_ci.clicked.connect(lambda: self.copy("q"))
        b_co.clicked.connect(lambda: self.copy("out"))
        b_md.clicked.connect(self.export_md)
        b_del.clicked.connect(self.del_sel)
        b_all.clicked.connect(self.del_all)
        self.onoff.toggled.connect(self.toggle_on)
        self.rows, self.shown = [], []
        self.reload()

    def reload(self):
        self.rows = claude_hist_load()
        kinds = sorted({str(r.get("kind", "")) for r in self.rows if r.get("kind")})
        days = sorted({str(r.get("t", ""))[:10] for r in self.rows if r.get("t")}, reverse=True)
        for box, items, first in ((self.kind, kinds, "종류 전체"), (self.day, days, "날짜 전체")):
            cur = box.currentText()
            box.blockSignals(True); box.clear(); box.addItem(first); box.addItems(items)
            i = box.findText(cur)
            box.setCurrentIndex(i if i >= 0 else 0); box.blockSignals(False)
        self.fill()

    def fill(self, *_):
        s = self.q.text().strip().lower()
        k = self.kind.currentText() if self.kind.currentIndex() > 0 else ""
        dd = self.day.currentText() if self.day.currentIndex() > 0 else ""
        self.shown = [r for r in self.rows
                      if (not k or r.get("kind") == k) and (not dd or str(r.get("t", "")).startswith(dd))
                      and (not s or s in (str(r.get("q", "")) + "\n" + str(r.get("out", "")) + "\n" + str(r.get("who", ""))).lower())]
        self.lst.blockSignals(True); self.lst.clear()
        for r in self.shown:
            t = str(r.get("t", ""))
            first = " ".join(str(r.get("q", "")).split())[:40]
            it = QListWidgetItem(f"{t[5:16].replace('T', ' ')}  [{r.get('kind', '')}] {r.get('who', '')}\n    {first}")
            if r.get("err"):
                it.setForeground(QColor(200, 60, 60))
            self.lst.addItem(it)
        self.lst.blockSignals(False)
        self.cnt.setText(f"{len(self.shown)} / {len(self.rows)}건")
        if self.shown:
            self.lst.setCurrentRow(0); self.show_row(0)
        else:
            self.view.setHtml("<p style='color:#999'>남은 이력이 없어요.</p>")

    def show_row(self, i):
        if not (0 <= i < len(self.shown)):
            return
        import html as _h
        r = self.shown[i]
        e = lambda x: _h.escape(str(x or "")).replace("\n", "<br>")
        err = f"<p style='color:#c33'><b>오류:</b> {e(r.get('err'))}</p>" if r.get("err") else ""
        self.view.setHtml(
            f"<p style='color:#888'>{e(str(r.get('t', '')).replace('T', ' '))} · {e(r.get('kind'))} · {e(r.get('who'))}</p>"
            f"<h3 style='color:#c2185b'>보낸 말 (인풋)</h3><p>{e(r.get('q')) or '(없음)'}</p>"
            f"<h3 style='color:#1565c0'>받은 답 (아웃풋)</h3><p>{e(r.get('out')) or '(없음)'}</p>{err}")

    def sel_rows(self):
        idx = sorted({m.row() for m in self.lst.selectedIndexes()})
        return [self.shown[i] for i in idx if i < len(self.shown)]

    def copy(self, key):
        rs = self.sel_rows()
        if rs:
            QApplication.clipboard().setText("\n\n---\n\n".join(str(r.get(key, "")) for r in rs))

    def export_md(self):
        rs = self.sel_rows() or self.shown
        if not rs:
            return
        p = os.path.join(claude_hist_dir(), f"내보내기_{datetime.datetime.now():%Y%m%d_%H%M%S}.md")
        try:
            with open(p, "w", encoding="utf-8") as f:
                for r in rs:
                    f.write(f"## {r.get('t', '')} · {r.get('kind', '')} · {r.get('who', '')}\n\n### 인풋\n{r.get('q', '')}\n\n"
                            f"### 아웃풋\n{r.get('out', '')}\n\n" + (f"> 오류: {r.get('err')}\n\n" if r.get("err") else ""))
            os.startfile(p)
        except Exception:
            pass

    def _ask(self, msg):
        return QMessageBox(QMessageBox.Question, "Claude 이력", msg, QMessageBox.Yes | QMessageBox.No, self).exec_() == QMessageBox.Yes

    def del_sel(self):
        rs = self.sel_rows()
        if rs and self._ask(f"고른 이력 {len(rs)}건을 지울까요?"):
            claude_hist_delete({(r["_f"], r["_i"]) for r in rs})
            self.reload()

    def del_all(self):
        if self.shown and self._ask(f"지금 목록에 보이는 이력 {len(self.shown)}건을 전부 지울까요?"):
            claude_hist_delete({(r["_f"], r["_i"]) for r in self.shown})
            self.reload()

    def toggle_on(self, on):
        self.app.cfg["claude_history"] = bool(on)
        self.app.save_cfg()

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


class SettingsDialog(QDialog):
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

    # 캐릭터: 등장시킬 멤버 고르기 (그룹별 체크)
    def tab_chars(self):
        """캐릭터 고르기 — 위 검색칸(초성 가능) + 왼쪽 작품 목록(고른 수) + 오른쪽 작품별·그룹별 체크"""
        from PyQt5.QtWidgets import QScrollArea, QLineEdit, QListWidget
        w = QWidget(); lay = QVBoxLayout(w)
        szbox = QGroupBox("크기"); sf = QFormLayout(szbox)
        self.size_form(sf)
        lay.addWidget(szbox)

        top = QHBoxLayout()
        self.pick_search = QLineEdit()
        self.pick_search.setPlaceholderText("🔍 이름·작품·그룹으로 찾기  (초성도 돼요: ㅎㄹㄹㅇㅂ)")
        self.pick_search.setClearButtonEnabled(True)
        self.pick_search.setStyleSheet("QLineEdit{padding:6px 8px;border:1px solid #f0bcd6;border-radius:8px;background:#fff;}")
        self.pick_search.textChanged.connect(lambda _=None: self.pick_filter())
        top.addWidget(self.pick_search, 1)
        self.pick_only = QCheckBox("고른 친구만")
        self.pick_only.toggled.connect(lambda _=False: self.pick_filter())
        top.addWidget(self.pick_only)
        for lab, fn in [("전체 선택", lambda: self.pick_set(self.app.roster)), ("전체 해제", lambda: self.pick_set([]))]:
            bt = QPushButton(lab); bt.clicked.connect(fn); top.addWidget(bt)
        lay.addLayout(top)
        self.pick_count = QLabel("")
        self.pick_count.setStyleSheet("color:#8a5a75;padding:2px 2px 4px 2px;")
        lay.addWidget(self.pick_count)

        fr = []
        used = set()
        for fname, sqs in FRANCHISE:
            sqs = [sq for sq in sqs if any(c in self.app.roster for c in SQUADS.get(sq, []))]
            if sqs:
                fr.append((fname, sqs)); used.update(sqs)
        rest_sq = [sq for sq in SQUADS if sq not in used and any(c in self.app.roster for c in SQUADS[sq])]
        if rest_sq:
            fr.append(("그 밖의 작품", rest_sq))
        loose = [c for c in self.app.roster if not any(c in SQUADS[sq] for _, sqs in fr for sq in sqs)]
        if loose:
            fr.append(("그 밖의 친구들", [None]))

        body = QHBoxLayout()
        self.fr_list = QListWidget()
        self.fr_list.setFixedWidth(200)
        self.fr_list.setStyleSheet(
            "QListWidget{background:#fff;border:1px solid #f0c8dc;border-radius:8px;outline:0;}"
            "QListWidget::item{padding:7px 8px;border-radius:6px;}"
            "QListWidget::item:selected{background:#ffd6ea;color:#7a2350;}"
            "QListWidget::item:hover{background:#fff0f7;}")
        body.addWidget(self.fr_list)
        page = QWidget(); pl = QVBoxLayout(page)
        self.fr_sections = []                      # [이름, 제목, [(상자, 격자, 멤버, 체크들, 모니터칸)], 목록 항목]
        for fname, sqs in fr:
            head = QLabel(fname)
            head.setStyleSheet("font-size:15px;font-weight:bold;color:#c8467e;padding:10px 2px 2px 2px;")
            pl.addWidget(head)
            boxes = []
            for sq in sqs:
                mem = loose if sq is None else [c for c in SQUADS[sq] if c in self.app.roster]
                if not mem:
                    continue
                box = QGroupBox(SQUAD_NAME.get(sq, "그 밖의 친구들"))
                g = QGridLayout(box)
                only = QPushButton("모두 선택")                 # 누를 때마다 이 그룹 모두 선택 ↔ 모두 해제
                only.setMaximumWidth(120)
                only.clicked.connect(lambda _=False, mem=mem: self.group_toggle(mem))
                self.group_btns.append((mem, only))
                g.addWidget(only, 0, 3)
                mc = None
                if len(QApplication.screens()) > 1:            # 모니터가 여럿이면 그룹마다 띄울 모니터
                    mc = QComboBox()
                    mc.addItem("모니터: 기본(화면 탭 설정)", "")
                    for i, sc in enumerate(QApplication.screens()):
                        gg = sc.geometry()
                        mc.addItem(f"모니터 {i + 1}" + (" (주)" if sc is QApplication.primaryScreen() else "")
                                   + f" {gg.width()}x{gg.height()}", sc.name())
                    mc.setCurrentIndex(max(0, mc.findData(CHAR_SCREEN.get(mem[0], ""))))
                    self.group_scr.append((mem, mc))
                    g.addWidget(mc, 1000, 0, 1, 4)
                cbs = []
                for n, c in enumerate(mem):
                    lab = self.app.chars[c]["label"]
                    if c in self.app.outfits and len(self.app.outfits[c]) > 1:
                        lab += f" ({len(self.app.outfits[c])}가지 모습)"
                    cb = QCheckBox(lab); cb.setChecked(c in self.app.team)
                    cb.toggled.connect(lambda _=False: self.group_labels())
                    cb._key = " ".join([lab, c, SQUAD_NAME.get(sq, "") if sq else "", fname]).lower()
                    self.picks[c] = cb
                    g.addWidget(cb, n // 3, n % 3)
                    cbs.append((c, cb))
                pl.addWidget(box)
                boxes.append((box, g, mem, cbs, mc))
            self.fr_list.addItem(fname)
            self.fr_sections.append([fname, head, boxes, self.fr_list.item(self.fr_list.count() - 1)])
        self.pick_none = QLabel("찾는 친구가 없어요. 이름 일부나 초성으로도 찾아 보세요.")
        self.pick_none.setStyleSheet("color:#a07890;padding:20px;")
        self.pick_none.hide()
        pl.addWidget(self.pick_none)
        pl.addStretch(1)
        self.pick_scroll = QScrollArea(); self.pick_scroll.setWidgetResizable(True); self.pick_scroll.setWidget(page)
        self.pick_scroll.setMinimumHeight(340)
        body.addWidget(self.pick_scroll, 1)
        lay.addLayout(body, 1)
        self.fr_list.itemClicked.connect(lambda it: self.pick_jump(it))
        # 왼쪽에서 고른 작품만 오른쪽에 보이기 (검색하거나 '고른 친구만'을 켜면 모든 작품에서 찾기)
        self.pick_fr = self.fr_sections[0][0] if self.fr_sections else None
        if self.fr_sections:
            self.fr_list.setCurrentItem(self.fr_sections[0][3])
        self.pick_filter()
        self.pick_note = QLabel("처음 켤 때는 엘리시아만 나와요. 여기서 고르면 다음에 켤 때도 그대로예요.")
        self.pick_note.setWordWrap(True)
        lay.addWidget(self.pick_note)
        return w

    @staticmethod
    def _cho(s):
        """한글 → 초성 (검색에서 'ㅎㄹ' 로 '홀로라이브' 찾기)"""
        t = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
        return "".join(t[(ord(ch) - 0xAC00) // 588] if "가" <= ch <= "힣" else ch for ch in s)

    def pick_filter(self):
        """검색어·'고른 친구만' 에 맞는 캐릭터만 보이게 — 격자를 다시 채워서 빈칸 없이"""
        q = self.pick_search.text().strip().lower().replace(" ", "")
        only = self.pick_only.isChecked()
        any_vis = False
        for sec in self.fr_sections:
            fname, head, boxes, item = sec
            fr_ok = bool(q or only) or getattr(self, "pick_fr", None) in (None, fname)
            sec_vis = False
            sec_any = False
            for box, g, mem, cbs, mc in boxes:
                for c, cb in cbs:
                    g.removeWidget(cb)
                n = 0
                for c, cb in cbs:
                    k = cb._key.replace(" ", "")
                    ok = (not q or q in k or q in self._cho(k)) and (not only or cb.isChecked())
                    sec_any = sec_any or ok
                    ok = ok and fr_ok
                    cb.setVisible(ok)
                    if ok:
                        g.addWidget(cb, n // 3, n % 3); n += 1
                box.setVisible(n > 0)
                sec_vis = sec_vis or n > 0
            head.setVisible(sec_vis)
            item.setHidden(not sec_any)
            any_vis = any_vis or sec_vis
        self.pick_none.setVisible(not any_vis)
        self.pick_scroll.verticalScrollBar().setValue(0)
        self.group_labels()

    def pick_jump(self, item):
        """왼쪽 작품 이름 누르면 오른쪽엔 그 작품만 보이게 (검색어·'고른 친구만'은 풀고)"""
        for fname, head, boxes, it in self.fr_sections:
            if it is item:
                self.pick_fr = fname
                for wdg, fn in ((self.pick_search, lambda: self.pick_search.clear()),
                                (self.pick_only, lambda: self.pick_only.setChecked(False))):
                    wdg.blockSignals(True); fn(); wdg.blockSignals(False)
                self.pick_filter()
                return

    def pick_follow(self, v):
        """스크롤하면 왼쪽 목록에서 지금 보고 있는 작품을 표시"""
        cur = None
        for fname, head, boxes, it in self.fr_sections:
            if head.isVisible() and head.y() <= v + 40:
                cur = it
        if cur is None:
            return
        self.fr_list.blockSignals(True)
        self.fr_list.setCurrentItem(cur)
        self.fr_list.blockSignals(False)

    # 의상: 캐릭터별 옷 고르기 + 알아서 갈아입기
    def tab_outfit(self):
        w = QWidget(); f = QFormLayout(w)
        # 캐릭터별 옷 고르기는 우클릭 메뉴 '옷 갈아입기'로 (여기엔 켜고 끄는 것만)
        on = QLabel("옷은 캐릭터를 우클릭 → '옷 갈아입기'에서 골라요."); on.setWordWrap(True); on.setStyleSheet("color:#9a8592;")
        f.addRow("", on)
        self.oauto = QCheckBox("가끔(12~25분마다) 알아서 옷 갈아입기")
        self.oauto.setChecked(self.app.cfg.get("outfit_auto", True))
        f.addRow("", self.oauto)
        self.doro_mo = None
        if "dorothy" in self.app.outfits and os.path.exists(os.path.join(CHARS_DIR, DORO_MOTION_DIR, "0.png")):
            self.doro_mo = QCheckBox("도로롱 모션 버전 쓰기")
            self.doro_mo.setChecked(bool(self.app.cfg.get("doro_motion", False)))
            self.doro_mo.toggled.connect(self.doro_motion_warn)
            f.addRow("", self.doro_mo)
            dn = QLabel("동작이 훨씬 많지만 생김새가 원본과 달라요."); dn.setWordWrap(True); dn.setStyleSheet("color:#887;")
            f.addRow("", dn)
        return w

    def doro_motion_warn(self, on):
        if not on:
            return
        from PyQt5.QtWidgets import QMessageBox
        r = QMessageBox.question(self, "도로롱 모션 버전",
                                 "모션 버전 도로롱은 원래 도로롱과 모습이 많이 달라요!\n"
                                 "(머리가 훨씬 크고, 강아지처럼 네 발로 걸어 다니는 모습이에요)\n\n"
                                 "대신 걷기·매달리기·개성 동작·사격 같은 움직임이 훨씬 많아요.\n그래도 바꿀까요?",
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes:
            self.doro_mo.blockSignals(True); self.doro_mo.setChecked(False); self.doro_mo.blockSignals(False)

    def pick_set(self, which):
        for c, cb in self.picks.items():
            cb.setChecked(c in which)

    def group_toggle(self, mem):
        """그룹 버튼: 다 켜져 있으면 그 그룹만 모두 끄고, 아니면 그 그룹만 모두 켬 (다른 그룹은 그대로)"""
        on = not all(self.picks[c].isChecked() for c in mem if c in self.picks)
        for c in mem:
            if c in self.picks:
                self.picks[c].setChecked(on)
        self.group_labels()

    def group_labels(self):
        for mem, bt in getattr(self, "group_btns", []):
            full = all(self.picks[c].isChecked() for c in mem if c in self.picks)
            bt.setText("모두 해제" if full else "모두 선택")
        # 왼쪽 작품 목록에 '고른 수/전체', 위에 전체 고른 수
        for fname, head, boxes, item in getattr(self, "fr_sections", []):
            cs = [cb for box, g, mem, cbs, mc in boxes for c, cb in cbs]
            on = sum(cb.isChecked() for cb in cs)
            item.setText(f"{fname}   {on}/{len(cs)}")
            head.setText(f"{fname}  ·  {on}/{len(cs)}")
        if hasattr(self, "pick_count"):
            on = sum(cb.isChecked() for cb in self.picks.values())
            self.pick_count.setText(f"고른 친구 {on}명  ·  전체 {len(self.picks)}명")

    # 화면: 모니터 · 크기 · 창 위 올라가기
    def tab_screen(self):
        w = QWidget(); f = QFormLayout(w)
        self.scs = list(QApplication.screens())
        self.mon = QComboBox()
        cur = target_screen()
        for i, sc in enumerate(self.scs):
            g = sc.geometry()
            self.mon.addItem(f"모니터 {i + 1}" + (" (주 모니터)" if sc is QApplication.primaryScreen() else "")
                             + f"   {g.width()}x{g.height()}")
        self.mon_start = next((i for i, sc in enumerate(self.scs) if sc is cur), 0)
        self.mon.setCurrentIndex(self.mon_start)
        self.mon.setEnabled(len(self.scs) > 1)
        f.addRow("띄울 모니터", self.mon)
        if len(self.scs) <= 1:
            f.addRow("", QLabel("(모니터가 하나라서 고를 게 없어요)"))
        if not getattr(self, "_sizes_done", False):      # 캐릭터 탭이 없으면(단독 버전) 크기는 여기
            self.size_form(f)
        # 흔들림·화면 그리기 (움직임 탭에서 옮겨 옴)
        self.sh = QComboBox()
        for lab, kv in SHAKE_LEVELS:
            self.sh.addItem(lab, kv)
        self.sh.setCurrentIndex(min(range(len(SHAKE_LEVELS)), key=lambda i: abs(SHAKE_LEVELS[i][1] - SHAKE["k"])))
        f.addRow("합동 장면 흔들림", self.sh)
        self.fps = QComboBox()
        for lab, v in [("부드럽게 (초당 60번, 기본)", 1), ("보통 (초당 30번, 컴퓨터가 버거울 때)", 2), ("가볍게 (초당 20번, 많이 버거울 때)", 3)]:
            self.fps.addItem(lab, v)
        self.fps.setCurrentIndex(max(0, self.fps.findData(self.app.substeps)))
        f.addRow("화면 그리기", self.fps)
        self.climb = QCheckBox("창 위에 올라가서 놀기"); self.climb.setChecked(self.app.climb_windows)
        f.addRow("", self.climb)
        self.ontop = QCheckBox("항상 위에 두기")
        self.ontop.setChecked(self.app.on_top)
        f.addRow("", self.ontop)
        note = QLabel("다른 창·전체화면 위에도 보여요. 끄면 창 뒤로 숨어요.")
        note.setWordWrap(True); note.setStyleSheet("color:#887;")
        f.addRow("", note)
        return w

    def size_form(self, f):
        """캐릭터 크기 · 말풍선 글자 크기 (합본은 캐릭터 탭 맨 위, 단독은 화면 탭)"""
        self._sizes_done = True
        # 크기: 미리 정한 크기 + 슬라이더로 세밀하게
        self.sz = QComboBox()
        for lab, v in SIZES:
            self.sz.addItem(f"{lab} ({v})", v)
        self.sz.addItem("직접 지정", 0)
        self.sl = QSlider(Qt.Horizontal); self.sl.setRange(48, 800); self.sl.setSingleStep(4); self.sl.setPageStep(20)
        self.sl_lab = QLabel()
        self.sl_lab.setMinimumWidth(48)
        self.sz.activated.connect(lambda i: self.sz.itemData(i) and self.sl.setValue(self.sz.itemData(i)))
        self.sl.valueChanged.connect(self.size_moved)
        self.sl.setValue(self.app.size); self.size_moved(self.app.size)
        row = QHBoxLayout(); row.addWidget(self.sl, 1); row.addWidget(self.sl_lab)
        f.addRow("캐릭터 크기", self.sz)
        f.addRow("", row)
        self.varied = QCheckBox("아이마다 크기 살짝 다르게"); self.varied.setChecked(bool(self.app.cfg.get("varied", False)))
        f.addRow("", self.varied)
        # 캐릭터별 크기: 고른 캐릭터만 기본 크기의 50~200%로
        from PyQt5.QtWidgets import QSpinBox
        self.cs_vals = {k: int(v) for k, v in dict(self.app.cfg.get("char_scale") or {}).items()}
        self.cs_pick = QComboBox()
        for _nm in sorted([n for n in self.app.chars if "@" not in n], key=lambda n: self.app.chars[n].get("label", n)):
            self.cs_pick.addItem(self.app.chars[_nm].get("label", _nm), _nm)
        self.cs_spin = QSpinBox(); self.cs_spin.setRange(50, 300); self.cs_spin.setSingleStep(5); self.cs_spin.setSuffix(" %")

        def _cs_load(_i=None):
            self.cs_spin.blockSignals(True)
            self.cs_spin.setValue(int(self.cs_vals.get(self.cs_pick.currentData(), 100)))
            self.cs_spin.blockSignals(False)

        def _cs_set(v):
            k = self.cs_pick.currentData()
            if k is None:
                return
            if int(v) == 100:
                self.cs_vals.pop(k, None)
            else:
                self.cs_vals[k] = int(v)
        self.cs_pick.currentIndexChanged.connect(_cs_load)
        self.cs_spin.valueChanged.connect(_cs_set)
        _cs_load()
        _cs_reset = QPushButton("모두 100%")
        _cs_reset.clicked.connect(lambda: (self.cs_vals.clear(), _cs_load()))
        _row2 = QHBoxLayout(); _row2.addWidget(self.cs_pick, 1); _row2.addWidget(self.cs_spin); _row2.addWidget(_cs_reset)
        f.addRow("캐릭터별 크기", _row2)
        self.bpx = QComboBox()
        for lab, v in BUBBLE_SIZES:
            self.bpx.addItem(f"{lab} ({v}px)", v)
        i = self.bpx.findData(BUBBLE_PX["px"])
        if i < 0:
            self.bpx.addItem(f"직접 지정 ({BUBBLE_PX['px']}px)", BUBBLE_PX["px"]); i = self.bpx.count() - 1
        self.bpx.setCurrentIndex(i)
        f.addRow("말풍선 글자 크기", self.bpx)

    def size_moved(self, v):
        self.sl_lab.setText(f"{v}px")
        i = self.sz.findData(v)
        self.sz.setCurrentIndex(i if i >= 0 else self.sz.count() - 1)

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

    def tab_more(self):
        """예전 우클릭에 있던 켜고 끄기 + 자동 실행 + 자리 비움 마중"""
        w = QWidget(); v = QVBoxLayout(w)
        v.addWidget(self.au)
        self.cp_cb = QCheckBox("커서랑 놀기 (쫓아오기·어지러움)")
        self.cp_cb.setChecked(self.app.cfg.get("cursor_play", True))
        self.sy_cb = QCheckBox("컴퓨터 상태에 반응 (배터리·인터넷·늦은 밤)")
        self.sy_cb.setChecked(self.app.cfg.get("sys_react", True))
        self.slp_cb = QCheckBox("수면 모드 (구석에서 자기)")
        self.slp_cb.setChecked(bool(self.app.cfg.get("sleep_mode", False)))
        self.rst_cb = QCheckBox("제자리 모드 (그 자리에서 책·게임·뒹굴)")
        self.rst_cb.setChecked(bool(self.app.cfg.get("rest_mode", False)))
        for cb in (self.cp_cb, self.sy_cb, self.slp_cb, self.rst_cb):
            v.addWidget(cb)
        if getattr(self, "iwg_box", None) is not None:
            v.addWidget(self.iwg_box)
        return w

    def tab_play(self):
        w = QWidget(); f = QFormLayout(w)
        self.ag = QCheckBox("내버려 둬도 알아서 단체 놀이·합동 장면"); self.ag.setChecked(self.app.cfg.get("auto_group", True))
        f.addRow("", self.ag)
        self.bb = QCheckBox("말풍선 보이기"); self.bb.setChecked(self.app.cfg.get("bubbles", True))
        f.addRow("", self.bb)
        self.cav = QCheckBox("마우스 커서 피해 다니기 (Ctrl 누른 채 머리에 올리면 쓰담쓰담)")
        self.cav.setChecked(self.app.cfg.get("cursor_avoid", True))
        f.addRow("", self.cav)
        self.wx_cb = QCheckBox("날씨 따라 행동하기 (인터넷 위치로 지금 날씨 확인 — 비 오면 우산, 눈 오면 눈싸움…)")
        self.wx_cb.setChecked(self.app.cfg.get("weather", True))
        f.addRow("", self.wx_cb)
        # 한 자리에 있기: 돌아다니지 않고 한쪽에 모여서 대기
        self.stay_cb = QCheckBox("한 자리에 있기 (돌아다니지 않고 한쪽에 모여서 대기)")
        self.stay_cb.setChecked(bool(self.app.cfg.get("stay", False)))
        self.stay_side = QComboBox()
        for _lab, _v in (("화면 오른쪽 아래", "right"), ("화면 왼쪽 아래", "left"), ("화면 가운데 아래", "center"),
                         ("직접 지정 (가로 위치 %)", "custom"), ("지금 있는 자리", "here")):
            self.stay_side.addItem(_lab, _v)
        self.stay_side.setCurrentIndex(max(0, self.stay_side.findData(self.app.cfg.get("stay_side", "right"))))
        f.addRow("", self.stay_cb)
        f.addRow("대기 위치", self.stay_side)
        self.stay_x = QSpinBox(); self.stay_x.setRange(0, 100); self.stay_x.setSuffix(" %")
        self.stay_x.setValue(int(self.app.cfg.get("stay_x", 80)))
        self.stay_x.setToolTip("0% = 화면 왼쪽 끝, 50% = 가운데, 100% = 오른쪽 끝")
        self.stay_x.setEnabled(self.stay_side.currentData() == "custom")
        self.stay_side.currentIndexChanged.connect(lambda *_: self.stay_x.setEnabled(self.stay_side.currentData() == "custom"))
        f.addRow("직접 지정 위치", self.stay_x)
        self.nosky_cb = QCheckBox("하늘로 안 올라가기 (풍선 타고 날아가지 않고 땅굴로만 나가기)")
        self.nosky_cb.setChecked(bool(self.app.cfg.get("no_sky", False)))
        f.addRow("", self.nosky_cb)
        self.maxon_sp = QSpinBox(); self.maxon_sp.setRange(1, MAX_COUNT); self.maxon_sp.setSuffix(" 명")
        self.maxon_sp.setValue(self.app.cap())
        self.maxon_sp.setToolTip("화면에 한 번에 나와 있는 최대 인원. 이보다 많이 골라 두면 8분마다 한 명씩 교대해요")
        f.addRow("화면 최대 등장 인원", self.maxon_sp)
        return w

    # 알림: 시각 · 켜고 끄기 · 미리 보기(미리 보기는 바로 실행)
    def tab_alarm(self):
        w = QWidget(); grid = QGridLayout(w)
        alarms = dict(ALARMS); alarms.update(self.app.cfg.get("alarms", {}))
        off = set(self.app.cfg.get("alarms_off", []))
        self.al = {}
        for r, key in enumerate(ALARMS):
            on = QCheckBox(ALARM_NAME[key]); on.setChecked(key not in off)
            te = QTimeEdit(QTime.fromString(alarms[key], "HH:mm")); te.setDisplayFormat("HH:mm")
            pv = QPushButton("미리 보기"); pv.clicked.connect(lambda _=False, key=key: self.app.alarm(key))
            grid.addWidget(on, r, 0); grid.addWidget(te, r, 1); grid.addWidget(pv, r, 2)
            self.al[key] = (on, te)
        grid.setRowStretch(len(ALARMS), 1)
        return w

    # 노래: 유튜브 링크 목록 (재생목록 링크도 OK)
    def tab_music(self):
        from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox
        w = QWidget(); v = QVBoxLayout(w)
        v.addWidget(QLabel("유튜브 링크(재생목록 링크도 돼요)를 넣어 두면 우클릭 → '노래 틀기 ♪'로 틀 수 있어요.\n"
                           "노래는 기본 브라우저에서 나오고, 그동안 친구들이 춤추며 흥얼거려요."))
        t = QTableWidget(0, 2); t.setHorizontalHeaderLabels(["이름", "유튜브 링크"])
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for it in self.app.music_list():
            r = t.rowCount(); t.insertRow(r)
            t.setItem(r, 0, QTableWidgetItem(it.get("name", ""))); t.setItem(r, 1, QTableWidgetItem(it.get("url", "")))
        self.music_tbl = t
        v.addWidget(t)
        row = QHBoxLayout()
        add, rm, play = QPushButton("추가"), QPushButton("선택 삭제"), QPushButton("선택한 노래 틀기")
        def _add():
            r = t.rowCount(); t.insertRow(r)
            t.setItem(r, 0, QTableWidgetItem(f"노래 {r + 1}")); t.setItem(r, 1, QTableWidgetItem("https://www.youtube.com/"))
            t.editItem(t.item(r, 1))
        add.clicked.connect(_add)
        rm.clicked.connect(lambda: [t.removeRow(r) for r in sorted({i.row() for i in t.selectedIndexes()}, reverse=True)])
        def _play():
            r = t.currentRow()
            if r >= 0 and t.item(r, 1):
                self.app.play_music({"name": t.item(r, 0).text() if t.item(r, 0) else "노래", "url": t.item(r, 1).text().strip()})
        play.clicked.connect(_play)
        for b in (add, rm, play):
            row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)
        f = QFormLayout()
        self.music_dance = QCheckBox("노래 트는 동안 다 같이 춤추고 흥얼거리기")
        self.music_dance.setChecked(self.app.cfg.get("music_dance", True))
        f.addRow("", self.music_dance)
        self.music_player = QComboBox()
        self.music_player.addItem("숨김 플레이어 (창 안 뜨고 소리만, 크롬·엣지 필요)", "hidden")
        self.music_player.addItem("작은 플레이어 창 (화면 오른쪽 아래)", "mini")
        self.music_player.addItem("평소 쓰는 브라우저로 열기", "browser")
        self.music_player.setCurrentIndex(max(0, self.music_player.findData(self.app.cfg.get("music_player", "hidden"))))
        f.addRow("재생 방식", self.music_player)
        self.music_min = QSpinBox(); self.music_min.setRange(5, 600); self.music_min.setSuffix(" 분")
        self.music_min.setValue(int(self.app.cfg.get("music_min", 60)))
        f.addRow("노래 모드 유지 시간", self.music_min)
        v.addLayout(f)
        note = QLabel("※ 유튜브 영상을 내려받지 않고 유튜브에서 바로 재생해요. 멈출 땐 우클릭 → 노래 틀기 ♪ → 노래 끄기.\n"
                      "※ 숨김 플레이어는 따로 쓰는 프로필이라 광고가 나올 수 있어요. '플레이어 창 보기'에서 유튜브에 한 번 로그인해 두면 그대로 유지돼요.\n"
                      "※ 캐릭터에게 '비 오는 날 듣기 좋은 노래 10곡 틀어 줘'처럼 부탁하면 찾아서 목록에 저장하고 틀어 줘요 (AI 연결 탭의 인터넷 검색 허용 필요).")
        note.setWordWrap(True)
        v.addWidget(note)
        return w

    # 기타: 자동 실행
    def tab_etc(self):
        w = QWidget(); f = QFormLayout(w)
        self.au_start = self.app.autostart_on()
        self.au = QCheckBox("윈도우 켤 때 자동 실행"); self.au.setChecked(self.au_start)   # → '화면·움직임' 탭에 붙임
        later = []                             # 물어보기와 따로 보여 줄 Claude 묶음 (수다·브리핑)
        ask = QGroupBox("캐릭터에게 물어보기")
        ag = QVBoxLayout(ask)
        self.ask_dbl = QCheckBox("캐릭터를 따닥(더블클릭)하면 물어보기")
        self.ask_dbl.setChecked(self.app.cfg.get("ask_dbl", True))
        ag.addWidget(self.ask_dbl)
        cli = self.app.claude_cli()
        from PyQt5.QtWidgets import QLineEdit
        er = QHBoxLayout(); er.addWidget(QLabel("대답해 줄 AI:"))
        self.ask_engine = QComboBox()
        self.ask_engine.addItem("Claude (Claude Code)", "claude")
        self.ask_engine.addItem("ChatGPT (Codex, ChatGPT 구독으로)", "codex")
        self.ask_engine.addItem("Gemini (구글 무료 API 키)", "gemini")
        self.ask_engine.setCurrentIndex(max(0, self.ask_engine.findData(self.app.ask_engine())))
        er.addWidget(self.ask_engine, 1); ag.addLayout(er)
        self.ask_mode = QComboBox()
        self.ask_mode.addItem("숨겨서 바로 대답 받기 (창 안 뜸, 말풍선으로 대답)", "hidden")
        self.ask_mode.addItem("AI 창을 열어서 묻기 (Claude·ChatGPT)", "window")
        self.ask_mode.setCurrentIndex(max(0, self.ask_mode.findData(self.app.cfg.get("ask_mode") or ("hidden" if self.app.ask_ready() else "window"))))
        ag.addWidget(self.ask_mode)
        cx = self.app.codex_cli()
        ag.addWidget(QLabel("Claude Code: " + ("찾음 ✓" if cli else "아직 없음 — PowerShell 에서  irm https://claude.ai/install.ps1 | iex")
                            + "\nChatGPT(Codex): " + ("찾음 ✓" if cx else "아직 없음 — '설치·연결 방법'을 눌러 보세요")))
        row = QHBoxLayout()
        for lab, fn in [("Claude 연결 가이드 보기", "Claude_연결_가이드.txt"), ("Claude Code 설치하기", "INSTALL_CLAUDE_CODE.bat")]:
            bt2 = QPushButton(lab)
            bt2.clicked.connect(lambda _=False, fn=fn: self.open_file(fn))
            row.addWidget(bt2)
        ag.addLayout(row)
        row = QHBoxLayout()
        bc = QPushButton("딸깍! ChatGPT 연결")
        bc.setToolTip("ChatGPT 구독 계정으로 대답하게 해요. 필요한 프로그램을 알아서 깔고, 브라우저가 열리면 ChatGPT 로그인만 하면 끝!")
        bc.clicked.connect(self.connect_codex)
        row.addWidget(bc)
        bg = QPushButton("딸깍! Gemini 연결 (무료)")
        bg.setToolTip("구글 계정으로 무료 키를 받아 Gemini 로 대답하게 해요")
        bg.clicked.connect(self.connect_gemini)
        row.addWidget(bg)
        bt3 = QPushButton("자세한 방법")
        bt3.clicked.connect(self.ai_guide)
        row.addWidget(bt3)
        bt4 = QPushButton("Claude 스킬 받기")
        bt4.setToolTip("Claude 앱 → 설정 → 기능(Capabilities) → 스킬 → 업로드에 이 파일을 올리면, Claude 대화에서 '펫한테 알려 줘' 같은 말로 캐릭터를 움직일 수 있어요")
        bt4.clicked.connect(lambda: __import__("webbrowser").open("https://github.com/sansan123123cc/MiniBuddies/raw/main/MiniBuddies_pet.skill"))
        row.addWidget(bt4)
        ag.addLayout(row)
        gr = QHBoxLayout(); gr.addWidget(QLabel("Gemini API 키:"))
        self.gemini_key = QLineEdit(self.app.cfg.get("gemini_key", "")); self.gemini_key.setEchoMode(QLineEdit.Password)
        self.gemini_key.setPlaceholderText("Gemini 를 쓸 때만 — 구글 AI 스튜디오에서 무료로 받은 키 붙여넣기")
        gr.addWidget(self.gemini_key, 1)
        gk = QPushButton("키 받으러 가기")
        gk.clicked.connect(lambda: __import__("webbrowser").open("https://aistudio.google.com/apikey"))
        gr.addWidget(gk); ag.addLayout(gr)
        nr = QHBoxLayout(); nr.addWidget(QLabel("캐릭터들이 나를 부르는 이름:"))
        self.my_name = QLineEdit(self.app.cfg.get("my_name", "")); self.my_name.setPlaceholderText("비우면 특별한 호칭 없이 (예: 지휘관, 선배, 주인님)")
        nr.addWidget(self.my_name); ag.addLayout(nr)
        self.ask_ctl = QCheckBox("물어본 캐릭터가 다른 친구들에게도 동작·말·장면을 시킬 수 있게 하기")
        self.ask_ctl.setChecked(self.app.cfg.get("ask_control", True))
        ag.addWidget(self.ask_ctl)
        self.ask_web = QCheckBox("숨겨서 물을 때 인터넷 검색도 허용하기 (최신 정보·뉴스 질문용)")
        self.ask_web.setChecked(self.app.cfg.get("ask_web", False))
        ag.addWidget(self.ask_web)
        self.ask_screen = QComboBox()
        self.ask_screen.addItem("화면 같이 보기: 안 함", "off")
        self.ask_screen.addItem("화면 같이 보기: 질문에 '화면·이거·여기·에러' 같은 말이 있을 때만", "auto")
        self.ask_screen.addItem("화면 같이 보기: 물어볼 때마다", "always")
        self.ask_screen.setCurrentIndex(max(0, self.ask_screen.findData(self.app.cfg.get("ask_screen", "auto"))))
        ag.addWidget(self.ask_screen)
        ac = QGroupBox("캐릭터끼리 수다 (Claude 사용량이 들어요)")
        acv = QFormLayout(ac)
        self.ai_chat = QCheckBox("가끔 화면 속 두 친구가 Claude 로 진짜 수다 떨기")
        self.ai_chat.setChecked(self.app.cfg.get("ai_chat", False))
        acv.addRow("", self.ai_chat)
        from PyQt5.QtWidgets import QSpinBox
        self.ai_chat_max = QSpinBox(); self.ai_chat_max.setRange(1, 50); self.ai_chat_max.setSuffix(" 번")
        self.ai_chat_max.setValue(int(self.app.cfg.get("ai_chat_max", 5)))
        acv.addRow("하루 최대", self.ai_chat_max)
        self.ai_chat_gap = QSpinBox(); self.ai_chat_gap.setRange(5, 600); self.ai_chat_gap.setSuffix(" 분")
        self.ai_chat_gap.setValue(int(self.app.cfg.get("ai_chat_gap", 40)))
        acv.addRow("최소 간격", self.ai_chat_gap)
        tb = QPushButton("지금 한 번 수다 떨게 하기")
        tb.clicked.connect(lambda: self.app.start_ai_chat(force=True) or None)
        acv.addRow("", tb)
        later.append(ac)
        bg = QGroupBox("관심사 브리핑 (하루 한 번 검색해서 알려 주기, Claude 사용량이 들어요)")
        bgv = QFormLayout(bg)
        self.brief_on = QCheckBox("매일 정한 시간에 관심사 소식 브리핑 받기")
        self.brief_on.setChecked(self.app.cfg.get("brief_on", False))
        bgv.addRow("", self.brief_on)
        self.brief_keys = []
        ks = list(self.app.cfg.get("brief_keys", [])) + [""] * 5
        for i in range(5):
            le = QLineEdit(ks[i]); le.setPlaceholderText(["예: 승리의 여신 니케", "예: 붕괴 스타레일", "예: 스텔라이브", "예: 인공지능", "예: 날씨"][i])
            self.brief_keys.append(le); bgv.addRow(f"키워드 {i + 1}", le)
        self.brief_time = QLineEdit(self.app.cfg.get("brief_time", "09:00")); self.brief_time.setPlaceholderText("09:00")
        bgv.addRow("시간 (24시)", self.brief_time)
        bb = QPushButton("지금 브리핑 받기")
        bb.clicked.connect(lambda: (self.app.cfg.__setitem__("brief_keys", [k.text().strip() for k in self.brief_keys if k.text().strip()][:5]),
                                    self.app.start_briefing(force=True)) and None)
        bgv.addRow("", bb)
        later.append(bg)
        iwg = QGroupBox("자리 비움 마중")
        iwv = QFormLayout(iwg)
        self.idle_welcome = QCheckBox("한동안 컴퓨터를 안 만지면 졸다가, 돌아오면 달려와서 '어서 와~!'")
        self.idle_welcome.setChecked(self.app.cfg.get("idle_welcome", True))
        iwv.addRow("", self.idle_welcome)
        self.idle_min = QSpinBox(); self.idle_min.setRange(1, 120); self.idle_min.setSuffix(" 분")
        self.idle_min.setValue(int(self.app.cfg.get("idle_min", 5)))
        iwv.addRow("자리 비움 판단", self.idle_min)
        self.iwg_box = iwg                      # → '화면·움직임' 탭에 붙임
        # 작업 권한: 숨겨서 물을 때 Claude 가 내 컴퓨터 파일·프로그램을 다룰 수 있게
        pw = QGroupBox("작업 권한 (숨겨서 물을 때)")
        pv = QVBoxLayout(pw)
        self.ask_power = QComboBox()
        self.ask_power.addItem("대답만 하기 (파일·프로그램 안 건드림)", "none")
        self.ask_power.addItem("아래 폴더 안의 파일 읽기·고치기·새로 만들기", "files")
        self.ask_power.addItem("폴더 파일 + 명령 실행 (프로그램 켜기·변환 등)", "full")
        self.ask_power.setCurrentIndex(max(0, self.ask_power.findData(self.app.cfg.get("ask_power", "none"))))
        pv.addWidget(self.ask_power)
        from PyQt5.QtWidgets import QListWidget
        self.ask_dirs = QListWidget(); self.ask_dirs.setMaximumHeight(80)
        for d in self.app.cfg.get("ask_dirs", []):
            self.ask_dirs.addItem(d)
        pv.addWidget(self.ask_dirs)
        dr = QHBoxLayout()
        da, dd = QPushButton("폴더 추가…"), QPushButton("선택 폴더 빼기")
        def _add_dir():
            from PyQt5.QtWidgets import QFileDialog
            d = QFileDialog.getExistingDirectory(self, "캐릭터가 다룰 수 있는 폴더 고르기")
            if d and not self.ask_dirs.findItems(d, Qt.MatchExactly):
                self.ask_dirs.addItem(os.path.normpath(d))
        da.clicked.connect(_add_dir)
        dd.clicked.connect(lambda: [self.ask_dirs.takeItem(self.ask_dirs.row(i)) for i in self.ask_dirs.selectedItems()])
        dr.addWidget(da); dr.addWidget(dd); dr.addStretch(1)
        pv.addLayout(dr)
        warn = QLabel("※ 캐릭터에게 한 부탁대로 실제로 파일을 고치고 명령을 실행해요. 고치기 전 파일은 .bak 으로 백업하라고 시켜 두지만, "
                      "중요한 폴더는 넣지 말고 작업용 폴더만 넣어 주세요. 지우기·설치·시스템 설정 변경은 하지 않고 방법만 알려 줘요.")
        warn.setWordWrap(True); warn.setStyleSheet("color:#b04a6a;")
        pv.addWidget(warn)
        self.ask_room = QComboBox()
        self.ask_room.addItem("대화 기억: 모두 한 방에서 이어서 (친구들 이야기도 다 기억)", "one")
        self.ask_room.addItem("대화 기억: 캐릭터마다 따로", "each")
        self.ask_room.setCurrentIndex(max(0, self.ask_room.findData(self.app.cfg.get("ask_room", "one"))))
        ag.addWidget(self.ask_room)
        lg = QPushButton("대화 기록 보기 (대화기록.txt)")
        lg.clicked.connect(lambda: self.open_file("대화기록.txt"))
        ag.addWidget(lg)
        fg = QPushButton("캐릭터들과 나눈 대화 기억 지우기")
        fg.clicked.connect(lambda: (self.app.cfg.pop("ask_sessions", None), self.app.save_cfg(),
                                    QMessageBox.information(self, "대화 기억", "다음 질문부터 새 대화로 시작해요.")))
        ag.addWidget(fg)
        self.ask_where = QComboBox()
        self.ask_where.addItem("창 열기: Claude 데스크톱 앱", "app")
        self.ask_where.addItem("창 열기: 웹 브라우저(claude.ai)", "web")
        self.ask_where.setCurrentIndex(max(0, self.ask_where.findData(self.app.cfg.get("ask_where", "app"))))
        ag.addWidget(self.ask_where)
        self.ask_send = QCheckBox("질문을 바로 보내기 (Claude 창이 맨 앞에 뜨면 Enter 를 대신 눌러 줌)")
        self.ask_send.setChecked(self.app.cfg.get("ask_send", True))
        ag.addWidget(self.ask_send)
        ag.addWidget(pw)                       # 작업 권한은 물어보기 맨 아래
        f.addRow(ask)
        for g_ in later:
            f.addRow(g_)
        ug = QGroupBox("사용량 창 (claude.ai 사용량을 작은 창으로)")
        ugl = QVBoxLayout(ug)
        self.ua_cb = QCheckBox("80%·95% 넘으면 펫이 말풍선으로 알려 주기")
        self.ua_cb.setChecked(self.app.cfg.get("usage_alert", True))
        ugl.addWidget(self.ua_cb)
        ub = QPushButton("사용량 창 띄우기")
        ub.clicked.connect(lambda: self.app.open_usage())
        ugl.addWidget(ub)
        f.addRow(ug)
        box = QGroupBox("Claude 연결 (MCP)")
        g = QVBoxLayout(box)
        self.mcp_on = QCheckBox("Claude 가 펫을 움직일 수 있게 하기 (이 컴퓨터 안에서만)")
        self.mcp_on.setChecked(self.app.cfg.get("mcp", True))
        g.addWidget(self.mcp_on)
        st = "연결 대기 중 (포트 %d)" % self.app.mcp_srv.server_port if self.app.mcp_srv else "꺼져 있음"
        g.addWidget(QLabel("상태: " + st))
        seen = getattr(self.app, "mcp_seen", None)
        g.addWidget(QLabel("Claude 접속: " + (f"확인됨 ({seen})" if seen else "아직 없음 (Claude 데스크톱을 완전히 껐다 켜 보세요)")))
        bt = QPushButton("딸깍! Claude 랑 연결하기")
        bt.clicked.connect(self.install_mcp)
        g.addWidget(bt)
        g.addWidget(QLabel("누르면 Claude 데스크톱을 잠깐 껐다 켜면서 알아서 연결해요."))
        f.addRow(box)
        return w

    # 업데이트: GitHub 에서 새 버전 자동으로 받기
    def tab_update(self):
        from PyQt5.QtWidgets import QLineEdit
        w = QWidget(); f = QFormLayout(w)
        man, uc = upd_load("manifest.json"), upd_load("update.json")
        f.addRow("지금 버전:", QLabel("v%s" % (man.get("version") or "개발용(설치 안 한 폴더)")))
        f.addRow("저장소:", QLabel(uc.get("repo") or man.get("repo") or "(없음)"))
        self.upd_tok = QLineEdit(uc.get("token", ""))
        self.upd_tok.setEchoMode(QLineEdit.Password)
        self.upd_tok.setPlaceholderText("github_pat_… (읽기 전용 토큰)")
        f.addRow("접근 토큰:", self.upd_tok)
        self.upd_auto = QCheckBox("새 버전이 나오면 알아서 받기 (켤 때 + 3시간마다 확인)")
        self.upd_auto.setChecked(uc.get("auto", True))
        f.addRow("", self.upd_auto)
        self.upd_lbl = QLabel(self.app.upd_msg or "")
        self.upd_lbl.setWordWrap(True)
        bt = QPushButton("지금 업데이트 확인")

        def go():
            self.save_update_cfg()
            self.upd_lbl.setText("확인 중…")
            self.app.check_update(quiet=False, done_cb=lambda m: self.upd_lbl.setText(m))
        bt.clicked.connect(go)
        f.addRow("", bt)
        f.addRow("", self.upd_lbl)
        bc = QPushButton("캐릭터 고르기 (쓰는 캐릭터만 받기·안 쓰는 캐릭터 지우기)…")
        bc.clicked.connect(self.app.open_char_picker)
        f.addRow("", bc)
        note = QLabel("받는 건 바뀐 파일뿐이고, settings.json(내 설정)·대화기록은 그대로 둬요.\n"
                      "업데이트가 끝나면 펫이 잠깐 사라졌다가 다시 켜져요.")
        note.setWordWrap(True)
        f.addRow("", note)
        return w

    def save_update_cfg(self):
        uc = upd_load("update.json")
        uc["token"] = self.upd_tok.text().strip()
        uc["auto"] = self.upd_auto.isChecked()
        if not uc["token"]:
            uc.pop("token")
            if not os.path.exists(upd_path("update.json")):
                return
        try:
            upd_save_cfg(uc)
        except Exception:
            pass

    def ai_guide(self):
        QMessageBox.information(self, "ChatGPT·Gemini 연결 방법", AI_GUIDE)

    def use_engine(self, e):
        """고른 AI 로 바로 쓰게 (환경설정 칸도 같이 맞춰서 [확인]을 눌러도 그대로)"""
        self.ask_engine.setCurrentIndex(max(0, self.ask_engine.findData(e)))
        self.ask_mode.setCurrentIndex(max(0, self.ask_mode.findData("hidden")))
        self.app.cfg["ask_engine"] = e; self.app.cfg["ask_mode"] = "hidden"
        self.app.save_cfg()

    def connect_codex(self):
        """딸깍! ChatGPT 연결: (없으면) Node.js → Codex 설치 → ChatGPT 로그인까지 창 하나로"""
        import subprocess
        if self.app.codex_cli():
            QMessageBox.information(self, "ChatGPT 연결", "Codex 는 이미 깔려 있어요! 로그인 창을 열게요.\n브라우저가 열리면 ChatGPT 계정으로 로그인만 해 주세요.")
        ps = os.path.join(MCP_HOME, "connect_chatgpt.ps1")
        os.makedirs(MCP_HOME, exist_ok=True)
        script = r"""$ErrorActionPreference = 'Continue'
$Host.UI.RawUI.WindowTitle = '꼬마 친구들 - ChatGPT 연결'
function Fresh { $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User') + ';' + "$env:APPDATA\npm" }
Write-Host ''
Write-Host '  ChatGPT 연결을 시작할게요! 이 창은 끝날 때까지 그대로 두세요.' -ForegroundColor Magenta
Write-Host ''
Fresh
if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
  if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host '  [1/3] Node.js 설치 중... (1~3분, 설치 허용 창이 뜨면 [예])' -ForegroundColor Cyan
    if (Get-Command winget -ErrorAction SilentlyContinue) {
      winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements --silent
    } else {
      Write-Host '  자동 설치가 안 되는 PC 예요. 열리는 페이지에서 Node.js (LTS) 를 깔고 이 버튼을 다시 눌러 주세요.' -ForegroundColor Yellow
      Start-Process 'https://nodejs.org/ko/download'
      Read-Host '  엔터를 누르면 닫혀요'; exit
    }
    Fresh
  }
  Write-Host '  [2/3] ChatGPT 연결 프로그램(Codex) 설치 중...' -ForegroundColor Cyan
  npm install -g @openai/codex
  Fresh
}
if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
  Write-Host '  설치가 끝나지 않았어요. PC 를 한 번 다시 켠 뒤 이 버튼을 다시 눌러 주세요.' -ForegroundColor Yellow
  Read-Host '  엔터를 누르면 닫혀요'; exit
}
Write-Host '  [3/3] 브라우저가 열리면 ChatGPT 계정으로 로그인해 주세요!' -ForegroundColor Cyan
codex login
Write-Host ''
Write-Host '  다 됐어요! 이제 캐릭터를 따닥 눌러서 물어보세요. (5초 뒤 창이 닫혀요)' -ForegroundColor Green
Start-Sleep 5
"""
        try:
            with open(ps, "w", encoding="utf-8-sig") as f:
                f.write(script)
            subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps],
                             creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
        except Exception as e:
            QMessageBox.warning(self, "ChatGPT 연결", f"연결 창을 못 열었어요: {e}\n'자세한 방법'을 보고 직접 해 주세요."); return
        self.use_engine("codex")

    def connect_gemini(self):
        """딸깍! Gemini 연결: 키 받는 페이지 열기 → 키를 복사하면 알아서 알아채서 붙여넣고 확인"""
        from PyQt5.QtWidgets import QInputDialog
        import webbrowser
        webbrowser.open("https://aistudio.google.com/apikey")
        cb = QApplication.clipboard()
        start = (cb.text() or "").strip()
        dlg = QInputDialog(self)
        dlg.setWindowTitle("Gemini 연결 (무료)")
        dlg.setLabelText("방금 열린 구글 AI 스튜디오에서\n① 구글 계정으로 로그인 → ② 'API 키 만들기' → ③ 키 복사\n\n"
                         "복사하면 아래 칸에 저절로 들어가요. 그다음 [OK]!")
        dlg.setTextEchoMode(QLineEdit.Password)
        dlg.resize(460, 160)
        def poll():
            t = (cb.text() or "").strip()
            if t != start and re.fullmatch(r"[A-Za-z0-9_\-]{30,60}", t) and not dlg.textValue():
                dlg.setTextValue(t)
        tm = QTimer(dlg); tm.timeout.connect(poll); tm.start(500)
        if not dlg.exec_():
            return
        key = dlg.textValue().strip()
        if not key:
            return
        self.app.cfg["gemini_key"] = key
        self.gemini_key.setText(key)
        self.use_engine("gemini")
        out, err = self.app.run_gemini("한 단어로만 대답해 줘: 안녕?")
        if out:
            QMessageBox.information(self, "Gemini 연결", "연결 완료! 이제 캐릭터를 따닥 눌러서 물어보세요 ♪")
        else:
            QMessageBox.warning(self, "Gemini 연결", f"키는 저장했는데 시험 대답이 안 왔어요.\n({err[:120]})\n키를 다시 복사해서 한 번 더 눌러 주세요.")

    def open_file(self, fn):
        path = os.path.join(BASE, fn)
        if not os.path.exists(path):
            QMessageBox.warning(self, "파일 없음", f"펫 폴더에 {fn} 이 없어요. 최신 zip 으로 다시 받아 주세요."); return
        try:
            os.startfile(path)
        except Exception as e:
            QMessageBox.warning(self, "열기 실패", str(e))

    def install_mcp(self):
        if QMessageBox.question(self, "Claude 연결",
                                "Claude 데스크톱을 잠깐 껐다가 다시 켜서 연결할게요.\n"
                                "Claude 에서 쓰던 내용(보내는 중인 메시지 등)이 있으면 먼저 정리해 주세요.\n\n진행할까요?") \
                != QMessageBox.Yes:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            ok, msg = self.app.install_mcp()
        finally:
            QApplication.restoreOverrideCursor()
        (QMessageBox.information if ok else QMessageBox.warning)(self, "Claude 연결", msg)

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

# ── 관심사 브리핑 보기 창 (메모장 대신 펫 전용 창) ──
def brief_html(text):
    """브리핑 글 → 보기 좋은 HTML (■ 제목, - 항목, 출처 링크)"""
    import html as _h
    url_re = re.compile(r"https?://[^\s)\]]+")

    def link(t):
        t = _h.escape(t)
        t = re.sub(r"\(출처:\s*(https?://[^\s)]+)\)", lambda m: '<a href="%s" style="color:#c45a8a;font-size:11px">[출처]</a>' % m.group(1), t)
        return url_re.sub(lambda m: m.group(0) if 'href="' + m.group(0) in t else '<a href="%s" style="color:#c45a8a">%s</a>' % (m.group(0), m.group(0)), t)
    out, in_ul = [], False
    lines = text.replace("\r", "").split("\n")
    for i, ln in enumerate(lines):
        st = ln.strip()
        if not st:
            if in_ul:
                out.append("</ul>"); in_ul = False
            continue
        if i == 0 and st.startswith("관심사 브리핑"):
            out.append('<h2 style="color:#d0588a;margin:0 0 2px 0">%s</h2>' % _h.escape(st)); continue
        if st.startswith("키워드:"):
            out.append('<div style="color:#9a8592;font-size:12px;margin-bottom:8px">%s</div>' % _h.escape(st)); continue
        if st.startswith("■") or st.startswith("##") or st.startswith("────"):
            if in_ul:
                out.append("</ul>"); in_ul = False
            out.append('<h3 style="color:#4a3a44;border-bottom:1px solid #f3c6d8;padding-bottom:2px;margin:14px 0 4px 0">%s</h3>'
                       % _h.escape(st.lstrip("■#─ ").rstrip("─ ")))
            continue
        if st.startswith("- ") or st.startswith("• "):
            if not in_ul:
                out.append('<ul style="margin:2px 0 2px -18px">'); in_ul = True
            out.append('<li style="margin-bottom:5px">%s</li>' % link(st[2:])); continue
        if in_ul:
            out.append("</ul>"); in_ul = False
        out.append('<p style="margin:3px 0">%s</p>' % link(st))
    if in_ul:
        out.append("</ul>")
    return ('<div style="font-family:\'Malgun Gothic\';font-size:14px;line-height:150%%;color:#4a3a44">%s</div>' % "".join(out))


class BriefingWindow(QWidget):
    """왼쪽: 날짜 목록 · 오른쪽: 브리핑 본문 (링크는 브라우저로)"""
    def __init__(self, app):
        super().__init__(None, Qt.Window)
        from PyQt5.QtWidgets import QListWidget, QTextBrowser, QSplitter
        self.app = app
        self.setWindowTitle("관심사 브리핑")
        self.setStyleSheet("QWidget{background:#FFF7FA} QListWidget{background:#fff;border:1px solid #f3c6d8;border-radius:8px;"
                           "font:13px 'Malgun Gothic'} QListWidget::item:selected{background:#fbe3ee;color:#b0476f}"
                           "QTextBrowser{background:#fff;border:1px solid #f3c6d8;border-radius:8px;padding:10px}"
                           "QPushButton{background:#fbe3ee;color:#b0476f;border:0;border-radius:7px;padding:5px 12px;font:13px 'Malgun Gothic'}"
                           "QPushButton:hover{background:#f7cfe0}")
        v = QVBoxLayout(self)
        sp = QSplitter(Qt.Horizontal)
        self.lst = QListWidget(); self.lst.setMaximumWidth(170)
        self.view = QTextBrowser(); self.view.setOpenExternalLinks(True)
        sp.addWidget(self.lst); sp.addWidget(self.view); sp.setStretchFactor(1, 1)
        v.addWidget(sp, 1)
        h = QHBoxLayout()
        b1 = QPushButton("지금 다시 받기"); b1.clicked.connect(lambda: self.app.start_briefing(force=True))
        b2 = QPushButton("폴더 열기"); b2.clicked.connect(self.open_dir)
        b3 = QPushButton("닫기"); b3.clicked.connect(self.close)
        self.top = QCheckBox("항상 위"); self.top.toggled.connect(self.set_top)
        h.addWidget(b1); h.addWidget(b2); h.addWidget(self.top); h.addStretch(1); h.addWidget(b3)
        v.addLayout(h)
        self.lst.currentTextChanged.connect(self.show_day)
        g = self.app.cfg.get("brief_geo")
        if g and len(g) == 4:
            self.setGeometry(*g)
        else:
            self.resize(900, 640)

    def set_top(self, on):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, bool(on)); self.show()

    def reload(self, select=None):
        fs = sorted((f for f in os.listdir(self.app.brief_dir()) if f.endswith(".txt")), reverse=True)
        self.lst.blockSignals(True); self.lst.clear()
        for f in fs:
            self.lst.addItem(f[:-4])
        self.lst.blockSignals(False)
        if fs:
            name = (select or fs[0])[:-4] if (select or fs[0]).endswith(".txt") else (select or fs[0])
            items = self.lst.findItems(name, Qt.MatchExactly)
            (self.lst.setCurrentItem(items[0]) if items else self.lst.setCurrentRow(0))
            self.show_day(self.lst.currentItem().text())

    def show_day(self, day):
        if not day:
            return
        try:
            txt = open(os.path.join(self.app.brief_dir(), day + ".txt"), encoding="utf-8-sig").read()
        except Exception as e:
            txt = "못 읽었어요: %s" % e
        self.view.setHtml(brief_html(txt))
        self.setWindowTitle("관심사 브리핑 — " + day)

    def open_dir(self):
        try:
            os.startfile(self.app.brief_dir())
        except Exception:
            pass

    def closeEvent(self, e):
        g = self.geometry()
        self.app.cfg["brief_geo"] = [g.x(), g.y(), g.width(), g.height()]
        self.app.save_cfg()
        super().closeEvent(e)
