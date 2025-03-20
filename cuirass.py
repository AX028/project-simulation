from _armor.armor import Cuirass

# *  ---------------------------------------------------
class ChainmailCuirass(Cuirass):
    def __init__(self):
        super().__init__(name="Chainmail Cuirass", defense_type="chainmail", current_durability=130,
                         max_durability=300, defense=15, rarity="uncommon", reforge="normal")
        self.damage_type_altercation = {
            "effective": [],
            "mediocre": ["bludgeoning"],
            "ineffective": ["piercing"],
            "transformable_damage_types": ["slashing"],
            "transformed_damage_type": "bludgeoning"
        }

# *  ---------------------------------------------------

class SteelCuirass(Cuirass):
    def __init__(self):
        super().__init__(name="Steel Cuirass", defense_type="plate", current_durability=200,
                         max_durability=450, defense=30, rarity="rare", reforge="normal")
        self.damage_type_altercation = {
            "effective": ["bludgeoning"],
            "mediocre": ["piercing"],
            "ineffective": ["slashing"],
            "transformable_damage_types": [],
            "transformed_damage_type": "bludgeoning"
        }

# *  ---------------------------------------------------

class IronCuirass(Cuirass):
    def __init__(self):
        super().__init__(name="Iron Cuirass", defense_type="plate", current_durability=75,
                         max_durability=300, defense=20, rarity="common", reforge="normal")
        self.damage_type_altercation = {
            "effective": [],
            "mediocre": ["slashing", "bludgeoning", "piercing"],
            "ineffective": [],
            "transformable_damage_types": [],
            "transformed_damage_type": ""
        }

# *  ---------------------------------------------------

class LeatherCuirass(Cuirass):
    def __init__(self):
        super().__init__(name="Leather Cuirass", defense_type="leather", current_durability=30,
                         max_durability=150, defense=25, rarity="unique", reforge="normal")
        self.damage_type_altercation = {
            "effective": [],
            "mediocre": [],
            "ineffective": ["slashing", "bludgeoning"],
            "transformable_damage_types": [],
            "transformed_damage_type": ""
        }

