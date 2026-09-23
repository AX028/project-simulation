import pytest

from project_simulation import (
    DiplomacyEngine,
    FactionState,
    TreatyStatus,
    WorldState,
)


def _world() -> WorldState:
    return WorldState(
        factions={
            "a": FactionState(
                "a",
                "Ash League",
                members=100,
                wealth=5000.0,
                military_power=20.0,
                territory=5.0,
            ),
            "b": FactionState(
                "b",
                "Blue Compact",
                members=120,
                wealth=6000.0,
                military_power=18.0,
                territory=6.0,
            ),
            "c": FactionState(
                "c",
                "Copper Union",
                members=80,
                wealth=3500.0,
                military_power=12.0,
                territory=4.0,
            ),
        }
    )


def test_signing_treaty_improves_relations_and_records_history() -> None:
    world = _world()
    diplomacy = DiplomacyEngine(world)
    treaty = diplomacy.sign_treaty(
        "ab-peace",
        "a",
        "b",
        terms=frozenset({"non_aggression", "trade"}),
        now=10.0,
    )
    assert treaty.status is TreatyStatus.ACTIVE
    assert world.factions["a"].relations["b"] > 0.0
    assert world.factions["b"].relations["a"] > 0.0
    assert world.history


def test_breaking_treaty_creates_asymmetric_betrayal_memory() -> None:
    world = _world()
    diplomacy = DiplomacyEngine(world)
    diplomacy.sign_treaty("ab", "a", "b", now=0.0)
    before_a = world.factions["a"].relations["b"]
    before_b = world.factions["b"].relations["a"]

    treaty = diplomacy.break_treaty(
        "ab",
        breaker_id="a",
        now=12.0,
        severity=0.8,
    )

    assert treaty.status is TreatyStatus.BROKEN
    assert treaty.broken_by == "a"
    assert world.factions["a"].relations["b"] < before_a
    assert world.factions["b"].relations["a"] < before_b
    assert (
        world.factions["b"].institutional_memory["betrayal:a"]
        > world.factions["a"].institutional_memory["broke_treaty:b"]
    )


def test_active_treaty_increases_cooperation() -> None:
    world = _world()
    diplomacy = DiplomacyEngine(world)
    baseline = diplomacy.cooperation_modifier("a", "b")
    diplomacy.sign_treaty("ab", "a", "b", now=0.0)
    assert diplomacy.cooperation_modifier("a", "b") > baseline


def test_betrayal_reduces_victim_cooperation_more_than_breaker() -> None:
    world = _world()
    diplomacy = DiplomacyEngine(world)
    diplomacy.sign_treaty("ab", "a", "b", now=0.0)
    diplomacy.break_treaty("ab", breaker_id="a", now=1.0, severity=1.0)
    assert diplomacy.cooperation_modifier("b", "a") < (
        diplomacy.cooperation_modifier("a", "b")
    )


def test_treaty_expires_at_end_time() -> None:
    world = _world()
    diplomacy = DiplomacyEngine(world)
    treaty = diplomacy.sign_treaty(
        "short",
        "a",
        "b",
        now=5.0,
        duration_hours=10.0,
    )
    assert diplomacy.expire_treaties(14.9) == []
    expired = diplomacy.expire_treaties(15.0)
    assert expired == [treaty]
    assert treaty.status is TreatyStatus.EXPIRED


def test_expired_or_broken_treaty_cannot_be_broken_again() -> None:
    world = _world()
    diplomacy = DiplomacyEngine(world)
    diplomacy.sign_treaty("ab", "a", "b", now=0.0)
    diplomacy.break_treaty("ab", breaker_id="a", now=1.0)
    with pytest.raises(ValueError, match="active"):
        diplomacy.break_treaty("ab", breaker_id="b", now=2.0)


def test_invalid_treaty_parameters_are_rejected() -> None:
    diplomacy = DiplomacyEngine(_world())
    with pytest.raises(ValueError, match="itself"):
        diplomacy.sign_treaty("self", "a", "a", now=0.0)
    with pytest.raises(ValueError, match="positive"):
        diplomacy.sign_treaty(
            "bad-duration",
            "a",
            "b",
            now=0.0,
            duration_hours=0.0,
        )
    with pytest.raises(KeyError, match="unknown faction"):
        diplomacy.sign_treaty("missing", "a", "missing", now=0.0)


def test_duplicate_treaty_ids_are_rejected() -> None:
    diplomacy = DiplomacyEngine(_world())
    diplomacy.sign_treaty("ab", "a", "b", now=0.0)
    with pytest.raises(ValueError, match="duplicate"):
        diplomacy.sign_treaty("ab", "a", "c", now=1.0)


def test_cooperation_modifier_is_always_bounded() -> None:
    world = _world()
    diplomacy = DiplomacyEngine(world)
    for index in range(50):
        treaty_id = f"t{index}"
        diplomacy.sign_treaty(treaty_id, "a", "b", now=float(index))
        diplomacy.break_treaty(
            treaty_id,
            breaker_id="a",
            now=float(index) + 0.5,
            severity=1.0,
        )
        assert -1.0 <= diplomacy.cooperation_modifier("a", "b") <= 1.0
        assert -1.0 <= diplomacy.cooperation_modifier("b", "a") <= 1.0


def test_hundred_treaty_cycles_never_exceed_memory_bounds() -> None:
    world = _world()
    diplomacy = DiplomacyEngine(world)
    for index in range(100):
        treaty_id = f"cycle-{index}"
        diplomacy.sign_treaty(treaty_id, "a", "b", now=float(index))
        diplomacy.break_treaty(
            treaty_id,
            breaker_id="a",
            now=float(index) + 0.25,
            severity=0.8,
        )
    for faction in world.factions.values():
        assert all(
            0.0 <= strength <= 1.0
            for strength in faction.institutional_memory.values()
        )
