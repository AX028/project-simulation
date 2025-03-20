import numpy as np
import matplotlib.pyplot as plt
from numba import jit, prange, float64, int64
from matplotlib.colors import LightSource, LinearSegmentedColormap
import matplotlib.cm as cm
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
import matplotlib.patches as mpatches
from numba.cuda.random import xoroshiro128p_normal_float32


# ----------------- CORE NOISE FUNCTIONS -----------------





@jit(nopython=True)
def generate_permutation_table():
    """Generate permutation table for Perlin noise"""
    permutation = np.arange(256, dtype=np.int64)
    np.random.shuffle(permutation)
    # Extend the permutation to avoid overflow issues
    p = np.zeros(512, dtype=np.int64)
    for i in range(512):
        p[i] = permutation[i % 256]
    return p


@jit(float64(float64), nopython=True)
def fade(t):
    """Fade function for Perlin noise: 6t^5 - 15t^4 + 10t^3"""
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


@jit(float64(int64, float64, float64), nopython=True)
def grad(hash_val, x, y):
    """Gradient function for 2D Perlin noise"""
    h = hash_val & 15
    # Convert low 4 bits of hash into 8 simple gradient directions
    u = x if h < 8 else y
    v = y if h < 4 else (x if h == 12 or h == 14 else 0.0)
    return (u if (h & 1) == 0 else -u) + (v if (h & 2) == 0 else -v)


@jit(float64(int64[:], float64, float64), nopython=True)
def perlin(p, x, y):
    """Calculate Perlin noise value at a specific point"""
    # Find unit grid cell containing point
    X = np.int64(np.floor(x)) & 255
    Y = np.int64(np.floor(y)) & 255

    # Get relative coordinates within grid cell
    x -= np.floor(x)
    y -= np.floor(y)

    # Compute fade curves
    u = fade(x)
    v = fade(y)

    # Hash coordinates of the 8 cube corners
    A = p[X] + Y
    AA = p[A]
    AB = p[A + 1]
    B = p[X + 1] + Y
    BA = p[B]
    BB = p[B + 1]

    # Add blended results from 4 corners of the grid cell
    res = ((1.0 - v) * ((1.0 - u) * grad(p[AA], x, y) +
                       u * grad(p[BA], x - 1.0, y)) +
    v * ((1.0 - u) * grad(p[AB], x, y - 1.0) +
         u * grad(p[BB], x - 1.0, y - 1.0)))
    # Scale result to [-1, 1] range
    return res


# ----------------- ENHANCED MAP GENERATION -----------------

@jit(float64[:, :](int64, int64, float64, int64), nopython=True, parallel=True)
def generate_perlin_noise_map(width, height, scale, octaves):
    """Generate a Perlin noise map with improved smoothness"""
    # Initialize noise map
    noise_map = np.zeros((height, width), dtype=np.float64)

    # Generate permutation table
    p = generate_permutation_table()

    # Generate fractal noise by adding multiple octaves
    max_value = 0.0
    amplitude = 1.0
    persistence = 0.55  # Slightly increased for smoother transitions

    for octave in range(octaves):
        # Adjust frequency and amplitude for each octave
        frequency = 1.8 ** octave  # Changed from 2.0 for smoother noise
        current_amplitude = amplitude * (persistence ** octave)
        max_value += current_amplitude

        # Parallel generation for better performance
        for y in prange(height):
            for x in prange(width):
                nx = x / scale * frequency
                ny = y / scale * frequency
                noise_map[y, x] += perlin(p, nx, ny) * current_amplitude

    # Normalize to [0, 1] range
    noise_map = (noise_map / max_value) * 0.5 + 0.5

    return noise_map


@jit(float64[:, :](float64[:, :], int64), nopython=True)
def apply_multi_pass_smoothing(noise_map, passes=3):
    """Apply multiple passes of Gaussian smoothing for extra smoothness"""
    height, width = noise_map.shape
    current_map = noise_map.copy()

    for _ in range(passes):
        smoothed_map = np.zeros((height, width), dtype=np.float64)

        # Apply smoothing to inner pixels
        for y in range(2, height - 2):
            for x in range(2, width - 2):
                # Extended 5x5 Gaussian kernel for smoother results
                smoothed_map[y, x] = (
                    # Center weight
                        current_map[y, x] * 0.16 +

                        # Direct neighbors (4)
                        current_map[y - 1, x] * 0.08 +
                        current_map[y + 1, x] * 0.08 +
                        current_map[y, x - 1] * 0.08 +
                        current_map[y, x + 1] * 0.08 +

                        # Diagonal neighbors (4)
                        current_map[y - 1, x - 1] * 0.05 +
                        current_map[y - 1, x + 1] * 0.05 +
                        current_map[y + 1, x - 1] * 0.05 +
                        current_map[y + 1, x + 1] * 0.05 +

                        # Extended neighbors (outer ring)
                        current_map[y - 2, x] * 0.03 +
                        current_map[y + 2, x] * 0.03 +
                        current_map[y, x - 2] * 0.03 +
                        current_map[y, x + 2] * 0.03 +

                        # Extended diagonal neighbors
                        current_map[y - 2, x - 1] * 0.02 +
                        current_map[y - 2, x + 1] * 0.02 +
                        current_map[y + 2, x - 1] * 0.02 +
                        current_map[y + 2, x + 1] * 0.02 +
                        current_map[y - 1, x - 2] * 0.02 +
                        current_map[y - 1, x + 2] * 0.02 +
                        current_map[y + 1, x - 2] * 0.02 +
                        current_map[y + 1, x + 2] * 0.02 +

                        # Corner pixels
                        current_map[y - 2, x - 2] * 0.01 +
                        current_map[y - 2, x + 2] * 0.01 +
                        current_map[y + 2, x - 2] * 0.01 +
                        current_map[y + 2, x + 2] * 0.01
                )

        # Handle borders (simpler 3x3 kernel for borders)
        for y in range(height):
            for x in range(width):
                if (y < 2 or y >= height - 2 or x < 2 or x >= width - 2):
                    # Count valid neighbors
                    count = 1.0  # Start with center pixel
                    total = current_map[y, x]

                    # Check all 8 neighbors
                    for dy in range(-1, 2):
                        for dx in range(-1, 2):
                            ny, nx = y + dy, x + dx
                            if (ny != y or nx != x) and 0 <= ny < height and 0 <= nx < width:
                                if dy == 0 or dx == 0:  # Cardinal directions
                                    total += current_map[ny, nx] * 0.12
                                    count += 0.12
                                else:  # Diagonals
                                    total += current_map[ny, nx] * 0.08
                                    count += 0.08

                    smoothed_map[y, x] = total / count

        # Update for next pass
        current_map = smoothed_map.copy()

    return current_map


@jit(float64[:, :](float64[:, :], int64), nopython=True)
def add_terrain_details(base_terrain, seed):
    """Add small terrain details for visual interest"""
    height, width = base_terrain.shape
    detail_map = np.zeros((height, width), dtype=np.float64)

    # Set new seed for detail noise
    np.random.seed(seed + 42)

    # Generate high-frequency, low-amplitude noise
    p = generate_permutation_table()

    for y in range(height):
        for x in range(width):
            # Small scale noise
            nx = x / 20.0
            ny = y / 20.0

            # Calculate detail noise (small amplitude)
            detail = perlin(p, nx, ny) * 0.05  # Only 5% influence

            # More details where slope changes (adds interesting terrain features)
            if x > 0 and x < width - 1 and y > 0 and y < height - 1:
                dx = abs(base_terrain[y, x + 1] - base_terrain[y, x - 1])
                dy = abs(base_terrain[y + 1, x] - base_terrain[y - 1, x])
                slope = np.sqrt(dx * dx + dy * dy)

                # Add more details to steep areas
                detail *= (1.0 + slope * 2.0)

            detail_map[y, x] = detail

    # Combine with base terrain
    result = base_terrain + detail_map

    # Normalize back to [0,1]
    min_val = result.min()
    max_val = result.max()
    result = (result - min_val) / (max_val - min_val)

    return result


# ----------------- CLIMATE & BIOME SYSTEMS -----------------

@jit(float64[:, :](int64, int64, int64), nopython=True)
def generate_temperature_map(width, height, seed):
    """Generate temperature map (north-south gradient + local variations)"""
    temp_map = np.zeros((height, width), dtype=np.float64)

    # Set new seed for temperature
    np.random.seed(seed + 123)

    # Generate base latitude gradient (north-south)
    for y in range(height):
        # Normalize y to 0-1 range and create a gradient
        norm_y = y / (height - 1)
        # Convert to temperature gradient (cooler in north, warmer in south)
        # Using a slightly curved gradient for more natural distribution
        base_temp = 1.0 - (norm_y - 0.5) * (norm_y - 0.5) * 4.0

        for x in range(width):
            temp_map[y, x] = base_temp

    # Add local temperature variations with Perlin noise
    noise_map = generate_perlin_noise_map(width, height, scale=150.0, octaves=4)

    # Blend the base gradient with the noise
    for y in range(height):
        for x in range(width):
            # Noise has less effect (30%) on the base temperature gradient
            temp_map[y, x] = temp_map[y, x] * 0.7 + (noise_map[y, x] - 0.5) * 0.3

    # Normalize to [0,1] range
    min_temp = temp_map.min()
    max_temp = temp_map.max()
    temp_map = (temp_map - min_temp) / (max_temp - min_temp)

    # Apply smoothing
    temp_map = apply_multi_pass_smoothing(temp_map, passes=2)

    return temp_map


@jit(float64[:, :](int64, int64, float64[:, :], float64[:, :], int64), nopython=True)
def generate_precipitation_map(width, height, terrain_map, temp_map, seed):
    """Generate precipitation map based on terrain and temperature"""
    precip_map = np.zeros((height, width), dtype=np.float64)

    # Set new seed for precipitation
    np.random.seed(seed + 456)

    # Generate base moisture pattern with Perlin noise
    base_moisture = generate_perlin_noise_map(width, height, scale=180.0, octaves=5)

    # Apply terrain and temperature influences
    for y in range(height):
        for x in range(width):
            # Base moisture from noise
            moisture = base_moisture[y, x]

            # Terrain influence: more rain at higher elevations (orographic effect)
            # but very high elevations get less (rain shadow effect)
            if terrain_map[y, x] < 0.7:
                moisture += terrain_map[y, x] * 0.3  # More rain with higher elevation
            else:
                moisture -= (terrain_map[y, x] - 0.7) * 1.0  # Rain shadow effect

            # Temperature influence: warm air holds more moisture
            # but extreme heat causes dryness (desert effect)
            if temp_map[y, x] < 0.7:
                moisture += temp_map[y, x] * 0.2  # Warmer means more potential rain
            else:
                moisture -= (temp_map[y, x] - 0.7) * 1.5  # Too hot = desert

            precip_map[y, x] = moisture

    # Normalize to [0,1] range
    min_precip = precip_map.min()
    max_precip = precip_map.max()
    precip_map = (precip_map - min_precip) / (max_precip - min_precip)

    # Apply smoothing for more natural rain patterns
    precip_map = apply_multi_pass_smoothing(precip_map, passes=3)

    return precip_map


@jit(float64[:, :](float64[:, :]), nopython=True)
def apply_medieval_terrain_transformation(noise_map):
    """Apply non-linear transformation for medieval RPG terrain"""
    height, width = noise_map.shape
    transformed = np.zeros((height, width), dtype=np.float64)

    for y in range(height):
        for x in range(width):
            val = noise_map[y, x]

            # RPG-friendly terrain distribution
            if val < 0.27:  # Water bodies
                # Create more interesting coastlines
                if val > 0.24:
                    # Shallow waters/wetlands
                    transformed[y, x] = 0.24 + (val - 0.24) * 0.8
                else:
                    transformed[y, x] = val * 0.9
            elif val < 0.35:  # Beaches and lowlands
                transformed[y, x] = 0.27 + (val - 0.27) * 1.2
            elif val < 0.65:  # Plains and forests (most inhabitable area)
                # Expand the middle range for more playable area
                transformed[y, x] = 0.33 + (val - 0.35) * 0.7
            elif val < 0.8:  # Hills and highlands
                transformed[y, x] = 0.54 + (val - 0.65) * 1.1
            else:  # Mountains and peaks (make them more dramatic)
                transformed[y, x] = 0.705 + (val - 0.8) * 2.0

    return transformed


@jit(int64[:, :](float64[:, :], float64[:, :], float64[:, :]), nopython=True)
def generate_medieval_biome_map(terrain_map, temp_map, precip_map):
    """Generate detailed medieval RPG biomes based on terrain, temperature and precipitation"""
    height, width = terrain_map.shape
    biome_map = np.zeros((height, width), dtype=np.int64)

    # Biome IDs for medieval RPG:
    # 0: Deep Water
    # 1: Shallow Water
    # 2: Beach/Shore
    # 3: Wetlands/Marsh
    # 4: Plains/Grassland
    # 5: Farmland (potential)
    # 6: Shrubland
    # 7: Deciduous Forest
    # 8: Pine Forest
    # 9: Hills
    # 10: Highland
    # 11: Mountains
    # 12: Snow Peaks
    # 13: Desert
    # 14: Savanna
    # 15: Tundra

    for y in range(height):
        for x in range(width):
            terrain = terrain_map[y, x]
            temp = temp_map[y, x]
            precip = precip_map[y, x]

            # Water bodies
            if terrain < 0.22:
                biome_map[y, x] = 0  # Deep Water
            elif terrain < 0.27:
                biome_map[y, x] = 1  # Shallow Water

            # Coastal areas
            elif terrain < 0.31:
                if precip > 0.7:
                    biome_map[y, x] = 3  # Wetlands/Marsh
                else:
                    biome_map[y, x] = 2  # Beach/Shore

            # Lowlands
            elif terrain < 0.4:
                if temp > 0.75 and precip < 0.25:
                    biome_map[y, x] = 13  # Desert
                elif temp > 0.6 and precip < 0.5:
                    biome_map[y, x] = 14  # Savanna
                elif temp < 0.25:
                    biome_map[y, x] = 15  # Tundra
                elif 0.3 < precip < 0.6:
                    biome_map[y, x] = 5  # Farmland (potential)
                else:
                    biome_map[y, x] = 4  # Plains/Grassland

            # Mid elevations
            elif terrain < 0.55:
                if temp > 0.6 and precip < 0.4:
                    biome_map[y, x] = 6  # Shrubland
                elif temp > 0.4:
                    biome_map[y, x] = 7  # Deciduous Forest
                else:
                    biome_map[y, x] = 8  # Pine Forest

            # Higher elevations
            elif terrain < 0.7:
                biome_map[y, x] = 9  # Hills
            elif terrain < 0.8:
                biome_map[y, x] = 10  # Highland

            # Highest elevations
            elif terrain < 0.9:
                biome_map[y, x] = 11  # Mountains
            else:
                biome_map[y, x] = 12  # Snow Peaks

    return biome_map


# ----------------- VISUALIZATION -----------------

def get_medieval_biome_color(biome_id):
    """Get RGB color for medieval RPG biomes"""
    colors = {
        0: (0.05, 0.10, 0.55),  # Deep Water
        1: (0.12, 0.22, 0.65),  # Shallow Water
        2: (0.85, 0.80, 0.55),  # Beach/Shore
        3: (0.40, 0.55, 0.40),  # Wetlands/Marsh
        4: (0.70, 0.85, 0.40),  # Plains/Grassland
        5: (0.85, 0.75, 0.40),  # Farmland
        6: (0.60, 0.65, 0.30),  # Shrubland
        7: (0.20, 0.55, 0.20),  # Deciduous Forest
        8: (0.15, 0.40, 0.15),  # Pine Forest
        9: (0.60, 0.55, 0.40),  # Hills
        10: (0.50, 0.45, 0.35),  # Highland
        11: (0.60, 0.60, 0.65),  # Mountains
        12: (0.95, 0.95, 0.95),  # Snow Peaks
        13: (0.90, 0.75, 0.40),  # Desert
        14: (0.80, 0.70, 0.30),  # Savanna
        15: (0.80, 0.85, 0.90),  # Tundra
    }
    return colors.get(biome_id, (0, 0, 0))


def get_medieval_biome_name(biome_id):
    """Get name for medieval RPG biomes"""
    names = {
        0: "Deep Water",
        1: "Shallow Water",
        2: "Beach/Shore",
        3: "Wetlands/Marsh",
        4: "Plains/Grassland",
        5: "Farmland",
        6: "Shrubland",
        7: "Deciduous Forest",
        8: "Pine Forest",
        9: "Hills",
        10: "Highland",
        11: "Mountains",
        12: "Snow Peaks",
        13: "Desert",
        14: "Savanna",
        15: "Tundra",
    }
    return names.get(biome_id, "Unknown")


def create_temperature_colormap():
    """Create temperature colormap from cold blue to hot red"""
    colors = [
        (0.05, 0.05, 0.9),  # Cold (blue)
        (0.3, 0.3, 0.9),  # Cool
        (0.5, 0.5, 0.9),  # Cool-mild
        (0.6, 0.8, 0.6),  # Mild
        (0.9, 0.9, 0.3),  # Warm
        (0.9, 0.7, 0.3),  # Hot
        (0.9, 0.4, 0.2),  # Very hot (red)
    ]
    return LinearSegmentedColormap.from_list("temperature", colors, N=256)


def create_precipitation_colormap():
    """Create precipitation colormap from dry brown to wet blue-green"""
    colors = [
        (0.8, 0.7, 0.4),  # Very dry (tan)
        (0.7, 0.8, 0.4),  # Dry
        (0.6, 0.8, 0.5),  # Moderate
        (0.4, 0.8, 0.6),  # Wet
        (0.3, 0.7, 0.8),  # Very wet
        (0.2, 0.6, 0.9),  # Extremely wet (blue)
    ]
    return LinearSegmentedColormap.from_list("precipitation", colors, N=256)


def visualize_medieval_rpg_map(terrain_map, biome_map, temp_map, precip_map):
    """Create a comprehensive RPG map visualization"""
    height, width = terrain_map.shape

    # Create a larger figure with multiple subplots
    fig = plt.figure(figsize=(18, 14))
    gs = GridSpec(2, 2, figure=fig, height_ratios=[2, 1], width_ratios=[2, 1])

    # 1. Main 2.5D terrain with biomes
    ax1 = fig.add_subplot(gs[0, 0], projection='3d')

    # Create a grid for 3D visualization
    x = np.linspace(0, width - 1, width)
    y = np.linspace(0, height - 1, height)
    X, Y = np.meshgrid(x, y)

    # Apply light source for 3D effect
    ls = LightSource(azdeg=315, altdeg=45)

    # Create custom colormap for biomes
    biome_colors = []
    for i in range(16):  # 16 different biome types
        biome_colors.append(get_medieval_biome_color(i))

    biome_cmap = LinearSegmentedColormap.from_list("biomes", biome_colors, N=256)

    # Create color array from biome map
    biome_colors_array = np.zeros((height, width, 3))
    for y in range(height):
        for x in range(width):
            biome_colors_array[y, x] = get_medieval_biome_color(biome_map[y, x])

    # Create elevation factor
    elevation_factor = 15  # Adjust for more dramatic terrain
    Z = terrain_map * elevation_factor

    # Plot surface with biome coloring and enhanced lighting
    rgb = ls.shade_rgb(biome_colors_array, Z, blend_mode='soft',
                       vert_exag=0.2, fraction=0.6)

    surf = ax1.plot_surface(
        X, Y, Z,
        facecolors=rgb,
        rstride=1,
        cstride=1,
        antialiased=True,
        shade=False
    )

    # Set plot parameters
    ax1.set_title("Medieval RPG Terrain Map", fontsize=16)
    ax1.set_xlabel('X')
    ax1.set_ylabel('Y')
    ax1.set_zlabel('Elevation')
    ax1.view_init(elev=40, azim=230)
    ax1.grid(False)

    # 2. Temperature map
    ax2 = fig.add_subplot(gs[0, 1])
    temp_cmap = create_temperature_colormap()
    temp_img = ax2.imshow(temp_map, cmap=temp_cmap)
    ax2.set_title("Temperature", fontsize=14)
    plt.colorbar(temp_img, ax=ax2, label='Temperature (Cold to Hot)')
    ax2.set_xticks([])
    ax2.set_yticks([])

    # 3. Precipitation map
    ax3 = fig.add_subplot(gs[1, 0])
    precip_cmap = create_precipitation_colormap()
    precip_img = ax3.imshow(precip_map, cmap=precip_cmap)
    ax3.set_title("Precipitation", fontsize=14)
    plt.colorbar(precip_img, ax=ax3, label='Precipitation (Dry to Wet)')
    ax3.set_xticks([])
    ax3.set_yticks([])

    # 4. Biome legend
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.axis('off')
    ax4.set_title("Biome Types", fontsize=14)

    # Create legend patches for all biomes
    legend_patches = []
    biome_ids = sorted(list(set(biome_map.flatten())))
    for biome_id in biome_ids:
        color = get_medieval_biome_color(biome_id)
        name = get_medieval_biome_name(biome_id)
        patch = mpatches.Patch(color=color, label=name)
        legend_patches.append(patch)

    ax4.legend(handles=legend_patches, loc='center', fontsize=10)

    plt.tight_layout()
    return fig



# ----------------- MAIN GENERATOR FUNCTION -----------------

def generate_medieval_rpg_map(width=256, height=256, seed=None):
    """Generate a complete medieval RPG map with terrain, temperature, precipitation and biomes"""
    # Set seed for reproducibility
    if seed is None:
        seed = np.random.randint(0, 10000)
    np.random.seed(seed)

    print(f"Generating RPG map with seed {seed}...")

    # 1. Generate base terrain
    print("Generating base terrain...")
    terrain_base = generate_perlin_noise_map(width, height, scale=120.0, octaves=7)

    # 2. Apply multi-pass smoothing for extra smooth terrain
    print("Applying smoothing...")
    terrain_smooth = apply_multi_pass_smoothing(terrain_base, passes=3)

    # 3. Add small terrain details
    print("Adding terrain details...")
    terrain_detailed = add_terrain_details(terrain_smooth, seed)

    # 4. Apply terrain transformation for RPG-friendly heights
    print("Creating RPG-optimized terrain...")
    terrain_rpg = apply_medieval_terrain_transformation(terrain_detailed)

    # 5. Generate temperature map
    print("Generating temperature map...")
    temp_map = generate_temperature_map(width, height, seed)

    # 6. Generate precipitation map
    print("Generating precipitation map...")
    precip_map = generate_precipitation_map(width, height, terrain_rpg, temp_map, seed)

    # 7. Generate detailed biome map
    print("Creating biomes...")
    biome_map = generate_medieval_biome_map(terrain_rpg, temp_map, precip_map)

    # 8. Visualize the results
    print("Creating visualization...")
    fig = visualize_medieval_rpg_map(terrain_rpg, biome_map, temp_map, precip_map)

    print("Map generation complete!")
    return terrain_rpg, biome_map, temp_map, precip_map, fig, seed


def visualize_medieval_rpg_map_2d(terrain_map, biome_map, temp_map, precip_map):
    """Create a 2D bird's-eye view visualization of the RPG map"""
    height, width = terrain_map.shape

    fig, axes = plt.subplots(2, 2, figsize=(14, 14))

    # 1. Biome Map
    ax1 = axes[0, 0]
    biome_colors_array = np.zeros((height, width, 3))
    for y in range(height):
        for x in range(width):
            biome_colors_array[y, x] = get_medieval_biome_color(biome_map[y, x])
    ax1.imshow(biome_colors_array)
    ax1.set_title("Biome Map", fontsize=14)
    ax1.set_xticks([])
    ax1.set_yticks([])

    # 2. Temperature Map
    ax2 = axes[0, 1]
    temp_cmap = create_temperature_colormap()
    temp_img = ax2.imshow(temp_map, cmap=temp_cmap)
    ax2.set_title("Temperature Map", fontsize=14)
    plt.colorbar(temp_img, ax=ax2, label='Temperature (Cold to Hot)')
    ax2.set_xticks([])
    ax2.set_yticks([])

    # 3. Precipitation Map
    ax3 = axes[1, 0]
    precip_cmap = create_precipitation_colormap()
    precip_img = ax3.imshow(precip_map, cmap=precip_cmap)
    ax3.set_title("Precipitation Map", fontsize=14)
    plt.colorbar(precip_img, ax=ax3, label='Precipitation (Dry to Wet)')
    ax3.set_xticks([])
    ax3.set_yticks([])

    # 4. Biome Legend
    ax4 = axes[1, 1]
    ax4.axis('off')
    ax4.set_title("Biome Types", fontsize=14)
    legend_patches = []
    biome_ids = sorted(list(set(biome_map.flatten())))
    for biome_id in biome_ids:
        color = get_medieval_biome_color(biome_id)
        name = get_medieval_biome_name(biome_id)
        patch = mpatches.Patch(color=color, label=name)
        legend_patches.append(patch)
    ax4.legend(handles=legend_patches, loc='center', fontsize=10)

    plt.tight_layout()
    return fig


def generate_medieval_rpg_map_2d(width=256, height=256, seed=None):
    """Generate a complete medieval RPG map and visualize it in 2D"""
    if seed is None:
        seed = np.random.randint(0, 10000)
    np.random.seed(seed)
    print(f"Generating RPG map with seed {seed}...")

    # Generate components
    terrain_base = generate_perlin_noise_map(width, height, scale=120.0, octaves=7)
    terrain_smooth = apply_multi_pass_smoothing(terrain_base, passes=3)
    terrain_detailed = add_terrain_details(terrain_smooth, seed)
    terrain_rpg = apply_medieval_terrain_transformation(terrain_detailed)
    temp_map = generate_temperature_map(width, height, seed)
    precip_map = generate_precipitation_map(width, height, terrain_rpg, temp_map, seed)
    biome_map = generate_medieval_biome_map(terrain_rpg, temp_map, precip_map)

    print("Creating visualization...")
    fig = visualize_medieval_rpg_map_2d(terrain_rpg, biome_map, temp_map, precip_map)
    print("Map generation complete!")
    return terrain_rpg, biome_map, temp_map, precip_map, fig, seed


#!TEST
if __name__ == "__main__":

    WIDTH, HEIGHT = 32, 32
    terrain, biomes, temperature, precipitation, fig, seed = generate_medieval_rpg_map_2d(WIDTH, HEIGHT)
    print(f"Map generated with seed: {seed}")
    plt.show()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            height_value = terrain[y, x]
            print(f"Terrain height at ({x},{y}): {height_value}")
            biome_id = biomes[y, x]
            biome_name = get_medieval_biome_name(biome_id)
            print(f"Biome at ({x},{y}): {biome_name} (ID: {biome_id})")
            temp_value = temperature[y, x]
            print(f"Temperature at ({x},{y}): {temp_value}")
            precip_value = precipitation[y, x]
            print(f"Precipitation at ({x},{y}): {precip_value}")

#?notes to access the code
# !terrain[y, x]
# !biomes[y, x]
# !temperature[y, x]
# !precip_value[y, x]

