import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QImage, QPainter
from PyQt5.QtWidgets import QDialog, QMenu

from minibuddies import app as application
from minibuddies.authoring.archive import export_archive, load_archive
from minibuddies.authoring.installed import install_into
from minibuddies.plugins.packs import read_pack
from minibuddies.ui.editor.dialog import PackEditor
from minibuddies.ui.editor.playback import PlaybackDialog
from minibuddies.ui.editor.rules import RuleDialog
from minibuddies.ui.editor.steps import StepDialog


def sprite(path, height=180):
    image = QImage(256, 256, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.fillRect(50, 30, 156, height, QColor("#ee6899"))
    painter.end()
    if not image.save(str(path)):
        raise RuntimeError(f"Could not save {path}")


class InteractionIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory(prefix="minibuddies-scenes-")))
        chars = ["reimu", "marisa", "cirno"]
        for name in chars:
            directory = self.root / "chars" / name
            directory.mkdir(parents=True)
            sprite(directory / "0.png")
        (self.root / "roster.txt").write_text("+".join(chars) + "!", encoding="utf-8")
        self.cfg_path = self.root / "settings.json"
        self.cfg_path.write_text(json.dumps({"active": chars, "mcp": False, "weather": False,
                                             "climb": False, "cursor_avoid": False, "on_top": False}), encoding="utf-8")
        pack = self.root / "plugins" / "test-duet"
        pack.mkdir(parents=True)
        sprite(pack / "cast.png", 135)
        interaction = {"name": "별빛 주고받기", "meet_chance": 1, "cooldown_seconds": 30, "roles": [
            {"character": "reimu", "steps": [
                {"ticks": 12, "file": "cast.png", "say": "먼저 할게!",
                 "effect": {"preset": "seal", "colors": ["#ff88aa"], "target": "marisa", "ticks": 16}},
                {"ticks": 10, "frame": 0},
            ]},
            {"character": "marisa", "steps": [
                {"ticks": 12, "frame": 0},
                {"ticks": 10, "file": "cast.png", "say": "다음은 나야!",
                 "effect": {"preset": "spark", "colors": ["#ffcc66"], "target": "reimu", "ticks": 16}},
            ]},
        ]}
        (pack / "plugin.json").write_text(json.dumps({"version": 1, "interactions": [interaction]}), encoding="utf-8")
        bad = self.root / "plugins" / "bad-duet"
        bad.mkdir()
        interaction["roles"][1]["character"] = "reimu"
        (bad / "plugin.json").write_text(json.dumps({"version": 1, "interactions": [interaction]}), encoding="utf-8")
        self.errors = []
        with patch.object(application, "BASE", str(self.root)), patch.object(application, "CHARS_DIR", str(self.root / "chars")), \
                patch.object(application, "_crash_write", self.errors.append), patch.object(sys, "argv", [str(self.root / "buddies.py")]):
            self.app = application.App()
        self.addCleanup(self.app.lock.close)
        self.pets = {}
        for i, char in enumerate(chars):
            self.app.add(entrance="drop", char=char)
            pet = self.app.buddies[-1]
            self.addCleanup(pet.close)
            pet.fx = 140 + 120 * i
            pet.stand_on(pet.surfaces()[-1])
            pet.set("idle", 1000)
            pet.show()
            self.pets[char] = pet
        self.reimu, self.marisa, self.cirno = (self.pets[char] for char in chars)
        self.library = self.app.plugins.interactions
        self.pack = self.app.plugins.packs[0]
        self.scene = self.pack.interactions[0]

    def trigger_menu(self):
        menu = QMenu()
        self.app.plugin_interaction_menu(menu, self.reimu)
        action = menu.actions()[0].menu().actions()[0]
        self.assertTrue(action.isEnabled())
        action.trigger()

    def reach_start(self):
        for _ in range(180):
            self.app.tick()
            if self.app.group and self.app.group["phase"] == "go":
                return self.app.group
        self.fail("The assigned pets did not gather")

    def test_roles_effects_and_completion(self):
        self.assertTrue(any("bad-duet" in error for error in self.errors))
        self.assertEqual(self.pack.id, "test-duet")
        self.assertEqual(list(self.app.plugins.available("cirno")), [])
        self.assertFalse(self.library.play(self.app, self.pack, self.scene))
        self.assertTrue(self.app.plugins.bind(self.app, "reimu", self.pack.id, True))
        self.assertFalse(self.library.play(self.app, self.pack, self.scene))
        self.assertTrue(self.app.plugins.bind(self.app, "marisa", self.pack.id, True))

        alternate_screen = self.marisa.scr().translated(900, 0)
        with patch.object(self.marisa, "scr", return_value=alternate_screen):
            self.assertIsNone(self.library.formation(self.app, self.scene, self.reimu))
        original = self.marisa.fx
        self.marisa.fx += self.scene.meet_distance
        self.assertIsNone(self.library.formation(self.app, self.scene, self.reimu))
        self.marisa.fx = original
        self.trigger_menu()
        group = self.reach_start()
        self.assertEqual(group["mem"], [self.reimu, self.marisa])
        self.assertEqual(self.cirno.state, "idle")
        self.assertLess(self.reimu.frame(), 0)
        self.assertEqual(self.marisa.frame(), 0)
        self.assertEqual(self.reimu.feet(self.reimu.frame()), self.reimu.surface[1])
        self.assertEqual(self.reimu.bubble.text, "먼저 할게!")
        overlay = group["effect"]
        self.assertTrue(overlay.windowFlags() & Qt.WindowTransparentForInput)
        initial = overlay.grab().toImage()
        for _ in range(12):
            self.app.tick()
        self.assertEqual(self.reimu.frame(), 0)
        self.assertLess(self.marisa.frame(), 0)
        self.assertEqual(self.marisa.bubble.text, "다음은 나야!")
        self.assertNotEqual(overlay.grab().toImage(), initial)
        for _ in range(16):
            self.app.tick()
        self.assertIsNone(self.app.group)
        self.assertFalse(overlay.isVisible())
        self.assertEqual([pet.state for pet in (self.reimu, self.marisa)], ["idle", "idle"])
        self.assertIsNone(self.reimu.bubble)
        self.assertIsNone(self.marisa.bubble)

    def test_automatic_cooldown_and_unbinding(self):
        for char in ("reimu", "marisa"):
            self.assertTrue(self.app.plugins.bind(self.app, char, self.pack.id, True))
        self.app.cfg["auto_group"] = False
        with patch("minibuddies.plugins.interactions.random.random", return_value=0.99):
            self.app.duo_tick()
            self.assertIsNone(self.app.group)
            self.app.cfg["auto_group"] = True
            self.app.duo_tick()
        self.assertEqual(self.app.group["kind"], "plugin_interaction")
        group = self.reach_start()
        overlay = group["effect"]
        self.app.plugins.bind(self.app, "marisa", self.pack.id, False)
        self.app.tick()
        self.assertIsNone(self.app.group)
        self.assertFalse(overlay.isVisible())
        self.app.plugins.bind(self.app, "marisa", self.pack.id, True)
        self.assertFalse(self.library.try_automatic(self.app))
        self.library.next_meet.clear()
        self.assertTrue(self.library.try_automatic(self.app))
        group = self.reach_start()
        overlay = group["effect"]
        self.marisa.drag = object()
        self.app.group_step()
        self.marisa.drag = None
        self.assertIsNone(self.app.group)
        self.assertFalse(overlay.isVisible())

    def test_participant_turn_uses_the_other_pets_position_when_the_step_begins(self):
        directory = self.root / "plugins" / "test-duet"
        manifest = directory / "plugin.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        reimu, marisa = (role["steps"] for role in data["interactions"][0]["roles"])
        reimu[0]["move"] = {"distance": 250, "height": 40}
        reimu[1]["dismiss_speech"] = True
        marisa[1]["turn"] = {"direction": "target", "target": "reimu"}
        manifest.write_text(json.dumps(data), encoding="utf-8")
        pack, _ = read_pack(directory, 0)
        self.app.plugins.packs[0] = pack
        self.app.cfg["auto_group"] = False
        for pet in (self.reimu, self.marisa):
            self.assertTrue(self.app.plugins.bind(self.app, pet.char, pack.id, True))
        self.assertTrue(self.library.play(self.app, pack, pack.interactions[0], self.reimu))
        self.reach_start()
        start = self.reimu.cx
        self.assertLess(start, self.marisa.cx)
        self.assertEqual(self.marisa.face, -1)

        for _ in range(6):
            self.app.tick()
        self.assertGreater(self.reimu.cx, start)
        self.assertAlmostEqual(self.reimu.feet(self.reimu.frame()), self.reimu.surface[1] - self.reimu.S * 0.40)
        for _ in range(6):
            self.app.tick()
        destination = self.reimu.cx
        self.assertGreater(destination, self.marisa.cx)
        self.assertEqual(self.marisa.face, 1)
        self.assertIsNone(self.reimu.bubble)
        self.assertAlmostEqual(self.reimu.feet(), self.reimu.surface[1])

        for _ in range(16):
            self.app.tick()
        self.assertIsNone(self.app.group)
        self.assertEqual(self.reimu.state, "idle")
        self.assertAlmostEqual(self.reimu.cx, destination)

    def test_periodic_interaction_follows_a_moving_character(self):
        editor = PackEditor(self.app)
        self.addCleanup(editor.deleteLater)
        targets = ["reimu", "marisa"]
        step = StepDialog(editor, editor, {"frame": 0, "ticks": 40}, True, "reimu", targets)
        step.travel.setCurrentIndex(step.travel.findData("follow"))
        self.assertEqual(step.follow_target.currentData(), "marisa")
        step.follow_distance.setValue(60)
        step.follow_speed.setValue(8)
        step.accept()
        self.assertEqual(step.result(), QDialog.Accepted)
        self.assertEqual(step.result_step["follow"], {"target": "marisa", "distance": 60, "speed": 8})
        sequences = {"reimu": [step.result_step],
                     "marisa": [{"frame": 0, "ticks": 40, "turn": {"direction": "right"}, "move": {"distance": 100}}]}
        rule = RuleDialog(editor, "interactions", {"name": "같이 걸어가기", "roles": [
            {"character": key, "steps": moves} for key, moves in sequences.items()
        ]})
        rule.trigger.setCurrentIndex(rule.trigger.findData("interval"))
        rule.interval.setValue(5)
        rule.accept()
        self.assertEqual(rule.rule["interval_seconds"], 5)
        self.assertEqual(rule.rule["meet_chance"], 0)
        editor.id.setText("test-follow")
        editor.name.setText("따라가기")
        editor.project.rules["interactions"] = [rule.rule]
        editor.sync_metadata()
        archive = self.root / "follow.mbpack"
        export_archive(editor.project, archive)
        restored = load_archive(archive)
        self.assertEqual(restored.rules["interactions"][0], rule.rule)
        install_into(self.app, restored)

        preview = PlaybackDialog(editor, editor, sequences, group=True)
        preview.pause()
        self.addCleanup(preview.close)
        tracks = preview.stage.motion
        preview.progress.setValue(40)
        self.assertAlmostEqual(tracks["marisa"].pose(40).x - tracks["reimu"].pose(40).x, 60)
        preview.progress.setValue(8)
        self.assertLess(tracks["reimu"].pose(8).x, tracks["reimu"].pose(40).x)

        for pet in (self.reimu, self.marisa):
            self.assertTrue(self.app.plugins.bind(self.app, pet.char, "test-follow", True))
        with patch("minibuddies.plugins.library.time.monotonic", return_value=100) as clock:
            self.app._tk = 29
            self.app.tick()
            self.assertIsNone(self.app.group)
            clock.return_value = 104
            self.app.plugins.tick_periodic(self.app)
            self.assertIsNone(self.app.group)
            clock.return_value = 105
            with patch.object(self.marisa, "isVisible", return_value=False):
                self.app.plugins.tick_periodic(self.app)
                self.assertIsNone(self.app.group)
            self.app.plugins.tick_periodic(self.app)
            self.assertIsNotNone(self.app.group)
            self.reach_start()
            reimu_x, marisa_x = self.reimu.cx, self.marisa.cx
            for _ in range(40):
                self.app.tick()
            self.assertIsNone(self.app.group)
            self.assertGreater(self.reimu.cx, reimu_x)
            self.assertGreater(self.marisa.cx, marisa_x)
            self.assertAlmostEqual(self.marisa.cx - self.reimu.cx, self.reimu.S * 0.60)
            self.app.plugins.tick_periodic(self.app)
            self.assertIsNone(self.app.group)
            clock.return_value = 110
            self.app.plugins.tick_periodic(self.app)
            self.assertIsNotNone(self.app.group)
