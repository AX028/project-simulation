from _armor.armor import Gorget

class IronGorget(Gorget):
    def __init__(self):
        super().__init__(name="Iron Gorget", current_durability=95, max_durability=95, defense_type="plate",
                         defense=3, rarity="common", reforge="normal")

    damage_type_altercation = {
        "transformable_damage_types": [],
        "effective": ["bludgeoning", "piercing"],
        "mediocre": ["slashing"],
        "ineffective": ["slashing"],
        "transformed_damage_type": "slashing"
    }

    def take_damage(self, damage, damage_type):
        if damage_type in self.damage_type_altercation['transformable_damage_types']:
            damage_type = self.damage_type_altercation['transformed_damage_type']  # transforms damage-type
            damage -= max(self.defense * max((2 + (1 - self.rarities[self.rarity])), 0), 0)  # reduces damage
            return damage, damage_type

        elif damage_type in self.damage_type_altercation['effective']:
            damage -= max(self.defense * max((2 + (1.2 - self.rarities[self.rarity])), 0), 0)  # reduces damage
            return damage, damage_type

        elif damage_type in self.damage_type_altercation['mediocre']:
            damage -= max(self.defense * max((2 + (1.4 - self.rarities[self.rarity])), 0), 0)  # reduces damage
            return damage, damage_type
            # Handling ineffective damage types (slashing, chainmail barely protects)
        elif damage_type in self.damage_type_altercation['ineffective']:
            damage -= max(self.defense * max((2 + (1.7 - self.rarities[self.rarity])), 0), 0)  # reduces damage
            return damage, damage_type
        else:
            return max(damage - 1, 0), damage_type


class ChainmailGorget(Gorget):
    def __init__(self):
        super().__init__(name="Chainmail Gorget", current_durability=75, max_durability=75, defense_type="chainmail",
                         defense=3, rarity="poor", reforge="normal")

    damage_type_altercation = {
        "transformable_damage_types": [],
        "effective": ["slashing", ""],
        "mediocre": [""],
        "ineffective": ["bludgeoning", "piercing"],
        "transformed_damage_type": "slashing"
    }

    def take_damage(self, damage, damage_type):
        if damage_type in self.damage_type_altercation['transformable_damage_types']:
            damage_type = self.damage_type_altercation['transformed_damage_type']  # transforms damage-type
            damage -= max(self.defense * max((2 + (1 - self.rarities[self.rarity])), 0), 0)  # reduces damage
            return damage, damage_type

        elif damage_type in self.damage_type_altercation['effective']:
            damage -= max(self.defense * max((2 + (1.2 - self.rarities[self.rarity])), 0), 0)  # reduces damage
            return damage, damage_type

        elif damage_type in self.damage_type_altercation['mediocre']:
            damage -= max(self.defense * max((2 + (1.4 - self.rarities[self.rarity])), 0), 0)  # reduces damage
            return damage, damage_type
            # Handling ineffective damage types (slashing, chainmail barely protects)
        elif damage_type in self.damage_type_altercation['ineffective']:
            damage -= max(self.defense * max((2 + (1.7 - self.rarities[self.rarity])), 0), 0)  # reduces damage
            return damage, damage_type
        else:
            return max(damage - 1, 0), damage_type
