from abc import ABC, abstractmethod
#base class for _status_effects
""""""

"""PARENT CLASS FOR STATUS EFFECTS DEALING WITH DAMAGE"""
class DamageStatusEffects(ABC):
    def __init__(self, name, current_cooldown, cooldown, strength, severity=1):
        self.name = name
        self.cooldown = cooldown
        self.current_cooldown = current_cooldown
        self.strength = strength
        self.severity = severity

    @abstractmethod #must alter this
    def apply_effect(self, damage):
        return damage

    def decrement_effect(self, decrement):
        self.strength -= decrement


"""PARENT CLASS FOR STATUS EFFECTS DEALING WITH DEBUFFS"""
class DebuffStatusEffects(ABC):
    def __init__(self, name, current_cooldown, cooldown, strength, severity=1):
        self.name = name
        self.cooldown = cooldown
        self.current_cooldown = current_cooldown
        self.strength = strength
        self.severity = severity

    @abstractmethod
    def apply_effect(self, damage):
        return damage

    def decrement_effect(self, decrement):
        self.strength -= decrement