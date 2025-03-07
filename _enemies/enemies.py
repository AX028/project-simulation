from abc import ABC, abstractmethod

#base _enemies class


class Enemies(ABC):
    def __init__(self, name, weapon, physical_strength, magical_strength, attack, health, level, exp, parts=None, drops=None):
        self.name = name
        self.weapon = weapon
        self.physical_strength = physical_strength
        self.magical_strength = magical_strength
        self.attack = attack
        self.health = health
        self.level = level
        self.exp = exp
        self.parts = parts
        self.drops = drops
        # self.exp = level*2 * exp



    @abstractmethod
    def basic_attack(self):
        pass

    @abstractmethod
    def special_ability(self):
        pass

    def level_up(self):  # level up
        if self.exp >= (20 + (self.level * 5)):
            self.physical_strength += 1
            self.magical_strength += 1
            self.attack += 1
            self.health += 1
            self.level += 1
            print(f"{self.name} leveled up! Now at Level {self.level}")
        else:
            print(f"{self.name} cannot level up.")

    def return_exp(self):
        return int((self.level * 5 + self.exp) / (2 + (self.level * 0.1))) #Returns the total exp divided by 2 + (self.level * 0.1) which should make it balanced?

    def __str__(self):
        return f"{self.name} - Level: {self.level} - Health: {self.health}"






