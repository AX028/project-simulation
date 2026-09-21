import pytest

from project_simulation import (
    ActorLODManager,
    Belief,
    Goal,
    Injury,
    InjuryType,
    Loadout,
    Memory,
    Mind,
    PhysicalItem,
    Physiology,
    Relationship,
    SimulationLOD,
    SpatialEntity,
    Vec3,
    WorldActor,
    abstract_actor,
    restore_actor,
)


def _actor() -> WorldActor:
    mind = Mind(
        memories=[
            Memory(
                subject=f"subject-{index}",
                proposition=f"memory-{index}",
                importance=0.1 + index * 0.08,
                emotional_intensity=0.2 + index * 0.05,
                confidence=0.5 + index * 0.04,
                accuracy=0.8,
                source="direct",
                created_at=float(index),
            )
            for index in range(10)
        ],
        beliefs={
            f"belief-{index}": Belief(
                subject=f"s-{index}",
                proposition=f"p-{index}",
                confidence=index / 10.0,
                source="direct",
                updated_at=float(index),
            )
            for index in range(10)
        },
        relationships={
            f"npc-{index}": Relationship(
                trust=float(index * 10),
                familiarity=float(index * 5),
            )
            for index in range(10)
        },
        goals={"survive": Goal("survive", 4.0)},
        knowledge={"wolves hunt at dusk", "bridge is unsafe"},
    )
    body = Physiology(70.0)
    body.fatigue = 37.0
    body.blood_lost_ml = 420.0
    body.add_injury(
        Injury(
            "left_leg",
            InjuryType.LACERATION,
            severity=0.4,
            bleeding_ml_per_min=2.0,
            pain=30.0,
            mobility_penalty=0.2,
        )
    )
    loadout = Loadout(
        70.0,
        carried_loose=[
            PhysicalItem("sword", "Sword", 1.5, 2.0, length_m=1.0),
            PhysicalItem("food", "Food", 3.0, 4.0),
        ],
    )
    return WorldActor(
        SpatialEntity(
            "actor",
            "Actor",
            Vec3(12.0, 8.0, 2.0),
            facing=Vec3(0.0, 1.0, 0.0),
            velocity=Vec3(1.0, 0.0, 0.0),
            mass_kg=72.0,
            tags=frozenset({"npc"}),
        ),
        mind,
        body,
        loadout,
        movement_speed_mps=1.6,
    )


def test_abstraction_preserves_physical_aggregates() -> None:
    actor = _actor()
    state = abstract_actor(
        actor,
        tier=SimulationLOD.REGION,
        now=20.0,
    )
    assert state.actor_id == actor.actor_id
    assert state.position == actor.spatial.position
    assert state.spatial_mass_kg == actor.spatial.mass_kg
    assert state.carried_mass_kg == actor.loadout.carried_mass_kg
    assert state.carried_volume_l == 6.0
    assert state.physiology.blood_lost_ml == actor.physiology.blood_lost_ml
    assert state.physiology.fatigue == actor.physiology.fatigue


def test_abstraction_prunes_memory_belief_and_relationship_counts() -> None:
    actor = _actor()
    state = abstract_actor(
        actor,
        tier=SimulationLOD.WORLD,
        now=20.0,
        memory_limit=3,
        belief_limit=4,
        relationship_limit=2,
    )
    assert state.original_memory_count == 10
    assert state.original_belief_count == 10
    assert state.original_relationship_count == 10
    assert state.compression_counts == (3, 4, 2)


def test_high_confidence_beliefs_survive_compression() -> None:
    actor = _actor()
    state = abstract_actor(
        actor,
        tier=SimulationLOD.WORLD,
        now=20.0,
        belief_limit=2,
    )
    keys = [key for key, _ in state.beliefs]
    assert keys == ["belief-9", "belief-8"]


def test_strong_relationships_survive_compression() -> None:
    actor = _actor()
    state = abstract_actor(
        actor,
        tier=SimulationLOD.WORLD,
        now=20.0,
        relationship_limit=2,
    )
    keys = [key for key, _ in state.relationships]
    assert keys == ["npc-9", "npc-8"]


def test_restore_preserves_key_physical_invariants() -> None:
    original = _actor()
    state = abstract_actor(
        original,
        tier=SimulationLOD.REGION,
        now=20.0,
    )
    restored = restore_actor(state)

    assert restored.actor_id == original.actor_id
    assert restored.spatial.position == original.spatial.position
    assert restored.spatial.velocity == original.spatial.velocity
    assert restored.spatial.mass_kg == original.spatial.mass_kg
    assert restored.physiology.blood_lost_ml == original.physiology.blood_lost_ml
    assert restored.physiology.injuries == original.physiology.injuries
    assert restored.loadout.carried_mass_kg == original.loadout.carried_mass_kg
    assert restored.mind.knowledge == original.mind.knowledge


def test_restore_does_not_share_mutable_physiology_with_snapshot() -> None:
    state = abstract_actor(
        _actor(),
        tier=SimulationLOD.REGION,
        now=20.0,
    )
    restored = restore_actor(state)
    restored.physiology.fatigue = 99.0
    assert state.physiology.fatigue == 37.0


def test_manager_demotes_and_promotes_actor() -> None:
    manager = ActorLODManager()
    actor = _actor()
    manager.register(actor, tier=SimulationLOD.LOCAL)

    abstracted = manager.transition(
        actor.actor_id,
        SimulationLOD.REGION,
        now=20.0,
    )
    assert not manager.is_detailed(actor.actor_id)
    assert manager.tier_of(actor.actor_id) is SimulationLOD.REGION
    assert abstracted.actor_id == actor.actor_id

    restored = manager.transition(
        actor.actor_id,
        SimulationLOD.LOCAL,
        now=30.0,
    )
    assert manager.is_detailed(actor.actor_id)
    assert manager.tier_of(actor.actor_id) is SimulationLOD.LOCAL
    assert restored.actor_id == actor.actor_id


def test_registering_duplicate_actor_is_rejected() -> None:
    manager = ActorLODManager()
    actor = _actor()
    manager.register(actor)
    with pytest.raises(ValueError, match="already registered"):
        manager.register(actor)


def test_fine_lod_cannot_be_abstracted_directly() -> None:
    with pytest.raises(ValueError, match="settlement-or-coarser"):
        abstract_actor(
            _actor(),
            tier=SimulationLOD.LOCAL,
            now=0.0,
        )


def test_repeated_lod_cycles_preserve_core_invariants() -> None:
    manager = ActorLODManager()
    original = _actor()
    manager.register(original)
    expected_mass = original.loadout.carried_mass_kg
    expected_position = original.spatial.position
    expected_blood_loss = original.physiology.blood_lost_ml

    for index in range(100):
        manager.transition(
            original.actor_id,
            SimulationLOD.REGION,
            now=float(index),
        )
        restored = manager.transition(
            original.actor_id,
            SimulationLOD.LOCAL,
            now=float(index) + 0.5,
        )
        assert restored.spatial.position == expected_position
        assert restored.loadout.carried_mass_kg == expected_mass
        assert restored.physiology.blood_lost_ml == expected_blood_loss
