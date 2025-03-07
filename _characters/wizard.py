from character import Characters
import random

# mana based character obviously, should have more wisdom, intelligence, and maybe a bit more charisma.
class Wizard(Characters):
    def __init__(self, name, strength, dexterity, constitution, intelligence, wisdom, charisma):
        # initialize parent func with addition attr
        super().__init__(name, strength, dexterity, constitution, intelligence, wisdom, charisma,
                         current_mana=intelligence * 7, health=constitution * 8, max_mana=intelligence * 8)

        # initialize mana shield
        self.mana_shield_active = False
        self.shield_duration = 0
        self.mana_shield_max_health = wisdom * 2
        self.mana_shield_current_health = self.mana_shield_max_health

    def level_up(self):  # every two levels dex increase by 1 to add slightly more dex to wiz
        # superimposed function
        super().level_up()

        # addition functionality
        self.wisdom += 2
        self.intelligence += 2
        self.dexterity += 1 if self.level % 2 == 0 else None

    def mana_shield(self):
        if self.current_mana >= 10:
            self.mana_shield_max_health = self.wisdom * 2
            self.mana_shield_active = True
            self.shield_duration = 3
            self.mana_shield_current_health = self.mana_shield_max_health
            self.current_mana -= 10
            print(f"Mana shield is active! Remaining mana: {self.current_mana}")
        else:
            print(f"Not enough mana! Current mana: {self.current_mana}")

    def receive_damage(self, enemy):
        damage_taken = max(enemy.attack - (self.constitution * 0.5), 1)  # reduce dmg by const factor and min dmg
        if self.mana_shield_active:
            if self.mana_shield_current_health <= damage_taken:
                over_damage = abs(self.mana_shield_current_health - damage_taken)
                self.mana_shield_active = False
                self.mana_shield_current_health = 0
                self.health -= over_damage
            else:
                self.mana_shield_current_health -= damage_taken
                print("Mana shield hit!")
                return 0
            # dec the shield duration by 1 on each attack
            self.shield_duration -= 1
            if self.shield_duration <= 0:
                self.mana_shield_active = False  # Shield expires after 3 attacks
                print(f"{self.name}'s mana shield has expired!")
                return damage_taken
        else:
            return damage_taken

    def attack_enemy(self):

        damage_dealt = max(self.strength * 2, 1)  # min dmg                                       #changed one to base value
        final_damage = int(damage_dealt * min(2.5, max(1.2, (self.dexterity * 0.5))) if random.randint(0,
         100) <= self.dexterity * 1 else damage_dealt)  # int value -- crit rate if crit chance determined by dexterity
        return final_damage


