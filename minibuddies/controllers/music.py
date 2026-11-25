"""YouTube playback lifecycle and pet reactions."""

import datetime
import os
import random
import re
import sys
import time
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication
from minibuddies.desktop import find_browser
from minibuddies.runtime import BASE, MCP_HOME


DEFAULT_MUSIC = [{"name": "내 재생목록", "url": "https://www.youtube.com/watch?v=JLM7z8afU4s&list=PLehDTIsIFasA"}]

YT_ID = re.compile(r"(?:v=|youtu\.be/|/shorts/|/embed/|/live/)([A-Za-z0-9_-]{11})")

def yt_id(url):
    m = YT_ID.search(str(url or ""))
    return m.group(1) if m else None

def yt_queue_url(songs):
    """여러 곡(유튜브 링크들) → 차례로 재생되는 하나의 유튜브 링크 (watch_videos)"""
    ids = [i for i in (yt_id(x.get("url") if isinstance(x, dict) else x) for x in songs) if i]
    ids = list(dict.fromkeys(ids))[:50]
    return ("https://www.youtube.com/watch_videos?video_ids=" + ",".join(ids)) if ids else None

MUSIC_LINES = ["♪~", "♪ 라라라~", "♬ 둠칫둠칫~", "♪ 이 노래 좋다~", "♬ 같이 불러요~", "♪♪", "♬ 흥얼흥얼~", "♪ 신난다~"]


class MusicController:
    # ── 노래 ─────────────────────────────
    def music_list(self):
        lst = self.cfg.get("music")
        if lst is None:
            lst = [dict(x) for x in DEFAULT_MUSIC]
        return [x for x in lst if isinstance(x, dict) and str(x.get("url", "")).startswith("http")]

    def play_music(self, item=None):
        """유튜브(재생목록) 링크를 기본 브라우저로 열고, 펫들은 노래 모드로 춤추고 흥얼거림"""
        lst = self.music_list()
        if item is None:
            if not lst:
                self.open_settings(); return False
            item = random.choice(lst)
        url, name = item.get("url", ""), item.get("name") or "노래"
        if item.get("songs"):                               # 추천 리스트: 여러 곡을 이어서 재생
            url = yt_queue_url(item["songs"]) or url
        if not self.open_player(url):
            return False
        self.music_on = name
        self.music_end = time.time() + 60 * int(self.cfg.get("music_min", 60))
        if not hasattr(self, "musict"):
            self.musict = QTimer(); self.musict.timeout.connect(self.music_tick)
        self.musict.start(7000)
        live = [b for b in self.buddies if b.surface and b.drag is None]
        for i, b in enumerate(live):
            if self.cfg.get("music_dance", True) and b.state not in self.BUSY:
                b.vx = 0; b.set(random.choice(["dance", "sing"]), random.randint(200, 360))
        if live:
            self.force_say(live[0], f"♪ '{name}' 틀었어요! 같이 들어요~", 6)
        return True

    def open_player(self, url):
        """노래 재생: 기본은 '숨김 플레이어'(화면에 안 보임). 크롬/엣지가 없거나 '브라우저로' 설정이면 기본 브라우저로.
        창을 아예 숨기면(SW_HIDE·화면 밖) 크롬이 '안 보이는 창'으로 보고 재생을 미뤄서, 화면 안에 띄우되 투명·클릭 통과로 만듦"""
        mode = self.cfg.get("music_player", "hidden")
        exe = find_browser() if sys.platform == "win32" and mode in ("hidden", "mini") else None
        self.close_player()
        if exe:
            import subprocess
            prof = os.path.join(MCP_HOME, "music_player")
            os.makedirs(prof, exist_ok=True)
            g = QApplication.primaryScreen().availableGeometry()
            w, h = 420, 260
            try:
                self.yt_proc = subprocess.Popen(
                    [exe, f"--user-data-dir={prof}", f"--app={url}", "--autoplay-policy=no-user-gesture-required",
                     "--no-first-run", "--no-default-browser-check", "--disable-session-crashed-bubble",
                     "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding",
                     "--disable-background-timer-throttling", "--disable-background-media-suspend",
                     "--disable-features=CalculateNativeWinOcclusion",
                     f"--window-size={w},{h}", f"--window-position={g.right() - w - 20},{g.bottom() - h - 20}"],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.yt_shown = mode == "mini"
                if mode == "hidden":                         # 뜨자마자 투명하게 (몇 초 동안 새 창이 생기면 그것도)
                    for k in range(1, 60):
                        QTimer.singleShot(k * 150 if k < 40 else 6000 + k * 400,
                                          lambda: None if getattr(self, "yt_shown", False) else self.player_ghost(True))
                return True
            except Exception:
                self.yt_proc = None
        try:
            import webbrowser
            webbrowser.open(url)
            return True
        except Exception:
            return False

    def player_ghost(self, on):
        """플레이어 창을 투명·클릭 통과·작업표시줄 숨김으로 (on) / 원래대로 (off). 창은 '떠 있는' 상태라 소리는 계속 남"""
        p = getattr(self, "yt_proc", None)
        if not p or p.poll() is not None or sys.platform != "win32":
            return
        import ctypes
        u = ctypes.windll.user32
        for hwnd in self._player_hwnds(p.pid):
            ex = u.GetWindowLongW(hwnd, -20)
            if on:
                ex = (ex | 0x80000 | 0x20 | 0x80) & ~0x40000     # LAYERED | TRANSPARENT | TOOLWINDOW, APPWINDOW 끄기
                u.SetWindowLongW(hwnd, -20, ex)
                u.SetLayeredWindowAttributes(hwnd, 0, 0, 2)      # 완전 투명
            else:
                ex = (ex & ~0x20 & ~0x80) | 0x40000
                u.SetWindowLongW(hwnd, -20, ex)
                u.SetLayeredWindowAttributes(hwnd, 0, 255, 2)
            u.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020)   # 스타일 반영

    def player_show(self, show=True):
        p = getattr(self, "yt_proc", None)
        if not p or p.poll() is not None or sys.platform != "win32":
            return
        import ctypes
        u = ctypes.windll.user32
        self.yt_shown = bool(show)
        if show:
            self.player_ghost(False)
            g = QApplication.primaryScreen().availableGeometry()
            for hwnd in self._player_hwnds(p.pid):
                u.ShowWindow(hwnd, 9)                           # SW_RESTORE
                u.SetWindowPos(hwnd, 0, g.right() - 440, g.bottom() - 280, 420, 260, 0x0004)
                u.SetForegroundWindow(hwnd)
        else:
            self.player_ghost(True)

    def _player_hwnds(self, pid):
        """그 프로세스의 크롬 주 창들 (투명하게 만든 창 포함)"""
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        out = []
        CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def cb(h, _):
            pp = wintypes.DWORD()
            u.GetWindowThreadProcessId(h, ctypes.byref(pp))
            if pp.value == pid and not u.GetWindow(h, 4) and u.IsWindowVisible(h):
                buf = ctypes.create_unicode_buffer(64)
                u.GetClassNameW(h, buf, 64)
                if buf.value.startswith("Chrome_WidgetWin"):
                    out.append(h)
            return True
        u.EnumWindows(CB(cb), 0)
        return out

    def close_player(self):
        p = getattr(self, "yt_proc", None)
        self.yt_proc = None
        if p and p.poll() is None:
            try:
                import subprocess
                subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=8)
            except Exception:
                try:
                    p.terminate()
                except Exception:
                    pass

    def save_playlist(self, name, songs, play=True):
        """추천받은 곡들을 노래 목록에 저장 (한 줄 = 여러 곡이 이어서 나오는 링크)"""
        songs = [x for x in songs if isinstance(x, dict) and yt_id(x.get("url"))]
        url = yt_queue_url(songs)
        if not url:
            return None
        lst = self.music_list()
        name = (name or "추천 리스트").strip()[:40]
        item = {"name": name, "url": url, "songs": [{"title": str(x.get("title") or x.get("name") or "")[:80], "url": x["url"]} for x in songs]}
        lst = [x for x in lst if x.get("name") != name] + [item]
        self.cfg["music"] = lst
        self.save_cfg()
        try:
            with open(os.path.join(BASE, "추천노래.txt"), "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M}] {name}\n" +
                        "\n".join(f"  {i + 1}. {x['title']}  {x['url']}" for i, x in enumerate(item["songs"])) + "\n")
        except Exception:
            pass
        if play:
            self.play_music(item)
        return item

    def stop_music(self, say=True):
        self.close_player()
        if getattr(self, "music_on", None):
            self.music_on = None
            if hasattr(self, "musict"):
                self.musict.stop()
            live = [b for b in self.buddies if b.surface]
            if say and live:
                b = random.choice(live)
                b.vx = 0; b.set("cheer", 90)
                self.force_say(b, "노래 끝~ 즐거웠어요♪", 6)

    def music_tick(self):
        if not getattr(self, "music_on", None):
            return self.musict.stop()
        if time.time() > getattr(self, "music_end", 0):
            return self.stop_music()
        if self.group or self.scene:
            return
        live = [b for b in self.buddies if b.surface and b.drag is None and b.state not in self.BUSY
                and b.state not in ("sleep", "nap")]
        for b in random.sample(live, min(len(live), random.randint(1, 2))):
            if self.cfg.get("music_dance", True):
                b.vx = 0; b.set(random.choice(["dance", "dance", "sing"]), random.randint(160, 300))
            if self.cfg.get("bubbles", True):
                b.say(random.choice(MUSIC_LINES), 90)
