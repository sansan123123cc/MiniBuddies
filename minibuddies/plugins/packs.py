"""Validate a local plugin manifest and its sprite data."""

import json
from dataclasses import dataclass
from pathlib import Path

from PyQt5.QtGui import QImage, QImageReader

from minibuddies.plugins.scenes import PACK_ID, action_name, probability, read_interaction, read_steps, speech_text

CELL = 256
SETTINGS_KEY = "character_plugins"
ALPHA_MASK = bytes(int(alpha >= 32) for alpha in range(256))


@dataclass(frozen=True)
class Sprite:
    path: Path
    bounds: dict


@dataclass(frozen=True)
class Action:
    label: str
    frames: tuple
    speech: str
    idle_chance: float
    characters: frozenset
    events: tuple


@dataclass(frozen=True)
class Pack:
    id: str
    label: str
    characters: frozenset
    actions: tuple
    interactions: tuple
    participants: frozenset


def character_ids(value):
    if not isinstance(value, list) or any(not isinstance(char, str) or not PACK_ID.fullmatch(char) for char in value):
        raise ValueError("characters에는 캐릭터 폴더 이름을 적어 주세요")
    return frozenset(value)


def pack_file(folder, name):
    if not isinstance(name, str) or not name:
        raise ValueError("파일 경로가 비어 있어요")
    relative = Path(name)
    if relative.anchor or ".." in relative.parts:
        raise ValueError(f"팩 안의 상대 경로를 사용하세요 ({name})")
    path = (folder / relative).resolve(strict=True)
    if not path.is_relative_to(folder) or not path.is_file():
        raise ValueError(f"팩 밖의 파일은 사용할 수 없어요 ({name})")
    return path


def load_sprite(path):
    reader = QImageReader(str(path))
    if path.suffix.lower() != ".png" or reader.format() != b"png":
        raise ValueError(f"PNG 파일이 필요해요 ({path.name})")
    if (reader.size().width(), reader.size().height()) != (CELL, CELL):
        raise ValueError(f"PNG는 {CELL}×{CELL}이어야 해요 ({path.name})")
    image = reader.read()
    if image.isNull() or not image.hasAlphaChannel():
        raise ValueError(f"투명 배경이 있는 PNG가 필요해요 ({path.name})")
    alpha = image.convertToFormat(QImage.Format_Alpha8)
    pixels = alpha.constBits().asstring(alpha.sizeInBytes()).translate(ALPHA_MASK)
    rows = [pixels[y * alpha.bytesPerLine():y * alpha.bytesPerLine() + CELL] for y in range(CELL)]
    occupied = [(y, row.find(b"\1"), row.rfind(b"\1")) for y, row in enumerate(rows) if b"\1" in row]
    if not occupied:
        raise ValueError(f"보이는 픽셀이 없어요 ({path.name})")
    bounds = {"top": occupied[0][0] / CELL, "bottom": (occupied[-1][0] + 1) / CELL,
              "left": min(row[1] for row in occupied) / CELL,
              "right": (max(row[2] for row in occupied) + 1) / CELL}
    return Sprite(path, bounds)


def read_pack(folder, sprite_offset):
    document = pack_file(folder, "plugin.json")
    if document.stat().st_size > 65536:
        raise ValueError("plugin.json은 64KB 이하여야 해요")
    data = json.loads(document.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("지원하는 plugin.json 버전은 1이에요")
    label = data.get("name", folder.name)
    characters = character_ids(data.get("characters", []))
    if not isinstance(label, str) or not label.strip() or len(label) > 80:
        raise ValueError("플러그인 이름을 1~80자로 입력하세요")
    definitions = data.get("actions", [])
    interactions = data.get("interactions", [])
    if not isinstance(definitions, list) or len(definitions) > 24:
        raise ValueError("actions는 최대 24개까지 정의할 수 있어요")
    if not isinstance(interactions, list) or len(interactions) > 16:
        raise ValueError("interactions는 최대 16개까지 정의할 수 있어요")
    if not definitions and not interactions:
        raise ValueError("actions 또는 interactions가 하나 이상 필요해요")

    sprites = {}
    actions = []
    names = set()

    def sprite_id(file):
        path = pack_file(folder, file)
        if path not in sprites:
            if len(sprites) >= 64:
                raise ValueError("팩마다 다른 PNG는 64장까지 넣을 수 있어요")
            # Negative IDs keep user frames separate from numbered built-in sprites.
            sprites[path] = (-1 - sprite_offset - len(sprites), load_sprite(path))
        return sprites[path][0]

    for definition in definitions:
        if not isinstance(definition, dict):
            raise ValueError("행동은 JSON 객체로 정의해 주세요")
        name = action_name(definition.get("name"), names)
        speech = speech_text(definition.get("say", ""))
        chance = probability(definition.get("idle_chance", 0), "idle_chance")
        allowed = character_ids(definition.get("characters", []))
        if characters and not allowed <= characters:
            raise ValueError("동작의 캐릭터는 팩의 characters 목록에 포함되어야 해요")
        beats, duration = read_steps(definition.get("frames"), sprite_id)
        if duration > 1800 or sum(beat.effect is not None for beat in beats) > 24:
            raise ValueError("한 개별 동작은 1800틱과 효과 24개 이하여야 해요")
        sequence = []
        frame = 0
        for beat in beats:
            if beat.frame is not None:
                frame = beat.frame
            sequence.append((frame, beat.ticks))
        # Keep the final pose on screen until the last effect has finished.
        last = beats[-1]
        sequence[-1] = (frame, duration - last.at)
        events = tuple(beat for beat in beats if beat.speech or beat.effect is not None)
        actions.append(Action(name, tuple(sequence), speech, chance, allowed, events))
    allowed = frozenset(characters)
    interactions = tuple(read_interaction(item, allowed, names, sprite_id) for item in interactions)
    participants = frozenset().union(*(interaction.characters for interaction in interactions))
    return Pack(folder.name, label, allowed, tuple(actions), interactions, participants), dict(sprites.values())
