"""Assign PNG sprites to built-in character frame slots."""

from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFileDialog, QFormLayout, QHBoxLayout, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget

from minibuddies.authoring.project import FRAME_LIMIT, read_image
from minibuddies.ui.editor.widgets import SpritePreview, image_file, show_error, spin
from minibuddies.ui.window_order import run_native_dialog

FRAME_NAMES = {0: "기본 자세", 1: "걷기", 2: "걷기", 3: "걷기", 4: "구르기", 5: "떨어지기", 6: "착지", 7: "잠자기",
               8: "달리기", 9: "달리기", 10: "점프", 11: "환호", 12: "손 흔들기", 13: "매달리기", 14: "올라가기",
               15: "먹기", 16: "울기", 17: "살짝 보기", 18: "걸터앉기", 19: "하품"}


def read_numbered_images(files):
    if len(files) > FRAME_LIMIT:
        raise ValueError(f"프레임은 최대 {FRAME_LIMIT}장까지 넣을 수 있어요.")
    result = {}
    for file in files:
        path = Path(file)
        if not path.stem.isascii() or not path.stem.isdecimal() or len(path.stem) > 4:
            raise ValueError(f"일괄 추가 파일은 0.png처럼 번호로 이름을 붙이세요. {path.name}")
        number = int(path.stem)
        if number in result:
            raise ValueError(f"{number}번 프레임이 중복됐어요.")
        result[number] = read_image(path)
    return result


class CharacterFrames(QWidget):
    def __init__(self, editor, get_frames=None):
        super().__init__()
        self.editor = editor
        self.get_frames = get_frames or (lambda: editor.project.frames)
        self.list = QListWidget()
        self.preview = SpritePreview(184)
        self.number = spin(0, 9999, 0)
        self.summary = QLabel()
        self.summary.setTextFormat(Qt.PlainText)
        tools = QHBoxLayout()
        for label, handler in (("PNG 넣기…", self.add_image), ("PNG 일괄 추가…", self.add_many), ("선택 삭제", self.remove)):
            button = QPushButton(label)
            button.clicked.connect(handler)
            tools.addWidget(button)
        tools.addStretch(1)
        side = QVBoxLayout()
        side.addWidget(self.preview)
        side.addStretch()
        form = QFormLayout()
        form.addRow("프레임 번호", self.number)
        body = QHBoxLayout()
        body.addWidget(self.list, 1)
        body.addLayout(side)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("0번은 기본 자세예요. PNG는 투명 배경 256×256로 준비하세요."))
        layout.addLayout(form)
        layout.addLayout(tools)
        layout.addLayout(body, 1)
        layout.addWidget(self.summary)
        self.list.currentRowChanged.connect(self.select)

    def refresh(self, selected=None):
        self.numbers = sorted(self.get_frames())
        self.list.clear()
        for number in self.numbers:
            self.list.addItem(f"{number} · {FRAME_NAMES[number]}" if number in FRAME_NAMES else str(number))
        self.summary.setText(f"프레임 {len(self.numbers)}장" + (" · 기본 자세 필요" if 0 not in self.numbers else ""))
        self.list.setCurrentRow(self.numbers.index(selected) if selected in self.numbers else 0)
        if not self.numbers:
            self.preview.display(None)

    def select(self, row):
        if row >= 0:
            number = self.numbers[row]
            self.number.setValue(number)
            self.preview.display(self.get_frames()[number])

    def add_image(self):
        number = self.number.value()
        data = image_file(self)
        if data is not None:
            self.store({number: data}, number)

    def add_many(self):
        files, _ = run_native_dialog(QFileDialog.getOpenFileNames, self, "번호가 붙은 PNG 프레임 가져오기", "", "PNG (*.png)")
        if not files:
            return
        try:
            new = read_numbered_images(files)
        except (OSError, ValueError) as error:
            show_error(self, error)
            return
        self.store(new, min(new))

    def store(self, new, selected):
        frames = self.get_frames()
        if len(set(frames) | set(new)) > FRAME_LIMIT:
            show_error(self, "프레임은 최대 256장까지 넣을 수 있어요.")
            return
        frames.update(new)
        self.editor.changed()
        self.refresh(selected)

    def remove(self):
        row = self.list.currentRow()
        if row >= 0:
            del self.get_frames()[self.numbers[row]]
            self.editor.changed()
            self.refresh()
