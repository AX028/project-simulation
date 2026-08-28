"""Deterministic headless world generation and chunk persistence."""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
from numpy.typing import NDArray

from .models import SimulationError, WorldConfig, WorldMap

WORLD_SCHEMA_VERSION = 1


def _smooth(layer: NDArray[np.float64], passes: int = 4) -> NDArray[np.float64]:
    result = layer.copy()
    for _ in range(passes):
        result = (
            result
            + np.roll(result, 1, 0)
            + np.roll(result, -1, 0)
            + np.roll(result, 1, 1)
            + np.roll(result, -1, 1)
        ) / 5
    minimum = float(result.min())
    maximum = float(result.max())
    return (result - minimum) / (maximum - minimum or 1.0)


def generate_world(config: WorldConfig, seed: int) -> WorldMap:
    if config.width <= 0 or config.height <= 0:
        raise ValueError("world dimensions must be positive")
    if config.chunk_size <= 0:
        raise ValueError("chunk size must be positive")
    rng = np.random.default_rng(seed)
    terrain = _smooth(rng.random((config.height, config.width)))
    latitude = np.abs(np.linspace(-1, 1, config.height))[:, None]
    temperature = np.clip(1 - latitude - terrain * 0.38 + rng.normal(0, 0.035, terrain.shape), 0, 1)
    precipitation = np.clip(_smooth(rng.random(terrain.shape), 3) * (1.15 - terrain * 0.35), 0, 1)
    biome = np.zeros(terrain.shape, dtype=np.uint8)
    biome[terrain < 0.27] = 0  # water
    biome[(terrain >= 0.27) & (temperature < 0.28)] = 1  # tundra
    biome[(terrain >= 0.27) & (temperature >= 0.28) & (precipitation < 0.3)] = 2  # dryland
    biome[(terrain >= 0.27) & (temperature >= 0.28) & (precipitation >= 0.3)] = 3  # woodland
    biome[terrain > 0.78] = 4  # mountain
    return WorldMap(seed, config, terrain, biome, temperature, precipitation)


class WorldStore:
    """Versioned HDF5 store that preserves independently readable chunks."""

    @staticmethod
    def write(world: WorldMap, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with h5py.File(destination, "w") as handle:
            handle.attrs.update(
                schema_version=WORLD_SCHEMA_VERSION,
                seed=world.seed,
                width=world.config.width,
                height=world.config.height,
                chunk_size=world.config.chunk_size,
            )
            group = handle.create_group("chunks")
            size = world.config.chunk_size
            for y in range(0, world.config.height, size):
                for x in range(0, world.config.width, size):
                    chunk = group.create_group(f"{y}_{x}")
                    bounds = np.s_[
                        y : min(y + size, world.config.height),
                        x : min(x + size, world.config.width),
                    ]
                    chunk.create_dataset("terrain", data=world.terrain[bounds], compression="gzip")
                    chunk.create_dataset("biome", data=world.biome[bounds], compression="gzip")
                    chunk.create_dataset(
                        "temperature", data=world.temperature[bounds], compression="gzip"
                    )
                    chunk.create_dataset(
                        "precipitation", data=world.precipitation[bounds], compression="gzip"
                    )

    @staticmethod
    def read(path: str | Path) -> WorldMap:
        try:
            with h5py.File(path, "r") as handle:
                version = int(handle.attrs["schema_version"])
                if version != WORLD_SCHEMA_VERSION:
                    raise SimulationError(f"unsupported world schema {version}")
                config = WorldConfig(
                    int(handle.attrs["width"]),
                    int(handle.attrs["height"]),
                    int(handle.attrs["chunk_size"]),
                )
                layers: dict[str, NDArray[np.generic]] = {
                    "terrain": np.zeros((config.height, config.width), dtype=np.float64),
                    "biome": np.zeros((config.height, config.width), dtype=np.uint8),
                    "temperature": np.zeros((config.height, config.width), dtype=np.float64),
                    "precipitation": np.zeros((config.height, config.width), dtype=np.float64),
                }
                for key, chunk in handle["chunks"].items():
                    y, x = (int(value) for value in key.split("_"))
                    for name, layer in layers.items():
                        data = chunk[name][...]
                        layer[y : y + data.shape[0], x : x + data.shape[1]] = data
                return WorldMap(
                    int(handle.attrs["seed"]),
                    config,
                    layers["terrain"],
                    layers["biome"],
                    layers["temperature"],
                    layers["precipitation"],
                )
        except (OSError, KeyError, ValueError) as exc:
            raise SimulationError(f"could not read world file: {exc}") from exc
