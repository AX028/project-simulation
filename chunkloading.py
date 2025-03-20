import h5py
from _map.map_generation import *

class ChunkGenerator:

    @staticmethod
    def generate_chunks(terrain, biomes, temperature, precipitation, chunk_size=32):
        terrain_chunks = {}
        biome_chunks = {}
        temperature_chunks = {}
        precipitation_chunks = {}

        height, width = terrain.shape

        for y in range(0, height, chunk_size):
            for x in range(0, width, chunk_size):
                coordinates = f"{y // chunk_size}_{x // chunk_size}"


                terrain_chunks[coordinates] = terrain[y:y+chunk_size, x:x+chunk_size]
                biome_chunks[coordinates] = biomes[y:y+chunk_size, x:x+chunk_size]
                temperature_chunks[coordinates] = temperature[y:y+chunk_size, x:x+chunk_size]
                precipitation_chunks[coordinates] = precipitation[y:y+chunk_size, x:x+chunk_size]

        return terrain_chunks, biome_chunks, temperature_chunks, precipitation_chunks

    @staticmethod
    def save_chunks(terrain_chunks, biome_chunks, temperature_chunks, precipitation_chunks, filename):
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
    def load_chunks(filename):
        filename = filename + ".h5"
        with h5py.File(filename, "r") as h5file:
            terrain_chunks = {key: np.array(h5file[f"terrain/{key}"]) for key in h5file["terrain"].keys()}
            biome_chunks = {key: np.array(h5file[f"biomes/{key}"]) for key in h5file["biomes"].keys()}
            temperature_chunks = {key: np.array(h5file[f"temperature/{key}"]) for key in h5file["temperature"].keys()}
            precipitation_chunks = {key: np.array(h5file[f"precipitation/{key}"]) for key in
                                    h5file["precipitation"].keys()}

        return terrain_chunks, biome_chunks, temperature_chunks, precipitation_chunks


def main():
    terrain, biomes, temperature, precipitation, fig, seed = generate_medieval_rpg_map_2d(1024, 1024)
    terrain_chunks, biome_chunks, temperature_chunks, precipitation_chunks = ChunkGenerator.generate_chunks(terrain, biomes, temperature, precipitation)
    ChunkGenerator.save_chunks(terrain_chunks, biome_chunks, temperature_chunks, precipitation_chunks, "test_chunks")
    terrain_chunks, biome_chunks, temperature_chunks, precipitation_chunks = ChunkGenerator.load_chunks("test_chunks")

    print(terrain_chunks)
    print(biome_chunks)
    print(temperature_chunks)
    print(precipitation_chunks)

if __name__ == "__main__":
    main()

