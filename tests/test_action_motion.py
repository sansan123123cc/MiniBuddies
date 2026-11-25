import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QDialog

from minibuddies import app as application
from minibuddies.authoring.archive import export_archive, load_archive
from minibuddies.authoring.installed import install_into
from minibuddies.plugins.scenes import read_steps
from minibuddies.ui.editor.dialog import PackEditor
from minibuddies.ui.editor.playback import PlaybackDialog
from minibuddies.ui.editor.rules import RuleDialog
from minibuddies.ui.editor.steps import StepDialog
from test_pack_editor import make_png


class ActionMotionTest(unittest.TestCase):
    def test_author_and_play_jump_turn_retreat_and_stop_at_destination(self):
        root = Path(self.enterContext(TemporaryDirectory(prefix="mbpack-motion-")))
        sprites = root / "chars"
        make_png(sprites / "reimu" / "0.png", "#de527e")
        make_png(sprites / "reimu" / "10.png", "#a44be4")
        (root / "roster.txt").write_text("reimu!", encoding="utf-8")
        (root / "settings.json").write_text(json.dumps({"active": ["reimu"], "mcp": False, "weather": False,
                                                         "climb": False, "cursor_avoid": False,
                                                         "on_top": False}), encoding="utf-8")
        with patch.object(application, "BASE", str(root)), patch.object(application, "CHARS_DIR", str(sprites)), \
                patch.object(sys, "argv", [str(root / "buddies.py")]):
            app = application.App()
        self.addCleanup(app.lock.close)
        editor = PackEditor(app)
        self.addCleanup(editor.deleteLater)

        first = StepDialog(editor, editor, {"frame": 0}, False, "reimu", [])
        first.frame_choice.setCurrentIndex(first.frame_choice.findData(10))
        first.travel.setCurrentIndex(first.travel.findData("jump"))
        first.facing.setCurrentIndex(first.facing.findData("right"))
        first.easing.setCurrentIndex(first.easing.findData("ease-out"))
        first.distance.setValue(100)
        first.height.setValue(60)
        first.ticks.setValue(8)
        first.speech.setText("출발")
        first.accept()
        self.assertEqual(first.result(), QDialog.Accepted)
        self.assertEqual(first.result_step["frame"], 10)
        self.assertEqual(first.result_step["move"], {"distance": 100, "height": 60, "easing": "ease-out"})
        self.assertEqual(first.result_step["turn"], {"direction": "right"})

        second = StepDialog(editor, editor, {"frame": 0, "ticks": 4}, False, "reimu", [])
        second.travel.setCurrentIndex(second.travel.findData("slide"))
        second.facing.setCurrentIndex(second.facing.findData("left"))
        second.distance.setValue(-50)
        second.dismiss_speech.setChecked(True)
        self.assertFalse(second.speech.isEnabled())
        second.accept()
        steps = [first.result_step, second.result_step]
        editor.id.setText("jump-check")
        editor.name.setText("이동 테스트")
        rule = RuleDialog(editor, "actions", {"name": "돌아서 점프", "frames": steps})
        rule.trigger.setCurrentIndex(rule.trigger.findData("interval"))
        rule.interval.setValue(12)
        rule.accept()
        self.assertEqual(rule.result(), QDialog.Accepted)
        editor.project.rules["actions"] = [rule.rule]
        editor.sync_metadata()
        archive = root / "jump.mbpack"
        export_archive(editor.project, archive)
        restored = load_archive(archive)
        self.assertEqual(restored.rules["actions"][0]["frames"], steps)
        self.assertEqual(restored.rules["actions"][0]["interval_seconds"], 12)
        install_into(app, restored)

        preview = PlaybackDialog(editor, editor, {"reimu": steps}, group=False)
        preview.pause()
        self.addCleanup(preview.close)
        preview.progress.setValue(4)
        track = preview.stage.motion["reimu"]
        self.assertEqual((track.pose(4).x, track.pose(4).lift, track.pose(4).face), (75, 60, 1))
        self.assertEqual(preview.stage.tracks["reimu"].speech(4), "출발")
        preview.progress.setValue(12)
        self.assertEqual((track.pose(12).x, track.pose(12).lift, track.pose(12).face), (150, 0, -1))
        self.assertEqual(preview.stage.tracks["reimu"].speech(12), "")
        preview.progress.setValue(4)
        self.assertEqual(track.pose(preview.stage.tick).x, 75)

        app.add(entrance="drop", char="reimu")
        pet = app.buddies[-1]
        self.addCleanup(pet.close)
        pet.fx = pet.scr().left() + 85
        pet.stand_on(pet.surfaces()[-1])
        pet.set("idle", 60)
        pet.face = -1
        initial = pet.cx
        pack = app.plugins.packs[0]
        self.assertTrue(app.plugins.bind(app, pet.char, pack.id, True))
        self.assertTrue(app.plugins.play(pet, pack, pack.actions[0]))
        for _ in range(4):
            app.tick()
        self.assertAlmostEqual(pet.cx, initial + pet.S * 0.75)
        self.assertAlmostEqual(pet.feet(pet.frame()), pet.surface[1] - pet.S * 0.60)
        self.assertEqual(pet.x(), int(pet.fx))
        for _ in range(4):
            app.tick()
        self.assertEqual(pet.face, -1)
        self.assertIsNone(pet.bubble)
        for _ in range(4):
            app.tick()
        self.assertEqual(pet.state, "idle")
        self.assertAlmostEqual(pet.cx, initial + pet.S * 1.5)
        self.assertAlmostEqual(pet.feet(), pet.surface[1])

        edge = round(pet.cx + 14)
        ledge = (pet.scr().left() + 10, pet.scr().top() + 250, edge)
        app.climb_windows = True
        app.windows = [ledge]
        pet.stand_on(ledge)
        self.assertTrue(app.plugins.play(pet, pack, pack.actions[0]))
        for _ in range(4):
            app.tick()
        self.assertLess(pet.feet(pet.frame()), ledge[1])
        pet.set("idle", 60)
        self.assertAlmostEqual(pet.feet(), ledge[1])
        self.assertIsNone(pet.plugin_action)
        self.assertTrue(app.plugins.play(pet, pack, pack.actions[0]))
        for _ in range(12):
            app.tick()
        self.assertEqual(pet.cx, edge - 1)
        self.assertEqual(pet.surface, ledge)

        with patch("minibuddies.plugins.library.time.monotonic", return_value=60) as clock:
            app.plugins.tick_periodic(app)
            self.assertEqual(pet.state, "idle")
            clock.return_value = 71
            app.plugins.tick_periodic(app)
            self.assertEqual(pet.state, "idle")
            clock.return_value = 72
            app.plugins.tick_periodic(app)
            self.assertEqual(pet.state, "seq")

    def test_validates_movement_and_turn_independently(self):
        for step in ({"ticks": 1, "move": {"height": 40}}, {"ticks": 8, "move": {"distance": 301}},
                     {"ticks": 8, "move": {"distance": 25, "easing": "other"}},
                     {"ticks": 8, "turn": {"direction": "target", "target": "marisa"}},
                     {"ticks": 8, "follow": {"target": "marisa"}},
                     {"ticks": 8, "say": "안녕", "dismiss_speech": True}):
            with self.subTest(step=step), self.assertRaises(ValueError):
                read_steps([step], None)
        beats, _ = read_steps([{"ticks": 8, "turn": {"direction": "left"}}], None)
        self.assertIsNone(beats[0].move)
        self.assertEqual(beats[0].turn.direction, "left")
