"""Shared environmental state for vision, movement, physiology, sound, and projectiles."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import cos, pi, sin

from .spatial import Vec3
from .validation import finite_number


class WeatherKind(StrEnum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    STORM = "storm"
    SNOW = "snow"
    FOG = "fog"


@dataclass(slots=True)
class EnvironmentState:
    world_hour: float = 12.0
    weather: WeatherKind = WeatherKind.CLEAR
    base_temperature_c: float = 18.0
    wind_velocity: Vec3 = field(default_factory=lambda: Vec3(0.0, 0.0, 0.0))
    precipitation: float = 0.0
    cloud_cover: float = 0.0
    fog_density: float = 0.0
    ground_wetness: float = 0.0

    def __post_init__(self) -> None:
        finite_number(self.world_hour, "world hour")
        finite_number(self.base_temperature_c, "base temperature")
        for name in ("precipitation", "cloud_cover", "fog_density", "ground_wetness"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between zero and one")

    @property
    def hour_of_day(self) -> float:
        return self.world_hour % 24.0

    @property
    def effective_precipitation(self) -> float:
        baseline = {
            WeatherKind.CLEAR: 0.0,
            WeatherKind.CLOUDY: 0.0,
            WeatherKind.RAIN: 0.55,
            WeatherKind.STORM: 0.9,
            WeatherKind.SNOW: 0.45,
            WeatherKind.FOG: 0.0,
        }[self.weather]
        return max(self.precipitation, baseline)

    @property
    def effective_cloud_cover(self) -> float:
        baseline = {
            WeatherKind.CLEAR: 0.0,
            WeatherKind.CLOUDY: 0.65,
            WeatherKind.RAIN: 0.8,
            WeatherKind.STORM: 1.0,
            WeatherKind.SNOW: 0.75,
            WeatherKind.FOG: 0.45,
        }[self.weather]
        return max(self.cloud_cover, baseline)

    @property
    def effective_fog_density(self) -> float:
        baseline = 0.7 if self.weather is WeatherKind.FOG else 0.0
        return max(self.fog_density, baseline)

    @property
    def daylight_factor(self) -> float:
        hour = self.hour_of_day
        if not 6.0 < hour < 18.0:
            return 0.0
        return max(0.0, sin(pi * (hour - 6.0) / 12.0))

    @property
    def illumination(self) -> float:
        daylight = self.daylight_factor
        cloud_factor = 1.0 - 0.55 * self.effective_cloud_cover
        fog_factor = 1.0 - 0.45 * self.effective_fog_density
        value = 0.03 + 0.97 * daylight * cloud_factor * fog_factor
        return max(0.02, min(1.0, value))

    @property
    def contrast_multiplier(self) -> float:
        value = (
            1.0
            - 0.35 * self.effective_precipitation
            - 0.55 * self.effective_fog_density
        )
        return max(0.2, min(1.0, value))

    @property
    def ambient_temperature_c(self) -> float:
        diurnal = 5.0 * cos(2.0 * pi * (self.hour_of_day - 15.0) / 24.0)
        weather_delta = {
            WeatherKind.CLEAR: 1.0,
            WeatherKind.CLOUDY: 0.0,
            WeatherKind.RAIN: -2.0,
            WeatherKind.STORM: -3.0,
            WeatherKind.SNOW: -7.0,
            WeatherKind.FOG: -1.0,
        }[self.weather]
        return self.base_temperature_c + diurnal + weather_delta

    @property
    def movement_speed_multiplier(self) -> float:
        wet = max(self.ground_wetness, self.effective_precipitation * 0.65)
        snow_penalty = 0.18 if self.weather is WeatherKind.SNOW else 0.0
        storm_penalty = 0.08 if self.weather is WeatherKind.STORM else 0.0
        value = 1.0 - wet * 0.22 - snow_penalty - storm_penalty
        return max(0.45, min(1.0, value))

    @property
    def ambient_noise_db(self) -> float:
        wind_speed = self.wind_velocity.magnitude
        weather_noise = {
            WeatherKind.CLEAR: 0.0,
            WeatherKind.CLOUDY: 0.0,
            WeatherKind.RAIN: 8.0,
            WeatherKind.STORM: 16.0,
            WeatherKind.SNOW: 2.0,
            WeatherKind.FOG: 0.0,
        }[self.weather]
        return min(
            80.0,
            15.0
            + wind_speed * 0.9
            + self.effective_precipitation * 10.0
            + weather_noise,
        )

    def advance(self, hours: float) -> None:
        """Advance weather-driven ground wetness, then the environment clock.

        Drying and precipitation use daylight and wind at the start of this
        step. One long step therefore differs from several shorter steps when
        daylight changes during the interval. Callers that need agreement
        must subdivide the step themselves.
        """
        hours = finite_number(hours, "environment time step")
        if hours < 0:
            raise ValueError("environment time may not move backward")
        if hours == 0:
            return
        precipitation_gain = self.effective_precipitation * 0.18 * hours
        drying = (
            (0.015 + 0.004 * self.wind_velocity.magnitude)
            * (0.4 + 0.6 * self.daylight_factor)
            * hours
        )
        self.ground_wetness = max(
            0.0,
            min(1.0, self.ground_wetness + precipitation_gain - drying),
        )
        self.world_hour += hours

    def describe(self) -> str:
        wind = self.wind_velocity.magnitude
        return (
            f"{self.weather.value}; {self.ambient_temperature_c:.1f} C; "
            f"wind {wind:.1f} m/s; illumination {self.illumination:.2f}; "
            f"ground wetness {self.ground_wetness:.2f}"
        )
