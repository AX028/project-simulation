import pygame
import json
import pygame
from _map.map_generation import *

# ! import random
# ! import time

"""

Ok so, each map is gonna be a grid of tiles. 
Each tile is gonna be nine parts                    

example_map 



class Map:
    def __init__(self, tiles):
        self.tiles = tiles


class Tile:
    def __init__(self, part):
        self.part = part





class Part:
    def __init__(self, state, elevation, terrain, liquids, entities, obstacles, items, vegetation,name=None):
        self.name = name
        self.state = state
        self.elevation = elevation
        self.terrain = terrain
        self.liquids = liquids
        self.entities = entities
        self.obstacles = obstacles
        self.items = items
        self.vegetation = vegetation
    def __repr__(self):
        return f"{self.name[:2]}"


"""

pygame.init()
width, height = 800, 600
screen = pygame.display.set_mode((width, height))
clock = pygame.time.Clock()
fullscreen = False

Width, Height = pygame.display.get_surface().get_size()
White = (255, 255, 255)
Black = (0, 0, 0)
font = pygame.font.Font(None, 10)
text_surface = font.render("Hi!", True, White)
text_rect = text_surface.get_rect(center=(width // 2, height // 2))

running = True
while running:
    clock.tick(60)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN: #Key pressing detection
            if event.key == pygame.K_ESCAPE:
                fullscreen = not fullscreen
                if fullscreen: # ! MAKE IT BLACK
                    screen = pygame.display.set_mode((width, height), pygame.FULLSCREEN)
                else:
                    screen = pygame.display.set_mode((width, height))

            elif event.key == pygame.K_h:
                screen.blit(text_surface, text_rect)
    screen.fill(Black)



    pygame.display.flip()






