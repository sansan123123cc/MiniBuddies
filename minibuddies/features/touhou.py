"""Scarlet Devil Mansion guard and Touhou spell-card interactions."""

import math
import random
import time
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QWidget


TOUHOU_MANSION = ("meiling", "koakuma", "patchouli", "sakuya", "remilia", "flandre")
TOUHOU_CAST_FRAMES = (200, 201, 202)
TOUHOU_GUARD_FRAME = 203
TOUHOU_CAST_TIMES = (22, 78)
TOUHOU_SPELLS = {
    "reimu": ("영부 「몽상봉인」", "seal", ("#ff7890", "#f9d16c", "#97c8fd", "#c999f9")),
    "marisa": ("연부 「마스터 스파크」", "spark", ("#cc93ff", "#ffdb68", "#fff7db")),
    "rumia": ("월부 「문라이트 레이」", "moon", ("#7661cf", "#c4c7ff")),
    "daiyousei": ("요정의 탄막", "fairy", ("#9de9b0", "#bdf8ed", "#f0ffce")),
    "cirno": ("동부 「퍼펙트 프리즈」", "freeze", ("#87bbff", "#b7a0ff", "#d9f8ff")),
    "meiling": ("화부 「방화현란」", "petal", ("#f58aba", "#70d7ad", "#fde280", "#9aa9fa")),
    "koakuma": ("도서관의 탄막", "books", ("#c490ee", "#f08bac", "#855ec7")),
    "patchouli": ("일부 「로열 플레어」", "sun", ("#f69a4d", "#f8cf58", "#ffefb1")),
    "sakuya": ("환세 「더 월드」", "clock", ("#bbdaef", "#eaf3fb", "#8aa1cb")),
    "remilia": ("홍부 「스칼렛 슛」", "scarlet", ("#e93d65", "#ff7990", "#ffc2cd")),
    "flandre": ("금기 「레바테인」", "slash", ("#ef3961", "#ffbf64")),
}
TOUHOU_PARTICLES = {
    "seal": (7, 1.7, 3.0, "orb"), "fairy": (8, 1.2, 2.8, "orb"),
    "freeze": (11, 2.4, 4.1, "diamond"), "petal": (11, 4.2, 3.1, "petal"),
    "books": (7, 2.0, 2.7, "diamond"), "sun": (15, math.tau, 3.0, "orb"),
    "clock": (11, 1.8, 4.4, "diamond"), "scarlet": (9, 1.45, 3.8, "orb"),
}

class TouhouDanmaku(QWidget):
    """두 펫 사이에서만 그리는 클릭 통과 탄막. 게임 판정과는 연결하지 않는다."""
    def __init__(self, mem, on_top):
        super().__init__()
        flags = Qt.FramelessWindowHint | Qt.Tool | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus
        self.setWindowFlags(flags | (Qt.WindowStaysOnTopHint if on_top else Qt.WindowFlags()))
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.mem = mem
        self.t = 0
        extent = max(b.S for b in mem)
        screen = mem[0].scr()
        left = max(screen.left(), int(min(b.cx for b in mem) - extent * 2.4))
        right = min(screen.right() + 1, int(max(b.cx for b in mem) + extent * 2.4))
        top = max(screen.top(), int(min(b.fy for b in mem) - extent * 1.8))
        bottom = min(screen.bottom() + 1, int(max(b.fy for b in mem) + extent * 1.8))
        self.setGeometry(left, top, max(1, right - left), max(1, bottom - top))
        self.show()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        for index, b in enumerate(self.mem):
            age = self.t - TOUHOU_CAST_TIMES[index]
            if not 0 <= age < 78:
                continue
            _, effect, palette = TOUHOU_SPELLS[b.char]
            opacity = min(1, (age + 1) / 7, (78 - age) / 19)
            p.save()
            p.translate(b.cx - self.x() + b.face * b.S * 0.2, b.fy + b.S * 0.57 - self.y())
            p.scale(b.face * b.S / 100, b.S / 100)
            p.setOpacity(opacity)
            if effect in ("spark", "moon", "slash"):
                reach = max(28, abs(self.mem[1 - index].cx - b.cx) * 100 / b.S - 55)
                self.draw_light(p, effect, palette, age, reach)
            else:
                self.draw_particles(p, effect, palette, age)
            p.restore()

    @staticmethod
    def draw_light(p, effect, palette, age, reach=180):
        from PyQt5.QtCore import QPointF
        from PyQt5.QtGui import QColor, QPainterPath, QPen
        length = min(180, reach) * min(1, (age + 1) / 15)
        if effect == "slash":
            p.rotate(-52 + 90 * min(1, age / 40))
            path = QPainterPath(QPointF(0, 6))
            path.quadTo(QPointF(length * 0.3, -length * 0.68), QPointF(length * 0.8, -length * 0.34))
            for color, width in zip(palette, (13, 5)):
                p.setPen(QPen(QColor(color), width, Qt.SolidLine, Qt.RoundCap))
                p.drawPath(path)
            return
        for side in (-1, 1) if effect == "moon" else (0,):
            p.save()
            p.rotate(side * (9 + min(age, 36) * 0.28))
            widths = (5.5, 2) if effect == "moon" else (22, 12, 4)
            for color, width in zip(palette, widths):
                p.setPen(QPen(QColor(color), width, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(QPointF(2, 0), QPointF(length, 0))
            p.restore()

    @staticmethod
    def draw_particles(p, effect, palette, age):
        from PyQt5.QtCore import QPointF
        from PyQt5.QtGui import QColor, QPolygonF
        count, spread, speed, shape = TOUHOU_PARTICLES[effect]
        p.setPen(Qt.NoPen)
        for wave, delay in enumerate((0, 17, 34)):
            elapsed = age - delay
            if not 0 <= elapsed < 45:
                continue
            travel = elapsed
            if effect in ("freeze", "clock"):
                travel -= min(14, max(0, elapsed - 12))
            for i in range(count):
                ratio = i / (count - 1)
                angle = (ratio - 0.5) * spread + (wave % 2 - 0.5) * 0.13
                if effect == "freeze":
                    angle += (ratio - 0.5) * min(0.5, max(0, elapsed - 26) * 0.035)
                elif effect in ("petal", "sun"):
                    angle += wave * 0.24 + elapsed * 0.015
                distance = 8 + travel * speed
                x = distance * math.cos(angle)
                y = distance * math.sin(angle) + math.sin(travel / 8 + i) * 6
                if effect == "seal":
                    orbit = i * math.tau / count + elapsed * 0.16
                    x = 12 + travel * speed + math.cos(orbit) * 13
                    y = math.sin(orbit) * (8 + travel * 0.42)
                color = QColor(palette[(i + wave) % len(palette)])
                if effect == "freeze" and elapsed >= 12:
                    color = QColor("#c8f2ff")
                color.setAlphaF(min(1, (45 - elapsed) / 12))
                p.setBrush(color)
                width = 5 if effect in ("seal", "scarlet") else 3.5
                if shape == "diamond":
                    dx, dy = math.cos(angle), math.sin(angle)
                    p.drawPolygon(QPolygonF([QPointF(x + dx * width * 2, y + dy * width * 2),
                                             QPointF(x + dy * 2.4, y - dx * 2.4),
                                             QPointF(x - dx * width * 2, y - dy * width * 2),
                                             QPointF(x - dy * 2.4, y + dx * 2.4)]))
                else:
                    p.drawEllipse(QPointF(x, y), width, width * (0.62 if shape == "petal" else 1))

def touhou_members(self, kind, who=None):
    """같은 모니터·바닥에서 가까이 만난, 전용 그림이 있는 펫만 고른다."""
    if self.group or self.scene or self.quiet():
        return []
    guard = kind == "touhou_guard"
    allowed = TOUHOU_MANSION if guard else TOUHOU_SPELLS
    frames = (TOUHOU_GUARD_FRAME,) if guard else TOUHOU_CAST_FRAMES
    ready = {b for b in self.buddies if b.char in allowed and b.drag is None
             and b.isVisible() and all(b.has_frame(frame) for frame in frames)}
    if len(ready) < 2:
        return []
    for a, b in self.pairs(near=340):
        screen = a.scr()
        if a not in ready or b not in ready or b.scr() != screen or (who and who not in (a, b)):
            continue
        max_size = max(a.S, b.S)
        if abs(a.cx - b.cx) > max_size * 2.3:
            continue
        lo = max(screen.left(), a.surface[0]) + max_size / 2
        hi = min(screen.right(), a.surface[2]) - max_size / 2
        if not guard:
            if hi - lo >= max_size * 1.15:
                return sorted((a, b), key=lambda pet: pet.cx)
            continue
        if hi <= lo:
            continue
        members = {a.char: a, b.char: b}
        for friend in self.buddies:
            if friend in ready and friend.surface == a.surface and friend.scr() == screen \
                    and friend.state in self.DUO_FREE \
                    and friend.goal is None and abs(friend.cx - a.cx) <= max_size * 3:
                members.setdefault(friend.char, friend)
        order = [members[char] for char in TOUHOU_MANSION if char in members]
        if max(pet.S for pet in order) >= min(screen.right(), a.surface[2]) - max(screen.left(), a.surface[0]):
            continue
        lift = sum(pet.S * (pet.fbottom(TOUHOU_GUARD_FRAME) - pet.ftop(TOUHOU_GUARD_FRAME))
                   for pet in order)
        if a.surface[1] - lift >= screen.top() + 4:
            return order
    return []

def touhou_play(self, kind, who=None):
    mem = self.touhou_members(kind, who)
    if not mem:
        return False
    screen = mem[0].scr()
    floor = mem[0].surface
    size = max(b.S for b in mem)
    lo = max(screen.left(), floor[0]) + size / 2
    hi = min(screen.right(), floor[2]) - size / 2
    gap = min(size * 1.8, hi - lo) if kind == "touhou_duel" else 0
    cx = sum(b.cx for b in mem) / len(mem)
    cx = max(lo + gap / 2, min(hi - gap / 2, cx))
    for i, b in enumerate(mem):
        b.goal = None; b.vx = 0
        b.gx = cx + (i - 0.5) * gap
        b.set("gather", 99999)
    self.group = {"kind": kind, "mem": mem, "cx": cx, "phase": "gather", "t": 0, "t0": 0,
                  "floor": floor}
    self.touhou_until = time.monotonic() + 40
    return True

def touhou_duel_tick(self, g, mem, t):
    if t > 160:
        self.group_break()
        return
    for i, b in enumerate(mem):
        age = t - TOUHOU_CAST_TIMES[i]
        charge, cast, recover = TOUHOU_CAST_FRAMES
        frame = charge if -22 <= age < 0 else cast if 0 <= age < 22 else recover if 22 <= age < 49 else 0
        b.gframe = [frame]
        b.fy = b.surface[1] - b.S * b.fbottom(frame)
        if age == 0:
            b.say(TOUHOU_SPELLS[b.char][0], 82)
    effect = g["effect"]
    effect.t = t
    effect.update()


def try_automatic(app):
    if (app.group or app.scene or app.quiet() or not app.cfg.get("auto_group", True)
            or len(TOUHOU_SPELLS.keys() & set(app.team)) < 2
            or time.monotonic() < getattr(app, "touhou_until", 0)):
        return False
    chance = random.random()
    if chance < 0.07 and app.touhou_play("touhou_guard"):
        return True
    return chance < 0.14 and app.touhou_play("touhou_duel")


def should_break(app, group, members):
    if group["kind"] not in ("touhou_duel", "touhou_guard"):
        return False
    return app.quiet() or app.scene or len(members) != len(group["mem"]) or any(
        pet.drag is not None or not pet.isVisible() or pet.surface != group["floor"]
        or pet.state not in ("gather", "group", "tower") or not pet.surface_alive() for pet in members
    )


def close_group(group):
    if group["kind"] == "touhou_duel" and "effect" in group:
        group["effect"].close()


def restore_pet(group, pet):
    if group["kind"] == "touhou_duel" and pet.surface and pet.drag is None:
        pet.stand_on(pet.surface)
        pet.vx = 0


def start_group(app, group, members):
    if group["kind"] == "touhou_guard":
        y = group["floor"][1]
        group["order"] = members[:]
        for pet in members:
            pet.set("tower")
            pet.face = 1
            pet.gframe = [TOUHOU_GUARD_FRAME]
            pet.fx = group["cx"] - pet.S / 2
            pet.fy = y - pet.S * pet.fbottom(TOUHOU_GUARD_FRAME)
            y = pet.fy + pet.S * (pet.ftop(TOUHOU_GUARD_FRAME) + 0.11)
            pet.raise_()
        return True
    if group["kind"] == "touhou_duel":
        for i, pet in enumerate(members):
            pet.face = 1 if i == 0 else -1
            pet.vx = 0
            pet.gframe = [0]
        group["effect"] = TouhouDanmaku(members, app.on_top)
        app.touhou_duel_tick(group, members, 0)
        return True
    return False


def advance_group(app, group, members, ticks):
    if group["kind"] == "touhou_duel":
        app.touhou_duel_tick(group, members, ticks)
        return True
    if group["kind"] == "touhou_guard":
        app.tower_tick(group, ticks, recenter=True)
        return True
    return False


def add_group_menu(app, menu, pet):
    for label, kind in (("카리스마 가드 타워", "touhou_guard"), ("스펠카드 탄막놀이", "touhou_duel")):
        if app.touhou_members(kind, pet):
            item = menu.addAction(label)
            item.triggered.connect(lambda _checked, k=kind: app.touhou_play(k, pet))


def add_pet_menu(app, menu, pet):
    if pet.char not in TOUHOU_MANSION or not pet.has_frame(TOUHOU_GUARD_FRAME):
        return

    def guard():
        app.ground(pet)
        pet.play_seq([(TOUHOU_GUARD_FRAME, 120)])

    menu.addAction("카리스마 가드", guard)
