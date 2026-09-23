"""Deterministic headless world generation and chunk persistence."""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
from numpy.typing import NDArray

from .models import SimulationError, WorldConfig, WorldMap

WORLD_SCHEMA_VERSION = 1
_LAYER_NAMES = ("terrain", "biome", "temperature", "precipitation")


def _smooth(layer: NDArray[np.float64], passes: int = 4) -> NDArray[np.float64]:
    result = layer.copy()
    for _ in range(passes):
        padded = np.pad(result, 1, mode="edge")
        result = (
            padded[1:-1, 1:-1]
            + padded[:-2, 1:-1]
            + padded[2:, 1:-1]
            + padded[1:-1, :-2]
            + padded[1:-1, 2:]
        ) / 5
    minimum = float(result.min())
    maximum = float(result.max())
    return (result - minimum) / (maximum - minimum or 1.0)


def generate_world(config: WorldConfig, seed: int) -> WorldMap:
    rng = np.random.default_rng(seed)
    terrain = _smooth(rng.random((config.height, config.width)))
    latitude = np.abs(np.linspace(-1, 1, config.height))[:, None]
    temperature = np.clip(
        1 - latitude - terrain * 0.38 + rng.normal(0, 0.035, terrain.shape),
        0,
        1,
    )
    precipitation = np.clip(
        _smooth(rng.random(terrain.shape), 3) * (1.15 - terrain * 0.35),
        0,
        1,
    )
    biome = np.zeros(terrain.shape, dtype=np.uint8)
    biome[terrain < 0.27] = 0
    biome[(terrain >= 0.27) & (temperature < 0.28)] = 1
    biome[
        (terrain >= 0.27)
        & (temperature >= 0.28)
        & (precipitation < 0.3)
    ] = 2
    biome[
        (terrain >= 0.27)
        & (temperature >= 0.28)
        & (precipitation >= 0.3)
    ] = 3
    biome[terrain > 0.78] = 4
    return WorldMap(seed, config, terrain, biome, temperature, precipitation)


def _expected_chunks(
    config: WorldConfig,
) -> dict[str, tuple[int, int, int, int]]:
    expected: dict[str, tuple[int, int, int, int]] = {}
    size = config.chunk_size
    for y in range(0, config.height, size):
        for x in range(0, config.width, size):
            height = min(size, config.height - y)
            width = min(size, config.width - x)
            expected[f"{y}_{x}"] = (y, x, height, width)
    return expected


def _validate_world_layers(world: WorldMap) -> None:
    expected_shape = (world.config.height, world.config.width)
    for name in _LAYER_NAMES:
        layer = getattr(world, name)
        if not isinstance(layer, np.ndarray):
            raise ValueError(f"world layer {name} must be a numpy array")
        if layer.shape != expected_shape:
            raise ValueError(
                f"world layer {name} has shape {layer.shape}; "
                f"expected {expected_shape}"
            )
        if not np.all(np.isfinite(layer)):
            raise ValueError(f"world layer {name} contains non-finite values")


class WorldStore:
    """Versioned HDF5 store with complete chunk validation."""

    @staticmethod
    def write(world: WorldMap, path: str | Path) -> None:
        _validate_world_layers(world)
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.unlink(missing_ok=True)
        try:
            with h5py.File(temporary, "w") as handle:
                handle.attrs.update(
                    schema_version=WORLD_SCHEMA_VERSION,
                    seed=world.seed,
                    width=world.config.width,
                    height=world.config.height,
                    chunk_size=world.config.chunk_size,
                )
                group = handle.create_group("chunks")
                for key, (y, x, height, width) in _expected_chunks(
                    world.config
                ).items():
                    chunk = group.create_group(key)
                    bounds = np.s_[y : y + height, x : x + width]
                    chunk.create_dataset(
                        "terrain",
                        data=world.terrain[bounds],
                        compression="gzip",
                    )
                    chunk.create_dataset(
                        "biome",
                        data=world.biome[bounds],
                        compression="gzip",
                    )
                    chunk.create_dataset(
                        "temperature",
                        data=world.temperature[bounds],
                        compression="gzip",
                    )
                    chunk.create_dataset(
                        "precipitation",
                        data=world.precipitation[bounds],
                        compression="gzip",
                    )
            temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    @staticmethod
    def read(path: str | Path) -> WorldMap:
        try:
            with h5py.File(path, "r") as handle:
                version = int(handle.attrs["schema_version"])
                if version != WORLD_SCHEMA_VERSION:
                    raise SimulationError(
                        f"unsupported world schema {version}"
                    )
                config = WorldConfig(
                    int(handle.attrs["width"]),
                    int(handle.attrs["height"]),
                    int(handle.attrs["chunk_size"]),
                )
                seed = int(handle.attrs["seed"])
                chunks = handle["chunks"]
                if not isinstance(chunks, h5py.Group):
                    raise SimulationError("world chunks entry must be a group")

                expected = _expected_chunks(config)
                actual_keys = set(chunks.keys())
                expected_keys = set(expected)
                missing = sorted(expected_keys - actual_keys)
                unexpected = sorted(actual_keys - expected_keys)
                if missing or unexpected:
                    raise SimulationError(
                        "world chunk set is incomplete or inconsistent; "
                        f"missing={missing}, unexpected={unexpected}"
                    )

                layers: dict[str, NDArray[np.generic]] = {
                    "terrain": np.empty(
                        (config.height, config.width),
                        dtype=np.float64,
                    ),
                    "biome": np.empty(
                        (config.height, config.width),
                        dtype=np.uint8,
                    ),
                    "temperature": np.empty(
                        (config.height, config.width),
                        dtype=np.float64,
                    ),
                    "precipitation": np.empty(
                        (config.height, config.width),
                        dtype=np.float64,
                    ),
                }

                for key, (y, x, height, width) in expected.items():
                    chunk = chunks[key]
                    if not isinstance(chunk, h5py.Group):
                        raise SimulationError(
                            f"world chunk {key} must be a group"
                        )
                    for name, layer in layers.items():
                        if name not in chunk:
                            raise SimulationError(
                                f"world chunk {key} is missing dataset {name}"
                            )
                        dataset = chunk[name]
                        if not isinstance(dataset, h5py.Dataset):
                            raise SimulationError(
                                f"world chunk {key}/{name} must be a dataset"
                            )
                        data = dataset[...]
                        expected_shape = (height, width)
                        if data.shape != expected_shape:
                            raise SimulationError(
                                f"world chunk {key}/{name} has shape "
                                f"{data.shape}; expected {expected_shape}"
                            )
                        if not np.all(np.isfinite(data)):
                            raise SimulationError(
                                f"world chunk {key}/{name} contains "
                                "non-finite values"
                            )
                        layer[y : y + height, x : x + width] = data

                return WorldMap(
                    seed,
                    config,
                    layers["terrain"],
                    layers["biome"],
                    layers["temperature"],
                    layers["precipitation"],
                )
        except SimulationError:
            raise
        except (OSError, KeyError, TypeError, ValueError) as exc:
            raise SimulationError(
                f"could not read world file: {exc}"
            ) from exc
