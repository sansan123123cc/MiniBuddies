"""Manage plugin bindings and replay actions on opted-in pets."""

import random
from pathlib import Path

from minibuddies.plugins.interactions import InteractionLibrary
from minibuddies.plugins.packs import SETTINGS_KEY, read_pack
from minibuddies.plugins.scenes import PACK_ID


class PluginLibrary:
    def __init__(self, root, report_error, installed_root=None):
        self.root = Path(root)
        self.packs = []
        self.sprites = {}
        self.interactions = InteractionLibrary(self)
        self.report_error = report_error
        roots = (self.root,) if installed_root is None else (self.root, Path(installed_root))
        for directory in roots:
            try:
                for folder in sorted(directory.iterdir()) if directory.is_dir() else ():
                    if folder.is_dir() and PACK_ID.fullmatch(folder.name) and (folder / "plugin.json").is_file():
                        self.load_folder(folder, directory)
            except OSError as error:
                report_error(f"[플러그인] {error}\n")

    def load_folder(self, folder, directory):
        try:
            resolved = folder.resolve()
            if resolved.parent != directory.resolve() or resolved.name != folder.name:
                raise ValueError("플러그인 폴더에는 외부 폴더 링크를 사용할 수 없어요")
            if any(pack.id == folder.name for pack in self.packs):
                raise ValueError("같은 ID의 플러그인이 이미 있어요")
            pack, sprites = read_pack(resolved, len(self.sprites))
        except (OSError, ValueError, RuntimeError) as error:
            self.report_error(f"[플러그인] {folder.name}: {error}\n")
            return False
        self.packs.append(pack)
        self.sprites.update(sprites)
        return True

    def available(self, char):
        return (pack for pack in self.packs
                if char in pack.participants or any(self.action_allowed(pack, action, char) for action in pack.actions))

    @staticmethod
    def action_allowed(pack, action, char):
        return (not pack.characters or char in pack.characters) and (not action.characters or char in action.characters)

    def actions_for(self, pack, char):
        return (action for action in pack.actions if self.action_allowed(pack, action, char))

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

    def can_play_action(self, pet, action):
        return self.can_play(pet) and all(frame < 0 or pet.has_frame(frame) for frame, _ in action.frames)

    def play(self, pet, pack, action):
        if (action not in self.actions_for(pack, pet.char) or pack not in self.enabled(pet)
                or not self.can_play_action(pet, action)):
            return False

        def finish():
            pet.stand_on(pet.surface)
            pet.set("idle", 60)

        pet.play_seq(action.frames, after=finish)
        pet.align_sequence = True
        pet.fy = pet.surface[1] - pet.S * pet.fbottom(pet.frame())
        if action.speech:
            pet.say(action.speech, min(pet.seq_total, 120))
        return True

    def play_idle(self, pet):
        for pack in self.enabled(pet):
            for action in self.actions_for(pack, pet.char):
                if action.idle_chance and random.random() < action.idle_chance and self.play(pet, pack, action):
                    return True
        return False
