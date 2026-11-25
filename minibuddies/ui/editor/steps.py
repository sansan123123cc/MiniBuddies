"""Edit and preview a sequence of poses, speech, and visual effects."""

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QColorDialog, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QPushButton, QVBoxLayout, QWidget,
)

from minibuddies.plugins.scenes import RGB
from minibuddies.ui.editor.widgets import SpritePreview, image_file, options, show_error, spin
from minibuddies.ui.window_order import run_native_dialog

PRESETS = (
    ("회전 구슬", "seal"), ("빛줄기", "spark"), ("갈라지는 빛", "moon"),
    ("요정 탄막", "fairy"), ("얼어붙는 탄", "freeze"), ("흩날리는 꽃잎", "petal"),
    ("마름모 탄", "books"), ("원형 탄막", "sun"), ("시간 정지 탄", "clock"),
    ("부채꼴 탄막", "scarlet"), ("빛의 궤적", "slash"),
)


class StepDialog(QDialog):
    def __init__(self, parent, editor, step, group, actor, targets, *, previous_pose=None):
        super().__init__(parent)
        self.setWindowTitle("액션 편집")
        self.editor, self.group, self.actor = editor, group, actor
        self.previous_pose = previous_pose or {"frame": 0}
        self.file = step.get("file")
        kinds = [("캐릭터 프레임", "frame"), ("새 PNG 이미지", "file"), ("이전 포즈 유지", "hold")]
        current = "file" if self.file else "frame" if "frame" in step else "hold"
        self.source = options(kinds, current)
        self.frame = spin(0, 9999, step.get("frame", 0))
        self.file_button = QPushButton("PNG 선택…")
        self.file_button.clicked.connect(self.choose_image)
        self.ticks = spin(1, 600, step.get("ticks", 24), " 틱")
        self.preview = SpritePreview(128)
        form = QFormLayout()
        form.addRow("포즈", self.source)
        form.addRow("프레임 번호", self.frame)
        form.addRow("이미지", self.file_button)
        form.addRow("재생 시간", self.ticks)
        effect = step.get("effect", {})
        self.speech = QLineEdit(step.get("say", ""))
        self.speech.setMaxLength(160)
        self.preset = options([("효과 없음", None), *PRESETS], effect.get("preset"))
        self.colors = QLineEdit(", ".join(effect.get("colors", ["#ff7990", "#fff1cf"])))
        self.color_button = QPushButton("색상 추가…")
        self.color_button.clicked.connect(self.add_color)
        palette = QHBoxLayout()
        palette.addWidget(self.colors)
        palette.addWidget(self.color_button)
        self.effect_ticks = spin(1, 180, effect.get("ticks", 78), " 틱")
        form.addRow("말풍선", self.speech)
        form.addRow("효과", self.preset)
        if group:
            self.target = options([(editor.character_label(key), key) for key in targets if key != actor], effect.get("target"))
            form.addRow("효과 대상", self.target)
        else:
            self.target = QLabel("캐릭터가 바라보는 방향")
            form.addRow("효과 방향", self.target)
        form.addRow("색상 (#RRGGBB)", palette)
        form.addRow("효과 길이", self.effect_ticks)
        self.preset.currentIndexChanged.connect(self.refresh)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.preview, alignment=Qt.AlignHCenter)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.source.currentIndexChanged.connect(self.refresh)
        self.frame.valueChanged.connect(self.refresh)
        self.refresh()

    def choose_image(self):
        data = image_file(self)
        if data is not None:
            self.file = self.editor.project.add_image(data)
            self.refresh()

    def add_color(self):
        color = run_native_dialog(QColorDialog.getColor, QColor("#ff7990"), self, "효과 색상")
        if color.isValid():
            colors = [part.strip() for part in self.colors.text().split(",") if part.strip()]
            self.colors.setText(", ".join([*colors[:5], color.name()]))

    def refresh(self):
        current = self.source.currentData()
        self.frame.setEnabled(current == "frame")
        self.file_button.setEnabled(current == "file")
        for control in (self.target, self.colors, self.color_button, self.effect_ticks):
            control.setEnabled(self.preset.currentData() is not None)
        step = self.previous_pose
        if current == "frame":
            step = {"frame": self.frame.value()}
        elif current == "file":
            step = {"file": self.file}
        self.preview.display(self.editor.step_image(step, self.actor))

    def accept(self):
        step = {"ticks": self.ticks.value()}
        current = self.source.currentData()
        if current == "frame":
            step["frame"] = self.frame.value()
        elif current == "file":
            if not self.file:
                show_error(self, "재생할 PNG를 선택하세요.")
                return
            step["file"] = self.file
        if self.speech.text():
            step["say"] = self.speech.text()
        if self.preset.currentData():
            colors = [part.strip() for part in self.colors.text().split(",")]
            if not 1 <= len(colors) <= 6 or any(not RGB.fullmatch(color) for color in colors):
                show_error(self, "#RRGGBB 색상을 1~6개 입력하세요.")
                return
            effect = {"preset": self.preset.currentData(), "colors": colors, "ticks": self.effect_ticks.value()}
            if self.group:
                target = self.target.currentData()
                if not target:
                    show_error(self, "효과를 받을 참가자를 선택하세요.")
                    return
                effect["target"] = target
            step["effect"] = effect
        self.result_step = step
        super().accept()


class Timeline(QWidget):
    def __init__(self, editor, *, group):
        super().__init__()
        self.editor, self.group = editor, group
        self.steps, self.actor, self.targets = [], "", []
        self.list = QListWidget()
        self.preview = SpritePreview()
        controls = QHBoxLayout()
        for label, handler in (("추가", self.add), ("편집", self.edit), ("삭제", self.remove),
                               ("위로", lambda: self.move_step(-1)), ("아래로", lambda: self.move_step(1))):
            button = QPushButton(label)
            button.clicked.connect(handler)
            controls.addWidget(button)
        self.play_button = QPushButton("포즈 미리 재생")
        self.play_button.setCheckable(True)
        self.play_button.toggled.connect(self.play)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.advance)
        body = QHBoxLayout()
        body.addWidget(self.list, 1)
        body.addWidget(self.preview)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(controls)
        layout.addLayout(body)
        layout.addWidget(self.play_button)
        self.list.currentRowChanged.connect(self.select)
        self.list.itemDoubleClicked.connect(self.edit)

    def load(self, steps, actor, targets):
        self.play_button.setChecked(False)
        self.steps, self.actor, self.targets = steps, actor, targets
        self.setEnabled(not self.group or bool(actor))
        self.refresh(0)

    def refresh(self, row):
        self.list.clear()
        for step in self.steps:
            pose = "PNG 이미지" if "file" in step else f"기본 프레임 {step['frame']}" if "frame" in step else "이전 포즈 유지"
            extra = " · ".join(part for part in (step.get("say"), step.get("effect", {}).get("preset")) if part)
            self.list.addItem(f"{pose} · {step['ticks']} 틱" + (f" · {extra}" if extra else ""))
        self.list.setCurrentRow(min(row, len(self.steps) - 1))
        self.play_button.setEnabled(bool(self.steps))

    def select(self, row):
        if not 0 <= row < len(self.steps):
            self.preview.display(None)
            return
        self.preview.display(self.editor.step_image(self.pose_before(row + 1), self.actor))

    def pose_before(self, row):
        return next((step for step in reversed(self.steps[:row]) if "frame" in step or "file" in step), {"frame": 0})

    def play(self, enabled):
        self.timer.stop()
        if enabled and self.steps:
            self.play_row = -1
            self.advance()

    def advance(self):
        self.play_row += 1
        if self.play_row >= len(self.steps):
            self.play_button.setChecked(False)
            return
        self.list.setCurrentRow(self.play_row)
        self.timer.start(self.steps[self.play_row]["ticks"] * 16)

    def edit(self):
        row = self.list.currentRow()
        if row >= 0:
            self.open_step(row, self.steps[row])

    def add(self):
        if len(self.steps) < 64:
            self.open_step(len(self.steps), {"frame": 0, "ticks": 24})

    def open_step(self, row, step):
        self.play_button.setChecked(False)
        dialog = StepDialog(self, self.editor, step, self.group, self.actor, self.targets,
                            previous_pose=self.pose_before(row))
        if dialog.exec_() == QDialog.Accepted:
            self.steps[row:row + 1] = [dialog.result_step]
            self.refresh(row)

    def remove(self):
        self.play_button.setChecked(False)
        row = self.list.currentRow()
        if row >= 0:
            self.steps.pop(row)
            self.refresh(row)

    def move_step(self, change):
        self.play_button.setChecked(False)
        row = self.list.currentRow()
        target = row + change
        if 0 <= row < len(self.steps) and 0 <= target < len(self.steps):
            self.steps[row], self.steps[target] = self.steps[target], self.steps[row]
            self.refresh(target)
