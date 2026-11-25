"""Discover installed characters and register newly authored content."""

import json
from pathlib import Path

from minibuddies.authoring.archive import install_project
from minibuddies.authoring.project import validate_id


def character_record(folder, name):
    skin = folder / "character"
    if not (skin / "0.png").is_file():
        raise ValueError("기본 자세 0번이 없어요.")
    with (skin / "meta.json").open(encoding="utf-8") as source:
        data = json.load(source)
    return {"dir": str(skin), "label": name, "meta": {int(key): value for key, value in data["frames"].items()},
            "rope": {}, "persona": []}


def load_characters(directory, occupied, report):
    if not directory.is_dir():
        return {}
    characters = {}
    for folder in sorted(directory.iterdir()):
        try:
            if not folder.is_dir() or folder.name.startswith(".") or folder.is_symlink():
                continue
            validate_id(folder.name)
            info_path = folder / "pack.json"
            if not info_path.is_file():
                continue
            info = json.loads(info_path.read_text(encoding="utf-8"))
            if info.get("format") != "minibuddies-pack" or info.get("kind") != "character" or info.get("id") != folder.name:
                continue
            if folder.name not in occupied:
                characters[folder.name] = character_record(folder, info["name"])
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            report(f"[제작 팩] {folder.name}: {error}\n")
    return characters


def install_into(app, project):
    occupied = set(app.chars) | {pack.id for pack in app.plugins.packs}
    folder, info = install_project(project, app.content_root, occupied)
    if (folder / "plugin.json").is_file():
        app.plugins.load_folder(folder, app.content_root)
    if info["kind"] == "character":
        key = info["id"]
        app.chars[key] = character_record(folder, info["name"])
        if not app.team:
            app.team = [app.mode]
        if not app.roster:
            app.roster = app.team[:]
        app.roster.append(key)
        app.one_each = True
    return folder
