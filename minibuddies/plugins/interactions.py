"""Match nearby pets to a manifest's roles and play their shared timeline."""

from collections import defaultdict
import random
import time

from minibuddies.effects import PluginEffectOverlay
from minibuddies.group_hooks import GroupHooks, close_effect, ground_group_interrupted, restore_ground_pet


def start_timeline(app, group, members):
    group["speech"] = {}
    for pet in members:
        pet.face = 1 if pet.cx < group["cx"] else -1
        pet.vx = 0
        pet.gframe = [0]
    if group["has_effects"]:
        group["effect"] = PluginEffectOverlay(members, app.on_top)
    advance_timeline(app, group, members, 0)


def advance_timeline(app, group, members, elapsed):
    if elapsed >= group["interaction"].duration:
        app.group_break()
        return
    overlay = group.get("effect")
    for pet, beat in group["timeline"].get(elapsed, ()):
        if beat.frame is not None:
            pet.gframe = [beat.frame]
            pet.fy = group["floor"][1] - pet.S * pet.fbottom(beat.frame)
        if beat.speech:
            previous = pet.bubble
            pet.say(beat.speech, min(120, group["interaction"].duration - elapsed))
            if pet.bubble is not previous and pet.bubble is not None:
                group["speech"][pet] = pet.bubble
        if beat.effect:
            overlay.show_effect(pet, group["cast"][beat.effect.target], beat.effect, elapsed)
    if overlay is not None:
        overlay.advance(elapsed)


def should_break(app, group, members):
    return ground_group_interrupted(app, group, members) or any(
        group["pack_id"] not in app.plugins.selected(app.cfg, pet.char) for pet in members
    )


def close_timeline(group):
    close_effect(group)
    for pet, bubble in group.get("speech", {}).items():
        if pet.bubble is bubble:
            bubble.close()
            pet.bubble = None


HOOKS = GroupHooks(start_timeline, advance_timeline, should_break, close_timeline, restore_ground_pet)


class InteractionLibrary:
    def __init__(self, plugins):
        self.plugins = plugins
        self.next_meet = {}

    def enabled(self, app, who=None):
        for pack in self.plugins.packs:
            for interaction in pack.interactions:
                if who is not None and who.char not in interaction.characters:
                    continue
                if all(pack.id in self.plugins.selected(app.cfg, char) for char in interaction.characters):
                    yield pack, interaction

    def formation(self, app, interaction, who=None):
        builtin = {role.character: role.builtin_frames for role in interaction.roles}
        eligible = sorted(
            (pet for pet in app.buddies if pet.char in interaction.characters and self.plugins.can_play(pet)
             and all(pet.has_frame(frame) for frame in builtin[pet.char])),
            key=lambda pet: pet.cx,
        )
        if len(eligible) < len(interaction.roles) or (who is not None and who not in eligible):
            return None
        for i, first in enumerate(eligible):
            screen = first.scr()
            floor = first.surface
            candidates = [pet for pet in eligible[i:]
                          if pet.cx - first.cx <= interaction.meet_distance
                          and pet.surface == floor and pet.scr() == screen]
            if who is not None and who not in candidates:
                continue
            cast = {who.char: who} if who is not None else {}
            for pet in candidates:
                cast.setdefault(pet.char, pet)
            if set(cast) != interaction.characters:
                continue
            members = sorted(cast.values(), key=lambda pet: pet.cx)
            size = max(pet.S for pet in members)
            left = max(screen.left(), floor[0]) + size / 2
            right = min(screen.right(), floor[2]) - size / 2
            gap = min(size * 1.6, (right - left) / (len(members) - 1))
            if gap < size * 0.7:
                continue
            extent = gap * (len(members) - 1) / 2
            center = min(max(left + extent, sum(pet.cx for pet in members) / len(members)), right - extent)
            return members, cast, floor, center, gap
        return None

    def play(self, app, pack, interaction, who=None):
        if (pack, interaction) not in self.enabled(app, who):
            return False
        formation = self.formation(app, interaction, who)
        if formation is None:
            return False
        members, cast, floor, center, gap = formation
        timeline = defaultdict(list)
        has_effects = False
        for role in interaction.roles:
            for beat in role.beats:
                timeline[beat.at].append((cast[role.character], beat))
                has_effects = has_effects or beat.effect is not None
        for i, pet in enumerate(members):
            pet.vx = 0
            pet.gx = center + gap * (i - (len(members) - 1) / 2)
            pet.set("gather", 99999)
        app.group = {"kind": "plugin_interaction", "hooks": HOOKS, "mem": members, "cx": center,
                     "phase": "gather", "t": 0, "t0": 0, "floor": floor, "pack_id": pack.id,
                     "interaction": interaction, "cast": cast, "timeline": timeline, "has_effects": has_effects}
        self.next_meet[pack.id, interaction.label] = time.monotonic() + interaction.cooldown_seconds
        return True

    def try_automatic(self, app):
        if app.group or app.scene or app.quiet() or not app.cfg.get("auto_group", True):
            return False
        now = time.monotonic()
        for pack, interaction in self.enabled(app):
            if (interaction.meet_chance and self.next_meet.get((pack.id, interaction.label), 0) <= now
                    and random.random() < interaction.meet_chance and self.play(app, pack, interaction)):
                return True
        return False
