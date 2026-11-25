"""Transparent Qt overlays and reusable visual effects for pets."""

import math

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QWidget


PARTICLE_EFFECTS = {
    "seal": (7, 1.7, 3.0, "orb"), "fairy": (8, 1.2, 2.8, "orb"),
    "freeze": (11, 2.4, 4.1, "diamond"), "petal": (11, 4.2, 3.1, "petal"),
    "books": (7, 2.0, 2.7, "diamond"), "sun": (15, math.tau, 3.0, "orb"),
    "clock": (11, 1.8, 4.4, "diamond"), "scarlet": (9, 1.45, 3.8, "orb"),
}
LIGHT_EFFECTS = frozenset(("spark", "moon", "slash"))
EFFECT_PRESETS = PARTICLE_EFFECTS.keys() | LIGHT_EFFECTS


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


def draw_particles(p, effect, palette, age):
    from PyQt5.QtCore import QPointF
    from PyQt5.QtGui import QColor, QPolygonF
    count, spread, speed, shape = PARTICLE_EFFECTS[effect]
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


class PetEffectOverlay(QWidget):
    """Paint effects over nearby pets without intercepting clicks."""

    def __init__(self, mem, on_top):
        super().__init__()
        flags = Qt.FramelessWindowHint | Qt.Tool | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus
        self.setWindowFlags(flags | (Qt.WindowStaysOnTopHint if on_top else Qt.WindowFlags()))
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.mem = mem
        extent = max(b.S for b in mem)
        screen = mem[0].scr()
        left = max(screen.left(), int(min(b.cx for b in mem) - extent * 2.4))
        right = min(screen.right() + 1, int(max(b.cx for b in mem) + extent * 2.4))
        top = max(screen.top(), int(min(b.fy for b in mem) - extent * 1.8))
        bottom = min(screen.bottom() + 1, int(max(b.fy for b in mem) + extent * 1.8))
        self.setGeometry(left, top, max(1, right - left), max(1, bottom - top))
        self.show()

    def painter(self):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        return painter

    def paint_spell(self, painter, pet, target, preset, palette, age, direction):
        painter.save()
        painter.translate(pet.cx - self.x() + direction * pet.S * 0.2,
                          pet.fy + pet.S * 0.57 - self.y())
        painter.scale(direction * pet.S / 100, pet.S / 100)
        painter.setOpacity(min(1, (age + 1) / 7, (78 - age) / 19))
        if preset in LIGHT_EFFECTS:
            reach = 180 if target is None else max(28, abs(target.cx - pet.cx) * 100 / pet.S - 55)
            draw_light(painter, preset, palette, age, reach)
        else:
            draw_particles(painter, preset, palette, age)
        painter.restore()


class PluginEffectOverlay(PetEffectOverlay):
    def __init__(self, pets, on_top):
        self.tick = 0
        self.bursts = []
        super().__init__(pets, on_top)

    def show_effect(self, source, target, effect, start):
        self.bursts.append((source, target, effect, start))

    def advance(self, tick):
        self.tick = tick
        self.bursts[:] = [burst for burst in self.bursts if tick - burst[3] < burst[2].ticks]
        self.update()

    def paintEvent(self, event):
        painter = self.painter()
        for source, target, effect, start in self.bursts:
            age = (self.tick - start) * 78 / effect.ticks
            direction = (source.face or 1) if target is None else (1 if source.cx <= target.cx else -1)
            self.paint_spell(painter, source, target, effect.preset, effect.colors, age, direction)
        painter.end()
