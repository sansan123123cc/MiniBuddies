"""Load local animation packs and run actions on the pets that opt into them."""

from dataclasses import dataclass
import json
from pathlib import Path
import random
import re

from PyQt5.QtGui import QImage, QImageReader


CELL = 256
SETTINGS_KEY = "character_plugins"
PACK_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
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


@dataclass(frozen=True)
class Pack:
    id: str
    label: str
    characters: frozenset
    actions: tuple


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
    characters = data.get("characters", [])
    if not isinstance(label, str) or not label.strip() or len(label) > 80:
        raise ValueError("플러그인 이름을 1~80자로 입력하세요")
    if not isinstance(characters, list) or any(not isinstance(char, str) or not PACK_ID.fullmatch(char) for char in characters):
        raise ValueError("characters에는 캐릭터 폴더 이름을 적어 주세요")
    definitions = data.get("actions")
    if not isinstance(definitions, list) or not 1 <= len(definitions) <= 24:
        raise ValueError("행동은 1~24개를 정의해 주세요")

    sprites = {}
    actions = []
    names = set()
    for definition in definitions:
        if not isinstance(definition, dict):
            raise ValueError("행동은 JSON 객체로 정의해 주세요")
        name = definition.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > 80 or name in names:
            raise ValueError("행동마다 고유한 이름을 1~80자로 입력하세요")
        names.add(name)
        speech = definition.get("say", "")
        chance = definition.get("idle_chance", 0)
        if not isinstance(speech, str) or len(speech) > 160:
            raise ValueError("말풍선은 160자 이내로 입력하세요")
        if type(chance) not in (int, float) or not 0 <= chance <= 1:
            raise ValueError("idle_chance는 0부터 1까지의 수여야 해요")
        frames = definition.get("frames")
        if not isinstance(frames, list) or not 1 <= len(frames) <= 64:
            raise ValueError("행동의 프레임은 1~64개여야 해요")
        sequence = []
        for frame in frames:
            ticks = frame.get("ticks") if isinstance(frame, dict) else None
            if type(ticks) is not int or not 1 <= ticks <= 600:
                raise ValueError("프레임의 ticks는 1~600 사이의 정수여야 해요")
            path = pack_file(folder, frame.get("file"))
            if path not in sprites:
                if len(sprites) >= 64:
                    raise ValueError("팩마다 다른 PNG는 64장까지 넣을 수 있어요")
                # Negative IDs keep user frames separate from numbered built-in sprites.
                sprites[path] = (-1 - sprite_offset - len(sprites), load_sprite(path))
            sequence.append((sprites[path][0], ticks))
        if sum(ticks for _, ticks in sequence) > 1800:
            raise ValueError("한 행동의 전체 길이는 1800틱 이하여야 해요")
        actions.append(Action(name, tuple(sequence), speech, chance))
    return Pack(folder.name, label, frozenset(characters), tuple(actions)), dict(sprites.values())


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
