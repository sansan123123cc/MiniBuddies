"""Editable pack data and validation shared by the editor and installer."""

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
import re

from minibuddies.plugins.packs import load_sprite, pack_file, read_pack

ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}")
ASSET = re.compile(r"assets/[a-f0-9]{24}\.png")
IMAGE_LIMIT = 1024 * 1024
FRAME_LIMIT = 256
JSON_LIMIT = 64 * 1024
RESERVED = {"con", "prn", "aux", "nul", *(f"{name}{i}" for name in ("com", "lpt") for i in range(1, 10))}


@dataclass
class Project:
    kind: str = "plugin"
    id: str = ""
    name: str = ""
    author: str = ""
    description: str = ""
    rules: dict = field(default_factory=lambda: {"version": 1, "actions": [], "interactions": []})
    assets: dict = field(default_factory=dict)
    frames: dict = field(default_factory=dict)
    cover: bytes | None = None

    def add_image(self, data):
        key = f"assets/{sha256(data).hexdigest()[:24]}.png"
        self.assets[key] = data
        return key

    def thumbnail(self):
        return self.cover or self.frames.get(0) or next((self.assets[step["file"]] for step in image_steps(self.rules)
                                                        if step["file"] in self.assets), None)


def sections(data, key):
    if not isinstance(data, dict) or not isinstance(items := data.get(key, []), list) or any(not isinstance(item, dict) for item in items):
        raise ValueError(f"{key}에는 JSON 객체 목록을 넣으세요.")
    return items


def image_steps(rules):
    """Yield only the places where the runtime schema accepts a sprite filename."""
    sequences = [sections(action, "frames") for action in sections(rules, "actions")]
    for interaction in sections(rules, "interactions"):
        sequences.extend(sections(role, "steps") for role in sections(interaction, "roles"))
    for sequence in sequences:
        for step in sequence:
            if "file" in step:
                if not isinstance(step["file"], str):
                    raise ValueError("액션 파일 이름은 문자열이어야 해요.")
                yield step


def validate_id(key):
    if not isinstance(key, str) or not ID.fullmatch(key) or key in RESERVED:
        raise ValueError("팩 ID는 영문 소문자·숫자로 시작하고, 영문 소문자·숫자·하이픈·밑줄 48자 이하여야 해요.")
    return key


def validate_text(value, length, field, *, required=False):
    if not isinstance(value, str) or len(value) > length or (required and not value.strip()):
        raise ValueError(f"{field}을(를) {length}자 이내로 입력하세요.")
    return value


def json_file(path, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(data) > JSON_LIMIT:
        raise ValueError("설정 파일이 너무 커요.")
    path.write_bytes(data)


def read_image(path):
    path = Path(path)
    if path.stat().st_size > IMAGE_LIMIT:
        raise ValueError("PNG 한 장은 1MB 이하여야 해요.")
    load_sprite(path)
    return path.read_bytes()


def write_image(path, data):
    if len(data) > IMAGE_LIMIT:
        raise ValueError("PNG 한 장은 1MB 이하여야 해요.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return load_sprite(path).bounds


def metadata(project):
    kind = project.kind
    if kind not in ("character", "plugin"):
        raise ValueError("지원하는 팩 종류가 아니에요.")
    return {"format": "minibuddies-pack", "version": 1, "id": validate_id(project.id), "kind": kind,
            "name": validate_text(project.name, 80, "이름", required=True),
            "author": validate_text(project.author, 80, "제작자"),
            "description": validate_text(project.description, 2000, "설명"),
            "actions": len(sections(project.rules, "actions")), "interactions": len(sections(project.rules, "interactions")),
            "frames": len(project.frames), "preview": "preview.png" if project.thumbnail() else None}


def materialize(project, root):
    info = metadata(project)
    if project.kind == "plugin" and project.frames:
        raise ValueError("플러그인 팩은 액션에서 사용할 PNG만 넣을 수 있어요.")
    root.mkdir()
    if info["preview"]:
        write_image(root / "preview.png", project.thumbnail())
    if project.kind == "character":
        if 0 not in project.frames or len(project.frames) > FRAME_LIMIT:
            raise ValueError("캐릭터에는 기본 자세 0번이 필요하고, 프레임은 최대 256장까지 넣을 수 있어요.")
        character = root / "character"
        bounds = {}
        for number, data in sorted(project.frames.items()):
            if type(number) is not int or not 0 <= number <= 9999:
                raise ValueError("프레임 번호는 0~9999 사이여야 해요.")
            bounds[str(number)] = write_image(character / f"{number}.png", data)
        json_file(character / "meta.json", {"cell": 256, "frames": bounds})
        (character / "name.txt").write_text(project.name + "\n", encoding="utf-8")
    if project.kind == "plugin" or info["actions"] or info["interactions"]:
        rules = {**project.rules, "version": 1, "name": project.name}
        files = {step["file"] for step in image_steps(rules)}
        if len(files) > 64:
            raise ValueError("동작에 추가할 PNG는 최대 64장이에요.")
        for filename in sorted(files):
            if not ASSET.fullmatch(filename) or filename not in project.assets:
                raise ValueError("동작에 사용할 그림이 팩에 없어요.")
            write_image(root / filename, project.assets[filename])
        json_file(root / "plugin.json", rules)
        read_pack(root, 0)
    json_file(root / "pack.json", info)
    return info


def load_legacy(folder):
    folder = Path(folder).resolve()
    read_pack(folder, 0)
    rules = json.loads((folder / "plugin.json").read_text(encoding="utf-8-sig"))
    key = folder.name.replace(".", "-")
    project = Project(id=key if ID.fullmatch(key) and key not in RESERVED else "",
                      name=rules.get("name", folder.name), rules=rules)
    for step in image_steps(rules):
        step["file"] = project.add_image(read_image(pack_file(folder, step["file"])))
    return project
