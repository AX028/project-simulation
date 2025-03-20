import pygame
import sys
from scripts.entities import PhysicsEntity
from scripts.utils import load_image, load_images
from scripts.tilemap import Tilemap
class Game:
    def __init__(self):
        pygame.init()

        pygame.display.set_caption('Test Platformer')
        self.screen = pygame.display.set_mode((640,480))

        self.display = pygame.Surface((320, 240))
        self.clock = pygame.time.Clock()


        self.movement = [False, False]

        self.assets = {
            'player': load_image('entities/player.png'),
            'decor' : load_images('tiles/decor'),
            'grass': load_images('tiles/grass'),
            'stone': load_images('tiles/stone'),
            'large_decor': load_images('tiles/large_decor'),
            'background': load_image('background.png'),

        }

        self.player = PhysicsEntity(self, 'player', (50, 50), (8, 15))
        self.tilemap = Tilemap(self, tile_size=16)



# ? Cam system
        self.cam = [0, 0] #position for it


    def run(self):
        while True:
            # self.display.fill((14, 219, 248))
            self.display.blit(self.assets['background'], (0,0)) #resets the screen to this background instead
            self.cam[0] += (self.player.rect().centerx - self.display.get_width() / 2 - self.cam[0]) / 30  # centers the player, makes it smooth
            self.cam[1] += (self.player.rect().centery - self.display.get_height() / 2 - self.cam[1]) / 30  # making it a 30 increments
            round_cam = (int(self.cam[0]), int(self.cam[1]))  # rounding it so that there's no jittering because its a pixel game
            self.tilemap.render(self.display, offset = round_cam) #so that the blocks move so on so forth


            self.player.update(self.tilemap, (self.movement[1] - self.movement[0], 0))
            self.player.render(self.display, offset = round_cam)#so that the blocks move so on so forth



            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_LEFT or event.key == pygame.K_a:
                        self.movement[0] = True

                    if event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                        self.movement[1] = True
                    if event.key == pygame.K_SPACE:
                        if self.player.readyJump == True:
                            self.player.velocity[1] =  -3

                if event.type == pygame.KEYUP:
                    if event.key == pygame.K_LEFT or event.key == pygame.K_a:
                        self.movement[0] = False
                    if event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                        self.movement[1] = False

            self.screen.blit(pygame.transform.scale(self.display, self.screen.get_size()))
            pygame.display.update()
            self.clock.tick(60)



Game().run()







