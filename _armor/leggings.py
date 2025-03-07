from _armor.armor import Leggings

class ChainmailLeggings(Leggings):
    def __init__(self):
        super().__init__(name="Chainmail Leggings", defense_type="chainmail", current_durability=250,
                         max_durability=250, defense=10, rarity="common", reforge="normal")
        self.damage_type_altercation = None
        self.damage_type_altercation = {
            "effective": [], #effective in general
            "mediocre": ["bludgeoning"], #somewhat effective and helps
            "ineffective": ["piercing"], #ineffective but still helps
            "transformable_damage_types": ["slashing"], #transformable assumes really effective
            "transformed_damage_type": "bludgeoning"
        }


        # Defense * 1 > ( 2 + (1 - Rarity[dict] (1.4)) )
        #  damage -= max(self.defense * (2 + (1 - self.rarities[self.rarity]), 0)

    def take_damage(self, damage, damage_type):
        if damage_type in self.damage_type_altercation['transformable_damage_types']:
            damage_type = self.damage_type_altercation['transformed_damage_type'] #transforms damage-type

            damage -= max(self.defense * (2 + (1 - self.rarities[self.rarity]), 0)) #accesses dictionary to reduce dmg
            return damage, damage_type
            #Handling rarities (Distributing the rarities to variable)

        elif damage_type in self.damage_type_altercation['effective']:
            damage -= max(self.defense * (2 + (1.2 - self.rarities[self.rarity]), 0)) # reduces damage based on rarity
            return damage, damage_type
            # Handling mediocre damage types (bludgeoning, chainmail weakens)

        elif damage_type in self.damage_type_altercation['mediocre']:
            damage -= max(self.defense * (2 + (1.4 - self.rarities[self.rarity]), 0))
                          # adjusts damage reduction based on rarity
            return damage, damage_type
            # Handling ineffective damage types (piercing, chainmail barely protects)

        elif damage_type in self.damage_type_altercation['ineffective']:
            damage -= max(self.defense * (2 + (1.7 - self.rarities[self.rarity]), 0))  # reduces impact of piercing based on rarity
            return damage, damage_type

        else:
            return damage - 1, damage_type


#this took so long im about a crash out




