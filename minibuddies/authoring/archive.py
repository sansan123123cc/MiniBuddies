"""Read and write portable .mbpack ZIP files without extracting arbitrary paths."""

import json
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from minibuddies.authoring.project import (
    ASSET, FRAME_LIMIT, IMAGE_LIMIT, JSON_LIMIT, Project, materialize, validate_id, validate_text,
)

EXTENSION = ".mbpack"
CHARACTER_FRAME = re.compile(r"character/(0|[1-9][0-9]{0,3})\.png")
CONTROL_FILES = {"pack.json", "plugin.json", "preview.png", "character/meta.json", "character/name.txt"}
MAX_SIZE = 128 * 1024 * 1024


def index(archive):
    entries = archive.infolist()
    names = set()
    if len(entries) > FRAME_LIMIT + 70 or sum(entry.file_size for entry in entries) > MAX_SIZE:
        raise ValueError("팩의 파일 수 또는 압축 해제 크기가 제한을 넘었어요.")
    for entry in entries:
        name = entry.filename
        if name not in CONTROL_FILES and not CHARACTER_FRAME.fullmatch(name) and not ASSET.fullmatch(name):
            raise ValueError(f"지원하지 않는 팩 경로예요. {name}")
        if name != entry.orig_filename or name in names or entry.flag_bits & 1 or entry.compress_type not in (ZIP_DEFLATED, ZIP_STORED):
            raise ValueError("중복 파일이 있거나 지원하지 않는 압축 방식이에요.")
        if entry.file_size > (IMAGE_LIMIT if name.endswith(".png") else JSON_LIMIT):
            raise ValueError(f"팩 파일이 너무 커요. {name}")
        names.add(name)
    return names


def read_info(archive, names):
    if "pack.json" not in names:
        raise ValueError("MiniBuddies 팩 정보가 없어요.")
    info = json.loads(archive.read("pack.json"))
    if (not isinstance(info, dict) or info.get("format") != "minibuddies-pack"
            or type(info.get("version")) is not int or info["version"] != 1):
        raise ValueError("지원하지 않는 MiniBuddies 팩 버전이에요.")
    validate_id(info.get("id"))
    if info.get("kind") not in ("plugin", "character"):
        raise ValueError("지원하지 않는 팩 종류예요.")
    for field, size in (("name", 80), ("author", 80), ("description", 2000)):
        validate_text(info.get(field, ""), size, field, required=field == "name")
    for field, maximum in (("actions", 24), ("interactions", 16), ("frames", FRAME_LIMIT)):
        count = info.get(field)
        if type(count) is not int or not 0 <= count <= maximum:
            raise ValueError(f"팩의 {field} 개수 정보가 올바르지 않아요.")
    if info.get("preview") not in (None, "preview.png") or info.get("preview") and "preview.png" not in names:
        raise ValueError("팩의 미리보기 정보를 확인해 주세요.")
    return info


def inspect_archive(path):
    """Read the ZIP index, metadata, and thumbnail only."""
    with ZipFile(path) as archive:
        names = index(archive)
        info = read_info(archive, names)
        cover = archive.read("preview.png") if info.get("preview") else None
    return info, cover


def load_archive(path):
    with ZipFile(path) as archive:
        names = index(archive)
        info = read_info(archive, names)
        project = Project(info["kind"], info["id"], info["name"], info.get("author", ""), info.get("description", ""))
        project.cover = archive.read("preview.png") if info.get("preview") else None
        if "plugin.json" in names:
            project.rules = json.loads(archive.read("plugin.json"))
            if not isinstance(project.rules, dict) or project.rules.get("version") != 1:
                raise ValueError("동작 파일 형식을 확인해 주세요.")
        project.assets = {name: archive.read(name) for name in sorted(names) if ASSET.fullmatch(name)}
        project.frames = {int(match.group(1)): archive.read(name) for name in names if (match := CHARACTER_FRAME.fullmatch(name))}
    if (project.kind == "plugin" and project.frames) or (project.kind == "character" and 0 not in project.frames):
        raise ValueError("팩의 종류와 캐릭터 프레임 구성이 맞지 않아요.")
    with TemporaryDirectory(prefix="mbpack-check-") as directory:
        actual = materialize(project, Path(directory) / project.id)
    if any(actual[field] != info[field] for field in ("actions", "interactions", "frames")):
        raise ValueError("팩의 미리보기 정보와 실제 내용이 일치하지 않아요.")
    return project


def export_archive(project, path):
    path = Path(path)
    with TemporaryDirectory(prefix="mbpack-export-", dir=path.parent) as directory:
        root = Path(directory) / project.id
        materialize(project, root)
        staged = Path(directory) / "export.mbpack"
        with ZipFile(staged, "w", compression=ZIP_DEFLATED) as archive:
            for item in sorted(root.rglob("*")):
                if item.is_file():
                    archive.write(item, item.relative_to(root).as_posix())
        with ZipFile(staged) as archive:
            index(archive)
        os.replace(staged, path)


def install_project(project, directory, used_ids):
    directory = Path(directory)
    key = validate_id(project.id)
    destination = directory / key
    if key in used_ids or destination.exists():
        raise ValueError("이 ID를 쓰는 팩이나 캐릭터가 이미 있어요. 팩 정보에서 ID를 바꿔 주세요.")
    directory.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".install-", dir=directory) as scratch:
        staged = Path(scratch) / key
        info = materialize(project, staged)
        if destination.exists():
            raise ValueError("같은 ID를 쓰는 팩이 먼저 설치됐어요.")
        os.rename(staged, destination)
    return destination, info
