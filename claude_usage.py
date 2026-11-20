# -*- coding: utf-8 -*-
"""Claude 사용량 위젯 — claude.ai '설정 → 사용량' 화면의 숫자(현재 세션·주간 한도)를 작은 창으로 띄워 둠.

- 펫 메뉴 'Claude 사용량 보기'로 켬 (따로 도는 작은 프로그램)
- 숫자는 공식 통로가 없어서, 위젯 안의 작은 브라우저(Edge WebView2)로 claude.ai 에 한 번 로그인해 두고
  사용량 화면을 5분마다 열어 글자만 읽음. 로그인은 이 위젯 전용 저장소(%APPDATA%\\DesktopPet\\claude_usage)에만 남음
- 읽은 숫자는 usage.json 에 저장 → 펫이 80%·95% 넘으면 말풍선으로 알려 줌
"""
import os, sys, json, time, re, threading, datetime

USAGE_URL = "https://claude.ai/settings/usage"
DATA = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "DesktopPet", "claude_usage")
OUT = os.path.join(DATA, "usage.json")
WIN = os.path.join(DATA, "window.json")
EVERY = 300                      # 몇 초마다 새로 읽을지

PCT = re.compile(r"(\d{1,3})\s*%\s*(사용|used)", re.I)
RESET = re.compile(r"(초기화|reset)", re.I)
WEEK = re.compile(r"^(주간\s*한도|weekly)", re.I)
HOME = re.compile(r"^https://claude\.ai/(new|recents|chats?|projects?|$)", re.I)


def parse(text):
    """사용량 화면 글자 → [{label, pct, reset}]
    화면 순서: 이름 줄 → (초기화 시각 줄) → 'NN% 사용됨' 줄. '주간 한도' 제목 아래 줄은 '주간 · ' 를 붙임"""
    lines = [l.strip() for l in str(text or "").splitlines() if l.strip()]
    rows, sec = [], ""
    for i, l in enumerate(lines):
        if WEEK.match(l):
            sec = "주간 · "
            continue
        m = PCT.search(l)
        if not m:
            continue
        j, reset = i - 1, ""
        if j >= 0 and RESET.search(lines[j]) and not PCT.search(lines[j]):
            reset, j = lines[j], j - 1
        label = lines[j] if j >= 0 and not PCT.search(lines[j]) else "?"
        if sec and not label.startswith(("현재", "Current")):
            label = sec + label
        rows.append({"label": label[:28], "pct": max(0, min(100, int(m.group(1)))), "reset": reset[:40]})
    return rows


def save_json(path, d):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass


def load_json(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return {}


UI_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
:root{--bg:rgba(255,247,250,.97);--fg:#4a3a44;--sub:#9a8592;--bar:#eadde4;--ok:#5b8def;--warn:#f0a030;--hot:#e5484d}
*{box-sizing:border-box}html,body{margin:0;height:100%;overflow:hidden;background:#FFF7FA;font:13px 'Malgun Gothic',sans-serif;color:var(--fg)}
#p{margin:0;height:100%;background:var(--bg);border:1px solid #f3c6d8;border-radius:12px;padding:10px 12px 8px;display:flex;flex-direction:column;gap:7px}
#h{display:flex;align-items:center;gap:6px;font-weight:700;color:#d0588a}
#h span{flex:1}
button{border:0;background:#fbe3ee;color:#b0476f;border-radius:7px;padding:2px 7px;font:12px 'Malgun Gothic',sans-serif;cursor:pointer}
button:hover{background:#f7cfe0}
.r{display:flex;flex-direction:column;gap:2px}
.t{display:flex;justify-content:space-between;gap:8px}.t b{font-weight:600}
.k{height:7px;border-radius:4px;background:var(--bar);overflow:hidden}.k i{display:block;height:100%;border-radius:4px;background:var(--ok)}
.s{color:var(--sub);font-size:11px}
#f{color:var(--sub);font-size:11px;margin-top:auto}
</style></head><body><div id="p" class="pywebview-drag-region">
<div id="h"><span class="pywebview-drag-region">Claude 사용량</span><button onclick="pywebview.api.refresh()" title="지금 새로 읽기">↻</button><button onclick="pywebview.api.login()" title="로그인 창 열기/닫기">로그인</button><button onclick="pywebview.api.close()" title="닫기">×</button></div>
<div id="rows"><div class="s">불러오는 중…</div></div>
<div id="f"></div></div>
<script>
function esc(s){return String(s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function render(d){
  var rows=d.rows||[],h='';
  rows.forEach(function(r){var c=r.pct>=95?'var(--hot)':r.pct>=80?'var(--warn)':'var(--ok)';
    h+='<div class="r"><div class="t"><b>'+esc(r.label)+'</b><span>'+r.pct+'%</span></div><div class="k"><i style="width:'+r.pct+'%;background:'+c+'"></i></div>'+(r.reset?'<div class="s">'+esc(r.reset)+'</div>':'')+'</div>'});
  document.getElementById('rows').innerHTML=h||'<div class="s">'+esc(d.status||'아직 숫자가 없어요')+'</div>';
  document.getElementById('f').textContent=(rows.length&&d.status?d.status+' · ':'')+(d.time?'갱신 '+d.time:'');
}
</script></body></html>"""


class Widget:
    def __init__(self, webview):
        self.wv = webview
        self.ui = None
        self.cw = None                # claude.ai 를 여는 브라우저 창 (평소엔 숨김, 로그인할 때만 보임)
        self.cw_shown = False
        self.data = load_json(OUT) or {"rows": [], "status": "", "time": ""}
        self.kick = threading.Event()
        self.alive = True

    # ── 창 ─────────────────────────────
    def make_ui(self):
        pos = load_json(WIN)
        n = max(2, len(self.data.get("rows") or []))
        self.ui = self.wv.create_window("Claude 사용량", html=UI_HTML, js_api=Api(self), width=270, height=74 + 50 * n,
                                        x=pos.get("x"), y=pos.get("y"), frameless=True, easy_drag=False,
                                        on_top=True, resizable=False, background_color="#FFF7FA")
        self.ui.events.loaded += lambda: self.push()
        self.ui.events.moved += lambda x, y: save_json(WIN, {"x": x, "y": y})
        self.ui.events.closed += self.quit

    def make_cw(self):
        self.cw = self.wv.create_window("Claude 로그인 (사용량 위젯 전용)", USAGE_URL, width=980, height=780, hidden=True)
        self.cw_shown = False
        self.cw.events.closed += self._cw_closed

    def _cw_closed(self):
        self.cw = None
        self.cw_shown = False

    def show_cw(self, on):
        if self.cw is None:
            self.make_cw()
        try:
            (self.cw.show if on else self.cw.hide)()
            self.cw_shown = on
        except Exception:
            pass

    def quit(self):
        self.alive = False
        self.kick.set()
        for w in list(self.wv.windows):
            try:
                w.destroy()
            except Exception:
                pass

    # ── 숫자 표시·저장 ──────────────────
    def push(self):
        try:
            if self.ui:
                self.ui.evaluate_js("render(%s)" % json.dumps(self.data, ensure_ascii=False))
                n = max(2, len(self.data.get("rows") or []))
                self.ui.resize(270, 74 + 50 * n)
        except Exception:
            pass

    def set(self, rows=None, status=""):
        if rows is not None:
            self.data["rows"] = rows
        self.data["status"] = status
        self.data["time"] = datetime.datetime.now().strftime("%H:%M")
        self.data["ts"] = time.time()
        save_json(OUT, self.data)
        self.push()

    # ── 읽기 ─────────────────────────────
    def page(self):
        try:
            url = self.cw.get_current_url() or ""
            txt = self.cw.evaluate_js("document.body ? document.body.innerText : ''") or ""
            return url, txt
        except Exception:
            return "", ""

    def read_once(self):
        if self.cw is None:
            self.make_cw()
            time.sleep(2)
        try:
            self.cw.load_url(USAGE_URL)
        except Exception:
            pass
        for _ in range(24):                       # 최대 약 36초 기다리며 글자가 그려지길 기다림
            time.sleep(1.5)
            if not self.alive:
                return
            url, txt = self.page()
            rows = parse(txt)
            if rows:
                self.set(rows, "")
                if self.cw_shown:
                    self.show_cw(False)
                return
            if "/login" in url or "/logout" in url:
                self.set(None, "로그인이 필요해요 — '로그인' 버튼")
                if not self.data.get("rows"):
                    self.show_cw(True)              # 처음이면 로그인 창을 바로 보여 줌
                return
        self.set(None, "숫자를 못 읽었어요 (화면이 바뀌었을 수 있어요)")

    def watch_login(self):
        """로그인 창이 열려 있는 동안: 로그인이 끝나 claude.ai 첫 화면으로 가면 사용량 화면으로 데려감"""
        url, txt = self.page()
        if parse(txt):
            self.set(parse(txt), "")
            self.show_cw(False)
            return True
        if HOME.match(url):
            try:
                self.cw.load_url(USAGE_URL)
            except Exception:
                pass
        return False

    def loop(self):
        time.sleep(1.0)
        self.push()
        last = 0
        while self.alive:
            if self.cw_shown:
                self.watch_login()
                self.kick.wait(3)
                self.kick.clear()
                continue
            if time.time() - last >= EVERY or self.kick.is_set():
                self.kick.clear()
                last = time.time()
                self.read_once()
                continue
            self.kick.wait(5)


class Api:
    def __init__(self, w):
        self._w = w

    def refresh(self):
        self._w.set(None, "읽는 중…")
        if self._w.cw_shown:
            try:
                self._w.cw.load_url(USAGE_URL)
            except Exception:
                pass
        self._w.kick.set()

    def login(self):
        self._w.show_cw(not self._w.cw_shown)
        self._w.kick.set()

    def close(self):
        threading.Thread(target=self._w.quit, daemon=True).start()


def main():
    import webview
    os.makedirs(DATA, exist_ok=True)
    w = Widget(webview)
    w.make_ui()
    w.make_cw()
    kw = dict(private_mode=False, storage_path=os.path.join(DATA, "web"))
    if sys.platform == "win32":
        kw["gui"] = "edgechromium"
    webview.start(w.loop, **kw)


if __name__ == "__main__":
    main()
