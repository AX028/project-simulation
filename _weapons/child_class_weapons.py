from .weapons import Weapon

#my comment!!! :c
class Sword(Weapon):
    def __init__(self, name="Sword", damage=10, damage_type="slash", weapon_type="sword",
                 quality="normal", current_durability=250, max_durability=250, reach = 1):
        super().__init__(name, damage, damage_type, weapon_type, quality, current_durability, max_durability)

        self.quality = quality
        self.current_durability = current_durability
        self.max_durability = max_durability

    def use(self, damage):
        quality_multiplier = {
            "poor": 0.75,
            "normal": 1.0,
            "uncommon": 1.2,
            "rare": 1.5,
            "epic": 1.75,
            "legendary": 2.0,
            "mythic": 2.5,
            "special": 5.0
        }
        can_use = super().durability
        if can_use:
            final_damage = damage * quality_multiplier[self.quality]
        else:
            final_damage = damage * 0.5
        return [final_damage, self.damage_type]





class Spear(Weapon):
    def __init__(self, name="Spear", damage=8, damage_type="pierce", weapon_type="spear",
                 quality="normal", current_durability=300, max_durability=300, reach = 3):
        super().__init__(name, damage, damage_type, weapon_type, quality, current_durability, max_durability, reach)

        self.quality = quality
        self.current_durability = current_durability
        self.max_durability = max_durability
        self.reach = reach

        #Smash hehe
#????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????
    def use(self, damage):
        quality_multiplier = {
            "poor": 0.75,
            "normal": 1.0,
            "uncommon": 1.2,
            "rare": 1.5,
            "epic": 1.75,
            "legendary": 2.0,
            "mythic": 2.5,
            "special": 5.0
        }
        can_use = super().durability
        if can_use:
            final_damage = damage * quality_multiplier[self.quality]
        else:
            final_damage = damage * 0.5
        return [final_damage, self.damage_type]

