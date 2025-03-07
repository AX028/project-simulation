from _status_effects.parent_effects_class import DamageStatusEffects


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
    pass

class Burn(DamageStatusEffects):
    pass


class InternalBurn(DamageStatusEffects):
    pass


class Poisoned(DamageStatusEffects):
    pass
