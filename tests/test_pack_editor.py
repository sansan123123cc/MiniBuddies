import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QPoint, QTimer, Qt
from PyQt5.QtGui import QColor, QImage, QPainter
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QDialog, QFileDialog, QInputDialog, QMenu, QPushButton

from minibuddies import app as application
from minibuddies.authoring.archive import export_archive, inspect_archive, load_archive
from minibuddies.authoring.installed import install_into
from minibuddies.authoring.project import Project, Skin
from minibuddies.effects import EFFECT_PRESETS
from minibuddies.ui.editor import dialog as editor_ui
from minibuddies.ui.editor.rules import RuleDialog
from minibuddies.ui.editor.skins import SkinDetails
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
        self.assertIn("필수 0번 필요", editor.frames.summary.text())
        artwork = make_png(directory / "0.png", "#7b75ca")
        with patch.object(QFileDialog, "getOpenFileName", return_value=(str(directory / "0.png"), "")):
            editor.frames.add_image()
        self.assertEqual(editor.project.frames[0], artwork)
        editor.frames.store({7: make_png(directory / "7.png", "#277dce")}, 7)
        self.assertIn("0번 등록 완료 · 권장 1/7장", editor.frames.summary.text())

        def edit_solo(rule):
            rule.name.setText("인사하기")
            rule.trigger.setCurrentIndex(1)
            rule.chance.setValue(12.5)
            rule.speech.setText("안녕하세요!")
            rule.timeline.add()
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
            if not step.group:
                self.assertEqual({step.preset.itemData(i) for i in range(1, step.preset.count())}, EFFECT_PRESETS)
                if step.previous_pose.get("frame") == 7:
                    step.source.setCurrentIndex(step.source.findData("hold"))
                    self.assertIsNotNone(step.preview.pixmap())
                    step.speech.setText("별빛을 모아!")
                    step.preset.setCurrentIndex(step.preset.findData("spark"))
                    step.colors.setText("#277dce, #ffdb68")
                    step.ticks.setValue(3)
                    step.effect_ticks.setValue(12)
                else:
                    step.frame.setValue(7)
                    step.ticks.setValue(2)
            elif step.actor == "star-cat":
                step.preset.setCurrentIndex(step.preset.findData("seal"))
            step.accept()
            return step.result()

        with patch.object(StepDialog, "exec_", save_step):
            with patch.object(RuleDialog, "exec_", edit_solo):
                editor.rules.add("actions")
            with patch.object(RuleDialog, "exec_", edit_group):
                editor.rules.add("interactions")
        solo = editor.project.rules["actions"][0]
        self.assertEqual(solo["idle_chance"], 0.125)
        self.assertEqual(solo["characters"], ["star-cat"])
        self.assertEqual(solo["frames"], [{"frame": 7, "ticks": 2}, {
            "ticks": 3, "say": "별빛을 모아!",
            "effect": {"preset": "spark", "colors": ["#277dce", "#ffdb68"], "ticks": 12},
        }])
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
        self.assertEqual(imported.project.rules["actions"][0], solo)
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
        cat.face = -1
        pack = next(app.plugins.available(cat.char))
        self.assertTrue(app.plugins.bind(app, cat.char, pack.id, True))
        self.assertTrue(app.plugins.play(cat, pack, pack.actions[0]))
        self.assertEqual(cat.frame(), 7)
        self.assertEqual(cat.bubble.text, "안녕하세요!")
        cat.step()
        self.assertIsNone(cat.plugin_action.overlay)
        cat.step()
        self.assertEqual(cat.frame(), 7)
        self.assertEqual(cat.bubble.text, "별빛을 모아!")
        overlay = cat.plugin_action.overlay
        self.assertTrue(overlay.isVisible())
        initial = overlay.grab().toImage()
        for _ in range(5):
            cat.step()
        self.assertEqual(cat.state, "seq")
        self.assertEqual(cat.frame(), 7)
        with patch.object(overlay, "paint_spell", wraps=overlay.paint_spell) as paint:
            self.assertNotEqual(overlay.grab().toImage(), initial)
            self.assertEqual(paint.call_args.args[-1], -1)
        for _ in range(7):
            cat.step()
        self.assertEqual(cat.state, "idle")
        self.assertIsNone(cat.plugin_action)
        self.assertIsNone(cat.bubble)
        self.assertFalse(overlay.isVisible())

        self.assertTrue(app.plugins.play(cat, pack, pack.actions[0]))
        cat.step()
        cat.step()
        overlay = cat.plugin_action.overlay
        cat.fall()
        self.assertFalse(overlay.isVisible())
        self.assertIsNone(cat.plugin_action)
        self.assertIsNone(cat.bubble)

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

    def test_import_keeps_the_current_kind_and_does_not_default_to_new_plugin(self):
        directory = Path(self.enterContext(TemporaryDirectory(prefix="mbpack-focus-")))
        png = make_png(directory / "0.png", "#bd6cb7")
        source = directory / "kitten.mbpack"
        export_archive(Project(kind="character", id="kitten", name="고양이", frames={0: png}), source)
        qapp = QApplication.instance() or QApplication([])
        self.qapp = qapp
        from types import SimpleNamespace
        app = SimpleNamespace(mode="kitten", chars={})
        editor = editor_ui.PackEditor(app)
        self.addCleanup(editor.close)
        editor.show()
        qapp.processEvents()
        new_plugin = next(button for button in editor.findChildren(QPushButton) if button.text() == "새 플러그인")
        self.assertFalse(new_plugin.autoDefault())

        def file_choice(*args):
            chooser = QDialog(editor)
            QTimer.singleShot(0, chooser.accept)
            chooser.exec_()
            return str(source), ""

        original = editor_ui.archive_preview

        def accept_preview(*args):
            QTimer.singleShot(10, lambda: qapp.activeModalWidget().accept())
            return original(*args)

        with patch.object(QFileDialog, "getOpenFileName", file_choice), patch.object(editor_ui, "archive_preview", accept_preview):
            editor.import_button.click()
        qapp.processEvents()
        self.assertEqual(editor.project.kind, "character")
        self.assertEqual(editor.kind.text(), "캐릭터")
        self.assertIs(editor.focusWidget(), editor.import_button)
        self.assertFalse(new_plugin.isDefault())
        editor.name.setFocus(Qt.OtherFocusReason)
        with patch.object(QFileDialog, "getOpenFileName", return_value=("", "")) as reopened:
            QTest.keyClick(editor.name, Qt.Key_Return)
        reopened.assert_not_called()
        self.assertTrue(editor.isVisible())
        self.assertEqual(editor.project.id, "kitten")
        with patch.object(QFileDialog, "getOpenFileName", return_value=("", "")):
            editor.import_button.click()
        self.assertIs(editor.focusWidget(), editor.import_button)
        self.assertEqual(editor.project.kind, "character")

    def test_skin_editor_round_trip_and_outfit_switch_survive_restart(self):
        directory = Path(self.enterContext(TemporaryDirectory(prefix="mbpack-skin-")))
        chars = directory / "chars"
        base_art = make_png(chars / "reimu" / "0.png", "#d3457c")
        (chars / "reimu" / "name.txt").write_text("레이무", encoding="utf-8")
        make_png(chars / "marisa" / "0.png", "#edbd74")
        make_png(chars / "reimu@stock" / "0.png", "#63b4e5")
        (directory / "roster.txt").write_text("reimu+marisa!", encoding="utf-8")
        (directory / "settings.json").write_text(json.dumps({"active": ["reimu", "marisa"], "mcp": False,
                                                             "weather": False, "on_top": False}), encoding="utf-8")

        def start():
            with patch.object(application, "BASE", str(directory)), patch.object(application, "CHARS_DIR", str(chars)), \
                    patch.object(sys, "argv", [str(directory / "buddies.py")]):
                return application.App()

        app = start()
        self.addCleanup(app.lock.close)
        editor = editor_ui.PackEditor(app)
        self.addCleanup(editor.deleteLater)
        next(button for button in editor.findChildren(QPushButton) if button.text() == "새 스킨 팩").click()
        self.assertFalse(editor.tabs.isTabVisible(editor.tabs.indexOf(editor.frames)))
        self.assertTrue(editor.tabs.isTabVisible(editor.tabs.indexOf(editor.skins)))
        editor.name.setText("봄 의상 모음")
        editor.id.setText("reimu-spring-pack")
        editor.target.setCurrentIndex(editor.target.findData("reimu"))

        def enter_skin(details):
            details.key.setText("spring")
            details.name.setText("봄 나들이")
            details.accept()
            return details.result()

        with patch.object(SkinDetails, "exec_", enter_skin):
            editor.skins.add()
        skin_art = make_png(directory / "skin.png", "#7cdb9a")
        with patch.object(QFileDialog, "getOpenFileName", return_value=(str(directory / "skin.png"), "")):
            editor.skins.frame_editor.add_image()
        pack = directory / "reimu-spring.mbpack"
        with patch.object(QFileDialog, "getSaveFileName", return_value=(str(pack), "")):
            editor.export()
        info, cover = inspect_archive(pack)
        self.assertEqual((info["kind"], info["target"], info["skins"][0]["name"]), ("skin", "reimu", "봄 나들이"))
        self.assertEqual(cover, skin_art)
        with patch.object(QFileDialog, "getOpenFileName", return_value=(str(pack), "")), \
                patch.object(editor_ui, "archive_preview", return_value=True):
            editor.open_pack()
        self.assertEqual(editor.kind.text(), "스킨 팩")
        self.assertEqual(editor.target.currentData(), "reimu")
        editor.install()
        self.assertIn("stock", app.outfits["reimu"])
        self.assertEqual(app.outfit["reimu"], "basic")
        self.assertEqual(Path(app.chars["reimu"]["dir"], "0.png").read_bytes(), base_art)
        app.add(entrance="drop", char="reimu")
        pet = app.buddies[-1]
        self.addCleanup(pet.close)
        pet.stand_on(pet.surfaces()[-1])

        def choose_outfit(menu, *args):
            for action in menu.actions():
                if action.menu():
                    choose_outfit(action.menu())
                elif action.text() == "봄 나들이":
                    action.trigger()

        with patch.object(QMenu, "exec_", choose_outfit):
            app.menu(QPoint(120, 120), pet)
        self.assertEqual(app.outfit["reimu"], "spring")
        self.assertEqual(app.chars["reimu"]["label"], "레이무")
        self.assertEqual(Path(app.chars["reimu"]["dir"], "0.png").read_bytes(), skin_art)
        asset = Project(kind="character", id="new-pet", name="새 친구", frames={0: base_art},
                        skins={"evening": Skin("저녁 의상", {0: skin_art})})
        export_archive(asset, directory / "bundled.mbpack")
        install_into(app, load_archive(directory / "bundled.mbpack"))
        self.assertEqual(app.outfit_label("new-pet", "evening"), "저녁 의상")
        with self.assertRaises(ValueError):
            install_into(app, Project(kind="skin", id="duplicate-skin", name="중복", target="reimu",
                                      skins={"spring": Skin("봄", {0: skin_art})}))
        self.assertFalse((directory / "user-packs" / "duplicate-skin").exists())

        app.lock.close()
        app = start()
        self.addCleanup(app.lock.close)
        self.assertEqual(app.outfit["reimu"], "spring")
        self.assertEqual(app.outfit_label("new-pet", "evening"), "저녁 의상")
        self.assertEqual(Path(app.chars["reimu"]["dir"], "0.png").read_bytes(), skin_art)
