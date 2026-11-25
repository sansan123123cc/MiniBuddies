import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication, QColorDialog, QDialog, QFileDialog, QWidget

from minibuddies.controllers import windows
from minibuddies.ui.editor.dialog import PackEditor
from minibuddies.ui.editor.rules import RuleDialog
from minibuddies.ui.editor.steps import StepDialog
from minibuddies.ui.menus import AppMenus
from minibuddies.ui.window_order import native_dialog_open, run_native_dialog


class WindowOrderTest(unittest.TestCase):
    def setUp(self):
        self.qapp = QApplication.instance() or QApplication([])
        self.controller = windows.WindowController()
        self.controller.on_top = True

    def show(self, widget, *, modal=False):
        if modal:
            widget.setWindowModality(Qt.ApplicationModal)
        self.addCleanup(widget.close)
        widget.show()
        self.qapp.processEvents()
        return widget

    def editor(self):
        return self.show(PackEditor(SimpleNamespace(chars={}, mode="reimu")), modal=True)

    def assert_promoted(self, promote, *widgets):
        self.assertEqual(
            [(int(wid), on, force) for (wid, on, force), _ in promote.call_args_list],
            [(int(widget.winId()), True, True) for widget in widgets],
        )

    def test_periodic_refresh_promotes_only_the_innermost_editor_dialog(self):
        editor = self.editor()
        rule = self.show(RuleDialog(editor, "interactions", {}), modal=True)
        action = self.show(StepDialog(rule, editor, {"frame": 0}, True, "reimu", ["reimu", "marisa"]), modal=True)
        self.assertIs(self.qapp.activeModalWidget(), action)

        with patch.object(windows.QApplication, "topLevelWidgets", return_value=[action, rule, editor]), \
                patch.object(windows, "set_topmost") as promote, patch.object(self.controller, "pet_windows") as pets:
            self.controller.keep_on_top(force=True)
            self.assert_promoted(promote, action)
            pets.assert_not_called()

            action.close()
            promote.reset_mock()
            self.controller.keep_on_top()
            self.assert_promoted(promote, rule)
            rule.close()
            promote.reset_mock()
            self.controller.keep_on_top()
            self.assert_promoted(promote, editor)

    def test_modeless_dialogs_and_popups_are_promoted_above_their_owners(self):
        parent = self.show(QDialog())
        child = self.show(QDialog(QWidget(parent)))
        dropdown = self.show(QWidget(child, Qt.Popup))
        self.assertIsNone(self.qapp.activeModalWidget())

        with patch.object(windows.QApplication, "topLevelWidgets", return_value=[dropdown, child, parent]), \
                patch.object(windows, "set_topmost") as promote:
            self.controller.raise_popups()
        self.assert_promoted(promote, parent, child, dropdown)

    def test_native_file_and_color_pickers_suspend_even_forced_refresh(self):
        editor = self.editor()
        action = self.show(StepDialog(editor, editor, {}, True, "reimu", ["reimu", "marisa"]), modal=True)

        def native_result(value):
            self.assertTrue(native_dialog_open())
            self.controller.keep_on_top(force=True)
            self.controller.raise_popups()
            return value

        with patch.object(windows, "set_topmost") as promote:
            with patch.object(QFileDialog, "getOpenFileName", side_effect=lambda *args: native_result(("", ""))):
                editor.open_pack()
            with patch.object(QColorDialog, "getColor", side_effect=lambda *args: native_result(QColor())):
                action.add_color()
            promote.assert_not_called()
            self.assertFalse(native_dialog_open())
            self.controller.keep_on_top(force=True)
            self.assert_promoted(promote, action)

        def failed_picker():
            raise OSError("picker failed")

        with self.assertRaises(OSError):
            run_native_dialog(failed_picker)
        self.assertFalse(native_dialog_open())

    def test_open_settings_does_not_raise_a_parent_while_a_modal_is_active(self):
        settings = self.show(QDialog())
        self.show(QDialog(settings), modal=True)
        app = AppMenus()
        app.settings_dlg = settings
        with patch.object(settings, "raise_") as raise_settings, patch.object(settings, "activateWindow") as activate:
            app.open_settings("에디터")
            raise_settings.assert_not_called()
            activate.assert_not_called()
