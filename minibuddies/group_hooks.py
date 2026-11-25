"""Common lifecycle for optional behaviors that run during a gathered group."""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class GroupHooks:
    start: Callable
    advance: Callable
    should_break: Callable
    close: Callable
    restore: Callable


def ground_group_interrupted(app, group, members):
    return app.quiet() or app.scene or len(members) != len(group["mem"]) or any(
        pet.drag is not None or not pet.isVisible() or pet.surface != group["floor"]
        or pet.state not in ("gather", "group", "tower") or not pet.surface_alive()
        for pet in members
    )


def close_effect(group):
    effect = group.get("effect")
    if effect is not None:
        effect.close()


def restore_ground_pet(group, pet):
    if pet.surface and pet.drag is None:
        pet.stand_on(pet.surface)
        pet.vx = 0
