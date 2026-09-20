"""Run repository quality gates repeatedly and score each gate.

A gate receives 10/10 only when every requested repetition succeeds. Any failed
repetition makes that gate 0/10 and the script exits non-zero.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Gate:
    name: str
    command: tuple[str, ...]


GATES = (
    Gate("pytest", (sys.executable, "-m", "pytest")),
    Gate("ruff", (sys.executable, "-m", "ruff", "check", ".")),
    Gate("mypy", (sys.executable, "-m", "mypy", "src/project_simulation")),
)


def run_gate(gate: Gate, repetitions: int) -> tuple[int, list[int]]:
    codes: list[int] = []
    print(f"\n=== {gate.name} ===", flush=True)
    for repetition in range(1, repetitions + 1):
        print(f"Pass {repetition}/{repetitions}: {' '.join(gate.command)}", flush=True)
        result = subprocess.run(gate.command, check=False)
        codes.append(result.returncode)
    rating = 10 if all(code == 0 for code in codes) else 0
    print(f"{gate.name} rating: {rating}/10; exit codes={codes}", flush=True)
    return rating, codes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be positive")

    ratings: dict[str, int] = {}
    for gate in GATES:
        rating, _ = run_gate(gate, args.repetitions)
        ratings[gate.name] = rating

    overall = 10 if all(value == 10 for value in ratings.values()) else 0
    print("\n=== VALIDATION SUMMARY ===")
    for name, rating in ratings.items():
        print(f"{name}: {rating}/10")
    print(f"overall: {overall}/10")
    return 0 if overall == 10 else 1


if __name__ == "__main__":
    raise SystemExit(main())
