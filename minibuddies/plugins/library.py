"""Manage character and plugin actions and replay them on pets."""

import random
import time
from pathlib import Path

from minibuddies.plugins.actions import ActionPlayback
from minibuddies.plugins.interactions import InteractionLibrary
from minibuddies.plugins.packs import SETTINGS_KEY, read_pack
from minibuddies.plugins.scenes import PACK_ID


class PluginLibrary:
    def __init__(self, root, report_error, installed_root=None, *, installed_characters=()):
        self.root = Path(root)
        self.packs = []
        self.character_packs = {}
        self.pack_folders = {}
        self.sprites = {}
        self.sprite_offset = 0
        self.interactions = InteractionLibrary(self)
        self.next_repeat = {}
        self.report_error = report_error
        installed_root = Path(installed_root) if installed_root is not None else None
        roots = (self.root,) if installed_root is None else (self.root, installed_root)
        for directory in roots:
            try:
                for folder in sorted(directory.iterdir()) if directory.is_dir() else ():
                    if folder.is_dir() and PACK_ID.fullmatch(folder.name) and (folder / "plugin.json").is_file():
                        self.load_folder(folder, directory, character_pack=(
                            directory == installed_root and folder.name in installed_characters))
            except OSError as error:
                report_error(f"[플러그인] {error}\n")

    def load_folder(self, folder, directory, *, character_pack=False):
        try:
            resolved = folder.resolve()
            if resolved.parent != directory.resolve() or resolved.name != folder.name:
                raise ValueError("플러그인 폴더에는 외부 폴더 링크를 사용할 수 없어요")
            if any(pack.id == folder.name for pack in self.packs):
                raise ValueError("같은 ID의 플러그인이 이미 있어요")
            pack, sprites = read_pack(resolved, self.sprite_offset)
        except (OSError, ValueError, RuntimeError) as error:
            self.report_error(f"[플러그인] {folder.name}: {error}\n")
            return False
        self.packs.append(pack)
        self.pack_folders[pack.id] = resolved
        self.sprites.update(sprites)
        self.sprite_offset += len(sprites)
        if character_pack:
            self.character_packs[pack.id] = pack
        return True

    def unload_folder(self, folder):
        pack_id = folder.name
        if self.pack_folders.get(pack_id) != folder:
            return set()
        del self.pack_folders[pack_id]
        self.packs[:] = [pack for pack in self.packs if pack.id != pack_id]
        self.character_packs.pop(pack_id, None)
        self.next_repeat = {key: stamp for key, stamp in self.next_repeat.items() if key[0] != pack_id}
        self.interactions.next_meet = {key: stamp for key, stamp in self.interactions.next_meet.items()
                                       if key[0] != pack_id}
        frames = {frame for frame, sprite in self.sprites.items() if sprite.path.is_relative_to(folder)}
        for frame in frames:
            del self.sprites[frame]
        return frames

    def available(self, char):
        return (pack for pack in self.packs
                if char in pack.participants or any(self.action_allowed(pack, action, char) for action in pack.actions))

    @staticmethod
    def action_allowed(pack, action, char):
        return (not pack.characters or char in pack.characters) and (not action.characters or char in action.characters)

    def actions_for(self, pack, char):
        return (action for action in pack.actions if self.action_allowed(pack, action, char))

    @staticmethod
    def configured_plugins(cfg, char):
        assignments = cfg.get(SETTINGS_KEY)
        selected = assignments.get(char) if isinstance(assignments, dict) else None
        return set(item for item in selected if isinstance(item, str)) if isinstance(selected, list) else set()

    def selected(self, cfg, char):
        selected = self.configured_plugins(cfg, char)
        if char in self.character_packs:
            selected.add(char)
        return selected

    def bind(self, app, char, pack_id, enabled):
        if char not in app.chars or all(pack.id != pack_id for pack in self.available(char)):
            return False
        if char == pack_id and char in self.character_packs:
            return enabled
        previous = app.cfg.get(SETTINGS_KEY)
        assignments = dict(previous) if isinstance(previous, dict) else {}
        selected = self.configured_plugins(app.cfg, char)
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
    def can_control(pet):
        return pet in pet.app.buddies and pet.drag is None and pet.isVisible()

    def can_play(self, pet):
        app = pet.app
        return (self.can_control(pet) and pet.goal is None
                and pet.state in app.DUO_FREE and pet.surface is not None and pet.surface_alive()
                and not (app.group or app.scene or app.quiet()))

    def can_play_action(self, pet, action, *, manual=False):
        ready = self.can_control(pet) if manual else self.can_play(pet)
        return ready and all(frame < 0 or pet.has_frame(frame) for frame, _ in action.frames)

    def play(self, pet, pack, action, *, manual=False):
        if (action not in self.actions_for(pack, pet.char) or pack not in self.enabled(pet)
                or not self.can_play_action(pet, action, manual=manual)):
            return False

        if manual:
            app = pet.app
            if app.group and pet in app.group["mem"]:
                app.group_break()
            pet.stop_plugin_action()
            app.ground(pet)
            if not pet.surface_alive():
                pet.stand_on(pet.surfaces()[-1])

        def finish():
            if pet.plugin_action is not None and pet.plugin_action.motion is not None:
                pet.plugin_action.advance(pet.seq_total)
            pet.stand_on(pet.surface)
            pet.set("idle", 60)

        pet.play_seq(action.frames, after=finish)
        pet.align_sequence = True
        pet.fy = pet.surface[1] - pet.S * pet.fbottom(pet.frame())
        pet.plugin_action = ActionPlayback(pet, pack.id, action.events)
        pet.plugin_action.advance(0, action.speech)
        return True

    def play_idle(self, pet):
        for pack in self.enabled(pet):
            for action in self.actions_for(pack, pet.char):
                if action.idle_chance and random.random() < action.idle_chance and self.play(pet, pack, action):
                    return True
        return False

    def periodic_rules(self, app):
        for pet in app.buddies:
            for pack in self.enabled(pet):
                for action in self.actions_for(pack, pet.char):
                    if action.interval_seconds:
                        yield pack, action, pet
        if app.cfg.get("auto_group", True):
            for pack, interaction in self.interactions.enabled(app):
                if interaction.interval_seconds:
                    yield pack, interaction, None

    def tick_periodic(self, app):
        now = time.monotonic()
        next_repeat = {}
        for pack, rule, pet in self.periodic_rules(app):
            key = (pack.id, rule.label, pet)
            deadline = self.next_repeat.get(key, now + rule.interval_seconds)
            if deadline <= now:
                started = self.play(pet, pack, rule) if pet is not None else self.interactions.play(app, pack, rule)
                if started:
                    deadline = now + rule.interval_seconds
            next_repeat[key] = deadline
        self.next_repeat = next_repeat
