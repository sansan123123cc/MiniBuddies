"""Daily briefing display."""

import os
import re
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QCheckBox, QHBoxLayout, QPushButton, QVBoxLayout, QWidget


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
