"""Runtime, movement, status, and session-control command handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .navigation import move_actor_with_collisions
from .spatial import Vec3

if TYPE_CHECKING:
    from .textworld import TextWorldSession


def move(
    session: TextWorldSession,
    args: tuple[str, ...],
) -> tuple[str, bool]:
    if not 1 <= len(args) <= 2:
        raise ValueError(
            "usage: move <north|south|east|west> [meters]"
        )
    directions = {
        "north": Vec3(0.0, 1.0, 0.0),
        "south": Vec3(0.0, -1.0, 0.0),
        "east": Vec3(1.0, 0.0, 0.0),
        "west": Vec3(-1.0, 0.0, 0.0),
    }
    try:
        direction = directions[args[0].lower()]
    except KeyError as exc:
        raise ValueError(
            "direction must be north, south, east, or west"
        ) from exc

    distance = session._positive_float(
        args[1] if len(args) == 2 else "1",
        "distance",
    )
    session.player.spatial.facing = direction
    destination = session.player.spatial.position + direction.scale(
        distance
    )
    speed = (
        session.player.effective_speed()
        * session.environment.movement_speed_multiplier
    )
    seconds = distance / max(0.001, speed)
    movement = move_actor_with_collisions(
        session.player,
        destination,
        seconds,
        session.entities,
        doors=session.doors.values(),
        exertion=0.35,
        ambient_c=session.environment.ambient_temperature_c,
        speed_multiplier=session.environment.movement_speed_multiplier,
    )
    session._advance_clock(
        seconds,
        already_advanced={session.player_id},
    )
    blocked = (
        ""
        if movement.hit is None
        else f" Movement blocked by {movement.hit.entity_id}."
    )
    return (
        f"You move {args[0].lower()} {movement.moved_distance_m:.2f} m. "
        f"Position: {session._position_text(session.player.spatial.position)}."
        f"{blocked}",
        False,
    )


def wait(
    session: TextWorldSession,
    args: tuple[str, ...],
) -> tuple[str, bool]:
    if len(args) > 1:
        raise ValueError("usage: wait [seconds]")
    seconds = session._positive_float(
        args[0] if args else "1",
        "seconds",
    )
    session._advance_clock(seconds)
    return f"You wait {seconds:.2f} seconds.", False


def status(
    session: TextWorldSession,
    args: tuple[str, ...],
) -> tuple[str, bool]:
    session._expect_count(args, 0, "status")
    body = session.player.physiology
    return (
        f"Position {session._position_text(session.player.spatial.position)}; "
        f"speed {session.player.effective_speed():.2f} m/s; "
        f"fatigue {body.fatigue:.2f}; blood lost "
        f"{body.blood_lost_ml:.1f} ml; "
        f"injuries {len(body.injuries)}; environment "
        f"{session.environment.describe()}.",
        False,
    )


def help_text(
    session: TextWorldSession,
    args: tuple[str, ...],
) -> tuple[str, bool]:
    session._expect_count(args, 0, "help")
    return (
        "Commands: look, map, move <direction> [m], "
        "advance <target> [s], attack <target> [body_part], "
        "inspect <target>, wait [s], status, "
        "take <item> [from <container>], put <item> in <container>, "
        "drop <item>, inventory, talk <target> [topic], "
        "open <object>, close <object>, shoot <target> [body_part], "
        "help, quit.",
        False,
    )


def quit_session(
    session: TextWorldSession,
    args: tuple[str, ...],
) -> tuple[str, bool]:
    session._expect_count(args, 0, "quit")
    return "Session ended.", True
