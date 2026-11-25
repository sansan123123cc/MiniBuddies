"""Claude interaction history window and storage."""

import datetime
import json
import os
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
)
from minibuddies.catalog import APP_NAME
from minibuddies.runtime import BASE


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
