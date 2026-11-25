"""Manage plugin bindings and replay actions on opted-in pets."""

import random
from minibuddies.plugins.packs import PACK_ID, SETTINGS_KEY, read_pack
from pathlib import Path


class PluginLibrary:
    def __init__(self, root, report_error):
        self.root = Path(root)
        self.packs = []
        self.sprites = {}
        try:
            folders = sorted(self.root.iterdir()) if self.root.is_dir() else []
        except OSError as error:
            report_error(f"[플러그인] {error}\n")
            return
        for folder in folders:
            if not folder.is_dir() or not PACK_ID.fullmatch(folder.name):
                continue
            try:
                if folder.resolve().parent != self.root.resolve() or folder.resolve().name != folder.name:
                    raise ValueError("플러그인 폴더에는 외부 폴더 링크를 사용할 수 없어요")
                pack, sprites = read_pack(folder.resolve(), len(self.sprites))
            except (OSError, ValueError, RuntimeError) as error:
                report_error(f"[플러그인] {folder.name}: {error}\n")
                continue
            self.packs.append(pack)
            self.sprites.update(sprites)

    def available(self, char):
        return (pack for pack in self.packs if not pack.characters or char in pack.characters)

    def selected(self, cfg, char):
        assignments = cfg.get(SETTINGS_KEY)
        selected = assignments.get(char) if isinstance(assignments, dict) else None
        return set(item for item in selected if isinstance(item, str)) if isinstance(selected, list) else set()

    def bind(self, app, char, pack_id, enabled):
        if char not in app.chars or all(pack.id != pack_id for pack in self.available(char)):
            return False
        previous = app.cfg.get(SETTINGS_KEY)
        assignments = dict(previous) if isinstance(previous, dict) else {}
        selected = self.selected(app.cfg, char)
        if enabled:
            selected.add(pack_id)
        else:
            selected.discard(pack_id)
        if selected:
            assignments[char] = sorted(selected)
        else:
            assignments.pop(char, None)
        app.cfg[SETTINGS_KEY] = assignments
        if app.save_cfg():
            return True
        if previous is None:
            app.cfg.pop(SETTINGS_KEY, None)
        else:
            app.cfg[SETTINGS_KEY] = previous
        return False

    def enabled(self, pet):
        selected = self.selected(pet.app.cfg, pet.char)
        return (pack for pack in self.available(pet.char) if pack.id in selected) if selected else iter(())

    @staticmethod
    def can_play(pet):
        app = pet.app
        return (pet in app.buddies and pet.drag is None and pet.goal is None and pet.isVisible()
                and pet.state in app.DUO_FREE and pet.surface is not None and pet.surface_alive()
                and not (app.group or app.scene or app.quiet()))

    def play(self, pet, pack, action):
        if action not in pack.actions or pack not in self.enabled(pet) or not self.can_play(pet):
            return False

        def finish():
            pet.stand_on(pet.surface)
            pet.set("idle", 60)

        pet.play_seq(action.frames, after=finish)
        pet.fy = pet.surface[1] - pet.S * pet.fbottom(pet.frame())
        if action.speech:
            pet.say(action.speech, min(pet.seq_total, 120))
        return True

    def play_idle(self, pet):
        for pack in self.enabled(pet):
            for action in pack.actions:
                if action.idle_chance and random.random() < action.idle_chance and self.play(pet, pack, action):
                    return True
        return False
