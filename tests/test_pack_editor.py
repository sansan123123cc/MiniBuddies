import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QImage, QPainter
from PyQt5.QtWidgets import QDialog, QFileDialog, QInputDialog, QPushButton

from minibuddies import app as application
from minibuddies.authoring.archive import export_archive, inspect_archive, load_archive
from minibuddies.authoring.project import Project
from minibuddies.ui.editor import dialog as editor_ui
from minibuddies.ui.editor.rules import RuleDialog
from minibuddies.ui.editor.steps import StepDialog


def make_png(path, color):
    path.parent.mkdir(parents=True, exist_ok=True)
    image = QImage(256, 256, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.fillRect(55, 38, 150, 185, QColor(color))
    painter.end()
    if not image.save(str(path)):
        raise RuntimeError("Unable to create the test sprite")
    return path.read_bytes()


class PackEditorIntegrationTest(unittest.TestCase):
    def test_settings_editor_character_and_rules_round_trip(self):
        directory = Path(self.enterContext(TemporaryDirectory(prefix="mbpack-ui-")))
        sprites = directory / "chars"
        make_png(sprites / "reimu" / "0.png", "#de527e")
        make_png(sprites / "marisa" / "0.png", "#dda74d")
        (directory / "roster.txt").write_text("reimu+marisa!", encoding="utf-8")
        cfg_path = directory / "settings.json"
        cfg_path.write_text(json.dumps({"active": ["reimu", "marisa"], "mcp": False, "weather": False,
                                        "climb": False, "on_top": False, "cursor_avoid": False}), encoding="utf-8")
        with patch.object(application, "BASE", str(directory)), patch.object(application, "CHARS_DIR", str(sprites)), \
                patch.object(sys, "argv", [str(directory / "buddies.py")]):
            app = application.App()
        self.addCleanup(app.lock.close)
        app.open_settings("에디터")
        settings = app.settings_dlg
        self.assertEqual(settings.tabs.tabText(settings.tabs.currentIndex()), "에디터")
        self.addCleanup(settings.close)
        launched = []
        with patch.object(editor_ui.PackEditor, "exec_", lambda editor: launched.append(editor) or QDialog.Rejected):
            next(button for button in settings.findChildren(QPushButton) if button.text() == "제작 에디터 열기…").click()
        self.assertEqual(len(launched), 1)
        editor = launched[0]
        self.addCleanup(editor.deleteLater)
        editor.new("character")
        editor.id.setText("star-cat")
        editor.name.setText("별빛 고양이")
        editor.author.setText("제작자")
        editor.description.setPlainText("별빛을 주고받는 테스트 캐릭터")
        self.assertTrue(editor.tabs.isTabVisible(1))
        artwork = make_png(directory / "0.png", "#7b75ca")
        with patch.object(QFileDialog, "getOpenFileName", return_value=(str(directory / "0.png"), "")):
            editor.frames.add_image()
        self.assertEqual(editor.project.frames[0], artwork)

        def edit_solo(rule):
            rule.name.setText("인사하기")
            rule.trigger.setCurrentIndex(1)
            rule.chance.setValue(12.5)
            rule.speech.setText("안녕하세요!")
            rule.timeline.add()
            rule.accept()
            return rule.result()

        def edit_group(rule):
            rule.name.setText("별빛 교환")
            rule.distance.setValue(420)
            for char in ("star-cat", "marisa"):
                with patch.object(QInputDialog, "getItem", return_value=(char, True)):
                    rule.add_character()
            rule.cast.setCurrentRow(0)
            rule.timeline.add()
            rule.cast.setCurrentRow(1)
            rule.timeline.add()
            rule.accept()
            return rule.result()

        def save_step(step):
            if step.group and step.actor == "star-cat":
                step.preset.setCurrentIndex(step.preset.findData("seal"))
            step.accept()
            return step.result()

        with patch.object(StepDialog, "exec_", save_step):
            with patch.object(RuleDialog, "exec_", edit_solo):
                editor.rules.add("actions")
            with patch.object(RuleDialog, "exec_", edit_group):
                editor.rules.add("interactions")
        self.assertEqual(editor.project.rules["actions"][0]["idle_chance"], 0.125)
        self.assertEqual(editor.project.rules["actions"][0]["characters"], ["star-cat"])
        self.assertEqual(editor.project.rules["interactions"][0]["roles"][0]["steps"][0]["effect"]["target"], "marisa")

        archive = directory / "character.mbpack"
        with patch.object(QFileDialog, "getSaveFileName", return_value=(str(archive), "")):
            editor.export()
        info, cover = inspect_archive(archive)
        self.assertEqual((info["kind"], info["author"], info["actions"], info["interactions"]), ("character", "제작자", 1, 1))
        self.assertEqual(cover, artwork)
        imported = editor_ui.PackEditor(app)
        self.addCleanup(imported.deleteLater)
        with patch.object(QFileDialog, "getOpenFileName", return_value=(str(archive), "")), \
                patch.object(editor_ui, "archive_preview", return_value=True) as preview:
            imported.open_pack()
        preview.assert_called_once()
        self.assertEqual(imported.project.description, info["description"])
        imported.install()
        self.assertIn("star-cat", app.roster)
        self.assertEqual(app.chars["star-cat"]["label"], "별빛 고양이")
        self.assertTrue((directory / "user-packs" / "star-cat" / "character" / "meta.json").is_file())
        self.assertFalse((sprites / "star-cat").exists())
        app.set_team([*app.team, "star-cat"])
        app.add(entrance="drop", char="star-cat")
        cat = app.buddies[-1]
        self.addCleanup(cat.close)
        cat.fx = 220; cat.stand_on(cat.surfaces()[-1]); cat.set("idle", 120); cat.show()
        pack = next(app.plugins.available(cat.char))
        self.assertTrue(app.plugins.bind(app, cat.char, pack.id, True))
        self.assertTrue(app.plugins.play(cat, pack, pack.actions[0]))
        self.assertEqual(cat.frame(), 0)

        app.lock.close()
        with patch.object(application, "BASE", str(directory)), patch.object(application, "CHARS_DIR", str(sprites)), \
                patch.object(sys, "argv", [str(directory / "buddies.py")]):
            reopened = application.App()
        reopened.lock.close()
        self.assertIn("star-cat", reopened.roster)
        self.assertEqual(reopened.plugins.selected(reopened.cfg, "star-cat"), {"star-cat"})

    def test_archive_rejects_extra_paths_and_preserves_export_on_failure(self):
        with TemporaryDirectory(prefix="mbpack-invalid-") as folder:
            directory = Path(folder)
            path = directory / "sample.zip"
            project = Project(kind="character", id="sample-cat", name="샘플 고양이")
            project.frames[0] = make_png(directory / "0.png", "#d474a3")
            export_archive(project, path)
            data = path.read_bytes()
            project.frames.clear()
            with self.assertRaises(ValueError):
                export_archive(project, path)
            self.assertEqual(path.read_bytes(), data)
            marker = f"{directory.name}-unexpected.txt"
            with ZipFile(path, "a") as archive:
                archive.writestr(f"../{marker}", "ignored")
            with self.assertRaises(ValueError):
                load_archive(path)
            self.assertFalse((directory.parent / marker).exists())
