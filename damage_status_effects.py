from _status_effects.parent_effects_class import DamageStatusEffects
from _characters.character import Characters
from _characters.barbarian import Barbarian

print(dir(Barbarian))

"""BLEED"""
class Bleed(DamageStatusEffects):
    def __init__(self, name="Bleed", strength=0, max_strength=5, cooldown=0, current_cooldown=3):
        super().__init__(name, cooldown, current_cooldown, strength)
        self.strength = strength
        self.max_strength = max_strength

    def apply_effect(self, damage):
        damage1 = damage
        self.strength = min(self.strength + 1, 5)
        for i in range(0, self.strength):
            damage += 0.5 if i < 3 else 1
        self.cooldown = 0
        print(f"{self.name} applied. Damage: {damage - damage1}")
        return damage

    def __str__(self):
        return f"{self.name} {self.strength}/{self.max_strength}"

class InternalBleed(DamageStatusEffects):
    def __init__(self, name="Internal Bleed", strength=0, max_strength=4, cooldown=0, current_cooldown=4):
        super().__init__(name, cooldown, current_cooldown, strength)
        self.strength = strength
        self.max_strength = max_strength

    def apply_effect(self, damage):
        base_damage = damage
        self.strength = min(self.strength + 1, self.max_strength)
        damage += self.strength * 1.5
        self.cooldown = 0
        print(f"{self.name} applied. Extra Damage: {damage - base_damage}")
        return damage

class Burn(DamageStatusEffects):
    def __init__(self, name="Burn", strength=0, max_strength=5, cooldown=0, current_cooldown=2):
        super().__init__(name, cooldown, current_cooldown, strength)
        self.strength = strength
        self.max_strength = max_strength

    def apply_effect(self, damage):
        base_damage = damage
        self.strength = min(self.strength + 1, self.max_strength)
        for i in range(self.strength):
            damage += 0.4 if i < 2 else 0.8
        self.cooldown = 0
        print(f"{self.name} applied. Extra Damage: {damage - base_damage}")
        return damage


class InternalBurn(DamageStatusEffects):
    def __init__(self, name="Internal Burn", strength=0, max_strength=4, cooldown=0, current_cooldown=4):
        super().__init__(name, cooldown, current_cooldown, strength)
        self.strength = strength
        self.max_strength = max_strength

    def apply_effect(self, damage):
        base_damage = damage
        self.strength = min(self.strength + 1, self.max_strength)
        damage += self.strength * 1.5
        self.cooldown = 0
        print(f"{self.name} applied. Extra Damage: {damage - base_damage}")
        return damage


class Poisoned(DamageStatusEffects):
    def __init__(self, name="Poisoned", strength=0, max_strength=3, cooldown=0, current_cooldown=5):
        super().__init__(name, cooldown, current_cooldown, strength)
        self.strength = strength
        self.max_strength = max_strength

    def apply_effect(self, damage):
        base_damage = damage
        self.strength = min(self.strength + 1, self.max_strength)
        damage += self.strength * 0.7
        self.cooldown = 0
        print(f"{self.name} applied. Extra Damage: {damage - base_damage}")
        return damage
