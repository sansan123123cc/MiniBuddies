"""Manifest schema for timed actions and interactions."""

from dataclasses import dataclass
import re

from minibuddies.effects import EFFECT_PRESETS, LIGHT_EFFECTS, EffectDesign, EffectLayer, Keyframe


PACK_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
RGB = re.compile(r"#[0-9a-fA-F]{6}")
SPEECH_TICKS = 120


@dataclass(frozen=True)
class Effect:
    preset: str
    colors: tuple
    target: str | None
    ticks: int
    design: EffectDesign | None = None


@dataclass(frozen=True)
class Beat:
    at: int
    ticks: int
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


def read_effect_designs(data, load_image=None):
    if not isinstance(data, dict) or len(data) > 24:
        raise ValueError("팩에 직접 만든 효과는 최대 24개까지 넣을 수 있어요")
    designs = {}
    for key, item in data.items():
        if not isinstance(key, str) or not PACK_ID.fullmatch(key) or key in EFFECT_PRESETS or not isinstance(item, dict):
            raise ValueError("효과에 기본 효과와 겹치지 않는 ID를 사용하세요")
        name = item.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise ValueError("효과 이름을 1~80자로 입력하세요")
        layers = item.get("layers")
        if not isinstance(layers, list) or not 1 <= len(layers) <= 12:
            raise ValueError("효과마다 레이어를 1~12개 넣으세요")
        designs[key] = EffectDesign(name, tuple(read_effect_layer(layer, load_image) for layer in layers))
    return designs


def read_colors(colors, *, optional=False):
    if not isinstance(colors, list) or not (0 if optional else 1) <= len(colors) <= 6 or any(
        not isinstance(color, str) or not RGB.fullmatch(color) for color in colors
    ):
        raise ValueError("#RRGGBB 색상을 1~6개 지정하세요")
    return tuple(colors)


def read_effect_layer(item, load_image):
    if not isinstance(item, dict):
        raise ValueError("효과 레이어는 JSON 객체여야 해요")
    name = item.get("name", "")
    if not isinstance(name, str) or len(name) > 60:
        raise ValueError("레이어 이름은 60자까지 입력하세요")
    kind = item.get("kind")
    if kind not in ("particles", "spark", "moon", "slash", "ring", "disc", "line", "image"):
        raise ValueError("지원하는 레이어 종류를 선택하세요")
    start = integer(item.get("start", 0), 0, 99, "레이어 시작 시점")
    end = integer(item.get("end", 100), start + 1, 100, "레이어 끝 시점")
    anchor, blend = item.get("anchor", "source"), item.get("blend", "normal")
    if anchor not in ("source", "midpoint", "target") or blend not in ("normal", "add"):
        raise ValueError("지원하는 기준 위치와 합성 방식을 선택하세요")
    frames = item.get("keyframes", [{"at": 0}])
    if not isinstance(frames, list) or not 1 <= len(frames) <= 12 or any(not isinstance(frame, dict) for frame in frames):
        raise ValueError("레이어마다 키프레임을 1~12개 넣으세요")
    keyframes = sorted((Keyframe(integer(frame.get("at"), 0, 100, "키프레임 시점"),
                                 integer(frame.get("x", 0), -200, 200, "X 위치"),
                                 integer(frame.get("y", 0), -200, 200, "Y 위치"),
                                 integer(frame.get("scale", 100), 1, 300, "크기"),
                                 integer(frame.get("rotation", 0), -720, 720, "회전"),
                                 integer(frame.get("opacity", 100), 0, 100, "불투명도")) for frame in frames),
                       key=lambda frame: frame.at)
    if len({frame.at for frame in keyframes}) != len(keyframes):
        raise ValueError("같은 시점에 키프레임을 두 개 넣을 수 없어요")
    common = {"kind": kind, "start": start, "end": end, "anchor": anchor, "blend": blend,
              "keyframes": tuple(keyframes), "colors": read_colors(item.get("colors", []), optional=True)}
    if kind == "image":
        files = item.get("files")
        if not isinstance(files, list) or not 1 <= len(files) <= 16 or any(not isinstance(path, str) or not path for path in files):
            raise ValueError("PNG 레이어에 프레임을 1~16장 넣으세요")
        return EffectLayer(**common, files=tuple(files), images=tuple(map(load_image, files)) if load_image else ())
    size = integer(item.get("size", 5), 1, 10, "굵기 또는 탄 크기")
    if kind != "particles":
        length = integer(item.get("length", 100), 10, 180 if kind in LIGHT_EFFECTS else 240, "길이 또는 지름")
        return EffectLayer(**common, size=size, length=length)
    shape = item.get("shape", "orb")
    speed = item.get("speed", 3.0)
    if shape not in ("orb", "diamond", "petal") or type(speed) not in (int, float) or not 0.5 <= speed <= 4.5:
        raise ValueError("탄 모양을 고르고 속도를 0.5~4.5 사이로 입력하세요")
    waves = integer(item.get("waves", 3), 1, 5, "발사 횟수")
    interval = integer(item.get("interval", 17), 1, 36, "발사 간격")
    if (waves - 1) * interval > 60:
        raise ValueError("마지막 탄이 효과 안에서 재생되도록 발사 횟수나 간격을 줄이세요")
    return EffectLayer(**common, size=size, shape=shape,
                       count=integer(item.get("count", 8), 1, 32, "한 번에 나가는 탄 수"),
                       spread=integer(item.get("spread", 90), 0, 360, "발사 각도"), speed=speed, waves=waves, interval=interval)


def read_effect(data, character, characters, designs):
    if not isinstance(data, dict):
        raise ValueError("effect는 JSON 객체여야 해요")
    name = data.get("preset")
    if not isinstance(name, str) or (name not in EFFECT_PRESETS and name not in designs):
        raise ValueError("지원하는 effect의 preset 이름을 사용하세요")
    colors = read_colors(data.get("colors"))
    target = data.get("target")
    if characters is None and target is not None:
        raise ValueError("개별 동작의 효과는 캐릭터가 바라보는 방향으로 재생해요")
    if characters is not None and (not isinstance(target, str) or target not in characters or target == character):
        raise ValueError("effect.target은 상호작용에 참여하는 다른 캐릭터여야 해요")
    return Effect(name, colors, target, integer(data.get("ticks", 78), 1, 180, "effect.ticks"), designs.get(name))


def read_steps(steps, sprite_id, *, character=None, characters=None, designs=None):
    if not isinstance(steps, list) or not 1 <= len(steps) <= 64:
        raise ValueError("액션 단계를 1~64개 정의하세요")
    beats = []
    at = end = 0
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError("각 액션 단계는 JSON 객체여야 해요")
        ticks = integer(step.get("ticks"), 1, 600, "ticks")
        if "file" in step and "frame" in step:
            raise ValueError("한 단계에는 file 또는 frame 중 하나를 사용하세요")
        frame = None
        if "frame" in step:
            frame = integer(step["frame"], 0, 9999, "frame")
        elif "file" in step:
            frame = sprite_id(step["file"])
        speech = speech_text(step.get("say", ""))
        effect = read_effect(step["effect"], character, characters, designs or {}) if "effect" in step else None
        beats.append(Beat(at, ticks, frame, speech, effect))
        end = max(end, at + ticks, at + effect.ticks if effect else 0)
        at += ticks
    return tuple(beats), end


def read_role(data, characters, sprite_id, designs):
    character = data["character"]
    beats, end = read_steps(data.get("steps"), sprite_id, character=character, characters=characters, designs=designs)
    builtin = frozenset(beat.frame for beat in beats if beat.frame is not None and beat.frame >= 0)
    return Role(character, beats, builtin), end


def read_interaction(data, allowed, names, sprite_id, designs=None):
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
    parsed = [read_role(role, characters, sprite_id, designs) for role in roles]
    duration = max(end for _, end in parsed)
    if duration > 1800 or sum(beat.effect is not None for role, _ in parsed for beat in role.beats) > 24:
        raise ValueError("한 상호작용은 1800틱과 효과 24개 이하여야 해요")
    return Interaction(label, tuple(role for role, _ in parsed), frozenset(characters), duration,
                       probability(data.get("meet_chance", 0), "meet_chance"),
                       integer(data.get("meet_distance", 340), 64, 1200, "meet_distance"),
                       integer(data.get("cooldown_seconds", 40), 5, 600, "cooldown_seconds"))
