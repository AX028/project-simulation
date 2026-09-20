import pytest

from project_simulation import Claim, Mind, RumorNetwork, SocialLink


def _minds(*names: str) -> dict[str, Mind]:
    result = {name: Mind() for name in names}
    for receiver in result.values():
        for sender in names:
            receiver.relationship(sender).trust = 60
            receiver.relationship(sender).familiarity = 60
    return result


def test_rumor_waits_for_link_delay() -> None:
    minds = _minds("a", "b")
    network = RumorNetwork(minds)
    network.add_link(SocialLink("a", "b", delay_hours=5.0))
    network.seed(
        rumor_id="r1",
        origin_id="a",
        claim=Claim("bridge", "bridge", "collapsed", 1.0, "a"),
        now=0.0,
    )
    assert network.advance_to(4.99) == []
    deliveries = network.advance_to(5.0)
    assert len(deliveries) == 1
    assert "bridge" in minds["b"].beliefs


def test_rumor_confidence_decays_across_hops() -> None:
    minds = _minds("a", "b", "c")
    network = RumorNetwork(minds)
    network.add_link(SocialLink("a", "b", 1.0, reliability=0.9))
    network.add_link(SocialLink("b", "c", 1.0, reliability=0.9))
    network.seed(
        rumor_id="r1",
        origin_id="a",
        claim=Claim("king", "king", "is dead", 1.0, "a"),
        now=0.0,
        max_hops=3,
    )
    deliveries = network.advance_to(3.0)
    assert len(deliveries) == 2
    assert deliveries[1].transmission.receiver_confidence < (
        deliveries[0].transmission.receiver_confidence
    )


def test_max_hops_stops_propagation() -> None:
    minds = _minds("a", "b", "c")
    network = RumorNetwork(minds)
    network.add_link(SocialLink("a", "b", 1.0))
    network.add_link(SocialLink("b", "c", 1.0))
    network.seed(
        rumor_id="r1",
        origin_id="a",
        claim=Claim("x", "x", "true", 1.0, "a"),
        now=0.0,
        max_hops=1,
    )
    deliveries = network.advance_to(10.0)
    assert [item.transmission.receiver_id for item in deliveries] == ["b"]
    assert "x" not in minds["c"].beliefs


def test_cycle_terminates_without_reusing_directed_edges() -> None:
    minds = _minds("a", "b", "c")
    network = RumorNetwork(minds)
    network.add_link(SocialLink("a", "b", 1.0))
    network.add_link(SocialLink("b", "c", 1.0))
    network.add_link(SocialLink("c", "a", 1.0))
    network.seed(
        rumor_id="cycle",
        origin_id="a",
        claim=Claim("x", "x", "true", 1.0, "a"),
        now=0.0,
        max_hops=20,
    )
    deliveries = network.advance_to(100.0)
    assert len(deliveries) <= 3
    assert network.pending_events == 0


def test_bidirectional_link_supports_reverse_spread() -> None:
    minds = _minds("a", "b")
    network = RumorNetwork(minds)
    network.add_link(SocialLink("a", "b", 1.0), bidirectional=True)
    network.seed(
        rumor_id="r1",
        origin_id="b",
        claim=Claim("road", "road", "closed", 1.0, "b"),
        now=0.0,
    )
    deliveries = network.advance_to(1.0)
    assert len(deliveries) == 1
    assert deliveries[0].transmission.receiver_id == "a"


def test_invalid_links_are_rejected() -> None:
    network = RumorNetwork(_minds("a", "b"))
    with pytest.raises(KeyError):
        network.add_link(SocialLink("a", "missing", 1.0))
    with pytest.raises(ValueError, match="reliability"):
        SocialLink("a", "b", 1.0, reliability=1.1)


def test_network_time_cannot_move_backward() -> None:
    network = RumorNetwork(_minds("a"))
    network.advance_to(10.0)
    with pytest.raises(ValueError, match="backward"):
        network.advance_to(9.0)


def test_fifty_node_chain_propagates_deterministically() -> None:
    names = tuple(f"n{i}" for i in range(50))
    minds = _minds(*names)
    network = RumorNetwork(minds)
    for index in range(len(names) - 1):
        network.add_link(
            SocialLink(
                names[index],
                names[index + 1],
                delay_hours=0.25,
                reliability=0.99,
            )
        )
    network.seed(
        rumor_id="chain",
        origin_id=names[0],
        claim=Claim("event", "event", "happened", 1.0, names[0]),
        now=0.0,
        max_hops=49,
    )
    deliveries = network.advance_to(20.0)
    assert len(deliveries) == 49
    assert "event" in minds[names[-1]].beliefs
    confidences = [
        delivery.transmission.receiver_confidence
        for delivery in deliveries
    ]
    assert all(
        later <= earlier
        for earlier, later in zip(confidences, confidences[1:], strict=False)
    )
