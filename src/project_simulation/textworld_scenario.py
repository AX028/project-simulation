"""Authored deterministic demo scenario for the text-world frontend."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from .ambient import AmbientAgent, AmbientNPCSimulation
from .cognition import Belief, Mind
from .content import create_character, create_enemy
from .doors import Door, PassageAxis
from .environment import EnvironmentState
from .npc_controller import NPCController
from .physiology import Loadout, PhysicalItem, Physiology
from .projectiles import ProjectileSpec
from .ranged import RangedWeapon
from .schedules import RoutineBlock, RoutineSchedule
from .simulation import SimulationKernel, WorldState
from .spatial import Bounds, SpatialEntity, Vec3
from .spatial_combat import SpatialCombatant, WeaponPhysics
from .worldstate import WorldActor

if TYPE_CHECKING:
    from .textworld import TextWorldSession


def build_demo_session(seed: int = 42) -> TextWorldSession:
    from .textworld import TextWorldSession

    player_actor = create_character("ranger", "Aster", seed)
    wolf_actor = create_enemy("wolf", 1, seed + 1)

    player_world = WorldActor(
        SpatialEntity(
            player_actor.actor_id,
            player_actor.name,
            Vec3(0.0, 0.0, 0.0),
            facing=Vec3(0.0, 1.0, 0.0),
        ),
        Mind(),
        Physiology(70.0),
        Loadout(70.0),
    )
    wolf_world = WorldActor(
        SpatialEntity(
            wolf_actor.actor_id,
            wolf_actor.name,
            Vec3(0.0, 8.0, 0.0),
            facing=Vec3(0.0, -1.0, 0.0),
            tags=frozenset({"hostile", "creature"}),
        ),
        Mind(),
        Physiology(38.0),
        Loadout(38.0),
        movement_speed_mps=1.8,
    )

    villager_mind = Mind(
        beliefs={
            "bridge": Belief(
                "east bridge",
                "the east bridge is damaged and unsafe for carts",
                0.85,
                "direct_observation",
                0.0,
            ),
            "wolves": Belief(
                "wolves",
                "wolves have been coming closer to the village at dusk",
                0.75,
                "neighbors",
                0.0,
            ),
        }
    )
    villager_mind.relationship(player_actor.actor_id).trust = 20.0
    villager_mind.relationship(player_actor.actor_id).respect = 10.0
    villager_world = WorldActor(
        SpatialEntity(
            "mira",
            "Mira",
            Vec3(2.0, 2.0, 0.0),
            facing=Vec3(-1.0, -1.0, 0.0),
            tags=frozenset({"npc"}),
        ),
        villager_mind,
        Physiology(62.0),
        Loadout(62.0),
    )

    sword = WeaponPhysics(
        "hunting sword",
        mass_kg=1.2,
        reach_m=0.85,
        handling=1.0,
        strike_speed_mps=11.0,
    )
    fangs = WeaponPhysics(
        "fangs",
        mass_kg=0.4,
        reach_m=0.25,
        handling=1.15,
        strike_speed_mps=9.0,
    )
    rope = PhysicalItem(
        "rope",
        "Rope",
        mass_kg=1.8,
        volume_l=3.0,
        length_m=8.0,
        accessibility_s=1.0,
    )
    scenery = (
        SpatialEntity(
            "barrel",
            "Barrel",
            Vec3(3.0, 3.0, 0.0),
            bounds=Bounds(0.4, 0.4, 0.9),
            mass_kg=35.0,
            tags=frozenset({"cover", "occluder", "solid"}),
        ),
        SpatialEntity(
            "rope",
            "Rope",
            Vec3(0.5, 0.8, 0.0),
            bounds=Bounds(0.15, 0.15, 0.1),
            mass_kg=rope.mass_kg,
            tags=frozenset({"item"}),
        ),
    )

    mira_schedule = RoutineSchedule(
        (
            RoutineBlock(22.0, 6.0, "sleep", "home"),
            RoutineBlock(6.0, 8.0, "breakfast", "home"),
            RoutineBlock(8.0, 17.0, "work", "market"),
            RoutineBlock(17.0, 22.0, "home", "home"),
        )
    )
    mira_ambient = AmbientNPCSimulation(
        agents={
            "mira": AmbientAgent(
                actor=villager_world,
                controller=NPCController(mira_schedule),
                locations={
                    "home": Vec3(2.0, 2.0, 0.0),
                    "market": Vec3(5.0, 2.0, 0.0),
                },
            )
        }
    )

    hunting_bow = RangedWeapon(
        name="hunting bow",
        projectile_spec=ProjectileSpec(
            "arrow",
            mass_kg=0.03,
            radius_m=0.01,
            drag_coefficient=0.002,
            gravity_mps2=9.81,
            max_lifetime_s=5.0,
        ),
        muzzle_speed_mps=60.0,
        ammunition=12,
        penetration_factor=1.0,
    )

    gate = Door(
        "gate",
        "Wooden gate",
        Vec3(3.0, 0.0, 0.0),
        width_m=1.1,
        height_m=2.1,
        axis=PassageAxis.X,
    )

    kernel = SimulationKernel(WorldState())
    return TextWorldSession(
        player_id=player_actor.actor_id,
        actors={
            player_actor.actor_id: player_world,
            wolf_actor.actor_id: wolf_world,
            "mira": villager_world,
        },
        combatants={
            player_actor.actor_id: SpatialCombatant(
                player_actor,
                player_world,
                sword,
            ),
            wolf_actor.actor_id: SpatialCombatant(
                wolf_actor,
                wolf_world,
                fangs,
            ),
        },
        rng=random.Random(seed),
        scenery=scenery,
        world_items={"rope": rope},
        doors={"gate": gate},
        ranged_weapons={player_actor.actor_id: hunting_bow},
        environment=EnvironmentState(world_hour=0.0),
        kernel=kernel,
        ambient=mira_ambient,
        seed=seed,
    )
