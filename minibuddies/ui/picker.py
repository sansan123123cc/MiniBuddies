"""Installed-character selection and first-run setup."""

import json
import os
import sys
import threading
import time
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from minibuddies.catalog import FRANCHISE, SQUADS, SQUAD_NAME
from minibuddies.updates import (
    upd_all_chars,
    upd_apply,
    upd_fetch_manifest,
    upd_get,
    upd_installed,
    upd_load,
    upd_path,
    upd_save_cfg,
)


# ── 캐릭터 고르기 창 (다이어트: 쓰는 캐릭터만 받기 · 안 쓰는 캐릭터 지우기) ──
def upd_char_dirs(files):
    """캐릭터 → 대표 폴더 (기본 의상 폴더 우선)"""
    dirs = {}
    for rel in files:
        if rel.endswith("/0.png") and rel.startswith("chars/"):
            d = rel.split("/")[1]
            if d.startswith("_"):
                continue
            c = d.split("@")[0]
            rank = 0 if d == c else (1 if d.endswith("@basic") else 2)
            if c not in dirs or rank < dirs[c][0]:
                dirs[c] = (rank, d)
    return {c: v[1] for c, v in dirs.items()}


class CharPicker(QDialog):
    """프랜차이즈 → 그룹 → 캐릭터 그림 타일. 체크한 캐릭터만 받고, 뺀 캐릭터는 지움"""
    def __init__(self, files, chosen, first=False):
        super().__init__()
        from PyQt5.QtWidgets import QScrollArea, QToolButton
        from PyQt5.QtCore import QSize
        self.setWindowTitle("캐릭터 고르기")
        self.resize(760, 640)
        self.files = files
        self.chars = upd_all_chars(files)
        self.dirs = upd_char_dirs(files)
        self.installed = upd_installed()
        self.names = upd_load("_thumbs/names.json") if os.path.exists(upd_path("_thumbs/names.json")) else {}
        self.btn = {}
        v = QVBoxLayout(self)
        head = QLabel(("처음 오셨네요! 데리고 놀 캐릭터를 골라 주세요. 고른 캐릭터만 받아서 가볍게 시작해요.\n"
                       if first else "") + "체크한 캐릭터만 받아요. 체크를 풀면 그 캐릭터(스킨 포함)는 컴퓨터에서 지워져요. 나중에 언제든 바꿀 수 있어요.")
        head.setWordWrap(True)
        v.addWidget(head)
        sc = QScrollArea(); sc.setWidgetResizable(True)
        body = QWidget(); bv = QVBoxLayout(body)
        used = set()
        groups = []
        for fr, sqs in FRANCHISE:
            for sq in sqs:
                mem = [c for c in SQUADS.get(sq, []) if c in self.chars and c not in used]
                used.update(mem)
                if mem:
                    groups.append((fr, SQUAD_NAME.get(sq, sq), mem))
        rest = [c for c in self.chars if c not in used]
        if rest:
            groups.append(("기타", "", rest))
        last_fr = None
        for fr, sqn, mem in groups:
            if fr != last_fr:
                t = QLabel("<b>%s</b>" % fr); bv.addWidget(t); last_fr = fr
            box = QGroupBox(sqn or " ")
            g = QGridLayout(box); g.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            for i, c in enumerate(mem):
                b = QToolButton(); b.setCheckable(True); b.setChecked(c in chosen)
                b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
                b.setIconSize(QSize(96, 96)); b.setFixedSize(112, 154)
                b.setStyleSheet("QToolButton{border:2px solid #eee;border-radius:10px;background:#fff}"
                                "QToolButton:checked{border:2px solid #e86a9a;background:#fff0f6}")
                b.toggled.connect(lambda _=None: self.sync())
                self.btn[c] = b
                g.addWidget(b, i // 5, i % 5)
            bv.addWidget(box)
        bv.addStretch(1)
        sc.setWidget(body); v.addWidget(sc, 1)
        self.sum = QLabel(""); v.addWidget(self.sum)
        h = QHBoxLayout()
        ba = QPushButton("전부 고르기"); ba.clicked.connect(lambda: [b.setChecked(True) for b in self.btn.values()])
        bn = QPushButton("전부 풀기"); bn.clicked.connect(lambda: [b.setChecked(False) for b in self.btn.values()])
        h.addWidget(ba); h.addWidget(bn); h.addStretch(1)
        self.ok = QPushButton("받기 시작" if first else "적용 (받기·지우기)")
        self.ok.clicked.connect(self.accept)
        cancel = QPushButton("닫기" if first else "취소"); cancel.clicked.connect(self.reject)
        h.addWidget(cancel); h.addWidget(self.ok)
        v.addLayout(h)
        self.refresh_tiles()
        self.sync()
        self.need = [c for c in self.chars if not os.path.exists(upd_path("_thumbs/%s.png" % c)) or c not in self.names]
        if self.need:                                      # 안 깔린 캐릭터 그림·이름은 조금씩 받아 옴 (캐시)
            threading.Thread(target=self.fetch_thumbs, daemon=True).start()
            self.tt = QTimer(self); self.tt.timeout.connect(self.refresh_tiles); self.tt.start(700)

    def fetch_thumbs(self):
        cfg, man = upd_load("update.json"), upd_load("manifest.json")
        repo = cfg.get("repo") or man.get("repo"); br = cfg.get("branch") or man.get("branch") or "main"
        os.makedirs(upd_path("_thumbs"), exist_ok=True)
        for c in list(self.need):
            d = self.dirs.get(c)
            if not d:
                continue
            try:
                tp = upd_path("_thumbs/%s.png" % c)
                if not os.path.exists(tp):
                    src = upd_path("chars/%s/0.png" % d)
                    data = open(src, "rb").read() if os.path.exists(src) else upd_get(repo, "chars/%s/0.png" % d, cfg.get("token"), br)
                    with open(tp + ".tmp", "wb") as f:
                        f.write(data)
                    os.replace(tp + ".tmp", tp)
                if c not in self.names:
                    src = upd_path("chars/%s/name.txt" % d)
                    raw = open(src, "rb").read() if os.path.exists(src) else upd_get(repo, "chars/%s/name.txt" % d, cfg.get("token"), br)
                    self.names[c] = raw.decode("utf-8", "ignore").strip() or c
            except Exception:
                pass
        try:
            with open(upd_path("_thumbs/names.json"), "w", encoding="utf-8") as f:
                json.dump(self.names, f, ensure_ascii=False)
        except Exception:
            pass
        self.need = []

    def refresh_tiles(self):
        from PyQt5.QtGui import QIcon
        for c, b in self.btn.items():
            d = self.dirs.get(c, c)
            nm = self.names.get(c)
            if not nm:
                try:
                    nm = open(upd_path("chars/%s/name.txt" % d), encoding="utf-8").read().strip()
                except Exception:
                    nm = c
            b.setText(nm + ("\n깔려 있음" if c in self.installed else ""))
            for tp in (upd_path("chars/%s/0.png" % d), upd_path("_thumbs/%s.png" % c)):
                if os.path.exists(tp):
                    b.setIcon(QIcon(QPixmap(tp))); break
        if getattr(self, "tt", None) and not self.need:
            self.tt.stop()

    def chosen(self):
        return {c for c, b in self.btn.items() if b.isChecked()}

    def sync(self):
        ch = self.chosen()
        add = [c for c in ch if c not in self.installed]
        rem = [c for c in self.installed if c not in ch and c in self.btn]
        self.sum.setText("고른 캐릭터 %d명 · 새로 받기 %d명 · 지우기 %d명" % (len(ch), len(add), len(rem)))
        self.ok.setEnabled(bool(ch))


def first_run_pick():
    """가벼운 설치(캐릭터 없음)로 처음 켰을 때: 고르기 창 → 고른 캐릭터만 받고 시작"""
    if not os.path.exists(upd_path("update.json")) or upd_installed():
        return
    from PyQt5.QtWidgets import QProgressDialog
    qa = QApplication.instance() or QApplication(sys.argv)
    remote = upd_fetch_manifest()
    if not remote or not remote.get("files"):
        QMessageBox.warning(None, "꼬마 친구들", "캐릭터 목록을 못 받았어요. 인터넷 연결을 확인하고 다시 켜 주세요.")
        sys.exit(0)
    dlg = CharPicker(remote["files"], set(), first=True)
    if not dlg.exec_():
        sys.exit(0)
    uc = upd_load("update.json"); uc["chars"] = sorted(dlg.chosen()); upd_save_cfg(uc)
    pd = QProgressDialog("고른 캐릭터 받는 중…", None, 0, 100); pd.setWindowTitle("꼬마 친구들"); pd.setMinimumDuration(0)
    st = {"done": 0, "all": 1, "err": None, "end": False}

    def work():
        try:
            upd_apply(remote, progress=lambda d, a: st.update(done=d, all=max(1, a)))
        except Exception as e:
            st["err"] = str(e)
        st["end"] = True
    threading.Thread(target=work, daemon=True).start()
    while not st["end"]:
        pd.setValue(int(st["done"] * 100 / st["all"])); pd.setLabelText("고른 캐릭터 받는 중… %d / %d" % (st["done"], st["all"]))
        qa.processEvents(); time.sleep(0.05)
    pd.close()
    if st["err"]:
        QMessageBox.warning(None, "꼬마 친구들", "받다가 멈췄어요: %s\n다시 켜면 받던 데서 이어 받아요." % st["err"])
        sys.exit(0)
