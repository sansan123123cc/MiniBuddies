import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QRect
from PyQt5.QtWidgets import QApplication, QFileDialog, QDialog

from minibuddies.authoring.archive import export_archive, inspect_archive, install_project, load_archive
from minibuddies.effects import PluginEffectOverlay, keyframe_values
from minibuddies.plugins.packs import read_pack
from minibuddies.ui.editor import effects as effect_editor, playback
from minibuddies.ui.editor.dialog import PackEditor
from minibuddies.ui.editor.rules import RuleDialog
from minibuddies.ui.editor.steps import StepDialog
from test_pack_editor import make_png


class EditorPlaybackTest(unittest.TestCase):
    def setUp(self):
        self.qapp = QApplication.instance() or QApplication([])
        self.root = Path(self.enterContext(TemporaryDirectory(prefix="mb-preview-")))
        self.characters = ("reimu", "marisa", "alice", "cirno", "sakuya", "meiling")
        app = SimpleNamespace(mode="reimu", chars={})
        for i, key in enumerate(self.characters):
            directory = self.root / key
            make_png(directory / "0.png", ("#d36589", "#ffbd60", "#7d84ed", "#67add5", "#f3f1f6", "#60b683")[i])
            app.chars[key] = {"label": key.title(), "dir": str(directory)}
        make_png(self.root / "reimu" / "7.png", "#25c9ba")
        self.editor = PackEditor(app)
        self.addCleanup(self.editor.close)

    def test_preview_plays_all_participants_and_seeks_through_effect_tail(self):
        effect = {"preset": "spark", "target": "meiling", "colors": ["#25c9ba"], "ticks": 35}
        self.editor.project.rules["effects"] = {
            "reply": {"name": "되돌아오는 빛", "layers": [{"kind": "line", "anchor": "target"}]},
        }
        roles = [{"character": key, "steps": [{"frame": 0, "ticks": 12}]} for key in self.characters]
        roles[0]["steps"].append({"frame": 7, "ticks": 4, "say": "별빛을 받아!", "effect": effect})
        roles[1]["steps"][0]["say"] = "기다릴게!"
        reply = {"preset": "reply", "target": "reimu", "colors": ["#ffbd60"], "ticks": 14}
        roles[-1]["steps"].append({"ticks": 8, "say": "여기야!", "effect": reply})
        rule = RuleDialog(self.editor, "interactions", {"roles": roles})
        rule.cast.setCurrentRow(3)
        self.assertTrue(rule.preview_button.isEnabled())

        def verify(dialog):
            self.assertTrue(dialog.timer.isActive())
            dialog.pause()
            stage = dialog.stage
            self.assertEqual(tuple(stage.tracks), self.characters)
            self.assertEqual(stage.duration, 47)
            self.assertEqual(stage.tracks["marisa"].speech(0), "기다릴게!")
            initial = stage.grab().toImage()
            dialog.progress.setValue(18)
            self.assertEqual(stage.tracks["reimu"].speech(18), "별빛을 받아!")
            self.assertEqual(stage.tracks["meiling"].speech(18), "여기야!")
            self.assertNotEqual(stage.tracks["reimu"].pose(18)[0], stage.tracks["reimu"].pose(0)[0])
            with patch.object(playback, "paint_effect", wraps=playback.paint_effect) as paint:
                self.assertNotEqual(stage.grab().toImage(), initial)
                outgoing, incoming = [call.kwargs for call in paint.call_args_list]
                self.assertGreater(outgoing["target_x"], outgoing["x"])
                self.assertEqual(outgoing["direction"], 1)
                self.assertEqual(incoming["target_x"], outgoing["x"])
                self.assertEqual(incoming["direction"], -1)
                self.assertEqual(incoming["design"].layers[0].anchor, "target")
            self.assertTrue(list(stage.tracks["reimu"].effects(46)))
            self.assertFalse(list(stage.tracks["reimu"].effects(47)))
            dialog.progress.setValue(47)
            dialog.toggle_play()
            self.assertEqual(dialog.progress.value(), 0)
            dialog.reject()
            self.assertFalse(dialog.timer.isActive())
            return QDialog.Rejected

        with patch.object(playback.PlaybackDialog, "exec_", verify):
            rule.preview_button.click()

    def test_authored_png_and_keyframes_round_trip_into_solo_preview_and_runtime(self):
        editor = self.editor
        editor.id.setText("stage-light")
        editor.name.setText("무대 효과")
        sprite_paths = [str(self.root / "reimu" / f"{number}.png") for number in (0, 7)]

        def define_png(layer):
            layer.kind.setCurrentIndex(layer.kind.findData("image"))
            with patch.object(QFileDialog, "getOpenFileNames", return_value=(sprite_paths, "")):
                layer.add_images()
            layer.move_image(-1)
            layer.start.setValue(20)
            layer.table.cellWidget(0, 1).setValue(-40)
            layer.table.cellWidget(1, 1).setValue(40)
            layer.accept()
            return layer.result()

        def define_ring(layer):
            layer.kind.setCurrentIndex(layer.kind.findData("ring"))
            layer.blend.setCurrentIndex(layer.blend.findData("add"))
            layer.colors.setText("#67add5")
            layer.add_keyframe()
            layer.table.cellWidget(2, 4).setValue(90)
            layer.accept()
            return layer.result()

        def define_effect(dialog):
            dialog.key.setText("stage-flash")
            dialog.name.setText("무대 섬광")
            for define_layer in (define_png, define_ring):
                with patch.object(effect_editor.LayerDialog, "exec_", define_layer):
                    dialog.add_layer()
            dialog.move_layer(-1)
            dialog.progress.setValue(45)
            self.assertEqual([layer.kind for layer in dialog.sample.design.layers], ["ring", "image"])
            self.assertFalse(dialog.sample.grab().isNull())
            dialog.accept()
            return dialog.result()

        with patch.object(effect_editor.EffectDialog, "exec_", define_effect):
            editor.effects.add()
        step = StepDialog(editor, editor, {"frame": 0, "ticks": 20}, False, "reimu", [])
        step.preset.setCurrentIndex(step.preset.findData("stage-flash"))
        step.effect_ticks.setValue(32)
        step.speech.setText("첫 번째 대사")
        step.accept()
        editor.project.rules["actions"] = [{"name": "무대 인사", "say": "시작 대사", "frames": [step.result_step]}]
        editor.sync_metadata()
        with patch.object(effect_editor, "show_error") as error:
            editor.effects.remove()
            error.assert_called_once()
        archive = self.root / "light.mbpack"
        export_archive(editor.project, archive)
        self.assertEqual(inspect_archive(archive)[0]["effects"], 1)
        restored = load_archive(archive)
        self.assertEqual(restored.rules["effects"], editor.project.rules["effects"])
        self.assertEqual(len(restored.assets), 2)
        editor.load(restored)
        rule = RuleDialog(editor, "actions", restored.rules["actions"][0])

        def verify(dialog):
            dialog.pause()
            self.assertEqual(dialog.stage.duration, 32)
            track = dialog.stage.tracks["reimu"]
            self.assertEqual(track.speech(0), "첫 번째 대사")
            before = dialog.stage.grab().toImage()
            dialog.progress.setValue(17)
            self.assertNotEqual(dialog.stage.grab().toImage(), before)
            dialog.reject()
            return QDialog.Rejected

        with patch.object(playback.PlaybackDialog, "exec_", verify):
            rule.preview_button.click()
        destination, _ = install_project(restored, self.root / "installed", set())
        pack, _ = read_pack(destination, 0)
        effect = pack.actions[0].events[0].effect
        layer = effect.design.layers[1]
        self.assertEqual(keyframe_values(layer.keyframes, 50)[0], 0)
        self.assertEqual(layer.images[0].pixelColor(100, 100).name(), "#25c9ba")
        self.assertEqual(layer.images[1].pixelColor(100, 100).name(), "#d36589")
        pet = SimpleNamespace(cx=160, fy=150, S=100, face=1, scr=lambda: QRect(0, 0, 400, 360))
        overlay = PluginEffectOverlay([pet], False)
        self.addCleanup(overlay.close)
        overlay.show_effect(pet, None, effect, 0)
        before = overlay.grab().toImage()
        overlay.advance(17)
        self.assertNotEqual(overlay.grab().toImage(), before)
