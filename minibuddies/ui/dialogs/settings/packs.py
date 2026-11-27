"""Install, list, and remove user packs from settings."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFileDialog, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QSizePolicy,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from minibuddies.authoring.archive import inspect_archive, load_archive
from minibuddies.authoring.installed import install_into, installed_packs, uninstall_from
from minibuddies.ui.pack_dialogs import PACK_ERRORS, PACK_FILTER, PACK_KINDS, archive_preview
from minibuddies.ui.window_order import run_native_dialog


class InstalledPacks(QGroupBox):
    removed = pyqtSignal()

    def __init__(self, app, parent=None):
        super().__init__("설치한 팩", parent)
        self.app = app
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.list = QTreeWidget()
        self.list.setHeaderLabels(["이름", "종류", "팩 ID"])
        self.list.setRootIsDecorated(False)
        self.list.setAlternatingRowColors(True)
        self.list.setMinimumHeight(160)
        self.list.setMaximumHeight(288)
        self.list.setStyleSheet(
            "QTreeWidget{background:white;alternate-background-color:#fff8fb;border:1px solid #f0c3d6;border-radius:8px;}"
            "QTreeWidget::item{padding:4px 6px;}"
            "QTreeWidget::item:selected{background:#ffd6ea;color:#7a2350;}"
        )
        self.list.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.list.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.list.header().setSectionResizeMode(2, QHeaderView.Interactive)
        self.list.header().resizeSection(2, 214)
        self.list.header().setStretchLastSection(False)
        self.list.currentItemChanged.connect(self.selection_changed)
        self.empty = QLabel("설치된 팩이 없어요.")
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        self.status.hide()
        self.install_button = QPushButton("팩 설치…")
        self.install_button.setAutoDefault(False)
        self.install_button.clicked.connect(self.install_pack)
        self.delete_button = QPushButton("선택한 팩 삭제…")
        self.delete_button.setAutoDefault(False)
        self.delete_button.clicked.connect(self.delete_selected)
        buttons = QHBoxLayout()
        buttons.addWidget(self.install_button)
        buttons.addStretch(1)
        buttons.addWidget(self.delete_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.list)
        layout.addWidget(self.empty)
        layout.addLayout(buttons)
        layout.addWidget(self.status)
        self.refresh()

    def selection_changed(self):
        self.delete_button.setEnabled(self.list.currentItem() is not None)

    def show_status(self, text):
        self.status.setText(text)
        self.status.show()

    def refresh(self, key=None):
        current = self.list.currentItem()
        if key is None and current:
            key = current.text(2)
        try:
            packs = installed_packs(self.app.content_root)
        except OSError:
            packs = []
            self.show_status("설치한 팩 목록을 읽지 못했어요.")
        self.list.clear()
        selected = None
        for info in packs:
            item = QTreeWidgetItem([info["name"], PACK_KINDS[info["kind"]], info["id"]])
            item.setToolTip(2, info["id"])
            self.list.addTopLevelItem(item)
            if info["id"] == key:
                selected = item
        self.list.setCurrentItem(selected or self.list.topLevelItem(0))
        self.list.setVisible(bool(packs))
        self.empty.setVisible(not packs)
        self.selection_changed()

    def install_pack(self):
        try:
            path, _ = run_native_dialog(QFileDialog.getOpenFileName, self, "MiniBuddies 팩 설치", "", PACK_FILTER)
            if not path:
                return
            info, cover = inspect_archive(path)
            if not archive_preview(self, info, cover, accept_text="이 PC에 설치"):
                return
            project = load_archive(path)
            install_into(self.app, project)
        except PACK_ERRORS as error:
            self.show_status(str(error))
            return
        self.refresh(project.id)
        self.show_status(f"‘{project.name}’ 팩을 설치했어요.")

    def confirm_delete(self, name, key):
        confirm = QMessageBox(QMessageBox.Question, "팩 삭제", "", parent=self)
        confirm.setTextFormat(Qt.PlainText)
        confirm.setText(f"‘{name}’ ({key}) 팩을 휴지통으로 옮길까요?")
        delete = confirm.addButton("삭제", QMessageBox.AcceptRole)
        cancel = confirm.addButton("취소", QMessageBox.RejectRole)
        confirm.setDefaultButton(cancel)
        confirm.setEscapeButton(cancel)
        confirm.exec_()
        return confirm.clickedButton() is delete

    def delete_selected(self):
        selected = self.list.currentItem()
        if selected is None:
            return
        name, key = selected.text(0), selected.text(2)
        if not self.confirm_delete(name, key):
            return
        try:
            saved = uninstall_from(self.app, key)
        except (OSError, ValueError, RuntimeError) as error:
            self.show_status(str(error))
            self.refresh()
            return
        self.refresh()
        self.show_status(f"‘{name}’ 팩을 휴지통으로 옮겼어요." if saved
                         else "팩을 휴지통으로 옮겼어요. 설정을 저장하지 못했어요.")
        self.removed.emit()
