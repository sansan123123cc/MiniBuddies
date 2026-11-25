"""Transparent Qt overlays and reusable visual effects for pets."""

from dataclasses import dataclass
import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QWidget


PARTICLE_EFFECTS = {
    "seal": (7, 1.7, 3.0, "orb"), "fairy": (8, 1.2, 2.8, "orb"),
    "freeze": (11, 2.4, 4.1, "diamond"), "petal": (11, 4.2, 3.1, "petal"),
    "books": (7, 2.0, 2.7, "diamond"), "sun": (15, math.tau, 3.0, "orb"),
    "clock": (11, 1.8, 4.4, "diamond"), "scarlet": (9, 1.45, 3.8, "orb"),
}
LIGHT_EFFECTS = frozenset(("spark", "moon", "slash"))
EFFECT_PRESETS = PARTICLE_EFFECTS.keys() | LIGHT_EFFECTS


@dataclass(frozen=True)
class Keyframe:
    at: int
    x: int = 0
    y: int = 0
    scale: int = 100
    rotation: int = 0
    opacity: int = 100


@dataclass(frozen=True)
class EffectLayer:
    kind: str
    start: int
    end: int
    keyframes: tuple
    anchor: str = "source"
    blend: str = "normal"
    colors: tuple = ()
    size: int = 5
    shape: str = "orb"
    count: int = 8
    spread: int = 90
    speed: float = 3.0
    waves: int = 3
    interval: int = 17
    length: int = 180
    files: tuple = ()
    images: tuple = ()


@dataclass(frozen=True)
class EffectDesign:
    name: str
    layers: tuple


def draw_light(p, effect, palette, age, reach=180, thickness=1.0):
    from PyQt5.QtCore import QPointF
    from PyQt5.QtGui import QColor, QPainterPath, QPen
    length = min(180, reach) * min(1, (age + 1) / 15)
    if effect == "slash":
        p.rotate(-52 + 90 * min(1, age / 40))
        path = QPainterPath(QPointF(0, 6))
        path.quadTo(QPointF(length * 0.3, -length * 0.68), QPointF(length * 0.8, -length * 0.34))
        for color, width in zip(palette, (13, 5)):
            p.setPen(QPen(QColor(color), width * thickness, Qt.SolidLine, Qt.RoundCap))
            p.drawPath(path)
        return
    for side in (-1, 1) if effect == "moon" else (0,):
        p.save()
        p.rotate(side * (9 + min(age, 36) * 0.28))
        widths = (5.5, 2) if effect == "moon" else (22, 12, 4)
        for color, width in zip(palette, widths):
            p.setPen(QPen(QColor(color), width * thickness, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(2, 0), QPointF(length, 0))
        p.restore()


def draw_particles(p, effect, palette, age, layer=None):
    from PyQt5.QtCore import QPointF
    from PyQt5.QtGui import QColor, QPolygonF
    if layer is None:
        count, spread, speed, shape = PARTICLE_EFFECTS[effect]
        width = 5 if effect in ("seal", "scarlet") else 3.5
        waves, interval = 3, 17
    else:
        count, spread, speed, shape = layer.count, math.radians(layer.spread), layer.speed, layer.shape
        width, waves, interval = layer.size, layer.waves, layer.interval
    divisor = count if layer and layer.spread == 360 else count - 1
    p.setPen(Qt.NoPen)
    for wave in range(waves):
        elapsed = age - wave * interval
        if not 0 <= elapsed < 45:
            continue
        travel = elapsed
        if effect in ("freeze", "clock"):
            travel -= min(14, max(0, elapsed - 12))
        for i in range(count):
            ratio = i / divisor if count > 1 else 0.5
            angle = (ratio - 0.5) * spread
            if layer is None:
                angle += (wave % 2 - 0.5) * 0.13
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
            if shape == "diamond":
                dx, dy = math.cos(angle), math.sin(angle)
                p.drawPolygon(QPolygonF([QPointF(x + dx * width * 2, y + dy * width * 2),
                                         QPointF(x + dy * 2.4, y - dx * 2.4),
                                         QPointF(x - dx * width * 2, y - dy * width * 2),
                                         QPointF(x - dy * 2.4, y + dx * 2.4)]))
            else:
                p.drawEllipse(QPointF(x, y), width, width * (0.62 if shape == "petal" else 1))


def keyframe_values(keyframes, progress):
    first = last = keyframes[0]
    for current in keyframes:
        last = current
        if progress <= current.at:
            break
        first = current
    weight = (progress - first.at) / (last.at - first.at) if first.at != last.at else 0
    return tuple(getattr(first, field) * (1 - weight) + getattr(last, field) * weight
                 for field in ("x", "y", "scale", "rotation", "opacity"))


def paint_layer(painter, layer, palette, progress):
    x, y, scale, rotation, opacity = keyframe_values(layer.keyframes, progress)
    painter.translate(x, y)
    painter.rotate(rotation)
    painter.scale(scale / 100, scale / 100)
    painter.setOpacity(opacity / 100)
    if layer.blend == "add":
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
    colors = layer.colors or palette
    if layer.kind == "image":
        if layer.images:
            image = layer.images[min(len(layer.images) - 1, int(progress * len(layer.images) / 100))]
            painter.drawImage(QRectF(-50, -50, 100, 100), image)
    elif layer.kind == "particles":
        draw_particles(painter, "", colors, progress * 0.78, layer)
    elif layer.kind in LIGHT_EFFECTS:
        draw_light(painter, layer.kind, colors, progress * 0.78, layer.length, layer.size / 5)
    elif layer.kind == "line":
        painter.setPen(QPen(QColor(colors[0]), layer.size, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(-layer.length / 2, 0), QPointF(layer.length / 2, 0))
    else:
        painter.setPen(QPen(QColor(colors[0]), layer.size) if layer.kind == "ring" else Qt.NoPen)
        painter.setBrush(QColor(colors[0]) if layer.kind == "disc" else Qt.NoBrush)
        radius = layer.length / 2
        painter.drawEllipse(QPointF(0, 0), radius, radius)


def paint_effect(painter, preset, palette, age, *, x, y, size, direction, target_x=None, target_y=None, design=None):
    if design is not None:
        progress = age / 78 * 100
        for layer in design.layers:
            if not layer.start <= progress < layer.end:
                continue
            anchor = (0.5 if layer.anchor == "midpoint" else 1) if layer.anchor != "source" and target_x is not None else 0
            anchor_x = x + (target_x - x) * anchor if anchor else x
            anchor_y = y + (target_y - y) * anchor if anchor and target_y is not None else y
            painter.save()
            painter.translate(anchor_x, anchor_y + size * 0.57)
            painter.scale(direction * size / 100, size / 100)
            paint_layer(painter, layer, palette, (progress - layer.start) * 100 / (layer.end - layer.start))
            painter.restore()
        return
    painter.save()
    painter.translate(x + direction * size * 0.2, y + size * 0.57)
    painter.scale(direction * size / 100, size / 100)
    painter.setOpacity(min(1, (age + 1) / 7, (78 - age) / 19))
    if preset in LIGHT_EFFECTS:
        reach = 180 if target_x is None else max(28, abs(target_x - x) * 100 / size - 55)
        draw_light(painter, preset, palette, age, reach)
    else:
        draw_particles(painter, preset, palette, age)
    painter.restore()


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
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        return painter

    def paint_spell(self, painter, pet, target, preset, palette, age, direction, *, design=None):
        paint_effect(painter, preset, palette, age, x=pet.cx - self.x(), y=pet.fy - self.y(),
                     size=pet.S, direction=direction, target_x=None if target is None else target.cx - self.x(),
                     target_y=None if target is None else target.fy - self.y(), design=design)


class PluginEffectOverlay(PetEffectOverlay):
    def __init__(self, pets, on_top, *, track_positions=False):
        self.tick = 0
        self.bursts = []
        self.expanded = False
        super().__init__(pets, on_top)
        if track_positions:
            self.expand_to_screen()

    def expand_to_screen(self):
        self.setGeometry(self.mem[0].scr())
        self.expanded = True

    def show_effect(self, source, target, effect, start):
        if effect.design is not None and not self.expanded:
            self.expand_to_screen()
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
            self.paint_spell(painter, source, target, effect.preset, effect.colors, age, direction, design=effect.design)
        painter.end()
