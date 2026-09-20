"""Text rendering helpers that translate simulation state into readable spatial information."""

from __future__ import annotations

from collections.abc import Iterable

from .spatial import Observation, SpatialEntity, Vec3, observe


def render_observations(observations: Iterable[Observation]) -> str:
    rows = sorted(observations, key=lambda item: (item.bearing, item.distance_m))
    if not rows:
        return "Nothing notable is visible."
    lines = []
    for item in rows:
        elevation = ""
        if abs(item.elevation_m) >= 0.5:
            elevation = f", elevation {item.elevation_m:+.1f} m"
        lines.append(
            f"{item.bearing:<13} {item.description:<32} {item.distance_m:>6.1f} m{elevation}"
        )
    return "\n".join(lines)


def narrative_view(
    observer: SpatialEntity,
    entities: Iterable[SpatialEntity],
    *,
    illumination: float = 1.0,
) -> str:
    visible: list[Observation] = []
    all_entities = list(entities)
    for entity in all_entities:
        if entity.entity_id == observer.entity_id:
            continue
        result = observe(
            observer,
            entity,
            illumination=illumination,
            obstacles=all_entities,
        )
        if result is not None:
            visible.append(result)

    if not visible:
        return "You see no notable creatures or objects nearby."

    visible.sort(key=lambda item: item.distance_m)
    sentences = []
    for item in visible[:5]:
        if item.distance_m < 3:
            distance = "very close"
        elif item.distance_m < 10:
            distance = "nearby"
        elif item.distance_m < 30:
            distance = "some distance away"
        else:
            distance = "far away"
        sentences.append(
            f"{item.description.capitalize()} is {distance} "
            f"to your {item.bearing.lower()}."
        )
    return " ".join(sentences)


def tactical_map(
    observer: SpatialEntity,
    entities: Iterable[SpatialEntity],
    *,
    width: int = 25,
    height: int = 13,
    meters_per_cell: float = 2.0,
) -> str:
    if width < 5 or height < 5:
        raise ValueError("map is too small")
    grid = [[" " for _ in range(width)] for _ in range(height)]
    center_x, center_y = width // 2, height // 2
    grid[center_y][center_x] = "@"

    symbol_for = {
        "creature": "C",
        "hostile": "H",
        "cover": "#",
        "door": "D",
        "item": "i",
    }

    for entity in entities:
        if entity.entity_id == observer.entity_id:
            continue
        delta = entity.position - observer.position
        gx = center_x + round(delta.x / meters_per_cell)
        gy = center_y - round(delta.y / meters_per_cell)
        if not (0 <= gx < width and 0 <= gy < height):
            continue
        symbol = next((symbol_for[tag] for tag in symbol_for if tag in entity.tags), "?")
        grid[gy][gx] = symbol

    border = "+" + "-" * width + "+"
    body = ["|" + "".join(row) + "|" for row in grid]
    legend = "@ you   H hostile   C creature   # cover   D door   i item"
    return "\n".join([border, *body, border, legend])


def move_toward(entity: SpatialEntity, destination: Vec3, distance_m: float) -> None:
    delta = destination - entity.position
    if delta.magnitude == 0:
        return
    entity.position = entity.position + delta.normalized().scale(min(distance_m, delta.magnitude))
