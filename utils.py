import pygame
import os

Base_Image_Path = '_data/images/'

def load_image(path):
    img = pygame.image.load(Base_Image_Path + path).convert()
    img.set_colorkey((0, 0, 0))
    return img
def load_images(path):
    images = []
    for img_name in sorted(os.listdir(Base_Image_Path + path)):
        images.append(load_image(path + '/' + img_name))
    return images

