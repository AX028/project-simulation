"""Utilities for splitting and persisting map layers in chunks.

This module provides helper functions for breaking large map arrays into
smaller pieces that can be saved and loaded independently.  The original
version tightly coupled chunk handling with the map generation module,
which made it difficult to test in isolation.  The updated version works
with plain NumPy arrays and includes a small demo that round-trips random
data through the API.
"""

from typing import Dict, Tuple

import h5py
import numpy as np


class ChunkGenerator:
    """Helper methods for working with map chunks."""

    @staticmethod
    def generate_chunks(
        terrain: np.ndarray,
        biomes: np.ndarray,
        temperature: np.ndarray,
        precipitation: np.ndarray,
        chunk_size: int = 32,
    ) -> Tuple[
        Dict[str, np.ndarray],
        Dict[str, np.ndarray],
        Dict[str, np.ndarray],
        Dict[str, np.ndarray],
    ]:
        """Split full map layers into equally sized chunks.

        Parameters
        ----------
        terrain, biomes, temperature, precipitation:
            Full-sized arrays representing different map layers.
        chunk_size:
            The width/height of each square chunk.

        Returns
        -------
        Tuple of dictionaries keyed by "y_x" chunk coordinates containing
        the corresponding sub-arrays for each map layer.
        """

        terrain_chunks: Dict[str, np.ndarray] = {}
        biome_chunks: Dict[str, np.ndarray] = {}
        temperature_chunks: Dict[str, np.ndarray] = {}
        precipitation_chunks: Dict[str, np.ndarray] = {}

        height, width = terrain.shape

        for y in range(0, height, chunk_size):
            for x in range(0, width, chunk_size):
                coordinates = f"{y // chunk_size}_{x // chunk_size}"

                terrain_chunks[coordinates] = terrain[y : y + chunk_size, x : x + chunk_size]
                biome_chunks[coordinates] = biomes[y : y + chunk_size, x : x + chunk_size]
                temperature_chunks[coordinates] = temperature[y : y + chunk_size, x : x + chunk_size]
                precipitation_chunks[coordinates] = precipitation[y : y + chunk_size, x : x + chunk_size]

        return terrain_chunks, biome_chunks, temperature_chunks, precipitation_chunks

    @staticmethod
    def save_chunks(
        terrain_chunks: Dict[str, np.ndarray],
        biome_chunks: Dict[str, np.ndarray],
        temperature_chunks: Dict[str, np.ndarray],
        precipitation_chunks: Dict[str, np.ndarray],
        filename: str,
    ) -> None:
        """Persist chunk dictionaries to an HDF5 file."""
        filename = filename + ".h5"
        with h5py.File(filename, "w") as h5file:
            terrain_group = h5file.create_group("terrain")
            biome_group = h5file.create_group("biomes")
            temperature_group = h5file.create_group("temperature")
            precipitation_group = h5file.create_group("precipitation")

            for chunk_coords in terrain_chunks:
                terrain_group.create_dataset(
                    chunk_coords, data=terrain_chunks[chunk_coords], compression="gzip"
                )
                biome_group.create_dataset(
                    chunk_coords, data=biome_chunks[chunk_coords], compression="gzip"
                )
                temperature_group.create_dataset(
                    chunk_coords, data=temperature_chunks[chunk_coords], compression="gzip"
                )
                precipitation_group.create_dataset(
                    chunk_coords, data=precipitation_chunks[chunk_coords], compression="gzip"
                )

    @staticmethod
    def load_chunks(
        filename: str,
    ) -> Tuple[
        Dict[str, np.ndarray],
        Dict[str, np.ndarray],
        Dict[str, np.ndarray],
        Dict[str, np.ndarray],
    ]:
        """Load chunk dictionaries from an HDF5 file."""
        filename = filename + ".h5"
        with h5py.File(filename, "r") as h5file:
            terrain_chunks = {key: np.array(h5file[f"terrain/{key}"]) for key in h5file["terrain"].keys()}
            biome_chunks = {key: np.array(h5file[f"biomes/{key}"]) for key in h5file["biomes"].keys()}
            temperature_chunks = {key: np.array(h5file[f"temperature/{key}"]) for key in h5file["temperature"].keys()}
            precipitation_chunks = {
                key: np.array(h5file[f"precipitation/{key}"]) for key in h5file["precipitation"].keys()
            }

        return terrain_chunks, biome_chunks, temperature_chunks, precipitation_chunks

    @staticmethod
    def reconstruct_layer(
        chunks: Dict[str, np.ndarray], chunk_size: int, height: int, width: int
    ) -> np.ndarray:
        """Reassemble a full map layer from its chunks.

        Parameters
        ----------
        chunks: dict
            Dictionary of chunk arrays keyed by "y_x" coordinates.
        chunk_size: int
            Size of each square chunk.
        height, width: int
            Dimensions of the resulting array.
        """

        full = np.zeros((height, width), dtype=next(iter(chunks.values())).dtype)
        for coord, data in chunks.items():
            cy, cx = map(int, coord.split("_"))
            y, x = cy * chunk_size, cx * chunk_size
            full[y : y + data.shape[0], x : x + data.shape[1]] = data
        return full


def main() -> None:
    """Simple demonstration that round-trips random data through the API."""
    height = width = 64
    terrain = np.random.rand(height, width)
    biomes = np.random.randint(0, 5, size=(height, width))
    temperature = np.random.rand(height, width)
    precipitation = np.random.rand(height, width)

    terrain_chunks, biome_chunks, temperature_chunks, precipitation_chunks = ChunkGenerator.generate_chunks(
        terrain, biomes, temperature, precipitation
    )
    ChunkGenerator.save_chunks(terrain_chunks, biome_chunks, temperature_chunks, precipitation_chunks, "test_chunks")
    terrain_chunks, biome_chunks, temperature_chunks, precipitation_chunks = ChunkGenerator.load_chunks("test_chunks")

    terrain_recon = ChunkGenerator.reconstruct_layer(terrain_chunks, 32, height, width)
    assert np.allclose(terrain, terrain_recon)
    print("Chunk round-trip successful; data reconstructed correctly.")


if __name__ == "__main__":
    main()
