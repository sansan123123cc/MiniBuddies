"""Monitor, size and display settings tabs."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QWidget,
)
from minibuddies.catalog import BUBBLE_PX, BUBBLE_SIZES, SHAKE, SHAKE_LEVELS, SIZES
from minibuddies.desktop import target_screen


class AppearanceTabs:
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
