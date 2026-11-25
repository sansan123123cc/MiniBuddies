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
from PyQt5.QtWidgets import QMenu

from minibuddies import app as application


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
