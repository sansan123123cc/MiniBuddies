# -*- coding: utf-8 -*-
"""사용량 위젯용 '진짜 브라우저' — 구글 로그인이 필요한 곳(Gemini, 구글로 가입한 ChatGPT)을 읽을 때 씀.

위젯 안의 작은 브라우저(WebView2)에선 구글이 로그인을 막아 두어서(2021년부터 앱 안 브라우저 차단),
이 PC 에 깔린 크롬(없으면 엣지·웨일)을 '위젯 전용 프로필'(%APPDATA%\\DesktopPet\\claude_usage\\real_browser)로 따로 띄움.
- 로그인할 때만 보이는 창으로 띄움 → 로그인이 끝나 사용량 숫자가 보이면 창을 저절로 닫음
- 평소엔 화면 없는(headless) 모드로 조용히 띄워 두고 사용량 페이지 글자만 읽음
- 평소 쓰는 크롬과 프로필이 달라서 서로 섞이지 않음. 읽은 글자는 이 PC 밖으로 안 나감
브라우저와는 크롬 개발자 도구 통로(127.0.0.1 전용 포트)로만 이야기함 — 추가 설치 부품 없이 파이썬 기본 기능만 씀
"""
import os, re, json, time, socket, base64, struct, subprocess

# ── 사이트별 정보 ─────────────────────────────
SITES = {
    "gpt": {"name": "ChatGPT", "url": "https://chatgpt.com/settings/usage", "host": "chatgpt.com"},
    "gem": {"name": "Gemini", "url": "https://gemini.google.com/usage", "host": "gemini.google.com"},
}
# 제목 줄 (이 줄 아래 몇 줄 안에 % 와 초기화 시각이 있음)
TITLES = {
    "gpt": re.compile(r"^(5\s*시간\s*단위\s*한도|주간\s*사용\s*한도|5[-\s]?hour\b.*limit|weekly\b.*limit)$", re.I),
    "gem": re.compile(r"^(현재\s*사용량|주간\s*한도|current\s+usage|weekly\s+(usage|limit))$", re.I),
}
USED = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%\s*(사용|used)", re.I)
LEFT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%\s*(남음|남았|left|remaining)", re.I)
RESET = re.compile(r"(초기화|reset)", re.I)
SHORT = {"5시간 단위 한도": "5시간 한도", "주간 사용 한도": "주간 한도"}
LOGIN_WORD = re.compile(r"(^|\n)\s*(로그인|log\s*in|sign\s*in)\s*($|\n)", re.I)
CHALLENGE = re.compile(r"(just a moment|verify you are human|사람인지 확인|잠시만 기다리십시오|checking your browser)", re.I)
AUTH_HOST = re.compile(r"^https://(accounts\.google\.com|auth\.openai\.com|auth0\.openai\.com)/", re.I)


LOG_MAX = 60000


def log(d, msg):
    """real_browser/log.txt 에 한 줄 (문제 생겼을 때 원인 찾기용, 오래된 건 잘라 냄)"""
    try:
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "log.txt")
        if os.path.exists(p) and os.path.getsize(p) > LOG_MAX:
            old = open(p, encoding="utf-8", errors="replace").read()[-LOG_MAX // 2:]
            open(p, "w", encoding="utf-8").write(old)
        with open(p, "a", encoding="utf-8") as f:
            f.write(time.strftime("%m-%d %H:%M:%S ") + msg + "\n")
    except Exception:
        pass


def parse(site, text):
    """사용량 페이지 글자 → [{label, pct(사용한 %), reset}]"""
    lines = [l.strip() for l in str(text or "").splitlines() if l.strip()]
    tre = TITLES[site]
    rows = []
    for i, l in enumerate(lines):
        if not tre.match(l):
            continue
        pct, reset = None, ""
        for x in lines[i + 1:i + 6]:
            if tre.match(x):
                break
            m = USED.search(x)
            if m and pct is None:
                pct = float(m.group(1))
                continue
            m = LEFT.search(x)
            if m and pct is None:
                pct = 100 - float(m.group(1))
                continue
            if RESET.search(x) and not reset and len(x) < 50:
                reset = x
        if pct is None:
            continue
        rows.append({"label": SHORT.get(re.sub(r"\s+", " ", l), l)[:20],
                     "pct": max(0, min(100, int(round(pct)))), "reset": reset[:40]})
    return rows


# ── 크롬 개발자 도구 통로 (아주 작은 웹소켓) ─────────────
class WS:
    def __init__(self, url, timeout=10):
        m = re.match(r"ws://([^/:]+):(\d+)(/.*)", url)
        if not m:
            raise ValueError("bad ws url")
        host, port, path = m.group(1), int(m.group(2)), m.group(3)
        self.s = socket.create_connection((host, port), timeout)
        self.s.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall(("GET %s HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n" % (path, host, port, key)).encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            c = self.s.recv(4096)
            if not c:
                raise IOError("closed")
            buf += c
        head, self.buf = buf.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise IOError("ws refused")

    def _frame(self, op, data):
        n = len(data)
        h = bytes([0x80 | op])
        if n < 126:
            h += bytes([0x80 | n])
        elif n < 65536:
            h += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            h += bytes([0x80 | 127]) + struct.pack(">Q", n)
        mask = os.urandom(4)
        self.s.sendall(h + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def send(self, text):
        self._frame(1, text.encode("utf-8"))

    def _read(self, n):
        while len(self.buf) < n:
            c = self.s.recv(65536)
            if not c:
                raise IOError("closed")
            self.buf += c
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self):
        msg = b""
        while True:
            b1, b2 = self._read(2)
            op, n = b1 & 0x0F, b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            mask = self._read(4) if b2 & 0x80 else None
            data = self._read(n)
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if op == 9:
                self._frame(10, data)
                continue
            if op == 8:
                raise IOError("closed")
            if op in (0, 1, 2):
                msg += data
                if b1 & 0x80:
                    return msg.decode("utf-8", "replace")

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


def cdp(ws_url, method, params=None, timeout=10):
    ws = WS(ws_url, timeout)
    try:
        ws.send(json.dumps({"id": 1, "method": method, "params": params or {}}))
        end = time.time() + timeout
        while time.time() < end:
            m = json.loads(ws.recv())
            if m.get("id") == 1:
                if "error" in m:
                    raise IOError(str(m["error"]))
                return m.get("result") or {}
        raise IOError("timeout")
    finally:
        ws.close()


def http(port, method, path, timeout=5):
    import http.client
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        c.request(method, path)
        r = c.getresponse()
        return json.loads(r.read().decode("utf-8") or "null")
    finally:
        c.close()


def find_browser():
    """크롬 → 엣지 → 웨일 순서로 찾음 → (경로, 종류)"""
    env = os.environ
    bases = [env.get("ProgramFiles"), env.get("ProgramFiles(x86)"), env.get("LOCALAPPDATA"), env.get("ProgramW6432")]
    bases = [b for b in dict.fromkeys(bases) if b]
    for kind, parts in (("chrome", ("Google", "Chrome", "Application", "chrome.exe")),
                        ("edge", ("Microsoft", "Edge", "Application", "msedge.exe")),
                        ("whale", ("Naver", "Naver Whale", "Application", "whale.exe"))):
        for b in bases:
            p = os.path.join(b, *parts)
            if os.path.isfile(p):
                return p, kind
    for name, kind in (("google-chrome", "chrome"), ("chromium", "chrome"), ("chromium-browser", "chrome")):
        import shutil
        p = shutil.which(name)
        if p:
            return p, kind
    return None, None


def user_agent(exe, kind):
    """화면 없는 모드는 'HeadlessChrome' 이라고 밝혀서 막힐 수 있음 → 보통 크롬처럼 보이게"""
    major = "131"
    try:
        d = os.path.dirname(exe)
        vs = [x for x in os.listdir(d) if re.match(r"^\d+\.\d+\.\d+\.\d+$", x)]
        if vs:
            major = sorted(vs, key=lambda v: [int(p) for p in v.split(".")])[-1].split(".")[0]
    except Exception:
        pass
    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/%s.0.0.0 Safari/537.36" % major)
    if kind == "edge":
        ua += " Edg/%s.0.0.0" % major
    return ua


class RealBrowser:
    """위젯 전용 프로필로 띄운 진짜 브라우저 하나. mode: 'hidden'(화면 없음) / 'login'(보이는 창) / 'offscreen'(화면 밖 창)"""

    def __init__(self, data_dir):
        self.dir = os.path.join(data_dir, "real_browser")
        self.prof = os.path.join(self.dir, "profile")
        self.exe, self.kind = find_browser()
        self.proc = None
        self.mode = None
        self.port = None
        cfg = self.cfg()
        self.quiet = cfg.get("quiet") or "hidden"     # 평소 읽기 방식 (막히면 offscreen 으로 바꿔 기억)

    def cfg(self):
        try:
            return json.load(open(os.path.join(self.dir, "cfg.json"), encoding="utf-8"))
        except Exception:
            return {}

    def save_cfg(self, **kw):
        c = self.cfg()
        c.update(kw)
        try:
            os.makedirs(self.dir, exist_ok=True)
            json.dump(c, open(os.path.join(self.dir, "cfg.json"), "w", encoding="utf-8"))
        except Exception:
            pass

    @property
    def name(self):
        return {"chrome": "크롬", "edge": "엣지", "whale": "웨일"}.get(self.kind, "브라우저")

    def running(self):
        if self.mode == "login":                      # 로그인 창은 통로 없이 띄움 → 프로그램이 살아 있는지만
            return self.proc is not None and self.proc.poll() is None
        return self.proc is not None and self.proc.poll() is None and self.port is not None

    def _port_file(self):
        return os.path.join(self.prof, "DevToolsActivePort")

    def _alive_port(self, port):
        try:
            return bool(http(port, "GET", "/json/version", 2))
        except Exception:
            return False

    def kill_orphan(self):
        """지난번 위젯이 갑자기 꺼져 남은 브라우저 정리 (같은 프로필을 잡고 있으면 새로 못 띄움)"""
        c = self.cfg()
        pid, port = c.get("pid"), c.get("port")
        lp = c.get("login_pid")
        if lp and os.name == "nt":                    # 지난번 로그인 창이 남아 있으면 (같은 브라우저 프로그램일 때만) 닫음
            try:
                out = subprocess.run(["tasklist", "/FI", "PID eq %d" % int(lp), "/NH"], capture_output=True, text=True,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.lower()
                if os.path.basename(self.exe or "x").lower() in out:
                    subprocess.run(["taskkill", "/T", "/PID", str(lp)], capture_output=True,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    time.sleep(1.5)
            except Exception:
                pass
            self.save_cfg(login_pid=None)
        if pid and port and self._alive_port(port):
            try:
                ws = http(port, "GET", "/json/version", 2).get("webSocketDebuggerUrl")
                cdp(ws, "Browser.close", timeout=3)
            except Exception:
                pass
            time.sleep(1.5)
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.save_cfg(pid=None, port=None)

    def stop(self):
        if self.port:
            try:
                ws = http(self.port, "GET", "/json/version", 2).get("webSocketDebuggerUrl")
                cdp(ws, "Browser.close", timeout=3)
            except Exception:
                pass
        p = self.proc
        if p is not None:
            for _ in range(20):
                if p.poll() is not None:
                    break
                time.sleep(0.25)
            if p.poll() is None:
                try:
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    else:
                        p.kill()
                except Exception:
                    pass
        self.proc, self.mode, self.port = None, None, None
        self.save_cfg(pid=None, port=None, login_pid=None)

    def start(self, mode, urls):
        """브라우저를 띄우고 통로 포트를 얻음. 실패하면 이유 글자를 돌려줌 (성공 None)"""
        if not self.exe:
            return "크롬·엣지를 못 찾았어요"
        self.stop()
        self.kill_orphan()
        os.makedirs(self.prof, exist_ok=True)
        try:
            os.remove(self._port_file())
        except Exception:
            pass
        # 로그인 창엔 개발자 도구 통로를 안 엶 — 통로가 열린 브라우저는 구글이 '안전하지 않은 브라우저'로 보고 로그인을 막음
        args = [self.exe, "--user-data-dir=" + self.prof] + ([] if mode == "login" else ["--remote-debugging-port=0"]) + [
                "--no-first-run",
                "--no-default-browser-check", "--disable-background-mode", "--disable-sync",
                "--disable-features=msEdgeStartupBoost,msImplicitSignin,Translate", "--lang=ko-KR"]
        if mode == "hidden":
            args += ["--headless=new", "--window-size=1280,900", "--user-agent=" + user_agent(self.exe, self.kind),
                     "--mute-audio"]
        elif mode == "offscreen":
            args += ["--window-position=-32000,-32000", "--window-size=1100,850", "--mute-audio"]
        else:
            args += ["--window-size=1100,860", "--window-position=120,60"]
        args += list(urls)
        log(self.dir, "start %s %s (%s)" % (mode, self.kind, self.exe))
        if mode == "login" and os.name == "nt":
            try:                                      # 위젯을 누른 직후라 앞으로 나올 수 있게 허락 (안 그러면 창이 뒤에 숨음)
                import ctypes
                ctypes.windll.user32.AllowSetForegroundWindow(-1)
            except Exception:
                pass
        try:
            self.proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL,
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                                         if mode != "login" else 0)
        except Exception as e:
            return "%s 를 못 켰어요 (%s)" % (self.name, e)
        self.mode = mode
        if mode == "login":
            self.save_cfg(login_pid=self.proc.pid)
            time.sleep(2)
            if self.proc.poll() is not None:
                log(self.dir, "  login window exited early code %s" % self.proc.returncode)
                self.proc, self.mode = None, None
                return "%s 로그인 창이 바로 꺼졌어요" % self.name
            return None
        for _ in range(60):
            time.sleep(0.25)
            try:
                port = int(open(self._port_file(), encoding="utf-8").read().split()[0])
                if self._alive_port(port):
                    self.port = port
                    self.save_cfg(pid=self.proc.pid, port=port)
                    log(self.dir, "  ready port %s" % port)
                    return None
            except Exception:
                pass
            if self.proc.poll() is not None:
                log(self.dir, "  exited early code %s" % self.proc.returncode)
                break
        log(self.dir, "  devtools port never opened")
        self.stop()
        return "%s 통로가 안 열렸어요 (다른 창이 같은 프로필을 잡고 있을 수 있어요)" % self.name

    def pages(self):
        try:
            return [t for t in (http(self.port, "GET", "/json/list") or []) if t.get("type") == "page"]
        except Exception:
            return []

    def tab(self, site, create=True):
        host = SITES[site]["host"]
        ps = self.pages()
        for t in ps:
            if host in (t.get("url") or ""):
                return t
        # 이 사이트 로그인 중(구글·오픈AI 로그인 화면)인 탭
        for t in ps:
            u = t.get("url") or ""
            if AUTH_HOST.match(u) and (site == "gem") == ("google" in u):
                return t
        if not create:
            return None
        try:
            from urllib.parse import quote
            return http(self.port, "PUT", "/json/new?" + quote(SITES[site]["url"], safe=":/?=&"))
        except Exception:
            return None

    def look(self, t):
        """탭의 지금 주소·글자"""
        try:
            r = cdp(t["webSocketDebuggerUrl"], "Runtime.evaluate", {
                "expression": "JSON.stringify({u:location.href,t:document.body?document.body.innerText:'',ti:document.title})",
                "returnByValue": True}, timeout=8)
            return json.loads(r.get("result", {}).get("value") or "{}")
        except Exception:
            return {}

    def title(self, t):
        """탭 제목·주소를 페이지에 붙지 않고 목록으로만 봄 (Cloudflare '잠시만 기다리십시오' 확인 중엔 페이지를 건드리면 안 끝남)"""
        for x in self.pages():
            if x.get("id") == t.get("id"):
                return x.get("title") or "", x.get("url") or ""
        return "", ""

    def checking(self, t):
        ti, _ = self.title(t)
        return bool(CHALLENGE.search(ti))

    def go(self, t, url):
        try:
            cdp(t["webSocketDebuggerUrl"], "Page.navigate", {"url": url}, timeout=8)
        except Exception:
            pass

    def front(self):
        """로그인 창을 맨 앞으로 (다른 창 뒤에 숨지 않게)"""
        try:
            for t in self.pages():
                try:
                    w = cdp(http(self.port, "GET", "/json/version", 2)["webSocketDebuggerUrl"],
                            "Browser.getWindowForTarget", {"targetId": t["id"]}, timeout=4)
                    cdp(http(self.port, "GET", "/json/version", 2)["webSocketDebuggerUrl"],
                        "Browser.setWindowBounds", {"windowId": w["windowId"], "bounds": {"windowState": "normal"}},
                        timeout=4)
                except Exception:
                    pass
                break
        except Exception:
            pass

    def read(self, site, wait=30, cancel=None):
        """사용량 페이지를 새로 열어 읽음 → (rows, 상태) 상태: ok / login / blocked / fail / cancel"""
        t = self.tab(site)
        if not t:
            log(self.dir, "read %s: no tab" % site)
            return [], "fail"
        self.go(t, SITES[site]["url"])
        t0 = time.time()
        last = {}
        while time.time() - t0 < wait:
            if cancel and cancel():
                return [], "cancel"
            time.sleep(1.5)
            if self.checking(t):                      # 사람 확인 중 → 페이지에 붙지 않고 기다림
                last = {"ti": "Just a moment"}
                continue
            p = self.look(t)
            last = p or last
            rows = parse(site, p.get("t"))
            if rows:
                return rows, "ok"
            u = p.get("u") or ""
            if AUTH_HOST.match(u):
                return [], "login"
            # 로그아웃 상태면 첫 화면 '로그인' 버튼만 보임 → 오래 안 기다림
            if time.time() - t0 > 7 and LOGIN_WORD.search(p.get("t") or "") and not RESET.search(p.get("t") or ""):
                return [], "login"
        log(self.dir, "read %s: gave up at %s / %r" % (site, (last.get("u") or "")[:80], (last.get("t") or "")[:160]))
        txt = (last.get("t") or "") + "\n" + (last.get("ti") or "")
        if CHALLENGE.search(txt):
            return [], "blocked"
        if LOGIN_WORD.search(last.get("t") or "") or AUTH_HOST.match(last.get("u") or ""):
            return [], "login"
        return [], "fail"

    def watch_login(self, site, nudged):
        """보이는 로그인 창: 숫자가 보이면 rows, 로그인 끝나 사이트 첫 화면이면 사용량 화면으로 데려감"""
        t = self.tab(site, create=False)
        if not t:
            return None
        if self.checking(t):                          # 사람 확인 중엔 페이지에 안 붙음 (붙으면 확인이 안 끝날 수 있음)
            if time.time() - nudged.get("_cf", 0) > 30:
                nudged["_cf"] = time.time()
                log(self.dir, "login %s: challenge page, waiting" % site)
            return None
        p = self.look(t)
        rows = parse(site, p.get("t"))
        if rows:
            return rows
        u = p.get("u") or ""
        host = SITES[site]["host"]
        if (host in u and SITES[site]["url"] not in u and not LOGIN_WORD.search(p.get("t") or "")
                and time.time() - nudged.get(site, 0) > 12):
            nudged[site] = time.time()
            self.go(t, SITES[site]["url"])
        return None
