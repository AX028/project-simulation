from _armor.armor import Leggings

class ChainmailLeggings(Leggings):
    def __init__(self):
        super().__init__(name="Chainmail Leggings", defense_type="chainmail", current_durability=250,
                         max_durability=250, defense=10, rarity="uncommon", reforge="normal")
        self.damage_type_altercation = {
            "effective": [], #effective in general
            "mediocre": ["bludgeoning"], #somewhat effective and helps
            "ineffective": ["piercing"], #ineffective but still helps
            "transformable_damage_types": ["slashing"], #transformable assumes really effective
            "transformed_damage_type": "bludgeoning"
        }


        # Defense * 1 > ( 2 + (1 - Rarity[dict] (1.4)) )
        #  damage -= max(self.defense * (2 + (1 - self.rarities[self.rarity]), 0)



# *  ---------------------------------------------------

class SteelLeggings(Leggings):
    def __init__(self):
        super().__init__(name="SteelLeggings", defense_type="plate", current_durability=375,
                         max_durability=375, defense=15, rarity="rare", reforge="normal")
        self.damage_type_altercation = {
            "effective": ["bludgeoning"], #effective in general
            "mediocre": ["piercing"], #somewhat effective and helps
            "ineffective": ["slashing"], #ineffective but still helps
            "transformable_damage_types": [], #transformable assumes really effective
            "transformed_damage_type": "bludgeoning"
        }





# *  ---------------------------------------------------

class IronLeggings(Leggings):
    def __init__(self):
        super().__init__(name="Iron Leggings", defense_type="plate", current_durability=self.max_durability,
                         max_durability=215, defense=6, rarity="common", reforge="normal")
        self.damage_type_altercation = {
            "effective": [], #effective in general
            "mediocre": ["slashing", "bludgeoning", "piercing"], #somewhat effective and helps
            "ineffective": [], #ineffective but still helps
            "transformable_damage_types": [], #transformable assumes really effective
            "transformed_damage_type": ""
        }






# *  ---------------------------------------------------


class LeatherLeggings(Leggings):
    def __init__(self):
        super().__init__(name="Leather Leggings", defense_type="leather", current_durability=105,
                         max_durability=105, defense=50, rarity="unique", reforge="normal")
        self.damage_type_altercation = {
            "effective": [], #effective in general
            "mediocre": [], #somewhat effective and helps
            "ineffective": ["slashing", "bludgeoning"], #ineffective but still helps
            "transformable_damage_types": [], #transformable assumes really effective
            "transformed_damage_type": ""
        }




