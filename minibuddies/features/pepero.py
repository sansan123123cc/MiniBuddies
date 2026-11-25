"""Pepero Day interactions and drawings."""

import datetime
import random
import time
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPainter
from minibuddies.catalog import CASUAL_CHARS, CHAR_CALL, DEFAULT_CALL, F, SQUADS, TICK
from minibuddies.runtime import _crash_write
from minibuddies.ui.widgets import Burst


# ── 빼빼로데이(11/11) 놀이: 기존 프레임 + 코드로 그린 빼빼로 → 모든 캐릭터·모든 의상 공통 ──
PEPERO_LINES = {
    "anis": {"give": ["{n}, 빼빼로 하나 줄게~ 탄산수랑 먹으면 꿀맛!", "오늘 빼빼로데이잖아? 아니스 특별 배급~"],
             "thanks": ["오, 나 주는 거야? 땡큐~!", "빼빼로 득템! 오늘 운 좋다~"],
             "game": ["빼빼로 게임 한 판? 먼저 놓는 사람이 지는 거다~", "도전? 아니스는 안 져~"],
             "user": ["{call}! 빼빼로 받아~ 아니스 특별 서비스야", "오늘 빼빼로데이인 거 알지? 자, {call} 몫!"]},
    "arisa": {"give": ["{n}님… 빼빼로 드릴게요. 콜라랑 같이 드세요", "빼빼로데이라서요… 하나 받으세요"],
              "thanks": ["어… 저 주시는 거예요? 감사합니다…!", "빼빼로…! 켠왕할 때 먹을게요"],
              "game": ["빼빼로 게임… 저 이거 진심으로 할 거예요", "먼저 부러뜨리면 지는 거예요?"],
              "user": ["{call}… 빼빼로 드릴게요. 식사는 하셨나요?", "오늘 빼빼로데이래요… {call} 몫 챙겨 왔어요"]},
    "bingha": {"give": ["{n}, 청초한 토끼가 빼빼로 줄게요~", "빼빼로데이 기념! 받아요~"],
               "thanks": ["헉 저 주는 거예요? 감동이에요…", "빼빼로 최고예요! 고마워요~"],
               "game": ["빼빼로 게임 해요! 저 청초하게 이길 거예요", "억까 없기예요? 시작!"],
               "user": ["{call}, 빼빼로 받아요~ 밥은 먹었어요?", "오늘 빼빼로데이! {call} 거 챙겼어요~"]},
    "chune": {"give": ["{n}아, 빼빼로 하나 묵어라!", "빼빼로데이 아이가~ 이거 받아라"],
              "thanks": ["오 내 주는 기가? 고맙데이!", "빼빼로 땡큐~ 맛있게 묵을게"],
              "game": ["빼빼로 게임 하자! 내 안 진다이~", "먼저 놓는 사람이 지는 기다?"],
              "user": ["{call}! 빼빼로 묵었나? 이거 받아라", "오늘 빼빼로데이다~ {call} 꺼 챙겼데이"]},
    "dokcake": {"give": ["{n}, 독쌤이 빼빼로 나눠 준다죠~", "빼빼로데이 특별 수업! 받아 가세요~"],
                "thanks": ["어? 저 주시는 겁니까~? 끼이이~!", "빼빼로 감사합니다~ 개떡이들한테 자랑해야지"],
                "game": ["빼빼로 게임 한다죠~ 독쌤 안 져요", "자, 수업 시작! 빼빼로 게임!"],
                "user": ["{call}~ 빼빼로 받아 가세요~", "빼빼로데이인데 {call} 거 없으면 섭하죠~ 자!"]},
    "dorothy": {"give": ["{n}, 빼빼로라는 걸 준비했어요. 티타임에 곁들이세요.", "후후, 오늘은 빼빼로를 나누는 날이라더군요."],
                "thanks": ["어머, 저에게? …나쁘지 않네요.", "후후, 귀하의 성의는 받아 두죠."],
                "game": ["빼빼로 게임… 흥미롭네요. 상대해 드리죠.", "먼저 물러서는 쪽이 지는 거예요. 후후."],
                "user": ["{call}, 빼빼로예요. 특별히 드리는 거랍니다.", "오늘은 빼빼로데이. {call}의 몫도 챙겨 두었어요."]},
    "ellie": {"give": ["{n}! 빼빼로 줄게, 냥~", "빼빼로데이 기념 익스플로전… 아니 선물!"],
              "thanks": ["얄루~ 나 주는 거야? 땡큐냥!", "빼빼로다! 롤 하면서 먹어야지"],
              "game": ["빼빼로 게임 하자! 지면 익스플로전이다", "냥! 먼저 놓으면 지는 거야~"],
              "user": ["{call}, 빼빼로 받아라냥~", "오늘 빼빼로데이! {call} 거 챙겨 왔어"]},
    "elysia": {"give": ["{n}~ 빼빼로 받아 줄래? 마음도 같이 담았어♪", "어머, 오늘 빼빼로데이잖아♪ 하나 줄게~"],
               "thanks": ["어머, 나한테? 나 울어버릴 거야~!", "고마워♪ 역시 다들 너무 귀엽다니까~"],
               "game": ["빼빼로 게임 할래? 귀여운 소녀랑 하는 거니까 영광이지♪", "후후, 먼저 부러뜨리면 지는 거야~♪"],
               "user": ["{call}~ 빼빼로 받아 줘♪ 오늘은 내 생일이기도 하다구~", "기분이 어때? 빼빼로 받은 기분♪"]},
    "eris": {"give": ["앙용~ {n}, 빼빼로 줄게!", "빼빼로데이니까 하나 받아~ 민트초코 맛은 없더라"],
             "thanks": ["헤헤, 나 주는 거야? 땡큐~", "빼빼로 받았다! 근끼한테 자랑해야지"],
             "game": ["빼빼로 게임 하자! 나 안해… 는 아니고 할래!", "먼저 놓으면 지는 거다~"],
             "user": ["{call}~ 빼빼로 받아! 앙용~", "오늘 빼빼로데이야! {call} 거야"]},
    "hina": {"give": ["{n}, 빼빼로 줄게요! 명천재의 선물!", "빼빼로데이 기념 도파민 충전~"],
             "thanks": ["헉 저 주는 거예요? 다이아 각이다!", "빼빼로 감사해요~ 최고!"],
             "game": ["빼빼로 게임 한 판 해요! 이번엔 다이아 각!", "먼저 부러뜨리면 지는 거예요!"],
             "user": ["{call}, 빼빼로 받아요! 명천재가 주는 거예요", "오늘 빼빼로데이! {call} 몫이에요~"]},
    "hiyori": {"give": ["{n}, 빼빼로 줄게요~ 하핫", "빼빼로데이래요! 하나 받아요~"],
               "thanks": ["하핫, 저 주는 거예요? 고마워요~", "기특하다구? 빼빼로 고마워요~"],
               "game": ["빼빼로 게임이요? 해 볼게요~ 하핫", "먼저 놓으면 지는 거죠? 좋아요!"],
               "user": ["{call}, 빼빼로 받아요~", "오늘 빼빼로데이래요! {call} 거 챙겼어요"]},
    "huya": {"give": ["{n}… 빼빼로 드릴게요. 후하요~", "빼빼로데이라서… 이거 받아요"],
             "thanks": ["…네? 저 주시는 거예요? (고장)", "후하요~ 빼빼로 감사합니다"],
             "game": ["빼빼로 게임… 저도 끼워 주세요", "에휴, 지면 어떡하지… 시작해요"],
             "user": ["{call}… 빼빼로 받아요. 후하요~", "오늘 빼빼로데이래요… {call} 거예요"]},
    "kanna": {"give": ["{n}, 빼빼로 받아요! 칸나가 주는 거예요~", "빼빼로데이 기념! 레몬맛은 없더라구요"],
              "thanks": ["와 저 주는 거예요? 고마워요!", "빼빼로…! 그냥 느껴~ 행복해요"],
              "game": ["빼빼로 게임 해요! 그냥 느껴~", "먼저 놓는 사람이 지는 거예요!"],
              "user": ["{call}, 빼빼로 받아요~", "오늘 빼빼로데이! {call} 거 챙겼어요"]},
    "karin": {"give": ["{n}! 카린이 빼빼로 줄게~❤️", "빼빼로데이잖아! 하나 받아~"],
              "thanks": ["꺄~ 나 주는 거야? 고마워❤️", "빼빼로다! 네일 보면서 먹어야지~"],
              "game": ["빼빼로 게임 할래? 카린 안 질 거야~", "먼저 놓으면 지는 거다~❤️"],
              "user": ["{call}~ 빼빼로 받아❤️", "오늘 빼빼로데이! {call} 거 특별히 챙겼어"]},
    "lize": {"give": ["{n}… 빼빼로 줄게. 느엥…", "빼빼로데이래… 하나 받아"],
             "thanks": ["…나 주는 거야? 고마워…", "느엥… 빼빼로 좋아"],
             "game": ["빼빼로 게임…? 해 볼까…", "…낯가리는데 그래도 할래"],
             "user": ["{call}… 빼빼로 받아", "오늘 빼빼로데이래… {call} 거야"]},
    "marian": {"give": ["{n}, 빼빼로예요. 다친 데 없죠?", "빼빼로데이래요. 하나 받으세요"],
               "thanks": ["저한테요? 고마워요…!", "빼빼로… 소중히 먹을게요"],
               "game": ["빼빼로 게임이요? 조, 조심히 할게요", "먼저 놓으면 지는 거죠?"],
               "user": ["{call}, 빼빼로 받아 주세요. 오늘도 고생 많았어요", "오늘 빼빼로데이래요. {call} 몫이에요"]},
    "mary": {"give": ["{n}, 빼빼로 줄게 냐", "빼빼로데이다 냐. 받아라 냐"],
             "thanks": ["메리 주는 거냐? 고맙다 냐", "빼빼로다 냐! 솜보다 좋다 냐"],
             "game": ["빼빼로 게임 하자 냐! 안 진다 냐", "먼저 놓으면 지는 거다 냐"],
             "user": ["{call}, 빼빼로 받아라 냐", "오늘 빼빼로데이다 냐. {call} 거다 냐"]},
    "mashiro": {"give": ["{n}, 빼빼로 줄게~ 흠흐밍", "빼빼로데이 상황극 시작! 받아~"],
                "thanks": ["꺄르륵 나 주는 거야? 고마워~", "빼빼로 받았다 흠흐밍~"],
                "game": ["자, 지금부터 빼빼로 게임 상황극이야", "먼저 놓으면 밍이다~"],
                "user": ["{call}~ 빼빼로 받아! 흠흐밍", "오늘 빼빼로데이야~ {call} 거야"]},
    "nana": {"give": ["{n}, 빼빼로 하나 묵어 보쏘!", "빼빼로데이다이가~ 받아라!"],
             "thanks": ["이거 나 주는 기가? 대박이제!", "으하하 빼빼로다! 고맙다~"],
             "game": ["빼빼로 게임 하자! 나나 안 진다!", "그거는 내가 설명해 줄게, 먼저 놓으면 지는 기다"],
             "user": ["{call}, 빼빼로 받아 보쏘!", "오늘 빼빼로데이다! {call} 꺼다~"]},
    "rang": {"give": ["{n}, 빼빼로 줄게! 어흥!", "빼빼로데이 기념! 받아~"],
             "thanks": ["나 주는 거야? 완전 대박!", "빼빼로 고마워! 쑥맛 아니지?"],
             "game": ["빼빼로 게임 하자! 랑이 30초 컷!", "먼저 놓으면 지는 거야!"],
             "user": ["{call}! 빼빼로 받아~ 어흥!", "오늘 빼빼로데이! {call} 거야"]},
    "rapi": {"give": ["{n}, 보급품이다. 빼빼로.", "오늘은 빼빼로를 나누는 날이라고 들었다."],
             "thanks": ["…나에게? 고맙다.", "보급품 수령 완료. 잘 먹겠다."],
             "game": ["빼빼로 게임… 작전으로 받아들이겠다.", "먼저 놓는 쪽이 패배. 개시한다."],
             "user": ["{call}, 빼빼로다. 받아 둬.", "오늘은 빼빼로데이. {call}의 몫이다."]},
    "riko": {"give": ["하이용사! {n}, 빼빼로 줄게!", "리코가 주는 빼빼로다~"],
             "thanks": ["아하하 나 주는 거야? 고마워!", "빼빼로다! 리코 천재 아니야?"],
             "game": ["빼빼로 게임 하자! 리코 기록 깰 거야", "먼저 놓으면 지는 거다~"],
             "user": ["{call}, 빼빼로 받아! 하이용사~", "오늘 빼빼로데이! {call} 거야"]},
    "rin": {"give": ["{n}, 빼빼로 하나 줄게요~", "빼빼로데이라 챙겨 왔어요, anyone?"],
            "thanks": ["어, 저 주는 거예요? 고마워요!", "뇨… 빼빼로 너무 좋아요"],
            "game": ["빼빼로 게임 해요! 노래하면서 할까요?", "먼저 놓으면 지는 거예요~"],
            "user": ["{call}, 빼빼로 받아요~", "오늘 빼빼로데이! {call} 거 챙겼어요"]},
    "scarlet": {"give": ["{n}, 빼빼로 하나 받게. 달빛 안주로 딱일세.", "허허, 오늘은 빼빼로를 나누는 날이라더군."],
                "thanks": ["허허, 날 주는 겐가? 고맙네.", "빼빼로라… 술안주로 아껴 두겠네."],
                "game": ["빼빼로 게임이라… 상대해 주지.", "먼저 놓는 쪽이 지는 걸세."],
                "user": ["{call}, 빼빼로일세. 받아 두게.", "오늘은 빼빼로데이라더군. {call} 몫일세."]},
    "shibuki": {"give": ["자자 {n}, 빼빼로 간다!", "빼빼로데이잖아! 받아~"],
                "thanks": ["구라야~ 나 주는 거야? 고마워!", "빼빼로다! 결론은 맛있다!"],
                "game": ["빼빼로 게임 하자! 결론은 내가 이긴다", "먼저 놓으면 지는 거다!"],
                "user": ["{call}! 빼빼로 받아~", "오늘 빼빼로데이! {call} 거야"]},
    "tabi": {"give": ["{n}, 빼빼로 줄게! 타비가 챙겼어", "빼빼로데이 보물이다! 받아~"],
             "thanks": ["나 주는 거야? 고마워! 보물 1호!", "빼빼로다~ 소중히 챙길게"],
             "game": ["빼빼로 게임 하자! 타비 안 져!", "먼저 놓으면 지는 거야!"],
             "user": ["{call}, 빼빼로 받아! 내가 챙겼어", "오늘 빼빼로데이! {call} 거야"]},
    "toa": {"give": ["{n}, 빼빼로 하나 줄게~", "빼빼로데이라서 챙겨 왔어"],
            "thanks": ["나 주는 거야? 고마워~", "빼빼로다! 하나도 안 무서워~"],
            "game": ["빼빼로 게임? 하나도 안 무서워!", "먼저 놓으면 지는 거야~"],
            "user": ["{call}, 빼빼로 받아~", "오늘 빼빼로데이! {call} 거야"]},
    "yuni": {"give": ["{n}, 빼빼로 줄게 욘서~", "빼빼로데이라 와~ 받아"],
             "thanks": ["유니 주는 거야? 배고팠어 와~", "빼빼로다! 유니는 귀여우니까 욘서~"],
             "game": ["빼빼로 게임 하자 와~", "먼저 놓으면 지는 거야 욘서~"],
             "user": ["{call}, 빼빼로 받아 욘서~", "오늘 빼빼로데이 와~ {call} 거야"]},
    "delia": {"give": ["{n}, 빼빼로 받으세요! 기사의 선물이에요.", "오늘은 빼빼로데이래요! 하나씩 나눠 드릴게요~"],
              "thanks": ["어머, 저에게요? 감사합니다!", "후후, 딸기 맛이면 더 좋았을 텐데… 그래도 고마워요!"],
              "game": ["빼빼로 게임이요? 기사는 물러서지 않아요!", "승부라면 자신 있어요. 시작해요!"],
              "user": ["{call}, 빼빼로예요! 오늘 의뢰 보수랍니다.", "빼빼로데이니까 {call} 몫도 챙겨 뒀어요!"]},
}
# 의상마다 말투가 확 달라지는 경우만 따로 (나머지 의상은 캐릭터 대사를 그대로 씀)
PEPERO_LINES_OUTFIT = {
    "dorothy@doro": {"give": ["도로롱! (빼빼로를 내민다)", "도로~ 도로롱~♪"], "thanks": ["도로롱!!", "도로도로~♪"],
                     "game": ["도로롱? 도로!", "도로롱~!"], "user": ["도로롱~ (빼빼로를 내민다)", "도로!♪"]},
}
PEPERO_GENERIC = {"give": ["{n}, 빼빼로 줄게~", "오늘 빼빼로데이잖아! 하나 받아~"],
                  "thanks": ["나 주는 거야? 고마워!", "빼빼로다! 잘 먹을게~"],
                  "game": ["빼빼로 게임 할래? 먼저 놓으면 지는 거야~", "빼빼로 게임 한 판!"],
                  "user": ["{call}, 빼빼로 받아~", "오늘 빼빼로데이! {call} 거야"]}
PEPERO_END = {"nom": ["냠…", "냠냠…", "두근두근…", "조금만 더…"],
              "break": ["뚝! 앗, 부러졌다!", "앗! 부러져 버렸어!"],
              "draw": ["무승부다~!", "아깝다~ 한 판 더?"],
              "lose": ["으앗, 못 하겠어!", "졌다… 부끄러워~"],
              "win": ["내가 이겼다~!", "빼빼로 게임 승리!"]}


def _pep_ms(t):
    return int(t * TICK)


def _pepero_day():
    """오늘이 빼빼로데이(11월 11일)인지 — 빼빼로 놀이 메뉴는 이날에만 보임"""
    return datetime.datetime.now().strftime("%m-%d") == "11-11"


def _pep_call(app, c):
    sq = next((s for s, m in SQUADS.items() if c in m), "")
    return app.cfg.get("my_name") or CHAR_CALL.get(c) or DEFAULT_CALL.get(sq, "") or "주인"


def _pep_say(app, b, kind, other=None, t=120):
    if b not in app.buddies:
        return
    k = f"{b.char}@{app.outfit.get(b.char)}"
    d = PEPERO_LINES_OUTFIT.get(k) or PEPERO_LINES.get(b.char) or PEPERO_GENERIC
    line = random.choice(d.get(kind) or PEPERO_GENERIC[kind])
    lab = app.chars.get(other.char, {}).get("label", "친구") if other is not None else "친구"
    b.say(line.replace("{n}", lab).replace("{call}", _pep_call(app, b.char)), t)


def _pep_set(b, kind=None, partner=None, bis=False):
    """kind: box(선물 상자) / stick(빼빼로 게임, 짝꿍까지 이어짐) / half(부러진 반쪽)"""
    b._pep = (kind, partner, bis) if kind else None
    try:
        b.update()
    except Exception:
        pass


def _pep_paint(b):
    from PyQt5.QtGui import QColor, QPen, QPainterPath
    from PyQt5.QtCore import QRectF, QPointF
    kind, partner, bis = b._pep
    S = float(b.S)
    f = b.frame()
    top, bot = b.ftop(f), b.fbottom(f)
    fc = 1 if (b.face or 1) > 0 else -1
    p = QPainter(b)
    p.setRenderHint(QPainter.Antialiasing)
    if kind == "box":                                   # 빨간 상자 + 위로 삐죽 나온 빼빼로 셋 + 흰 하트
        w, h = S * 0.15, S * 0.19
        cx = S / 2 + fc * S * 0.27
        cy = S * (top + (bot - top) * 0.56)
        x0, y0 = cx - w / 2, cy - h / 2
        pen = QPen(QColor(95, 52, 30), max(1.5, S * 0.016)); pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        for i in range(3):
            sx = x0 + w * (0.25 + 0.25 * i)
            p.drawLine(QPointF(sx, y0 + h * 0.2), QPointF(sx + (i - 1) * S * 0.012, y0 - h * 0.38))
        p.setPen(QPen(QColor(150, 20, 50), max(1.0, S * 0.006)))
        p.setBrush(QColor(232, 60, 95))
        p.drawRoundedRect(QRectF(x0, y0, w, h), w * 0.16, w * 0.16)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255))
        r = w * 0.18
        hx, hy = cx, cy
        p.drawEllipse(QPointF(hx - r * 0.55, hy - r * 0.35), r * 0.62, r * 0.62)
        p.drawEllipse(QPointF(hx + r * 0.55, hy - r * 0.35), r * 0.62, r * 0.62)
        path = QPainterPath()
        path.moveTo(hx - r * 1.12, hy - r * 0.15); path.lineTo(hx + r * 1.12, hy - r * 0.15); path.lineTo(hx, hy + r * 1.15)
        path.closeSubpath()
        p.drawPath(path)
    elif kind in ("stick", "half"):                     # 입에 문 빼빼로 (게임: 짝꿍과 가운데에서 만남)
        mx = S / 2 + fc * S * 0.11
        my = S * (top + (bot - top) * 0.40)
        if kind == "stick" and partner is not None and partner in b.app.buddies:
            ex = max(0.0, min(S, S / 2 + (partner.cx - b.cx) / 2))
        else:
            ex = mx + fc * S * 0.09
        th = max(2.0, S * 0.03)
        pen = QPen(QColor(95, 52, 30), th); pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(mx, my), QPointF(ex, my))
        if bis:                                         # 내 쪽 끝은 과자 손잡이
            pen2 = QPen(QColor(232, 188, 122), th); pen2.setCapStyle(Qt.RoundCap)
            p.setPen(pen2)
            p.drawLine(QPointF(mx, my), QPointF(mx + (ex - mx) * 0.28, my))
    p.end()


def _pep_free(app, b):
    return (b in app.buddies and b.surface and b.drag is None and b.state not in app.BUSY
            and b.state not in ("seq", "group", "tower", "train") and not getattr(b, "_pep", None))


def _pep_user(app, a):
    from PyQt5.QtGui import QCursor
    a.goal = None; a.vx = 0
    a.face = 1 if QCursor.pos().x() > a.cx else -1
    _pep_set(a, "box")
    a.play_seq([(F["hands"], 170), (F["cheer"], 60)], after=lambda: _pep_set(a, None))
    _pep_say(app, a, "user", t=170)
    QTimer.singleShot(_pep_ms(260), lambda: _pep_set(a, None))


def _pep_give(app, a, o):
    _pep_say(app, a, "give", o)

    def meet(me=None, other=None):
        if a not in app.buddies or o not in app.buddies:
            return
        for b in (a, o):
            b.vx = 0; b.goal = None
        a.face = 1 if o.cx > a.cx else -1
        o.face = -a.face
        _pep_set(a, "box")
        a.play_seq([(F["hands"], 80), (F["cheer"], 60)])
        o.play_seq([(F["surprise"], 80), (F["cheer"], 70), (F["photo"], 80)])

        def handover():
            _pep_set(a, None)
            if o in app.buddies:
                _pep_set(o, "box")
                _pep_say(app, o, "thanks", a)
        QTimer.singleShot(_pep_ms(80), handover)
        QTimer.singleShot(_pep_ms(240), lambda: _pep_set(o, None))
    if abs(a.cx - o.cx) < a.S * 1.15 or app.quiet():
        meet()
    else:
        a.go_to(o, "approach", ticks=500, arrive=meet)


def _pep_game(app, a, o):
    _pep_say(app, a, "game", o)

    def meet(me=None, other=None):
        if a not in app.buddies or o not in app.buddies or a.surface != o.surface:
            return
        for b in (a, o):
            b.vx = 0; b.goal = None
        d = 1 if o.cx >= a.cx else -1
        mid = (a.cx + o.cx) / 2
        gap = (a.S + o.S) / 2 * 0.64
        a.fx = mid - d * gap / 2 - a.S / 2
        o.fx = mid + d * gap / 2 - o.S / 2
        a.face = d; o.face = -d
        steps = 5
        stand = F["chat"]
        a.play_seq([(stand, 60 + steps * 50 + 10)]); o.play_seq([(stand, 60 + steps * 50 + 10)])
        _pep_set(a, "stick", o, True); _pep_set(o, "stick", a, False)

        def step(i):
            if a not in app.buddies or o not in app.buddies:
                return
            a.fx += d * a.S * 0.03; o.fx -= d * o.S * 0.03
            a.update(); o.update()
            if i % 2 == 0:
                random.choice((a, o)).say(random.choice(PEPERO_END["nom"]), 45)
        for i in range(steps):
            QTimer.singleShot(_pep_ms(60 + i * 50), lambda i=i: step(i))

        def end():
            if a not in app.buddies or o not in app.buddies:
                for b in (a, o):
                    _pep_set(b, None)
                return
            if random.random() < 0.7:                    # 뚝! 가운데서 부러짐
                y = a.fy + a.S * (a.ftop(stand) + (a.fbottom(stand) - a.ftop(stand)) * 0.40)
                Burst((a.cx + o.cx) / 2, y, a.S * 0.35)
                _pep_set(a, "half", None, True); _pep_set(o, "half")
                a.play_seq([(F["surprise"], 50), (F["lol"], 100)]); o.play_seq([(F["surprise"], 50), (F["lol"], 100)])
                a.say(random.choice(PEPERO_END["break"]), 90)
                QTimer.singleShot(_pep_ms(60), lambda: o in app.buddies and o.say(random.choice(PEPERO_END["draw"]), 90))
            else:                                        # 한 명이 먼저 포기
                lo, wi = random.sample([a, o], 2)
                _pep_set(lo, None); _pep_set(wi, "half", None, wi is a)
                lo.play_seq([(F["pout"], 110)]); wi.play_seq([(F["cheer"], 110)])
                lo.say(random.choice(PEPERO_END["lose"]), 90)
                QTimer.singleShot(_pep_ms(50), lambda: wi in app.buddies and wi.say(random.choice(PEPERO_END["win"]), 90))
            QTimer.singleShot(_pep_ms(160), lambda: (_pep_set(a, None), _pep_set(o, None)))
        QTimer.singleShot(_pep_ms(60 + steps * 50 + 20), end)
    if abs(a.cx - o.cx) < a.S * 1.15 or app.quiet():
        meet()
    else:
        a.go_to(o, "approach", ticks=500, arrive=meet)


def _pep_event(self, kind=None, force=False, who=None):
    if not force and getattr(self, "_pep_busy", 0) > time.time():
        return False
    if self.quiet() and not force:
        return False
    live = [b for b in self.buddies if _pep_free(self, b)]
    if not live and force:                              # 메뉴에서 시켰으면 하던 걸 멈추고서라도
        live = [b for b in self.buddies if b.drag is None and b.surface]
        for b in live:
            _pep_set(b, None)
    if force and who is not None and who in self.buddies and who not in live and who.drag is None:
        _pep_set(who, None)                             # 우클릭한 그 애가 꼭 주인공
        live.append(who)
    if not live:
        if force and self.buddies:
            random.choice(self.buddies).say("지금은 빼빼로 줄 수 있는 애가 없어요… 바닥에 내려오면 다시 해 봐요!", 150)
        return False
    a = who if who in live else random.choice(live)
    pals = [b for b in live if a.surface and b is not a and b.surface == a.surface
            and (not self.quiet() or abs(b.cx - a.cx) < a.S * 1.15)]
    if kind is None:
        kind = random.choice(["give", "give", "game", "game", "user"]) if pals else "user"
    if kind in ("give", "game") and not pals:
        kind = "user"
    self._pep_busy = time.time() + 22
    if kind == "user":
        _pep_user(self, a)
    else:
        o = min(pals, key=lambda x: abs(x.cx - a.cx))
        (_pep_give if kind == "give" else _pep_game)(self, a, o)
    return True


def pepero_event(self, kind=None, force=False, who=None):
    """빼빼로데이 놀이: give(친구에게 주기) / game(빼빼로 게임) / user(화면 주인에게 주기)"""
    try:
        return _pep_event(self, kind, force, who)
    except Exception:
        import traceback
        _crash_write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] 빼빼로 놀이 오류\n" + traceback.format_exc())
        if self.buddies:
            random.choice(self.buddies).say("빼빼로 놀이 중에 오류가 났어요 (crash.log 에 적어 뒀어요)", 200)
        return False

def install(App, Buddy):
    """Attach the pepero behavior to the application."""
    try:
        _pep_orig_paint = Buddy.paintEvent

        def _pep_paint_event(self, e):
            _pep_orig_paint(self, e)
            if getattr(self, "_pep", None):
                try:
                    _pep_paint(self)
                except Exception:
                    pass
        Buddy.paintEvent = _pep_paint_event
        App.pepero_event = pepero_event
        _pep_orig_minute = App.minute_tick

        def _pep_minute(self):
            try:  # 11/11 하루 한 번: 기념일 기본 축하 대신 다 같이 모여서 빼빼로데이 축하
                now = datetime.datetime.now()
                today = now.strftime("%Y-%m-%d")
                if _pepero_day() and now.hour >= 7 and self.cfg.get("event_day") != today \
                        and sum(1 for b in self.buddies if b.surface) >= 1:
                    self.cfg["event_day"] = today
                    self.save_cfg()
                    self.pepero_gather()
            except Exception:
                pass
            _pep_orig_minute(self)
            try:
                now = datetime.datetime.now()
                if _pepero_day() and 8 <= now.hour <= 23 and random.random() < 0.3:
                    self.pepero_event()
            except Exception:
                pass
        App.minute_tick = _pep_minute

        def _pep_shout(app, b):
            if app.outfit.get(b.char) == "doro":
                return random.choice(["도로롱~!♪", "도로도로~!!"])
            if b.char in CASUAL_CHARS:
                return random.choice(["빼빼로데이 축하해~!", "해피 빼빼로데이~!"])
            return random.choice(["빼빼로데이 축하해요~!", "해피 빼빼로데이!"])

        def pepero_gather(self):
            """빼빼로데이: 다 같이 한가운데 모여서 '빼빼로데이 축하해!' → 한 명씩 화면 주인에게 빼빼로 상자"""
            self._pep_busy = time.time() + 45
            live = [b for b in self.buddies if b.surface and b.drag is None]
            if self.team and len(self.buddies) >= 2:
                self.group_event("pepero", force=True)  # 모으기·재시도는 단체 놀이 쪽에서
                if live:
                    random.choice(live).say("다들 모여~ 오늘 빼빼로데이야!", 120)
                return
            for i, b in enumerate(live):  # 팀이 없으면 각자 자리에서 다 같이
                b.goal = None; b.vx = 0
                QTimer.singleShot(i * 250, lambda b=b: b in self.buddies and (b.set("cheer", 150), b.say(_pep_shout(self, b), 110)))
            for i, b in enumerate(live[:10]):
                QTimer.singleShot(4200 + i * 1700, lambda b=b: b in self.buddies and b.surface and _pep_user(self, b))
        App.pepero_gather = pepero_gather

        _pep_orig_gstart = App.group_start

        def _pep_gstart(self, g, mem):
            if g.get("kind") != "pepero":
                return _pep_orig_gstart(self, g, mem)
            cf = F["cheer"] if isinstance(F["cheer"], list) else [F["cheer"]]
            for b in mem:
                b.face = 1 if g["cx"] >= b.cx else -1
                b.gframe = [F["walk"][0]]
            mem[0].say("다들 모였지? 하나, 둘, 셋!", 90)

            def shout():
                for b in mem:
                    if b in self.buddies and b.state == "group":
                        b.face = 1; b.gframe = cf
                        b.say(_pep_shout(self, b), 110)
            QTimer.singleShot(1800, shout)
            giv = mem[:10]
            for i, b in enumerate(giv):  # 한 명씩 화면 주인에게 빼빼로 상자 내밀기
                def give(b=b):
                    if b in self.buddies and b.state == "group":
                        b.gframe = [F["hands"]]
                        _pep_set(b, "box")
                        _pep_say(self, b, "user", None, 130)

                def done(b=b):
                    _pep_set(b, None)
                    if b in self.buddies and b.state == "group":
                        b.gframe = cf
                QTimer.singleShot(5200 + i * 1700, give)
                QTimer.singleShot(5200 + i * 1700 + 3000, done)
            g["end_at"] = time.time() + 5.2 + len(giv) * 1.7 + 4.5
        App.group_start = _pep_gstart

        _pep_orig_grun = App.group_run

        def _pep_grun(self, g, mem, t):
            if g.get("kind") != "pepero":
                return _pep_orig_grun(self, g, mem, t)
            if time.time() > g.get("end_at", 0):
                for b in mem:
                    _pep_set(b, None)
                self.group_break()
        App.group_run = _pep_grun
    except Exception as _e:
        print("pepero hook failed:", _e)
