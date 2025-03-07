from abc import ABC, abstractmethod
from _body_parts.body_parts import HumanoidBodyParts

#Base _characters class



"""strength determines physical attacks, stamina
dexterity determines ranged attacks, speed, initiative, stealth, and movements
constitution determines health, healing, resisting poison, concentration, stamina. 
intelligence determines resist mental effects, arcana, investigation, nature, and spell casting
wisdom determines animal handling, insight, medicine, survival, cleric and druid
charisma determines talking with others, and shop events, and convincing."""


class Characters(ABC):
    def __init__(self, name, strength, dexterity, constitution, intelligence, wisdom, charisma, current_mana, max_mana,
                 weapon, body_type=HumanoidBodyParts()):
        self.name = name
        self.strength = strength
        self.dexterity = dexterity
        self.constitution = constitution
        self.intelligence = intelligence
        self.wisdom = wisdom
        self.charisma = charisma
        self.level = 1
        self.exp = 0
        self.current_mana = current_mana
        self.max_mana = max_mana
        self.weapon = weapon
        self.body_type = body_type

        self.intimidation = body_type.get_intimidation() + weapon.intimidation
        self.current_mana = intelligence * 5
        self.max_mana = intelligence * 5  # max mana based on intelligence


    def receive_damage(self, damage):
        damage_taken = max(damage - (self.constitution * 0.5), 1)  # reduce dmg by const factor and min dmg
        return damage_taken

    @abstractmethod
    def attack_enemy(self):
        pass


    def leveling(self, enemy):
        leveling_determine = True if (enemy.exp + self.exp) > (20 + (self.level * 5)) else False #if exp gained from monster is above level cap, return true which then calls the level up function
        self.level_up() if leveling_determine == True else None #calls the level up function if true

    def level_up(self): #level up
        self.current_mana = self.max_mana
        self.level += 1
        self.strength += 1
        self.dexterity += 1
        self.constitution += 1
        self.intelligence += 1
        self.wisdom += 1
        self.charisma += 1

        print(f"{self.name} leveled up! Now at Level {self.level}")


    @property
    def regenerate_mana(self):
        """mana regen based on int, min of 1 and max of your max mana"""
        regeneration_rate = 1 + (self.intelligence // 5)
        self.current_mana = min(self.max_mana, self.current_mana + regeneration_rate)
        return self.current_mana



