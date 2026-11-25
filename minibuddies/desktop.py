"""Monitor selection, cursor target and Windows integration."""

import os
import sys
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QApplication


class _CursorTarget:
    """커서 쫓기용 가짜 목표 (go_to 에 친구 대신 넣음)"""
    S = 0
    surface = None
    @property
    def cx(self):
        return QCursor.pos().x()
CURSOR = _CursorTarget()

# ── 띄울 모니터 (settings.json "screen": 모니터 이름, 없으면 주 모니터) ─────────
SCREEN = {"name": None}

def target_screen():
    for sc in QApplication.screens():
        if SCREEN["name"] and sc.name() == SCREEN["name"]:
            return sc
    return QApplication.primaryScreen()       # 저장한 모니터가 빠져 있으면 주 모니터로

CHAR_SCREEN = {}                              # 캐릭터별 모니터 (settings.json "char_screen")

def screen_for(char):
    want = CHAR_SCREEN.get(char)
    if want:
        for sc in QApplication.screens():
            if sc.name() == want:
                return sc
    return target_screen()

# ── 창 목록 (윈도우 전용) ─────────────────────────────
try:
    import ctypes
    from ctypes import wintypes
    user32, dwmapi = ctypes.windll.user32, ctypes.windll.dwmapi
    def window_tops():
        res = []
        CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def cb(hwnd, _):
            if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                return True
            if user32.GetWindowTextLengthW(hwnd) == 0:
                return True
            cloaked = ctypes.c_int(0)
            dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), 4)
            if cloaked.value:
                return True
            r = wintypes.RECT()
            if dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:
                user32.GetWindowRect(hwnd, ctypes.byref(r))
            if r.right - r.left > 150 and r.bottom - r.top > 80:
                res.append((r.left, r.top, r.right))
            return True
        user32.EnumWindows(CB(cb), 0)
        return res
    def set_topmost(wid, on, force=False):
        """윈도우: 맨 위 고정/해제 (창을 깜빡이지 않고, 포커스도 안 뺏음). 이미 그 상태면 건드리지 않음(끊김 방지)"""
        h = wintypes.HWND(int(wid))
        if not force and bool(user32.GetWindowLongW(h, -20) & 0x8) == bool(on):
            return True
        user32.SetWindowPos(wintypes.HWND(int(wid)), wintypes.HWND(-1 if on else -2), 0, 0, 0, 0,
                            0x0001 | 0x0002 | 0x0010 | 0x0200)
        return True
except Exception:
    def window_tops():
        return []
    def set_topmost(wid, on, force=False):
        return False

def find_browser():
    """숨김 플레이어로 쓸 크롬/엣지 (따로 쓰는 프로필이라 평소 브라우저와 안 섞임)"""
    pf, pf86, la = (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                    os.environ.get("LOCALAPPDATA", ""))
    for c in [os.path.join(pf, r"Google\Chrome\Application\chrome.exe"), os.path.join(pf86, r"Google\Chrome\Application\chrome.exe"),
              os.path.join(la, r"Google\Chrome\Application\chrome.exe"),
              os.path.join(pf86, r"Microsoft\Edge\Application\msedge.exe"), os.path.join(pf, r"Microsoft\Edge\Application\msedge.exe")]:
        if c and os.path.exists(c):
            return c
    return None

def pid_windows(pid):
    """그 프로세스의 보이는 창들 (윈도우 전용)"""
    out = []
    if sys.platform != "win32":
        return out
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _):
        p = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and u.IsWindowVisible(h) and not u.GetWindow(h, 4):   # 4 = GW_OWNER: 주 창만
            out.append(h)
        return True
    u.EnumWindows(CB(cb), 0)
    return out
