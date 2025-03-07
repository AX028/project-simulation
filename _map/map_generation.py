import pygame
"""
from _data.animation import Untitled_Artwork
multiplier = 0.75
width, height = int(1080 * multiplier), int(780 * multiplier)
pygame.init()
FPS = 60
clock = pygame.time.Clock()
screen = pygame.display.set_mode((width, height))
Animation_speed = 3
frames = [
    pygame.transform.scale(pygame.image.load(f"D:/Aden/Python Coding/Character/_data/animation/Untitled_Artwork/Untitled_Artwork-{str(i).zfill(2)}.png"), (width, height))
    for i in range(1, 65)
]


current_frame = 0



running = True
while running:
    screen.fill((0, 0, 0))  # Clear screen

    # Event handling
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            pass

    current_frame = (current_frame + 1) % (64 * Animation_speed)

    if current_frame == 0:
        running = False

    frame_index = current_frame // Animation_speed

    screen.blit(frames[frame_index],(0, 0))
    pygame.display.flip()
    clock.tick(FPS)
"""



Neighbor_Offsets = [(-1, 0), (-1, -1), (0, -1), (0, 0), (1, -1), (1, 0), (-1, 1), (0 , 1), (1, 1)]

class Tilemap:
    def init(self, game, tile_size = 16):
        self.tile_size = tile_size
        self.tilemap = {} #dictionary because to call cordinates,
        self.offgrid_tiles = []
        self.game = game

        for i in range(10):
            self.tilemap[str(3 + i) + ';10'] = {'type' : 'grass', 'variant': 1, 'pos' : (3 + i, 10)}
            self.tilemap['10;' + str(5 + i)] = {'type' : 'stone', 'variant': 1, 'pos' : (10, 5 + i)}

    def tiles_around(self, pos):
        tiles = []
        tile_loc = (int(pos[0] // self.tile_size), int(pos[1] // self.tile_size))
        for offset in Neighbor_Offsets:
            check_loc = str(tile_loc[0] + offset[0]) + ';' + str(tile_loc[1] + offset[1])
            if check_loc in self.tilemap:
                tiles.append(self.tilemap[check_loc])
        return tiles

    def render(self, surf):

        for tile in self.offgrid_tiles: #generate off grid tiles first
            surf.blit(self.game.assets[tile['type']][tile['variant']], tile['pos'])

        for loc in self.tilemap:
            tile = self.tilemap[loc]
            surf.blit(self.game.assets[tile['type']][tile['variant']], (tile['pos'][0] * self.tile_size, tile['pos'][1] * self.tile_size))



