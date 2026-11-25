"""Assistant and update settings tabs."""

import os
import re
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from minibuddies.catalog import AI_GUIDE
from minibuddies.runtime import BASE, MCP_HOME
from minibuddies.updates import upd_load, upd_path, upd_save_cfg


class IntegrationTabs:
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
