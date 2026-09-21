"""Shared finite/range validation helpers for simulation domain models."""

from __future__ import annotations

from math import isfinite


def finite_number(value: int | float, name: str) -> float:
    number = float(value)
    if not isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def nonnegative_number(value: int | float, name: str) -> float:
    number = finite_number(value, name)
    if number < 0:
        raise ValueError(f"{name} may not be negative")
    return number


def positive_number(value: int | float, name: str) -> float:
    number = finite_number(value, name)
    if number <= 0:
        raise ValueError(f"{name} must be positive")
    return number


def bounded_number(
    value: int | float,
    name: str,
    minimum: float,
    maximum: float,
) -> float:
    number = finite_number(value, name)
    if not minimum <= number <= maximum:
        raise ValueError(
            f"{name} must be between {minimum} and {maximum}"
        )
    return number
