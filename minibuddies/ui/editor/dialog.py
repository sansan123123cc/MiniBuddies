"""Settings entry point and project-level creation/import/export controls."""

from pathlib import Path
from zipfile import BadZipFile

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from minibuddies.authoring.archive import EXTENSION, export_archive, inspect_archive, load_archive
from minibuddies.authoring.installed import install_into
from minibuddies.authoring.project import IMAGE_LIMIT, Project, load_legacy
from minibuddies.ui.editor.effects import EffectPanel
from minibuddies.ui.editor.frames import CharacterFrames
from minibuddies.ui.editor.rules import RuleList
from minibuddies.ui.editor.skins import SkinPanel
from minibuddies.ui.editor.widgets import SpritePreview, image_file, image_pixmap, show_error
from minibuddies.ui.window_order import run_native_dialog

PACK_FILTER = "MiniBuddies 팩 (*.mbpack *.zip)"
PACK_ERRORS = (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError, BadZipFile)
PACK_KINDS = {"character": "캐릭터", "plugin": "플러그인", "skin": "스킨 팩"}


def line(limit):
    widget = QLineEdit()
    widget.setMaxLength(limit)
    return widget


def archive_preview(parent, info, cover):
    dialog = QDialog(parent)
    dialog.setWindowTitle("MiniBuddies 팩 미리보기")
    sprite = SpritePreview(180)
    sprite.display(cover)
    title = QLabel(info["name"])
    title.setTextFormat(Qt.PlainText)
    title.setStyleSheet("font-size:16pt;font-weight:bold;")
    target = f"대상 {info['target']}" if info["kind"] == "skin" else ""
    details = QLabel(" · ".join(value for value in (PACK_KINDS[info["kind"]], info["id"], info.get("author"), target) if value))
    details.setTextFormat(Qt.PlainText)
    counts = QLabel(f"개별 동작 {info['actions']} · 상호작용 {info['interactions']} · 기본 프레임 {info['frames']}"
                    + (f" · 스킨 {len(info['skins'])}개" if info.get("skins") else "")
                    + (f" · 효과 {info['effects']}개" if info.get("effects") else ""))
    counts.setWordWrap(True)
    description = QPlainTextEdit(info.get("description", ""))
    description.setReadOnly(True)
    description.setPlaceholderText("설명 없음")
    fields = QVBoxLayout()
    fields.addWidget(title)
    fields.addWidget(details)
    fields.addWidget(counts)
    fields.addWidget(description)
    content = QHBoxLayout()
    content.addWidget(sprite)
    content.addLayout(fields, 1)
    buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
    buttons.addButton("에디터에서 열기", QDialogButtonBox.AcceptRole)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout = QVBoxLayout(dialog)
    layout.addLayout(content)
    layout.addWidget(buttons)
    dialog.resize(510, 250)
    return dialog.exec_() == QDialog.Accepted


class PackEditor(QDialog):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.setWindowTitle("MiniBuddies 제작 에디터")
        self.resize(830, 600)
        self.setMinimumSize(660, 460)
        self.id = line(48)
        self.id.setPlaceholderText("예: starlight-duet")
        self.name = line(80)
        self.author = line(80)
        self.description = QPlainTextEdit()
        self.description.setMaximumHeight(110)
        self.preview = SpritePreview(196)
        self.kind = QLabel()
        self.target_label = QLabel("대상 캐릭터")
        self.target = QComboBox()
        self.target.setEditable(True)
        self.target.setInsertPolicy(QComboBox.NoInsert)
        self.target.lineEdit().setPlaceholderText("캐릭터를 고르거나 ID 입력")
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        self.tabs = QTabWidget()
        self.frames = CharacterFrames(self)
        self.rules = RuleList(self)
        self.skins = SkinPanel(self)
        self.effects = EffectPanel(self)
        self.controls = QHBoxLayout()
        self.import_button = QPushButton("팩 가져오기…")
        for button, handler in ((QPushButton("새 플러그인"), lambda: self.new("plugin")),
                                (QPushButton("새 캐릭터"), lambda: self.new("character")),
                                (QPushButton("새 스킨 팩"), lambda: self.new("skin")),
                                (self.import_button, self.open_pack), (QPushButton("기존 플러그인 열기…"), self.open_legacy)):
            button.clicked.connect(handler)
            self.controls.addWidget(button)
        self.controls.addStretch()
        layout = QVBoxLayout(self)
        layout.addLayout(self.controls)
        layout.addWidget(self.tabs, 1)
        layout.addWidget(self.status)
        self.tabs.addTab(self.info_page(), "팩 정보")
        self.tabs.addTab(self.frames, "캐릭터 프레임")
        self.tabs.addTab(self.rules, "트리거 · 조건 · 액션")
        self.tabs.addTab(self.skins, "스킨")
        self.tabs.addTab(self.effects, "효과")
        footer = QHBoxLayout()
        footer.addStretch()
        for label, handler in (("이 PC에 설치", self.install), ("팩 내보내기…", self.export), ("닫기", self.reject)):
            button = QPushButton(label)
            button.clicked.connect(handler)
            footer.addWidget(button)
        layout.addLayout(footer)
        # A file dialog can leave Qt looking for a new default on the editor, including in hidden tabs.
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)
            button.setDefault(False)
        for field in (self.id, self.name, self.author, self.description):
            field.textChanged.connect(self.metadata_changed)
        self.target.currentTextChanged.connect(self.metadata_changed)
        self.load(Project())

    def info_page(self):
        page = QWidget()
        form = QFormLayout()
        for label, widget in (("팩 종류", self.kind), (self.target_label, self.target), ("이름", self.name),
                              ("팩 ID", self.id), ("제작자", self.author), ("설명", self.description)):
            form.addRow(label, widget)
        cover = QPushButton("대표 이미지 선택…")
        cover.clicked.connect(self.choose_cover)
        reset = QPushButton("자동 이미지 사용")
        reset.clicked.connect(self.reset_cover)
        side = QVBoxLayout()
        side.addWidget(self.preview)
        side.addWidget(cover)
        side.addWidget(reset)
        side.addStretch()
        view = QHBoxLayout(page)
        view.addLayout(form, 1)
        view.addLayout(side)
        return page

    def load(self, project):
        self.loading = True
        self.project = project
        self.id.setText(project.id)
        self.name.setText(project.name)
        self.author.setText(project.author)
        self.description.setPlainText(project.description)
        self.kind.setText(PACK_KINDS[project.kind])
        self.target_label.setVisible(project.kind == "skin")
        self.target.setVisible(project.kind == "skin")
        self.target.clear()
        if project.kind == "skin":
            for key in self.known_characters():
                self.target.addItem(self.character_label(key), key)
            index = self.target.findData(project.target)
            self.target.setCurrentIndex(index)
            if index < 0:
                self.target.setEditText(project.target)
        self.tabs.setTabVisible(self.tabs.indexOf(self.frames), project.kind == "character")
        self.tabs.setTabVisible(self.tabs.indexOf(self.skins), project.kind in ("character", "skin"))
        self.tabs.setCurrentIndex(0)
        self.frames.refresh()
        self.rules.refresh()
        self.skins.refresh()
        self.effects.refresh()
        self.preview.display(self.project.thumbnail() or self.step_image({"frame": 0}, self.preview_actor()))
        self.status.clear()
        self.dirty = self.loading = False
        self.name.setFocus(Qt.OtherFocusReason)

    def metadata_changed(self):
        if not self.loading:
            self.dirty = True

    def changed(self):
        self.dirty = True
        self.status.clear()
        self.preview.display(self.project.thumbnail() or self.step_image({"frame": 0}, self.preview_actor()))

    def sync_metadata(self):
        project = self.project
        new_id = self.id.text().strip()
        if project.kind == "character" and project.id and new_id and project.id != new_id:
            old = project.id
            for entry in [project.rules, *project.rules.get("actions", [])]:
                if "characters" in entry:
                    entry["characters"] = list(dict.fromkeys(new_id if key == old else key for key in entry["characters"]))
            for scene in project.rules.get("interactions", []):
                for role in scene["roles"]:
                    if role["character"] == old:
                        role["character"] = new_id
                    for step in role["steps"]:
                        if step.get("effect", {}).get("target") == old:
                            step["effect"]["target"] = new_id
        project.id = new_id
        project.name = self.name.text().strip()
        project.author = self.author.text().strip()
        project.description = self.description.toPlainText().strip()
        if project.kind == "skin":
            target = self.target.currentText().strip()
            index = self.target.findText(target)
            project.target = self.target.itemData(index) if index >= 0 else target

    def known_characters(self):
        keys = list(self.app.chars)
        if self.project.kind == "character" and self.project.id and self.project.id not in keys:
            keys.insert(0, self.project.id)
        return keys

    def character_label(self, key, *, include_id=True):
        if self.project.kind == "character" and key == self.project.id:
            label = self.project.name or key
            return f"{label} ({key})" if include_id else label
        record = self.app.chars.get(key) or {}
        if "label" in record:
            return f"{record['label']} ({key})" if include_id else record["label"]
        return key

    def preview_actor(self):
        project = self.project
        if project.kind == "character":
            return project.id
        if project.kind == "skin":
            return project.target
        roles = next((scene["roles"] for scene in project.rules.get("interactions", [])), [])
        if roles:
            return roles[0]["character"]
        for action in project.rules.get("actions", []):
            if action.get("characters"):
                return action["characters"][0]
        return self.app.mode

    def step_image(self, step, key):
        if "file" in step:
            return self.project.assets.get(step["file"])
        number = step.get("frame", 0)
        if self.project.kind == "character" and key == self.project.id:
            return self.project.frames.get(number)
        record = self.app.chars.get(key) or {}
        if "dir" in record:
            try:
                path = Path(record["dir"]) / f"{number}.png"
                if path.stat().st_size <= IMAGE_LIMIT:
                    return path.read_bytes()
            except OSError:
                pass
        return None

    def effect_image(self, file):
        image = image_pixmap(self.project.assets.get(file)).toImage()
        if image.isNull():
            raise ValueError("효과에 사용할 PNG가 팩에 없어요")
        return image

    def choose_cover(self):
        data = image_file(self)
        if data is not None:
            self.project.cover = data
            self.changed()

    def reset_cover(self):
        self.project.cover = None
        self.changed()

    def discard_ok(self):
        return not self.dirty or QMessageBox.question(self, "편집 내용",
            "아직 내보내지 않은 변경이 있어요. 현재 편집을 그만둘까요?",
            QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel) == QMessageBox.Discard

    def new(self, kind):
        if self.discard_ok():
            self.load(Project(kind=kind, target=self.app.mode if kind == "skin" else ""))

    def open_pack(self):
        try:
            path, _ = run_native_dialog(QFileDialog.getOpenFileName, self, "MiniBuddies 팩 가져오기", "", PACK_FILTER)
            if not path:
                return
            info, cover = inspect_archive(path)
            if archive_preview(self, info, cover) and self.discard_ok():
                self.load(load_archive(path))
                self.status.setText("팩을 열었어요. 편집하거나 이 PC에 설치할 수 있어요.")
        except PACK_ERRORS as error:
            show_error(self, error)
        finally:
            self.import_button.setFocus(Qt.OtherFocusReason)

    def open_legacy(self):
        path, _ = run_native_dialog(QFileDialog.getOpenFileName, self, "기존 플러그인 열기",
                                    str(self.app.plugins.root), "플러그인 (plugin.json)")
        if path and self.discard_ok():
            try:
                self.load(load_legacy(Path(path).parent))
            except PACK_ERRORS as error:
                show_error(self, error)

    def prepare(self):
        self.sync_metadata()
        if self.project.thumbnail() is None:
            return self.step_image({"frame": 0}, self.preview_actor())
        return None

    def export(self):
        preview = self.prepare()
        suggested = (self.project.id or "minibuddies-pack") + EXTENSION
        path, _ = run_native_dialog(QFileDialog.getSaveFileName, self, "MiniBuddies 팩 내보내기", suggested, PACK_FILTER)
        if not path:
            return
        target = Path(path)
        if target.suffix.lower() not in (EXTENSION, ".zip"):
            target = target.with_name(target.name + EXTENSION)
            if target.exists() and QMessageBox.question(self, "파일 교체", "같은 이름의 팩 파일을 교체할까요?") != QMessageBox.Yes:
                return
        try:
            if preview:
                self.project.cover = preview
            export_archive(self.project, target)
            self.dirty = False
            self.status.setText(f"팩을 내보냈어요. {target.name}")
        except PACK_ERRORS as error:
            show_error(self, error)

    def install(self):
        preview = self.prepare()
        try:
            if preview:
                self.project.cover = preview
            install_into(self.app, self.project)
            self.dirty = False
            if self.project.kind == "skin":
                self.status.setText("설치했어요. 대상 펫을 우클릭하고 옷 갈아입기 또는 모습 바꾸기에서 스킨을 고르세요.")
            else:
                self.status.setText("설치했어요. 환경설정의 캐릭터 탭을 다시 열거나 펫의 플러그인 메뉴에서 사용할 수 있어요.")
        except PACK_ERRORS as error:
            show_error(self, error)

    def reject(self):
        if self.discard_ok():
            super().reject()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not isinstance(self.focusWidget(), QPushButton):
            event.accept()
            return
        super().keyPressEvent(event)
