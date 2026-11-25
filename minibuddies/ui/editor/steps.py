"""Edit a sequence of poses, movement, speech, and visual effects."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QCheckBox, QColorDialog, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from minibuddies.plugins.motion import DISTANCE_LIMIT, FOLLOW_SPEED_LIMIT, HEIGHT_LIMIT
from minibuddies.plugins.scenes import RGB, read_move
from minibuddies.ui.editor.frames import FRAME_NAMES
from minibuddies.ui.editor.widgets import SpritePreview, image_file, options, show_error, spin
from minibuddies.ui.window_order import run_native_dialog

PRESETS = (
    ("회전 구슬", "seal"), ("빛줄기", "spark"), ("갈라지는 빛", "moon"),
    ("요정 탄막", "fairy"), ("얼어붙는 탄", "freeze"), ("흩날리는 꽃잎", "petal"),
    ("마름모 탄", "books"), ("원형 탄막", "sun"), ("시간 정지 탄", "clock"),
    ("부채꼴 탄막", "scarlet"), ("빛의 궤적", "slash"),
)
TURN_OPTIONS = (("현재 방향 유지", None), ("왼쪽 보기", "left"), ("오른쪽 보기", "right"), ("반대로 돌기", "flip"))
EASING_OPTIONS = (("일정 속도", "linear"), ("점점 빠르게", "ease-in"), ("점점 느리게", "ease-out"),
                  ("부드럽게 출발 · 정지", "ease-in-out"))


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
        self.frame_choice = options([("번호 직접 입력", None), *((f"{name} · {i}", i) for i, name in FRAME_NAMES.items())],
                                    self.frame.value())
        self.frame_choice.currentIndexChanged.connect(self.choose_frame)
        self.file_button = QPushButton("PNG 선택…")
        self.file_button.clicked.connect(self.choose_image)
        self.ticks = spin(1, 600, step.get("ticks", 24), " 틱")
        self.preview = SpritePreview(128)
        self.missing_pose = QLabel("미리보기 캐릭터에 이 프레임이 없어요.")
        self.missing_pose.setWordWrap(True)
        self.tabs = QTabWidget()
        pose_tab = QWidget()
        pose_layout = QVBoxLayout(pose_tab)
        pose_layout.addWidget(self.preview, alignment=Qt.AlignHCenter)
        pose_form = QFormLayout()
        pose_form.addRow("포즈", self.source)
        frames = QHBoxLayout()
        frames.addWidget(self.frame_choice, 1)
        frames.addWidget(self.frame)
        pose_form.addRow("동작 프레임", frames)
        pose_form.addRow("", self.missing_pose)
        pose_form.addRow("이미지", self.file_button)
        effect = step.get("effect", {})
        self.speech = QLineEdit(step.get("say", ""))
        self.speech.setMaxLength(160)
        self.dismiss_speech = QCheckBox("이 단계에서 말풍선 닫기")
        self.dismiss_speech.setChecked(step.get("dismiss_speech", False))
        self.speech.setEnabled(not self.dismiss_speech.isChecked())
        self.dismiss_speech.toggled.connect(lambda checked: self.speech.setEnabled(not checked))
        pose_form.addRow("말풍선", self.speech)
        pose_form.addRow("", self.dismiss_speech)
        pose_layout.addLayout(pose_form)
        pose_layout.addStretch()
        self.tabs.addTab(pose_tab, "포즈·말풍선")
        self.add_travel_tab(step, editor, group, actor, targets)

        effect_tab = QWidget()
        form = QFormLayout(effect_tab)
        custom = [(f"{entry['name']} ({key})", key) for key, entry in editor.project.rules.get("effects", {}).items()]
        self.preset = options([("효과 없음", None), *PRESETS, *custom], effect.get("preset"))
        self.colors = QLineEdit(", ".join(effect.get("colors", ["#ff7990", "#fff1cf"])))
        self.color_button = QPushButton("색상 추가…")
        self.color_button.clicked.connect(self.add_color)
        palette = QHBoxLayout()
        palette.addWidget(self.colors)
        palette.addWidget(self.color_button)
        self.effect_ticks = spin(1, 180, effect.get("ticks", 78), " 틱")
        form.addRow("효과", self.preset)
        if group:
            self.target = options([(editor.character_label(key), key) for key in targets if key != actor], effect.get("target"))
            form.addRow("효과 대상", self.target)
        else:
            self.target = QLabel("캐릭터가 바라보는 방향")
            form.addRow("효과 방향", self.target)
        form.addRow("색상 (#RRGGBB)", palette)
        form.addRow("효과 길이", self.effect_ticks)
        self.tabs.addTab(effect_tab, "효과")
        self.preset.currentIndexChanged.connect(self.refresh)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        duration = QFormLayout()
        duration.addRow("단계 재생 시간", self.ticks)
        layout.addLayout(duration)
        layout.addWidget(self.tabs)
        layout.addWidget(buttons)
        self.source.currentIndexChanged.connect(self.refresh)
        self.frame.valueChanged.connect(self.refresh)
        self.refresh()

    def add_travel_tab(self, step, editor, group, actor, targets):
        move, turn, follow = (step.get(kind, {}) for kind in ("move", "turn", "follow"))
        travel_modes = [("이동 없음", None), ("수평 이동", "slide"), ("점프", "jump")]
        if group:
            travel_modes.append(("캐릭터 따라가기", "follow"))
        mode = "follow" if follow else "jump" if move.get("height") else "slide" if move else None
        self.travel = options(travel_modes, mode)
        self.distance = spin(-DISTANCE_LIMIT, DISTANCE_LIMIT, move.get("distance", 0), " %")
        self.height = spin(1, HEIGHT_LIMIT, move.get("height") or 60, " %")
        self.easing = options(EASING_OPTIONS, move.get("easing", "linear"))
        movement = QGroupBox("이동")
        form = self.travel_form = QFormLayout(movement)
        form.addRow("이동 방식", self.travel)
        form.addRow("수평 거리", self.distance)
        form.addRow("점프 높이", self.height)
        form.addRow("수평 속도 변화", self.easing)
        self.follow_fields = []
        other_characters = [(editor.character_label(key), key) for key in targets if key != actor]
        if group:
            self.follow_target = options(other_characters, follow.get("target"))
            self.follow_distance = spin(0, DISTANCE_LIMIT, follow.get("distance", 70), " %")
            self.follow_speed = spin(1, FOLLOW_SPEED_LIMIT, follow.get("speed", 3), " %/틱")
            self.follow_fields = [self.follow_target, self.follow_distance, self.follow_speed]
            for label, field in zip(("따라갈 캐릭터", "유지할 거리", "이동 속도"), self.follow_fields):
                form.addRow(label, field)
        self.travel_guide = QLabel()
        self.travel_guide.setWordWrap(True)
        form.addRow(self.travel_guide)
        turn_items = list(TURN_OPTIONS)
        if group:
            turn_items.append(("다른 캐릭터 바라보기", "target"))
        self.facing = options(turn_items, turn.get("direction"))
        turn_box = QGroupBox("방향 전환")
        form = QFormLayout(turn_box)
        form.addRow("바라볼 방향", self.facing)
        self.turn_target = None
        if group:
            self.turn_target = options(other_characters, turn.get("target"))
            form.addRow("바라볼 캐릭터", self.turn_target)
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(turn_box)
        layout.addWidget(movement)
        layout.addStretch()
        self.tabs.addTab(tab, "이동·방향")
        self.travel.currentIndexChanged.connect(self.refresh_travel)
        self.facing.currentIndexChanged.connect(self.refresh_travel)
        self.distance.valueChanged.connect(self.refresh_travel)
        self.refresh_travel()

    def refresh_travel(self):
        mode = self.travel.currentData()
        following = mode == "follow"
        for field in (self.distance, self.height, self.easing, *self.follow_fields):
            visible = following == (field in self.follow_fields)
            field.setVisible(visible)
            self.travel_form.labelForField(field).setVisible(visible)
        self.travel_guide.setText("펫 한 마리의 너비가 100%예요. 이 단계가 끝날 때까지 따라갑니다." if following
                                  else "펫 한 마리의 너비가 100%예요. 양수는 전진, 음수는 후퇴입니다.")
        self.distance.setEnabled(mode is not None)
        self.height.setEnabled(mode == "jump")
        self.easing.setEnabled(mode is not None and self.distance.value() != 0)
        if self.turn_target is not None:
            self.turn_target.setEnabled(self.facing.currentData() == "target")

    def choose_frame(self):
        number = self.frame_choice.currentData()
        if number is not None:
            self.frame.setValue(number)

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
        self.frame_choice.setEnabled(current == "frame")
        self.frame_choice.blockSignals(True)
        index = self.frame_choice.findData(self.frame.value())
        self.frame_choice.setCurrentIndex(max(0, index))
        self.frame_choice.blockSignals(False)
        self.file_button.setEnabled(current == "file")
        for control in (self.target, self.colors, self.color_button, self.effect_ticks):
            control.setEnabled(self.preset.currentData() is not None)
        step = self.previous_pose
        if current == "frame":
            step = {"frame": self.frame.value()}
        elif current == "file":
            step = {"file": self.file}
        data = self.editor.step_image(step, self.actor)
        self.missing_pose.setVisible(bool(self.actor and current == "frame" and data is None))
        self.preview.display(data)

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
        if self.dismiss_speech.isChecked():
            step["dismiss_speech"] = True
        elif self.speech.text():
            step["say"] = self.speech.text()
        mode = self.travel.currentData()
        if mode == "follow":
            target = self.follow_target.currentData()
            if not target:
                self.tabs.setCurrentIndex(1)
                show_error(self, "따라갈 캐릭터를 선택하세요.")
                return
            step["follow"] = {"target": target, "distance": self.follow_distance.value(), "speed": self.follow_speed.value()}
        elif mode:
            movement = {"distance": self.distance.value(), "height": self.height.value() if mode == "jump" else 0,
                        "easing": self.easing.currentData()}
            try:
                read_move(movement, step["ticks"])
            except ValueError as error:
                self.tabs.setCurrentIndex(1)
                show_error(self, error)
                return
            step["move"] = movement
        direction = self.facing.currentData()
        if direction:
            step["turn"] = {"direction": direction}
            if direction == "target":
                target = self.turn_target.currentData()
                if not target:
                    self.tabs.setCurrentIndex(1)
                    show_error(self, "바라볼 캐릭터를 선택하세요.")
                    return
                step["turn"]["target"] = target
        if self.preset.currentData():
            colors = [part.strip() for part in self.colors.text().split(",")]
            if not 1 <= len(colors) <= 6 or any(not RGB.fullmatch(color) for color in colors):
                self.tabs.setCurrentIndex(2)
                show_error(self, "#RRGGBB 색상을 1~6개 입력하세요.")
                return
            effect = {"preset": self.preset.currentData(), "colors": colors, "ticks": self.effect_ticks.value()}
            if self.group:
                target = self.target.currentData()
                if not target:
                    self.tabs.setCurrentIndex(2)
                    show_error(self, "효과를 받을 캐릭터를 선택하세요.")
                    return
                effect["target"] = target
            step["effect"] = effect
        self.result_step = step
        super().accept()


class Timeline(QWidget):
    changed = pyqtSignal()

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
        body = QHBoxLayout()
        body.addWidget(self.list, 1)
        body.addWidget(self.preview)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(controls)
        layout.addLayout(body)
        self.list.currentRowChanged.connect(self.select)
        self.list.itemDoubleClicked.connect(self.edit)

    def load(self, steps, actor, targets):
        self.steps, self.actor, self.targets = steps, actor, targets
        self.setEnabled(not self.group or bool(actor))
        self.refresh(0)

    def refresh(self, row):
        self.list.clear()
        for step in self.steps:
            pose = "이전 포즈 유지"
            if "file" in step:
                pose = "PNG 이미지"
            elif "frame" in step:
                number = step["frame"]
                pose = f"{FRAME_NAMES.get(number, '프레임')} {number}"
            move, turn = step.get("move", {}), step.get("turn", {})
            distance, height = move.get("distance", 0), move.get("height", 0)
            travel = f"이동 {distance:+d}%" if distance else ""
            if "follow" in step:
                travel = f"{self.editor.character_label(step['follow']['target'])} 따라가기"
            jump = f"점프 {height}%" if height else ""
            direction = dict((key, label) for label, key in TURN_OPTIONS).get(turn.get("direction")) if turn else None
            if turn.get("target"):
                direction = f"{self.editor.character_label(turn['target'])} 보기"
            speech = "말풍선 닫기" if step.get("dismiss_speech") else step.get("say")
            extra = " · ".join(part for part in (direction, travel, jump, speech, step.get("effect", {}).get("preset")) if part)
            self.list.addItem(f"{pose} · {step['ticks']} 틱" + (f" · {extra}" if extra else ""))
        self.list.setCurrentRow(min(row, len(self.steps) - 1))

    def select(self, row):
        if not 0 <= row < len(self.steps):
            self.preview.display(None)
            return
        self.preview.display(self.editor.step_image(self.pose_before(row + 1), self.actor))

    def pose_before(self, row):
        return next((step for step in reversed(self.steps[:row]) if "frame" in step or "file" in step), {"frame": 0})

    def edit(self):
        row = self.list.currentRow()
        if row >= 0:
            self.open_step(row, self.steps[row])

    def add(self):
        if len(self.steps) < 64:
            self.open_step(len(self.steps), {"frame": 0, "ticks": 24})

    def open_step(self, row, step):
        dialog = StepDialog(self, self.editor, step, self.group, self.actor, self.targets,
                            previous_pose=self.pose_before(row))
        if dialog.exec_() == QDialog.Accepted:
            self.steps[row:row + 1] = [dialog.result_step]
            self.refresh(row)
            self.changed.emit()

    def remove(self):
        row = self.list.currentRow()
        if row >= 0:
            self.steps.pop(row)
            self.refresh(row)
            self.changed.emit()

    def move_step(self, change):
        row = self.list.currentRow()
        target = row + change
        if 0 <= row < len(self.steps) and 0 <= target < len(self.steps):
            self.steps[row], self.steps[target] = self.steps[target], self.steps[row]
            self.refresh(target)
            self.changed.emit()
