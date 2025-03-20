from _characters.character import Characters

import random


class Rogue(Characters):
    def __init__(self, name, strength, dexterity, constitution, intelligence, wisdom, charisma):
        # does the thingy with the parent class
        super().__init__(name, strength, dexterity, constitution, intelligence, wisdom, charisma, max_mana=intelligence*6, current_mana = intelligence*5)

        self.stealth = 0  # new thingy stealth hehe
        self.crit_chance = 0  # crit chance implemented through attr

    def level_up(self):
        #level up bias for dext
        super().level_up()  # uses parent class level up
        self.stealth += 2  # stealth stat increase level up
        self.crit_chance += 0.05  # crit chance level up
        self.dexterity += 2 #increases by 3
        self.charisma += 1 #icnreases by 2

        print(f"{self.name} leveled up! Stealth: {self.stealth}, Crit Chance: {self.crit_chance * 100}%")

    def attack_enemy(self):
        #overriding attack method
        crit_multiplier = 1.3 if random.random() <= self.crit_chance else 1
        damage_dealt = max(self.strength * 0.5, 1)
        #crit multiplier
        damage_dealt *= crit_multiplier

        #bonus dmg backstab and crit
        stealth_damage_bonus = 1.2 if self.stealth > 10 else 1
        damage_dealt *= stealth_damage_bonus
        final_damage = int(damage_dealt * min(2.0, max(1.1, (self.dexterity * 0.5))) if random.randint(0,
                                100) <= self.dexterity * 2 else damage_dealt)  #apply dmg

        return final_damage

    def use_stealth(self):
        """attempt to hide."""
        success = random.random() <= self.stealth / 100  #  success chance
        print(f"{self.name} successfully sneaked past the enemy!") if success else print(
            f"{self.name} failed to hide and was spotted!")

    def receive_damage(self, damage):
        damage_taken = max(damage - (self.constitution * 0.5), 1) if random.randint(0, 100) > (self.dexterity * 0.5) else 0 # reduce dmg by const factor and min dmg and evade chance
        return damage_taken

