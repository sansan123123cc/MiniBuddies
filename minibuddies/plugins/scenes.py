"""Manifest schema for interactions played by explicitly named characters."""

from dataclasses import dataclass
import re

from minibuddies.effects import EFFECT_PRESETS


PACK_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
RGB = re.compile(r"#[0-9a-fA-F]{6}")


@dataclass(frozen=True)
class Effect:
    preset: str
    colors: tuple
    target: str
    ticks: int


@dataclass(frozen=True)
class Beat:
    at: int
    frame: int | None
    speech: str
    effect: Effect | None


@dataclass(frozen=True)
class Role:
    character: str
    beats: tuple
    builtin_frames: frozenset


@dataclass(frozen=True)
class Interaction:
    label: str
    roles: tuple
    characters: frozenset
    duration: int
    meet_chance: float
    meet_distance: int
    cooldown_seconds: int


def integer(value, minimum, maximum, field):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{field}는 {minimum}~{maximum} 사이의 정수여야 해요")
    return value


def probability(value, field):
    if type(value) not in (int, float) or not 0 <= value <= 1:
        raise ValueError(f"{field}는 0부터 1까지의 수여야 해요")
    return value


def speech_text(value):
    if not isinstance(value, str) or len(value) > 160:
        raise ValueError("말풍선은 160자 이내로 입력하세요")
    return value


def action_name(value, names):
    if not isinstance(value, str) or not value.strip() or len(value) > 80 or value in names:
        raise ValueError("행동마다 고유한 이름을 1~80자로 입력하세요")
    names.add(value)
    return value


def read_effect(data, character, characters):
    if not isinstance(data, dict):
        raise ValueError("effect는 JSON 객체여야 해요")
    name = data.get("preset")
    if not isinstance(name, str) or name not in EFFECT_PRESETS:
        raise ValueError("지원하는 effect의 preset 이름을 사용하세요")
    colors = data.get("colors")
    if not isinstance(colors, list) or not 1 <= len(colors) <= 6 or any(
        not isinstance(color, str) or not RGB.fullmatch(color) for color in colors
    ):
        raise ValueError("effect.colors에 #RRGGBB 색상을 1~6개 지정하세요")
    target = data.get("target")
    if not isinstance(target, str) or target not in characters or target == character:
        raise ValueError("effect.target은 상호작용에 참여하는 다른 캐릭터여야 해요")
    return Effect(name, tuple(colors), target, integer(data.get("ticks", 78), 1, 180, "effect.ticks"))


def read_role(data, characters, sprite_id):
    character = data["character"]
    steps = data.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 64:
        raise ValueError("캐릭터마다 steps를 1~64개 정의하세요")
    beats = []
    at = end = 0
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError("steps의 각 항목은 JSON 객체여야 해요")
        ticks = integer(step.get("ticks"), 1, 600, "ticks")
        if "file" in step and "frame" in step:
            raise ValueError("한 단계에는 file 또는 frame 중 하나를 사용하세요")
        frame = None
        if "frame" in step:
            frame = integer(step["frame"], 0, 9999, "frame")
        elif "file" in step:
            frame = sprite_id(step["file"])
        speech = speech_text(step.get("say", ""))
        effect = read_effect(step["effect"], character, characters) if "effect" in step else None
        beats.append(Beat(at, frame, speech, effect))
        end = max(end, at + ticks, at + effect.ticks if effect else 0)
        at += ticks
    builtin = frozenset(beat.frame for beat in beats if beat.frame is not None and beat.frame >= 0)
    return Role(character, tuple(beats), builtin), end


def read_interaction(data, allowed, names, sprite_id):
    if not isinstance(data, dict):
        raise ValueError("상호작용은 JSON 객체로 정의해 주세요")
    label = action_name(data.get("name"), names)
    roles = data.get("roles")
    if not isinstance(roles, list) or not 2 <= len(roles) <= 6:
        raise ValueError("roles에 서로 다른 캐릭터를 2~6명 지정하세요")
    characters = set()
    for role in roles:
        char = role.get("character") if isinstance(role, dict) else None
        if not isinstance(char, str) or not PACK_ID.fullmatch(char) or char in characters:
            raise ValueError("같은 캐릭터를 중복해서 쓰지 않고 chars 폴더의 이름을 사용하세요")
        characters.add(char)
    if allowed and not characters <= allowed:
        raise ValueError("roles의 캐릭터는 팩의 characters 목록에 포함되어야 해요")
    parsed = [read_role(role, characters, sprite_id) for role in roles]
    duration = max(end for _, end in parsed)
    if duration > 1800 or sum(beat.effect is not None for role, _ in parsed for beat in role.beats) > 24:
        raise ValueError("한 상호작용은 1800틱과 효과 24개 이하여야 해요")
    return Interaction(label, tuple(role for role, _ in parsed), frozenset(characters), duration,
                       probability(data.get("meet_chance", 0), "meet_chance"),
                       integer(data.get("meet_distance", 340), 64, 1200, "meet_distance"),
                       integer(data.get("cooldown_seconds", 40), 5, 600, "cooldown_seconds"))
