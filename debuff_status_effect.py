from _status_effects.parent_effects_class import DebuffStatusEffects, DamageStatusEffects

import time
"""WEAKNESS"""
class PhysicalWeakness(DebuffStatusEffects):
    def __init__(self, name="Weakness""", strength=0, max_strength=3, cooldown=0, current_cooldown=2):
        super().__init__(name, cooldown, current_cooldown, strength)
        self.strength = strength
        self.max_strength = max_strength


    #this should only be applied to person with the weakness not the other way around
    def apply_effect(self, damage, body_part):
        self.strength = min(self.strength + 1, 3)
        damage *= 0.8 #reduces damage by 20%
        self.cooldown = 0
        return damage #muah <3

    def remove_effect(self):
        self.cooldown += 1
        if self.cooldown >= self.current_cooldown:
            self.strength -= 1 #oh hell nah balance this

class ArmorPenetration(DebuffStatusEffects):
    def __init__(self, name = "ArmorPenetration", strength = 0, max_strength = 2, cooldown = 0, current_cooldown = 3):
        super().__init__(name, cooldown, current_cooldown, strength)
        self.strength = strength
        self.max_strength = max_strength


    def apply_effect(self, armor):
        armor.defense *= 0.8 # * bro this so isn't it/right change this later






class Disorientation(DebuffStatusEffects):
    #make a fricking accuracy effect later SIGH
    pass


class Corrosion(DamageStatusEffects):
    def __init__(self, name="Corrosion", strength=0, max_strength=3, cooldown=0, current_cooldown=3):
        super().__init__(name, cooldown, current_cooldown, strength)
        self.strength = strength
        self.max_strength = max_strength

    def apply_effect(self, damage):

        initial_damage = damage
        self.strength = min(self.strength + 1, self.max_strength)  # Increase strength but cap it

        # Damage increases by 1 per stack, maxing out at max_strength
        damage += self.strength * 3 #balance plz

        self.cooldown = 0  # Reset cooldown on application
        print(f"{self.name} applied. Additional Damage: {damage - initial_damage}")
        return damage

    def __str__(self):
        return f"{self.name} {self.strength}/{self.max_strength}"



class Shock(DebuffStatusEffects):
    #paralysis accuracy
    pass


class Paralysis(DebuffStatusEffects):
    #make movements slower and also decrease movement stuff

    pass


class Freeze(DebuffStatusEffects):
    #decrease movement speed, damage, and brittle?
    pass


class Slowness(DebuffStatusEffects):
    #decrease the stamina
    pass

