"""Discover installed characters and register newly authored content."""

import json
from pathlib import Path

from minibuddies.authoring.archive import install_project
from minibuddies.authoring.project import skin_details, validate_id


def sprite_record(directory, name):
    if not (directory / "0.png").is_file():
        raise ValueError("기본 자세 0번이 없어요.")
    with (directory / "meta.json").open(encoding="utf-8") as source:
        data = json.load(source)
    return {"dir": str(directory), "label": name, "meta": {int(key): value for key, value in data["frames"].items()},
            "rope": {}, "persona": []}


def skin_records(folder, info):
    records = {}
    for key, skin in skin_details(info.get("skins", [])).items():
        record = sprite_record(folder / "skins" / key, skin["name"])
        record["skin_label"] = skin["name"]
        records[key] = record
    return records


def mount_skins(chars, outfits, base, skins):
    if not skins:
        return
    choices = outfits.get(base, {})
    original = choices.get("basic") or chars.get(base) or next(iter(choices.values()), None)
    if original is None:
        return
    choices = outfits.setdefault(base, choices)
    if base in chars and chars[base] is not None and not choices:
        choices["basic"] = chars[base]
    for key, record in skins.items():
        choices.setdefault(key, {**record, "label": original["label"]})


def load_content(directory, occupied, report):
    characters = {}
    skins = {}
    try:
        folders = sorted(directory.iterdir()) if directory.is_dir() else []
    except OSError as error:
        report(f"[제작 팩] {error}\n")
        return characters, skins
    for folder in folders:
        try:
            if not folder.is_dir() or folder.name.startswith(".") or folder.is_symlink():
                continue
            validate_id(folder.name)
            info_path = folder / "pack.json"
            if not info_path.is_file():
                continue
            info = json.loads(info_path.read_text(encoding="utf-8"))
            if info.get("format") != "minibuddies-pack" or info.get("version") != 1 or info.get("id") != folder.name:
                continue
            kind = info.get("kind")
            if kind == "character" and folder.name not in occupied:
                data = sprite_record(folder / "character", info["name"])
                wardrobe = skin_records(folder, info)
                characters[folder.name] = data
                target = folder.name
            elif kind == "skin":
                target = validate_id(info.get("target"))
                wardrobe = skin_records(folder, info)
            else:
                continue
            choices = skins.setdefault(target, {})
            for key, record in wardrobe.items():
                choices.setdefault(key, record)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            report(f"[제작 팩] {folder.name}: {error}\n")
    return characters, skins


def install_into(app, project):
    occupied = set(app.chars) | {pack.id for pack in app.plugins.packs}
    if project.kind == "skin":
        target = validate_id(project.target)
        if target not in app.chars:
            raise ValueError(f"대상 캐릭터 ‘{target}’를 먼저 설치해 주세요.")
        overlap = set(app.outfits.get(target, {})) & project.skins.keys()
        if overlap:
            raise ValueError(f"대상 캐릭터에 같은 스킨 ID가 있어요. {', '.join(sorted(overlap))}")
    folder, info = install_project(project, app.content_root, occupied)
    if (folder / "plugin.json").is_file():
        app.plugins.load_folder(folder, app.content_root)
    if info["kind"] == "character":
        key = info["id"]
        app.chars[key] = sprite_record(folder / "character", info["name"])
        if not app.team:
            app.team = [app.mode]
        if not app.roster:
            app.roster = app.team[:]
        app.roster.append(key)
        app.one_each = True
    if info.get("skins"):
        target = info["target"] if info["kind"] == "skin" else info["id"]
        mount_skins(app.chars, app.outfits, target, skin_records(folder, info))
        choices = app.outfits.get(target, {})
        if choices and target not in app.outfit:
            app.outfit[target] = next(iter(choices))
    return folder
