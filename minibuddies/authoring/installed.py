"""Discover, install, and remove authored packs."""

import json
from pathlib import Path

from PyQt5.QtCore import QFile

from minibuddies.authoring.archive import install_project
from minibuddies.authoring.project import JSON_LIMIT, skin_details, validate_id, validate_text
from minibuddies.plugins.packs import SETTINGS_KEY, pack_file


def installed_pack(directory, key):
    key = validate_id(key)
    root = directory.resolve(strict=True)
    path = root / key
    folder = path.resolve(strict=True)
    if path.is_symlink() or folder != path or not folder.is_dir():
        raise ValueError("설치한 팩 폴더를 확인해 주세요.")
    manifest = pack_file(folder, "pack.json")
    if manifest.stat().st_size > JSON_LIMIT:
        raise ValueError("팩 정보 파일이 너무 커요.")
    info = json.loads(manifest.read_text(encoding="utf-8"))
    if (not isinstance(info, dict) or info.get("format") != "minibuddies-pack"
            or type(info.get("version")) is not int or info["version"] != 1 or info.get("id") != key
            or info.get("kind") not in ("character", "plugin", "skin")):
        raise ValueError("설치한 MiniBuddies 팩 정보를 확인해 주세요.")
    validate_text(info.get("name"), 80, "이름", required=True)
    return folder, info


def installed_packs(directory):
    if not directory.exists():
        return []
    packs = []
    for path in directory.iterdir():
        try:
            _, info = installed_pack(directory, path.name)
        except (OSError, ValueError, RuntimeError):
            continue
        packs.append(info)
    return sorted(packs, key=lambda info: (info["name"].casefold(), info["id"]))


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
            if not folder.is_dir() or folder.name.startswith(".") or not (folder / "pack.json").is_file():
                continue
            folder, info = installed_pack(directory, folder.name)
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
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as error:
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
        app.plugins.load_folder(folder, app.content_root, character_pack=info["kind"] == "character")
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


def belongs_to_pack(record, folder):
    return bool(record and Path(record["dir"]).resolve().is_relative_to(folder))


def discard_bindings(cfg, pack_id, removed_character):
    bindings = cfg.get(SETTINGS_KEY)
    if not isinstance(bindings, dict):
        return
    for char, ids in list(bindings.items()):
        if char == removed_character:
            del bindings[char]
        elif pack_id and isinstance(ids, list) and pack_id in ids:
            remaining = [item for item in ids if item != pack_id]
            if remaining:
                bindings[char] = remaining
            else:
                del bindings[char]


def remove_character(app, key):
    del app.chars[key]
    app.outfits.pop(key, None)
    app.outfit.pop(key, None)
    app.pending.discard(key)
    for roster in (app.roster, getattr(app, "new_friends", [])):
        roster[:] = [char for char in roster if char != key]
    for name in ("active", "seen_roster"):
        if isinstance(app.cfg.get(name), list):
            app.cfg[name] = [char for char in app.cfg[name] if char != key]
    app.cfg.get("outfit", {}).pop(key, None)
    if app.mode == key:
        app.mode = next(iter(app.roster), next(iter(app.chars)))
    if key in app.team:
        team = [char for char in app.team if char != key]
        if not team:
            if app.mode not in app.roster:
                app.roster.append(app.mode)
            team = [app.mode]
        app.set_team(team)


def remove_skins(app, skins):
    for char, keys in skins.items():
        choices = app.outfits[char]
        for key in keys:
            del choices[key]
        current = app.outfit.get(char)
        if current not in keys:
            continue
        grounded = {pet: pet.fbottom(pet.frame()) for pet in app.buddies if pet.char == char
                    and pet.surface and pet.drag is None and pet.state not in app.BUSY}
        fallback = "basic" if "basic" in choices else next(iter(choices))
        app.apply_outfit(char, fallback)
        app.cfg.setdefault("outfit", {})[char] = fallback
        for pet in (pet for pet in app.buddies if pet.char == char):
            if pet in grounded:
                pet.fy += pet.S * (grounded[pet] - pet.fbottom(pet.frame()))
            pet.update()


def uninstall_from(app, key):
    folder, info = installed_pack(app.content_root, key)
    base = app.outfits.get(key, {}).get("basic") or app.chars.get(key)
    character = key if info["kind"] == "character" and belongs_to_pack(base, folder) else None
    if character and len(app.chars) == 1:
        raise ValueError("다른 캐릭터를 하나 이상 설치한 뒤 이 팩을 삭제해 주세요.")
    skins = {char: [skin for skin, art in choices.items() if belongs_to_pack(art, folder)]
             for char, choices in app.outfits.items() if char != character}
    skins = {char: keys for char, keys in skins.items() if keys}
    changed_outfits = {char for char, keys in skins.items() if app.outfit.get(char) in keys}
    affected = changed_outfits | ({character} if character else set())
    plugin = key if app.plugins.pack_folders.get(key) == folder else None

    trash = QFile(str(folder))
    if not trash.moveToTrash():
        raise OSError(f"팩을 휴지통으로 옮기지 못했어요. {trash.errorString()}")

    if app.scene and any(pet.char in affected for pet in app.scene_mem):
        app.scene_end()
    if app.group and ((plugin and app.group.get("pack_id") == plugin)
                      or any(pet.char in affected for pet in app.group["mem"])):
        app.group_break()
    for pet in list(app.buddies):
        if pet.char == character:
            app.remove(pet)
        elif pet.plugin_action and (pet.plugin_action.pack_id == plugin or pet.char in changed_outfits):
            pet.set("idle", 30)
            if pet.surface and pet.drag is None:
                pet.stand_on(pet.surface)
    removed_frames = app.plugins.unload_folder(folder)
    for cache in (app._pix, app._spix):
        for entry in [entry for entry in cache if entry[0] == character or entry[1] in removed_frames]:
            del cache[entry]
    discard_bindings(app.cfg, plugin, character)
    remove_skins(app, skins)
    if character:
        remove_character(app, character)
    return app.save_cfg()
