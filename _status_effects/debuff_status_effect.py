from _status_effects.parent_effects_class import DebuffStatusEffects, DamageStatusEffects

import time
"""WEAKNESS"""
class PhysicalWeakness(DebuffStatusEffects):
    def __init__(self, name="Weakness""", strength=0, max_strength=3, cooldown=0, current_cooldown=2):
        super().__init__(name, cooldown, current_cooldown, strength)
        self.strength = strength
        self.max_strength = max_strength


    #this should only be applied to person with the weakness not the other way around
    def apply_effect(self, damage):
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


    # def apply_effect(self, character, part_of_body):
    #    dictionary = character.body_parts.parts
    #    for parts in dictionary:
    #        for key, value in parts[part_of_body].items():
    #            if key == "armor":
    #                reduced_defense = value.defense * 0.8
    #     return reduced_defense



class Disorientation(DebuffStatusEffects):
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
    pass


class Paralysis(DebuffStatusEffects):
    pass


class Freeze(DebuffStatusEffects):
    pass


class Slowness(DebuffStatusEffects):
    pass

