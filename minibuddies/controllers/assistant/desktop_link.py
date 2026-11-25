"""Assistant desktop connection and MCP installation."""

import json
import os
import shutil
import sys
from PyQt5.QtCore import QTimer
from minibuddies.runtime import BASE, MCP_HOME


class DesktopLink:
    def auto_send(self, waited=0):
        """맨 앞 창이 Claude(앱 또는 claude.ai 브라우저 탭)일 때만 입력칸을 눌러 커서를 넣고 Enter.
        다른 창이 앞에 있으면 아무것도 안 누름 (엉뚱한 곳에 Enter 가 들어가지 않게)"""
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
        except Exception:
            return
        hwnd = user32.GetForegroundWindow()
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        exe = ""
        try:
            k32 = ctypes.windll.kernel32
            h = k32.OpenProcess(0x1000, False, pid.value)
            pb = ctypes.create_unicode_buffer(520); sz = wintypes.DWORD(520)
            if h and k32.QueryFullProcessImageNameW(h, 0, pb, ctypes.byref(sz)):
                exe = os.path.basename(pb.value).lower()
            if h:
                k32.CloseHandle(h)
        except Exception:
            pass
        is_claude = exe == "claude.exe" or "Claude" in buf.value
        self.ask_log(f"try{waited} title={buf.value!r} class={cls.value} exe={exe} -> {'Claude' if is_claude else 'skip'}")
        if not is_claude:
            if waited < 20:                              # 창이 뜰 때까지 최대 10초 기다림
                QTimer.singleShot(500, lambda: self.auto_send(waited + 1))
            return
        if not getattr(self, "_send_clicked", False):
            # 입력칸에 커서 넣기: 창 가운데 아래쪽(대화 입력칸 자리)을 한 번 클릭
            r = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            self._send_clicked = True
            QTimer.singleShot(2500, lambda: self._click_send(hwnd, r))   # 페이지가 다 뜰 시간
            return

    def _click_send(self, hwnd, r):
        import ctypes
        user32 = ctypes.windll.user32
        if user32.GetForegroundWindow() != hwnd:
            self.ask_log("foreground changed, skip"); return
        # 질문이 채워진 입력칸 오른쪽 아래의 보내기 버튼 대신, 입력칸 글자 위를 눌러 커서를 넣고 Enter
        w, h = r.right - r.left, r.bottom - r.top
        from ctypes import wintypes
        pts = [None, (0.5, 0.80), (0.5, 0.62)]          # 1) 그냥 Enter  2~3) 입력칸 자리 클릭 후 Enter
        def step(i=0):
            if i >= len(pts) or user32.GetForegroundWindow() != hwnd:
                self._send_clicked = False; return
            if pts[i]:
                x, y = int(r.left + w * pts[i][0]), int(r.top + h * pts[i][1])
                old = wintypes.POINT(); user32.GetCursorPos(ctypes.byref(old))
                user32.SetCursorPos(x, y)
                user32.mouse_event(0x0002, 0, 0, 0, 0); user32.mouse_event(0x0004, 0, 0, 0, 0)
                user32.SetCursorPos(old.x, old.y)
                user32.keybd_event(0x23, 0, 0, 0); user32.keybd_event(0x23, 0, 2, 0)    # End (글자 끝으로)
            user32.keybd_event(0x0D, 0, 0, 0); user32.keybd_event(0x0D, 0, 2, 0)        # Enter
            self.ask_log(f"enter #{i} {('click ' + str(pts[i])) if pts[i] else ''} (win {w}x{h})")
            QTimer.singleShot(900, lambda: step(i + 1))   # 이미 보냈으면 빈 칸이라 Enter 해도 아무 일 없음
        step()

    def claude_cfg_paths(self):
        roam = os.environ.get("APPDATA", "")
        paths = [os.path.join(roam, "Claude", "claude_desktop_config.json")]
        pk = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Packages")
        if os.path.isdir(pk):
            for d in os.listdir(pk):
                if d.lower().startswith("claude"):
                    c = os.path.join(pk, d, "LocalCache", "Roaming", "Claude")
                    if os.path.isdir(c):
                        paths.append(os.path.join(c, "claude_desktop_config.json"))
        return paths

    def mcp_state(self):
        """'ok' (이미 연결 설정 있음) / 'missing'"""
        dst = os.path.join(MCP_HOME, "pet_mcp.py")
        for path in self.claude_cfg_paths():
            try:
                ent = json.load(open(path, encoding="utf-8")).get("mcpServers", {}).get("desktop-pet")
            except Exception:
                continue
            if ent and os.path.normcase(os.path.abspath((ent.get("args") or [""])[-1])) == os.path.normcase(os.path.abspath(dst)):
                return "ok"
        return "missing"

    def _ps(self, script, timeout=15):
        import subprocess
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                               capture_output=True, text=True, timeout=timeout,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return r.stdout
        except Exception:
            return ""

    def install_mcp(self, restart=True):
        """딸깍 연결: pet_mcp.py 를 고정 위치에 두고, Claude 를 잠깐 끄고, 설정 파일에 desktop-pet 을 넣고, 다시 켬.
        (Claude 가 켜져 있는 동안 설정 파일을 고치면 Claude 가 자기 설정으로 다시 덮어써 버림)"""
        import subprocess, time
        try:
            os.makedirs(MCP_HOME, exist_ok=True)
            dst = os.path.join(MCP_HOME, "pet_mcp.py")
            shutil.copy(os.path.join(BASE, "pet_mcp.py"), dst)       # 늘 최신 서버로
            already = self.mcp_state() == "ok"
            exe = sys.executable
            if exe.lower().endswith("pythonw.exe") and os.path.exists(exe[:-11] + "python.exe"):
                exe = exe[:-11] + "python.exe"
            # 1) Claude 위치 기억해 두고 끄기
            info = self._ps("$p=Get-Process -Name claude -ErrorAction SilentlyContinue | Select-Object -First 1;"
                            "if($p){'PATH:'+$p.Path};"
                            "$a=Get-StartApps | Where-Object {$_.Name -eq 'Claude'} | Select-Object -First 1;"
                            "if($a){'APPID:'+$a.AppID}") if restart and os.name == "nt" else ""
            was_running = "PATH:" in info
            path_exe = next((l[5:].strip() for l in info.splitlines() if l.startswith("PATH:")), "")
            appid = next((l[6:].strip() for l in info.splitlines() if l.startswith("APPID:")), "")
            if already and not restart:
                return True, "이미 연결 설정이 들어 있어요."
            if was_running:
                subprocess.run(["taskkill", "/IM", "claude.exe", "/T", "/F"], capture_output=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                for _ in range(20):                                   # 완전히 꺼질 때까지
                    time.sleep(0.4)
                    if "claude" not in self._ps("Get-Process -Name claude -ErrorAction SilentlyContinue | Select -Expand Name", 5).lower():
                        break
                time.sleep(0.8)
            # 2) 설정 넣기 (다른 내용은 그대로 두고 desktop-pet 만)
            done = []
            for path in self.claude_cfg_paths():
                if not os.path.isdir(os.path.dirname(path)) and done:
                    continue
                os.makedirs(os.path.dirname(path), exist_ok=True)
                cfg = {}
                if os.path.exists(path):
                    shutil.copy(path, path + ".bak")
                    try:
                        cfg = json.load(open(path, encoding="utf-8"))
                    except Exception:
                        continue
                old = cfg.get("mcpServers", {}).get("desktop-pet")
                if not (old and (old.get("args") or [""])[-1] == dst):
                    cfg.setdefault("mcpServers", {})["desktop-pet"] = {"command": exe, "args": [dst]}
                    json.dump(cfg, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                done.append(path)
            # 3) Claude 다시 켜기
            if was_running:
                if appid:
                    subprocess.Popen(["explorer.exe", "shell:AppsFolder\\" + appid])
                elif path_exe:
                    subprocess.Popen([path_exe])
            if not done:
                return False, "Claude 설정 파일을 찾지 못했어요. Claude 데스크톱이 설치돼 있는지 확인해 주세요."
            tail = ("Claude 를 다시 켜는 중이에요. 다 켜지면 펫이 'Claude 랑 연결됐어요!' 하고 인사해요."
                    if was_running else "Claude 데스크톱을 켜면 바로 연결돼요.")
            return True, ("이미 연결돼 있어서 최신으로 정리만 했어요!\n\n" if already else "연결 완료!\n\n") + tail
        except Exception as e:
            return False, f"실패했어요: {e}"
