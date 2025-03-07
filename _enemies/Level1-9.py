from _enemies.enemies import Enemies
import random
import time


"""SLIME"""
class Slime(Enemies):
    def __init__(self, name="Slime", weapon=None, physical_strength=5, magical_strength=5, attack=5, health=30, level=1, exp=6, mass=10, max_mass=10):
        super().__init__(name=name, weapon=weapon, physical_strength=physical_strength,
                         magical_strength=magical_strength, attack=attack,
                         health=health, level=level, exp=exp)

        self.mass = mass
        self.max_mass = max_mass

    def basic_attack(self):
        return self.attack

    def slime_throw(self):
        self.mass -= 1
        if self.mass < self.max_mass:
            self.health -= 2

        damage = self.physical_strength + max((self.attack + self.mass - 5), 1)
        return damage

    def split(self):
        if self.mass >= 5:
            new_slime = Slime(name=f"{self.name} Clone", mass=self.mass // 2, level=self.level)
            self.mass //= 2
            self.health = max(self.health // 2, 1)
            return new_slime
        return None

    def take_damage(self, damage, damage_type):
        if damage_type == "Fire":
            damage *= 2
        self.health -= damage
        if self.health <= 0:
            return True
        return False

    def __str__(self):
        return f"{self.name} (Level {self.level}) - HP: {self.health}, Mass: {self.mass}, Attack: {self.attack}"




"""GOBLIN"""
class Goblin(Enemies):
    def __init__(self, name="Goblin", weapon="Short Sword", physical_strength=8, magical_strength=3,
                 attack=6, health=35, level=1, exp=10, agility=5):

        super().__init__(name=name, weapon=weapon, physical_strength=physical_strength,
                         magical_strength=magical_strength, attack=attack,
                         health=health, level=level, exp=exp)

        self.agility = agility


    def basic_attack(self):
        base_damage = self.attack + self.physical_strength
        return base_damage

    def sneak_attack(self):
        damage = (self.attack + self.physical_strength) * 1.5  # sneak attack does 1.5x damage
        self.agility += 2  # boosttyyy eh he agility after sneak attack
        return damage

    def take_damage(self, damage):
        dodge_chance = max(0.01 * self.level + (self.agility * 0.01), 0.1)  # BALANCE THIS HERE
        dodge = True if random.random() < dodge_chance else False
        if dodge:
            return 0
        else:
            return damage


    def __str__(self):
        return f"{self.name} (Level {self.level}) - HP: {self.health}, Agility: {self.agility}, Attack: {self.attack}"




"""SKELLY"""
class Skeleton(Enemies):                  #bone bow maybe
    def __init__(self, name="Skeleton", weapon="Bone Sword" , physical_strength=6, magical_strength=2,
                 attack=4, health=40, level=1, exp=12, bones=15):

        super().__init__(name=name, weapon=weapon, physical_strength=physical_strength,
                         magical_strength=magical_strength, attack=attack,
                         health=health, level=level, exp=exp, drops=None)

        self.bones = bones  # number of bones representing durbaility opr health? health prolly
        self.drops = ["bone sword"]


    def basic_attack(self):
        return self.attack

    def skeleton_attack(self):
        damage = self.attack + self.physical_strength
        print(f"{self.name} swings its {self.weapon}!")
        return damage

    def take_damage(self, damage):
        self.health -= damage
        if self.health <= 0 and self.bones > 5:
            self.revives()
            return False  #  revives, no die trust
        elif self.health <= 0:
            print(f"{self.name} is destroyed.")
            return True  # ouchied fully
        return False

    def revives(self):
        print(f"{self.name} revives using its remaining bones!")
        self.health = 20  # trust the process
        self.bones -= 5  # damn thats a lot of bones :) get it? bones? bon- ok ill stop.

    def __str__(self):
        return f"{self.name} (Level {self.level}) - HP: {self.health}, Bones: {self.bones}, Attack: {self.attack}"



class Forest_Sprout():
    def __init__(self, name = "Forest Sprout", weapon = "Leaf Whip",health = 20, level = 1, exp = 10, attack = 2,
                 magical_strength = 1, physical_strength = 1):
        super().__init__(name=name, weapon=weapon, physical_strength=physical_strength,
                         magical_strength=magical_strength, attack=attack,
                         health=health, level=level, exp=exp)





