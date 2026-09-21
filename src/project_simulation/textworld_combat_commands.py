"""Combat and acoustic command handlers for the text-world frontend."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .acoustics import HeardSound, HearingProfile, SoundEvent, propagate_sound
from .cognition import Memory
from .models import BodyPart
from .navigation import move_actor_with_collisions
from .projectiles import ProjectileSimulator
from .ranged import aim_point_for_body_part, resolve_projectile_impact
from .skills import PracticeEvent
from .spatial import Vec3
from .spatial_combat import SpatialCombatResolver

if TYPE_CHECKING:
    from .textworld import TextWorldSession


def advance(
    session: TextWorldSession,
    args: tuple[str, ...],
) -> tuple[str, bool]:
    if not 1 <= len(args) <= 2:
        raise ValueError("usage: advance <target> [seconds]")
    target_id = session._resolve_actor(args[0])
    if target_id == session.player_id:
        raise ValueError("cannot advance toward yourself")
    seconds = session._positive_float(
        args[1] if len(args) == 2 else "1",
        "seconds",
    )
    target = session.actors[target_id]
    direction = target.spatial.position - session.player.spatial.position
    if direction.magnitude > 0:
        session.player.spatial.facing = direction.normalized()
    before = session.player.spatial.position.distance_to(
        target.spatial.position
    )
    movement = move_actor_with_collisions(
        session.player,
        target.spatial.position,
        seconds,
        session.entities,
        doors=session.doors.values(),
        exertion=0.45,
        ambient_c=session.environment.ambient_temperature_c,
        speed_multiplier=session.environment.movement_speed_multiplier,
    )
    session._advance_clock(
        seconds,
        already_advanced={session.player_id},
    )
    after = session.player.spatial.position.distance_to(
        target.spatial.position
    )
    blocked = (
        ""
        if movement.hit is None
        else f" Blocked by {movement.hit.entity_id}."
    )
    return (
        f"You advance {movement.moved_distance_m:.2f} m "
        f"toward {target.spatial.name}; "
        f"distance {before:.2f} -> {after:.2f} m.{blocked}",
        False,
    )


def attack(
    session: TextWorldSession,
    args: tuple[str, ...],
) -> tuple[str, bool]:
    if not 1 <= len(args) <= 2:
        raise ValueError("usage: attack <target> [body_part]")
    target_id = session._resolve_actor(args[0])
    if target_id == session.player_id:
        raise ValueError("cannot attack yourself")
    if (
        session.player_id not in session.combatants
        or target_id not in session.combatants
    ):
        raise ValueError("target is not a combatant")

    part: BodyPart | None = None
    if len(args) == 2:
        try:
            part = BodyPart(args[1].lower())
        except ValueError as exc:
            valid = ", ".join(item.value for item in BodyPart)
            raise ValueError(
                f"body_part must be one of: {valid}"
            ) from exc

    attacker = session.combatants[session.player_id]
    target = session.combatants[target_id]
    result = SpatialCombatResolver(session.rng).resolve_attack(
        attacker,
        target,
        selected_part=part,
    )
    if result.in_reach:
        difficulty = min(
            100.0,
            25.0
            + target.actor.stats.agility * 1.5
            + target.actor.stats.evasion * 50.0,
        )
        session.player.skills.practice(
            attacker.weapon.skill_id,
            PracticeEvent(
                difficulty=difficulty,
                duration_hours=1.0 / 3600.0,
                quality=0.82 if result.hit else 0.58,
                context=f"combat:{target.actor.archetype}",
            ),
        )
    session._advance_clock(1.0)
    return result.text, False


def shoot(
    session: TextWorldSession,
    args: tuple[str, ...],
) -> tuple[str, bool]:
    if not 1 <= len(args) <= 2:
        raise ValueError("usage: shoot <target> [body_part]")
    target_id = session._resolve_actor(args[0])
    if target_id == session.player_id:
        raise ValueError("cannot shoot yourself")
    if session.player_id not in session.ranged_weapons:
        raise ValueError("you do not have a ranged weapon")
    if target_id not in session.combatants:
        raise ValueError("target does not have a detailed combat profile")

    part = BodyPart.TORSO
    if len(args) == 2:
        try:
            part = BodyPart(args[1].lower())
        except ValueError as exc:
            valid = ", ".join(item.value for item in BodyPart)
            raise ValueError(
                f"body_part must be one of: {valid}"
            ) from exc

    target = session.actors[target_id]
    origin = session.player.spatial.position + Vec3(
        0.0,
        0.0,
        session.player.spatial.bounds.height * 0.85,
    )
    aim_point = aim_point_for_body_part(target.spatial, part)
    direction = aim_point - origin
    if direction.magnitude <= 0:
        raise ValueError("target is too close for a valid shot")
    session.player.spatial.facing = Vec3(
        direction.x,
        direction.y,
        0.0,
    ).normalized()

    weapon = session.ranged_weapons[session.player_id]
    projectile = weapon.fire(
        owner_id=session.player_id,
        origin=origin,
        direction=direction,
    )
    emit_sound(
        session,
        category="weapon",
        description=f"{weapon.name} firing",
        position=origin,
        loudness_db_at_1m=65.0,
        source_id=session.player_id,
    )
    simulator = ProjectileSimulator()
    simulator.launch(projectile)

    projectile_targets = [
        actor.spatial
        for actor_id, actor in session.actors.items()
        if actor_id != session.player_id
    ]
    projectile_targets.extend(session.scenery)
    projectile_targets.extend(
        door.spatial
        for door in session.doors.values()
        if not door.is_open and not door.destroyed
    )
    steps = simulator.simulate_until_inactive(
        projectile.projectile_id,
        projectile_targets,
        dt_s=0.01,
        wind_velocity=session.environment.wind_velocity,
    )
    hit = next(
        (step.hit for step in steps if step.hit is not None),
        None,
    )
    flight_time = sum(step.elapsed_s for step in steps)
    session._advance_clock(max(1.0, flight_time))

    practice_quality = 0.45
    if hit is not None and hit.target_id == target_id:
        practice_quality = 0.85
    elif hit is not None:
        practice_quality = 0.60
    shot_distance = origin.distance_to(aim_point)
    session.player.skills.practice(
        weapon.skill_id,
        PracticeEvent(
            difficulty=min(100.0, 25.0 + shot_distance * 4.0),
            duration_hours=max(1.0, flight_time) / 3600.0,
            quality=practice_quality,
            context=f"ranged:{target.actor.archetype}",
        ),
    )

    if hit is None:
        return (
            f"You fire {weapon.name}, but the projectile hits nothing. "
            f"Ammunition remaining: {weapon.ammunition}.",
            False,
        )

    emit_sound(
        session,
        category="impact",
        description="projectile impact",
        position=hit.position,
        loudness_db_at_1m=58.0,
        source_id=session.player_id,
    )

    if hit.target_id in session.combatants:
        combatant = session.combatants[hit.target_id]
        impact_part = (
            part if hit.target_id == target_id else BodyPart.TORSO
        )
        impact = resolve_projectile_impact(
            hit,
            combatant.actor,
            combatant.world_actor.physiology,
            selected_part=impact_part,
            penetration_factor=weapon.penetration_factor,
        )
        prefix = (
            ""
            if hit.target_id == target_id
            else f"The shot is intercepted by {combatant.actor.name}. "
        )
        return (
            f"{prefix}{impact.text} Ammunition remaining: "
            f"{weapon.ammunition}.",
            False,
        )

    if hit.target_id in session.doors:
        door = session.doors[hit.target_id]
        door_damage = max(0.0, hit.kinetic_energy_j ** 0.5)
        dealt = door.apply_damage(door_damage)
        return (
            f"The projectile strikes {door.name} for {dealt:.1f} structural "
            f"damage. Ammunition remaining: {weapon.ammunition}.",
            False,
        )

    struck = session._resolve_entity(hit.target_id)
    return (
        f"The projectile strikes {struck.name} at "
        f"{hit.kinetic_energy_j:.1f} J. Ammunition remaining: "
        f"{weapon.ammunition}.",
        False,
    )


def emit_sound(
    session: TextWorldSession,
    *,
    category: str,
    description: str,
    position: Vec3,
    loudness_db_at_1m: float,
    source_id: str | None = None,
) -> tuple[HeardSound, ...]:
    created_hour = (
        session.kernel.world.time_hours
        if session.kernel is not None
        else session.elapsed_seconds / 3600.0
    )
    event = SoundEvent(
        sound_id=f"sound-{len(session.sound_events)}",
        position=position,
        loudness_db_at_1m=loudness_db_at_1m,
        category=category,
        description=description,
        created_hour=created_hour,
        source_id=source_id,
    )
    session.sound_events.append(event)

    listeners = [
        (
            actor.spatial,
            session.hearing_profiles.get(
                actor_id,
                HearingProfile(),
            ),
        )
        for actor_id, actor in session.actors.items()
        if actor_id != source_id
    ]
    heard = propagate_sound(
        event,
        listeners,
        obstacles=session.entities,
        ambient_noise_db=session.environment.ambient_noise_db,
    )
    for perception in heard:
        actor = session.actors.get(perception.listener_id)
        if actor is None:
            continue
        confidence = max(
            0.05,
            min(1.0, 0.2 + 0.8 * perception.clarity),
        )
        actor.mind.remember(
            Memory(
                subject=category,
                proposition=f"heard {description}",
                importance=0.45,
                emotional_intensity=0.25,
                confidence=confidence,
                accuracy=perception.clarity,
                source="hearing",
                created_at=created_hour,
                tags=frozenset({"sound", category}),
            )
        )
    return heard
