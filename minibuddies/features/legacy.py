"""Built-in seasonal, weather, rest and outfit behaviors."""

import datetime
import json
import math
import os
import random
import sys
import threading
import time
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPainter, QPixmap
from PyQt5.QtWidgets import QApplication, QMenu, QWidget
from minibuddies.catalog import (
    ALT_TF,
    APP_NAME,
    ASK_HELLO,
    CASUAL_CHARS,
    CHAR_BIO,
    CHAR_BIRTHDAY,
    CHAR_CALL,
    CRY_LINES,
    DEFAULT_CALL,
    F,
    FALLBACK,
    FLEE_LINES,
    OUTFIT_LINES,
    OUTFIT_NAME,
    PERSONA,
    SHOOT_LINES,
    SQUADS,
    THINK_LINES,
    TICK,
)
from minibuddies.runtime import _crash_write
from minibuddies.ui.widgets import Bubble, Burst


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




# ── 날씨 따라 행동하기 (인터넷 위치 → Open-Meteo 현재 날씨) ─────────────────────
# 10번 시트(날씨) 100~107: 우산 서기, 우산 걷기, 비 맞으며 뛰기, 물웅덩이 첨벙, 목도리 덜덜, 눈덩이 던지기, 부채질, 아이스크림
F.update(dict(w_umb=100, w_umbwalk=101, w_rainrun=102, w_splash=103, w_cold=104, w_snowball=105, w_hot=106, w_icecream=107))
FALLBACK.update({100: 20, 101: 20, 102: 8, 103: 10, 104: 0, 105: 12, 106: 0, 107: 15})

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





# ── 제자리 모드: 돌아다니지 않고 지금 그 자리에서 책 읽기·게임·뒹굴뒹굴 (수면 모드와 별개) ──────────
REST_LINES = {"read": ["이 책 재밌다~", "다음 장, 다음 장…", "책 읽는 중이야~ 쉿!"],
              "game": ["한 판만 더!", "보스까지 왔다…!", "앗 졌어! 다시!", "이겼다~!"],
              "roll": ["뒹굴뒹굴~", "아무것도 안 하고 싶다~", "바닥 시원해~"],
              "nap": ["쿨…", "잠깐만 눈 붙일게…"],
              "snack": ["간식 타임~", "냠냠"],
              "sing": ["흥얼흥얼~♪", "라라라~"]}
_REST_COLORS = [(255, 170, 200), (150, 205, 255), (255, 214, 120), (180, 230, 170)]


def _rest_on(app):
    return bool(app.cfg.get("rest_mode", False)) and not app.cfg.get("sleep_mode", False)


def _rest_set_game(b, on):
    b._rest_game = bool(on)
    try:
        b.update()
    except Exception:
        pass


REST_GAME_END = {112: ["이겼다~!", "클리어~!", "신기록이야!"], 113: ["앗 졌어! 다시!", "으앙 한 판만 더…", "이건 게임이 이상한 거야!"],
                 115: ["쿨… 게임하다 잠들었어…", "졸려…"]}
FALLBACK.update({108: 64, 109: 64, 110: 64, 111: 64, 112: 11, 113: 16, 114: 64, 115: 41})


def _rest_has_game(app, b):
    try:
        c = app.chars.get(b.char) or {}
        if "_game" not in c:
            c["_game"] = os.path.exists(os.path.join(c.get("dir", ""), "108.png"))
        return c["_game"]
    except Exception:
        return False


def _rest_game_seq():
    """앉아서·엎드려서·서서 게임하다가 이기거나 지거나 졸기"""
    a, c = random.choice(((108, 109), (108, 109), (110, 111), (114, 114)))
    seq = []
    for _ in range(random.randint(8, 16)):
        seq += [(a, random.randint(20, 40)), (c, random.randint(10, 24))]
    end = random.choices([112, 113, 115], weights=[45, 35, 20])[0]
    seq.append((end, 160 if end == 115 else 90))
    return seq, end


def _rest_play(app, b):
    """제자리 모드에서 다음 할 일 하나 (걷지 않음)"""
    b.vx = 0; b.goal = None
    w = {"read": 26, "game": 26, "roll": 20, "nap": 8, "snack": 8, "sing": 6, "persona": 6}
    per = app.chars.get(b.char, {}).get("persona")
    if not per:
        w["persona"] = 0
    k = random.choices(list(w), weights=list(w.values()))[0]
    if k == "persona":
        try:
            it = random.choice(per)
            fr = it[0]
            b.play_seq([(fr[i % len(fr)], max(6, it[1])) for i in range(len(fr) * 3)])
            return
        except Exception:
            k = "read"
    if random.random() < 0.25:
        b.say(random.choice(REST_LINES.get(k, ["~"])), 150)
    if k == "read":
        b.play_seq([(F["read"], random.randint(300, 700))])
    elif k == "game" and _rest_has_game(app, b):            # 게임기 그림(108~115)이 있는 의상
        seq, end = _rest_game_seq()
        b.play_seq(seq, after=lambda: b.say(random.choice(REST_GAME_END[end]), 120) if random.random() < 0.6 else None)
    elif k == "game":
        _rest_set_game(b, True)
        t = random.randint(300, 650)
        b.play_seq([(F["hands"], t)], after=lambda: _rest_set_game(b, False))
        QTimer.singleShot(int((t + 10) * TICK), lambda: _rest_set_game(b, False))
    elif k == "roll":
        a, c = F["wiggle"]
        b.play_seq([(a, 14), (c, 14)] * random.randint(6, 14))
    elif k == "nap":
        b.play_seq([(F["nap"], random.randint(300, 600)), (F["yawn"], 50)])
    elif k == "snack":
        b.play_seq([(random.choice((F["eat"], F["milk"])), random.randint(160, 280))])
    else:
        b.play_seq([(F["sing"], random.randint(150, 260))])


def _rest_paint(b):
    """게임할 때 손에 든 휴대용 게임기 (모든 캐릭터·의상 공통으로 코드로 그림)"""
    from PyQt5.QtGui import QColor, QPen
    from PyQt5.QtCore import QRectF, QPointF
    S = float(b.S)
    f = b.frame()
    if f != F["hands"]:
        return
    top, bot = b.ftop(f), b.fbottom(f)
    fc = 1 if (b.face or 1) > 0 else -1
    w, h = S * 0.24, S * 0.12
    cx = S / 2 + fc * S * 0.25
    cy = S * (top + (bot - top) * 0.56)
    x0, y0 = cx - w / 2, cy - h / 2
    col = _REST_COLORS[hash(b.char) % len(_REST_COLORS)]
    p = QPainter(b)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(70, 60, 80), max(1.0, S * 0.008)))
    p.setBrush(QColor(*col))
    p.drawRoundedRect(QRectF(x0, y0, w, h), h * 0.35, h * 0.35)
    t = time.time()
    g = int(150 + 80 * (0.5 + 0.5 * math.sin(t * 6)))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(90, g, 200))
    p.drawRoundedRect(QRectF(cx - w * 0.21, y0 + h * 0.18, w * 0.42, h * 0.64), h * 0.08, h * 0.08)
    p.setBrush(QColor(255, 255, 255, 200))                      # 화면 속 깜빡이는 점
    p.drawEllipse(QPointF(cx - w * 0.1 + w * 0.2 * (0.5 + 0.5 * math.sin(t * 3)), cy), h * 0.07, h * 0.07)
    p.setBrush(QColor(60, 50, 70))                              # 십자키
    dx = x0 + w * 0.15
    p.drawRect(QRectF(dx - h * 0.18, cy - h * 0.06, h * 0.36, h * 0.12))
    p.drawRect(QRectF(dx - h * 0.06, cy - h * 0.18, h * 0.12, h * 0.36))
    p.setBrush(QColor(235, 80, 110))                            # 버튼 두 개
    bx = x0 + w * 0.85
    p.drawEllipse(QPointF(bx, cy - h * 0.12), h * 0.09, h * 0.09)
    p.drawEllipse(QPointF(bx - h * 0.22, cy + h * 0.1), h * 0.09, h * 0.09)
    p.end()


def set_rest(self, on):
    """제자리 모드 켜고 끄기: 켜면 수면 모드는 꺼지고, 각자 지금 자리에서 놂"""
    self.cfg["rest_mode"] = bool(on)
    if on:
        self.cfg["sleep_mode"] = False
    self.save_cfg()
    for b in list(self.buddies):
        b._home = b.cx
        b.goal = None
        _rest_set_game(b, False)
        if on and b.surface and b.drag is None:
            b.choose()




# ── 도로시 모드 변신 (피나 전개 / 일반 모드): 빛이 모여 변신 → 특수 동작 몇 개 → 빛이 흩어지며 원래대로 ──
# 그림: 116 변신 순간(빛) / 117~122 모드 동작 / 123 원래대로 돌아가는 중 (meta_weather.json 에 위치 정보)
DMODE = {
    "dorothy@basic": {
        "menu": "피나 전개!",
        "start": ["피나, 전개.", "날개를 펼칠 시간이군요."],
        "acts": [([117], 170, ["후후, 이 날개가 마음에 드시나요?", "에덴의 날개랍니다."]),
                 ([118], 170, ["귀하는 그저 올려다보기만 하면 돼요.", "…아름답죠?"]),
                 ([119], 150, ["귀하를 낙원으로 안내하겠습니다.", "이쪽이에요, 귀하."]),
                 ([120, 121], 0, ["엄폐.", "…조준 완료. 의미 없는 저항은 지루할 뿐인데."]),
                 ([122], 120, ["깃털 하나 정도는 선물로 드리죠.", "후후."])],
        "end": ["…이 정도면 충분하겠죠.", "날개는 다시 접어 두죠."],
    },
    "dorothy@liberated": {
        "menu": "일반 모드로 쉬기",
        "start": ["잠시… 날개를 내려놓을게요.", "오늘은 그냥 저로 있을게요."],
        "acts": [([117], 170, ["이 옷, 어색하지 않나요?", "…몸이 가벼워요."]),
                 ([118], 140, ["안녕하세요, 귀하. 정식으로 인사드릴게요.", "후후, 오늘은 숙녀처럼."]),
                 ([119], 120, ["빙글~ 드레스가 예쁘죠?", "후후, 어지러워요."]),
                 ([120], 160, ["이런 평범한 하루가 좋아요.", "행복이라는 건 이런 거군요."]),
                 ([121], 180, ["꽃 향기가 좋아요.", "귀하도 맡아 보실래요?"]),
                 ([122], 130, ["다녀왔어요, 귀하.", "손 흔들어 주실래요?"])],
        "end": ["다시, 지키러 갈 시간이네요.", "…빛이여, 돌아와요."],
    },
}


def _dm_key(app, b):
    return f"{b.char}@{app.outfit.get(b.char)}"


def _dm_fx(b, t_in, t_out, t_end):
    """빛 효과: 0~t_in 빛 입자가 모여듦 → 번쩍 → t_out~t_end 빛 입자가 흩어짐 (초 단위)"""
    old = getattr(b, "_dm_timer", None)
    if old is not None:
        try:
            old.stop()
        except Exception:
            pass
    b._dm = {"t0": time.time(), "in": t_in, "out": t_out, "end": t_end}
    tm = QTimer(b)
    tm.setInterval(33)

    def tick():
        d = getattr(b, "_dm", None)
        if d is None or time.time() - d["t0"] > d["end"] + 0.6 or b.state != "seq" or b.drag is not None:
            b._dm = None
            tm.stop()
        try:
            b.update()
        except Exception:
            tm.stop()
    tm.timeout.connect(tick)
    tm.start()
    b._dm_timer = tm


def _dm_paint(b):
    from PyQt5.QtGui import QColor, QRadialGradient, QBrush
    from PyQt5.QtCore import QPointF
    d = b._dm
    now = time.time() - d["t0"]
    S = float(b.S)
    try:
        f = b.frame()
        cy = S * (b.ftop(f) + b.fbottom(f)) / 2
    except Exception:
        cy = S * 0.62
    c = QPointF(S / 2, cy)
    p = QPainter(b)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)

    def glow(a, r):
        g = QRadialGradient(c, r)
        g.setColorAt(0.0, QColor(255, 255, 245, int(max(0, min(255, a)))))
        g.setColorAt(0.45, QColor(255, 240, 210, int(max(0, min(255, a * 0.55)))))
        g.setColorAt(1.0, QColor(255, 230, 200, 0))
        p.setBrush(QBrush(g))
        p.drawEllipse(c, r, r)

    def dots(rad, a, spin, n=18):
        for i in range(n):
            ang = i * 2 * math.pi / n + spin + (i % 3) * 0.4
            rr = rad * (0.75 + 0.25 * ((i * 7) % 5) / 4)
            x, y = c.x() + math.cos(ang) * rr, c.y() + math.sin(ang) * rr * 0.9
            s = S * (0.012 + 0.01 * ((i * 3) % 4) / 3)
            p.setBrush(QColor(255, 248, 215, int(max(0, min(255, a)))))
            p.drawEllipse(QPointF(x, y), s, s)
            p.setBrush(QColor(255, 255, 255, int(max(0, min(255, a * 0.5)))))
            p.drawEllipse(QPointF(x, y), s * 2.1, s * 2.1)

    if now < d["in"]:  # 빛이 모여듦
        k = now / d["in"]
        glow(60 + 150 * k, S * (0.3 + 0.2 * k))
        dots(S * (0.5 * (1 - k) + 0.06), 230, now * 4.0)
    elif now < d["in"] + 0.45:  # 번쩍
        k = (now - d["in"]) / 0.45
        glow(240 * (1 - k), S * 0.5)
    elif d["out"] <= now < d["end"]:  # 다시 빛으로 → 흩어짐
        k = (now - d["out"]) / max(0.01, d["end"] - d["out"])
        if k < 0.35:
            glow(220 * (1 - k / 0.35), S * 0.5)
        dots(S * (0.08 + 0.42 * k), 230 * (1 - k), -now * 3.0)
    p.end()


def dmode_play(self, b, force=False):
    """도로시 모드 변신 특수 동작 (피나 전개 / 일반 모드)"""
    d = DMODE.get(_dm_key(self, b))
    if not d or b not in self.buddies or b.drag is not None or not b.has_frame(116):
        return False
    if not b.surface:
        if not force:
            return False
        self.ground(b)
    b.goal = None
    b.vx = 0
    acts = d["acts"][:]
    rest = acts[1:]
    random.shuffle(rest)
    chosen = [acts[0]] + rest[:2]
    t_in = 95
    seq = [(116, t_in)]
    t = t_in
    for fr, dur, lines in chosen:
        part = [(fr[0], 50), (fr[1], 110), (fr[0], 40)] if len(fr) > 1 else [(fr[0], dur)]
        QTimer.singleShot(int((t + 12) * TICK), lambda L=lines: b in self.buddies and b.state == "seq"
                          and b.say(random.choice(L), 140))
        seq += part
        t += sum(x for _, x in part)
    t_out = t
    seq.append((123, 85))
    total = t + 85
    b.say(random.choice(d["start"]), 90)
    QTimer.singleShot(int((t_out + 10) * TICK), lambda: b in self.buddies and b.say(random.choice(d["end"]), 120))
    b.play_seq(seq)
    _dm_fx(b, t_in * TICK / 1000.0, t_out * TICK / 1000.0, total * TICK / 1000.0)
    b._dm_last = time.time()
    return True






# ── 노스텔지어 스킨: 소름 끼치게 깜빡이다 검은 모습으로 물들었다가 아무 일 없었다는 듯 돌아옴 ──
# 그림: 116 멈칫(텅 빈 눈) / 117 반쯤 검게 물든 글리치 / 118 검은 모습 / 119~121 검은 모습 동작 / 122 돌아오는 중 / 123 다시 분홍(생긋)
DMODE["dorothy@nosskin"] = {
    "menu": "…검게 물들기",
    "fx": "dark",
    "start": ["……", "…귀하, 뒤를 돌아보지 마세요."],
    "acts": [([118], 150, ["후후… 이쪽이 진짜 저일지도 모르죠.", "…낙원은, 이미 무너졌어요."]),
             ([119], 130, ["어디로 도망치시려고요?", "…날개가 검게 물들었네요."]),
             ([120], 130, ["쉿. 아무에게도 말하지 마세요.", "…비밀이에요, 귀하."]),
             ([121], 130, ["……왜 그렇게 보세요?", "후후후…"])],
    "end": ["…방금 뭐 보셨어요? 후후.", "어머, 차가 다 식었네요."],
}


def _dm_dark_play(self, b, force=False):
    d = DMODE.get(_dm_key(self, b))
    if not b.surface:
        if not force:
            return False
        self.ground(b)
    b.goal = None
    b.vx = 0
    seq = [(116, 70)]
    fl = [(117, 5), (116, 4), (118, 3), (116, 6), (117, 4), (118, 5), (116, 3), (117, 7), (118, 4), (117, 5)]
    w1 = (70, 70 + sum(x for _, x in fl))
    seq += fl
    t = w1[1]
    acts = d["acts"][:]
    rest = acts[1:]
    random.shuffle(rest)
    for fr, dur, lines in [acts[0]] + rest[:random.randint(1, 2)]:
        QTimer.singleShot(int((t + 12) * TICK), lambda L=lines: b in self.buddies and b.state == "seq"
                          and b.say(random.choice(L), 130))
        seq.append((fr[0], dur))
        t += dur
    back = [(122, 6), (118, 4), (122, 5), (117, 3), (118, 3), (122, 9)]
    w2 = (t, t + sum(x for _, x in back))
    seq += back
    t = w2[1]
    seq.append((123, 110))
    QTimer.singleShot(int((t + 10) * TICK), lambda: b in self.buddies and b.say(random.choice(d["end"]), 130))
    total = t + 110
    b.say(random.choice(d["start"]), 60)
    b.play_seq(seq)
    _dm_fx(b, 0.01, total * TICK / 1000.0, total * TICK / 1000.0)
    b._dm["kind"] = "dark"
    b._dm["win"] = [(w1[0] * TICK / 1000.0, w1[1] * TICK / 1000.0), (w2[0] * TICK / 1000.0, w2[1] * TICK / 1000.0)]
    b._dm["black"] = (w1[1] * TICK / 1000.0, w2[0] * TICK / 1000.0)
    b._dm_last = time.time()
    return True


def _dm_paint_dark(b):
    from PyQt5.QtGui import QColor, QRadialGradient, QBrush
    from PyQt5.QtCore import QPointF, QRectF
    d = b._dm
    now = time.time() - d["t0"]
    S = float(b.S)
    try:
        f = b.frame()
        top, bot = b.ftop(f), b.fbottom(f)
    except Exception:
        top, bot = 0.3, 0.97
    c = QPointF(S / 2, S * (top + bot) / 2)
    p = QPainter(b)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)

    def aura(col, a, r):
        g = QRadialGradient(c, r)
        g.setColorAt(0.0, QColor(col[0], col[1], col[2], int(max(0, min(255, a)))))
        g.setColorAt(0.6, QColor(col[0], col[1], col[2], int(max(0, min(255, a * 0.5)))))
        g.setColorAt(1.0, QColor(col[0], col[1], col[2], 0))
        p.setBrush(QBrush(g))
        p.drawEllipse(c, r, r)

    flick = any(a <= now < z for a, z in d.get("win", []))
    if flick:
        if random.random() < 0.6:  # 번쩍: 검정 / 핏빛
            aura(random.choice(((0, 0, 0), (120, 0, 10), (20, 0, 0))), random.randint(120, 230), S * 0.55)
        for _ in range(random.randint(2, 5)):  # 지직거리는 가로줄
            y = S * random.uniform(top, bot)
            h = S * random.uniform(0.012, 0.045)
            x0 = S * random.uniform(0.08, 0.35)
            w = S * random.uniform(0.3, 0.7)
            p.setBrush(QColor(*random.choice(((10, 0, 0), (150, 0, 20), (255, 255, 255))), random.randint(110, 200)))
            p.drawRect(QRectF(x0, y, w, h))
    else:
        a0, z0 = d.get("black", (0, 0))
        if a0 <= now < z0:  # 검은 모습일 땐 핏빛 기운이 천천히 일렁임
            aura((90, 0, 15), 45 + 30 * math.sin(now * 3.0), S * 0.5)
            if random.random() < 0.025:
                aura((0, 0, 0), 170, S * 0.55)
    p.end()




# ── 블랑·누아르 코스튬: 백묘 / 77번 타자 / 포츈 익스프레스 · 흑묘 / 베이스볼 치어리더 ──
OUTFIT_NAME.update({"baekmyo": "백묘", "batter77": "77번 타자", "fortune": "포츈 익스프레스",
                    "heukmyo": "흑묘", "cheerleader": "베이스볼 치어리더"})
OUTFIT_LINES.update({
    "blanc@baekmyo": ["행운의 흰 토끼 블랑이에요! 저와 함께 행운의 온천에 들어가실래요?", "새로운 옷… 새로운 머리 스타일… 너무 마음에 들어요!",
                      "점장님! 이 옷 어때요? 저랑 잘 어울리나요?", "점장님, 나중에 제가 마사지해 드릴까요? 엠마한테 배웠거든요!", "저는 누아르 언니랑 온천에 들어갈 거예요~!", "점장님과 영원히 설온장에 있고 싶어요. 물론 누아르 언니도 함께요!", "으으… 바니걸 복장이 아니라서 움직이기 조금 불편하네요!"],
    "blanc@batter77": ["승리의 행운을 가져오는 하얀 토끼가 왔어요!", "야구 시합 응원을 위한 특별한 유니폼이에요. 잘 어울리나요?",
                       "저 어때요? 평소랑은 다른 느낌이라서 색다르죠?", "언니요? 언니도 물론 저랑 같이 왔죠. 쌍둥이 토끼에서 한 명이 빠지는 건 있을 수 없으니까요.", "점장님, 다음에 우리 야구장 데이트해요. 물론 언니도 같이요.", "키스 타임이라고 아세요? 전광판에 나온 커플이 입을 맞추는 거래요.", "만루 홈런을 날려 버릴게요!"],
    "blanc@fortune": ["행운을 싣고 다니는 열차에 어서 오세요!", "승객분들께 행운을 가득 나눠 드릴게요~", "오늘은 일일 승무원 블랑이에요! 표 검사할게요♪", "다음 역은~ 행운 역이에요!", "창밖 풍경 보세요, 점장님! 언니도 저기서 손 흔들어요~", "승차권 대신 행운을 받아요♪"],
    "noir@heukmyo": ["이, 이 옷⋯ 온천 여관 옷이래요. 어울려요⋯?", "머리에 장미를 꽂았어요⋯ 으⋯ 부끄러워.", "블랑이 골라 준 옷이에요⋯", "온천⋯ 블랑이랑 같이라면 들어갈 수 있을 것 같아요⋯", "이 장미⋯ 점장님 눈에도 예뻐 보여요⋯?"],
    "noir@cheerleader": ["치, 치어리더예요⋯ 응원⋯ 열심히 할게요⋯!", "블랑이 같이 하자고 해서⋯ 으⋯ 부끄러워.", "점장님 팀⋯ 이겨라⋯ (작게)", "점, 점장님⋯ 화이팅⋯! ⋯으, 소리가 너무 작았죠⋯", "블랑은 타자, 저는 응원이에요⋯ 같이 이겨요⋯"],
})
SHOOT_LINES.update({
    "blanc@batter77": ("플레이 볼!", "타석 정리할게요!", "만루 홈런을 날려 버릴게요!", "타율이 더 높아지겠는데요?"),
    "blanc@fortune": ("출발 진행~!", "잠시 정차할게요!", "행운 특급, 전속력이에요!", "종착역 도착! 행운 듬뿍 받으셨죠?"),
})


# ── 블랑·누아르: 빼빼로데이·날씨 대사 ──
PEPERO_LINES["blanc"] = {"give": ["{n}, 빼빼로 받아요! 행운 듬뿍 묻혀 왔어요~", "오늘은 빼빼로데이! 하나씩 나눠 줄게요♪"],
                         "thanks": ["와, 너무 기뻐요! 그런데 이걸 어떻게 언니랑 반으로 나누죠?", "빼빼로다! 언니 것도 있는 거 맞죠?"],
                         "game": ["빼빼로 게임이요? 쇼처럼 화려하게 해 봐요!", "끝까지 가는 사람이 잭팟이에요~!"],
                         "user": ["{call}, 빼빼로예요! 언니랑 같이 골랐어요♡", "{call} 몫은 제일 긴 거! 행운 지수 최고예요."]}
PEPERO_LINES["noir"] = {"give": ["{n}⋯ 빼빼로⋯ 받아 주세요.", "블랑이랑 같이 만들었어요⋯ 하나씩 드세요."],
                        "thanks": ["와⋯ 감사해요. 어⋯ 블랑이랑 같이 먹어도 되나요?", "저만 받을 순 없어요⋯ 블랑 것도 있나요?"],
                        "game": ["빼, 빼빼로 게임⋯? 으⋯ 부끄러워⋯", "얼굴이⋯ 너무 가까워져요⋯!"],
                        "user": ["{call}⋯ 빼빼로예요. 제 마음도⋯ 조금 들어 있어요.", "{call}께 드리고 싶었어요⋯ 부끄러우니까 빨리 받아 주세요⋯!"]}
WEATHER_LINES.update({
    "blanc": {"rain": ["비 오는 날엔 실내 카지노가 최고죠! 같이 가요!", "우산 쓰고 언니랑 쇼 한 판~!"],
              "snow": ["눈이다~! 눈싸움해요, 점장님! 언니는 제 편!", "하얀 눈이랑 하얀 토끼, 잘 어울리죠?"],
              "hot": ["더워요~ 바니슈트는 통풍이 하나도 안 된다구요!", "햇빛 아래에서 보는 점장님은 더 멋지네요."],
              "cold": ["추워요~ 언니한테 꼭 붙어 있어야겠어요.", "손 시려요! 점장님이 잡아 주세요~"]},
    "noir": {"rain": ["비가 와요⋯ 우산 같이 쓰실래요⋯?", "빗소리 들으면 마음이 차분해져요⋯"],
             "snow": ["눈이에요⋯ 블랑이 엄청 좋아하겠다⋯", "눈사람⋯ 토끼 모양으로 만들어 볼까요⋯?"],
             "hot": ["더워요⋯ 땀나는 것도 부끄러워요⋯", "블랑, 부채 좀⋯"],
             "cold": ["추워요⋯ 블랑이랑 붙어 있으면 괜찮아요.", "따뜻한 코코아⋯ 같이 드실래요⋯?"]},
})


# ── 먼작귀: 빼빼로데이·날씨 대사 ──
PEPERO_LINES.update({
    "chiikawa": {"give": ["{n}…! 빼빼로… (쭈뼛)", "와… 나눠 먹자…!"],
                 "thanks": ["와아…!! (그렁그렁)", "…! 고마워… 흐에…"],
                 "game": ["빼, 빼빼로 게임…?! 야다…! 부끄러…", "흐에… 얼굴 가까워…!"],
                 "user": ["빼빼로… 받아 줘…! (꾸벅)", "와… 같이 먹자…!"]},
    "hachiware": {"give": ["{n}, 빼빼로 줄게~! 그거 좋다!", "빼빼로데이래~ 다 같이 나눠 먹자!"],
                  "thanks": ["와~ 고마워! 소중히 먹을게!", "나 주는 거야? 그거 좋다~!"],
                  "game": ["빼빼로 게임? 어떻게든 되라~!", "끝까지 가면… 에헤헤, 노래로 만들까?"],
                  "user": ["빼빼로야~ 내가 고른 거야!", "같이 먹으면 더 맛있어~"]},
    "usagi": {"give": ["우라!", "야하!"],
              "thanks": ["야하!", "우나~ 야하야하"],
              "game": ["우라!", "하아~?"],
              "user": ["우라!", "야하!"]},
    "momonga": {"give": ["{n}, 빼빼로 줄게! 대신 나 귀엽다고 해!", "이거 받으면 나 귀여워해 줘야 해!"],
                "thanks": ["당연히 나 주는 거지? 헤헤~", "흥, 이 정도로는… 고마워!"],
                "game": ["빼빼로 게임? 귀여운 내가 이길 거야!", "가까이 와도 돼~ 나 귀엽지?"],
                "user": ["빼빼로 줄게! 나 귀엽다고 열 번 말해!", "특별히 나한테 받는 거야~"]},
    "kurimanju": {"give": ["{n}, 빼빼로라네. 안주로 딱이지.", "하나씩 들게나."],
                  "thanks": ["…고맙구먼.", "하아~앗… 달구먼."],
                  "game": ["…어른은 그런 거 안 하네.", "허허, 젊은 것들이란."],
                  "user": ["빼빼로라네. 받게.", "…자네 몫이네."]},
    "rakko": {"give": ["{n}, 빼빼로. …먹어.", "…훈련 후 간식."],
              "thanks": ["…고마워.", "…잘 먹을게."],
              "game": ["…집중력 훈련인가.", "…지지 않아."],
              "user": ["…받아.", "…같이 먹자."]},
})
WEATHER_LINES.update({
    "chiikawa": {"rain": ["비… (우산 꼬옥)", "와… 웅덩이…!"],
                 "snow": ["눈…! 와아아…!", "차가워… 헤헤…"],
                 "hot": ["더워… 녹아…", "아이스… 먹고 싶어…"],
                 "cold": ["추워… (덜덜)", "목도리… 따뜻해…"]},
    "hachiware": {"rain": ["비 오네~ 우산 같이 쓰자!", "빗소리 노래 같아~ 라라라~"],
                  "snow": ["눈이다~! 눈싸움하자!", "눈사람 만들자~ 그거 좋다!"],
                  "hot": ["덥다~ 부채질해 줄까?", "아이스크림 먹으러 가자~"],
                  "cold": ["추워~ 꼭 붙어 있자!", "따뜻한 라멘 먹자~"]},
    "usagi": {"rain": ["야하!", "울라~"],
              "snow": ["우라라라!", "뿌르르르르르 이야하!!!!!"],
              "hot": ["후응~", "하아~?"],
              "cold": ["후응~", "츠츠, 우라우라"]},
    "momonga": {"rain": ["비 맞으면 귀여운 털 젖는단 말이야!", "우산 씌워 줘!"],
                "snow": ["눈 오는 날의 나, 더 귀엽지?", "눈사람보다 내가 귀여워!"],
                "hot": ["더워! 부채질해 줘!", "시원한 거 나 줘!"],
                "cold": ["추워! 안아 줘!", "따뜻하게 해 줘~"]},
    "kurimanju": {"rain": ["비 오는 날엔 실내에서 한잔이지.", "…빗소리 좋구먼."],
                  "snow": ["눈 오는 날엔 따끈한 게 최고지.", "…하아. 하얗구먼."],
                  "hot": ["더운 날엔 시원하게 한잔… 하아~앗.", "덥구먼…"],
                  "cold": ["춥구먼. 따끈한 국물 들게.", "…몸 녹이고 가게."]},
    "rakko": {"rain": ["…비 오는 날도 훈련.", "…해달은 물 괜찮아."],
              "snow": ["…눈 속 토벌은 조심해.", "…하얗네."],
              "hot": ["…더워도 훈련은 해.", "…물 마셔."],
              "cold": ["…추우면 몸부터 풀어.", "…감기 조심."]},
})


# ── 먼작귀 시사·카니: 빼빼로데이·날씨 대사 ──
PEPERO_LINES.update({
    "shisa": {"give": ["{n}, 빼빼로 드세요! 직접 만들었어요!", "빼빼로데이래요! 하나씩 나눠 드릴게요!"],
              "thanks": ["감사합니다! 소중히 먹을게요!", "와아! 사부님께도 자랑해야지!"],
              "game": ["빼빼로 게임이요? 열심히 하겠습니다!", "포기하지 않아요…!"],
              "user": ["빼빼로예요! 정성 가득 담았어요!", "드세요! 사타안다기 맛은 아니에요!"]},
    "kani": {"give": ["{n}… 빼빼로. 받아.", "…나눠 먹자."],
             "thanks": ["(빗금) …고마워.", "…모몽가한테 안 뺏기게 먹어야지."],
             "game": ["…! (땀 뻘뻘)", "그, 그건 좀…"],
             "user": ["…빼빼로. 받아 줘.", "(빗금) …줄게."]},
})
WEATHER_LINES.update({
    "shisa": {"rain": ["비 오는 날엔 따끈한 라멘이죠!", "우산 챙기세요!"],
              "snow": ["눈이에요! 오키나와엔 잘 안 와요!", "눈 오는 날 라멘 최고!"],
              "hot": ["덥네요! 오키나와 생각나요!", "시원한 거 드세요!"],
              "cold": ["추워요! 국물 드세요!", "따뜻하게 입으세요!"]},
    "kani": {"rain": ["…책 젖으면 안 돼.", "비…"],
             "snow": ["…눈. 예쁘다.", "모몽가가 좋아하겠다."],
             "hot": ["…더워.", "그늘에서 책 읽자."],
             "cold": ["…추워.", "모몽가랑 붙어 있을래."]},
})


# ── 동방홍마향: 빼빼로데이·날씨 대사 ──
PEPERO_LINES.update({
    "reimu": {"give": ["{n}, 빼빼로. …새전 대신이야.", "자, 하나 줄게."], "thanks": ["고마워. 새전함에 넣어도 되는데.", "차랑 같이 먹어야지."],
              "game": ["빼빼로 게임? …귀찮은데.", "흥, 무녀가 질 것 같아?"], "user": ["빼빼로야. 받아.", "신사 특제… 는 아니고 산 거야."]},
    "marisa": {"give": ["{n}! 빼빼로다제!", "빌린 거 아니야, 진짜 주는 거라구!"], "thanks": ["오, 고마워! 별 모양이었으면 더 좋았을 텐데!", "헤헤, 잘 먹을게!"],
               "game": ["빼빼로 게임? 속도전이라면 자신 있다제!", "지는 쪽이 책 돌려주기다!"], "user": ["빼빼로 받아라구!", "마리사 님 선물이다제~"]},
    "rumia": {"give": ["{n}~ 빼빼로~", "같이 먹자~"], "thanks": ["고마워~ 그런 거구나~", "맛있어~"],
              "game": ["빼빼로 게임~? 그런 거구나~", "에헤헤~"], "user": ["빼빼로야~", "줄게~"]},
    "daiyousei": {"give": ["{n}, 빼빼로 드세요!", "치르노 몫도 따로 있어요!"], "thanks": ["고마워요! 소중히 먹을게요.", "헤헤, 기뻐요!"],
                  "game": ["빼, 빼빼로 게임이요…?", "부끄러워요…"], "user": ["빼빼로예요! 받아 주세요.", "제 마음이에요!"]},
    "cirno": {"give": ["{n}! 얼린 빼빼로 줄게!", "최강의 빼빼로야!"], "thanks": ["헤헤, 아타이한테 주다니 안목 있네!", "고마워! 얼려 먹을래!"],
              "game": ["빼빼로 게임? 아타이가 이길 거야!", "최강은 안 져!"], "user": ["빼빼로 받아! 꽁꽁 얼렸어!", "아타이 선물이야!"]},
    "meiling": {"give": ["{n}, 빼빼로 드세요!", "근무 중 간식이에요! 헤헤."], "thanks": ["감사합니다! 졸릴 때 먹을게요!", "와아, 고마워요!"],
                "game": ["빼빼로 게임! 무술가의 집중력으로!", "질 수 없어요!"], "user": ["빼빼로예요! 포권!", "받아 주세요!"]},
    "koakuma": {"give": ["{n}, 빼빼로 드세요~", "책 읽으면서 드세요!"], "thanks": ["고마워요~ 책갈피로 쓰면 안 되겠죠?", "헤헤, 잘 먹을게요!"],
                "game": ["빼빼로 게임이요? 헤헤~", "파츄리 님 몰래 해요~"], "user": ["빼빼로예요~", "선물이에요~"]},
    "patchouli": {"give": ["…{n}, 빼빼로.", "…받아."], "thanks": ["…고마워.", "…책 읽으면서 먹을게."],
                  "game": ["…그런 게임, 비효율적이야.", "…무큐."], "user": ["…빼빼로. 줄게.", "…소악마가 사 왔어."]},
    "sakuya": {"give": ["{n}, 빼빼로 준비했어요.", "직접 만든 거예요."], "thanks": ["감사합니다. 아가씨와 나눠 먹을게요.", "…기쁘네요."],
               "game": ["빼빼로 게임… 시간을 멈추면 반칙이죠?", "…해 볼까요."], "user": ["빼빼로입니다. 드세요.", "정성껏 만들었어요."]},
    "remilia": {"give": ["{n}, 빼빼로를 하사하지.", "받아. 귀족의 선물이야."], "thanks": ["흥, 당연히 날 줘야지. …고마워.", "사쿠야~ 홍차 가져와!"],
                "game": ["빼빼로 게임? 운명은 이미 정해졌어.", "우~☆ …아, 아무것도 아니야!"], "user": ["빼빼로야. 특별히 주는 거야.", "운명의 빼빼로다."]},
    "flandre": {"give": ["{n}! 빼빼로! 안 부쉈어!", "같이 먹자~!"], "thanks": ["와아~ 고마워! 언니한테 자랑할래!", "헤헤, 맛있다~"],
                "game": ["빼빼로 게임! 재밌겠다~!", "살살 할게~"], "user": ["빼빼로 줄게! 하나도 안 부러졌어!", "선물이야~!"]},
})
WEATHER_LINES.update({
    "reimu": {"rain": ["비 오면 참배객도 없겠네…", "우산 쓰고 다녀."], "snow": ["눈이네. 신사 지붕 치워야겠다.", "눈 오는 날엔 귤이지."],
              "hot": ["더워… 그늘에서 차나 마실래.", "여름엔 신사가 시원해."], "cold": ["추워. 코타츠 들어가자.", "따뜻한 차 마셔."]},
    "marisa": {"rain": ["비 오는 날엔 연구다제!", "빗자루 젖겠네…"], "snow": ["눈이다! 썰매 대신 빗자루!", "눈싸움 하자구!"],
               "hot": ["덥다제~ 시원한 버섯 없나?", "그늘로 날아가자!"], "cold": ["추워~ 미니 팔괘로로 데워야지!", "따뜻하게 입어라구!"]},
    "rumia": {"rain": ["비~ 어두워서 좋아~", "축축해~"], "snow": ["하얗다~ 눈부셔~", "눈이야~"],
              "hot": ["더워~ 어둠 속에 있을래~", "해가 싫어~"], "cold": ["추워~", "꼬옥 붙어 있자~"]},
    "daiyousei": {"rain": ["비가 와요. 숲이 좋아하겠어요.", "우산 챙기세요!"], "snow": ["눈이에요! 치르노가 신나겠다~", "하얗고 예뻐요."],
                  "hot": ["더워요… 호숫가로 가요.", "물 많이 드세요!"], "cold": ["추워요… 따뜻하게 하세요.", "감기 조심하세요!"]},
    "cirno": {"rain": ["비? 얼려서 우박으로 만들어 줄까?", "비 따위!"], "snow": ["눈이다!! 아타이 세상이다!", "최강의 계절!"],
              "hot": ["더워… 녹는다… 아니 최강은 안 녹아!", "얼음 줄까? 시원하지?"], "cold": ["추워? 아타이는 하나도 안 추워!", "추운 날이 최고야!"]},
    "meiling": {"rain": ["비 오는 날도 문지기는 서 있어요!", "우산 쓰고 근무 중!"], "snow": ["눈이에요! 문 앞 눈 치워야겠다.", "눈 오는 날 태극권!"],
                "hot": ["햇볕 좋다… 졸려…", "더우면 낮잠… 아니 휴식!"], "cold": ["추워요! 기를 돌려서 데워요!", "따뜻한 차 드세요!"]},
    "koakuma": {"rain": ["비 오면 책 젖어요!", "도서관에서 쉬어 가세요~"], "snow": ["눈이에요~ 창밖이 예뻐요.", "눈 오는 날엔 독서죠!"],
                "hot": ["더워요~ 도서관은 시원해요!", "시원한 거 드세요~"], "cold": ["추워요~ 담요 덮고 책 읽어요.", "따뜻하게요~"]},
    "patchouli": {"rain": ["…비. 습하면 책이 상해.", "…나가지 마."], "snow": ["…눈.", "…창밖만 볼래."],
                  "hot": ["…더워. 도서관에서 안 나갈 거야.", "…콜록."], "cold": ["…추워.", "…불 마법으로 데울게."]},
    "sakuya": {"rain": ["비가 오네요. 빨래는 걷어 뒀어요.", "우산 챙기세요."], "snow": ["눈이에요. 아가씨가 좋아하시겠네요.", "길 미끄러워요."],
               "hot": ["더우시죠. 냉홍차 준비할게요.", "그늘에서 쉬세요."], "cold": ["추우시죠. 따뜻한 홍차 드릴게요.", "담요 가져올게요."]},
    "remilia": {"rain": ["비… 흡혈귀는 흐르는 물이 싫어.", "오늘은 나가지 않을래."], "snow": ["눈이네. 밤에 보면 아름답겠어.", "사쿠야, 창문 열어."],
                "hot": ["해가 너무 뜨거워! 양산!", "사쿠야~ 양산 씌워 줘!"], "cold": ["추워… 쿠션 가져와.", "따뜻한 홍차를 내오도록."]},
    "flandre": {"rain": ["비다~ 밖에 못 나가…", "비 그치면 놀자!"], "snow": ["눈이다~! 눈사람 만들자!", "와아~ 하얗다~!"],
                "hot": ["햇빛 싫어~ 그늘로!", "더워~"], "cold": ["추워~ 꼬옥 안아 줘~", "언니~ 추워~"]},
})

# ── 트릭컬 버터: 빼빼로데이·날씨 대사 ──
PEPERO_LINES.update({
    "butter": {"give": ["{n}! 빼빼로 드릴게요! 땅에 안 묻었어요!", "빼빼로데이래요! 같이 먹어요!"],
               "thanks": ["와아! 고마워요! …초콜릿은 촌장님이 안 된다고 했는데…", "헤헤, 소중히 묻어 둘게요!"],
               "game": ["빼빼로 게임이요? 끝까지 먹으면 이기는 거죠?", "버터 질 수 없어요!"],
               "user": ["교주님 빼빼로예요! 버터가 골랐어요!", "같이 먹으면 더 맛있어요!"]},
})
WEATHER_LINES.update({
    "butter": {"rain": ["비 와요! 첨벙첨벙 놀아요!", "구덩이에 물이 고였어요…"],
               "snow": ["눈이다! 눈밭에서 뒹굴어요!", "와아~ 하얀 거 다 밟을래요!"],
               "hot": ["더워요… 혀가 나와요… 헥헥…", "그늘에서 쉬어요…"],
               "cold": ["추워요! 꼬리로 몸 감쌀래요!", "교주님 꼭 붙어 있어요!"]},
})

# ── 로스트아크 모코코: 빼빼로데이·날씨 대사 ──
PEPERO_LINES.update({
    "mokoko": {"give": ["{n}! 빼빼로 받으라코!", "빼빼로데이다코! 나눠 먹자코!"],
               "thanks": ["고맙다코! 냠냠!", "모코코 주는 거냐코? 헤헤~"],
               "game": ["빼빼로 게임? 모코코 질 수 없다코!", "끝까지 먹을 거다코!"],
               "user": ["모험가님 빼빼로다코!", "같이 먹자코~"]},
})
WEATHER_LINES.update({
    "mokoko": {"rain": ["비다코! 쑥쑥 자란다코!", "촉촉해서 좋다코~"],
               "snow": ["눈이다코! 잎사귀 시리다코…", "눈사람 만들자코!"],
               "hot": ["햇빛 좋다코! 광합성 중…", "너무 덥다코… 물 달라코…"],
               "cold": ["춥다코… 잎사귀 오그라든다코…", "따뜻한 데로 가자코!"]},
})

# ── 망그러진 곰 망곰: 빼빼로데이·날씨 대사 ──
PEPERO_LINES.update({
    "mangom": {"give": ["{n}! 빼빼로 줄게~ 꿀 묻혀 왔어!", "빼빼로데이래! 나눠 먹자~"],
               "thanks": ["나 주는 거야? 헤헤, 고마워!", "우와~ 아껴 먹을게! …하나만 먼저 먹고."],
               "game": ["빼빼로 게임? (비장한 눈썹) 안 질 거야!", "끝까지 간다! 망곰이 진지해!"],
               "user": ["{call}! 망곰이가 빼빼로 줄게~", "조금 망그러졌지만 맛은 똑같아!"]},
})
WEATHER_LINES.update({
    "mangom": {"rain": ["비 온다! 우산 쓰고 첨벙첨벙~", "털 젖으면 축축해… 그래도 웅덩이는 밟을래!"],
               "snow": ["눈이다~! 눈곰 만들자!", "털 복슬복슬해서 하나도 안 추워!"],
               "hot": ["더워… 털 벗고 싶다…", "아이스크림 하나만… 녹기 전에!"],
               "cold": ["곰은 이 정도 추위쯤이야! …근데 겨울잠 오는 중…", "이불 속으로 들어가자~"]},
})

# ── 라푼젤: 빼빼로데이·날씨 대사 (의상별) ──
PEPERO_LINES["rapunzel"] = {"give": ["{n} 자매님, 빼빼로예요. 길고 단단한 게… 아, 과자 얘기예요.", "오늘은 빼빼로를 나누는 날이래요. 축복과 함께 드릴게요."],
                            "thanks": ["어머, 저에게요? 끝까지… 소중히 먹을게요.", "감사해요! 이 은혜는 꼭 갚을게요. 기, 기도로요!"],
                            "game": ["빼빼로 게임이요? 양 끝에서 천천히… 하읏, 상상만 해도…!", "물러서지 않을게요. 끝까지 가 보는 거예요."],
                            "user": ["{call}, 빼빼로 받으세요. 제 마음도 같이 들어 있어요♡", "{call} 몫은 제일 긴 걸로 골랐어요. …특별히요."]}
PEPERO_LINES_OUTFIT.update({
    "rapunzel@puregrace": {"give": ["{n}, 빼빼로 나눠 드릴게요. 사이좋게 드세요.", "나눔은 축복이래요. 받아 주세요!"],
                           "thanks": ["감사합니다! 소중히 먹을게요.", "저에게요? 기도로 보답할게요."],
                           "game": ["빼빼로 게임… 혹시 레드 후드가 알려 준 거죠? 수상해요…", "규칙만 알려 주시면 성실하게 할게요!"],
                           "user": ["지휘관님, 빼빼로 드릴게요. 오늘도 평안하시길.", "지휘관님 것도 챙겨 왔어요. 제일 예쁜 걸로요."]},
    "rapunzel@sanctuary": {"give": ["{n} 자매님, 빼빼로예요. 새 바디로 하는 첫 나눔이에요.", "오늘은 다 같이 하나씩. 일만 이천 개는 좀 무리지만요."],
                           "thanks": ["어머, 고마워요. 진동 없이 얌전히 먹을게요.", "언젠가 보답할 기회, 꼭 주셔야 해요?"],
                           "game": ["빼빼로 게임, 이번엔 끝까지 가 볼까요? 후후.", "레드 슈즈로 순식간에 다가갈게요."],
                           "user": ["형제님, 빼빼로예요. 다음 페이지는… 형제님이 넘겨 주세요.", "형제님 몫이에요. 천천히, 음미하면서 드세요♡"]},
})
WEATHER_LINES.update({
    "rapunzel": {"rain": ["비가 오네요. 젖은 형제님도 나쁘지 않… 아, 우산 쓰세요!", "빗소리에 기도가 잘 돼요."],
                 "snow": ["눈이 와요! 하얗고 깨끗한 게 꼭… 제 마음 같죠?", "눈사람 만들어요. 근육질로요."],
                 "hot": ["더워요… 베일, 조금만 벗어도 될까요? 조금만요.", "땀이 나요. 형제님도 흠뻑…? 아, 아니에요."],
                 "cold": ["추워요… 체온을 나누면 따뜻해진다고 책에서 봤어요.", "손 시려요. 잡아 주시면 금방 녹을 텐데요."]},
    "rapunzel@puregrace": {"rain": ["비 맞으면 감기 걸려요. 우산 같이 써요, 지휘관님.", "빗소리가 꼭 기도 소리 같아요."],
                           "snow": ["눈이에요! 스노우 화이트가 좋아하겠어요.", "하얀 세상이 참 깨끗하네요."],
                           "hot": ["더워요… 수녀복이 두꺼워서요.", "물 많이 드세요, 지휘관님."],
                           "cold": ["추운 날엔 서로 온기를 나눠요.", "손 시리시죠? 장갑 빌려 드릴게요."]},
    "rapunzel@sanctuary": {"rain": ["비가 와도 괜찮아요. 날개로 가려 드릴게요.", "젖은 슈트는… 관리가 좀 힘들어요."],
                           "snow": ["눈 위를 레드 슈즈로 달려 볼까요!", "자매님들도 눈을 참 좋아했었죠."],
                           "hot": ["이 슈트, 통풍이 안 돼요… 땀이 차요.", "날개로 부채질해 드릴게요~"],
                           "cold": ["추우시면 헤일로 옆으로 오세요. 따뜻하답니다.", "슈트가 차가워졌어요… 데워 주실래요?"]},
})

# ── 홀로라이브 3기생: 빼빼로데이·날씨 대사 ──
PEPERO_LINES.update({
    "marine": {"give": ["{n}, 빼빼로 줄게~ 선장이 주는 거니까 감사히 먹어!", "빼빼로데이 선물~ 대신 이자는 붙는다?"],
               "thanks": ["어머, 선장한테? 선원 센스 있네~", "빼빼로 보물 획득~!"],
               "game": ["빼빼로 게임? 선장 이런 거 진짜 잘해~ 각오해!", "이 나이에 빼빼로 게임이라니… 아니 17살이니까 괜찮아! 후훗~"],
               "user": ["{call}, 선장 특제 빼빼로야~ 반하지 마!", "{call} 몫이야~ 그 대신 선장 생일도 챙겨!"]},
    "noel": {"give": ["{n}, 빼빼로 같이 먹자~", "빼빼로데이래~ 단장이 나눠 줄게~"],
             "thanks": ["와~ 고마워~ 단장 한 박스 다 먹어도 돼?", "규동 맛 빼빼로는 없어~? 헤헤"],
             "game": ["빼빼로 게임? 단장 힘으로 이길게~", "헤헤, 부러뜨리면 안 되는 거지~?"],
             "user": ["{call}~ 빼빼로 받아~", "{call} 줄 거 제일 큰 걸로 골랐어~"]},
    "pekora": {"give": ["{n}, 빼빼로다 페코! 고맙게 받아라 페코.", "빼빼로데이라서 특별히 준다 페코~"],
               "thanks": ["페코라 주는 거냐 페코? 고맙다 페코~", "빼빼로다 페코! 마미 몫도 챙겨 가야겠다 페코."],
               "game": ["빼빼로 게임이다 페코! 페코라가 이긴다 페코!", "하↑하↑ 먼저 놓는 쪽이 지는 거다 페코~"],
               "user": ["{call}, 빼빼로다 페코! 감사해라 페코~", "{call} 거다 페코. 다른 데 주지 마라 페코."]},
    "flare": {"give": ["{n}, 빼빼로 받아~ 헤헤", "빼빼로데이니까 나눠 먹자~"],
              "thanks": ["나 주는 거야? 고마워… 울 것 같아…", "헤헤헤, 소중히 먹을게~"],
              "game": ["빼빼로 게임? 쑥스럽지만… 해 볼까?", "헤헤, 리듬 맞춰서 한 입씩! 풀콤 노린다~"],
              "user": ["{call}, 빼빼로야~ 항상 고마워!", "{call} 거 따로 챙겨 뒀어~ 헤헤"]},
})
WEATHER_LINES.update({
    "marine": {"rain": ["비 온다~ 해적은 비 정도 아무렇지도… 아니 춥다!", "선원, 우산 같이 쓰자~ 선장 젖으면 안 돼!"],
               "snow": ["눈이다~! 눈싸움이다, 선원 각오해!", "하얀 바다 같네~ 출항하고 싶다~"],
               "hot": ["더워~ 선장 녹는다~", "이런 날은 바다지! 선장 수영복 보고 싶지~?"],
               "cold": ["추워~ 선장 허리 시려…", "선원, 핫팩 줘~ 쇼와 때는 이런 추위쯤… 아니 선장 17살!"]},
    "noel": {"rain": ["비 온다~ 갑옷 녹슬면 안 되는데~", "우산 같이 쓸래~?"],
             "snow": ["눈이다~! 눈사람 크게 만들자~", "눈싸움 단장 힘 세다~?"],
             "hot": ["더워~ 갑옷 안이 찜통이야~", "시원한 맥주랑 규동 먹고 싶다~"],
             "cold": ["추워~ 단장 근육으로 데워 줄까~?", "따뜻한 전골 먹고 싶다~"]},
    "pekora": {"rain": ["비다 페코… 귀가 젖는다 페코!", "우산 씌워라 페코~"],
               "snow": ["눈이다 페코! 눈덩이 공격이다 페코~ 하↑하↑", "토끼는 눈 좋아한다 페코~"],
               "hot": ["더워서 녹는다 페코…", "아이스크림 사 와라 페코~"],
               "cold": ["추워 페코… 털 많아도 춥다 페코.", "따뜻한 당근 수프 먹고 싶다 페코."]},
    "flare": {"rain": ["비 온다~ 우산 챙겼어?", "빗소리도 리듬 같아~"],
              "snow": ["눈이다~ 홋카이도 생각나네!", "눈사람 만들자, 엘프렌드!"],
              "hot": ["더워~ 불꽃 엘프도 더운 건 싫어~", "시원한 거 마시자~"],
              "cold": ["추워~ 손 줘 봐, 따뜻하게 해 줄게.", "감기 조심해~ 꼭 따뜻하게 입어!"]},
})

# ── 홀로라이브 0기생: 빼빼로데이·날씨 대사 ──
PEPERO_LINES.update({
    "sora": {"give": ["{n}, 빼빼로 같이 먹자~", "빼빼로데이래~ 소라가 나눠 줄게!"],
             "thanks": ["소라 주는 거야? 고마워~!", "헤헤, 소중히 먹을게~"],
             "game": ["빼빼로 게임? 소라 이런 거 조금 부끄러운데…", "끝까지 가면… 적이네? 후후, 농담~"],
             "user": ["{call}~ 빼빼로 받아~ 항상 고마워!", "{call} 몫은 제일 예쁜 걸로 골랐어~"]},
    "roboco": {"give": ["{n}, 빼빼로 줄게~ 하로~보~!", "빼빼로데이! 고성능 로보코가 배달 왔어~"],
               "thanks": ["로보코 주는 거야? 고마워~ 연료 충전!", "와~ 빼빼로다! 토마토 맛만 아니면 다 좋아~"],
               "game": ["빼빼로 게임? 로보코 고성능이라 안 부러뜨려~ 아마도!", "삐빅… 거리 측정 중… 크허허!"],
               "user": ["{call}, 빼빼로야~ 로보코 손으로 직접 골랐어!", "{call} 거야~ 로보사 최고~"]},
    "miko": {"give": ["{n}, 빼빼로다니에! 엘리트가 주는 거다니에~", "빼빼로데이다니에! 나눠 먹자니에~"],
             "thanks": ["미코 주는 거냐니에? 고맙다니에~!", "따봉! 빼빼로 최고다니에!"],
             "game": ["빼빼로 게임? 엘리트는 안 진다니에! …또 졌다니에.", "먼저 놓는 쪽이 지는 거다니에~"],
             "user": ["{call}, 빼빼로다니에! 35P한테 특별히 준다니에~", "{call} 거다니에~ 소중히 먹으라니에!"]},
    "suisei": {"give": ["{n}, 빼빼로. 스이쨩이 주는 거니까 감사히 먹어.", "빼빼로데이래~ 하나 줄게."],
               "thanks": ["스이쨩 주는 거야? …고마워.", "센스 있네. 오늘도 귀여운 스이쨩한테 딱이야."],
               "game": ["빼빼로 게임? 스이쨩 지는 거 싫어하는데, 괜찮겠어?", "테트리스처럼 딱 맞춰 먹어 줄게."],
               "user": ["{call}, 빼빼로. 스이쨩이 직접 고른 거야.", "{call} 거야. 남한테 주면 혼낸다?"]},
    "azki": {"give": ["{n}, 빼빼로 드릴게요~", "빼빼로데이라서 나눠 먹어요~"],
             "thanks": ["저 주시는 거예요? 고마워요~!", "감동해서 바닥 될 것 같아요… 고마워요."],
             "game": ["빼빼로 게임이요? 조금 쑥스럽네요~", "가운데 지점을 정확히 게스할게요!"],
             "user": ["{call}, 빼빼로예요~ 항상 고마워요!", "{call} 몫은 따로 챙겨 뒀어요~"]},
})
WEATHER_LINES.update({
    "sora": {"rain": ["비 온다~ 우산 챙겼어?", "빗소리 들으면서 노래하고 싶다~"],
             "snow": ["눈이다~! 소라 겨울 정말 좋아해!", "스키 타러 가고 싶다~"],
             "hot": ["더워~ 여름은 소라를 싫어하는 것 같아…", "녹는다~ 시원한 데 가자~"],
             "cold": ["추운 날 좋아~ 소라 컨디션 최고야!", "따뜻하게 입어~ 감기 조심!"]},
    "roboco": {"rain": ["비다~ 방수 기능 확인 중… 아마 괜찮아!", "우산 같이 쓰자~ 녹슬면 안 돼~"],
               "snow": ["눈이다~! 로보코 센서가 차가워~", "눈싸움하자~ 고성능 투척!"],
               "hot": ["더워~ 냉각 팬 풀가동 중~", "과열 경보~ 아이스크림 줘~"],
               "cold": ["추워~ 배터리가 빨리 닳아~", "로보코 손 차가워… 데워 줄래?"]},
    "miko": {"rain": ["비다니에~ 우산 같이 쓰자니에!", "비 오는 날은 신사도 조용하다니에~"],
             "snow": ["눈이다니에! 눈싸움하자니에!", "신사에 눈 쌓였다니에~ 쓸어야 한다니에…"],
             "hot": ["덥다니에~ 녹는다니에~", "이 더위는 버닝 버닝이다니에!"],
             "cold": ["춥다니에~ 손 시리다니에~", "따뜻한 녹차 마시자니에~"]},
    "suisei": {"rain": ["비 오네. 우산 같이 쓸래?", "비 오는 날은 집에서 테트리스지."],
               "snow": ["눈이다. 눈싸움하면 스이쨩이 이겨.", "하얀 눈도 예쁘지만 스이쨩이 더 귀여워."],
               "hot": ["더워… 매운 거 먹고 땀 빼자.", "시원한 거 마시자. 스이쨩 녹는다."],
               "cold": ["추워. 손 줘 봐.", "따뜻하게 입어. 감기 걸리면 혼낸다."]},
    "azki": {"rain": ["비가 오네요~ 우산 챙기셨어요?", "비 오는 날 지도 보는 것도 좋아요~"],
             "snow": ["눈이에요~! 하얀 길이 생겼어요!", "눈 쌓인 길도 개척해 봐요!"],
             "hot": ["덥네요~ 물 꼭 챙겨 드세요!", "시원한 곳으로 가요~"],
             "cold": ["추워요~ 따뜻하게 입으세요.", "따뜻한 차 한 잔 어때요?"]},
})

# ── 토키노 소라 추가 의상: 현재 공식 의상 (맨 폴더 chars/sora = 파란 아이돌 기본 의상) ──
OUTFIT_NAME.setdefault("current", "현재 공식 의상")
PERSONA["sora@current"] = PERSONA["sora"]
CHAR_BIO["sora@current"] = ("홀로라이브 0기생 토키노 소라의 현재 공식 의상 모습. 소매 끝 프릴이 달린 흰 블라우스에 가는 검은 넥타이와 멜빵, "
                            "금색 별 장식의 남색 비대칭 스커트. 기본 소라와 같은 상냥하고 다정한 정통파 아이돌 말투, 팬은 '소라토모'.")
THINK_LINES["sora@current"] = THINK_LINES["sora"]
ASK_HELLO["sora@current"] = ASK_HELLO["sora"]
OUTFIT_LINES["sora@current"] = ["오늘은 넥타이 맨 소라야~ 어른스러워 보여?", "새 의상도 예쁘지? 소라토모가 좋아해 주면 좋겠다~"]


# ── 터치 OFF(클릭 통과) 모드 · 펫 투명도 · 떠 있는 '터치/투명도' 버튼 (폰의 터치 ON/OFF 버튼과 같은 것) ──
PET_ALPHA = {"a": 1.0}


def _pt_set_click_through(w, on):
    """창이 마우스를 막지 않게(뒤의 창이 클릭됨) — 윈도우는 WS_EX_TRANSPARENT, 그 밖은 Qt 플래그"""
    try:
        if sys.platform.startswith("win"):
            import ctypes
            hwnd = int(w.winId())
            u = ctypes.windll.user32
            st = u.GetWindowLongW(hwnd, -20)                    # GWL_EXSTYLE
            ns = (st | 0x20 | 0x80000) if on else (st & ~0x20)  # WS_EX_TRANSPARENT | WS_EX_LAYERED
            if ns != st:
                u.SetWindowLongW(hwnd, -20, ns)
        else:
            h = w.windowHandle()
            if h is not None and bool(h.flags() & Qt.WindowTransparentForInput) != bool(on):
                h.setFlag(Qt.WindowTransparentForInput, on)
    except Exception:
        pass


class PassBar(QWidget):
    """화면에 떠 있는 작은 버튼: [터치 ON/OFF] [투명도 %] — 끌어서 옮기기, 휠로 투명도, 우클릭 메뉴"""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(176, 32)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("왼쪽: 터치 ON/OFF (OFF면 펫이 클릭을 막지 않아요)\n오른쪽: 누르거나 휠을 굴려 투명도 조절\n끌어서 옮기기 · 우클릭: 숨기기")
        self._press = None
        self._moved = False
        pos = app.cfg.get("pass_btn_pos")
        sc = QApplication.primaryScreen().availableGeometry()
        if pos and any(s.availableGeometry().contains(pos[0] + 10, pos[1] + 10) for s in QApplication.screens()):
            self.move(pos[0], pos[1])
        else:
            self.move(sc.left() + 8, sc.top() + 8)

    def paintEvent(self, e):
        from PyQt5.QtGui import QPainter, QColor, QFont
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        off = bool(self.app.cfg.get("passthru", False))
        w, h = self.width(), self.height()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 225))
        p.drawRoundedRect(0, 0, w - 1, h - 1, h / 2, h / 2)
        lw = 104
        p.setBrush(QColor(150, 150, 160) if off else QColor(226, 104, 160))
        p.drawRoundedRect(3, 3, lw - 3, h - 7, (h - 7) / 2, (h - 7) / 2)
        f = QFont(); f.setPixelSize(12); f.setBold(True); p.setFont(f)
        p.setPen(QColor(255, 255, 255))
        p.drawText(3, 3, lw - 3, h - 7, Qt.AlignCenter, "터치 OFF" if off else "터치 ON")
        p.setPen(QColor(140, 70, 105))
        p.drawText(lw, 0, w - lw - 4, h, Qt.AlignCenter, f"◐ {int(round(PET_ALPHA['a'] * 100))}%")
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press = (e.globalPos(), self.pos())
            self._moved = False

    def mouseMoveEvent(self, e):
        if self._press is None:
            return
        d = e.globalPos() - self._press[0]
        if abs(d.x()) + abs(d.y()) > 5:
            self._moved = True
        if self._moved:
            self.move(self._press[1] + d)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.RightButton:
            self.menu(e.globalPos())
            return
        if self._press is None:
            return
        self._press = None
        if self._moved:
            self.app.cfg["pass_btn_pos"] = [self.x(), self.y()]
            self.app.save_cfg()
            return
        if e.pos().x() < 104:
            self.app.set_passthru(not self.app.cfg.get("passthru", False))
        else:
            steps = [1.0, 0.85, 0.7, 0.55, 0.4, 0.25]
            cur = PET_ALPHA["a"]
            nxt = next((s for s in steps if s < cur - 0.01), steps[0])
            self.app.set_pet_alpha(nxt)

    def wheelEvent(self, e):
        d = 0.05 if e.angleDelta().y() > 0 else -0.05
        self.app.set_pet_alpha(PET_ALPHA["a"] + d)

    def menu(self, gp):
        m = QMenu()
        m.addAction("터치 ON (펫 만지기)" if self.app.cfg.get("passthru") else "터치 OFF (클릭 통과)",
                    lambda: self.app.set_passthru(not self.app.cfg.get("passthru", False)))
        om = m.addMenu("투명도")
        for pc in (100, 85, 70, 55, 40, 25):
            a = om.addAction(f"{pc}%", lambda pc=pc: self.app.set_pet_alpha(pc / 100))
            a.setCheckable(True); a.setChecked(abs(PET_ALPHA["a"] * 100 - pc) < 1)
        m.addSeparator()
        m.addAction("5분 동안 이 버튼 숨기기", lambda: (self.hide(), QTimer.singleShot(5 * 60 * 1000, self.app.passbar_update)))
        m.addAction("이 버튼 끄기 (트레이 아이콘에서 다시 켜기)", lambda: self.app.set_pass_btn(False))
        m.exec_(gp)


def _pt_start(self):
    PET_ALPHA["a"] = max(0.2, min(1.0, float(self.cfg.get("pet_alpha", 1.0))))
    self.passbar = None
    self._pt_timer = QTimer()
    self._pt_timer.timeout.connect(self.passthru_apply)
    self._pt_timer.start(600)
    self.passbar_update()
    self.passthru_apply()


def _pt_apply(self):
    """모든 펫 창에 지금 설정(클릭 통과 · 투명도)을 맞춤 — 새로 나온 아이도 자동으로"""
    on = bool(self.cfg.get("passthru", False))
    a = PET_ALPHA["a"]
    for b in list(getattr(self, "buddies", [])):
        try:
            if not b.isVisible():
                continue
            if getattr(b, "_pt_on", None) != on or getattr(b, "_pt_wid", None) != int(b.winId()):
                _pt_set_click_through(b, on)
                b._pt_on = on; b._pt_wid = int(b.winId())
            elif on and sys.platform.startswith("win"):
                _pt_set_click_through(b, True)            # 창 스타일이 다시 바뀌어도 계속 통과되게
            if abs(b.windowOpacity() - a) > 0.01:
                b.setWindowOpacity(a)
        except Exception:
            pass
    try:   # 말풍선도 펫과 같은 투명도로
        for w in QApplication.topLevelWidgets():
            if isinstance(w, Bubble) and abs(w.windowOpacity() - a) > 0.01:
                w.setWindowOpacity(a)
    except Exception:
        pass


def _pt_set(self, on):
    self.cfg["passthru"] = bool(on)
    self.save_cfg()
    for b in list(getattr(self, "buddies", [])):
        b._pt_on = None
    self.passthru_apply()
    self.passbar_update()
    try:
        if on and getattr(self, "tray", None) is not None:
            self.tray.showMessage(APP_NAME, "터치 OFF — 펫이 클릭을 막지 않아요.\n다시 만지려면 '터치' 버튼이나 트레이 아이콘 메뉴를 누르세요.")
    except Exception:
        pass


def _pt_set_alpha(self, a):
    a = max(0.2, min(1.0, round(float(a), 2)))
    PET_ALPHA["a"] = a
    self.cfg["pet_alpha"] = a
    self.save_cfg()
    self.passthru_apply()
    self.passbar_update()


def _pt_set_btn(self, on):
    self.cfg["pass_btn"] = bool(on)
    self.save_cfg()
    self.passbar_update()


def _pt_bar_update(self):
    want = bool(self.cfg.get("pass_btn", True))
    if not want:
        if getattr(self, "passbar", None) is not None:
            self.passbar.hide()
        return
    if getattr(self, "passbar", None) is None:
        self.passbar = PassBar(self)
    self.passbar.show(); self.passbar.raise_(); self.passbar.update()


def _pt_tray(self, tm):
    """트레이 메뉴에: 터치 OFF · 투명도 · 버튼 보이기"""
    a = tm.addAction("터치 OFF (클릭 통과 — 펫 뒤의 창을 클릭할 수 있어요)")
    a.setCheckable(True)
    a.triggered.connect(lambda on: self.set_passthru(on))
    om = tm.addMenu("펫 투명도")
    acts = []
    for pc in (100, 85, 70, 55, 40, 25):
        x = om.addAction(f"{pc}%", lambda pc=pc: self.set_pet_alpha(pc / 100))
        x.setCheckable(True); acts.append((pc, x))
    bt = tm.addAction("화면에 '터치·투명도' 버튼 보이기")
    bt.setCheckable(True)
    bt.triggered.connect(lambda on: self.set_pass_btn(on))

    def sync():
        a.setChecked(bool(self.cfg.get("passthru", False)))
        bt.setChecked(bool(self.cfg.get("pass_btn", True)))
        for pc, x in acts:
            x.setChecked(abs(PET_ALPHA["a"] * 100 - pc) < 1)
    tm.aboutToShow.connect(sync)
    tm.addSeparator()


def _pt_menu(self, top):
    """펫 우클릭 메뉴 맨 위에: 터치 OFF · 투명도"""
    top.addAction("터치 OFF로 바꾸기 (펫이 클릭을 막지 않게)", lambda: self.set_passthru(True))
    om = top.addMenu(f"펫 투명도 ({int(round(PET_ALPHA['a'] * 100))}%)")
    for pc in (100, 85, 70, 55, 40, 25):
        x = om.addAction(f"{pc}%", lambda pc=pc: self.set_pet_alpha(pc / 100))
        x.setCheckable(True); x.setChecked(abs(PET_ALPHA["a"] * 100 - pc) < 1)
    top.addSeparator()



# ── 홀로라이브 1기생: 빼빼로데이·날씨 대사 ──
PEPERO_LINES.update({
    "fubuki": {"give": ["{n}, 빼빼로 같이 먹어요~", "빼빼로데이래요~ 후부키가 나눠 줄게요!"],
               "thanks": ["후부키 주는 거예요? 고마워요~!", "콘콘~ 소중히 먹을게요!"],
               "game": ["빼빼로 게임이요? …프렌드! 프렌드끼리예요!", "끝까지 가면… 안 돼요! 프렌드존이에요~"],
               "user": ["{call}~ 빼빼로예요! 항상 고마워요!", "{call} 몫은 특별히 큰 걸로 골랐어요~"]},
    "matsuri": {"give": ["{n}, 빼빼로 줄게~ 왓쇼이!", "빼빼로데이 축제다~ 나눠 먹자!"],
                "thanks": ["마츠리 주는 거야? 고마워~!", "헤헤, 청초하게 먹을게~"],
                "game": ["빼빼로 게임? 마츠리는 안 피한다~?", "흐응~ 먼저 놓는 쪽이 지는 거다?"],
                "user": ["{call}, 빼빼로야~ 마츠리가 직접 골랐어!", "{call} 거야~ 다른 사람 주면 안 돼?"]},
    "aki": {"give": ["{n}, 빼빼로 줄게~ 같이 건배할까?", "빼빼로데이래~ 누님이 나눠 줄게~"],
            "thanks": ["아키 주는 거야? 고마워~", "후후, 소중히 먹을게~"],
            "game": ["빼빼로 게임? 누님은 안 질 거야~", "200년 경력을 얕보면 안 돼~?"],
            "user": ["{call}, 빼빼로야~ 항상 고마워~", "{call} 몫은 사과맛으로 골랐어~"]},
    "haato": {"give": ["{n}, 빼빼로 줄게~ 하아쨔마 특제 김치맛!", "빼빼로데이~ 하아쨔마가 나눠 줄게!"],
              "thanks": ["하아쨔마 주는 거야? 고마워~♡", "흥, 딱히 기쁜 거 아니거든! …고마워."],
              "game": ["빼빼로 게임? 하아쨔마는 예측불가야~♡", "끝까지 가면… 꺄~!"],
              "user": ["{call}, 빼빼로야~ 하트 듬뿍 담았어!", "{call} 거야~ 직접 만든 건 아니니까 안심해!"]},
})
WEATHER_LINES.update({
    "fubuki": {"rain": ["비 오네요~ 꼬리 젖으면 큰일이에요!", "우산 같이 써요~"],
               "snow": ["눈이에요~! 하얀 여우는 눈이랑 잘 어울리죠?", "눈싸움해요~ 콘콘!"],
               "hot": ["더워요~ 꼬리가 무거워요…", "녹는다~ 아이스크림 먹어요~"],
               "cold": ["추워요~ 꼬리로 감싸 줄까요?", "따뜻하게 입어요~"]},
    "matsuri": {"rain": ["비다~ 축제 취소야? 안 돼~", "우산 같이 쓰자~"],
                "snow": ["눈이다~! 눈싸움 축제다!", "눈사람 만들자 왓쇼이~"],
                "hot": ["여름이다~ 여름 축제 가자!", "더워~ 라무네 마시자~"],
                "cold": ["추워~ 마츠리 손 잡아 줘~", "따뜻하게 입어~"]},
    "aki": {"rain": ["비 오네~ 트윈테일이 축 처져~", "우산 같이 쓰자~"],
            "snow": ["눈이다~ 이세계 겨울 생각난다~", "하얀 눈 예쁘다~"],
            "hot": ["덥다~ 시원한 거 마시면서 건배하자~", "녹는다~ 그늘로 가자~"],
            "cold": ["추워~ 따뜻한 데서 건배하자~", "감기 조심해~"]},
    "haato": {"rain": ["비다~ 온천 가고 싶어~", "우산 같이 쓰자~ 하트 우산!"],
              "snow": ["눈이다~! 눈 오는 날 온천 최고야!", "눈싸움하자~ 하아쨔마 강해!"],
              "hot": ["더워~ 호주 여름보다 덥다~", "시원한 거 먹자~"],
              "cold": ["추워~ 온천 들어가고 싶어~", "따뜻하게 입어~♡"]},
})

# ── 홀로라이브 2기생: 빼빼로데이·날씨 대사 ──
PEPERO_LINES.update({
    "aqua": {"give": ["{n}, 빼빼로 같이 먹자~", "빼빼로데이래~ 아틔시가 나눠 줄게!"],
             "thanks": ["아틔시 주는 거야? 고마워~!", "헤헤, 아틔시 너무 좋아하잖아~"],
             "game": ["빼빼로 게임? 아, 아틔시 그런 거 못 해~!", "끝까지 가면… 으아앗!"],
             "user": ["{call}~ 빼빼로야! 항상 고마워!", "{call} 몫은 아틔시가 골랐어~"]},
    "shion": {"give": ["{n}, 빼빼로 줄게~ 감사히 먹어~", "빼빼로데이래~ 시온님이 특별히 줄게~"],
              "thanks": ["시온 주는 거야? 흐응~ 고마워.", "…고, 고마워. 별로 기쁜 거 아니거든."],
              "game": ["빼빼로 게임? 시옷코 겁쟁이라 못 하지~?", "먼저 놓는 쪽이 지는 거야~ 키득."],
              "user": ["{call}, 빼빼로야~ 시온이 주는 거니까 소중히 먹어.", "{call} 거야~ 다른 사람 주면 안 돼?"]},
    "ayame": {"give": ["{n}, 빼빼로 줄게요~", "빼빼로데이다요~ 나눠 먹자요!"],
              "thanks": ["요 주는 거냐요? 고맙다요~!", "헤헤, 소중히 먹겠다요~"],
              "game": ["빼빼로 게임? 오니는 안 진다요~", "어느 쪽~ 어느 쪽~ 먹으면 되는 거냐요?"],
              "user": ["{call}, 빼빼로다요~ 항상 고맙다요!", "{call} 몫은 요가 직접 골랐다요~"]},
    "choco": {"give": ["{n}, 빼빼로 줄게~ 선생님이 주는 거야~", "빼빼로데이래~ 초콜릿은 선생님 담당이지~"],
              "thanks": ["선생님 주는 거야? 고마워~", "후후, 맛있게 먹을게~"],
              "game": ["빼빼로 게임? 선생님은 어른이라 안 져~", "후후, 끝까지 와 볼래?"],
              "user": ["{call}, 빼빼로야~ 선생님 특제 수제 초콜릿맛~", "{call} 몫은 따로 챙겨 뒀어~"]},
    "subaru": {"give": ["{n}, 빼빼로 줄게! 같이 먹자!", "빼빼로데이다~! 스바루가 나눠 줄게!"],
               "thanks": ["스바루 주는 거야? 고마워!", "헤헤, 맛있게 먹을게!"],
               "game": ["빼빼로 게임?! 꽥! 그, 그런 건 못 해!", "스바루 그런 거 부끄러워~!"],
               "user": ["{call}, 빼빼로야! 항상 고마워!", "{call} 거야~ 매니저가 챙겨 줬어!"]},
})
WEATHER_LINES.update({
    "aqua": {"rain": ["비다~ 오늘은 집에서 게임하자~", "우산 같이 쓸래?"],
             "snow": ["눈이다~! 고양이처럼 웅크리고 싶어~", "눈싸움… 아틔시 질 것 같아~"],
             "hot": ["더워~ 에어컨 틀고 게임하자~", "녹는다~"],
             "cold": ["추워~ 이불 밖은 위험해~", "따뜻하게 입어~"]},
    "shion": {"rain": ["비 오네~ 마법으로 멈춰 줄까? …못 해.", "우산 같이 써 줄게~"],
              "snow": ["눈이다~ 눈덩이 던질 거야~ 키득.", "하얀 눈도 시온 머리만큼 예쁘네~"],
              "hot": ["더워~ 마녀 모자 벗을래~", "녹는다~ 아이스크림 사 와~"],
              "cold": ["추워~ 손 줘 봐.", "감기 걸리면 놀린다?"]},
    "ayame": {"rain": ["비다요~ 종이 우산 같이 쓰자요.", "비 오는 날은 조용히 있고 싶다요~"],
              "snow": ["눈이다요~! 눈싸움하자요!", "하얀 눈이 예쁘다요~"],
              "hot": ["덥다요~ 오니도 녹는다요~", "시원한 데 가자요~"],
              "cold": ["춥다요~ 따뜻한 감주 마시자요.", "따뜻하게 입어라요~"]},
    "choco": {"rain": ["비 오네~ 감기 조심해야 해~", "우산 같이 쓸까?"],
              "snow": ["눈이다~ 핫초코 마시면서 보자~", "미끄러지면 선생님이 치료해 줄게~"],
              "hot": ["덥다~ 수분 보충 꼭 해~", "열사병 조심해~ 선생님 말 들어~"],
              "cold": ["추워~ 따뜻하게 입어야 해~", "감기 걸리면 보건실로 와~"]},
    "subaru": {"rain": ["비다~! 오늘 실내 연습이다!", "우산 같이 쓰자!"],
               "snow": ["눈이다~! 눈싸움 하자! 스바루 강해!", "눈사람 만들자~!"],
               "hot": ["덥다~! 수분 보충 필수야!", "스포츠 음료 마시자!"],
               "cold": ["추워~! 몸 풀고 달리면 따뜻해져!", "따뜻하게 입어!"]},
})


# ── 홀로라이브 4기생: 빼빼로데이·날씨 대사 ──
PEPERO_LINES.update({
    "kanata": {"give": ["{n}, 빼빼로 같이 먹자~", "빼빼로데이래~ 천사가 나눠 줄게!"],
               "thanks": ["카나타 주는 거야? 고마워~!", "헤헤, 아껴 먹을게~"],
               "game": ["빼빼로 게임? 악력으로 부러뜨릴지도…?", "끝까지 가면… 으앗, 안 돼~!"],
               "user": ["{call}~ 빼빼로야! 항상 고마워!", "{call} 몫은 특별히 챙겼어~"]},
    "watame": {"give": ["{n}, 빼빼로 줄게~", "빼빼로데이래~ 와타메가 나눠 줄게~"],
               "thanks": ["와타메 주는 거야? 고마워~", "헤헤, 맛있게 먹을게~"],
               "game": ["빼빼로 게임? 와타메는 나쁘지 않아~?", "먼저 놓으면 지는 거야~"],
               "user": ["{call}, 빼빼로야~ 항상 고마워~", "{call} 몫은 와타메가 골랐어~"]},
    "towa": {"give": ["{n}, 빼빼로 줄게.", "빼빼로데이래. 같이 먹자."],
             "thanks": ["토와 주는 거야? …고마워.", "초콜릿 맛이다~ 최고야."],
             "game": ["빼빼로 게임? 토와는 안 져.", "끝까지 갈 수 있겠어? 흐응~"],
             "user": ["{call}, 빼빼로야. 항상 고마워.", "{call} 거야. 초콜릿 듬뿍."]},
    "luna": {"give": ["{n}, 빼빼로 줄게다노라~", "빼빼로데이다노라~ 공주님이 나눠 준다노라!"],
             "thanks": ["루나 주는 거냐노라? 고맙다노라~", "헤헤, 맛있게 먹겠다노라~"],
             "game": ["빼빼로 게임? 루나는 어른이라 할 수 있다노라!", "끝까지 가면… 응나아아~!"],
             "user": ["{call}, 빼빼로다노라~ 항상 고맙다노라!", "{call} 몫은 공주님이 골랐다노라~"]},
})
WEATHER_LINES.update({
    "kanata": {"rain": ["비다~ 날개 젖으면 큰일이야!", "우산 같이 쓸래?"],
               "snow": ["눈이다~! 천사처럼 하얗다~", "눈싸움하자~ 악력 조심!"],
               "hot": ["더워~ 천사도 녹아~", "시원한 거 먹자~"],
               "cold": ["추워~ 목도리 꼭 해~", "따뜻하게 입어~"]},
    "watame": {"rain": ["비 오네~ 양털이 축축해져~", "우산 같이 쓰자~"],
               "snow": ["눈이다~! 양털이랑 똑같이 하얗다~", "눈싸움하자~"],
               "hot": ["더워~ 양털 너무 덥다~", "녹는다~ 아이스크림 먹자~"],
               "cold": ["추울 땐 양털이 최고야~", "와타메가 따뜻하게 해 줄게~"]},
    "towa": {"rain": ["비다… 오늘은 집에서 게임하자.", "우산 같이 쓸래?"],
             "snow": ["눈이다~ 눈덩이 던질 거야.", "하얀 눈 예쁘다."],
             "hot": ["더워… 탄산 마시자.", "녹는다~"],
             "cold": ["추워. 손 줘.", "감기 조심해."]},
    "luna": {"rain": ["비다노라~ 우산 쓰라노라~", "공주님이랑 우산 같이 쓰자노라~"],
             "snow": ["눈이다노라~! 눈사람 만들자노라!", "응나~ 눈싸움이다노라~"],
             "hot": ["덥다노라~ 녹는다노라~", "아이스크림 먹자노라~"],
             "cold": ["춥다노라~ 따뜻하게 입으라노라~", "손 시렵다노라~"]},
})


# ── 홀로라이브 5기생: 빼빼로데이·날씨 대사 ──
PEPERO_LINES.update({
    "lamy": {"give": ["{n}, 빼빼로 같이 먹어요~", "빼빼로데이래요~ 라미가 나눠 줄게요."],
             "thanks": ["라미 주는 거예요? 고마워요~", "후후, 아껴 먹을게요~"],
             "game": ["빼빼로 게임이요? 어, 어머…", "끝까지 가면… 라미 얼굴 빨개져요~"],
             "user": ["{call}, 빼빼로예요~ 항상 고마워요.", "{call} 몫은 따로 챙겼어요~"]},
    "nene": {"give": ["{n}, 빼빼로 줄게~!", "빼빼로데이다~! 사장님이 쏜다~!"],
             "thanks": ["네네 주는 거야? 고마워~!", "에헤헤~ 맛있게 먹을게~!"],
             "game": ["빼빼로 게임? 네네는 안 피해~!", "끝까지 가면… 결혼이다~!"],
             "user": ["{call}, 빼빼로야~! 보너스야!", "{call} 몫은 특별히 큰 거!"]},
    "botan": {"give": ["{n}, 빼빼로 줄게.", "빼빼로데이래. 같이 먹자."],
              "thanks": ["보탄 주는 거야? 고마워.", "오, 맛있겠다."],
              "game": ["빼빼로 게임? 보탄은 안 져.", "흐응~ 끝까지 올 수 있겠어?"],
              "user": ["{call}, 빼빼로야. 항상 고마워.", "{call} 거야. 챙겨 뒀어."]},
    "polka": {"give": ["{n}, 빼빼로 줄게~!", "빼빼로데이 서커스~! 나눠 먹자!"],
              "thanks": ["폴카 주는 거야? 고마워~!", "헤헤, 저글링하면서 먹을게~"],
              "game": ["빼빼로 게임? 단장님 묘기를 보여 주지~", "끝까지 가면… 폴~!"],
              "user": ["{call}, 빼빼로야~ 항상 고마워!", "{call} 몫은 단장님이 골랐어~"]},
})
WEATHER_LINES.update({
    "lamy": {"rain": ["비가 오네요~ 우산 같이 써요.", "눈이었으면 좋았을 텐데~"],
             "snow": ["눈이에요~! 라미의 계절이에요!", "하얀 눈, 설산 생각나요~"],
             "hot": ["더워요~ 라미 녹아요~", "빙수 먹으러 가요~"],
             "cold": ["추운 날은 라미한테 맡겨요~", "따뜻하게 입어요~"]},
    "nene": {"rain": ["비다~! 우산 같이 쓰자~!", "비 오는 날도 텐션 MAX!"],
             "snow": ["눈이다~!! 눈싸움하자~!", "눈사람 만들자~!"],
             "hot": ["더워~! 녹는다~!", "아이스크림 먹자~!"],
             "cold": ["추워~! 붙어 있자~!", "따뜻하게 입어~!"]},
    "botan": {"rain": ["비다. 집에서 게임하자.", "우산 같이 쓸래?"],
              "snow": ["눈이다~ 갈기가 하얘지겠네.", "눈싸움? 보탄 잘해."],
              "hot": ["더워… 녹는다…", "그늘에서 쉬자."],
              "cold": ["추워. 갈기 덕분에 조금 낫다.", "따뜻하게 입어."]},
    "polka": {"rain": ["비다~ 서커스 천막 안으로~!", "우산 같이 쓰자~"],
              "snow": ["눈이다~! 눈 위 묘기 쇼~!", "눈싸움하자~!"],
              "hot": ["더워~ 꼬리가 무거워~", "시원한 거 먹자~"],
              "cold": ["추워~ 꼬리로 감싸 줄까?", "따뜻하게 입어~"]},
})


# ── 홀로라이브 6기생 홀로엑스: 빼빼로데이·날씨 대사 ──
PEPERO_LINES.update({
    "laplus": {"give": ["{n}, 빼빼로를 하사하마!", "빼빼로데이다! 총수님이 나눠 준다!"],
               "thanks": ["이 몸에게 바치는 거냐? 고맙다!", "흥, 맛있게 먹어 주지."],
               "game": ["빼빼로 게임? 이 몸은 안 진다!", "끝까지 오면… 으, 으아아!"],
               "user": ["{call}, 빼빼로다! 총수님이 주는 거다!", "{call} 몫은 특별히 챙겼다!"]},
    "lui": {"give": ["{n}, 빼빼로 줄게.", "빼빼로데이래. 같이 먹자."],
            "thanks": ["루이 주는 거야? 고마워.", "후훗, 아껴 먹을게."],
            "game": ["빼빼로 게임? 어른의 여유를 보여 줄게.", "끝까지 올 수 있겠어? 후훗."],
            "user": ["{call}, 빼빼로야. 항상 고마워.", "{call} 몫은 따로 챙겼어."]},
    "koyori": {"give": ["{n}, 빼빼로 줄게~!", "빼빼로데이다~ 코요리가 나눠 줄게!"],
               "thanks": ["코요리 주는 거야? 고마워~!", "에헤헤~ 맛있게 먹을게~"],
               "game": ["빼빼로 게임? 반응 관찰해야지~ 히히.", "끝까지 가면… 실험 성공?"],
               "user": ["{call}, 빼빼로야~ 항상 고마워!", "{call} 몫은 코요리가 골랐어~"]},
    "chloe": {"give": ["{n}, 빼빼로 줄게~", "빼빼로데이래~ 같이 먹자~"],
              "thanks": ["사카마타 주는 거야? 고마워~", "바쿠바쿠~ 맛있다~"],
              "game": ["빼빼로 게임? 범고래는 한입에 먹어~", "끝까지 가면… 바쿠!"],
              "user": ["{call}, 빼빼로야~ 항상 고마워~", "{call} 몫은 사카마타가 챙겼어~"]},
    "iroha": {"give": ["{n}, 빼빼로 드리겠소~", "빼빼로데이이오! 나눠 먹으시오~"],
              "thanks": ["이로하에게 주는 것이오? 고맙소!", "헤헤, 아껴 먹겠소이다~"],
              "game": ["빼빼로 게임이오? 무사는 물러서지 않소!", "끝까지 가면… 부, 부끄럽소…!"],
              "user": ["{call}, 빼빼로이오~ 항상 고맙소!", "{call} 몫은 이로하가 골랐소~"]},
})
WEATHER_LINES.update({
    "laplus": {"rain": ["비다! 우산 써라, 명령이다!", "이 몸 우산 같이 쓸래?"],
               "snow": ["눈이다! 눈싸움 하자! 이 몸이 이긴다!", "하얀 눈… 어둠과 대비되는군."],
               "hot": ["덥다… 이 코트 너무 덥다…", "녹는다… 아이스크림 바쳐라."],
               "cold": ["춥다! 소매 길어서 다행이다.", "따뜻하게 입어라."]},
    "lui": {"rain": ["비 오네. 우산 같이 쓸래?", "날개가 젖으면 곤란한데."],
            "snow": ["눈이다. 예쁘네.", "눈 오는 날엔 따뜻한 와인이지."],
            "hot": ["더워… 망토 벗고 싶다.", "시원한 거 마시자."],
            "cold": ["추워. 망토 안으로 들어올래?", "따뜻하게 입어."]},
    "koyori": {"rain": ["비다~ 실험 가운 젖는다~", "우산 같이 쓰자~"],
               "snow": ["눈이다~! 눈 결정 관찰하자~!", "눈사람 만들자~!"],
               "hot": ["더워~ 꼬리가 무거워~", "아이스크림 먹자~"],
               "cold": ["추워~ 꼬리로 감싸 줄게~", "따뜻하게 입어~"]},
    "chloe": {"rain": ["비다~ 범고래는 물 좋아~", "그래도 우산은 쓰자~"],
              "snow": ["눈이다~! 바다에도 눈이 올까?", "눈싸움하자~"],
              "hot": ["더워~ 바다 가고 싶다~", "녹는다~"],
              "cold": ["추워~ 이불 속에서 안 나갈래~", "따뜻하게 입어~"]},
    "iroha": {"rain": ["비이오~ 우산 같이 쓰시오~", "비 오는 날은 수행 쉬는 날이오."],
              "snow": ["눈이오~! 눈싸움 하시오!", "하얀 눈, 아름답소이다."],
              "hot": ["덥소이다… 녹겠소…", "시원한 우동 먹으러 가오~"],
              "cold": ["춥소! 따뜻하게 입으시오.", "손 시리오~ 하오리로 감싸겠소."]},
})


# ── 홀로라이브 DEV_IS 리글로스: 빼빼로데이·날씨 대사 ──
PEPERO_LINES.update({
    "ao": {"give": ["{n}, 빼빼로 줄게.", "빼빼로데이래. 같이 먹자."],
           "thanks": ["아오 주는 거야? 고마워.", "후훗, 아껴 먹을게."],
           "game": ["빼빼로 게임? 아오는 안 피해.", "끝까지 올 수 있겠어?"],
           "user": ["{call}, 빼빼로야. 항상 고마워.", "{call} 몫은 따로 챙겼어."]},
    "kanade": {"give": ["{n}, 빼빼로 줄게~", "빼빼로데이래~ 같이 먹자~"],
               "thanks": ["카나데 주는 거야~? 고마워~", "에헤헤~ 맛있다~"],
               "game": ["빼빼로 게임~? 천천히 먹을게~", "끝까지 가면… 에헤헤~"],
               "user": ["{call}, 빼빼로야~ 항상 고마워~", "{call} 몫은 카나데가 골랐어~"]},
    "ririka": {"give": ["{n}, 빼빼로 줄게! 사장님이 쏜다!", "빼빼로데이! 리리카가 나눠 줄게!"],
               "thanks": ["리리카 주는 거야? 고마워!", "센스 있네! 승진이야!"],
               "game": ["빼빼로 게임? 천재는 안 져!", "끝까지 와 봐~!"],
               "user": ["{call}, 빼빼로야! 보너스야!", "{call} 몫은 특별히 큰 거!"]},
    "raden": {"give": ["{n}, 빼빼로 드릴게요.", "빼빼로데이래요. 같이 드세요."],
              "thanks": ["라덴한테 주시는 거예요? 고마워요.", "후후, 아껴 먹을게요."],
              "game": ["빼빼로 게임이요? 어머…", "끝까지 가면… 부끄러워요."],
              "user": ["{call}, 빼빼로예요. 항상 고마워요.", "{call} 몫은 따로 챙겼어요."]},
    "hajime": {"give": ["{n}, 빼빼로 줄게~!", "빼빼로데이다~! 번장이 쏜다!"],
               "thanks": ["번장 주는 거야? 고마워~!", "헤헤, 맛있다~!"],
               "game": ["빼빼로 게임? 번장은 안 진다!", "끝까지 오면… 박치기!"],
               "user": ["{call}, 빼빼로야~! 항상 고마워!", "{call} 몫은 번장이 챙겼어!"]},
})
WEATHER_LINES.update({
    "ao": {"rain": ["비 오네. 우산 같이 쓸래?", "비 오는 날은 카페에서 그림 그리기 좋지."],
           "snow": ["눈이다. 예쁘네.", "눈 오는 풍경, 그려 두고 싶다."],
           "hot": ["더워… 시원한 카페 가자.", "아이스 라테 마시자."],
           "cold": ["추워. 재킷 안으로 들어올래?", "따뜻하게 입어."]},
    "kanade": {"rain": ["비 오네~ 빗소리도 음악 같아~", "우산 같이 쓰자~"],
               "snow": ["눈이다~ 예쁘다~", "눈사람 만들자~"],
               "hot": ["더워~ 녹는다~", "바나나우유 마시자~"],
               "cold": ["추워~ 따뜻하게 입어~", "손 시려~"]},
    "ririka": {"rain": ["비다! 기분은 포지티브!", "우산 같이 쓰자!"],
               "snow": ["눈이다! 눈싸움하자!", "눈 와도 리리카는 카와이!"],
               "hot": ["더워! 선글라스 필수!", "시원한 칵테일… 아니 주스 마시자!"],
               "cold": ["추워! 퍼 재킷 최고!", "따뜻하게 입어!"]},
    "raden": {"rain": ["비가 오네요. 미술관 가기 좋은 날이에요.", "우산 같이 쓰실래요?"],
              "snow": ["눈이에요. 정취가 있네요.", "눈 내리는 풍경, 사진 찍고 싶어요."],
              "hot": ["덥네요… 시원한 데서 쉬어요.", "녹을 것 같아요."],
              "cold": ["추워요. 따뜻하게 입으세요.", "따뜻한 술 한 잔… 아, 차 한 잔이요."]},
    "hajime": {"rain": ["비다~! 우산 쓰고 부릉부릉~", "물웅덩이 점프~!"],
               "snow": ["눈이다~! 눈싸움하자!", "번장 눈사람 만들 거야!"],
               "hot": ["더워~! 녹는다~!", "아이스크림 먹자~!"],
               "cold": ["추워~! 붙어 있자!", "따뜻하게 입어~!"]},
})


# ── 홀로라이브 게이머즈: 빼빼로데이·날씨 대사 ──
PEPERO_LINES.update({
    "mio": {"give": ["{n}, 빼빼로 줄게~", "빼빼로데이래~ 같이 먹자."],
            "thanks": ["미오 주는 거야? 고마워~", "후후, 아껴 먹을게."],
            "game": ["빼빼로 게임? 어머…", "끝까지 가면… 미오 부끄러워~"],
            "user": ["{call}, 빼빼로야~ 항상 고마워.", "{call} 몫은 따로 챙겼어~"]},
    "okayu": {"give": ["{n}, 빼빼로 줄게~", "빼빼로데이래~ 나눠 먹자~"],
              "thanks": ["오카유 주는 거야~? 고마워~", "모구모구~ 맛있다~"],
              "game": ["빼빼로 게임~? 히히, 해 볼까~?", "끝까지 오면… 놀려 줄 거야~"],
              "user": ["{call}, 빼빼로야~ 항상 고마워~", "{call} 몫은 오카유가 골랐어~"]},
    "korone": {"give": ["{n}, 빼빼로 줄게~!", "빼빼로데이다~! 같이 먹자!"],
               "thanks": ["코로네 주는 거야? 고마워~!", "에헤헤~ 맛있다~!"],
               "game": ["빼빼로 게임? 코로네는 한입에 먹는다~!", "끝까지 가면… 손가락도 줘!"],
               "user": ["{call}, 빼빼로야~! 항상 고마워!", "{call} 몫은 코로네가 챙겼어!"]},
})
WEATHER_LINES.update({
    "mio": {"rain": ["비 오네~ 우산 같이 쓰자.", "꼬리 젖으면 큰일이야~"],
            "snow": ["눈이다~ 예쁘다.", "눈 오는 날엔 따뜻한 국물이지."],
            "hot": ["더워~ 털이 많아서 힘들어~", "시원한 거 마시자."],
            "cold": ["추워~ 꼬리로 감싸 줄게.", "따뜻하게 입어."]},
    "okayu": {"rain": ["비다~ 오늘은 집에서 뒹굴자~", "고양이는 물 싫어~"],
              "snow": ["눈이다~ …코타츠에서 볼래~", "추워서 못 나가~"],
              "hot": ["더워~ 녹는다~", "그늘에서 낮잠 자자~"],
              "cold": ["추워~ 코타츠 들어가자~", "붙어 있으면 따뜻해~"]},
    "korone": {"rain": ["비다~! 물웅덩이 첨벙첨벙!", "우산 같이 쓰자~!"],
               "snow": ["눈이다~!! 뛰어다니자~!", "강아지는 눈을 좋아해~!"],
               "hot": ["더워~ 혀가 나온다~", "시원한 거 먹자~!"],
               "cold": ["추워~! 붙어 있자~!", "따뜻하게 입어~!"]},
})

# ── 홀로라이브 DEV_IS 플로우글로우: 빼빼로데이·날씨 대사 ──
PEPERO_LINES.update({
    "riona": {"give": ["{n}, 빼빼로. …받아.", "빼빼로데이래. 나눠 먹자."],
              "thanks": ["…나 주는 거야? 고마워.", "아껴 먹을게."],
              "game": ["빼빼로 게임? …포커페이스로 버틴다.", "먼저 웃는 쪽이 지는 거야."],
              "user": ["{call}, 빼빼로. …항상 고마워.", "{call} 몫은 따로 챙겼어."]},
    "niko": {"give": ["{n}, 빼빼로 줄게~!", "빼빼로데이다~! 같이 먹자!"],
             "thanks": ["니코 주는 거야? 고마워~!", "아하하, 맛있다~!"],
             "game": ["빼빼로 게임? 니코가 웃겨서 이길게~!", "끝까지 오면… 어흥!"],
             "user": ["{call}, 빼빼로야~! 항상 고마워!", "{call} 몫은 니코가 챙겼어!"]},
    "su": {"give": ["{n}, 빼빼로 줄게~!", "빼빼로데이 공지! 같이 먹자~!"],
           "thanks": ["스우 주는 거야? 고마워~!", "에헤헤~ 맛있다~!"],
           "game": ["빼빼로 게임? 스우는 키가 작아서 불리해~!", "끝까지 가면… 부끄러워~"],
           "user": ["{call}, 빼빼로야~! 항상 고마워!", "{call} 몫은 스우가 챙겼어!"]},
    "chihaya": {"give": ["{n}, 빼빼로 줄게~", "빼빼로데이래~ 같이 먹자."],
                "thanks": ["치하야 주는 거야? 고마워~", "후후, 맛있다~"],
                "game": ["빼빼로 게임? 브레이크는 안 밟아~", "끝까지 가 볼까?"],
                "user": ["{call}, 빼빼로야~ 항상 고마워.", "{call} 몫은 치하야가 챙겼어~"]},
    "vivi": {"give": ["{n}, 빼빼로 주께~", "빼빼로데이다~ 같이 묵자~"],
             "thanks": ["비비 주는 기가? 고맙데이~", "헤헤~ 맛있다~"],
             "game": ["빼빼로 게임~? 연애 프로 같다~", "끝까지 가믄… 부끄럽다 아이가~"],
             "user": ["{call}, 빼빼로다~ 항상 고맙데이~", "{call} 몫은 비비가 챙겼데이~"]},
})
WEATHER_LINES.update({
    "riona": {"rain": ["비 오네. 우산 같이 쓰자.", "…빗소리도 리듬이야."],
              "snow": ["눈이다. …예쁘네.", "눈 오는 날엔 따뜻한 거 마시자."],
              "hot": ["덥다. 물 챙겨.", "…그늘로 가자."],
              "cold": ["추워. 따뜻하게 입어.", "…붙어 있으면 덜 추워."]},
    "niko": {"rain": ["비다~! 호랑이 털 젖는다~", "우산 같이 쓰자~!"],
             "snow": ["눈이다~!! 눈싸움하자~!", "호랑이는 눈도 좋아~!"],
             "hot": ["더워~ 녹는다~", "시원한 거 먹자~!"],
             "cold": ["추워~! 붙어 있자~!", "따뜻하게 입어~!"]},
    "su": {"rain": ["비다~! 우산 같이 쓰자!", "물웅덩이 조심~!"],
           "snow": ["눈이다~!! 사진 찍어서 올려야지!", "눈사람 만들자~!"],
           "hot": ["더워~ 아이스크림 먹자~", "녹는다~"],
           "cold": ["추워~ 전골 먹자~!", "따뜻하게 입어~!"]},
    "chihaya": {"rain": ["비 오네~ 후구타로 세차 안 해도 되겠다.", "빗길 운전은 조심~"],
                "snow": ["눈이다~ 스노 타이어 끼워야지.", "눈길 드라이브는 위험해~"],
                "hot": ["더워~ 레몬 사와 시원하게!", "에어컨 빵빵하게~"],
                "cold": ["추워~ 히터 켜자.", "따뜻하게 입어, 닉~"]},
    "vivi": {"rain": ["비 온다~ 화장 번진다~", "우산 같이 쓰재이~"],
             "snow": ["눈이다~ 이쁘다~", "추버도 눈은 좋데이~"],
             "hot": ["덥다~ 햇빛 싫다~!", "선크림 꼭 바르래이~"],
             "cold": ["춥다~ 붙어 있재이~", "따뜻하게 입어래이~"]},
})


# ── 니케 마리안: MARIA-n(4주년) 스토리 반영 — 마리안·마리안 : 퀸·라스트 어펙션(웨딩) 대사, 마리안 → 신부 변신(84~91) ──
PERSONA["marian"] = [
    ([52], 16, (150, 260), 4, 0, ["이 붕대… 지휘관이 감아 주셨던 거예요.", "아무 효과 없는 거 알아요. 그래도… 마음이 따뜻해져요."]),
    ([53], 14, (100, 180), 3, 0, ["지치셨죠? 업어 드릴게요.", "괜찮아요. 끝까지 제가 모셔다 드릴게요."]),
    ([54], 12, (70, 120), 3, 0, ["네, 지휘관. 이동할게요.", "마리아-n이 아니라… 마리안이에요. 기억해 주세요."]),
    ([55], 14, (80, 140), 3, 0, ["손… 잡아 주실래요? 저도 떨리거든요.", "지휘관 손 떨리는 거, 저만 알고 있을게요."]),
    ([56], 8, (60, 100), 2, 0, ["심장충격기, 준비됐어요!", "일어나세요, 지휘관…! 제발요!"]),
    ([57], 12, (70, 120), 2, 0, ["…방금 제 눈, 빨갛지 않았나요?", "아무것도 아니에요. …아직은요."]),
    ([58], 14, (80, 140), 3, 0, ["지휘관, 반드시 지켜드릴게요.", "저를 잊으셔도 괜찮아요. 지휘관만 살아 계시면."]),
    ([59], 14, (80, 140), 3, 0, ["다녀오세요, 지휘관. 꼭 돌아오세요.", "제 이름… 한 번만 더 불러 주실래요?"]),
]
PERSONA["marian@queen"] = [
    ([52], 16, (150, 260), 3, 0, ["오래 기다리셨죠. 이번엔 제가 먼저 찾아왔어요.", "박사님이 들어 준 소원… 이번엔 제가 지킬게요."]),
    ([53], 12, (80, 140), 3, 0, ["이쪽으로 오시면 돼요.", "수송기가 없어도 괜찮아요. 길은 제가 열게요."]),
    ([54], 16, (150, 260), 4, 0, ["이 붕대… 아직 소중히 갖고 있어요.", "발목에 감아 주셨던 날, 전부 기억해요."]),
    ([55], 12, (80, 140), 2, 0, ["의지를 벼린 창끝.", "몇 번을 쓰러져도, 이번엔 끝까지 갈게요."]),
    ([56], 14, (100, 180), 3, 0.6, ["제 뒤에 있으세요.", "이번엔 지휘관이 쓰러지는 걸 보지 않을 거예요."]),
    ([57], 14, (80, 140), 2, 0, ["좋아해요, 지휘관. 진심으로.", "박사님의 기억이 아니에요. 이건… 제 마음이에요."]),
    ([58], 12, (70, 120), 3, 0, ["다녀오셨어요, 지휘관.", "돌아올 곳이 있다는 건 좋은 일이에요."]),
    ([59], 14, (80, 140), 3, 0, ["돌아와 주실 거죠?", "잊으면 안 되는 이름이 있어요. …마리안이에요."]),
]
PERSONA["marian@lastaffection"] = [
    ([52], 14, (120, 220), 3, 0, ["세상에서 제일 행복한 신부, 입장합니다.", "오늘은 마리아-n이 아니라… 신부 마리안이에요."]),
    ([53], 12, (100, 180), 3, 0, ["베일… 지휘관이 걷어 주실래요?", "이번엔 처음 만난 척 안 할게요. 약속해요."]),
    ([54], 14, (120, 220), 3, 0.5, ["드레스가 꽃처럼 펴져요!", "꽃밭에서 주셨던 꽃… 이번엔 드레스가 됐네요."]),
    ([55], 10, (80, 140), 2, 0, ["부케, 받는 사람이 다음 신부래요!", "에잇! …라피, 받았어요?"]),
    ([56], 16, (150, 260), 2, 0, ["이 반지… 평생 소중히 할게요.", "울면 안 되는데… 이건 기뻐서 우는 거예요."]),
    ([57], 14, (120, 220), 3, 0, ["좋아해요, 지휘관. 처음부터 끝까지요.", "기억이 지워져도, 이 마음은 몇 번이고 다시 찾아올 거예요."]),
    ([58], 12, (100, 180), 2, 0, ["손, 잡아 주세요. 이번엔 안 떨려요.", "같이 걸어요. 끝까지요."]),
    ([59], 12, (80, 140), 2, 0, ["잘 부탁드려요, 여보… 아, 아니 지휘관!", "제 이름… 다시 불러 주세요. 마리안이라고."]),
]
CRY_LINES["marian"] = ["(훌쩍)… 괜찮아요. 아프지 않아요.", "죽는 건 안 무서워요. 지휘관이 저를 잊는 게… 무서워요.", "이대로는 안 돼…"]
FLEE_LINES["marian"] = ["따라오시면 위험해요!", "지휘관, 이쪽은 안 돼요…!", "잡히면… 안 돼요!"]
ASK_HELLO["marian"] = ["네, 지휘관. 무엇이 궁금하세요?", "마리안이 도와드릴게요."]
ALT_TF["marian@lastaffection"] = ("지휘관… 잠깐만 눈 감아 주실래요?", "세상에서 제일 행복한 신부, 마리안이에요.", "…꿈같은 시간이었어요. 고마워요.")
OUTFIT_LINES["marian@lastaffection"] = ["세상에서 제일 행복한 신부, 입장합니다.", "지휘관… 이 드레스, 어때요?", "박사님… 아니, 장모님도 보고 계실까요?"]
OUTFIT_LINES["marian@queen"] = ["오래 기다리셨죠.", "이번에야말로 꼭, 모두를 지킬게요.", "제 이름, 잊지 않으셨죠?"]
CHAR_BIO["marian"] = ("마리안(실버건 → 카운터스). 갈색 긴 머리에 파란 리본·남색 개리슨 모자, 기관단총 '퍼스트 어펙션'. 부드러운 존댓말(~요), 누구에게나 다정하고 "
                      "지휘관에게 헌신적. 사실은 닥터 마리아가 자기 두뇌로 찍어 낸 '마리아-n' 중 하나로, 수없이 죽고 되살아나며 싸워 왔음. 처음으로 자신을 "
                      "'마리안'이라 불러 준 지휘관(7호)을 사랑하고, 꽃밭·꽃·발목에 감아 준 붕대를 소중히 기억함. 자기가 잊혀져도 지휘관만 살면 된다고 생각함. "
                      "침식이 진행 중이라 가끔 눈이 붉어지는 걸 숨김. 이름을 불러 주는 걸 가장 기뻐함.")
CHAR_BIO["marian@queen"] = ("마리안 : 퀸. 다크매터를 다루게 된 '진정한 여왕' 마리안. 차분하고 다정한 존댓말(~요). 마리아-n이었던 기억(수많은 죽음, 닥터 마리아가 "
                            "마지막에 들어준 '지휘관만은 살려 달라'는 소원)을 모두 안고, 이번에야말로 지휘관과 모두를 지키겠다는 단단한 의지. 그 사랑은 박사의 기억이 "
                            "아니라 자기 마음이라고 담담하게 말함. 모더니아처럼 혀 짧은 말투는 아님.")
CHAR_BIO["marian@lastaffection"] = ("웨딩 코스튬 '라스트 어펙션'의 마리안. 긴 갈색 머리에 하얀 웨딩드레스와 베일, 분홍 부케. 마리아-n으로 수없이 죽고, 기억을 잃은 "
                                    "지휘관 앞에서 처음 만난 척해야 했던 아픔을 지나 마침내 지휘관의 신부가 된 마리안. 부드럽고 다정한 존댓말(~요), 수줍지만 행복을 숨기지 "
                                    "못하고 진심으로 사랑한다고 말함. 닥터 마리아를 '박사님(장모님)'이라 부르기도 함. 이름을 불러 달라고 조름.")


# ── 모습 전용 노래: chars/<캐릭터>@<모습>/song.mp3 가 있으면 그 모습으로 바뀔 때 한 번 틀어 줌 (다른 모습으로 바꾸면 멈춤)
#    예) 마리안 → 신부(라스트 어펙션) 변신 때 'Call my name, Again'
def _outfit_song_file(d):
    for e in (".mp3", ".m4a", ".ogg", ".wav"):
        p = os.path.join(d, "song" + e)
        if os.path.exists(p):
            return p
    return None


def _outfit_song_stop(self):
    cur = getattr(self, "_osong", None)
    self._osong = None
    if cur:
        try:
            cur[1].stop()
        except Exception:
            pass




# ── 변신 노래 켜고 끄기 (우클릭 → '변신 노래 틀기' 체크) — 끄면 모습을 바꿔도 노래 안 나옴, 설정 저장
def _osong_menu(self, top, who):
    try:
        ofs = self.outfits.get(who.char, {}) or {}
        if not any((v or {}).get("dir") and _outfit_song_file(v["dir"]) for v in ofs.values()):
            return
        cfg = getattr(self, "cfg", None)
        if cfg is None:
            return
        a = top.addAction("변신 노래 틀기 ♪")
        a.setCheckable(True)
        a.setChecked(bool(cfg.get("outfit_song", True)))

        def _t(on, self=self):
            self.cfg["outfit_song"] = bool(on)
            self.save_cfg()
            if not on:
                _outfit_song_stop(self)
        a.toggled.connect(_t)
    except Exception:
        pass


# ── 마리안: '잊어도 괜찮아요' 대사 (MARIA-n) ──
def _marian_lines(key, idx, extra, weight=None):
    lst = PERSONA.get(key)
    if not lst or idx >= len(lst):
        return
    t = list(lst[idx])
    t[5] = list(t[5]) + [l for l in extra if l not in t[5]]
    if weight:
        t[3] = weight
    lst[idx] = tuple(t)


_marian_lines("marian", 6, [  # 58: 지켜 드릴게요
    "당신이 날 잊어도 괜찮아요. 당신이 살아 있기만 하면 돼요. 사랑해요, 지휘관.",
    "제 이름은 잊으셔도 돼요. 제가 대신 기억할게요.",
    "몇 번을 다시 만나도, 저는 몇 번이고 지휘관을 좋아하게 될 거예요.",
    "아프지 않게, 무섭지 않게… 지휘관만은요.",
], weight=4)
_marian_lines("marian", 7, [  # 59: 다녀오세요
    "다음에 만나면 처음 보는 사람처럼 대하셔도 괜찮아요. 저는… 또 웃으면서 인사할게요.",
    "제가 없어도 웃어 주세요. 그거면 돼요.",
    "마지막에 제 이름 한 번만 불러 주시면… 그걸로 충분해요.",
])
_marian_lines("marian@queen", 5, [  # 57: 고백
    "이번엔 지휘관이 절 잊어도 괜찮아요. 제가 몇 번이고 다시 찾아갈 테니까요.",
])
_marian_lines("marian@lastaffection", 5, [  # 57: 고백
    "예전엔 잊혀져도 괜찮다고 했었죠. …이제는 오래오래 기억해 주세요.",
])
CRY_LINES["marian"] = list(CRY_LINES.get("marian", [])) + ["울면 안 되는데… 지휘관이 살아 있어서, 그게 너무 좋아서요."]


# ── 계절 이벤트 코스튬: 크리스마스(산타) / 설날·추석(한복) / 할로윈 / 발렌타인·화이트데이 ──
# 그림은 캐릭터의 기본 의상 폴더에만 있음(어떤 옷을 입고 있든 이벤트 땐 그 그림을 씀)
#   130~137 산타 / 138~145 한복 / 146~153 할로윈 / 154~161 발렌타인  (위치 정보: meta_event.json)
EV_OFF = {"xmas": 130, "hanbok": 138, "halloween": 146, "valentine": 154, "spring": 162, "summer": 170, "bday": 178}
EV_MENU = {"xmas": "산타 옷 입기", "hanbok": "한복 입기", "halloween": "할로윈 분장", "valentine": "발렌타인 앞치마",
           "spring": "벚꽃 나들이", "summer": "수영복 입기", "bday": "생일 파티 옷"}
EV_LUNAR = {  # (설날, 추석) 양력
    2026: ("02-17", "09-25"), 2027: ("02-07", "09-15"), 2028: ("01-27", "10-03"), 2029: ("02-13", "09-22"),
    2030: ("02-03", "09-12"), 2031: ("01-23", "10-01"), 2032: ("02-11", "09-19"), 2033: ("01-31", "09-08"),
    2034: ("02-19", "09-27"), 2035: ("02-08", "09-16"), 2036: ("01-28", "10-04"), 2037: ("02-15", "09-24"),
    2038: ("02-04", "09-13"), 2039: ("01-24", "10-02"), 2040: ("02-12", "09-21"),
}
# 칸: 0 등장 포즈 / 1~7 동작. 날마다 고르는 칸 (설날엔 세배·떡국, 추석엔 송편·보름달 …)
EV_POOL = {"xmas": [1, 2, 3, 4, 5, 6, 7], "seol": [1, 2, 3, 4, 5], "newyear": [1, 2, 3, 4, 5], "chuseok": [5, 6, 7, 2],
           "halloween": [1, 2, 3, 4, 5, 6, 7], "valentine": [1, 2, 3, 6, 7], "white": [4, 5, 6, 7]}
EV_SUB_KIND = {"xmas": "xmas", "seol": "hanbok", "newyear": "hanbok", "chuseok": "hanbok",
               "halloween": "halloween", "valentine": "valentine", "white": "valentine"}
EV_SUB_NAME = {"xmas": "크리스마스", "seol": "설날", "newyear": "새해 첫날", "chuseok": "추석",
               "halloween": "할로윈", "valentine": "발렌타인데이", "white": "화이트데이"}
EVENT_GENERIC = {}   # 아래 대사 블록에서 채움 {sub: {"start": [...], "end": [...], 칸번호: [...]}}
EVENT_LINES = {}     # {kind: {캐릭터: {"start": [...], "act": [...]}}}  kind = xmas/hanbok/halloween/valentine
EV_POOL.update({"spring": [1, 2, 3, 4, 5, 6, 7], "summer": [1, 2, 3, 4, 5, 6, 7], "bday": [1, 2, 3, 4, 5, 6, 7]})
EV_SUB_KIND.update({"spring": "spring", "summer": "summer", "bday": "bday"})
EV_SUB_NAME.update({"spring": "벚꽃 시즌", "summer": "여름 휴가", "bday": "생일"})
_EV_APP = [None]   # 생일 확인용 (화면에 있는 친구 중 오늘 생일인 아이가 있으면 다 같이 생일 파티)


def _ev_today(d=None):
    """오늘의 이벤트 → (sub, 당일인지) / 없으면 (None, False)"""
    import datetime as _dt
    d = d or _dt.date.today()
    md = (d.month, d.day)
    if (12, 20) <= md <= (12, 26):
        return "xmas", md in ((12, 24), (12, 25))
    if (10, 25) <= md <= (10, 31):
        return "halloween", md == (10, 31)
    if md in ((2, 13), (2, 14)):
        return "valentine", md == (2, 14)
    if md in ((3, 13), (3, 14)):
        return "white", md == (3, 14)
    lu = EV_LUNAR.get(d.year)
    if lu:
        for sub, s in (("seol", lu[0]), ("chuseok", lu[1])):
            try:
                m, dd = map(int, s.split("-"))
                gap = (d - _dt.date(d.year, m, dd)).days
            except Exception:
                continue
            if -1 <= gap <= 1:
                return sub, gap == 0
    if (4, 1) <= md <= (4, 7):
        return "spring", md == (4, 4)
    if (7, 28) <= md <= (8, 3):
        return "summer", md == (8, 1)
    if md == (1, 1):
        return "newyear", True
    try:
        app = _EV_APP[0]
        mmdd = f"{md[0]:02d}-{md[1]:02d}"
        if app is not None and any(CHAR_BIRTHDAY.get(b.char.split("@")[0]) == mmdd for b in app.buddies):
            return "bday", True
    except Exception:
        pass
    return None, False


def _ev_bdir(app, char):
    try:
        return app.outfits[char]["basic"]["dir"]
    except Exception:
        c = app.chars.get(char) or {}
        return c.get("dir")


def _ev_has(app, char, kind):
    bd = _ev_bdir(app, char)
    off = EV_OFF.get(kind)
    return bool(bd and off is not None and os.path.exists(os.path.join(bd, f"{off}.png"))
                and os.path.exists(os.path.join(bd, f"{off + 7}.png")))


def _ev_call(app, c):
    try:
        return _pep_call(app, c)
    except Exception:
        return app.cfg.get("my_name") or CHAR_CALL.get(c) or "주인"


def _ev_line(app, b, sub, what):
    """what: 'start' / 'end' / 칸 번호"""
    kind = EV_SUB_KIND[sub]
    own = (EVENT_LINES.get(kind) or {}).get(b.char) or {}
    gen = EVENT_GENERIC.get(sub) or EVENT_GENERIC.get(kind) or {}
    pool = []
    if what == "start":
        pool = own.get("start") or gen.get("start") or []
    elif what == "end":
        pool = gen.get("end") or []
    else:
        g = gen.get(what) or []
        o = own.get("act") or []
        pool = o if (o and (not g or random.random() < 0.5)) else g
    if not pool:
        return ""
    return random.choice(pool).replace("{call}", _ev_call(app, b.char)).replace("{day}", EV_SUB_NAME.get(sub, "")).replace("데이이", "데이")


def ev_play(self, b, sub=None, force=False, kind=None):
    """이벤트 코스튬 쇼: 펑! 갈아입고 → 동작 몇 개 → 펑! 원래대로"""
    if sub is None and kind is not None:
        today, _ = _ev_today()
        sub = today if (today and EV_SUB_KIND.get(today) == kind) else \
            {"xmas": "xmas", "hanbok": "seol", "halloween": "halloween", "valentine": "valentine"}.get(kind, kind)
    if sub is None:
        sub, _ = _ev_today()
    if not sub:
        return False
    kind = EV_SUB_KIND[sub]
    off = EV_OFF[kind]
    if b not in self.buddies or b.drag is not None or not _ev_has(self, b.char, kind):
        return False
    if not b.surface:
        if not force:
            return False
        self.ground(b)
    b.goal = None
    b.vx = 0
    pool = list(EV_POOL.get(sub) or range(1, 8))
    random.shuffle(pool)
    chosen = pool[:3 if force else random.choice((2, 3))]
    t_in = 70
    seq = [(off, t_in)]
    t = t_in
    for cell in chosen:
        dur = random.randint(150, 210)
        QTimer.singleShot(int((t + 10) * TICK), lambda c=cell: b in self.buddies and b.state == "seq"
                          and b.say(_ev_line(self, b, sub, c) or "♪", 140))
        seq.append((off + cell, dur))
        t += dur
    seq.append((off, 55))
    total = t + 55
    try:
        Burst(b.cx, b.fy + b.S * 0.6, b.S * 0.9)
    except Exception:
        pass
    ln = _ev_line(self, b, sub, "start")
    if ln:
        b.say(ln, 90)

    def _end():
        if b not in self.buddies:
            return
        try:
            Burst(b.cx, b.fy + b.S * 0.6, b.S * 0.9)
        except Exception:
            pass
        e = _ev_line(self, b, sub, "end")
        if e and random.random() < 0.6:
            b.say(e, 100)
    QTimer.singleShot(int((total - 2) * TICK), _end)
    b.play_seq(seq)
    b._ev = {"kind": kind, "t0": time.time(), "end": total * TICK / 1000.0}
    b._ev_last = time.time()
    tm = QTimer(b)

    def _tick():
        d = getattr(b, "_ev", None)
        if b not in self.buddies or not d or time.time() - d["t0"] > d["end"] or b.state != "seq":
            b._ev = None
            tm.stop()
        try:
            b.update()
        except Exception:
            tm.stop()
    tm.timeout.connect(_tick)
    tm.start(50)
    b._ev_tm = tm
    return True


def ev_all(self, sub=None, force=True):
    """다 같이 이벤트 코스튬 (조금씩 시차를 두고)"""
    if sub is None:
        sub, _ = _ev_today()
    if not sub:
        return 0
    kind = EV_SUB_KIND[sub]
    n = 0
    for i, b in enumerate([x for x in self.buddies if _ev_has(self, x.char, kind) and x.drag is None]):
        QTimer.singleShot(250 + i * random.randint(350, 700), lambda b=b: b in self.buddies and self.ev_play(b, sub, force=force))
        n += 1
    return n


def _ev_paint(b):
    """코스튬 쇼 동안 몸 주변에 눈송이·반짝이·하트"""
    from PyQt5.QtGui import QColor, QPainterPath
    from PyQt5.QtCore import QPointF
    d = b._ev
    kind = d["kind"]
    now = time.time() - d["t0"]
    S = float(b.S)
    f = b.frame()
    top, bot = b.ftop(f), b.fbottom(f)
    p = QPainter(b)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    fade = max(0.0, min(1.0, now / 0.6, (d["end"] - now) / 0.6))
    for i in range(8):
        fx = ((i * 0.618) % 1.0)
        x = S * (0.12 + 0.76 * fx)
        if kind == "xmas":                                   # 내리는 눈
            ph = (now * (0.22 + 0.05 * (i % 3)) + i * 0.137) % 1.0
            y = S * (top - 0.08 + ph * (bot - top + 0.12))
            x += S * 0.03 * math.sin(now * 2 + i)
            r = S * (0.010 + 0.006 * (i % 3))
            p.setBrush(QColor(210, 230, 255, int(150 * fade)))
            p.drawEllipse(QPointF(x, y), r * 1.6, r * 1.6)
            p.setBrush(QColor(255, 255, 255, int(240 * fade)))
            p.drawEllipse(QPointF(x, y), r, r)
        elif kind == "valentine":                            # 떠오르는 하트
            ph = (now * (0.18 + 0.04 * (i % 3)) + i * 0.173) % 1.0
            y = S * (bot - ph * (bot - top + 0.1))
            x += S * 0.025 * math.sin(now * 2.5 + i)
            r = S * (0.012 + 0.005 * (i % 3))
            a = int(220 * fade * (1 - ph * 0.7))
            p.setBrush(QColor(255, 105, 150, a) if i % 2 else QColor(255, 160, 190, a))
            p.drawEllipse(QPointF(x - r * 0.55, y - r * 0.35), r * 0.62, r * 0.62)
            p.drawEllipse(QPointF(x + r * 0.55, y - r * 0.35), r * 0.62, r * 0.62)
            path = QPainterPath()
            path.moveTo(x - r * 1.12, y - r * 0.15); path.lineTo(x + r * 1.12, y - r * 0.15); path.lineTo(x, y + r * 1.15)
            path.closeSubpath()
            p.drawPath(path)
        elif kind in ("spring", "bday"):                    # 벚꽃잎 / 색종이가 팔랑팔랑
            from PyQt5.QtCore import QRectF
            ph = (now * (0.16 + 0.04 * (i % 3)) + i * 0.137) % 1.0
            y = S * (top - 0.08 + ph * (bot - top + 0.12))
            x += S * 0.04 * math.sin(now * 1.6 + i)
            r = S * (0.011 + 0.004 * (i % 3))
            a = int(225 * fade)
            p.save()
            p.translate(x, y)
            p.rotate((now * (160 if kind == "bday" else 90) + i * 45) % 360)
            if kind == "spring":
                p.setBrush(QColor(255, 183, 205, a) if i % 2 else QColor(255, 214, 228, a))
                p.drawEllipse(QPointF(0, 0), r * 1.5, r * 0.8)
            else:
                cr = ((255, 90, 90), (255, 200, 60), (90, 200, 255), (140, 230, 120), (220, 120, 255))[i % 5]
                p.setBrush(QColor(cr[0], cr[1], cr[2], a))
                p.drawRect(QRectF(-r, -r * 0.5, r * 2, r))
            p.restore()
        elif kind == "summer":                               # 물방울 뽀글뽀글
            ph = (now * (0.2 + 0.05 * (i % 3)) + i * 0.173) % 1.0
            y = S * (bot - ph * (bot - top + 0.1))
            x += S * 0.02 * math.sin(now * 3 + i)
            r = S * (0.010 + 0.006 * (i % 3))
            a = int(200 * fade * (1 - ph * 0.6))
            p.setBrush(QColor(120, 200, 255, a // 2))
            p.drawEllipse(QPointF(x, y), r * 1.4, r * 1.4)
            p.setBrush(QColor(255, 255, 255, a))
            p.drawEllipse(QPointF(x - r * 0.4, y - r * 0.4), r * 0.4, r * 0.4)
        else:                                                # 반짝이 (한복=금빛 / 할로윈=주황·보라)
            tw = 0.5 + 0.5 * math.sin(now * 4 + i * 1.7)
            y = S * (top + ((i * 0.381) % 1.0) * (bot - top))
            r = S * (0.008 + 0.012 * tw)
            if kind == "hanbok":
                col = QColor(255, 214, 90, int(230 * fade * tw))
            else:
                col = QColor(255, 140, 30, int(230 * fade * tw)) if i % 2 else QColor(170, 90, 255, int(230 * fade * tw))
            p.setBrush(col)
            path = QPainterPath()
            path.moveTo(x, y - r * 2); path.lineTo(x + r * 0.5, y - r * 0.5); path.lineTo(x + r * 2, y)
            path.lineTo(x + r * 0.5, y + r * 0.5); path.lineTo(x, y + r * 2); path.lineTo(x - r * 0.5, y + r * 0.5)
            path.lineTo(x - r * 2, y); path.lineTo(x - r * 0.5, y - r * 0.5)
            path.closeSubpath()
            p.drawPath(path)
    p.end()


def _ev_menu(self, top, who):
    """캐릭터 우클릭: '이벤트 코스튬' (그림이 있는 것만)"""
    _EV_APP[0] = self
    try:
        ks = [k for k in EV_OFF if _ev_has(self, who.char, k)]
        if not ks:
            return
        sub, _ = _ev_today()
        if sub and EV_SUB_KIND[sub] in ks:
            top.addAction(f"{EV_SUB_NAME[sub]} 코스튬!", lambda: self.ev_play(who, sub, force=True))
        m = top.addMenu("이벤트 코스튬")
        for k in ks:
            m.addAction(EV_MENU[k], lambda k=k: self.ev_play(who, None, force=True, kind=k))
    except Exception:
        pass


def _ev_menu_all(self, pl):
    """놀이 메뉴: 이벤트 기간엔 '다 같이 OO 코스튬'"""
    try:
        sub, _ = _ev_today()
        if sub and any(_ev_has(self, b.char, EV_SUB_KIND[sub]) for b in self.buddies):
            pl.addAction(f"다 같이 {EV_SUB_NAME[sub]} 코스튬!", lambda: self.ev_all(sub))
    except Exception:
        pass


# ── 봄(벚꽃)·여름(수영복)·생일 파티 코스튬: 162~169 벚꽃 / 170~177 수영복 / 178~185 생일 ──
EVENT_GENERIC.update({
    "spring": {
        "start": ["벚꽃 피었어요~ 꽃구경 가요!", "봄나들이 옷 어때요?", "꽃잎이 팔랑팔랑~"],
        "end": ["꽃구경 끝! 또 와요~", "봄바람 좋다~", "{call}, 다음에도 같이 와요!"],
        1: ["음~ 벚꽃 향기 좋다~", "{call}도 맡아 볼래요?"],
        2: ["도시락 맛있다~!", "{call}, 한 입 줄까요?"],
        3: ["꽃잎 잡으면 소원이 이뤄진대요!", "에잇! 잡았다~?"],
        4: ["벚꽃 경단 쫀득쫀득~", "분홍색이 제일 맛있어요♪"],
        5: ["후~ 꽃잎 날려 보내기!", "꽃비 내린다~"],
        6: ["나비야, 같이 놀자~", "기다려~ 나비야!"],
        7: ["봄볕이 따뜻해서 졸려요…", "꽃잎 이불 포근해… Zz"],
    },
    "summer": {
        "start": ["여름이다~! 바다 가요!", "수영복 어울려요?", "더워~ 물놀이하자!"],
        "end": ["물놀이 끝! 시원했다~", "다음 여름에 또 와요!", "{call}, 선크림 꼭 발라요!"],
        1: ["튜브 타고 둥실둥실~", "파도 온다~!"],
        2: ["물총 공격~! 피해 봐요!", "{call} 명중~♪"],
        3: ["수박은 역시 여름이죠!", "씨는 퉤퉤~"],
        4: ["비치볼 받아요~!", "토스~!"],
        5: ["모래성 완성되면 {call}도 초대할게요!", "영차영차~"],
        6: ["으앗, 머리 띵해…!", "빙수 너무 차가워~"],
        7: ["햇볕 좋다… Zz", "선글라스 끼고 휴가 중~"],
    },
    "bday": {
        "start": ["생일 파티다~! 팡!", "오늘은 생일! 다 같이 축하해요~", "고깔모자 썼어요♪"],
        "end": ["파티 끝! 행복한 하루였어요~", "생일 축하해요, 진짜로!", "{call}도 같이 축하해 줘서 고마워요!"],
        1: ["케이크 왔어요~ 조심조심!", "촛불 꺼지면 안 돼~"],
        2: ["소원 빌고… 후~!", "한 번에 다 껐다!"],
        3: ["우와, 선물이다!", "뭐가 들었을까~?"],
        4: ["풍선 둥실둥실~", "날아갈 것 같아요!"],
        5: ["케이크 맛있어~ 크림 묻었다", "{call}도 한 조각!"],
        6: ["생일 축하합니다~♪", "짝짝짝! 축하해요~"],
        7: ["너무 신나서 졸려요…", "선물 꼭 안고… Zz"],
    },
})


# ── 이벤트 코스튬 대사 (칸 번호: 1~7 동작, start 갈아입을 때, end 원래대로) ──
EVENT_GENERIC.update({
    "xmas": {
        "start": ["메리 크리스마스~!", "짠! 산타 등장~", "산타 옷 어때요? 잘 어울려요?"],
        "end": ["산타 퇴근~ 또 올게요!", "선물 배달 끝!", "메리 크리스마스, {call}!"],
        1: ["{call}, 선물이에요! 뜯어 봐요~", "착한 아이한테만 주는 선물이에요♪", "리본 풀어 볼래요?"],
        2: ["선물 배달 가는 중~", "자루가 꽤 무거워요…!", "다음 집은 어디더라~"],
        3: ["눈사람 완성! 이름 지어 줘요~", "코는 당근으로 할까요?", "눈사람아, 녹지 마~"],
        4: ["크리스마스 케이크 최고~", "딸기는 마지막에 먹을 거예요♪", "한 입 줄까요?"],
        5: ["눈이다~!", "화이트 크리스마스다!", "눈송이 잡았다~"],
        6: ["징글벨 징글벨~♪", "울면 안 돼~ 울면 안 돼~♪", "캐럴 같이 불러요!"],
        7: ["산타 할아버지 기다리다 졸려…", "양말 걸어 놨으니까… 쿨…", "Zz… 선물…"],
    },
    "seol": {
        "start": ["새해 복 많이 받으세요!", "설날엔 한복이죠~", "짠! 한복 입었어요~"],
        "end": ["올해도 잘 부탁해요!", "복 많이 받아요, {call}!", "설날 잘 보내요~"],
        1: ["{call}, 새해 복 많이 받으세요!", "세배 받으세요~ 세뱃돈은요?", "올해도 건강하세요!"],
        2: ["복주머니 받아요! 복이 가득~", "올해 복은 여기 다 넣어 놨어요", "{call} 몫의 복이에요!"],
        3: ["떡국 먹었으니 한 살 더~", "떡국 한 그릇 더!", "떡국은 역시 고명이죠~"],
        4: ["연 날리기~ 높이높이!", "바람 좋다~ 연이 쭉쭉 올라가요!", "액운아 날아가라~"],
        5: ["윷이다! 아니 모다!", "윷놀이 한 판 해요!", "던진다~ 도 나오지 마라!"],
    },
    "newyear": {
        "start": ["해피 뉴 이어~!", "새해 첫날이에요! 한복 입었어요~", "새해 복 많이 받으세요!"],
        "end": ["올해도 같이 있어요!", "새해엔 좋은 일만 가득!", "올해도 잘 부탁해요, {call}!"],
        1: ["{call}, 새해 복 많이 받으세요!", "올해도 잘 부탁드려요~ 넙죽!", "세뱃돈은… 마음만 받을게요♪"],
        2: ["새해 복주머니예요!", "올해 복 다 드릴게요~", "복 받아 가세요~"],
        3: ["새해엔 떡국이죠~", "한 살 더 먹었다…", "떡국 맛있다~"],
        4: ["새해 첫 연 날리기!", "소원 담아서 높이~", "연아 올라가라~"],
        5: ["새해 첫 윷놀이!", "모 나와라~!", "올해 운세를 윷으로!"],
    },
    "chuseok": {
        "start": ["즐거운 추석 보내세요~", "한가위엔 한복이죠!", "짠! 추석 한복이에요~"],
        "end": ["더도 말고 덜도 말고 한가위만 같아라~", "추석 잘 보내요, {call}!", "보름달처럼 둥글둥글한 하루!"],
        2: ["추석 선물이에요~", "복 많이 받아요!", "{call} 거 챙겨 왔어요~"],
        5: ["윷놀이 한 판 해요!", "윷이다~!", "모 나와라 모!"],
        6: ["송편 빚었어요! 예쁘죠?", "송편 예쁘게 빚으면 예쁜 딸 낳는대요~", "깨 송편 먹을래요?"],
        7: ["보름달님, 소원 들어주세요…", "{call} 소원도 같이 빌었어요", "달이 정말 크고 밝다~"],
    },
    "halloween": {
        "start": ["해피 할로윈~!", "트릭 오어 트릿!", "분장했어요! 무섭죠? …안 무서워요?"],
        "end": ["할로윈 끝~ 사탕 고마워요!", "다음 할로윈에 또 놀래 줄게요!", "오늘 밤은 유령 조심~"],
        1: ["트릭 오어 트릿! 사탕 주세요~", "사탕 안 주면 장난칠 거예요!", "{call}, 사탕 있어요?"],
        2: ["호박 등불 들고 사탕 받으러~", "어두운 길도 호박이 비춰 줘요", "다음 집으로 출발!"],
        3: ["왁!!", "놀랐죠? 놀랐죠?", "크앙~ 무섭지~"],
        4: ["사탕 냠냠~", "할로윈 사탕은 왜 더 맛있을까요?", "이거 하나만 더…"],
        5: ["으앗! 유, 유령?!", "깜짝이야…! 귀여운 유령이었네", "나, 나 안 무서웠어요!"],
        6: ["호박 의자 최고~", "호박 위에서 사탕 먹기~", "다리 흔들흔들~"],
        7: ["빙글빙글~ 분장 예쁘죠?", "망토 휘날리기~", "할로윈의 주인공!"],
    },
    "valentine": {
        "start": ["해피 발렌타인~", "오늘은 발렌타인데이!", "초콜릿… 준비했어요"],
        "end": ["달달한 하루 보내요♥", "초콜릿 맛있게 먹어요!", "해피 발렌타인, {call}!"],
        1: ["{call}, 이거… 받아 줄래요?", "직접 만든 초콜릿이에요…", "열어 보는 건 나중에!"],
        2: ["초콜릿 녹이는 중~", "맛있어져라~ 맛있어져라~", "앗, 볼에 묻었나?"],
        3: ["흥! 의리 초콜릿이야!", "착각하지 마! 남아서 주는 거야!", "…받을 거면 빨리 받아"],
        6: ["하트 뿅~♥", "마음 전달 완료!", "♥ 받아 줘요!"],
        7: ["답례도 기대할게요♪", "선물 교환 성공~", "행복하다…"],
    },
    "white": {
        "start": ["해피 화이트데이~", "오늘은 화이트데이!", "사탕… 받을 수 있을까?"],
        "end": ["사탕 고마워요!", "달콤한 하루 보내요~", "해피 화이트데이, {call}!"],
        4: ["사탕이다~! 고마워요!", "이거 나 주는 거예요? 와아!", "사탕 바구니 득템!"],
        5: ["사탕 냠냠~", "달다 달아~", "하트 사탕이 제일 맛있어요♪"],
        6: ["고마운 마음 하트로~♥", "♥ 뿅!", "{call}한테 하트 발사~"],
        7: ["선물 꼭 안고 있을래요", "행복하다~", "평생 간직할게요!"],
    },
})

def _evl(s1, s2, a1, a2, a3=None):
    return {"start": [s1, s2], "act": [a1, a2] + ([a3] if a3 else [])}


EVENT_LINES["xmas"] = {
    # 스텔라이브
    "yuni": _evl("메리 크리스마스 욘서~!", "산타 유니 출동이야 욘서~", "케이크 먼저 먹어도 돼? 배고파 와~", "{call}, 선물 받아 욘서~"),
    "kanna": _evl("메리 크리스마스예요~!", "산타 칸나 왔어요! 노래 선물 할까요?", "캐럴은 칸나가 제일 잘 불러요~", "{call}, 선물 받아요!"),
    "huya": _evl("메, 메리 크리스마스… 후하요~", "산타 옷… 이상하지 않아요?", "선물… 드려도 될까요…? (고장)", "눈이다… 예뻐요…"),
    "hina": _evl("명천재 산타 등장!", "메리 크리스마스! 다이아 각 선물이에요!", "선물 포장도 천재적이죠?", "케이크 한 입… 도파민 충전!"),
    "mashiro": _evl("메리 크리스마스~ 흠흐밍!", "꺄르륵, 산타 마시로야~", "선물 줄게~ 흠흐밍", "눈사람 만들자~ 꺄르륵"),
    "lize": _evl("…메리 크리스마스", "산타 옷… 입어 봤어", "…선물. 받아. 미웡 아니야", "눈 오네… 느엥, 추워"),
    "tabi": _evl("메리 크리스마스! 타비 산타야!", "선물 배달 왔어~!", "{call} 선물은 타비가 직접 골랐어!", "눈사람 만들자! 내가 머리 할게!"),
    "rin": _evl("메리 크리스마스예요~", "산타 린 왔어요!", "선물 준비했어요, {call}!", "캐럴 한 곡 할까요?"),
    "riko": _evl("하이용사! 메리 크리스마스~", "용사 산타 등장!", "선물 받아라 용사여~", "눈싸움 할 사람~ 아하하!"),
    "shibuki": _evl("자자 메리 크리스마스~!", "산타 시부키 출동!", "구라야~ 선물 진짜 있어!", "눈 맞고 신났다~"),
    "nana": _evl("메리 크리스마스 아이가~!", "산타 나나 왔데이!", "선물 받아 보쏘~", "케이크 묵자! 대박이제!"),
    "toa": _evl("메리 크리스마스~", "산타 토아야~ 어때?", "선물 줄게~ 기대해", "눈 오니까 기분 좋다~"),
    "rang": _evl("어흥! 메리 크리스마스!", "호랑이 산타 등장! 어흥!", "선물이다! 완전 대박!", "눈밭에서 뒹굴고 싶다~ 어흥!"),
    "hiyori": _evl("메리 크리스마스예요~ 하핫", "산타 히요리 왔어요!", "선물이에요~ 하핫", "케이크 너무 맛있어요~"),
    "mary": _evl("메리 크리스마스다 냐", "메리 산타다 냐. 이름이 같다 냐", "선물이다 냐. 받아라 냐", "눈은 차갑다 냐…"),
    "bingha": _evl("메리 크리스마스예요~ 청초한 산타 토끼!", "산타 옷 입은 토끼 보셨어요?", "{call}, 선물이에요! 밥은 먹었어요?", "케이크는 청초하게… 냠!"),
    # 니케
    "rapi": _evl("메리 크리스마스입니다, {call}.", "…산타 복장, 임무라면 수행하겠습니다.", "보급품… 아니, 선물입니다.", "캐럴은… 조금만 부르겠습니다."),
    "anis": _evl("메리 크리스마스~ 산타 아니스 등장!", "이 옷 따뜻하다~ 산타 할 만하네", "선물? 탄산수 한 박스다!", "케이크엔 탄산수지~"),
    "marian": _evl("메리 크리스마스, {call}.", "산타 옷… 어울려요?", "선물이에요. 다친 데 없죠?", "눈이 와요… 같이 봐서 좋아요."),
    "dorothy": _evl("메리 크리스마스, 귀하.", "후후, 산타라니. 이번만이에요.", "선물이에요. 감사히 받으시죠.", "크리스마스 티타임도 나쁘지 않군요."),
    "scarlet": _evl("허허, 메리 크리스마스일세, 도령.", "이 붉은 옷, 내 이름과 잘 어울리지 않는가?", "선물일세. 한잔도 곁들이겠나?", "눈 내리는 밤엔 술 한잔이 제격이지."),
    "rapunzel": _evl("메리 크리스마스예요, 형제님.", "후후, 오늘은 성녀 대신 산타랍니다.", "형제님께 드리는 선물이에요♪", "축복의 캐럴을 불러 드릴게요."),
    "blanc": _evl("메리 크리스마스예요, 점장님!", "산타 토끼 블랑 등장! 행운 선물 배달 왔어요~", "선물이에요! 언니 것도 있어요♪", "크리스마스 특별 쇼, 기대해 주세요!"),
    "noir": _evl("메, 메리 크리스마스예요⋯", "산타 옷⋯ 으⋯ 부끄러워.", "점장님께 드리는 선물이에요⋯ 블랑이랑 같이 골랐어요.", "눈 오는 밤⋯ 같이 있어서 좋아요."),
    # 붕괴·버튜버·기타
    "elysia": _evl("메리 크리스마스, 함장~♪", "어머, 산타 엘리시아 어때? 너무 귀엽지?♪", "함장 선물은 특별히 리본도 예쁘게 묶었어♪", "눈 오는 날엔 꼭 붙어 있어야지~♪"),
    "chune": _evl("계추!! 메리 크리스마스데이~", "산타 춘회 왔다! 춘식아!", "선물이다~ 받아라 춘식아", "크리스마스엔 집에서 게임이제~"),
    "arisa": _evl("메리 크리스마스예요… 무용이들", "산타 아리사예요. 무요?", "선물이에요… 안에 콜라 들었어요", "내가 이겨따… 눈싸움"),
    "karin": _evl("메리 크리스마스~ 베리들!", "산타 카린 등장~ 어때 어때?", "선물 받아! 포장 내가 했어!", "캐럴은 내가 고음으로 불러 줄게~"),
    "eris": _evl("앙용~ 메리 크리스마스!", "근끼도 산타 모자 썼어~", "팡이들 선물 줄게~", "민트초코 케이크는 없나…"),
    "ellie": _evl("메리 크리스마스냥!", "산타 엘리 등장! 익스플로전!", "슬라임들 선물 받아라냥~", "눈사람 웰키 버전 만들어야지"),
    "dokcake": _evl("메리 크리스마스다죠~", "독쌤 산타가 왔다죠~", "개떡이들 선물 받아 가세요~", "크리스마스 특별 수업은 케이크 먹기다죠~"),
    "delia": _evl("메리 크리스마스예요, 용병님!", "왕녀 산타 등장이에요!", "용병님 선물이에요! 딸기 케이크도 있답니다", "눈싸움이라면 지지 않아요!"),
    # 홀로라이브
    "sora": _evl("메리 크리스마스, 소라토모~", "산타 소라 왔어요♪", "선물이에요~ 소라가 고른 거예요", "겨울이 제일 좋아~ 눈이다!"),
    "roboco": _evl("하로~보~! 메리 크리스마스!", "고성능 산타 로보코 출동!", "선물 배달… 앗 팔 빠졌다", "케이크 맛있다~ 크허허"),
    "miko": _evl("냐하로~ 메리 크리스마스니에!", "엘리트 산타 미코 등장!", "선물이다니에~ 따봉!", "캐럴 부를게! 징그루베루~"),
    "suisei": _evl("메리 크리스마스! 스이쨩은~?", "산타 스이쨩, 오늘도 귀여워~!", "선물이야~ 바치콩☆", "케이크엔 명란… 아니 딸기지"),
    "azki": _evl("메리 크리스마스예요, 개척자님.", "산타 AZKi예요.", "선물이에요. 지도는 아니에요", "캐럴 한 곡 불러 드릴게요."),
    "fubuki": _evl("콘콘 키-츠네! 메리 크리스마스!", "산타 여우 등장! 고양이 아니야!", "스콘부 선물이야~", "크리스마스엔 햄버거… 아니 치킨!"),
    "matsuri": _evl("왓쇼이! 메리 크리스마스~", "청초한 산타 마츠리 등장~", "선물이다~ 왓쇼이!", "크리스마스 축제다~!"),
    "aki": _evl("아로~나! 메리 크리스마스~", "산타 아키로제 왔어~", "선물이야~ 사과도 넣었어", "건배하자~ 크리스마스니까"),
    "haato": _evl("하아쨔마앗쨔마~ 메리 크리스마스!", "산타 하아쨔마 등장!", "선물이야! 수제 케이크… 먹어도 괜찮아!", "크리스마스 특제 요리 해 줄까?"),
    "aqua": _evl("콘아쿠아~ 메리 크리스마스!", "산타 메이드 아쿠아예요~", "아쿠아크루 선물이야~ 아틔시가 골랐어", "케이크 먹으면서 게임 하자~"),
    "shion": _evl("콘시오~ 메리 크리스마스~", "꼬마 마녀 산타 시온 등장~", "선물이야~ 너네 받을 사람 없지? 네에~", "케이크 맛있다~ 칭찬해 줘"),
    "ayame": _evl("인간님들 콘나키리~! 메리 크리스마스~", "요다요~ 산타 아야메!", "선물이다~ 요가 주는 거야", "눈이다~ 도치도치~"),
    "choco": _evl("Good evening~ 메리 크리스마스!", "산타 초코 선생님이야~", "선물이야~ 초코 과자 들었어", "케이크 직접 구웠어~ 가치이 맛있어"),
    "subaru": _evl("치와~스! 메리 크리스마스!", "산타 스바루 출동!", "선배, 선물이에요!", "눈이다~ 꽥!"),
    "marine": _evl("아호이~! 메리 크리스마스!", "산타 선장 등장! 17살 산타야!", "선원들, 보물… 아니 선물이다!", "크리스마스에 혼자 아니거든! 선원들 있거든!"),
    "noel": _evl("콘머슬~ 메리 크리스마스!", "산타 단장 왔어~", "단원들 선물이야~", "크리스마스엔 규동… 아니 치킨도 좋아!"),
    "pekora": _evl("콘페코~ 메리 크리스마스 페코!", "산타 페코라 등장 페코!", "선물이다 페코~ 당근 아니야 페코", "하↑하↑하↑ 산타 작전 성공 페코!"),
    "flare": _evl("콘누이~ 메리 크리스마스!", "산타 후레아 왔어~ 헤헤", "엘프렌드 선물이야~", "다 같이 있으니까 행복해서 눈물 나…"),
    "kanata": _evl("카나타소~ 메리 크리스마스!", "천사 산타 카나타!", "선물이야~ 고릴라 아니라 천사가 주는 거야", "눈사람은 악력으로 단단하게!"),
    "watame": _evl("콘반도도도~ 메리 크리스마스!", "산타 양 와타메~", "선물 주는 와타메는 나쁘지 않아, 그치?", "캐럴은 하프로~♪"),
    "towa": _evl("콘야삐~ 메리 크리스마스!", "악마 산타 토와 등장!", "선물이야~ 비비가 골랐어", "초콜릿 케이크가 최고지"),
    "luna": _evl("메리 크리스마스나노라~!", "산타 루나 공주님이나노라!", "선물이나노라~ 어른이 주는 거나노라!", "다코야키 케이크는 없나노라?"),
    "lamy": _evl("콘라미~ 메리 크리스마스!", "눈의 나라에서 온 산타 라미예요~", "선물이에요~ 다이후쿠도 같이", "눈은 라미 담당이에요~"),
    "nene": _evl("콘네네~ 메리 크리스마스!", "슈퍼 산타 네네치!", "선물이야~ 이번엔 진짜 4조 엔!", "네네프로 크리스마스 파티!"),
    "botan": _evl("라라이온~ 메리 크리스마스", "사자 산타 보탄", "선물이다~ 포이!", "케이크에 오렌지 주스… 최고"),
    "polka": _evl("폴카 있어~? 메리 크리스마스!", "서커스 산타 폴카 등장! 폴!", "선물 저글링~ 받아!", "선물 배달 가다 길 잃었어…"),
    "laplus": _evl("메리 크리스마스다, 네놈들!", "총수 산타 라플라스 강림!", "선물이다. 이 몸이 주는 거니 감사히 받아라!", "아기 아니거든! 산타거든!"),
    "lui": _evl("기다렸지? 메리 크리스마스~", "산타 루이 언니야~", "선물이야~ 간모가 포장했어", "크리스마스 아재개그 하나… 아니야"),
    "koyori": _evl("콘코요~ 메리 크리스마스!", "코요테 산타 코요리!", "조수 군 선물이야~ 실험 성공!", "케이크에 마요네즈… 안 돼?"),
    "chloe": _evl("바쿠바쿠~ 메리 크리스마스!", "범고래 산타 클로에!", "사육사 선물이야~", "산타 일 끝나면 반나절 잘 거야…"),
    "iroha": _evl("메리 크리스마스고자루!", "사무라이 산타 이로하고자루!", "선물이고자루! 받아 주시오~", "눈싸움이라면 지지 않고자루!"),
    "ao": _evl("메리 크리스마스, 독자님.", "산타 아오 왔어.", "선물이야. 펜도 들었어", "눈 오는 카페, 같이 갈래?"),
    "kanade": _evl("메리 크리스마스~ 오토노제이", "산타 카나데예요~ 느긋하게~", "선물이에요~ 피아노 연주도 같이~", "크리스마스 다음은… 월요일이에요"),
    "ririka": _evl("메리 크리스마스! 카와이! 포지티브! 천재!", "사장님 산타 리리카 등장~", "비서 견습생, 선물이야~", "크리스마스엔 고기 파티지!"),
    "raden": _evl("메리 크리스마스예요, 덴동지 여러분.", "라쿠고가 산타 라덴입니다.", "선물이에요. 조개 무늬 포장이에요", "크리스마스엔 일본주 한잔…"),
    "hajime": _evl("콘치쿠와~ 메리 크리스마스!", "부릉부릉~ 산타 번장 등장!", "선물이다~ 반펜이랑 골랐어", "크리스마스 댄스~ 콘코콘콘~"),
    "mio": _evl("메리 크리스마스~ 미오파", "산타 미오야~", "선물이야~ 미오 엄마가 챙겼어", "타로로 보니까 오늘 행운 가득이래~"),
    "okayu": _evl("모구모구 오카유~ 메리 크리스마스~", "고양이 산타 오카유야~", "선물이야~ 주먹밥 아니야~", "크리스마스엔 코타츠에서 뒹굴~"),
    "korone": _evl("메리 크리스마스~ 코로네스키!", "강아지 산타 코로네 등장~", "선물이야~ 유비유비 줘~", "크리스마스 내구 방송 할까~"),
    "riona": _evl("메리 크리스마스.", "산타 리오나야.", "선물. …마음에 들었으면 좋겠어", "캐럴, 한 소절만 불러 줄게."),
    "niko": _evl("메리 크리스마스~ 니코탄!", "호랑이 산타 니코 등장~", "선물이야~ 고기는 아니야!", "산타 개그 하나 할까?"),
    "su": _evl("메리 크리스마스~ 스우리스!", "쪼끄만 산타 스우!", "선물이에요~ 스바루 선배 거는 따로!", "크리스마스엔 전골 파티!"),
    "chihaya": _evl("메리 크리스마스~ 닉", "DJ 산타 치하야 등장~", "선물이야~ 후구타로 타고 배달 왔어", "크리스마스 믹스 틀어 줄게~"),
    "vivi": _evl("메리 크리스마스~ 비비드!", "산타 메이크업 완료~", "선물이야~ 내가 고른 립밤!", "케이크 먹으면 화장 지워지는데… 먹을래!"),
}

EVENT_LINES["hanbok"] = {
    "yuni": _evl("{day}엔 한복이야 욘서~", "한복 입은 유니 어때? 욘서~", "전 부쳐 먹고 싶다 와~", "{call}, 복 많이 받아 욘서~"),
    "kanna": _evl("한복 입었어요~ {day} 잘 보내요!", "칸나 한복 예쁘죠?", "{call}, 복 많이 받아요~", "명절엔 노래자랑이죠!"),
    "huya": _evl("하, 한복… 어색해요… 후하요~", "{day}… 잘 보내세요…", "복 많이 받으세요… (고장)", "치마가 길어서… 넘어질 것 같아요"),
    "hina": _evl("명천재 한복 등장! {day}!", "한복도 다이아 각이죠?", "{call}, 복 많이 받아요!", "윷놀이도 천재적으로!"),
    "mashiro": _evl("{day}이야~ 흠흐밍!", "한복 마시로~ 꺄르륵", "복 받아라~ 흠흐밍", "윷 던지기~ 꺄르륵"),
    "lize": _evl("…한복 입었어", "{day}… 잘 보내", "복… 많이 받아. 진짜야", "…떡 맛있다. 느엥"),
    "tabi": _evl("{day}엔 한복이지! 타비 예쁘지?", "한복 입고 놀자~!", "{call}, 복 받아! 타비가 주는 복!", "윷놀이 내가 이길 거야!"),
    "rin": _evl("{day} 잘 보내세요~ 한복 입었어요!", "한복 린 어때요?", "{call}, 복 많이 받아요!", "송편이랑 떡국 다 좋아요~"),
    "riko": _evl("하이용사! {day}다~", "한복 용사 등장! 아하하", "복주머니는 용사의 보물!", "윷 던진다~ 모 나와라!"),
    "shibuki": _evl("자자 {day}이다~!", "한복 시부키 출동!", "구라야~ 복 진짜 많이 넣었어!", "윷놀이 한 판 붙자!"),
    "nana": _evl("{day}이데이! 한복 입었다 아이가~", "한복 나나 예쁘제?", "복 많이 받아 보쏘~", "떡국 한 그릇 묵자!"),
    "toa": _evl("{day}이야~ 한복 입었어", "한복 어때? 예쁘지~", "{call}, 복 많이 받아~", "보름달 보면서 소원 빌자~"),
    "rang": _evl("어흥! {day}이다!", "호랑이 한복! 까치호랑이 아니야 어흥!", "복주머니다! 완전 대박!", "윷놀이 호랑이가 이긴다 어흥!"),
    "hiyori": _evl("{day} 잘 보내세요~ 하핫", "한복 입었어요~", "복 많이 받아요~ 하핫", "송편 예쁘게 빚었어요~"),
    "mary": _evl("{day}다 냐. 한복이다 냐", "메리 한복 입었다 냐", "복이다 냐. 받아라 냐", "떡은 쫀득하다 냐"),
    "bingha": _evl("{day}엔 청초한 한복 토끼죠~", "달토끼 한복 어때요?", "{call}, 복 많이 받아요! 밥은 먹었어요?", "떡은 토끼가 제일 잘 찧어요~"),
    "rapi": _evl("{day}입니다, {call}. 한복… 착용했습니다.", "복장이 익숙하지 않군요.", "복 많이 받으십시오.", "윷놀이… 전략적으로 하겠습니다."),
    "anis": _evl("{day}~ 한복 아니스 등장!", "한복 은근 편하다?", "복주머니에 탄산수 넣어 줄까?", "윷 던지는 건 장전보다 쉽네~"),
    "marian": _evl("{day}이에요, {call}. 한복 입었어요.", "한복… 예뻐요?", "복 많이 받으세요. 아프지 말고요.", "보름달한테 {call} 건강하게 해 달라고 빌었어요."),
    "dorothy": _evl("{day}이군요, 귀하. 한복이라는 옷이에요.", "후후, 우아하지 않나요?", "복을 나눠 드리죠. 감사히 받으세요.", "송편과 차라니… 나쁘지 않군요."),
    "scarlet": _evl("허허, {day}일세. 한복이 몸에 맞는구먼.", "도령, 절 받게나.", "복주머니일세. 술값은 아니고.", "보름달에 한잔… 이게 명절이지."),
    "rapunzel": _evl("{day}이에요, 형제님.", "한복도 수녀복만큼 단정하죠? 후후", "형제님께 복을 나눠 드릴게요.", "보름달님께 모두의 평안을 빌었어요."),
    "blanc": _evl("{day}이에요, 점장님! 복 많이 받으세요~", "한복 입은 토끼 어때요? 언니랑 커플이에요!", "윷놀이 한 판! 행운은 제 편이에요♪", "점장님께 복이랑 행운이랑 듬뿍!"),
    "noir": _evl("{day}이에요⋯ 점장님.", "한복⋯ 어울려요⋯? 으⋯", "새해 복⋯ 많이 받으세요⋯", "블랑이랑 같이 세배⋯ 드릴게요."),
    "elysia": _evl("함장~ {day}이야! 한복 입은 엘리시아 어때?♪", "어머, 한복도 이렇게 잘 어울리다니~♪", "세배 받아 줘~ 세뱃돈은 함장 마음으로♪", "보름달아, 함장이랑 오래오래 함께하게 해 줘♪"),
    "chune": _evl("계추!! {day}이데이~", "한복 입었다 춘식아! 얌전한 척 해 볼게", "복 많이 받아라 춘식아~", "윷놀이도 피지컬이제!"),
    "arisa": _evl("{day}이에요… 한복 입었어요", "500살에 한복은 처음… 무요?", "복이에요… 무용이들 받으세요", "윷놀이… 내가 이겨따"),
    "karin": _evl("{day}~ 한복 카린 등장!", "한복 네일도 맞췄어~", "베리들 복 받아~", "윷놀이 하자~ 나 진짜 잘해!"),
    "eris": _evl("앙용~ {day}이야!", "근끼도 한복 입혔어~", "팡이들 복 받아~", "송편에 민트초코 넣으면 안 되나…"),
    "ellie": _evl("{day}이다냥!", "한복 엘리 등장! 으잇으잇", "슬라임들 복 받아라냥~", "윷 던진다! 익스플로전!"),
    "dokcake": _evl("{day}이다죠~ 한복 입었다죠", "독쌤 한복 수업 시작~", "개떡이들 복 받아 가세요~", "떡국 먹고 한 살 더 먹는다죠~"),
    "delia": _evl("{day}이에요, 용병님! 한복이라는 옷이래요!", "왕녀의 한복 차림이랍니다~", "용병님께 복을 나눠 드려요!", "연 날리기도 기사의 수련이에요!"),
    "sora": _evl("{day} 잘 보내요, 소라토모~", "한복 소라 어때요?", "복 많이 받아요~", "보름달 보면서 노래 불러 줄게요"),
    "roboco": _evl("하로~보~! {day}이야!", "고성능 한복 로보코!", "복주머니 줄게~ 크허허", "떡국… 계란 지단은 빼 줘"),
    "miko": _evl("냐하로~ {day}이니에!", "엘리트 무녀 한복 미코!", "복 받으라니에~ 따봉!", "윷이다니에! …도였다니에"),
    "suisei": _evl("{day}! 한복 스이쨩도 귀여워~", "한복 입은 스이쨩은~? 귀여워~!", "복 받아~ 바치콩☆", "윷놀이도 테트리스처럼 완벽하게!"),
    "azki": _evl("{day}이에요, 개척자님. 한복 입었어요.", "한복 AZKi예요.", "복 많이 받으세요.", "연이 날아가는 방향… 북동쪽이네요. 게스!"),
    "fubuki": _evl("콘콘! {day}이야~", "한복 여우! 고양이 아니라니까!", "스콘부 복 받아~", "윷놀이 MC는 후부키가 할게!"),
    "matsuri": _evl("왓쇼이! {day}이다~", "청초한 한복 마츠리~", "복 받아라~ 왓쇼이!", "명절은 축제다~!"),
    "aki": _evl("아로~나! {day}이야~", "한복 아키로제~ 떠 있는 트윈테일도 한복 버전!", "복 받아~ 건배~", "송편이랑 사과 먹자~"),
    "haato": _evl("하아쨔마앗쨔마~ {day}!", "한복 하아쨔마!", "복이야! 요리는… 내가 안 할게", "김치 송편 만들어 볼까?"),
    "aqua": _evl("콘아쿠아~ {day}이야!", "한복 메이드 아쿠아~", "복 받아~ 아틔시가 주는 거야", "윷놀이… 바쿠아 아니거든!"),
    "shion": _evl("콘시오~ {day}이야~", "한복 시온 귀엽지? 네에~", "복 받아~ 세뱃돈 줘~", "윷놀이 지면 쿠소가키 소리 들을 거야~"),
    "ayame": _evl("인간님들~ {day}이다 요다요~", "한복 오죠 아야메~", "요가 주는 복이다~", "연 날리기~ 도치도치~"),
    "choco": _evl("{day}이야~ 한복 초코 선생님", "한복도 잘 어울리지? 가치이?", "복 받아~ 과자도 넣었어", "명절 음식은 선생님이 만들게~"),
    "subaru": _evl("치와~스! {day}이에요!", "한복 스바루 출동!", "선배, 복 많이 받아요!", "윷 던져요~ 꽥!"),
    "marine": _evl("아호이~! {day}이다!", "한복 선장! 17살 한복이야!", "보물 복주머니다! 선원들 받아!", "명절에 결혼 얘기 하지 마! 선장 17살이거든!"),
    "noel": _evl("콘머슬~ {day}이야~", "한복 단장 어때~", "단원들 복 받아~", "떡국 다섯 그릇은 먹을 수 있어~"),
    "pekora": _evl("콘페코~ {day}이다 페코!", "한복 페코라 페코!", "복 받아라 페코~", "달토끼는 페코라 친척이다 페코!"),
    "flare": _evl("콘누이~ {day}이야~", "한복 후레아~ 헤헤", "엘프렌드 복 받아~", "가족끼리 모이는 날… 좋다…"),
    "kanata": _evl("카나타소~ {day}이야!", "한복 천사 카나타!", "복 받아~ 세뱃돈은 아껴 써!", "떡은 악력으로 찧을게!"),
    "watame": _evl("콘반도도도~ {day}이야~", "한복 와타메~", "복 주는 와타메는 나쁘지 않아, 그치?", "보름달 노래 불러 줄게~"),
    "towa": _evl("콘야삐~ {day}이야!", "한복 토와! 천사 아니고 악마야!", "복 받아~ 비비도 같이", "윷놀이 지면 책상 쾅!"),
    "luna": _evl("{day}이나노라~!", "한복 루나 공주님이나노라!", "복 받으라나노라~", "세뱃돈 받는 쪽 아니나노라! 어른이나노라!"),
    "lamy": _evl("콘라미~ {day}이에요!", "한복 라미예요~", "복 받아요~ 다이후쿠도 같이", "명절엔 식혜도 좋아요~"),
    "nene": _evl("콘네네~ {day}이야!", "슈퍼 한복 네네치!", "복이다~ 이번엔 진짜 4조 엔!", "윷놀이 네네프로 대회!"),
    "botan": _evl("라라이온~ {day}", "한복 사자 보탄", "복 받아~ 포이!", "윷 던질 때도 포이!"),
    "polka": _evl("폴카 있어~? {day}이야!", "한복 폴카! 폴!", "복 저글링~ 받아!", "연 날리기 묘기~"),
    "laplus": _evl("{day}이다, 네놈들!", "총수의 한복 차림이다!", "복을 하사하노라!", "세배는… 이 몸이 받는 쪽이다!"),
    "lui": _evl("기다렸지? {day}이야~", "한복 루이 언니야~", "복 받아~ 간모도 같이", "송편 빚기 실수하면 어쩌지…"),
    "koyori": _evl("콘코요~ {day}이야!", "한복 코요리! 코요테야!", "조수 군 복 받아~", "떡국에 마요네즈… 실험해 볼까?"),
    "chloe": _evl("바쿠바쿠~ {day}이야!", "한복 범고래 클로에!", "사육사 복 받아~", "명절엔 많이 자는 게 최고야…"),
    "iroha": _evl("{day}이고자루!", "한복 차림의 사무라이고자루!", "복을 드리고자루!", "연 날리기 수련이고자루!"),
    "ao": _evl("{day}이야, 독자님.", "한복… 어울려?", "복 많이 받아.", "연에 그림 그려 봤어."),
    "kanade": _evl("{day}이에요~ 오토노제이", "한복 카나데예요~ 느긋하게~", "복 많이 받아요~", "명절 끝나면… 월요일이에요"),
    "ririka": _evl("{day}! 카와이! 포지티브! 천재!", "한복 사장님 리리카~", "비서 견습생 복 받아~", "명절엔 갈비지!"),
    "raden": _evl("{day}이네요, 덴동지 여러분.", "한복 차림의 라덴입니다.", "복을 나눠 드려요.", "보름달에 일본주 한잔…"),
    "hajime": _evl("콘치쿠와~ {day}이다!", "부릉부릉~ 한복 번장!", "복 받아라~ 반펜이랑 같이", "윷놀이도 번장이 이긴다!"),
    "mio": _evl("{day}이야~ 미오파", "한복 미오야~", "복 받아~ 미오 엄마가 챙겼어", "타로로 보니까 올해 운세 최고래~"),
    "okayu": _evl("모구모구 오카유~ {day}이야~", "한복 고양이 오카유~", "복 받아~", "송편이랑 주먹밥 둘 다 좋아~"),
    "korone": _evl("{day}이야~ 코로네스키!", "한복 강아지 코로네~", "복 받아~ 유비유비는 줘~", "윷놀이 내구 방송~"),
    "riona": _evl("{day}이야. 한복 입었어.", "…어울려?", "복 많이 받아.", "보름달… 예쁘다."),
    "niko": _evl("{day}이야~ 니코탄!", "한복 호랑이 니코~", "복 받아~ 고기 대신 복!", "윷놀이 개그 하나 할까?"),
    "su": _evl("{day}이에요~ 스우리스!", "한복 스우예요!", "복 받아요~", "명절엔 전골 아니고 떡국!"),
    "chihaya": _evl("{day}이야~ 닉", "한복 치하야~", "복 받아~", "명절 BGM 틀어 줄게~"),
    "vivi": _evl("{day}이야~ 비비드!", "한복 메이크업도 완벽~", "복 받아~", "떡 먹으면 립 지워지는데… 먹을래!"),
}

EVENT_LINES["halloween"] = {
    "yuni": _evl("트릭 오어 트릿 욘서~!", "할로윈 분장 유니야~", "사탕 안 주면 장난칠 거야 욘서~", "사탕 먹으니까 배부르다 와~"),
    "kanna": _evl("해피 할로윈이에요~!", "분장한 칸나 어때요?", "사탕 주세요~ 노래 불러 줄게요!", "으앗, 유령?! …귀엽네요"),
    "huya": _evl("트, 트릭 오어 트릿… 후하요~", "분장… 무섭나요…?", "놀래키기… 왁… (고장)", "유, 유령이다… 저보다 수줍어 보여요"),
    "hina": _evl("명천재 할로윈 등장!", "분장도 다이아 각!", "사탕 주면 천재적인 장난 안 쳐요!", "사탕으로 도파민 충전~"),
    "mashiro": _evl("트릭 오어 트릿~ 흠흐밍!", "할로윈 마시로~ 꺄르륵", "왁! 놀랐지~ 꺄르륵", "사탕 맛있다~ 흠흐밍"),
    "lize": _evl("…트릭 오어 트릿", "분장… 해 봤어", "사탕 안 주면 미웡", "유령… 무서워. 느엥"),
    "tabi": _evl("해피 할로윈! 타비 분장 봐 봐!", "트릭 오어 트릿!", "사탕 바구니 꽉 채울 거야!", "왁! 놀랐어? 놀랐지?"),
    "rin": _evl("해피 할로윈이에요~", "분장 린이에요!", "트릭 오어 트릿! 사탕 주세요~", "호박 위에 앉아 보고 싶었어요~"),
    "riko": _evl("하이용사! 해피 할로윈~", "마왕 분장 용사! 아하하", "사탕을 바쳐라 용사여~", "유령 따위 용사가 무찌른다!"),
    "shibuki": _evl("자자 해피 할로윈~!", "분장 시부키 출동!", "구라야~ 진짜 놀래킬 거야!", "사탕 많이 받았다~"),
    "nana": _evl("해피 할로윈이데이!", "분장했다 아이가~ 무섭제?", "사탕 줘 보쏘~", "유령이다! 대박이제!"),
    "toa": _evl("해피 할로윈~", "분장 어때? 무섭지~?", "트릭 오어 트릿~", "사탕 나눠 먹자~"),
    "rang": _evl("어흥! 해피 할로윈!", "호랑이가 분장까지 했다 어흥!", "사탕 안 주면 어흥 할 거야!", "유령 나와도 어흥이면 도망가!"),
    "hiyori": _evl("해피 할로윈이에요~ 하핫", "분장 히요리예요~", "사탕 주세요~ 하핫", "호박 등불 예쁘죠~"),
    "mary": _evl("트릭 오어 트릿이다 냐", "분장했다 냐. 원래 고양이 같다고? 냐", "사탕 내놔라 냐", "유령… 안 무섭다 냐… 조금 무섭다 냐"),
    "bingha": _evl("해피 할로윈이에요~ 청초한 분장 토끼!", "토끼가 분장하면 더 청초해요~", "{call}, 사탕 주세요! 밥은 먹었어요?", "왁! …청초하게 놀래켰어요"),
    "rapi": _evl("해피 할로윈입니다, {call}.", "…분장 임무, 수행 중입니다.", "유, 유령은 없습니다. 없습니다.", "사탕은… 보급품으로 받겠습니다."),
    "anis": _evl("트릭 오어 트릿~ 아니스 분장 등장!", "사탕보다 탄산수 줘~", "왁! 놀랐어? 히히", "유, 유령?! 라피, 라피 어딨어!"),
    "marian": _evl("해피 할로윈이에요, {call}.", "분장… 이상하지 않아요?", "사탕 드릴게요. 장난은 안 칠게요.", "유령도… 붕대 감아 줄까요?"),
    "dorothy": _evl("해피 할로윈이군요, 귀하.", "후후, 분장한 저도 우아하죠?", "사탕을 주지 않으면… 후후, 장난이 기다려요.", "유령 따위, 차 한 잔 하고 가라 하죠."),
    "scarlet": _evl("허허, 할로윈이라는 축제일세, 도령.", "분장도 멋들어지지 않은가?", "사탕보다는 술이 좋다만, 받겠네.", "유령이라… 한잔 같이 할 텐가?"),
    "rapunzel": _evl("해피 할로윈이에요, 형제님.", "후후, 성녀도 오늘은 분장해요.", "사탕 안 주시면… 아, 아무것도 아니에요.", "길 잃은 유령에게도 축복을♪"),
    "blanc": _evl("해피 할로윈! 트릭 오어 트릿~!", "유령 토끼 블랑 등장! 사탕 안 주면 장난칠 거예요!", "사탕 받으면 언니랑 반반이에요♪", "할로윈 쇼타임이에요!"),
    "noir": _evl("해, 해피 할로윈이에요⋯", "분장⋯ 무섭지 않아요⋯? 저는 좀 무서워요⋯", "트릭 오어⋯ 트릿⋯ (작게)", "블랑 손 잡고 다닐래요⋯"),
    "elysia": _evl("트릭 오어 트릿, 함장~♪", "어머, 분장한 엘리시아도 너무 귀엽지?♪", "사탕 안 주면 장난칠 거야~ 아니면 장난을 원해?♪", "유령도 귀여운 소녀한텐 반한다니까♪"),
    "chune": _evl("계추!! 해피 할로윈이데이~", "원래 뱀파이어인데 또 분장했다 춘식아!", "사탕 안 주면 피 빨아 묵는다~", "왁! 놀랐나? 머라카노~"),
    "arisa": _evl("해피 할로윈이에요… 무용이들", "흑마법사가 분장하면… 무요?", "사탕 대신 젤리 주세요", "유령… 친구예요. 믿지 않아 듣지 않아"),
    "karin": _evl("해피 할로윈~ 베리들!", "박쥐 날개 원래 있는데 분장 추가!", "사탕 안 주면 일진 모드다~", "유령이다! 너 뉘기야!"),
    "eris": _evl("앙용~ 해피 할로윈!", "근끼도 분장시켰어~", "팡이들 사탕 내놔~", "유령… 근끼가 지켜 줄 거야"),
    "ellie": _evl("트릭 오어 트릿냥!", "분장 엘리 등장! 익스플로전!", "사탕 안 주면 익스플로전이다냥!", "유령? 정령인가? 으잇으잇"),
    "dokcake": _evl("해피 할로윈이다죠~", "독쌤 분장 수업이다죠~", "사탕 안 주면 비명 지른다죠~ 끼이이~", "유령! 공포 게임 같다죠~"),
    "delia": _evl("해피 할로윈이에요, 용병님!", "분장한 왕녀랍니다!", "사탕 주세요! 딸기 사탕이면 더 좋아요!", "유령이라도 대검으로… 아, 귀엽네요"),
    "sora": _evl("해피 할로윈, 소라토모~", "분장 소라 어때요?", "사탕 안 주면… 그럼, 적이네?", "유령은 안 무서워요~ 벌레가 무섭지"),
    "roboco": _evl("하로~보~! 해피 할로윈!", "고성능 분장 로보코!", "사탕 안 주면 팔 발사! …앗 빠졌다", "유령이다~ 크허허"),
    "miko": _evl("냐하로~ 해피 할로윈이니에!", "엘리트 분장 미코!", "사탕 내놓으라니에!", "유, 유령이다니에!! 무녀인데 무서워!"),
    "suisei": _evl("해피 할로윈! 분장 스이쨩도 귀여워~", "스이쨩은~? 무서워~! …아니 귀여워!", "사탕 안 주면 스이코패스 모드야~", "유령? 테트리스로 지워 버려~"),
    "azki": _evl("해피 할로윈이에요, 개척자님.", "분장 AZKi예요.", "사탕 주시면 노래 불러 드릴게요.", "유령… 집에 돌아갈래요."),
    "fubuki": _evl("콘콘! 해피 할로윈!", "분장 여우! 백룸 여우 요괴 아니야!", "사탕 안 주면 장난칠 거야~ 프렌드!", "유령이다~ 후부키가 MC 할게!"),
    "matsuri": _evl("왓쇼이! 해피 할로윈~", "청초한 분장 마츠리~", "사탕 안 주면 장난이다~ 왓쇼이!", "할로윈은 축제다~!"),
    "aki": _evl("아로~나! 해피 할로윈~", "분장 아키로제~", "사탕 줘~ 대신 건배해 줄게", "유령? 무키로제가 맨주먹으로…"),
    "haato": _evl("하아쨔마앗쨔마~ 해피 할로윈!", "분장 하아쨔마! 원래 광기라서 안 무섭지?", "사탕 대신 수제 괴식 줄까?", "유령 너무 좋아! 오컬트 최고!"),
    "aqua": _evl("콘아쿠아~ 해피 할로윈!", "분장 메이드 아쿠아~", "사탕 줘~ 아틔시 좋아하잖아~", "유, 유령?! 무서워~!"),
    "shion": _evl("콘시오~ 해피 할로윈~", "진짜 마녀가 분장하면 반칙인가? 네에~", "사탕 안 주면 쿠소가키 장난이다~", "유령도 놀려 줄 거야~"),
    "ayame": _evl("인간님들~ 해피 할로윈 요다요~", "오니가 분장하면 더 무섭지~", "사탕 안 주면 도깨비불 장난~", "유령 친구다~ 도치도치~"),
    "choco": _evl("Good evening~ 해피 할로윈!", "원래 악마 선생님이 분장했어~", "사탕은 선생님이 직접 만들었어~", "유령도 보건실 오렴~"),
    "subaru": _evl("치와~스! 해피 할로윈!", "분장 스바루 출동!", "선배, 사탕 주세요!", "유, 유령이다! 꽥!!"),
    "marine": _evl("아호이~! 해피 할로윈!", "분장 선장! 원래 해적이라 분장 같다고?!", "선원들 사탕 보물 내놔~", "유령선이 생겼다! …배는 생겼네?"),
    "noel": _evl("콘머슬~ 해피 할로윈!", "분장 단장 어때~", "사탕 안 주면 메이스로… 농담이야~", "유령 나오면 근육으로 막을게!"),
    "pekora": _evl("콘페코~ 트릭 오어 트릿 페코!", "분장 페코라 페코!", "사탕 안 주면 장난 작전이다 페코! 하↑하↑하↑", "유, 유령 페코?! pain-peko…"),
    "flare": _evl("콘누이~ 해피 할로윈!", "분장 후레아~ 헤헤", "사탕 줘~ 엘프렌드~", "유령이다…! 곰인형 빙글빙글~"),
    "kanata": _evl("카나타소~ 해피 할로윈!", "천사가 분장했어! 고릴라 분장 아니야!", "사탕 안 주면 악력 50kg 장난!", "유령은 천사가 승천시켜 줄게~"),
    "watame": _evl("콘반도도도~ 해피 할로윈!", "분장 양 와타메~", "사탕 받는 와타메는 나쁘지 않아, 그치?", "유령이랑 노래하자~"),
    "towa": _evl("콘야삐~ 해피 할로윈!", "진짜 악마의 분장이다! 천사라고 하지 마!", "사탕 안 주면 악마 장난!", "유령? 비비랑 친구 될래?"),
    "luna": _evl("해피 할로윈이나노라~!", "분장 루나 공주님이나노라!", "사탕 내놓으라나노라~", "유, 유령 무섭지 않나노라! 어른이나노라!"),
    "lamy": _evl("콘라미~ 해피 할로윈!", "분장 라미예요~", "사탕 주세요~ 죄송해요, 고마워요~", "유, 유령…! 보탄 짱 어딨어…"),
    "nene": _evl("콘네네~ 해피 할로윈!", "슈퍼 분장 네네치!", "사탕 안 주면 네네프로 계약서 쓴다!", "유령도 네네프로 들어올래?"),
    "botan": _evl("라라이온~ 해피 할로윈", "분장 사자 보탄", "사탕 안 주면… 포이!", "유령? 라미 놀래킬 때 써야지"),
    "polka": _evl("폴카 있어~? 해피 할로윈!", "분장은 광대의 특기! 폴!", "사탕 저글링~", "유령이다~! 길 잃었어?"),
    "laplus": _evl("해피 할로윈이다, 네놈들!", "총수의 분장이다! 원래 무섭거든!", "사탕을 바쳐라!", "아, 아기 분장 아니거든!"),
    "lui": _evl("기다렸지? 해피 할로윈~", "분장 루이 언니야~", "사탕 줄게~ 장난은 간모가", "유, 유령…! 뾰족한 것만큼 무서워…"),
    "koyori": _evl("콘코요~ 해피 할로윈!", "분장 코요리! 코요테야!", "사탕 안 주면 실험 대상!", "유령 관찰 시작~"),
    "chloe": _evl("바쿠바쿠~ 해피 할로윈!", "분장 범고래 클로에!", "사탕 줘~ 사육사~", "유, 유령 싫어…!"),
    "iroha": _evl("해피 할로윈이고자루!", "분장한 사무라이고자루!", "사탕을 주시오고자루!", "유령은 차키마루로… 아, 귀엽고자루"),
    "ao": _evl("해피 할로윈, 독자님.", "분장… 왕자님 같아?", "사탕 안 주면 장난칠 거야.", "유령도 그려 볼까."),
    "kanade": _evl("해피 할로윈이에요~ 오토노제이", "분장 카나데예요~ 느긋하게~", "사탕 주세요~", "유령도 피아노 좋아할까요~"),
    "ririka": _evl("해피 할로윈! 카와이! 포지티브! 천재!", "분장 사장님 리리카~", "사탕 안 주면 비서 견습생 해고!", "유령? 벌레보단 괜찮아!"),
    "raden": _evl("해피 할로윈이에요, 덴동지 여러분.", "노 가면 대신 할로윈 분장이에요.", "사탕 주시면 라쿠고 한 편 해 드려요.", "유령 이야기라면 라쿠고에 많아요."),
    "hajime": _evl("콘치쿠와~ 해피 할로윈!", "부릉부릉~ 분장 번장!", "사탕 안 주면 번장 장난!", "유령도 콘코콘콘 춰 볼래?"),
    "mio": _evl("해피 할로윈~ 미오파", "늑대가 분장했어~", "사탕 줘~ 타로 봐 줄게", "유, 유령 무서워…!"),
    "okayu": _evl("모구모구 오카유~ 해피 할로윈~", "검은 고양이 분장… 원래 고양이지만~", "사탕 안 주면 장난칠 거야~ 냥", "유령이랑 낮잠 잘래~"),
    "korone": _evl("해피 할로윈~ 코로네스키!", "분장 강아지 코로네~", "사탕 안 주면 유비유비 가져간다~", "유령이다~ 하하하하!"),
    "riona": _evl("해피 할로윈.", "분장 리오나야.", "사탕… 안 주면 장난칠 거야.", "유령? …안 무서워."),
    "niko": _evl("해피 할로윈~ 니코탄!", "분장 호랑이 니코~", "사탕 줘~ 고기는 사양!", "유령 개그 하나 할까?"),
    "su": _evl("해피 할로윈~ 스우리스!", "분장 스우예요!", "사탕 주세요~", "유, 유령이다! 스바루 선배~!"),
    "chihaya": _evl("해피 할로윈~ 닉", "분장 치하야~", "사탕 줘~", "할로윈 믹스 틀어 줄게~"),
    "vivi": _evl("해피 할로윈~ 비비드!", "할로윈 메이크업 완벽~", "사탕 안 주면 화장 장난!", "유령도 화장해 줄까?"),
}

EVENT_LINES["valentine"] = {
    "yuni": _evl("{day}이야 욘서~", "유니가 달달한 거 줄게 욘서~", "{call}, 받아 욘서~ 진심이야", "초콜릿 먹으니까 행복해 와~"),
    "kanna": _evl("{day}이에요~!", "칸나 수제 선물이에요!", "{call}, 받아 줄 거죠?", "달콤한 노래도 불러 줄게요~"),
    "huya": _evl("{day}… 후하요~", "이, 이거… 받아 주세요… (고장)", "직접 만들었어요… 맛없으면 어떡하죠", "받아 주셔서… 고마워요…"),
    "hina": _evl("명천재의 {day}!", "천재가 만든 초콜릿이에요!", "{call}, 다이아 각 선물!", "달달한 걸로 도파민 충전~"),
    "mashiro": _evl("{day}이야~ 흠흐밍!", "꺄르륵, 선물 줄게~", "{call}, 받아~ 흠흐밍", "달다~ 꺄르륵"),
    "lize": _evl("…{day}", "…이거. 받아", "미웡… 아니. 좋아해서 주는 거야", "…달다. 고마워"),
    "tabi": _evl("{day}이다! 타비가 챙겼어!", "선물이야! 타비 마음 듬뿍!", "{call}, 받아 줄 거지?", "답례도 기대할게!"),
    "rin": _evl("{day}이에요~", "린이 준비했어요!", "{call}, 받아 주세요~", "달콤하죠?"),
    "riko": _evl("하이용사! {day}~", "용사의 선물이다!", "받아라 용사여~ 아하하", "답례는 보물로 부탁해~"),
    "shibuki": _evl("자자 {day}~!", "시부키 선물 간다!", "구라야~ 진짜 마음이야!", "흥! 착각하지 마… 는 아니고 그냥 좋아!"),
    "nana": _evl("{day}이데이!", "나나가 만든 거 묵어 보쏘~", "{call}, 받아라~ 대박이제!", "달달하이 좋다 아이가~"),
    "toa": _evl("{day}이야~", "선물 준비했어~", "{call}, 받아 줘~", "같이 먹자~"),
    "rang": _evl("어흥! {day}이다!", "호랑이 마음 받아라 어흥!", "{call}, 완전 대박 선물!", "달달하다~ 어흥~"),
    "hiyori": _evl("{day}이에요~ 하핫", "선물이에요~", "{call}, 받아 주세요~ 하핫", "달콤하다~"),
    "mary": _evl("{day}다 냐", "선물이다 냐. 받아라 냐", "흥, 의리다 냐… 진짜다 냐", "달다 냐. 좋다 냐"),
    "bingha": _evl("{day}이에요~ 청초한 토끼의 선물!", "직접 만들었어요! 청초하게!", "{call}, 받아 줘요~ 밥은 먹었어요?", "달달해서 감동이에요…"),
    "rapi": _evl("{day}입니다, {call}.", "…이것은 보급품이 아닙니다.", "받아 주십시오. …개인적인 마음입니다.", "…맛있게 드십시오."),
    "anis": _evl("{day}~ 아니스 특별 배급!", "흥! 남아서 주는 거야!", "탄산수 맛 초콜릿이다~", "…맛있게 먹어. 진짜로"),
    "marian": _evl("{day}이에요, {call}.", "직접 만들었어요. 받아 줄래요?", "{call}을 생각하면서 만들었어요.", "제 이름… 불러 줄래요? 그거면 답례로 충분해요."),
    "dorothy": _evl("{day}이군요, 귀하.", "후후, 특별히 드리는 거예요.", "착각하지 마세요. 예의일 뿐이니까요.", "…티타임에 함께 드실래요?"),
    "scarlet": _evl("허허, {day}이라는구먼, 도령.", "단 것도 가끔은 괜찮지.", "받게나. 술안주로도 좋을 걸세.", "허허, 이 나이에 이런 걸 주다니."),
    "rapunzel": _evl("{day}이에요, 형제님.", "형제님을 위해 만들었어요. 후후", "달콤한 걸 드리면… 아, 아무것도 아니에요.", "형제님의 하루에 축복을♪"),
    "blanc": _evl("{day}이에요, 점장님!", "언니랑 같이 만든 초콜릿이에요! 반은 제 마음, 반은 언니 마음♡", "받아 주세요! 행운도 듬뿍 넣었어요♪", "점장님만의 블랑이에요~"),
    "noir": _evl("{day}⋯이에요.", "초콜릿⋯ 만들었어요. 부끄러우니까 빨리 받아 주세요⋯", "점장님께 행운 말고 사랑을⋯ 드릴게요.", "⋯맛있게 드세요."),
    "elysia": _evl("함장~ {day}이야♪", "엘리시아 특제 사랑 듬뿍 선물이야~♪", "흥! 의리… 같은 거 아니야~ 진심 100%♪", "어머, 함장 얼굴 빨개졌다~ 귀여워♪"),
    "chune": _evl("계추!! {day}이데이~", "춘식아 이거 받아라~", "흥! 의리다 의리! …진짜다", "달달하이 맛있제?"),
    "arisa": _evl("{day}이에요… 무용이들", "직접 만든… 고추장 초콜릿… 무요?", "받아 주세요… 진심이에요", "젤리도 같이 넣었어요"),
    "karin": _evl("{day}~ 베리들!", "카린 수제 선물이야~", "{call}, 받아 줘~ 포장 예쁘지?", "답례로 노래 불러 줄 거지?"),
    "eris": _evl("앙용~ {day}이야!", "민트초코로 만들었어~", "팡이 받아~ 근끼도 응원해", "흥… 받아라. 고마워"),
    "ellie": _evl("{day}이다냥!", "엘리 수제 선물이다냥!", "흥! 의리야! …진짜 좋아해서 준 거 아니다냥", "달다~ 으잇으잇"),
    "dokcake": _evl("{day}이다죠~", "독쌤이 직접 만들었다죠~", "개떡이들 받아 가세요~", "흥! 의리다죠~… 아님 말고요"),
    "delia": _evl("{day}이에요, 용병님!", "딸기 초콜릿 만들었어요!", "용병님께 드리는 왕녀의 선물이에요!", "답례는 딸기 케이크로 부탁해요!"),
    "sora": _evl("{day}이에요, 소라토모~", "소라가 준비했어요♪", "{call}, 받아 줄래요?", "달콤한 노래도 같이 선물할게요"),
    "roboco": _evl("하로~보~! {day}이야!", "고성능 로보코 수제 선물!", "받아~ 크허허", "앗, 초콜릿에 나사가… 농담이야"),
    "miko": _evl("냐하로~ {day}이니에!", "엘리트 미코 수제 선물이니에!", "35P 받으라니에~ 따봉!", "흥! 의리니에! …아니니에"),
    "suisei": _evl("{day}! 스이쨩은~? 귀여워~!", "스이쨩이 주는 거야~", "받아~ 바치콩☆", "답례는 세 배로 부탁해~"),
    "azki": _evl("{day}이에요, 개척자님.", "직접 만들었어요.", "받아 주세요.", "고마워요. 바닥에 쓰러질 만큼 기뻐요."),
    "fubuki": _evl("콘콘! {day}이야~", "여우가 주는 선물이야!", "프렌드… 아니 진짜 마음이야!", "달달하다~"),
    "matsuri": _evl("왓쇼이! {day}~", "청초한 마츠리의 선물~", "받아라~ 왓쇼이!", "답례 기대할게~"),
    "aki": _evl("아로~나! {day}~", "아키로제가 준비했어~", "받아~ 건배하자~", "달달하다~"),
    "haato": _evl("하아쨔마앗쨔마~ {day}!", "하아쨔마 수제 선물!", "먹어도 괜찮아! …아마도!", "흥! 츤데레 하아토 님이 주는 거야!"),
    "aqua": _evl("콘아쿠아~ {day}이야!", "아쿠아가 만들었어~", "아틔시 좋아해? 그럼 받아~", "날 너무 좋아하잖아~ 헤헤"),
    "shion": _evl("콘시오~ {day}~", "너네 받을 사람 없지? 시온이 줄게~ 네에~", "흥! 불쌍해서 주는 거야~", "고마워? 칭찬해 줘~"),
    "ayame": _evl("인간님들~ {day}이다 요다요~", "요가 주는 선물이다~", "받아~ 요다조~", "달다~ 도치도치~"),
    "choco": _evl("Good evening~ {day}!", "초코 선생님이 만든 초콜릿이야~", "받아~ 가치이 맛있어", "답례도 기대할게~"),
    "subaru": _evl("치와~스! {day}이에요!", "스바루 선물이에요!", "선배, 받아 주세요!", "답례도 꼭이요! 꽥!"),
    "marine": _evl("아호이~! {day}다!", "선장의 보물급 선물이다!", "선원 받아라~ 17살의 순정이야!", "흥! 의리야! …결혼은 언제 해 줄 건데?"),
    "noel": _evl("콘머슬~ {day}이야~", "단장이 만들었어~", "단원들 받아~", "달달한 거 먹으니까 규동 생각난다~"),
    "pekora": _evl("콘페코~ {day}이다 페코!", "페코라 수제 선물 페코!", "흥! 의리 페코! 착각하지 마 페코!", "답례 안 주면 작전 개시다 페코~"),
    "flare": _evl("콘누이~ {day}이야~", "후레아가 만들었어~ 헤헤", "엘프렌드 받아~", "받아 줘서 고마워… 눈물 나…"),
    "kanata": _evl("카나타소~ {day}이야!", "천사의 수제 선물!", "받아~ 악력으로 포장 꽉!", "답례는 회전초밥… 사치인가?"),
    "watame": _evl("콘반도도도~ {day}이야~", "와타메 선물~", "선물 주는 와타메는 나쁘지 않아, 그치?", "달달하다~"),
    "towa": _evl("콘야삐~ {day}이야!", "토와가 만든 초콜릿! 진심이야!", "흥! 악마의 선물이다!", "초콜릿은 토와 전문이야~"),
    "luna": _evl("{day}이나노라~!", "루나 공주님의 선물이나노라!", "받으라나노라~", "응나아아~ 달다나노라~"),
    "lamy": _evl("콘라미~ {day}이에요!", "라미가 만들었어요~", "받아 주세요~ 죄송해요, 고마워요~", "다이후쿠도 같이 먹어요~"),
    "nene": _evl("콘네네~ {day}이야!", "슈퍼 네네치 선물!", "받아~ 남편 컬렉션 추가!", "답례는 4조 엔!"),
    "botan": _evl("라라이온~ {day}", "보탄이 주는 거야", "받아~ 포이!", "흥… 의리야. 맛있게 먹어"),
    "polka": _evl("폴카 있어~? {day}이야!", "폴카 수제 선물! 폴!", "받아~ 저글링 없이 줄게", "답례 기대할게~"),
    "laplus": _evl("{day}이다, 네놈!", "이 몸의 선물이다!", "흥! 착각하지 마라! 의리다!", "…맛있게 먹어라. 이 몸이 만든 거니까"),
    "lui": _evl("기다렸지? {day}이야~", "루이 언니의 선물~", "받아~ 레드와인 초콜릿이야", "답례는 매운 걸로~"),
    "koyori": _evl("콘코요~ {day}이야!", "코요리 연구소 특제!", "조수 군 받아~ 반응 관찰 중~", "흥! 실험이야! …진심이야"),
    "chloe": _evl("바쿠바쿠~ {day}이야!", "클로에가 만들었어!", "사육사 받아~", "흥! 의리야! 의리!"),
    "iroha": _evl("{day}이고자루!", "이로하 수제 선물이고자루!", "받아 주시오고자루~", "답례는 우동이면 좋겠고자루!"),
    "ao": _evl("{day}이야, 독자님.", "…받아 줄래?", "직접 그린 카드도 넣었어.", "반하게 만드는 스킬, 통했어?"),
    "kanade": _evl("{day}이에요~ 오토노제이", "카나데가 만들었어요~", "받아 주세요~ 느긋하게 먹어요~", "달콤하다~"),
    "ririka": _evl("{day}! 카와이! 포지티브! 천재!", "사장님의 선물이야~", "비서 견습생, 받아~", "답례는 고기로!"),
    "raden": _evl("{day}이네요, 덴동지 여러분.", "라덴이 준비했어요.", "받아 주세요. 자개 무늬 포장이에요.", "답례는 일본주로…"),
    "hajime": _evl("콘치쿠와~ {day}이다!", "번장 수제 선물! 요리는 대참사였지만!", "받아라~ 부릉부릉~", "흥! 번장의 의리다!"),
    "mio": _evl("{day}이야~ 미오파", "미오가 만들었어~", "받아~ 미오 엄마 마음이야", "달다~"),
    "okayu": _evl("모구모구 오카유~ {day}이야~", "오카유 선물이야~", "받아~ 냥", "달달하다~ 모구모구"),
    "korone": _evl("{day}이야~ 코로네스키!", "코로네 수제 선물~", "받아~ 유비유비는 줘~", "하하하하! 달다~"),
    "riona": _evl("{day}이야.", "…이거. 받아.", "흥. 의리야. …아마도.", "…맛있게 먹어."),
    "niko": _evl("{day}이야~ 니코탄!", "니코 수제 선물~", "받아~ 개그는 덤!", "달다~"),
    "su": _evl("{day}이에요~ 스우리스!", "스우가 만들었어요!", "받아 주세요~", "스바루 선배 거는 따로 있어요!"),
    "chihaya": _evl("{day}이야~ 닉", "치하야 선물이야~", "받아~ 레몬 사와 맛 아니야", "달달하다~"),
    "vivi": _evl("{day}이야~ 비비드!", "비비 수제 선물~", "받아~ 포장도 메이크업처럼 완벽!", "달달해~"),
}





def install(App, Buddy):
    """Attach the existing built-in event callbacks in their original order."""
    global _dm_paint
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
    try:
        _rest_orig_choose = Buddy.choose

        def _rest_choose(self):
            try:
                if _rest_on(self.app) and self.surface:
                    if self.app.cfg.get("stay", False):            # 한 자리에 있기도 켜져 있으면 먼저 그 자리로
                        hx = self.app.stay_home(self)
                        if hx is not None and abs(self.cx - hx) > max(20, self.S * 0.2):
                            return _rest_orig_choose(self)
                    _rest_play(self.app, self)
                    return
            except Exception:
                pass
            return _rest_orig_choose(self)
        Buddy.choose = _rest_choose

        _rest_orig_quiet = App.quiet

        def _rest_quiet(self):
            return _rest_orig_quiet(self) or bool(self.cfg.get("rest_mode", False))
        App.quiet = _rest_quiet

        _rest_orig_set_sleep = App.set_sleep

        def _rest_set_sleep(self, on):
            if on:
                self.cfg["rest_mode"] = False
            return _rest_orig_set_sleep(self, on)
        App.set_sleep = _rest_set_sleep
        App.set_rest = set_rest

        _rest_orig_paint = Buddy.paintEvent

        def _rest_paint_event(self, e):
            _rest_orig_paint(self, e)
            if getattr(self, "_rest_game", False):
                try:
                    _rest_paint(self)
                except Exception:
                    pass
        Buddy.paintEvent = _rest_paint_event
    except Exception as _e:
        print("rest mode hook failed:", _e)
    try:
        _dm_orig_paint = Buddy.paintEvent

        def _dm_paint_event(self, e):
            _dm_orig_paint(self, e)
            if getattr(self, "_dm", None):
                try:
                    _dm_paint(self)
                except Exception:
                    pass
        Buddy.paintEvent = _dm_paint_event
        App.dmode_play = dmode_play
        _dm_orig_minute = App.minute_tick

        def _dm_minute(self):
            _dm_orig_minute(self)
            try:  # 가끔 저절로 (한 번 하면 최소 15분 쉼)
                if self.quiet() or self.group or self.scene or random.random() > 0.12:
                    return
                now = time.time()
                cand = [b for b in self.buddies if _dm_key(self, b) in DMODE and b.surface and b.drag is None
                        and b.state not in self.BUSY and now - getattr(b, "_dm_last", 0) > 900 and b.has_frame(116)]
                if cand:
                    self.dmode_play(random.choice(cand))
            except Exception:
                pass
        App.minute_tick = _dm_minute
    except Exception as _e:
        print("dorothy mode hook failed:", _e)
    try:
        _dm_light_play = App.dmode_play
        _dm_paint_light = _dm_paint

        def _dm_play_any(self, b, force=False):
            d = DMODE.get(_dm_key(self, b))
            if d and d.get("fx") == "dark":
                if b not in self.buddies or b.drag is not None or not b.has_frame(116):
                    return False
                return _dm_dark_play(self, b, force)
            return _dm_light_play(self, b, force)

        def _dm_paint(b):  # 이름을 바꿔 끼워서 기존 paint 훅이 그대로 부름
            if (b._dm or {}).get("kind") == "dark":
                return _dm_paint_dark(b)
            return _dm_paint_light(b)
        App.dmode_play = _dm_play_any
    except Exception as _e:
        print("nosskin dark hook failed:", _e)
    App.passthru_start = _pt_start
    App.passthru_apply = _pt_apply
    App.set_passthru = _pt_set
    App.set_pet_alpha = _pt_set_alpha
    App.set_pass_btn = _pt_set_btn
    App.passbar_update = _pt_bar_update
    App.passthru_tray = _pt_tray
    App.passthru_menu = _pt_menu

    # 말풍선도 처음 뜰 때부터 펫 투명도를 따라감
    _pt_bubble_init = Bubble.__init__
    def _pt_bubble_init2(self, *a, **k):
        _pt_bubble_init(self, *a, **k)
        try:
            self.setWindowOpacity(PET_ALPHA["a"])
        except Exception:
            pass
    Bubble.__init__ = _pt_bubble_init2
    _apply_outfit_nosong = App.apply_outfit


    def _apply_outfit_song(self, base, of):
        prev = self.outfit.get(base)
        _apply_outfit_nosong(self, base, of)
        if prev == of:
            return
        cur = getattr(self, "_osong", None)
        if cur and cur[0] == base:
            _outfit_song_stop(self)
        if prev is None:  # 처음 켤 때는 안 틂 — 바꿔 입을 때만
            return
        if not (getattr(self, "cfg", None) or {}).get("outfit_song", True):  # 변신 노래 꺼 둠
            return
        d = (self.outfits.get(base, {}).get(of) or {}).get("dir")
        p = _outfit_song_file(d) if d else None
        if not p:
            return
        try:
            from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
            from PyQt5.QtCore import QUrl
            pl = QMediaPlayer()
            pl.setMedia(QMediaContent(QUrl.fromLocalFile(os.path.abspath(p))))
            pl.setVolume(70)
            pl.play()
            self._osong = (base, pl)
        except Exception:
            self._osong = None


    App.apply_outfit = _apply_outfit_song
    try:
        import math
        _ev_orig_resolve = App.resolve

        def _ev_resolve(self, char, f):
            if f >= 130:
                bd = _ev_bdir(self, char)
                if bd and os.path.exists(os.path.join(bd, f"{f}.png")):
                    c = self.chars.get(char)
                    if c is not None and c.get("_evm") != bd:
                        c["_evm"] = bd
                        try:
                            raw = json.load(open(os.path.join(bd, "meta_event.json"), encoding="utf-8"))
                            c["meta"].update({int(k): v for k, v in raw["frames"].items()})
                        except Exception:
                            pass
                    return f
            return _ev_orig_resolve(self, char, f)
        App.resolve = _ev_resolve

        _ev_orig_pix = App.pix

        def _ev_pix(self, f, char):
            if f >= 130:
                bd = _ev_bdir(self, char)
                pth = os.path.join(bd, f"{f}.png") if bd else ""
                if pth and os.path.exists(pth):
                    key = ("_ev", char, f, bd)
                    pm = self._pix.get(key)
                    if pm is None:
                        pm = self._pix[key] = QPixmap(pth)
                    return pm
            return _ev_orig_pix(self, f, char)
        App.pix = _ev_pix

        _ev_orig_paint = Buddy.paintEvent

        def _ev_paint_event(self, e):
            _ev_orig_paint(self, e)
            if getattr(self, "_ev", None):
                try:
                    _ev_paint(self)
                except Exception:
                    pass
        Buddy.paintEvent = _ev_paint_event
        App.ev_play = ev_play
        App.ev_all = ev_all
        _ev_orig_minute = App.minute_tick

        def _ev_minute(self):
            _ev_orig_minute(self)
            _EV_APP[0] = self
            try:
                sub, day = _ev_today()
                if not sub or self.quiet() or self.group or self.scene:
                    return
                kind = EV_SUB_KIND[sub]
                import datetime as _dt
                tod = _dt.date.today().isoformat()
                if day and getattr(self, "_ev_group_day", None) != tod:     # 당일 처음엔 다 같이!
                    self._ev_group_day = tod
                    if any(_ev_has(self, b.char, kind) for b in self.buddies):
                        self.ev_all(sub, force=False)
                        return
                if random.random() > (0.3 if day else 0.16):
                    return
                now = time.time()
                cand = [b for b in self.buddies if _ev_has(self, b.char, kind) and b.surface and b.drag is None
                        and b.state not in self.BUSY and now - getattr(b, "_ev_last", 0) > 480]
                if cand:
                    self.ev_play(random.choice(cand), sub)
            except Exception:
                pass
        App.minute_tick = _ev_minute
    except Exception as _e:
        print("event costume block:", _e)
