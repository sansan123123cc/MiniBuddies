"""Desktop window management and application restart."""

import datetime
import os
import sys
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QApplication
from minibuddies.catalog import APP_NAME
from minibuddies.desktop import (
    CHAR_SCREEN,
    SCREEN,
    screen_for,
    set_topmost,
    target_screen,
    user32,
    window_tops,
    wintypes,
)
from minibuddies.runtime import ENTRY_SCRIPT, _crash_write
from minibuddies.ui.dialogs import HistoryDialog, SettingsDialog


class WindowController:
    def restart_self(self):
        """새 파일로 펫 다시 켜기 (자리 잡고 있던 '한 번만 켜기' 잠금을 먼저 풀어 줌)"""
        import subprocess
        try:
            self.lock.close()
        except Exception:
            pass
        exe = sys.executable
        if exe.lower().endswith("python.exe"):
            w = exe[:-10] + "pythonw.exe"
            if os.path.exists(w):
                exe = w
        script = os.path.abspath(sys.argv[0]) if sys.argv[0].endswith(".py") else ENTRY_SCRIPT
        try:
            proc = subprocess.Popen([exe, script] + sys.argv[1:], cwd=os.path.dirname(script),
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0),
                                    close_fds=True)
        except Exception as e:
            self.ask_log("restart error: %s" % e)
            self.relisten()
            return
        self.ask_log("restart: 새 프로그램 켜는 중")
        self._restart_wait(proc, 0)

    def relisten(self):
        """다시 켜기 실패 → 잠금을 다시 잡고 지금 프로그램이 계속 돌기"""
        try:
            from PyQt5.QtNetwork import QLocalServer
            QLocalServer.removeServer(self.lock_name)
            self.lock = QLocalServer(); self.lock.listen(self.lock_name)
            self.lock.newConnection.connect(self.on_lock_conn)
        except Exception:
            pass

    def on_lock_conn(self):
        """두 번째로 켠 프로그램이 'show' 를 보내면 친구들 다시 등장. 다시 켜기 확인용 'ping' 은 무시"""
        c = self.lock.nextPendingConnection()
        if c is None:
            return
        def read():
            try:
                data = bytes(c.readAll())
            except Exception:
                data = b""
            if not data.startswith(b"ping"):
                self.all_drop()
        c.readyRead.connect(lambda: QTimer.singleShot(0, read))

    def _restart_wait(self, proc, waited):
        """새 프로그램이 '한 번만 켜기' 잠금을 잡으면(=제대로 켜졌으면) 그때 나는 꺼짐. 새 게 바로 죽으면 나는 안 꺼짐"""
        from PyQt5.QtNetwork import QLocalSocket
        sock = QLocalSocket(); sock.connectToServer(self.lock_name)
        if sock.waitForConnected(200):
            sock.write(b"ping"); sock.flush(); sock.waitForBytesWritten(200); sock.disconnectFromServer()
            self.ask_log("restart: 새 프로그램 켜짐 → 이전 것 종료")
            self.qapp.quit(); return
        dead = proc.poll() is not None
        if dead or waited >= 40:
            self.ask_log("restart: 새 프로그램이 안 켜짐 (%s) → 지금 것 계속 실행" % ("종료 코드 %s" % proc.returncode if dead else "시간 초과"))
            _crash_write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] 업데이트 뒤 다시 켜기 실패 — 이전 버전으로 계속 실행\n")
            if not dead:
                try: proc.kill()
                except Exception: pass
            self.relisten()
            return
        QTimer.singleShot(500, lambda: self._restart_wait(proc, waited + 1))

    def rename_shortcuts(self):
        """예전 이름(Stellive Pet) 바로가기를 새 이름으로 (한 번만)"""
        if self.cfg.get("renamed_v1") or os.name != "nt":
            return
        dirs = []
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
            dirs.append(os.path.expandvars(winreg.QueryValueEx(k, "Desktop")[0]))
        except Exception:
            pass
        dirs += [os.path.join(os.path.expanduser("~"), "Desktop"),
                 os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs")]
        for d in dirs:
            old, new = os.path.join(d, "Stellive Pet.lnk"), os.path.join(d, f"{APP_NAME}.lnk")
            try:
                if os.path.exists(old) and not os.path.exists(new):
                    os.replace(old, new)
            except Exception:
                pass
        self.cfg["renamed_v1"] = True
        self.save_cfg()

    def pet_windows(self):
        from PyQt5.QtWidgets import QDialog, QMenu
        return [w for w in QApplication.topLevelWidgets()
                if w.isVisible() and not isinstance(w, (QDialog, QMenu)) and w.windowFlags() & Qt.Tool]

    def keep_on_top(self, force=False):
        # 켜져 있으면 매번 다시 맨 위로: 메신저처럼 스스로 '맨 위'인 창이 활성화되면 먼저 뜬 펫 창이 그 뒤로 밀리기 때문
        from PyQt5.QtWidgets import QDialog, QMenu
        if QApplication.activePopupWidget() is not None and not force:
            return                                       # 우클릭 메뉴·드롭다운이 열려 있는 동안엔 창 순서를 건드리지 않음 (드롭다운이 닫히거나 가려짐)
        force = force or self.on_top
        for w in self.pet_windows():
            try:
                if not set_topmost(w.winId(), self.on_top, force):
                    want = bool(self.on_top)
                    if bool(w.windowFlags() & Qt.WindowStaysOnTopHint) != want:   # 윈도우가 아니면 Qt 방식으로
                        w.setWindowFlag(Qt.WindowStaysOnTopHint, want); w.show()
            except Exception:
                pass
        self.raise_popups()

    def demote(self, w):
        """맨 위 고정을 풀고 지금 보고 있는 창 바로 뒤로 (위로 튀어나오지 않게)"""
        try:
            h = wintypes.HWND(int(w.winId()))
            if not (user32.GetWindowLongW(h, -20) & 0x8):
                return
            fg = user32.GetForegroundWindow()
            user32.SetWindowPos(h, wintypes.HWND(fg) if fg else wintypes.HWND(-2), 0, 0, 0, 0,
                                0x0001 | 0x0002 | 0x0010 | 0x0200)
        except Exception:
            pass

    def raise_popups(self):
        """우클릭 메뉴·환경설정·물어보기 창은 언제나 펫(캐릭터·말풍선)보다 위에"""
        from PyQt5.QtWidgets import QDialog, QMenu
        dialogs, pops = [], []
        for w in QApplication.topLevelWidgets():
            if not w.isVisible():
                continue
            if isinstance(w, QMenu) or w.windowType() in (Qt.Popup, Qt.ToolTip):
                pops.append(w)                           # 드롭다운 목록·메뉴는 맨 마지막에 (환경설정 창이 덮지 않게)
            elif isinstance(w, QDialog):
                if isinstance(w, (SettingsDialog, HistoryDialog)) and not w.isActiveWindow():
                    self.demote(w)                   # 다른 창을 보고 있으면 환경설정은 그 창 뒤로 (항상 위 X)
                    continue
                dialogs.append(w)
        for w in dialogs + pops:
            try:
                set_topmost(w.winId(), True, True)
            except Exception:
                pass

    def set_on_top(self, on):
        self.on_top = bool(on)
        self.cfg["on_top"] = self.on_top
        self.save_cfg()
        self.keep_on_top(force=True)
        for b in self.buddies:
            if b.surface:
                b.say("맨 위에 있을게요!" if on else "창 뒤에서 놀고 있을게요~", 90)
                break

    def scan(self):
        if not self.climb_windows:
            self.windows = []
            return
        gs = {sc.name(): sc.geometry() for sc in [target_screen()] + [screen_for(c) for c in CHAR_SCREEN]}.values()
        self.windows = [w for w in window_tops()
                        if any(w[2] > g.left() and w[0] < g.right() and g.top() <= w[1] < g.bottom() for g in gs)]

    # ── 윈도우 시작 시 자동 실행 (시작프로그램 폴더에 작은 실행 파일을 만들어 둠) ──
    def autostart_path(self):
        startup = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows",
                               "Start Menu", "Programs", "Startup")
        arg = sys.argv[1] if len(sys.argv) > 1 else self.mode
        safe = "".join(ch if ch.isalnum() else "_" for ch in arg)
        return startup, os.path.join(startup, f"RabbitPet_{safe}.vbs")

    def autostart_on(self):
        try:
            return os.path.exists(self.autostart_path()[1])
        except Exception:
            return False

    def set_autostart(self, on):
        try:
            folder, path = self.autostart_path()
            if not on:
                if os.path.exists(path):
                    os.remove(path)
                return
            if not os.path.isdir(folder):
                return
            exe = sys.executable
            if exe.lower().endswith("python.exe"):          # 창 없이 실행되는 pythonw 사용
                w = exe[:-10] + "pythonw.exe"
                if os.path.exists(w):
                    exe = w
            script = os.path.abspath(sys.argv[0]) if sys.argv[0].endswith(".py") else ENTRY_SCRIPT
            arg = sys.argv[1] if len(sys.argv) > 1 else self.mode
            q = lambda s: '""' + s + '""'
            line = ('Set sh = CreateObject("WScript.Shell")\r\n'
                    f'sh.CurrentDirectory = "{os.path.dirname(script)}"\r\n'
                    f'sh.Run "{q(exe)} {q(script)} {arg}", 0, False\r\n')
            with open(path, "w", encoding="utf-16") as f:       # 한글 경로도 OK
                f.write(line)
        except Exception:
            pass

    def set_screen(self, sc):
        """다른 모니터로 이사: 장면·단체 놀이는 끝내고 모두 새 모니터 하늘에서 뚝"""
        primary = sc is QApplication.primaryScreen()
        SCREEN["name"] = None if primary else sc.name()
        if primary:
            self.cfg.pop("screen", None)
        else:
            self.cfg["screen"] = sc.name()
        self.save_cfg()
        if self.scene:
            self.scene_end()
        if self.group:
            self.group_break()
        self.scan()
        self.all_drop()
