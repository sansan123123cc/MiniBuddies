"""Shared pack preview for opening and installing archives."""

from zipfile import BadZipFile

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout

from minibuddies.ui.editor.widgets import SpritePreview


PACK_FILTER = "MiniBuddies 팩 (*.mbpack *.zip)"
PACK_ERRORS = (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError, BadZipFile)
PACK_KINDS = {"character": "캐릭터", "plugin": "플러그인", "skin": "스킨 팩"}


def archive_preview(parent, info, cover, *, accept_text="에디터에서 열기"):
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
    buttons.addButton(accept_text, QDialogButtonBox.AcceptRole)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout = QVBoxLayout(dialog)
    layout.addLayout(content)
    layout.addWidget(buttons)
    dialog.resize(510, 250)
    return dialog.exec_() == QDialog.Accepted
