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


def make_sprite(path, height):
    image = QImage(256, 256, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.fillRect(48, 30, 160, height, QColor("#f65e92"))
    painter.end()
    if not image.save(str(path)):
        raise RuntimeError(f"Could not write {path}")


class PluginIntegrationTest(unittest.TestCase):
    def test_character_menu_binding_and_playback(self):
        with TemporaryDirectory(prefix="minibuddies-plugins-") as directory:
            root = Path(directory)
            self.exercise_application(root)

    def exercise_application(self, root):
        active = ["reimu", "marisa"]
        for char in active:
            folder = root / "chars" / char
            folder.mkdir(parents=True)
            make_sprite(folder / "0.png", 190)
        (root / "roster.txt").write_text("+".join(active) + "!", encoding="utf-8")
        (root / "settings.json").write_text(json.dumps({
            "active": active, "mcp": False, "climb": False, "weather": False, "on_top": False,
        }), encoding="utf-8")

        valid = root / "plugins" / "wave-pack"
        valid.mkdir(parents=True)
        make_sprite(valid / "first.png", 200)
        make_sprite(valid / "second.png", 120)
        data = {"version": 1, "name": "인사 팩", "actions": [
            {"name": "손 흔들기", "say": "안녕!", "idle_chance": 1,
             "frames": [{"file": "first.png", "ticks": 2}, {"file": "second.png", "ticks": 3}]},
        ]}
        (valid / "plugin.json").write_text(json.dumps(data), encoding="utf-8")
        invalid = root / "plugins" / "bad-pack"
        invalid.mkdir()
        data["actions"][0]["frames"][0]["file"] = "../wave-pack/first.png"
        (invalid / "plugin.json").write_text(json.dumps(data), encoding="utf-8")
        restricted = root / "plugins" / "marisa-only"
        restricted.mkdir()
        make_sprite(restricted / "frame.png", 180)
        (restricted / "plugin.json").write_text(json.dumps({
            "version": 1, "characters": ["marisa"], "actions": [
                {"name": "마리사 인사", "frames": [{"file": "frame.png", "ticks": 4}]},
            ],
        }), encoding="utf-8")

        errors = []
        with patch.object(application, "BASE", str(root)), patch.object(application, "CHARS_DIR", str(root / "chars")), \
                patch.object(application, "_crash_write", errors.append), patch.object(sys, "argv", [str(root / "buddies.py")]):
            app = application.App()
        self.addCleanup(app.lock.close)
        self.assertTrue(any("bad-pack" in error for error in errors))
        self.assertEqual([pack.id for pack in app.plugins.packs], ["marisa-only", "wave-pack"])
        self.assertEqual([pack.id for pack in app.plugins.available("reimu")], ["wave-pack"])

        pets = []
        for index, char in enumerate(active):
            app.add(entrance="drop", char=char)
            pet = app.buddies[-1]
            self.addCleanup(pet.close)
            pet.fx = 120 + index * 210
            pet.stand_on(pet.surfaces()[-1])
            pet.set("idle", 60)
            pet.show()
            pets.append(pet)
        reimu, marisa = pets
        pack = next(app.plugins.available("reimu"))
        action = pack.actions[0]
        self.assertFalse(app.plugins.play(reimu, pack, action))
        with patch.object(app, "save_cfg", return_value=False):
            self.assertFalse(app.plugins.bind(app, reimu.char, pack.id, True))
        self.assertEqual(app.plugins.selected(app.cfg, reimu.char), set())

        def pack_menu(pet):
            context = QMenu()
            app.plugin_menu(context, pet)
            plugin_menu = context.actions()[0].menu()
            return context, next(item.menu() for item in plugin_menu.actions() if item.text() == pack.label)

        menu, options = pack_menu(reimu)
        options.actions()[0].trigger()
        self.assertEqual(json.loads((root / "settings.json").read_text())["character_plugins"], {"reimu": ["wave-pack"]})
        self.assertFalse(app.plugins.play(marisa, pack, action))

        reimu.set("run", 80)
        group = app.group = {"mem": [marisa]}
        self.assertFalse(app.plugins.play(reimu, pack, action))
        menu, options = pack_menu(reimu)
        self.assertTrue(options.actions()[-1].isEnabled())
        options.actions()[-1].trigger()
        self.assertIs(app.group, group)
        app.group = None
        self.assertEqual(reimu.state, "seq")
        self.assertEqual(reimu.frame(), action.frames[0][0])
        self.assertEqual(reimu.feet(reimu.frame()), reimu.surface[1])
        self.assertFalse(app.pix(reimu.frame(), reimu.char).isNull())
        reimu.step()
        reimu.step()
        self.assertEqual(reimu.frame(), action.frames[1][0])
        self.assertEqual(reimu.feet(reimu.frame()), reimu.surface[1])
        for _ in range(3):
            reimu.step()
        self.assertEqual(reimu.state, "idle")
        self.assertEqual(reimu.feet(), reimu.surface[1])

        reimu.choose()
        self.assertEqual(reimu.state, "seq")
        menu, options = pack_menu(reimu)
        options.actions()[0].trigger()
        for _ in range(5):
            reimu.step()
        self.assertEqual(reimu.state, "idle")
        self.assertFalse(app.plugins.play_idle(reimu))
        self.assertEqual(marisa.state, "idle")
