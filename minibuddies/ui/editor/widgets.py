"""Common image and form widgets for the pack editor."""

from PyQt5.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PyQt5.QtGui import QImageReader, QPixmap
from PyQt5.QtWidgets import QComboBox, QFileDialog, QLabel, QMessageBox, QSpinBox

from minibuddies.authoring.project import read_image
from minibuddies.ui.window_order import run_native_dialog


def show_error(parent, error):
    box = QMessageBox(QMessageBox.Warning, "MiniBuddies 에디터", str(error), parent=parent)
    box.setTextFormat(Qt.PlainText)
    box.exec_()


def image_file(parent):
    path, _ = run_native_dialog(QFileDialog.getOpenFileName, parent, "스프라이트 PNG 고르기", "", "PNG (*.png)")
    if not path:
        return None
    try:
        return read_image(path)
    except (OSError, ValueError) as error:
        show_error(parent, error)
        return None


def image_pixmap(data):
    if not data:
        return QPixmap()
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QIODevice.ReadOnly)
    reader = QImageReader(buffer, b"png")
    if reader.size().width() != 256 or reader.size().height() != 256:
        return QPixmap()
    return QPixmap.fromImage(reader.read())


class SpritePreview(QLabel):
    def __init__(self, size=164):
        super().__init__()
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        self.setTextFormat(Qt.PlainText)
        self.setStyleSheet("background:#30293e;color:#e8dbe8;border-radius:12px;")
        self.display(None)

    def display(self, data):
        pixmap = image_pixmap(data)
        if pixmap.isNull():
            self.setText("미리보기 없음")
        else:
            self.setPixmap(pixmap.scaled(self.width() - 20, self.height() - 20,
                                         Qt.KeepAspectRatio, Qt.SmoothTransformation))


def options(items, selected=None):
    combo = QComboBox()
    for label, key in items:
        combo.addItem(label, key)
    index = combo.findData(selected)
    if index >= 0:
        combo.setCurrentIndex(index)
    return combo


def spin(lo, hi, value, suffix=""):
    box = QSpinBox()
    box.setRange(lo, hi)
    box.setValue(value)
    box.setSuffix(suffix)
    return box
