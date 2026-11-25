"""Play, alarms and music settings tabs."""

from PyQt5.QtCore import QTime
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)
from minibuddies.catalog import ALARMS, ALARM_NAME, MAX_COUNT


class ActivityTabs:
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
