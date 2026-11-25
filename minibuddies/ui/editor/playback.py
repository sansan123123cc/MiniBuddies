"""Play a rule in the editor with all of its actors on a shared stage."""

from PyQt5.QtCore import QPointF, QRect, QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QFontMetrics, QPainter, QPolygonF
from PyQt5.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from minibuddies.catalog import TICK
from minibuddies.effects import paint_effect
from minibuddies.plugins.motion import INTERACTION_GAP, MotionActor, compile_motion
from minibuddies.plugins.packs import sprite_bounds
from minibuddies.plugins.scenes import SPEECH_TICKS, read_effect_designs, read_steps
from minibuddies.ui.editor.widgets import image_pixmap


class PreviewTrack:
    def __init__(self, editor, character, steps, characters, designs, opening_speech):
        self.label = editor.character_label(character, include_id=False) or "캐릭터"
        self.opening_speech = opening_speech
        assets = {}

        def sprite_id(path):
            return assets.setdefault(path, -len(assets) - 1)

        self.beats, self.duration = read_steps(steps, sprite_id, character=character, characters=characters,
                                               designs=designs) if steps else ((), 0)
        poses = {0: {"frame": 0}, **{index: {"file": path} for path, index in assets.items()}}
        poses.update({beat.frame: {"frame": beat.frame} for beat in self.beats if beat.frame is not None and beat.frame >= 0})
        self.sprites = {}
        for index, pose in poses.items():
            image = image_pixmap(editor.step_image(pose, character)).toImage()
            bounds = None if image.isNull() else sprite_bounds(image)
            self.sprites[index] = (image, bounds or {"top": 0.1, "bottom": 0.98})

    def pose(self, tick):
        frame = next((beat.frame for beat in reversed(self.beats) if beat.at <= tick and beat.frame is not None), 0)
        return self.sprites[frame]

    def speech(self, tick):
        for beat in reversed(self.beats):
            if beat.at <= tick:
                if beat.dismiss_speech:
                    return ""
                if beat.speech:
                    return beat.speech if tick - beat.at < SPEECH_TICKS else ""
        return self.opening_speech if tick < SPEECH_TICKS else ""

    def effects(self, tick):
        return ((beat.effect, (tick - beat.at) * 78 / beat.effect.ticks) for beat in self.beats
                if beat.effect and 0 <= tick - beat.at < beat.effect.ticks)


class PreviewStage(QWidget):
    def __init__(self, tracks):
        super().__init__()
        self.tracks = tracks
        self.duration = max(track.duration for track in tracks.values())
        self.tick = 0
        midpoint = (len(tracks) - 1) / 2
        actors = {key: MotionActor((i - midpoint) * INTERACTION_GAP * 100,
                                   1 if len(tracks) == 1 or i < midpoint else -1, 100)
                  for i, key in enumerate(tracks)}
        self.motion = compile_motion(actors, {key: track.beats for key, track in tracks.items()})
        extents = [track.extents() for track in self.motion.values()]
        left = min(extent[0] for extent in extents)
        right = max(extent[1] for extent in extents)
        self.stage_center = (left + right) / 2
        self.stage_width = right - left + 300
        self.jump_clearance = max(extent[2] for extent in extents)
        self.setMinimumHeight(328)

    def seek(self, tick):
        self.tick = tick
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#30293e"))
        floor = int(self.height() * 0.77)
        p.fillRect(0, floor, self.width(), self.height() - floor, QColor("#393149"))
        p.setPen(QColor("#70667d"))
        p.drawLine(0, floor, self.width(), floor)
        center = self.width() / 2
        count = len(self.tracks)
        size = min(128, self.width() * 100 / self.stage_width, (floor - 24) * 100 / (100 + self.jump_clearance))
        gap = size * INTERACTION_GAP
        bubble_width = min(216, gap - 8) if count > 1 else min(240, self.width() - 28)
        positions = {}
        for key, track in self.tracks.items():
            pose = self.motion[key].pose(self.tick)
            x = center + (pose.x - self.stage_center) * size / 100
            face = pose.face
            image, bounds = track.pose(self.tick)
            y = floor - size * (bounds["bottom"] + pose.lift / 100)
            positions[key] = (x, y, face, y + size * bounds["top"])
            if not image.isNull():
                p.save()
                p.translate(x, y)
                p.scale(face, 1)
                p.drawImage(QRectF(-size / 2, 0, size, size), image)
                p.restore()
            label = p.fontMetrics().elidedText(track.label, Qt.ElideRight, int(gap))
            color = "#e6dcf2" if not image.isNull() else "#bfb0cc"
            p.setPen(QColor(color))
            if image.isNull():
                p.drawText(QRectF(x - gap / 2, y, gap, size), Qt.AlignCenter, "그림 없음")
            p.drawText(QRectF(x - gap / 2, floor + 5, gap, 24), Qt.AlignCenter, label)
        for key, track in self.tracks.items():
            x, y, face, _ = positions[key]
            for effect, age in track.effects(self.tick):
                target_x, target_y = positions[effect.target][:2] if effect.target else (None, None)
                direction = face if target_x is None else (1 if x <= target_x else -1)
                paint_effect(p, effect.preset, effect.colors, age, x=x, y=y, size=size, direction=direction,
                             target_x=target_x, target_y=target_y, design=effect.design)
        if self.tick < self.duration:
            for key, track in self.tracks.items():
                text = track.speech(self.tick)
                if text:
                    x, _, _, top = positions[key]
                    self.draw_speech(p, text, x, top, bubble_width)
        p.end()

    @staticmethod
    def draw_speech(p, text, x, top, width):
        p.save()
        font = p.font()
        font.setPixelSize(13)
        flags = Qt.TextWrapAnywhere | Qt.AlignCenter
        text_box = QRect(0, 0, int(width - 16), 1000)
        height = QFontMetrics(font).boundingRect(text_box, flags, text).height() + 12
        if height > top - 16:
            font.setPixelSize(10)
            height = QFontMetrics(font).boundingRect(text_box, flags, text).height() + 12
        p.setFont(font)
        bubble = QRectF(x - width / 2, max(6, top - 10 - height), width, min(height, top - 16))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#fff4e8"))
        p.drawRoundedRect(bubble, 8, 8)
        p.drawPolygon(QPolygonF([QPointF(x - 5, bubble.bottom() - 1), QPointF(x + 5, bubble.bottom() - 1),
                                 QPointF(x, bubble.bottom() + 6)]))
        p.setPen(QColor("#30293e"))
        p.drawText(bubble.adjusted(8, 6, -8, -6), flags, text)
        p.restore()


class PlaybackDialog(QDialog):
    def __init__(self, parent, editor, sequences, *, group, opening_speech=""):
        super().__init__(parent)
        self.setWindowTitle("상호작용 미리 재생" if group else "개별 동작 미리 재생")
        designs = read_effect_designs(editor.project.rules.get("effects", {}), editor.effect_image)
        characters = set(sequences) if group else None
        tracks = {key: PreviewTrack(editor, key, steps, characters, designs, opening_speech) for key, steps in sequences.items()}
        self.stage = PreviewStage(tracks)
        self.progress = QSlider(Qt.Horizontal)
        self.progress.setRange(0, self.stage.duration)
        self.progress.valueChanged.connect(self.seek)
        self.clock = QLabel()
        self.play_button = QPushButton()
        self.play_button.setAutoDefault(False)
        self.play_button.clicked.connect(self.toggle_play)
        close = QPushButton("닫기")
        close.setAutoDefault(False)
        close.clicked.connect(self.reject)
        controls = QHBoxLayout()
        controls.addWidget(self.play_button)
        controls.addWidget(self.progress, 1)
        controls.addWidget(self.clock)
        controls.addWidget(close)
        layout = QVBoxLayout(self)
        layout.addWidget(self.stage, 1)
        layout.addLayout(controls)
        self.resize(850 if group else 560, 440)
        self.timer = QTimer(self, interval=TICK, timerType=Qt.PreciseTimer)
        self.timer.timeout.connect(self.advance)
        self.seek(0)
        self.toggle_play()

    def seek(self, tick):
        self.stage.seek(tick)
        self.clock.setText(f"{tick * TICK / 1000:.1f} / {self.stage.duration * TICK / 1000:.1f} 초")

    def toggle_play(self):
        if self.timer.isActive():
            self.pause()
        else:
            if self.progress.value() == self.stage.duration:
                self.progress.setValue(0)
            self.play_button.setText("일시정지")
            self.timer.start()

    def advance(self):
        self.progress.setValue(self.progress.value() + 1)
        if self.progress.value() == self.stage.duration:
            self.pause()

    def pause(self):
        self.timer.stop()
        self.play_button.setText("재생")

    def done(self, result):
        self.pause()
        super().done(result)
