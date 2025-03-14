import pygame

class PhysicsEntity:
    def __init__(self, game, e_type, pos, size):
        self.game = game
        self.e_type = e_type
        self.pos = list(pos)
        self.size = size
        self.velocity = [0 , 0]

    def update(self, movement=(0, 0)):
        frame_movement = (movement[0] + self.velocity[0], movement[1] + self.velocity[1])

        self.pos[0] += frame_movement[0] #self-explanatory
        self.pos[1] += frame_movement[1]

                                    # ? Changed this to int, might break
        self.velocity[1] = min(5, int(self.velocity[1] + 0.1)) #caps it at 5 so char doesn't accelerate forever

    def render(self, surf):
        surf.blit(self.game.assets['player'], self.pos)





