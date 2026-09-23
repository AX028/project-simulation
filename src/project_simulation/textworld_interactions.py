"""Non-combat text-world interaction command handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .dialogue import converse
from .doors import Door
from .spatial import Bounds, SpatialEntity
from .textui import narrative_view, tactical_map

if TYPE_CHECKING:
    from .textworld import TextWorldSession


def look(session: TextWorldSession, args: tuple[str, ...]) -> tuple[str, bool]:
    session._expect_count(args, 0, "look")
    return (
        narrative_view(
            session.player.spatial,
            session.entities,
            illumination=session.environment.illumination,
            contrast=session.environment.contrast_multiplier,
            vision=session.player.vision,
        ),
        False,
    )


def map_view(
    session: TextWorldSession,
    args: tuple[str, ...],
) -> tuple[str, bool]:
    session._expect_count(args, 0, "map")
    return tactical_map(session.player.spatial, session.entities), False


def inspect(
    session: TextWorldSession,
    args: tuple[str, ...],
) -> tuple[str, bool]:
    from .spatial import observe

    session._expect_count(args, 1, "inspect <target>")
    target = session._resolve_entity(args[0])
    observation = observe(
        session.player.spatial,
        target,
        session.player.vision,
        illumination=session.environment.illumination,
        contrast=session.environment.contrast_multiplier,
        obstacles=session.entities,
    )
    if observation is None:
        return "You cannot currently perceive that target.", False
    return (
        f"{observation.description}; {observation.distance_m:.2f} m "
        f"{observation.bearing.lower()}, elevation "
        f"{observation.elevation_m:+.2f} m, clarity {observation.clarity:.2f}.",
        False,
    )


def take(
    session: TextWorldSession,
    args: tuple[str, ...],
) -> tuple[str, bool]:
    from .spatial import observe

    session._expect_count(args, 1, "take <item>")
    entity = session._resolve_entity(args[0])
    try:
        item = session.world_items[entity.entity_id]
    except KeyError as exc:
        raise ValueError(f"{entity.name} cannot be taken") from exc

    distance = session.player.spatial.position.distance_to(entity.position)
    if distance > 1.5:
        raise ValueError(
            f"{entity.name} is too far away to take ({distance:.2f} m)"
        )
    observation = observe(
        session.player.spatial,
        entity,
        session.player.vision,
        obstacles=session.entities,
    )
    if observation is None:
        raise ValueError(f"you cannot currently perceive {entity.name}")

    session.player.loadout.carried_loose.append(item)
    session.scenery = tuple(
        candidate
        for candidate in session.scenery
        if candidate.entity_id != entity.entity_id
    )
    del session.world_items[entity.entity_id]
    session._advance_clock(0.5)
    return (
        f"You take {item.name}. Carried mass: "
        f"{session.player.loadout.carried_mass_kg:.2f} kg.",
        False,
    )


def drop(
    session: TextWorldSession,
    args: tuple[str, ...],
) -> tuple[str, bool]:
    session._expect_count(args, 1, "drop <item>")
    lowered = args[0].lower()
    matches = [
        item
        for item in session.player.loadout.carried_loose
        if item.item_id.lower() == lowered or item.name.lower() == lowered
    ]
    if len(matches) != 1:
        if not matches:
            raise ValueError(f"you are not carrying: {args[0]}")
        raise ValueError(f"ambiguous carried item: {args[0]}")

    item = matches[0]
    session.player.loadout.carried_loose.remove(item)
    position = (
        session.player.spatial.position
        + session.player.spatial.facing.normalized().scale(0.6)
    )
    volume_m3 = max(0.000125, item.volume_l / 1000.0)
    side = volume_m3 ** (1.0 / 3.0)
    entity = SpatialEntity(
        item.item_id,
        item.name,
        position,
        bounds=Bounds(side / 2.0, side / 2.0, side),
        mass_kg=item.mass_kg,
        tags=frozenset({"item"}),
    )
    session.scenery = (*session.scenery, entity)
    session.world_items[item.item_id] = item
    session._advance_clock(0.5)
    return (
        f"You drop {item.name}. Carried mass: "
        f"{session.player.loadout.carried_mass_kg:.2f} kg.",
        False,
    )


def inventory(
    session: TextWorldSession,
    args: tuple[str, ...],
) -> tuple[str, bool]:
    session._expect_count(args, 0, "inventory")
    items = session.player.loadout.carried_loose
    if not items:
        return (
            f"You are carrying nothing. Load ratio "
            f"{session.player.loadout.load_ratio:.2f}.",
            False,
        )
    lines = ", ".join(
        f"{item.name} ({item.mass_kg:.2f} kg)"
        for item in sorted(items, key=lambda value: value.item_id)
    )
    return (
        f"Carrying: {lines}. Total "
        f"{session.player.loadout.carried_mass_kg:.2f} kg; "
        f"load ratio {session.player.loadout.load_ratio:.2f}.",
        False,
    )


def talk(
    session: TextWorldSession,
    args: tuple[str, ...],
) -> tuple[str, bool]:
    from .spatial import observe

    if not 1 <= len(args) <= 2:
        raise ValueError("usage: talk <target> [topic]")
    target_id = session._resolve_actor(args[0])
    if target_id == session.player_id:
        raise ValueError("cannot talk to yourself")
    target = session.actors[target_id]

    distance = session.player.spatial.position.distance_to(target.spatial.position)
    if distance > 3.0:
        raise ValueError(
            f"{target.spatial.name} is too far away to talk ({distance:.2f} m)"
        )
    observation = observe(
        session.player.spatial,
        target.spatial,
        session.player.vision,
        obstacles=session.entities,
    )
    if observation is None:
        raise ValueError(
            f"you cannot currently perceive {target.spatial.name}"
        )

    topic = args[1] if len(args) == 2 else None
    now = session.elapsed_seconds / 3600.0
    result = converse(
        speaker_id=target_id,
        speaker_name=target.spatial.name,
        speaker=target.mind,
        listener_id=session.player_id,
        listener=session.player.mind,
        now=now,
        topic=topic,
    )
    session._advance_clock(1.0)
    return result.text, False


def open_door(
    session: TextWorldSession,
    args: tuple[str, ...],
) -> tuple[str, bool]:
    session._expect_count(args, 1, "open <door>")
    door = resolve_door(session, args[0])
    require_door_reach(session, door)
    door.open_door()
    session._advance_clock(0.5)
    return f"You open {door.name}.", False


def close_door(
    session: TextWorldSession,
    args: tuple[str, ...],
) -> tuple[str, bool]:
    session._expect_count(args, 1, "close <door>")
    door = resolve_door(session, args[0])
    require_door_reach(session, door)
    door.close_door()
    session._advance_clock(0.5)
    return f"You close {door.name}.", False


def require_door_reach(session: TextWorldSession, door: Door) -> None:
    from .spatial import observe

    distance = session.player.spatial.position.distance_to(door.position)
    if distance > 1.5:
        raise ValueError(
            f"{door.name} is too far away to manipulate ({distance:.2f} m)"
        )
    observation = observe(
        session.player.spatial,
        door.spatial,
        session.player.vision,
        obstacles=session.entities,
    )
    if observation is None:
        raise ValueError(f"you cannot currently perceive {door.name}")


def resolve_door(session: TextWorldSession, query: str) -> Door:
    lowered = query.lower()
    matches = [
        door
        for door in session.doors.values()
        if door.door_id.lower() == lowered or door.name.lower() == lowered
    ]
    if len(matches) != 1:
        if not matches:
            raise ValueError(f"unknown door: {query}")
        raise ValueError(f"ambiguous door: {query}")
    return matches[0]
