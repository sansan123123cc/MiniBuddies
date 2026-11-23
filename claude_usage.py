# -*- coding: utf-8 -*-
"""Claude 사용량 위젯 — claude.ai '설정 → 사용량' 화면의 숫자(현재 세션·주간 한도)를 작은 창으로 띄워 둠.

- 펫 메뉴 'Claude 사용량 보기'로 켬 (따로 도는 작은 프로그램)
- 숫자는 공식 통로가 없어서, 위젯 안의 작은 브라우저(Edge WebView2)로 claude.ai 에 한 번 로그인해 두고
  사용량 화면을 5분마다 열어 글자만 읽음. 로그인은 이 위젯 전용 저장소(%APPDATA%\\DesktopPet\\claude_usage)에만 남음
- 읽은 숫자는 usage.json 에 저장 → 펫이 80%·95% 넘으면 말풍선으로 알려 줌
- NovelAI 도 같이: 위젯 전용 브라우저로 novelai.net 에 한 번 로그인해 두면, 그 페이지 안에서 구독 상태
  (V5 같은 최신 모델의 남은 사용량 %, 다음 1% 충전까지 시간, Anlas)만 읽어 옴. 로그인 정보는 페이지 밖으로 안 나감
"""
import os, sys, json, time, re, threading, datetime

USAGE_URL = "https://claude.ai/settings/usage"
DATA = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "DesktopPet", "claude_usage")
OUT = os.path.join(DATA, "usage.json")
WIN = os.path.join(DATA, "window.json")
NAI_TOKEN = os.path.join(DATA, "nai_token.txt")   # NovelAI '영구 API 토큰'(pst-…) — 이 PC 에만 저장
NAI_API = ("https://image.novelai.net/user/subscription", "https://api.novelai.net/user/subscription")
EVERY = 300                      # 몇 초마다 새로 읽을지

PCT = re.compile(r"(\d{1,3})\s*%\s*(사용|used)", re.I)
RESET = re.compile(r"(초기화|reset)", re.I)
WEEK = re.compile(r"^(주간\s*한도|weekly)", re.I)
NAI_URL = "https://novelai.net/image"
NAI_HOME = re.compile(r"^https://novelai\.net/", re.I)
# novelai.net 페이지 안에서만 실행: 그 페이지의 로그인으로 구독 상태를 물어보고 결과만 window.__nai 에 남김
# '로그인 상태 유지'를 안 켜면 NovelAI 는 로그인 정보를 sessionStorage 에만 둠 → 거기서도 찾고, 위젯 전용 창이니 localStorage 로 옮겨 다음 실행에도 유지
NAI_JS = r"""(function(){try{var s=JSON.parse(localStorage.getItem('session')||'null');
if(!s||!s.auth_token){s=JSON.parse(sessionStorage.getItem('session')||'null');if(s&&s.auth_token){try{localStorage.setItem('session',JSON.stringify(s))}catch(e){}}}
if(!s||!s.auth_token){window.__nai={login:true};return 'login'}
window.__nai=null;
fetch('https://image.novelai.net/user/subscription',{headers:{Authorization:'Bearer '+s.auth_token}})
.then(function(r){return r.json()}).then(function(j){window.__nai={ok:true,j:j}})
.catch(function(e){window.__nai={err:String(e)}});return 'started'}catch(e){window.__nai={err:String(e)};return 'err'}})()"""


def dur(sec):
    """초 → '1시간 40분' / '40분'"""
    try:
        m = max(0, int(sec)) // 60
    except Exception:
        return ""
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    return ((f"{d}일 " if d else "") + (f"{h}시간 " if h else "") + (f"{m}분" if m or not (d or h) else "")).strip()


# 남은 장수: API 는 %만 줌. NovelAI 화면의 '12% remaining (~208 images)'·'14.3% (~247 images)' 로 맞춘 비율
# (보통 해상도·28스텝 V5 기준 1% ≈ 17.34장)
NAI_IMG_PER_PCT = 17.34


def nai_parse(j):
    """구독 상태 JSON → {pct, anlas, next} / 로그인 필요면 None"""
    if not isinstance(j, dict) or j.get("statusCode"):
        return None
    u = j.get("usage") or {}
    t = j.get("trainingStepsLeft") or {}
    anlas = int(t.get("fixedTrainingStepsLeft") or 0) + int(t.get("purchasedTrainingSteps") or 0)
    pct = max(0, min(100, int(u.get("percent") or 0)))
    nxt = "가득 찼어요" if pct >= 100 else ("다음 1% 충전까지 " + dur(u.get("timeUntilNextPercent"))
                                       if u.get("timeUntilNextPercent") is not None else "")
    if u.get("isNegative"):
        nxt = "한도를 넘겨서 지금은 Anlas 가 들어가요"
    return {"pct": pct, "imgs": int(pct * NAI_IMG_PER_PCT), "anlas": anlas, "next": nxt, "opus": j.get("tier") == 3}


HOME = re.compile(r"^https://claude\.ai/(new|recents|chats?|projects?|$)", re.I)


def nai_token():
    try:
        with open(NAI_TOKEN, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def nai_fetch(token):
    """영구 API 토큰으로 구독 상태를 직접 물어봄 → (결과 dict 또는 None, 상태 글자)"""
    import urllib.request, urllib.error
    last = "NovelAI 에 연결을 못 했어요"
    for url in NAI_API:
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token, "Accept": "application/json",
                                                   "User-Agent": "Mozilla/5.0 (DesktopPet usage widget)"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                n = nai_parse(json.loads(r.read().decode("utf-8")))
                if n:
                    return n, ""
                last = "NovelAI 응답을 못 읽었어요"
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return None, "토큰이 맞지 않아요 — 다시 붙여 넣어 주세요"
            last = "NovelAI 응답 오류 (%s)" % e.code
        except Exception:
            pass
    return None, last


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
#nai{display:flex;flex-direction:column;gap:2px;border-top:1px dashed #f3c6d8;padding-top:6px}#nai:empty{display:none}
</style></head><body><div id="p" class="pywebview-drag-region">
<div id="h"><span class="pywebview-drag-region">Claude 사용량</span><button onclick="pywebview.api.refresh()" title="지금 새로 읽기">↻</button><button id="lb" onclick="pywebview.api.login()" title="로그인 창 열기/닫기" hidden>로그인</button><button onclick="pywebview.api.close()" title="닫기">×</button></div>
<div id="rows"><div class="s">불러오는 중…</div></div>
<div id="nai"></div>
<div id="f"></div></div>
<script>
function esc(s){return String(s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function renderNai(n){
  var el=document.getElementById('nai');
  if(!n){el.innerHTML='';return}
  var a=document.activeElement;if(a&&a.id==='nt'&&a.value)return;
  var btn='<button onclick="pywebview.api.nai_login()">'+(n.shown?'NAI 창 닫기':'NAI 로그인')+'</button>';
  if(n.need_login||n.pct==null){el.innerHTML='<div class="t"><b>NovelAI</b>'+btn+'</div><div class="s">'+esc(n.status||'API 토큰을 넣으면 V5 남은 양·Anlas 가 보여요')+'</div>'
    +'<div class="t" style="gap:4px"><input id="nt" type="password" placeholder="pst-… 토큰 붙여넣기" style="flex:1;min-width:0;border:1px solid #f3c6d8;border-radius:6px;padding:2px 5px;font:12px Malgun Gothic,sans-serif"><button onclick="saveTok()">저장</button></div>';return}
  var p=n.pct,c=p<=5?'var(--hot)':p<=20?'var(--warn)':'var(--ok)';
  el.innerHTML='<div class="r"><div class="t"><b>NovelAI V5 남은 양</b><span>'+p+'%'+(n.imgs!=null?' · 약 '+Number(n.imgs).toLocaleString()+'장':'')+'</span></div><div class="k"><i style="width:'+p+'%;background:'+c+'"></i></div>'
    +(n.next?'<div class="s">'+esc(n.next)+'</div>':'')+'</div><div class="t" style="margin-top:4px"><b>Anlas</b><span>'+Number(n.anlas||0).toLocaleString()+'</span></div>'
    +(n.shown?'<div class="s">'+btn+'</div>':'')+(n.tok?'<div class="s"><button onclick="clearTok()" title="저장한 토큰 지우기">토큰 지우기</button></div>':'');
}
function clearTok(){pywebview.api.nai_token('')}
function saveTok(){var i=document.getElementById('nt');var v=(i&&i.value||'').trim();if(!v)return;i.value='';pywebview.api.nai_token(v)}
function render(d){
  var rows=d.rows||[],h='';
  rows.forEach(function(r){var c=r.pct>=95?'var(--hot)':r.pct>=80?'var(--warn)':'var(--ok)';
    h+='<div class="r"><div class="t"><b>'+esc(r.label)+'</b><span>'+r.pct+'%</span></div><div class="k"><i style="width:'+r.pct+'%;background:'+c+'"></i></div>'+(r.reset?'<div class="s">'+esc(r.reset)+'</div>':'')+'</div>'});
  document.getElementById('rows').innerHTML=h||'<div class="s">'+esc(d.status||'아직 숫자가 없어요')+'</div>';
  renderNai(d.nai);
  var lb=document.getElementById('lb');lb.hidden=!(d.need_login||!rows.length||d.cw);lb.textContent=d.cw?'로그인 창 닫기':'로그인';
  document.getElementById('f').textContent=(rows.length&&d.status?d.status+' · ':'')+(d.time?'갱신 '+d.time:'');
}
</script></body></html>"""


class Widget:
    def __init__(self, webview):
        self.wv = webview
        self.ui = None
        self.cw = None                # claude.ai 를 여는 브라우저 창 (평소엔 숨김, 로그인할 때만 보임)
        self.cw_shown = False
        self.nw = None                # novelai.net 을 여는 브라우저 창 (평소엔 숨김)
        self.nw_shown = False
        self.data = load_json(OUT) or {"rows": [], "status": "", "time": ""}
        self.kick = threading.Event()
        self.alive = True

    # ── 창 ─────────────────────────────
    def make_ui(self):
        pos = load_json(WIN)
        n = max(2, len(self.data.get("rows") or []))
        self.data.setdefault("nai", {"need_login": True})
        self.ui = self.wv.create_window("Claude 사용량", html=UI_HTML, js_api=Api(self), width=270, height=self.height(),
                                        x=pos.get("x"), y=pos.get("y"), frameless=True, easy_drag=False,
                                        on_top=True, resizable=False, background_color="#FFF7FA")
        self.ui.events.loaded += lambda: self.push()
        self.ui.events.moved += lambda x, y: save_json(WIN, {"x": x, "y": y})
        self.ui.events.closed += self.quit

    def make_cw(self):
        self.cw = self.wv.create_window("Claude 로그인 (사용량 위젯 전용)", USAGE_URL, width=980, height=780, hidden=True)
        self.cw_shown = False
        self.cw.events.closed += self._cw_closed

    def make_nw(self):
        self.nw = self.wv.create_window("NovelAI 로그인 (사용량 위젯 전용)", NAI_URL, width=980, height=780, hidden=True)
        self.nw_shown = False
        self.nw.events.closed += self._nw_closed

    def _nw_closed(self):
        self.nw = None
        self.nw_shown = False
        self.push()

    def show_nw(self, on):
        if self.nw is None:
            self.make_nw()
        try:
            (self.nw.show if on else self.nw.hide)()
            self.nw_shown = on
        except Exception:
            pass
        self.push()

    def read_nai(self, wait=24):
        """구독 상태를 물어봄 → data['nai']. 성공하면 True
        1) 저장한 영구 API 토큰이 있으면 그걸로 직접 (구글 로그인 계정도 됨)
        2) 없으면 위젯 전용 창의 novelai.net 로그인으로 (이메일·비밀번호 로그인만 됨 — 구글 로그인 팝업은 위젯 창에서 못 돌아옴)"""
        tok = nai_token()
        if tok:
            n, st = nai_fetch(tok)
            if n:
                self.set_nai(n)
                if self.nw_shown:
                    self.show_nw(False)
                return True
            self.set_nai({"need_login": True, "status": st})
            return False
        if self.nw is None:
            self.make_nw()
            time.sleep(4)
        try:
            url = self.nw.get_current_url() or ""
            if not NAI_HOME.match(url):
                self.nw.load_url(NAI_URL)
                time.sleep(4)
            st = self.nw.evaluate_js(NAI_JS)
        except Exception:
            return False
        if st == "login":
            self.set_nai({"need_login": True})
            return False
        for _ in range(wait):
            time.sleep(1.0)
            if not self.alive:
                return False
            try:
                r = json.loads(self.nw.evaluate_js("JSON.stringify(window.__nai||null)") or "null")
            except Exception:
                r = None
            if not r:
                continue
            if r.get("ok"):
                n = nai_parse(r.get("j"))
                if n is None:
                    self.set_nai({"need_login": True})
                    return False
                self.set_nai(n)
                if self.nw_shown:
                    self.show_nw(False)
                return True
            if r.get("login"):
                self.set_nai({"need_login": True})
                return False
            self.set_nai(dict(self.data.get("nai") or {}, status="NovelAI 를 못 읽었어요"))
            return False
        return False

    def set_nai(self, n):
        n = dict(n)
        n["time"] = datetime.datetime.now().strftime("%H:%M")
        self.data["nai"] = n
        save_json(OUT, self.data)
        self.push()

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
        self.push()

    def quit(self):
        self.alive = False
        self.kick.set()
        for w in list(self.wv.windows):
            try:
                w.destroy()
            except Exception:
                pass

    # ── 숫자 표시·저장 ──────────────────
    def height(self):
        n = max(2, len(self.data.get("rows") or []))
        nai = self.data.get("nai") or {}
        extra = 0 if not nai else (72 if nai.get("need_login") or nai.get("pct") is None else 82)
        if extra == 82 and (nai.get("shown") or nai.get("tok")):
            extra += 24
        return 74 + 50 * n + extra

    def push(self):
        try:
            if self.ui:
                nai = self.data.get("nai")
                if nai is not None:
                    nai = dict(nai, shown=self.nw_shown, tok=bool(nai_token()))
                self.ui.evaluate_js("render(%s)" % json.dumps(dict(self.data, cw=self.cw_shown, nai=nai), ensure_ascii=False))
                self.ui.resize(270, self.height())
        except Exception:
            pass

    def set(self, rows=None, status="", need_login=None):
        if rows is not None:
            self.data["rows"] = rows
            self.data["need_login"] = False     # 숫자를 읽었으면 로그인된 것 → 로그인 버튼 숨김
        if need_login is not None:
            self.data["need_login"] = need_login
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
                self.set(None, "로그인이 필요해요 — '로그인' 버튼", need_login=True)
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
            if self.nw_shown:                         # NovelAI 로그인 창이 열려 있는 동안: 로그인되면 바로 읽고 창 닫기
                self.read_nai(wait=4)
                self.kick.wait(3)
                self.kick.clear()
                continue
            if time.time() - last >= EVERY or self.kick.is_set():
                self.kick.clear()
                last = time.time()
                self.read_once()
                self.read_nai()
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

    def nai_login(self):
        self._w.show_nw(not self._w.nw_shown)
        self._w.kick.set()

    def nai_token(self, tok):
        tok = (tok or "").strip().strip('"').strip()
        try:
            os.makedirs(DATA, exist_ok=True)
            if tok:
                with open(NAI_TOKEN, "w", encoding="utf-8") as f:
                    f.write(tok)
            elif os.path.exists(NAI_TOKEN):
                os.remove(NAI_TOKEN)
        except Exception:
            pass
        w = self._w
        if tok:
            w.set_nai({"need_login": True, "status": "토큰 확인 중…"})
            threading.Thread(target=w.read_nai, daemon=True).start()
        else:
            w.set_nai({"need_login": True})

    def close(self):
        threading.Thread(target=self._w.quit, daemon=True).start()


def main():
    import webview
    os.makedirs(DATA, exist_ok=True)
    w = Widget(webview)
    w.make_ui()
    w.make_cw()
    w.make_nw()
    kw = dict(private_mode=False, storage_path=os.path.join(DATA, "web"))
    if sys.platform == "win32":
        kw["gui"] = "edgechromium"
    webview.start(w.loop, **kw)


if __name__ == "__main__":
    main()
