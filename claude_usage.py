# -*- coding: utf-8 -*-
"""Claude 사용량 위젯 — claude.ai '설정 → 사용량' 화면의 숫자(현재 세션·주간 한도)를 작은 창으로 띄워 둠.

- 펫 메뉴 'Claude 사용량 보기'로 켬 (따로 도는 작은 프로그램)
- 숫자는 공식 통로가 없어서, 위젯 안의 작은 브라우저(Edge WebView2)로 claude.ai 에 한 번 로그인해 두고
  사용량 화면을 5분마다 열어 글자만 읽음. 로그인은 이 위젯 전용 저장소(%APPDATA%\\DesktopPet\\claude_usage)에만 남음
- 읽은 숫자는 usage.json 에 저장 → 펫이 80%·95% 넘으면 말풍선으로 알려 줌
- Claude 계정 여러 개: 계정마다 로그인 저장소를 따로 둠. 첫 계정('main')은 예전 그대로 이 창의 저장소(web)를 쓰고,
  추가한 계정은 계정별 작은 읽기 프로그램(--acct <id>)이 자기 저장소(accounts/<id>/web)로 따로 돌며 state.json 에 숫자를 남김.
  계정마다 이름·색을 붙여 구분하고, 삭제하면 그 계정의 로그인 정보(저장소 폴더)도 같이 지움
- NovelAI 도 같이: 위젯 전용 브라우저로 novelai.net 에 한 번 로그인해 두면, 그 페이지 안에서 구독 상태
  (V5 같은 최신 모델의 남은 사용량 %, 다음 1% 충전까지 시간, Anlas)만 읽어 옴. 로그인 정보는 페이지 밖으로 안 나감
"""
import os, sys, json, time, re, threading, datetime

USAGE_URL = "https://claude.ai/settings/usage"
DATA = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "DesktopPet", "claude_usage")
OUT = os.path.join(DATA, "usage.json")
WIN = os.path.join(DATA, "window.json")
SHOW = os.path.join(DATA, "show.json")           # 보일 것 고르기 {claude, nai}
NAI_TOKEN = os.path.join(DATA, "nai_token.txt")   # NovelAI '영구 API 토큰'(pst-…) — 이 PC 에만 저장
NAI_API = ("https://image.novelai.net/user/subscription", "https://api.novelai.net/user/subscription")
EVERY = 300                      # 몇 초마다 새로 읽을지
ACCTS = os.path.join(DATA, "accounts.json")      # Claude 계정 목록 [{id, name, color}]
ACC_DIR = os.path.join(DATA, "accounts")         # 추가 계정별 폴더 (web 저장소·state.json·cmd.json)
ALIVE = os.path.join(DATA, "alive.json")         # 위젯 본체가 살아 있다는 표시 (읽기 프로그램이 보고 스스로 꺼짐)
COLORS = ["#5b8def", "#e0679a", "#2fb380", "#f09a30", "#8b6cf0", "#1fb5c9", "#c9792f", "#7a8aa0"]
MAIN = "main"

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
# claude.ai 페이지 안에서만: 지금 로그인된 계정의 이메일·이름을 물어봐서 window.__who 에 남김 (계정 구분 표시용)
WHO_JS = r"""(function(){window.__who=null;fetch('/api/account',{credentials:'include'}).then(function(r){return r.ok?r.json():null})
.then(function(j){j=j||{};var a=j.account||j;window.__who={e:a.email_address||a.email||'',n:a.full_name||a.display_name||a.name||''}})
.catch(function(){window.__who={e:'',n:''}});return 1})()"""


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


def load_accounts():
    """Claude 계정 목록. 처음엔 예전 로그인(web 저장소)을 쓰는 'main' 하나"""
    a = load_json(ACCTS)
    lst = a.get("list") if isinstance(a, dict) else None
    if not isinstance(lst, list):
        lst = [{"id": MAIN, "name": "", "color": COLORS[0]}]
    out, seen = [], set()
    for i, x in enumerate(lst):
        if not isinstance(x, dict) or not x.get("id") or x["id"] in seen:
            continue
        seen.add(x["id"])
        out.append({"id": str(x["id"]), "name": str(x.get("name") or "")[:16],
                    "color": x.get("color") if x.get("color") in COLORS else COLORS[i % len(COLORS)]})
    return out


def save_accounts(lst):
    save_json(ACCTS, {"list": lst})


def acc_dir(aid):
    return os.path.join(ACC_DIR, re.sub(r"[^A-Za-z0-9_-]", "", aid))


class ClaudeSession:
    """claude.ai 사용량 화면을 여는 숨은 브라우저 창 하나 = Claude 계정 하나.
    report(rows=None, status=None, need_login=None, who=None) 로 읽은 결과를 알려 줌"""

    def __init__(self, wv, title, report):
        self.wv = wv
        self.title = title
        self.report = report
        self.cw = None
        self.shown = False
        self.alive = True
        self.who = None                 # {"e": 이메일, "n": 이름}
        self.who_tried = False

    def make(self):
        self.cw = self.wv.create_window(self.title, USAGE_URL, width=980, height=780, hidden=True)
        self.shown = False
        self.cw.events.closed += self._closed

    def _closed(self):
        self.cw = None
        self.shown = False
        self.report()

    def show(self, on):
        if self.cw is None:
            self.make()
        try:
            (self.cw.show if on else self.cw.hide)()
            self.shown = on
        except Exception:
            pass
        self.report()

    def page(self):
        try:
            url = self.cw.get_current_url() or ""
            txt = self.cw.evaluate_js("document.body ? document.body.innerText : ''") or ""
            return url, txt
        except Exception:
            return "", ""

    def ask_who(self):
        """로그인된 계정 이메일 (구분 표시용). 못 읽어도 괜찮음"""
        try:
            self.cw.evaluate_js(WHO_JS)
            for _ in range(8):
                time.sleep(0.8)
                r = json.loads(self.cw.evaluate_js("JSON.stringify(window.__who||null)") or "null")
                if r is not None:
                    if r.get("e") or r.get("n"):
                        self.who = {"e": str(r.get("e") or "")[:60], "n": str(r.get("n") or "")[:30]}
                    return
        except Exception:
            pass

    def got(self, rows):
        if self.who is None and not self.who_tried:
            self.who_tried = True
            self.ask_who()
        self.report(rows, "", False, self.who)
        if self.shown:
            self.show(False)

    def read_once(self):
        if self.cw is None:
            self.make()
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
                self.got(rows)
                return
            if "/login" in url or "/logout" in url:
                self.who, self.who_tried = None, False
                self.report(None, "로그인이 필요해요 — '로그인' 버튼", True)
                return
        self.report(None, "숫자를 못 읽었어요 (화면이 바뀌었을 수 있어요)")

    def watch_login(self):
        """로그인 창이 열려 있는 동안: 로그인이 끝나 claude.ai 첫 화면으로 가면 사용량 화면으로 데려감"""
        url, txt = self.page()
        rows = parse(txt)
        if rows:
            self.who, self.who_tried = None, False       # 방금 (다른 계정으로) 로그인했을 수 있음
            self.got(rows)
            return True
        if HOME.match(url):
            try:
                self.cw.load_url(USAGE_URL)
            except Exception:
                pass
        return False

    def logout(self):
        """이 창의 Claude 로그인 지우기 (main 계정 삭제용 — main 저장소는 NovelAI 로그인과 같이 쓰니 폴더째 못 지움)"""
        try:
            if self.cw is None:
                self.make()
                time.sleep(2)
            try:
                self.cw.clear_cookies()
            except Exception:
                pass
            self.cw.load_url("https://claude.ai/logout")
            time.sleep(4)
        except Exception:
            pass


UI_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
:root{--bg:rgba(255,247,250,.97);--fg:#4a3a44;--sub:#9a8592;--bar:#eadde4;--ok:#5b8def;--warn:#f0a030;--hot:#e5484d;--pk:#d0588a;--ln:#f3c6d8}
*{box-sizing:border-box}[hidden]{display:none!important}html,body{margin:0;overflow:hidden;background:#FFF7FA;font:13px 'Malgun Gothic',sans-serif;color:var(--fg)}
#p{margin:0;background:var(--bg);border:1px solid var(--ln);border-radius:12px;padding:8px 12px 8px;display:flex;flex-direction:column;gap:8px}
#h{display:flex;align-items:center;gap:5px;color:var(--sub);font-size:11px}
#h span{flex:1}
button{white-space:nowrap;flex:none;border:0;background:#fbe3ee;color:#b0476f;border-radius:7px;padding:2px 7px;font:12px 'Malgun Gothic',sans-serif;cursor:pointer}
button:hover{background:#f7cfe0}
button.no{background:#f1ecef;color:#7a6872}button.no:hover{background:#e7dfe4}
button.del{background:#fde2e3;color:#c0353b}button.del:hover{background:#fbcfd1}
button.ic{padding:2px 5px;background:transparent;color:var(--sub)}button.ic:hover{background:#f6e6ee;color:#b0476f}
.sec{display:flex;flex-direction:column;gap:7px}
.col{display:flex;flex-direction:column;gap:7px}
.sec+.sec{border-top:1px dashed var(--ln);padding-top:8px}
.st{display:flex;align-items:center;gap:6px;font-weight:700;color:var(--pk);font-size:13px}.st span{flex:1}
.r{display:flex;flex-direction:column;gap:2px}
.t{display:flex;justify-content:space-between;gap:8px}.t b{font-weight:600}
.k{height:7px;border-radius:4px;background:var(--bar);overflow:hidden}.k i{display:block;height:100%;border-radius:4px;background:var(--ok)}
.s{color:var(--sub);font-size:11px}
#set{display:flex;flex-direction:column;gap:4px;background:#fff;border:1px solid var(--ln);border-radius:8px;padding:6px 8px}
#set label{display:flex;align-items:center;gap:6px;cursor:pointer}
#set input{accent-color:var(--pk);margin:0}
#f{color:var(--sub);font-size:11px}
input.tx{flex:1;min-width:0;border:1px solid var(--ln);border-radius:6px;padding:2px 5px;font:12px 'Malgun Gothic',sans-serif}
.acc{position:relative;background:#fff;border:1px solid #f1e3ea;border-left:5px solid var(--c);border-radius:9px;padding:6px 8px 7px;display:flex;flex-direction:column;gap:5px}
.acc .k i{background:var(--c)}
.ah{display:flex;align-items:center;gap:5px}
.tag{display:inline-flex;align-items:center;gap:5px;min-width:0;flex:1;font-weight:700;font-size:13px;color:var(--c)}
.tag u{text-decoration:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dot{flex:none;width:14px;height:14px;border-radius:50%;background:var(--c);border:2px solid #fff;box-shadow:0 0 0 1px var(--c);cursor:pointer;padding:0}
.no2{flex:none;font-size:10px;font-weight:700;color:#fff;background:var(--c);border-radius:5px;padding:0 4px}
.em{color:var(--sub);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:-3px}
.warn{color:#c0353b;font-size:11px}
.ask{display:flex;flex-direction:column;gap:4px;background:#fff4f5;border:1px solid #f6c9cc;border-radius:7px;padding:5px 7px}
.ask .t{justify-content:flex-end;gap:4px}
.row{display:flex;gap:4px;align-items:center}
</style></head><body><div id="p" class="pywebview-drag-region">
<div id="h"><span class="pywebview-drag-region">사용량</span><button onclick="pywebview.api.refresh()" title="지금 새로 읽기">↻</button><button id="gb" onclick="togSet()" title="보일 것 고르기">⚙</button><button onclick="pywebview.api.close()" title="닫기">×</button></div>
<div id="set" hidden><div class="s">보일 것 고르기</div>
<label><input type="checkbox" id="oc" onchange="setShow('claude',this.checked)">Claude 사용량</label>
<label><input type="checkbox" id="on" onchange="setShow('nai',this.checked)">NovelAI 사용량</label></div>
<div class="sec" id="sc"><div class="st"><span>Claude 사용량</span><button id="ab" onclick="addOpen()" title="Claude 계정 하나 더 추가">＋ 계정</button></div>
<div id="add" class="row" hidden><input class="tx" id="an" maxlength="16" placeholder="이 계정 이름 (예: 회사·개인)"><button onclick="addGo()">추가</button><button class="no" onclick="addOpen(false)">취소</button></div>
<div id="accs" class="col"><div class="s">불러오는 중…</div></div></div>
<div class="sec" id="sn"><div class="st"><span>NovelAI 사용량</span><span id="nb" style="flex:none;display:flex;gap:4px"></span></div><div id="nai" class="col"></div></div>
<div id="f"></div></div>
<script>
var D={},SH={claude:true,nai:true},UI={del:null,ren:null};
function esc(s){return String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function bar(label,val,pct,c,sub){return '<div class="r"><div class="t"><b>'+esc(label)+'</b><span>'+val+'</span></div><div class="k"><i style="width:'+pct+'%'+(c?';background:'+c:'')+'"></i></div>'+(sub?'<div class="s">'+esc(sub)+'</div>':'')+'</div>'}
function fit(){setTimeout(function(){try{pywebview.api.fit(Math.ceil(document.getElementById('p').getBoundingClientRect().height)+2)}catch(e){}},30)}
function togSet(){var e=document.getElementById('set');e.hidden=!e.hidden;fit()}
function setShow(k,on){SH[k]=on;if(!SH.claude&&!SH.nai){SH[k==='claude'?'nai':'claude']=true}pywebview.api.set_show(SH.claude,SH.nai);paint()}
function addOpen(on){var e=document.getElementById('add');e.hidden=(on===false)?true:!e.hidden;if(!e.hidden){var i=document.getElementById('an');i.value='';i.focus()}fit()}
function addGo(){var i=document.getElementById('an');pywebview.api.acc_add((i.value||'').trim());i.value='';document.getElementById('add').hidden=true;fit()}
function renOpen(id){UI.ren=id;UI.del=null;paint();var i=document.getElementById('rn');if(i){i.focus();i.select()}}
function renGo(id){var i=document.getElementById('rn');pywebview.api.acc_rename(id,(i&&i.value||'').trim());UI.ren=null}
function delOpen(id){UI.del=id;UI.ren=null;paint()}
function delGo(id){UI.del=null;pywebview.api.acc_delete(id)}
function cancel(){UI.del=UI.ren=null;paint()}
function accHtml(a,i,n,dup){
  var nm=a.name||('계정 '+(i+1)),rows=a.rows||[],h='';
  h+='<div class="acc" style="--c:'+a.color+'"><div class="ah">';
  h+='<button class="dot" title="색 바꾸기" onclick="pywebview.api.acc_color(\\''+a.id+'\\')"></button>';
  if(UI.ren===a.id){
    h+='<input class="tx" id="rn" maxlength="16" value="'+esc(a.name)+'" placeholder="계정 '+(i+1)+'" onkeydown="if(event.key===\\'Enter\\')renGo(\\''+a.id+'\\');if(event.key===\\'Escape\\')cancel()"><button onclick="renGo(\\''+a.id+'\\')">저장</button><button class="no" onclick="cancel()">취소</button></div>';
  }else{
    h+='<span class="tag">'+(n>1?'<span class="no2">'+(i+1)+'</span>':'')+'<u title="'+esc(nm)+'">'+esc(nm)+'</u></span>';
    if(a.need_login||!rows.length||a.cw)h+='<button onclick="pywebview.api.acc_login(\\''+a.id+'\\')" title="이 계정 로그인 창 열기/닫기">'+(a.cw?'창 닫기':'로그인')+'</button>';
    h+='<button class="ic" title="이름 바꾸기" onclick="renOpen(\\''+a.id+'\\')">✎</button>';
    h+='<button class="ic" title="계정 삭제" onclick="delOpen(\\''+a.id+'\\')">🗑</button></div>';
  }
  if(a.email||a.who_name)h+='<div class="em" title="'+esc(a.email)+'">'+esc(a.email||a.who_name)+'</div>';
  if(dup)h+='<div class="warn">⚠ 위의 다른 칸과 같은 계정이에요 — 다른 계정으로 로그인해 주세요</div>';
  if(UI.del===a.id){
    h+='<div class="ask"><div class="s" style="color:#a0474b">「'+esc(nm)+'」 계정을 지울까요? 이 위젯에 저장된 로그인도 같이 지워져요.</div><div class="t"><button class="del" onclick="delGo(\\''+a.id+'\\')">삭제</button><button class="no" onclick="cancel()">취소</button></div></div>';
  }
  rows.forEach(function(r){h+=bar(r.label,r.pct+'%',r.pct,r.pct>=95?'var(--hot)':r.pct>=80?'var(--warn)':'',r.reset)});
  if(!rows.length)h+='<div class="s">'+esc(a.status||'아직 숫자가 없어요')+'</div>';
  else if(a.status)h+='<div class="s">'+esc(a.status)+'</div>';
  if(a.time)h+='<div class="s" style="text-align:right;margin-top:-3px">갱신 '+esc(a.time)+'</div>';
  return h+'</div>';
}
function renderNai(n){
  var el=document.getElementById('nai'),nb=document.getElementById('nb');
  var a=document.activeElement;if(a&&a.id==='nt'&&a.value)return;
  n=n||{need_login:true};
  var lg='<button onclick="pywebview.api.nai_login()" title="이메일 계정 로그인 창 열기/닫기">'+(n.shown?'로그인 창 닫기':'로그인')+'</button>';
  if(n.need_login||n.pct==null){
    nb.innerHTML=lg;
    el.innerHTML='<div class="s">'+esc(n.status||'API 토큰을 넣으면 V5 남은 양·Anlas 가 보여요')+'</div>'
      +'<div class="t" style="gap:4px"><input id="nt" class="tx" type="password" placeholder="pst-… 토큰 붙여넣기"><button onclick="saveTok()">저장</button></div>';return}
  nb.innerHTML=n.tok?'<button onclick="clearTok()" title="저장한 토큰 지우기">토큰 지우기</button>':(n.shown?lg:'');
  var p=n.pct,c=p<=5?'var(--hot)':p<=20?'var(--warn)':'var(--ok)';
  el.innerHTML=bar('V5 남은 양',p+'%'+(n.imgs!=null?' · 약 '+Number(n.imgs).toLocaleString()+'장':''),p,c,n.next)
    +'<div class="t"><b>Anlas</b><span>'+Number(n.anlas||0).toLocaleString()+'</span></div>';
}
function clearTok(){pywebview.api.nai_token('')}
function saveTok(){var i=document.getElementById('nt');var v=(i&&i.value||'').trim();if(!v)return;i.value='';pywebview.api.nai_token(v)}
function paint(){
  var d=D,accs=d.accounts||[];
  if(d.show){SH.claude=d.show.claude!==false;SH.nai=d.show.nai!==false}
  document.getElementById('oc').checked=SH.claude;document.getElementById('on').checked=SH.nai;
  document.getElementById('sc').hidden=!SH.claude;document.getElementById('sn').hidden=!SH.nai;
  var seen={},h='';
  accs.forEach(function(a,i){var e=(a.email||'').toLowerCase(),dup=!!(e&&seen[e]);if(e)seen[e]=1;h+=accHtml(a,i,accs.length,dup)});
  if(!accs.length)h='<div class="s">등록된 계정이 없어요 — ＋ 계정으로 추가해 주세요</div>';
  document.getElementById('accs').innerHTML=h;
  renderNai(d.nai);
  document.getElementById('f').textContent=(!SH.claude&&d.nai&&d.nai.time)?'갱신 '+d.nai.time:'';
  fit();
}
function render(d){D=d;if(d.show){SH.claude=d.show.claude!==false;SH.nai=d.show.nai!==false}
  var a=document.activeElement;if(a&&(a.id==='rn'||a.id==='an')){renderNai(d.nai);return}paint()}
</script></body></html>"""


def blank_state():
    return {"rows": [], "status": "", "time": "", "need_login": False, "email": "", "who_name": "", "ts": 0}


class Widget:
    def __init__(self, webview):
        self.wv = webview
        self.ui = None
        self.nw = None                # novelai.net 을 여는 브라우저 창 (평소엔 숨김)
        self.nw_shown = False
        self.data = load_json(OUT) or {}
        sh = load_json(SHOW) or {}
        self.show = {"claude": sh.get("claude", True) is not False, "nai": sh.get("nai", True) is not False}
        self.kick = threading.Event()
        self.alive = True
        self.lock = threading.RLock()
        self.accounts = load_accounts()
        save_accounts(self.accounts)
        # 계정별 화면 상태. 예전 usage.json(계정 하나) 의 숫자는 main 으로 이어받음
        old = self.data.get("accounts") if isinstance(self.data.get("accounts"), dict) else {}
        self.st = {}
        for a in self.accounts:
            s = dict(blank_state(), **(old.get(a["id"]) or {}))
            if a["id"] == MAIN and not old and self.data.get("rows"):
                s.update(rows=self.data.get("rows") or [], time=self.data.get("time", ""), ts=self.data.get("ts", 0))
            self.st[a["id"]] = s
        self.main = None              # main 계정 = 이 프로그램의 claude.ai 창
        if any(a["id"] == MAIN for a in self.accounts):
            self.main = ClaudeSession(webview, self.login_title(MAIN), lambda *a, **k: self.report(MAIN, *a, **k))
        self.procs = {}               # 추가 계정 읽기 프로그램 {id: Popen}
        self.restarts = {}
        self.cmd_seq = 0

    def login_title(self, aid):
        a = self.acc(aid)
        nm = (a and a["name"]) or "계정 %d" % (self.index(aid) + 1)
        return "Claude 로그인 — %s (사용량 위젯 전용)" % nm

    def acc(self, aid):
        for a in self.accounts:
            if a["id"] == aid:
                return a
        return None

    def index(self, aid):
        for i, a in enumerate(self.accounts):
            if a["id"] == aid:
                return i
        return len(self.accounts)

    # ── 창 ─────────────────────────────
    def make_ui(self):
        pos = load_json(WIN)
        self.data.setdefault("nai", {"need_login": True})
        self.ui = self.wv.create_window("사용량", html=UI_HTML, js_api=Api(self), width=270, height=self.height(),
                                        x=pos.get("x"), y=pos.get("y"), frameless=True, easy_drag=False,
                                        on_top=True, resizable=False, background_color="#FFF7FA")
        self.ui.events.loaded += lambda: self.push()
        self.ui.events.moved += lambda x, y: save_json(WIN, {"x": x, "y": y})
        self.ui.events.closed += self.quit

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
        self.save()
        self.push()

    def quit(self):
        self.alive = False
        self.kick.set()
        for aid in list(self.procs):
            self.send(aid, "quit")
        for w in list(self.wv.windows):
            try:
                w.destroy()
            except Exception:
                pass

    # ── 계정 상태 ────────────────────────
    def report(self, aid, rows=None, status=None, need_login=None, who=None):
        with self.lock:
            s = self.st.get(aid)
            if s is None:
                return
            if rows is not None:
                s["rows"] = rows
                s["need_login"] = False     # 숫자를 읽었으면 로그인된 것 → 로그인 버튼 숨김
                s["ts"] = time.time()
                s["time"] = datetime.datetime.now().strftime("%H:%M")
            if need_login is not None:
                s["need_login"] = need_login
                if need_login:
                    s["rows"] = []
                    s["email"] = s["who_name"] = ""
            if status is not None:
                s["status"] = status
            if who:
                s["email"], s["who_name"] = who.get("e", ""), who.get("n", "")
            if rows is not None or status is not None or need_login is not None:
                self.save()
        self.push()

    def save(self):
        """usage.json: 펫이 읽는 rows(계정이 여럿이면 '이름 · 항목'으로 합침) + 계정별 상태 + NovelAI"""
        with self.lock:
            rows, ts = [], 0
            many = len(self.accounts) > 1
            for i, a in enumerate(self.accounts):
                s = self.st.get(a["id"]) or {}
                nm = a["name"] or "계정 %d" % (i + 1)
                for r in s.get("rows") or []:
                    rows.append(dict(r, label=(nm + " · " + r["label"]) if many else r["label"]))
                ts = max(ts, float(s.get("ts") or 0))
            out = dict(self.data, rows=rows, ts=ts or self.data.get("ts", 0),
                       accounts={a["id"]: self.st.get(a["id"]) or {} for a in self.accounts})
            out.pop("cw", None)
            self.data = out
            save_json(OUT, out)

    def height(self):
        n = sum(max(1, len((self.st.get(a["id"]) or {}).get("rows") or [])) for a in self.accounts) or 1
        nai = self.data.get("nai") or {}
        extra = 0 if not nai else (72 if nai.get("need_login") or nai.get("pct") is None else 82)
        if extra == 82 and (nai.get("shown") or nai.get("tok")):
            extra += 24
        return 70 + 46 * n + 46 * len(self.accounts) + extra

    def push(self):
        try:
            if self.ui:
                with self.lock:
                    accs = []
                    for a in self.accounts:
                        s = dict(self.st.get(a["id"]) or blank_state())
                        s.update(a)
                        if a["id"] == MAIN:
                            s["cw"] = bool(self.main and self.main.shown)
                        else:
                            s["cw"] = bool(s.get("shown"))
                        accs.append(s)
                    nai = self.data.get("nai")
                    if nai is not None:
                        nai = dict(nai, shown=self.nw_shown, tok=bool(nai_token()))
                    payload = {"accounts": accs, "nai": nai, "show": self.show}
                self.ui.evaluate_js("render(%s)" % json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass

    # ── 추가 계정 읽기 프로그램 ──────────────
    def send(self, aid, cmd):
        self.cmd_seq += 1
        save_json(os.path.join(acc_dir(aid), "cmd.json"), {"seq": time.time() + self.cmd_seq / 1000.0, "cmd": cmd,
                                                            "title": self.login_title(aid)})

    def spawn(self, aid, login=False):
        import subprocess
        p = self.procs.get(aid)
        if p is not None and p.poll() is None:
            if login:
                self.send(aid, "login")
            return
        d = acc_dir(aid)
        os.makedirs(d, exist_ok=True)
        if login:
            self.send(aid, "login")
        exe = sys.executable
        try:
            self.procs[aid] = subprocess.Popen([exe, os.path.abspath(__file__), "--acct", aid, self.login_title(aid)],
                                               cwd=os.path.dirname(os.path.abspath(__file__)),
                                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception as e:
            self.report(aid, status="읽기 프로그램을 못 켰어요 (%s)" % e)

    def poll_procs(self):
        """추가 계정들의 state.json 을 모아 오고, 꺼진 읽기 프로그램은 다시 켬"""
        save_json(ALIVE, {"ts": time.time()})
        changed = False
        for a in list(self.accounts):
            aid = a["id"]
            if aid == MAIN:
                continue
            p = self.procs.get(aid)
            if self.show["claude"] and (p is None or p.poll() is not None):
                hist = [t for t in self.restarts.get(aid, []) if time.time() - t < 120]
                if len(hist) < 5:
                    hist.append(time.time())
                    self.restarts[aid] = hist
                    self.spawn(aid)
                elif (self.st.get(aid) or {}).get("status") != "읽기 프로그램이 자꾸 꺼져요 — 위젯을 다시 켜 주세요":
                    self.report(aid, status="읽기 프로그램이 자꾸 꺼져요 — 위젯을 다시 켜 주세요")
            s = load_json(os.path.join(acc_dir(aid), "state.json"))
            if not s:
                continue
            with self.lock:
                cur = self.st.setdefault(aid, blank_state())
                keep = {k: s.get(k) for k in ("rows", "status", "time", "need_login", "email", "who_name", "ts", "shown")
                        if k in s}
                if any(cur.get(k) != v for k, v in keep.items()):
                    cur.update(keep)
                    changed = True
        if changed:
            self.save()
            self.push()

    # ── 계정 추가·이름·색·삭제 ────────────────
    def add_account(self, name):
        with self.lock:
            used = {a["color"] for a in self.accounts}
            color = next((c for c in COLORS if c not in used), COLORS[len(self.accounts) % len(COLORS)])
            aid = "a%d" % int(time.time() * 1000)
            self.accounts.append({"id": aid, "name": (name or "")[:16], "color": color})
            self.st[aid] = dict(blank_state(), status="로그인 창이 열리면 이 계정으로 로그인해 주세요", need_login=True)
            save_accounts(self.accounts)
        self.save()
        self.push()
        self.spawn(aid, login=True)

    def rename(self, aid, name):
        with self.lock:
            a = self.acc(aid)
            if not a:
                return
            a["name"] = (name or "")[:16]
            save_accounts(self.accounts)
        if aid == MAIN and self.main:
            try:
                self.main.title = self.login_title(MAIN)
                if self.main.cw:
                    self.main.cw.set_title(self.main.title)
            except Exception:
                pass
        elif aid in self.procs:
            self.send(aid, "title")
        self.save()
        self.push()

    def recolor(self, aid):
        with self.lock:
            a = self.acc(aid)
            if not a:
                return
            i = COLORS.index(a["color"]) if a["color"] in COLORS else -1
            a["color"] = COLORS[(i + 1) % len(COLORS)]
            save_accounts(self.accounts)
        self.push()

    def delete_account(self, aid):
        """목록에서 빼고 그 계정 로그인도 지움. 추가 계정은 저장소 폴더째, main 은 claude.ai 로그아웃"""
        with self.lock:
            if not self.acc(aid):
                return
            self.accounts = [a for a in self.accounts if a["id"] != aid]
            self.st.pop(aid, None)
            save_accounts(self.accounts)
        self.save()
        self.push()
        if aid == MAIN:
            m, self.main = self.main, None
            if m:
                m.alive = False
                m.logout()
                try:
                    if m.cw:
                        m.cw.destroy()
                except Exception:
                    pass
            return
        p = self.procs.pop(aid, None)
        self.send(aid, "quit")
        for _ in range(40):
            if p is None or p.poll() is not None:
                break
            time.sleep(0.25)
        if p is not None and p.poll() is None:
            try:
                p.kill()
            except Exception:
                pass
        import shutil
        for _ in range(20):                         # 브라우저 파일이 잠깐 잠겨 있을 수 있어 몇 번 다시 시도
            shutil.rmtree(acc_dir(aid), ignore_errors=True)
            if not os.path.exists(acc_dir(aid)):
                break
            time.sleep(1)

    # ── 읽기 ─────────────────────────────
    def loop(self):
        time.sleep(1.0)
        self.push()
        last = 0
        while self.alive:
            self.poll_procs()
            m = self.main
            if m and m.shown:
                m.watch_login()
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
                if self.show["claude"] and m:
                    st = self.st.get(MAIN) or {}
                    m.read_once()
                    st = self.st.get(MAIN) or {}
                    if st.get("need_login") and not st.get("rows") and not st.get("ts") and m.alive:
                        m.show(True)                  # 처음이면 로그인 창을 바로 보여 줌
                if self.show["nai"]:
                    self.read_nai()
                continue
            self.kick.wait(3)


class Api:
    def __init__(self, w):
        self._w = w

    def refresh(self):
        w = self._w
        for a in w.accounts:
            w.report(a["id"], status="읽는 중…")
            if a["id"] != MAIN:
                w.send(a["id"], "refresh")
        if w.main and w.main.shown:
            try:
                w.main.cw.load_url(USAGE_URL)
            except Exception:
                pass
        w.kick.set()

    def acc_login(self, aid):
        w = self._w
        if aid == MAIN:
            if w.main:
                w.main.show(not w.main.shown)
        else:
            s = w.st.get(aid) or {}
            if s.get("shown"):
                w.send(aid, "hide")
            else:
                w.spawn(aid, login=True)
        w.kick.set()

    def acc_add(self, name):
        threading.Thread(target=self._w.add_account, args=(name,), daemon=True).start()

    def acc_rename(self, aid, name):
        self._w.rename(aid, name)

    def acc_color(self, aid):
        self._w.recolor(aid)

    def acc_delete(self, aid):
        threading.Thread(target=self._w.delete_account, args=(aid,), daemon=True).start()

    def nai_login(self):
        self._w.show_nw(not self._w.nw_shown)
        self._w.kick.set()

    def fit(self, h):
        """화면 내용 높이에 맞춰 창 크기 조절 (켠 항목·줄 수에 따라 달라짐)"""
        try:
            h = max(60, min(1000, int(h)))
            if getattr(self._w, "_h", None) != h:
                self._w._h = h
                self._w.ui.resize(270, h)
        except Exception:
            pass

    def set_show(self, claude, nai):
        w = self._w
        w.show = {"claude": bool(claude) or not nai, "nai": bool(nai)}
        save_json(SHOW, w.show)
        if not w.show["claude"]:
            if w.main and w.main.shown:
                w.main.show(False)
            for aid in list(w.procs):                 # Claude 를 끄면 추가 계정 읽기 프로그램도 쉼
                w.send(aid, "quit")
            w.procs.clear()
        if not w.show["nai"] and w.nw_shown:
            w.show_nw(False)
        w.push()
        w.kick.set()                                  # 새로 켠 항목은 바로 읽기

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


class Reader:
    """추가 계정 하나만 읽는 작은 프로그램 (claude_usage.py --acct <id> <창 제목>).
    자기 저장소에 로그인해 두고 숫자를 state.json 에 씀. 위젯 본체가 cmd.json 으로 login/hide/refresh/quit 를 시킴"""

    def __init__(self, webview, aid, title):
        self.wv = webview
        self.aid = aid
        self.dir = acc_dir(aid)
        self.state = dict(blank_state(), **(load_json(os.path.join(self.dir, "state.json")) or {}))
        self.state["shown"] = False
        self.sess = ClaudeSession(webview, title, self.report)
        self.seq = (load_json(os.path.join(self.dir, "cmd.json")) or {}).get("seq", 0)
        self.want_login = False
        c = load_json(os.path.join(self.dir, "cmd.json"))
        if c.get("cmd") == "login" and time.time() - float(c.get("seq") or 0) < 30:
            self.want_login = True                    # 방금 '추가'·'로그인'을 눌러서 켜진 것
        self.alive = True
        self.started = time.time()

    def report(self, rows=None, status=None, need_login=None, who=None):
        s = self.state
        if rows is not None:
            s.update(rows=rows, need_login=False, ts=time.time(), time=datetime.datetime.now().strftime("%H:%M"))
        if need_login is not None:
            s["need_login"] = need_login
            if need_login:
                s.update(rows=[], email="", who_name="")
        if status is not None:
            s["status"] = status
        if who:
            s["email"], s["who_name"] = who.get("e", ""), who.get("n", "")
        s["shown"] = self.sess.shown
        save_json(os.path.join(self.dir, "state.json"), s)

    def parent_alive(self):
        a = load_json(ALIVE)
        ts = float(a.get("ts") or 0)
        return time.time() - ts < 60 or time.time() - self.started < 60

    def command(self):
        c = load_json(os.path.join(self.dir, "cmd.json"))
        if not c or float(c.get("seq") or 0) <= float(self.seq or 0):
            return None
        self.seq = c.get("seq")
        if c.get("title"):
            self.sess.title = c["title"]
            try:
                if self.sess.cw:
                    self.sess.cw.set_title(c["title"])
            except Exception:
                pass
        return c.get("cmd")

    def quit(self):
        self.alive = False
        self.sess.alive = False
        for w in list(self.wv.windows):
            try:
                w.destroy()
            except Exception:
                pass

    def loop(self):
        time.sleep(1.0)
        if self.want_login:
            self.sess.show(True)
        last = 0
        while self.alive:
            if not self.parent_alive() or not os.path.isdir(self.dir):
                self.quit()
                return
            cmd = self.command()
            if cmd == "quit":
                self.quit()
                return
            if cmd == "login":
                self.sess.show(True)
            elif cmd == "hide":
                self.sess.show(False)
            elif cmd == "refresh":
                last = 0
            if self.sess.shown:
                self.sess.watch_login()
                self.report()
                time.sleep(2)
                continue
            if time.time() - last >= EVERY:
                last = time.time()
                self.sess.read_once()
                continue
            time.sleep(2)


def reader_main(aid, title):
    import webview
    r = Reader(webview, aid, title)
    os.makedirs(r.dir, exist_ok=True)
    r.sess.make()
    kw = dict(private_mode=False, storage_path=os.path.join(r.dir, "web"))
    if sys.platform == "win32":
        kw["gui"] = "edgechromium"
    webview.start(r.loop, **kw)


def main():
    import webview
    if len(sys.argv) >= 3 and sys.argv[1] == "--acct":
        reader_main(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "Claude 로그인 (사용량 위젯 전용)")
        return
    os.makedirs(DATA, exist_ok=True)
    w = Widget(webview)
    w.make_ui()
    if w.main:
        w.main.make()
    w.make_nw()
    kw = dict(private_mode=False, storage_path=os.path.join(DATA, "web"))
    if sys.platform == "win32":
        kw["gui"] = "edgechromium"
    webview.start(w.loop, **kw)


if __name__ == "__main__":
    main()
