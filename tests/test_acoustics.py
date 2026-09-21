import pytest

from project_simulation import (
    Bounds,
    HearingProfile,
    SoundEvent,
    SpatialEntity,
    Vec3,
    count_sound_occluders,
    distance_attenuation_db,
    hear_sound,
    propagate_sound,
)


def _listener(
    entity_id: str = "listener",
    position: Vec3 | None = None,
) -> SpatialEntity:
    return SpatialEntity(
        entity_id,
        entity_id.title(),
        Vec3(0.0, 0.0, 0.0) if position is None else position,
    )


def _sound(
    *,
    position: Vec3 | None = None,
    loudness: float = 60.0,
) -> SoundEvent:
    return SoundEvent(
        "sound",
        Vec3(0.0, 1.0, 1.5) if position is None else position,
        loudness,
        "test",
        "a test sound",
        0.0,
        "source",
    )


def test_distance_attenuation_matches_inverse_distance_db_rule() -> None:
    assert distance_attenuation_db(1.0) == pytest.approx(0.0)
    assert distance_attenuation_db(10.0) == pytest.approx(20.0)
    assert distance_attenuation_db(100.0) == pytest.approx(40.0)


def test_distance_attenuation_rejects_negative_distance() -> None:
    with pytest.raises(ValueError, match="distance"):
        distance_attenuation_db(-1.0)


def test_near_sound_is_heard() -> None:
    result = hear_sound(
        _sound(loudness=60.0),
        _listener(position=Vec3(0.0, 4.0, 0.0)),
    )
    assert result is not None
    assert result.perceived_db > 20.0


def test_far_quiet_sound_falls_below_threshold() -> None:
    result = hear_sound(
        _sound(position=Vec3(0.0, 1000.0, 1.5), loudness=35.0),
        _listener(),
    )
    assert result is None


def test_hearing_sensitivity_extends_detection() -> None:
    event = _sound(position=Vec3(0.0, 100.0, 1.5), loudness=45.0)
    listener = _listener()
    normal = hear_sound(
        event,
        listener,
        HearingProfile(threshold_db=20.0),
    )
    sensitive = hear_sound(
        event,
        listener,
        HearingProfile(threshold_db=20.0, sensitivity_db=20.0),
    )
    assert normal is None
    assert sensitive is not None


def test_solid_occluder_reduces_perceived_sound() -> None:
    event = _sound(position=Vec3(0.0, 10.0, 1.5), loudness=60.0)
    listener = _listener()
    wall = SpatialEntity(
        "wall",
        "Wall",
        Vec3(0.0, 5.0, 0.0),
        bounds=Bounds(2.0, 0.2, 3.0),
        tags=frozenset({"solid"}),
    )
    clear = hear_sound(event, listener)
    blocked = hear_sound(event, listener, obstacles=[wall])
    assert clear is not None
    assert blocked is not None
    assert blocked.perceived_db < clear.perceived_db
    assert blocked.occluders == 1


def test_multiple_occluders_stack_loss() -> None:
    event = _sound(position=Vec3(0.0, 12.0, 1.5), loudness=80.0)
    listener = _listener()
    walls = [
        SpatialEntity(
            f"wall-{index}",
            "Wall",
            Vec3(0.0, float(y), 0.0),
            bounds=Bounds(2.0, 0.2, 3.0),
            tags=frozenset({"occluder"}),
        )
        for index, y in enumerate((3, 6, 9))
    ]
    result = hear_sound(event, listener, obstacles=walls)
    assert result is not None
    assert result.occluders == 3


def test_count_occluders_ignores_named_entities() -> None:
    wall = SpatialEntity(
        "wall",
        "Wall",
        Vec3(0.0, 5.0, 0.0),
        bounds=Bounds(2.0, 0.2, 3.0),
        tags=frozenset({"solid"}),
    )
    assert count_sound_occluders(
        Vec3(0.0, 0.0, 1.0),
        Vec3(0.0, 10.0, 1.0),
        [wall],
    ) == 1
    assert count_sound_occluders(
        Vec3(0.0, 0.0, 1.0),
        Vec3(0.0, 10.0, 1.0),
        [wall],
        ignored_ids=frozenset({"wall"}),
    ) == 0


def test_propagation_returns_heard_listeners_in_distance_order() -> None:
    event = _sound(position=Vec3(0.0, 0.0, 1.5), loudness=70.0)
    listeners = [
        (_listener("far", Vec3(0.0, 10.0, 0.0)), HearingProfile()),
        (_listener("near", Vec3(0.0, 2.0, 0.0)), HearingProfile()),
    ]
    heard = propagate_sound(event, listeners)
    assert [item.listener_id for item in heard] == ["near", "far"]


def test_hearing_direction_points_toward_source() -> None:
    event = _sound(position=Vec3(10.0, 0.0, 1.5), loudness=70.0)
    result = hear_sound(event, _listener())
    assert result is not None
    assert result.direction.x > 0.9


def test_clarity_is_bounded() -> None:
    for loudness in (20.0, 40.0, 80.0, 140.0):
        result = hear_sound(
            _sound(loudness=loudness),
            _listener(),
            HearingProfile(threshold_db=0.0),
        )
        assert result is not None
        assert 0.0 <= result.clarity <= 1.0


def test_invalid_acoustic_parameters_are_rejected() -> None:
    with pytest.raises(ValueError, match="loudness"):
        _sound(loudness=-1.0)
    with pytest.raises(ValueError, match="occlusion"):
        HearingProfile(occlusion_loss_db=-1.0)


def test_thousand_identical_hearing_resolutions_are_deterministic() -> None:
    event = _sound(position=Vec3(3.0, 4.0, 1.5), loudness=65.0)
    listener = _listener()
    values = [hear_sound(event, listener) for _ in range(1000)]
    assert len(set(values)) == 1
