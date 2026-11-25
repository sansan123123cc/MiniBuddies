"""Edit alternate looks using the same numbered frames as built-in outfits."""

from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from minibuddies.authoring.project import SKIN_LIMIT, Skin, validate_skin_id
from minibuddies.ui.editor.frames import CharacterFrames, read_numbered_images
from minibuddies.ui.editor.widgets import show_error


class SkinDetails(QDialog):
    def __init__(self, parent, current_id, name, occupied):
        super().__init__(parent)
        self.setWindowTitle("스킨 정보")
        self.occupied = occupied
        self.key = QLineEdit(current_id)
        self.key.setMaxLength(48)
        self.key.setPlaceholderText("예: spring")
        self.name = QLineEdit(name)
        self.name.setMaxLength(80)
        form = QFormLayout()
        form.addRow("스킨 ID", self.key)
        form.addRow("표시 이름", self.name)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("확인")
        buttons.button(QDialogButtonBox.Cancel).setText("취소")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def accept(self):
        key = self.key.text().strip()
        try:
            validate_skin_id(key)
            if not self.name.text().strip():
                raise ValueError("스킨 이름을 입력하세요.")
            if key in self.occupied:
                raise ValueError("팩에 같은 스킨 ID가 있어요.")
        except ValueError as error:
            show_error(self, error)
            return
        self.result_skin = key, self.name.text().strip()
        super().accept()


class SkinPanel(QWidget):
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.keys = []
        self.list = QListWidget()
        self.list.setMaximumWidth(200)
        self.frame_editor = CharacterFrames(editor, self.current_frames)
        tools = QHBoxLayout()
        for label, handler in (("스킨 추가…", self.add), ("스킨 폴더 가져오기…", self.import_folder),
                               ("이름·ID 편집…", self.rename), ("선택 삭제", self.remove)):
            button = QPushButton(label)
            button.setAutoDefault(False)
            button.clicked.connect(handler)
            tools.addWidget(button)
        tools.addStretch()
        body = QHBoxLayout()
        body.addWidget(self.list, 1)
        body.addWidget(self.frame_editor, 4)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("스킨을 고르고 캐릭터와 동일한 프레임 번호로 PNG를 넣으세요."))
        layout.addLayout(tools)
        layout.addLayout(body, 1)
        self.list.currentRowChanged.connect(self.selection_changed)
        self.list.itemDoubleClicked.connect(self.rename)

    def current_key(self):
        row = self.list.currentRow()
        return self.keys[row] if 0 <= row < len(self.keys) else ""

    def current_frames(self):
        skin = self.editor.project.skins.get(self.current_key())
        return skin.frames if skin else {}

    def selection_changed(self):
        self.frame_editor.setEnabled(bool(self.current_key()))
        self.frame_editor.refresh()

    def refresh(self, selected=""):
        self.keys = list(self.editor.project.skins)
        self.list.blockSignals(True)
        self.list.clear()
        for key in self.keys:
            self.list.addItem(f"{self.editor.project.skins[key].name} ({key})")
        self.list.setCurrentRow(self.keys.index(selected) if selected in self.keys else 0)
        self.list.blockSignals(False)
        self.selection_changed()

    def edit_skin(self, old, name, frames, *, suggested_id=""):
        if not old and len(self.editor.project.skins) >= SKIN_LIMIT:
            show_error(self, f"한 팩에 스킨을 최대 {SKIN_LIMIT}개 넣을 수 있어요.")
            return
        occupied = set(self.editor.project.skins) - {old}
        dialog = SkinDetails(self, old or suggested_id, name, occupied)
        if dialog.exec_() != QDialog.Accepted:
            return
        key, label = dialog.result_skin
        if old:
            del self.editor.project.skins[old]
        self.editor.project.skins[key] = Skin(label, frames)
        self.editor.changed()
        self.refresh(key)

    def add(self):
        self.edit_skin("", "", {})

    def import_folder(self):
        directory = QFileDialog.getExistingDirectory(self, "번호가 붙은 PNG가 있는 스킨 폴더 선택")
        if not directory:
            return
        folder = Path(directory)
        try:
            files = [path for path in folder.iterdir() if path.is_file() and path.suffix.lower() == ".png" and path.stem.isdecimal()]
            frames = read_numbered_images(files)
            if 0 not in frames:
                raise ValueError("스킨 폴더에 0.png가 필요해요.")
            name_file = folder / "name.txt"
            name = name_file.read_text(encoding="utf-8-sig").strip() if name_file.is_file() else folder.name
        except (OSError, ValueError) as error:
            show_error(self, error)
            return
        self.edit_skin("", name, frames, suggested_id=folder.name.rsplit("@", 1)[-1])

    def rename(self):
        key = self.current_key()
        if key:
            skin = self.editor.project.skins[key]
            self.edit_skin(key, skin.name, skin.frames)

    def remove(self):
        key = self.current_key()
        if key and QMessageBox.question(self, "스킨 삭제", "선택한 스킨과 프레임을 편집 중인 팩에서 지울까요?") == QMessageBox.Yes:
            del self.editor.project.skins[key]
            self.editor.changed()
            self.refresh()
