"""Author layered effects and preview them with the same renderer as desktop pets."""

from copy import deepcopy

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView, QColorDialog, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHeaderView, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSlider, QTableWidget, QVBoxLayout, QWidget,
)

from minibuddies.authoring.project import read_image, rule_steps
from minibuddies.catalog import TICK
from minibuddies.effects import LIGHT_EFFECTS, paint_effect
from minibuddies.plugins.scenes import read_effect_designs, read_effect_layer
from minibuddies.ui.editor.widgets import options, show_error, spin
from minibuddies.ui.window_order import run_native_dialog


KINDS = (
    ("원 테두리", "ring"), ("채운 원", "disc"), ("선", "line"), ("PNG 애니메이션", "image"),
    ("파티클", "particles"), ("빛줄기", "spark"), ("갈라지는 빛", "moon"), ("빛의 궤적", "slash"),
)
SHAPES = (("원", "orb"), ("마름모", "diamond"), ("꽃잎", "petal"))
KEYFRAME_FIELDS = (
    ("at", "시점 %", 0, 100, 0), ("x", "X", -200, 200, 0), ("y", "Y", -200, 200, 0),
    ("scale", "크기 %", 1, 300, 100), ("rotation", "회전 °", -720, 720, 0), ("opacity", "불투명", 0, 100, 100),
)


def controls(items):
    layout = QHBoxLayout()
    for label, handler in items:
        button = QPushButton(label)
        if label in ("↑", "↓"):
            button.setFixedWidth(34)
        button.setAutoDefault(False)
        button.clicked.connect(handler)
        layout.addWidget(button)
    layout.addStretch()
    return layout


class EffectSample(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(340, 240)
        self.design = None
        self.progress = 0
        self.zoom = 1.0

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor("#30293e"))
        x, y = self.width() * 0.33, self.height() / 2
        target = self.width() * 0.67
        size = min(self.width() / 5, 85) * self.zoom
        if self.design is not None:
            paint_effect(painter, "", ("#ff7990", "#fff1cf", "#bc9fff"), self.progress * 0.78,
                         x=x, y=y - size * 0.57, size=size, direction=1, target_x=target, design=self.design)
        painter.setPen(QColor("#dfd3ed"))
        for position, label in ((x, "시전자"), (target, "대상")):
            painter.drawText(int(position - 22), self.height() - 12, label)
        painter.end()


class LayerDialog(QDialog):
    def __init__(self, parent, editor, item):
        super().__init__(parent)
        self.editor = editor
        self.setWindowTitle("효과 레이어")
        self.name = QLineEdit(item.get("name", ""))
        self.name.setMaxLength(60)
        self.kind = options(KINDS, item.get("kind", "ring"))
        self.anchor = options([("시전자", "source"), ("두 캐릭터 사이", "midpoint"), ("대상", "target")],
                              item.get("anchor", "source"))
        self.blend = options([("일반", "normal"), ("밝기 더하기", "add")], item.get("blend", "normal"))
        self.start = spin(0, 99, item.get("start", 0), " %")
        self.end = spin(1, 100, item.get("end", 100), " %")
        self.colors = QLineEdit(", ".join(item.get("colors", [])))
        self.colors.setPlaceholderText("비워두면 액션 색상 사용")
        color_button = QPushButton("색상 추가…")
        color_button.setAutoDefault(False)
        color_button.clicked.connect(self.add_color)
        self.palette = QWidget()
        palette_layout = QHBoxLayout(self.palette)
        palette_layout.setContentsMargins(0, 0, 0, 0)
        palette_layout.addWidget(self.colors)
        palette_layout.addWidget(color_button)
        self.size = spin(1, 10, item.get("size", 5))
        self.length = spin(10, 240, item.get("length", 100))
        self.shape = options(SHAPES, item.get("shape", "orb"))
        self.count = spin(1, 32, item.get("count", 8))
        self.spread = spin(0, 360, item.get("spread", 90), "°")
        self.speed = QDoubleSpinBox()
        self.speed.setRange(0.5, 4.5)
        self.speed.setDecimals(1)
        self.speed.setSingleStep(0.1)
        self.speed.setValue(item.get("speed", 3.0))
        self.waves = spin(1, 5, item.get("waves", 3))
        self.interval = spin(1, 36, item.get("interval", 17))
        self.particle_fields = (self.shape, self.count, self.spread, self.speed, self.waves, self.interval)
        self.files = list(item.get("files", []))
        self.frames = QListWidget()
        self.frames.setMaximumHeight(72)
        self.png_tools = QWidget()
        self.png_tools.setLayout(controls((
            ("PNG 추가…", self.add_images), ("삭제", self.remove_image),
            ("↑", lambda: self.move_image(-1)), ("↓", lambda: self.move_image(1)),
        )))
        self.form = QFormLayout()
        for label, field in (
            ("레이어 이름", self.name), ("종류", self.kind), ("기준 위치", self.anchor), ("합성", self.blend),
            ("시작", self.start), ("끝", self.end), ("색상 (#RRGGBB)", self.palette),
            ("굵기 / 탄 크기", self.size), ("길이 / 지름", self.length), ("탄 모양", self.shape),
            ("탄 수", self.count), ("발사 각도", self.spread), ("탄 속도", self.speed), ("발사 횟수", self.waves),
            ("발사 간격", self.interval), ("PNG 프레임", self.frames), ("", self.png_tools),
        ):
            self.form.addRow(label, field)
        self.table = QTableWidget(0, len(KEYFRAME_FIELDS))
        self.table.setHorizontalHeaderLabels([label for _, label, *_ in KEYFRAME_FIELDS])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        frames = item.get("keyframes", [{"at": 0, "scale": 65}, {"at": 100, "scale": 130, "opacity": 0}])
        for frame in frames:
            self.append_keyframe(frame)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        keyframes = QVBoxLayout()
        label = QLabel("키프레임 · 시점은 이 레이어 안에서의 재생 위치")
        keyframes.addWidget(label)
        keyframes.addLayout(controls((("키프레임 추가", self.add_keyframe), ("키프레임 삭제", self.remove_keyframe))))
        keyframes.addWidget(self.table, 1)
        body = QHBoxLayout()
        body.addLayout(self.form)
        body.addLayout(keyframes, 1)
        layout = QVBoxLayout(self)
        layout.addLayout(body, 1)
        layout.addWidget(buttons)
        self.kind.currentIndexChanged.connect(self.refresh)
        self.start.valueChanged.connect(self.refresh)
        self.waves.valueChanged.connect(self.refresh)
        self.refresh_files()
        self.refresh()
        self.resize(950, 470)

    def refresh(self):
        kind = self.kind.currentData()
        visibility = {
            **{field: kind == "particles" for field in self.particle_fields},
            self.frames: kind == "image", self.png_tools: kind == "image",
            self.palette: kind != "image", self.size: kind not in ("image", "disc"),
            self.length: kind not in ("particles", "image"),
        }
        for field, visible in visibility.items():
            field.setVisible(visible)
            label = self.form.labelForField(field)
            if label is not None:
                label.setVisible(visible)
        self.length.setMaximum(180 if kind in LIGHT_EFFECTS else 240)
        self.end.setMinimum(self.start.value() + 1)
        self.interval.setEnabled(self.waves.value() > 1)
        self.interval.setMaximum(min(36, 60 // max(1, self.waves.value() - 1)))

    def add_color(self):
        color = run_native_dialog(QColorDialog.getColor, QColor("#ff7990"), self, "레이어 색상")
        if color.isValid():
            existing = [part.strip() for part in self.colors.text().split(",") if part.strip()]
            self.colors.setText(", ".join([*existing[:5], color.name()]))

    def append_keyframe(self, frame):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for column, (key, _, low, high, default) in enumerate(KEYFRAME_FIELDS):
            field = spin(low, high, frame.get(key, default))
            if key == "opacity":
                field.setSuffix("%")
            self.table.setCellWidget(row, column, field)
        self.table.setCurrentCell(row, 0)

    def add_keyframe(self):
        if self.table.rowCount() < 12:
            used = {self.table.cellWidget(row, 0).value() for row in range(self.table.rowCount())}
            at = min((tick for tick in range(101) if tick not in used), key=lambda tick: abs(tick - 50))
            self.append_keyframe({"at": at})

    def remove_keyframe(self):
        if self.table.rowCount() > 1 and self.table.currentRow() >= 0:
            self.table.removeRow(self.table.currentRow())

    def refresh_files(self, row=0):
        self.frames.clear()
        for i, file in enumerate(self.files):
            icon = QIcon(QPixmap.fromImage(self.editor.effect_image(file)))
            self.frames.addItem(QListWidgetItem(icon, f"프레임 {i + 1}"))
        self.frames.setCurrentRow(min(len(self.files) - 1, row))

    def add_images(self):
        paths, _ = run_native_dialog(QFileDialog.getOpenFileNames, self, "효과 PNG 프레임 추가", "", "PNG (*.png)")
        if not paths:
            return
        if len(self.files) + len(paths) > 16:
            show_error(self, "PNG 레이어에 프레임을 최대 16장 넣을 수 있어요.")
            return
        try:
            images = [read_image(path) for path in paths]
        except (OSError, ValueError) as error:
            show_error(self, error)
            return
        self.files.extend(self.editor.project.add_image(image) for image in images)
        self.refresh_files(len(self.files) - 1)

    def remove_image(self):
        row = self.frames.currentRow()
        if row >= 0:
            self.files.pop(row)
            self.refresh_files(row)

    def move_image(self, change):
        row = self.frames.currentRow()
        target = row + change
        if 0 <= row < len(self.files) and 0 <= target < len(self.files):
            self.files[row], self.files[target] = self.files[target], self.files[row]
            self.refresh_files(target)

    def accept(self):
        kind = self.kind.currentData()
        frames = [{key: self.table.cellWidget(row, column).value()
                   for column, (key, *_) in enumerate(KEYFRAME_FIELDS)} for row in range(self.table.rowCount())]
        item = {"kind": kind, "name": self.name.text().strip(), "anchor": self.anchor.currentData(),
                "blend": self.blend.currentData(), "start": self.start.value(), "end": self.end.value(),
                "keyframes": sorted(frames, key=lambda frame: frame["at"])}
        if kind == "image":
            item["files"] = self.files
        else:
            item["size"] = self.size.value()
            if self.colors.text().strip():
                item["colors"] = [color.strip() for color in self.colors.text().split(",")]
            if kind == "particles":
                item.update(shape=self.shape.currentData(), count=self.count.value(), spread=self.spread.value(),
                            speed=self.speed.value(), waves=self.waves.value(), interval=self.interval.value())
            else:
                item["length"] = self.length.value()
        try:
            read_effect_layer(item, self.editor.effect_image)
        except ValueError as error:
            show_error(self, error)
            return
        self.result_layer = item
        super().accept()


class EffectDialog(QDialog):
    def __init__(self, parent, editor, definitions, key):
        super().__init__(parent)
        self.editor, self.definitions, self.original_key = editor, definitions, key
        self.setWindowTitle("효과 편집" if key else "새 효과")
        item = definitions.get(key, {})
        self.layers = deepcopy(item.get("layers", []))
        self.key = QLineEdit(key or "")
        self.key.setMaxLength(64)
        self.key.setReadOnly(bool(key))
        self.key.setPlaceholderText("예: starlight")
        self.name = QLineEdit(item.get("name", ""))
        self.name.setMaxLength(80)
        form = QFormLayout()
        form.addRow("효과 ID", self.key)
        form.addRow("이름", self.name)
        self.layer_list = QListWidget()
        self.layer_list.itemDoubleClicked.connect(self.edit_layer)
        left = QVBoxLayout()
        left.addLayout(form)
        left.addWidget(QLabel("레이어 · 위에서 아래로 그리는 순서"))
        left.addLayout(controls((
            ("추가…", self.add_layer), ("편집…", self.edit_layer), ("삭제", self.remove_layer),
            ("↑", lambda: self.move_layer(-1)), ("↓", lambda: self.move_layer(1)),
        )))
        left.addWidget(self.layer_list, 1)
        self.sample = EffectSample()
        self.progress = QSlider(Qt.Horizontal)
        self.progress.setRange(0, 100)
        self.progress.valueChanged.connect(self.seek)
        zoom = options([("100%", 1.0), ("50%", 0.5), ("25%", 0.25)], 1.0)
        zoom.currentIndexChanged.connect(lambda: self.set_zoom(zoom.currentData()))
        preview = QPushButton("효과 미리 재생")
        preview.setAutoDefault(False)
        preview.clicked.connect(self.play)
        transport = QHBoxLayout()
        transport.addWidget(preview)
        transport.addWidget(self.progress, 1)
        transport.addWidget(zoom)
        self.timer = QTimer(self, interval=TICK)
        self.timer.timeout.connect(self.advance)
        right = QVBoxLayout()
        right.addWidget(self.sample, 1)
        right.addLayout(transport)
        body = QHBoxLayout()
        body.addLayout(left, 1)
        body.addLayout(right, 2)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(body, 1)
        layout.addWidget(buttons)
        self.refresh()
        self.resize(750, 380)

    def refresh(self, row=0):
        self.timer.stop()
        labels = {kind: label for label, kind in KINDS}
        self.layer_list.clear()
        self.layer_list.addItems([f"{layer.get('name') or labels[layer['kind']]}  ·  {layer.get('start', 0)}–{layer.get('end', 100)}%"
                                  for layer in self.layers])
        self.layer_list.setCurrentRow(min(row, len(self.layers) - 1))
        self.sample.design = None
        if self.layers:
            self.sample.design = self.design()
        self.sample.update()

    def design(self):
        return read_effect_designs({"preview-effect": {"name": "미리보기", "layers": self.layers}},
                                   self.editor.effect_image)["preview-effect"]

    def add_layer(self):
        if len(self.layers) < 12:
            self.open_layer(len(self.layers), {})

    def edit_layer(self):
        row = self.layer_list.currentRow()
        if row >= 0:
            self.open_layer(row, self.layers[row])

    def open_layer(self, row, item):
        self.timer.stop()
        dialog = LayerDialog(self, self.editor, item)
        if dialog.exec_() == QDialog.Accepted:
            self.layers[row:row + 1] = [dialog.result_layer]
            self.refresh(row)
        dialog.deleteLater()

    def remove_layer(self):
        row = self.layer_list.currentRow()
        if row >= 0:
            self.layers.pop(row)
            self.refresh(row)

    def move_layer(self, change):
        row = self.layer_list.currentRow()
        target = row + change
        if 0 <= row < len(self.layers) and 0 <= target < len(self.layers):
            self.layers[row], self.layers[target] = self.layers[target], self.layers[row]
            self.refresh(target)

    def set_zoom(self, value):
        self.sample.zoom = value
        self.sample.update()

    def seek(self, progress):
        self.sample.progress = progress
        self.sample.update()

    def play(self):
        if self.layers:
            self.progress.setValue(0)
            self.timer.start()

    def advance(self):
        self.progress.setValue(self.progress.value() + 2)
        if self.progress.value() == 100:
            self.timer.stop()

    def accept(self):
        key = self.key.text().strip()
        if key != self.original_key and key in self.definitions:
            show_error(self, "같은 ID의 효과가 이미 있어요.")
            return
        item = {"name": self.name.text().strip(), "layers": self.layers}
        try:
            read_effect_designs({**self.definitions, key: item})
        except ValueError as error:
            show_error(self, error)
            return
        self.result_effect = key, item
        super().accept()

    def done(self, result):
        self.timer.stop()
        super().done(result)


class EffectPanel(QWidget):
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self.edit)
        layout = QVBoxLayout(self)
        layout.addLayout(controls((("효과 추가…", self.add), ("편집…", self.edit), ("삭제", self.remove))))
        layout.addWidget(self.list)

    def refresh(self, selected=None):
        items = self.editor.project.rules.get("effects", {})
        self.keys = list(items)
        self.list.clear()
        self.list.addItems([f"{items[key]['name']} ({key})" for key in self.keys])
        self.list.setCurrentRow(self.keys.index(selected) if selected in items else 0)

    def add(self):
        self.open_effect(None)

    def edit(self):
        row = self.list.currentRow()
        if row >= 0:
            self.open_effect(self.keys[row])

    def open_effect(self, key):
        rules = self.editor.project.rules
        dialog = EffectDialog(self, self.editor, rules.get("effects", {}), key)
        if dialog.exec_() == QDialog.Accepted:
            new_key, item = dialog.result_effect
            rules.setdefault("effects", {})[new_key] = item
            self.editor.changed()
            self.refresh(new_key)
        dialog.deleteLater()

    def remove(self):
        row = self.list.currentRow()
        if row >= 0:
            key = self.keys[row]
            rules = self.editor.project.rules
            if any(step.get("effect", {}).get("preset") == key for step in rule_steps(rules)):
                show_error(self, "액션에서 사용 중인 효과예요. 해당 액션에서 효과를 먼저 바꾸세요.")
                return
            del rules["effects"][key]
            self.editor.changed()
            self.refresh()
