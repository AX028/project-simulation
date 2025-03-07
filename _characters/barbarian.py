from character import Characters
import random
# ! barbarian is made for sustained battles, gaining strength as a battle is going on


class Barbarian(Characters):
    def __init__(self, name, strength, dexterity, constitution, intelligence, wisdom, charisma, rage, frenzy, max_rage=10, max_frenzy=25):
        #note, you cannot have a non-default parameter before a default one in classes.
        super().__init__(name, strength, dexterity, constitution, intelligence, wisdom, charisma, max_mana=intelligence*5, current_mana = 0)

        self.current_mana = intelligence * 5
        self.rage = rage
        self.max_rage = max_rage  #decreases damage taken for each rage stacks
        self.frenzy = frenzy
        self.max_frenzy = max_frenzy  #increases damage dealt for frenzy

    def receive_damage(self, damage): #adds the rage modifier
        damage_taken = max((damage - (self.constitution * 0.5)) * (min(self.rage, self.max_rage) * 0.1), 1)  # reduce dmg by const factor and min dmg
        return max(damage_taken, 1)


    def attack_enemy(self):                                                                      #2.5 multiplier might be too much change this later
        damage_dealt = max((self.strength * 0.5) * (min(self.frenzy, self.max_frenzy)/10 + 1, self.max_frenzy), 1)  # min dmg   and adding frenzy multiplier                                         #modified crit ratio to be much harder
        final_damage = int(damage_dealt * min(2.5, max(1.2, (self.dexterity * 0.5))) if random.randint(0, 100) <= min(self.dexterity * 0.5, 25) else damage_dealt)  # int value -- crit rate if crit chance determined by dexterity
        return final_damage


    def level_up(self): #level up
        super().level_up() #parent function, now change some values.
        self.strength += 2 # increases by 3
        self.constitution += 1 #increase by 2

        print(f"{self.name} leveled up! Now at Level {self.level}")