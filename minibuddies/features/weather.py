"""Weather conditions and associated pet reactions."""

import datetime
import json
import os
import random
import threading
import time
from PyQt5.QtCore import QTimer
from minibuddies.catalog import F, FALLBACK, TICK
from minibuddies.features.pepero import _pep_free
from minibuddies.runtime import _crash_write


# ── 날씨 따라 행동하기 (인터넷 위치 → Open-Meteo 현재 날씨) ─────────────────────
# 10번 시트(날씨) 100~107: 우산 서기, 우산 걷기, 비 맞으며 뛰기, 물웅덩이 첨벙, 목도리 덜덜, 눈덩이 던지기, 부채질, 아이스크림

WEATHER = {"kind": None, "temp": None, "code": None, "city": "", "next": 0.0, "new": None, "busy": False}
WEATHER_NAME = {"rain": "비", "snow": "눈", "hot": "더움", "cold": "추움", "clear": "맑음", "cloud": "흐림"}

# 캐릭터별 날씨 대사 (rain 비 / snow 눈 / hot 더위 / cold 추위) — 없으면 WEATHER_GENERIC
WEATHER_LINES = {
    "elysia": {"rain": ["비가 오네~ 우산 속으로 들어올래?♪", "빗소리도 꽤 낭만적이지 않아?"],
               "snow": ["눈이다~! 눈싸움 하자♪", "하얀 눈 위의 핑크 엘프, 예쁘지?"],
               "hot": ["으음~ 더워서 녹아버릴 것 같아…", "아이스크림 하나 나눠 먹을래?♪"],
               "cold": ["추워~ 꼭 안아 주면 따뜻해질 텐데♪", "목도리 둘러 줄래?"]},
    "arisa": {"rain": ["비 오는 날엔 흑마법이 더 잘 된다고!", "우산 없는 애는 내 우산 밑으로~"],
              "snow": ["눈이다! 눈덩이 마법 받아라!", "눈 오는 날은 집에서 게임이지~"],
              "hot": ["더워… 마력이 증발한다…", "콜라 어디 있어 콜라!"],
              "cold": ["추워추워… 마법진으로 불 좀 피우자", "손 시려~"]},
    "karin": {"rain": ["비 오는 날은 노래가 더 잘 나와~", "우산 같이 쓸래?"],
              "snow": ["눈이다~! 사진 찍자!", "눈사람 만들자!"],
              "hot": ["더워서 목소리 다 녹겠어…", "딸기 빙수 먹고 싶다~"],
              "cold": ["으으 추워… 담요 줘!", "따뜻한 거 마시고 싶어"]},
    "eris": {"rain": ["비 오니까… 그냥 누워 있을래…", "빗소리 좋다… 졸려…"],
             "snow": ["눈… 차가워…", "눈덩이 맞으면 울 거야…"],
             "hot": ["더워… 민트초코 아이스크림…", "에어컨 앞에서 안 움직일래…"],
             "cold": ["추워… 이불 밖은 위험해…", "토끼 인형 꼭 안고 있을래…"]},
    "ellie": {"rain": ["비 오면 털이 젖는다냥…", "우산 쓰고 산책 가자냥~"],
              "snow": ["눈이다냥! 폭렬 눈덩이!", "발자국 콩콩 찍을래냥~"],
              "hot": ["더워서 녹는다냥…", "붕어빵 말고 아이스크림냥!"],
              "cold": ["추워서 웅크리는 거다냥…", "따뜻한 데 어디냥~"]},
    "anis": {"rain": ["비 오잖아~ 오늘은 땡땡이 각!", "우산 챙겼어, 지휘관?"],
             "snow": ["눈싸움이다~! 내 눈덩이 받아라!", "눈 오면 탄산 대신 핫초코지~"],
             "hot": ["더워~ 탄산 한 캔만…", "휴가 가고 싶다 진짜~"],
             "cold": ["추워추워! 지휘관 패딩 좀 빌려줘", "손 시려… 호호"]},
    "rapi": {"rain": ["강우 확인. 지휘관, 우산을 쓰세요.", "시야가 나쁩니다. 조심하세요."],
             "snow": ["적설 확인. 미끄러우니 주의하세요.", "…눈싸움입니까. 봐드리지 않겠습니다."],
             "hot": ["기온이 높습니다. 수분 보충을.", "…덥군요."],
             "cold": ["기온이 낮습니다. 따뜻하게 입으세요, 지휘관.", "체온 유지가 필요합니다."]},
    "marian": {"rain": ["비가 와요, 지휘관님. 감기 조심하세요.", "우산 같이 쓰실래요?"],
               "snow": ["눈이 와요! 같이 걸어요, 지휘관님.", "손이 차가우시네요…"],
               "hot": ["더우시죠? 시원한 거 드릴게요.", "땀 닦아 드릴까요?"],
               "cold": ["추우시죠? 목도리 둘러 드릴게요.", "따뜻하게 하고 다니세요."]},
    "dorothy": {"rain": ["빗소리가 고요하네요, 귀하.", "젖으면 곤란해요. 우산 아래로 오세요."],
                "snow": ["눈이 내리는군요… 아름다워요.", "눈덩이라… 유치하지만, 한 번쯤은."],
                "hot": ["더위는 숙녀의 적이에요.", "그늘로 가요, 귀하."],
                "cold": ["추위엔 따뜻한 차가 제일이죠.", "손을 녹여 드릴까요, 귀하?"]},
    "scarlet": {"rain": ["비라… 검이 녹슬겠군.", "우산은 거추장스럽지만, 오늘만은."],
                "snow": ["눈이로군. 수련하기 좋은 날이다.", "눈덩이도 검처럼 베어 주지."],
                "hot": ["덥군… 술이라도 한잔 하고 싶다.", "이 더위엔 검을 쥐기도 싫구나."],
                "cold": ["추위쯤이야. …조금 춥군.", "따뜻한 술 한잔이면 된다."]},
    "bingha": {"rain": ["비 온다! 우산 우산!", "비 오는 날엔 집에 있자~"],
               "snow": ["눈이다~! 눈사람 만들자!", "눈 먹으면 안 돼… 진짜?"],
               "hot": ["더워어… 아이스크림 사 줘~", "녹아 버릴 거 같아…"],
               "cold": ["추워추워~ 손 잡아 줘!", "꽁꽁 얼었어…"]},
    "chune": {"rain": ["비가 오네요~ 우산 챙기셨어요?", "빗소리 들으면서 쉬어요~"],
              "snow": ["눈 와요! 눈싸움 해요!", "첫눈엔 소원 빌어야죠~"],
              "hot": ["더워요… 부채 좀 부쳐 주세요~", "시원한 거 먹으러 가요!"],
              "cold": ["추워요~ 따뜻하게 입어요!", "손 시려워라…"]},
    "dokcake": {"rain": ["비 온다~ 오늘 방송 각이다!", "우산 없으면 내 거 써~"],
                "snow": ["눈싸움이다! 뚝딱 눈덩이!", "강아지가 눈 보면 좋아하겠다~"],
                "hot": ["더워 죽겠다… 냉면 먹자", "에어컨 틀어 줘!!"],
                "cold": ["추워!! 억울해!", "따뜻한 거… 따뜻한 거 줘…"]},
    "delia": {"rain": ["비가 오네요… 검이 녹슬면 안 되는데.", "우산 같이 쓰실래요, 용병님?"],
              "snow": ["눈이다! 델시아 왕궁에서도 이렇게 쌓였었어요.", "눈싸움이에요! 기사는 지지 않아요!"],
              "hot": ["갑옷 안이 너무 더워요…", "딸기 빙수 먹고 싶어요…"],
              "cold": ["갑옷이 차가워서 손이 시려요…", "따뜻한 홍차 한 잔 어때요?"]},
}
WEATHER_GENERIC = {"rain": ["비 온다~ 우산 챙겨!", "빗소리 좋다~", "으앗, 비 맞았어!"],
                   "snow": ["눈 온다~!", "눈싸움 하자!", "눈사람 만들고 싶어~"],
                   "hot": ["더워어… 녹는다…", "아이스크림 먹고 싶다~", "부채질 부채질…"],
                   "cold": ["추워추워…", "손 시려~", "따뜻한 거 마시고 싶다"]}
_W = {"app": None}


def _wx_kind(temp, code):
    if code is None:
        return None
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99):
        return "rain"
    if temp is not None and temp >= 27:
        return "hot"
    if temp is not None and temp <= 2:
        return "cold"
    return "cloud" if code in (2, 3, 45, 48) else "clear"


def _wx_fetch():
    """뒤에서 실행: 인터넷 위치(대략) → 현재 기온·날씨 코드"""
    import urllib.request

    def get(u):
        req = urllib.request.Request(u, headers={"User-Agent": "MiniBuddies-pet"})
        return json.loads(urllib.request.urlopen(req, timeout=8).read().decode("utf-8"))
    try:
        lat = lon = None; city = ""
        for u in ("https://ipapi.co/json/", "https://get.geojs.io/v1/ip/geo.json", "https://ipwho.is/"):
            try:
                g = get(u)
                lat, lon = float(g["latitude"]), float(g["longitude"]); city = g.get("city") or ""
                break
            except Exception:
                continue
        if lat is None:
            lat, lon, city = 37.5665, 126.978, "서울"
        w = get("https://api.open-meteo.com/v1/forecast?latitude=%.3f&longitude=%.3f"
                "&current=temperature_2m,weather_code&timezone=auto" % (lat, lon))
        cur = w["current"]
        WEATHER["new"] = (city, float(cur["temperature_2m"]), int(cur["weather_code"]))
    except Exception:
        WEATHER["next"] = time.time() + 600          # 실패하면 10분 뒤 다시
    finally:
        WEATHER["busy"] = False


def _wx_on(app):
    return bool(app.cfg.get("weather", True))


def _wx_has(app, b):
    """이 캐릭터(지금 의상)에 날씨 그림(100번)이 있는지"""
    c = app.chars.get(b.char) or {}
    if "_wok" not in c:
        c["_wok"] = os.path.exists(os.path.join(c.get("dir", ""), "100.png"))
    return c["_wok"]


def _wx_line(app, b, kind):
    d = WEATHER_LINES.get(f"{b.char}@{app.outfit.get(b.char)}") or WEATHER_LINES.get(b.char) or {}
    return random.choice(d.get(kind) or WEATHER_GENERIC.get(kind) or ["오늘 날씨 어때?"])


def weather_label(self):
    k = WEATHER.get("kind")
    if k is None:
        return "날씨 놀이 (날씨 확인 중…)"
    t = WEATHER.get("temp")
    return f"날씨 놀이 ({WEATHER.get('city') or '여기'} {WEATHER_NAME.get(k, k)} {t:.0f}°C)"


def _wx_event(self, force=False, who=None, announce=False):
    k = WEATHER.get("kind")
    live = [b for b in self.buddies if _pep_free(self, b)]
    if not live and force:
        live = [b for b in self.buddies if b.drag is None and b.surface]
    if not live:
        if force and self.buddies:
            random.choice(self.buddies).say("다들 바빠서 지금은 못 놀아요… 바닥에 내려오면 다시 해 봐요!", 150)
        return False
    if k in (None, "clear", "cloud"):
        if force:
            a = who if who in live else random.choice(live)
            if k is None:
                a.say("날씨 알아보는 중이야~ 조금만 기다려!", 150)
            else:
                t = WEATHER.get("temp")
                a.say(f"지금 {WEATHER.get('city') or '여기'} 날씨는 {WEATHER_NAME[k]}, {t:.0f}°C야~ 놀기 딱 좋다!", 200)
                a.play_seq([(F["cheer"], 60), (F["wave"], 60)])
        return False
    a = who if who in live else random.choice(live)
    a.goal = None; a.vx = 0
    has = _wx_has(self, a)
    a.say(_wx_line(self, a, k), 200)
    if k == "rain":
        if not has or random.random() < 0.6:
            a.play_seq([(100, 200)] if has else [(F["umbrella"][0], 120)])
        else:
            a.play_seq([(103, 22), (F["land"], 10), (103, 22), (F["cheer"], 40)])
    elif k == "snow":
        pals = [b for b in live if b is not a and b.surface == a.surface and abs(b.cx - a.cx) < a.S * 4]
        if has and pals and random.random() < 0.7:
            o = min(pals, key=lambda x: abs(x.cx - a.cx))
            a.face = 1 if o.cx > a.cx else -1
            o.goal = None; o.vx = 0
            a.play_seq([(105, 45), (F["lol"], 50)])

            def hit():
                if o in self.buddies:
                    o.play_seq([(F["hit"], 20), (F["surprise"], 30), (105 if _wx_has(self, o) else F["angry"], 45)])
                    o.say(random.choice(["으악 차가워!", "앗 차거! 받아라!", "눈덩이 맞았다~!"]), 120)
            QTimer.singleShot(int(28 * TICK), hit)
        else:
            a.play_seq([(104, 160)] if has else [(F["surprise"], 40), (F["cheer"], 60)])
    elif k == "hot":
        a.play_seq([(random.choice((106, 107)), 200)] if has else [(F["eat"], 160)])
    elif k == "cold":
        a.play_seq([(104, 200)] if has else [(F["cry"], 60)])
    return True


def weather_event(self, force=False, who=None, announce=False):
    try:
        return _wx_event(self, force, who, announce)
    except Exception:
        import traceback
        _crash_write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] 날씨 놀이 오류\n" + traceback.format_exc())
        return False

def install(App, Buddy):
    """Attach the weather behavior to the application."""
    F.update(dict(w_umb=100, w_umbwalk=101, w_rainrun=102, w_splash=103, w_cold=104, w_snowball=105, w_hot=106, w_icecream=107))
    FALLBACK.update({100: 20, 101: 20, 102: 8, 103: 10, 104: 0, 105: 12, 106: 0, 107: 15})
    try:
        _wx_orig_frame = Buddy.frame

        def _wx_frame(self):
            f = _wx_orig_frame(self)
            app = _W["app"]
            k = WEATHER.get("kind")
            if app is None or k not in ("rain", "snow", "hot", "cold") or not _wx_on(app):
                return f
            if getattr(self, "_wk", None) != k:          # 날씨가 바뀌면 이 아이가 날씨 모습을 할지 새로 정함
                self._wk = k
                self._wmode = random.random() < {"rain": 0.8, "snow": 0.5, "hot": 0.4, "cold": 0.6}[k]
            if not self._wmode or not _wx_has(app, self):
                return f
            st = self.state
            if k == "rain":
                if st == "walk":
                    return 101 if (self.anim // 10) % 2 else 100
                if st == "idle":
                    return 100
                if st == "run":
                    return 102
            elif st == "idle":
                return 106 if k == "hot" else 104
            return f
        Buddy.frame = _wx_frame

        _wx_orig_resolve = App.resolve

        def _wx_resolve(self, char, f):
            if f >= 100:                                  # 날씨 그림 위치 정보(meta_weather.json)를 처음 쓸 때 합침
                c = self.chars.get(char)
                if c is not None and not c.get("_wmeta"):
                    c["_wmeta"] = 1
                    try:
                        raw = json.load(open(os.path.join(c["dir"], "meta_weather.json"), encoding="utf-8"))
                        c["meta"].update({int(k): v for k, v in raw["frames"].items()})
                    except Exception:
                        pass
            return _wx_orig_resolve(self, char, f)
        App.resolve = _wx_resolve
        App.weather_event = weather_event
        App.weather_label = weather_label
        _wx_orig_minute = App.minute_tick

        def _wx_minute(self):
            _wx_orig_minute(self)
            try:
                _W["app"] = self
                if not _wx_on(self):
                    return
                now = time.time()
                if now >= WEATHER["next"] and not WEATHER["busy"]:
                    WEATHER["busy"] = True
                    WEATHER["next"] = now + 1800                 # 30분마다
                    threading.Thread(target=_wx_fetch, daemon=True).start()
                if WEATHER["new"]:
                    city, temp, code = WEATHER["new"]; WEATHER["new"] = None
                    old = WEATHER["kind"]
                    WEATHER.update(city=city, temp=temp, code=code, kind=_wx_kind(temp, code))
                    if WEATHER["kind"] != old and WEATHER["kind"] in ("rain", "snow", "hot", "cold") and not self.quiet():
                        self.weather_event(announce=True)
                    return
                h = datetime.datetime.now().hour
                if WEATHER["kind"] in ("rain", "snow", "hot", "cold") and 7 <= h <= 23 and random.random() < 0.15 \
                        and not self.quiet():
                    self.weather_event()
            except Exception:
                pass
        App.minute_tick = _wx_minute
    except Exception as _e:
        print("weather hook failed:", _e)
