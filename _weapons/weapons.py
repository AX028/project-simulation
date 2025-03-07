from abc import ABC, abstractmethod
#base Weapon class

class Weapon(ABC):

    def __init__(self, name, damage, damage_type, weapon_type, quality, current_durability, max_durability,
                 intimidation):
        self.name = name  # Weapon name
        self.damage = damage  # base damage
        self.current_durability = current_durability  # durability
        self.max_durability = max_durability  # max durability
        self.damage_type = damage_type  # dmg type: slashing, stabbing
        self.weapon_type = weapon_type  # type of weapon, sword axe
        self.quality = quality  # quality like legendary or something
        self.intimidation = intimidation


    def is_broken(self):
        return self.current_durability <= 0

    @abstractmethod
    def use(self, damage):
        pass

    @property
    def durability(self):
        return self.current_durability >= 1 #true if it has more than one durability

    def repair(self, repair_amount):
        if self.is_broken():
            print(f"{self.name} is broken. It needs to be repaired first.")
            return False
        else:
            self.current_durability = min(self.current_durability + repair_amount, self.max_durability)
            print(f"{self.name} repaired. Current durability: {self.current_durability}/{self.max_durability}")
            return True

    def __str__(self):
        #representation of weapon
        return f"{self.name} ({self.weapon_type}, {self.damage_type}) - Quality: {self.quality}"
