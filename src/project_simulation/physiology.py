"""Lightweight physiological and inventory simulation focused on meaningful consequences."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import exp

from .validation import bounded_number, nonnegative_number, positive_number


class InjuryType(StrEnum):
    LACERATION = "laceration"
    PUNCTURE = "puncture"
    FRACTURE = "fracture"
    BLUNT = "blunt"
    BURN = "burn"


@dataclass(slots=True)
class Injury:
    location: str
    injury_type: InjuryType
    severity: float
    bleeding_ml_per_min: float = 0.0
    pain: float = 0.0
    mobility_penalty: float = 0.0
    manipulation_penalty: float = 0.0
    infection_risk: float = 0.0

    def __post_init__(self) -> None:
        bounded_number(self.severity, "injury severity", 0.0, 1.0)
        nonnegative_number(self.bleeding_ml_per_min, "injury bleeding")
        bounded_number(self.pain, "injury pain", 0.0, 100.0)
        bounded_number(self.mobility_penalty, "mobility penalty", 0.0, 1.0)
        bounded_number(
            self.manipulation_penalty,
            "manipulation penalty",
            0.0,
            1.0,
        )
        bounded_number(self.infection_risk, "infection risk", 0.0, 1.0)


@dataclass(slots=True)
class Physiology:
    mass_kg: float
    hydration_l: float = 3.0
    caloric_reserve_kcal: float = 2400.0
    sleep_debt_hours: float = 0.0
    fatigue: float = 0.0
    core_temperature_c: float = 37.0
    blood_volume_ml: float | None = None
    blood_lost_ml: float = 0.0
    injuries: list[Injury] = field(default_factory=list)

    def __post_init__(self) -> None:
        positive_number(self.mass_kg, "body mass")
        nonnegative_number(self.hydration_l, "hydration")
        nonnegative_number(self.caloric_reserve_kcal, "caloric reserve")
        nonnegative_number(self.sleep_debt_hours, "sleep debt")
        bounded_number(self.fatigue, "fatigue", 0.0, 100.0)
        positive_number(self.core_temperature_c, "core temperature")
        nonnegative_number(self.blood_lost_ml, "blood lost")
        if self.blood_volume_ml is None:
            self.blood_volume_ml = self.mass_kg * 70.0
        else:
            positive_number(self.blood_volume_ml, "blood volume")
        for injury in self.injuries:
            self._validate_injury(injury)

    @property
    def blood_loss_ratio(self) -> float:
        assert self.blood_volume_ml is not None
        return min(1.0, self.blood_lost_ml / self.blood_volume_ml)

    @property
    def conscious(self) -> bool:
        return self.blood_loss_ratio < 0.42 and 32.0 < self.core_temperature_c < 42.0

    @property
    def performance_modifier(self) -> float:
        injury_penalty = min(
            0.65,
            sum(
                injury.severity * 0.12 + injury.mobility_penalty * 0.08
                for injury in self.injuries
            ),
        )
        blood_penalty = min(0.7, self.blood_loss_ratio * 1.8)
        fatigue_penalty = min(0.55, self.fatigue / 180.0)
        sleep_penalty = min(0.35, self.sleep_debt_hours / 30.0)
        return max(0.05, 1.0 - injury_penalty - blood_penalty - fatigue_penalty - sleep_penalty)

    def tick(self, minutes: float, *, exertion: float = 0.0, ambient_c: float = 20.0) -> None:
        minutes = nonnegative_number(minutes, "elapsed minutes")
        exertion = nonnegative_number(exertion, "exertion")
        ambient_c = float(ambient_c)
        if not -150.0 <= ambient_c <= 150.0:
            raise ValueError("ambient temperature is outside supported range")
        self.blood_lost_ml += sum(i.bleeding_ml_per_min for i in self.injuries) * minutes
        self.caloric_reserve_kcal -= minutes / 60.0 * (70.0 + 260.0 * max(0.0, exertion))
        self.hydration_l -= minutes / 60.0 * (0.04 + 0.22 * max(0.0, exertion))
        self.fatigue = min(100.0, self.fatigue + minutes / 60.0 * (2.0 + 8.0 * exertion))
        thermal_pull = (ambient_c - self.core_temperature_c) * 0.002
        metabolic_heat = 0.012 * exertion
        self.core_temperature_c += minutes * (thermal_pull + metabolic_heat)
        if self.hydration_l < 1.0:
            self.fatigue = min(100.0, self.fatigue + minutes * 0.02)

    def rest(self, hours: float, quality: float = 1.0) -> None:
        hours = nonnegative_number(hours, "rest hours")
        quality = bounded_number(quality, "rest quality", 0.0, 1.0)
        self.fatigue *= exp(-0.22 * hours * quality)
        recovered = hours * quality
        self.sleep_debt_hours = max(0.0, self.sleep_debt_hours - recovered)
        for injury in self.injuries:
            injury.infection_risk = max(0.0, injury.infection_risk - 0.003 * hours * quality)

    @staticmethod
    def _validate_injury(injury: Injury) -> None:
        bounded_number(injury.severity, "injury severity", 0.0, 1.0)
        nonnegative_number(injury.bleeding_ml_per_min, "injury bleeding")
        bounded_number(injury.pain, "injury pain", 0.0, 100.0)
        bounded_number(injury.mobility_penalty, "mobility penalty", 0.0, 1.0)
        bounded_number(
            injury.manipulation_penalty,
            "manipulation penalty",
            0.0,
            1.0,
        )
        bounded_number(injury.infection_risk, "infection risk", 0.0, 1.0)

    def add_injury(self, injury: Injury) -> None:
        self._validate_injury(injury)
        self.injuries.append(injury)


@dataclass(slots=True, frozen=True)
class PhysicalItem:
    item_id: str
    name: str
    mass_kg: float
    volume_l: float
    length_m: float = 0.0
    accessibility_s: float = 1.0

    def __post_init__(self) -> None:
        nonnegative_number(self.mass_kg, "item mass")
        nonnegative_number(self.volume_l, "item volume")
        nonnegative_number(self.length_m, "item length")
        nonnegative_number(self.accessibility_s, "item accessibility")


@dataclass(slots=True)
class Container:
    name: str
    max_volume_l: float
    max_length_m: float
    retrieval_penalty_s: float
    items: list[PhysicalItem] = field(default_factory=list)

    def __post_init__(self) -> None:
        positive_number(self.max_volume_l, "container volume")
        positive_number(self.max_length_m, "container max length")
        nonnegative_number(self.retrieval_penalty_s, "retrieval penalty")
        if self.used_volume_l > self.max_volume_l:
            raise ValueError("container starts over capacity")
        if any(item.length_m > self.max_length_m for item in self.items):
            raise ValueError("container contains an overlength item")

    @property
    def used_volume_l(self) -> float:
        return sum(item.volume_l for item in self.items)

    def can_fit(self, item: PhysicalItem) -> bool:
        return (
            self.used_volume_l + item.volume_l <= self.max_volume_l
            and item.length_m <= self.max_length_m
        )

    def add(self, item: PhysicalItem) -> None:
        if not self.can_fit(item):
            raise ValueError(f"{item.name} does not fit in {self.name}")
        self.items.append(item)


@dataclass(slots=True)
class Loadout:
    body_mass_kg: float
    comfortable_load_ratio: float = 0.28
    containers: list[Container] = field(default_factory=list)
    carried_loose: list[PhysicalItem] = field(default_factory=list)

    def __post_init__(self) -> None:
        positive_number(self.body_mass_kg, "loadout body mass")
        positive_number(
            self.comfortable_load_ratio,
            "comfortable load ratio",
        )

    @property
    def carried_mass_kg(self) -> float:
        return sum(i.mass_kg for c in self.containers for i in c.items) + sum(
            i.mass_kg for i in self.carried_loose
        )

    @property
    def load_ratio(self) -> float:
        comfortable = max(1.0, self.body_mass_kg * self.comfortable_load_ratio)
        return self.carried_mass_kg / comfortable

    @property
    def fatigue_multiplier(self) -> float:
        ratio = self.load_ratio
        return float(1.0 + ratio**1.7)

    def retrieval_time(self, item_id: str) -> float:
        for item in self.carried_loose:
            if item.item_id == item_id:
                return item.accessibility_s
        for container in self.containers:
            for item in container.items:
                if item.item_id == item_id:
                    return item.accessibility_s + container.retrieval_penalty_s
        raise KeyError(item_id)
