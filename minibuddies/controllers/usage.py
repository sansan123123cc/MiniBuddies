"""Assistant usage notifier."""

import json
import os
import random
import sys
import threading
import time
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox
from minibuddies.runtime import BASE


class UsageController:
    # ── Claude 사용량 위젯: claude_usage.py 를 따로 띄움 (claude.ai 사용량 화면의 숫자를 작은 창에) ──
    USAGE_JSON = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "DesktopPet", "claude_usage", "usage.json")

    def usage_ready(self):
        """위젯에 필요한 작은 브라우저 부품(pywebview)이 깔려 있는지"""
        try:
            import importlib.util, site
            if importlib.util.find_spec("webview") is not None:
                return True
            return os.path.isdir(os.path.join(site.getusersitepackages(), "webview"))
        except Exception:
            return False

    def usage_note(self, text, secs=6):
        bs = [b for b in self.buddies if b.surface] or list(self.buddies)
        if bs:
            self.force_say(random.choice(bs), text, secs)

    def open_usage(self, auto=False):
        """메뉴 'Claude 사용량 보기': 위젯이 없으면 띄우고, 부품이 없으면 설치부터"""
        import subprocess
        p = getattr(self, "usage_proc", None)
        if p is not None and p.poll() is None:
            if not auto:
                self.usage_note("사용량 창은 이미 떠 있어~ 화면 어딘가에 있을 거야")
            return
        if not self.usage_ready():
            if auto:
                return
            if getattr(self, "usage_installing", False):
                self.usage_note("사용량 창 부품 설치 중이야, 조금만 기다려 줘~")
                return
            r = QMessageBox.question(None, "Claude 사용량",
                                     "사용량 창에 필요한 작은 브라우저 부품(pywebview)을 한 번 설치해야 해요.\n"
                                     "지금 설치할까요? (1분 정도, 인터넷 필요)")
            if r == QMessageBox.Yes:
                self.usage_install()
            return
        script = os.path.join(BASE, "claude_usage.py")
        if not os.path.exists(script):
            self.usage_note("사용량 위젯 파일이 아직 없어 — 업데이트를 받은 뒤 다시 해 줘")
            return
        exe = sys.executable
        if exe.lower().endswith("python.exe") and os.path.exists(exe[:-10] + "pythonw.exe"):
            exe = exe[:-10] + "pythonw.exe"
        try:
            self.usage_quitting = False
            self.usage_proc = subprocess.Popen([exe, script], cwd=BASE,
                                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.cfg["usage_widget"] = True
            self.save_cfg()
        except Exception as e:
            self.ask_log("usage widget error: %s" % e)

    def usage_install(self):
        import subprocess
        self.usage_installing = True
        self.usage_done = None
        self.usage_note("사용량 창 부품 설치 시작! 1분쯤 걸려~")
        exe = sys.executable
        if exe.lower().endswith("pythonw.exe") and os.path.exists(exe[:-11] + "python.exe"):
            exe = exe[:-11] + "python.exe"
        def run():
            try:
                r = subprocess.run([exe, "-m", "pip", "install", "--user", "pywebview"], capture_output=True, text=True,
                                   timeout=900, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.usage_done = (r.returncode == 0, (r.stderr or r.stdout or "")[-400:])
            except Exception as e:
                self.usage_done = (False, str(e))
        threading.Thread(target=run, daemon=True).start()
        self._usage_wait()

    def _usage_wait(self):
        d = getattr(self, "usage_done", None)
        if d is None:
            QTimer.singleShot(1500, self._usage_wait)
            return
        self.usage_done = None
        self.usage_installing = False
        ok, err = d
        if ok:
            import importlib
            importlib.invalidate_caches()
            self.usage_note("설치 끝! 사용량 창 띄울게♪")
            self.open_usage()
        else:
            self.ask_log("pywebview install failed: " + err)
            QMessageBox.warning(None, "Claude 사용량", "부품 설치에 실패했어요.\n\n" + err)

    def usage_stop(self):
        p = getattr(self, "usage_proc", None)
        if p is not None and p.poll() is None:
            self.usage_quitting = True          # 펫이 꺼지면서 닫는 것 → 다음에 켤 때 다시 띄움
            try:
                p.terminate()
            except Exception:
                pass

    def usage_tick(self):
        """1분마다: 위젯을 사용자가 닫았는지 확인 + 80%·95% 넘으면 말풍선으로 알림 (같은 초기화 시각엔 한 번씩만)"""
        p = getattr(self, "usage_proc", None)
        if p is not None and p.poll() is not None:
            self.usage_proc = None
            if not getattr(self, "usage_quitting", False) and self.cfg.get("usage_widget"):
                self.cfg["usage_widget"] = False
                self.save_cfg()
        if not self.cfg.get("usage_widget") or not self.cfg.get("usage_alert", True):
            return
        try:
            d = json.load(open(self.USAGE_JSON, encoding="utf-8"))
        except Exception:
            return
        if time.time() - float(d.get("ts", 0) or 0) > 900:
            return
        warned = self.__dict__.setdefault("usage_warned", set())
        for r in d.get("rows") or []:
            pct = int(r.get("pct", 0) or 0)
            lv = 95 if pct >= 95 else 80 if pct >= 80 else 0
            key = f"{r.get('label')}|{r.get('reset')}|{lv}"
            if not lv or key in warned:
                continue
            warned.add(key)
            when = f" ({r.get('reset')})" if r.get("reset") else ""
            if lv == 95:
                self.usage_note(f"Claude {r.get('label')} 사용량 {pct}%… 거의 다 썼어!{when}", 8)
            else:
                self.usage_note(f"Claude {r.get('label')} 사용량이 {pct}% 넘었어~ 조금 아껴 쓰자{when}", 8)
            break
