# Base Armor class
class Armor:
    def __init__(self, name, current_durability, max_durability, defense_type,
                 defense, rarity, reforge, armor_type, intimidation):
        self.name = name
        self.current_durability = current_durability
        self.max_durability = max_durability
        self.defense_type = defense_type
        self.defense = defense
        self.rarity = rarity
        self.reforge = reforge
        self.armor_type = armor_type
        self.intimidation = intimidation
        self.max_defense = self.defense # ? might need to add a reapply defense method

        self.rarities = {
            "poor": 0.7,
            "common": 1,
            "uncommon": 1.2,
            "rare": 1.4,
            "epic": 1.6,
            "legendary": 2,
            "mythic": 2.5,
            "special": 5
        }

    def repair(self):
        self.max_durability -= int(self.max_durability * 0.05)
        self.current_durability = self.max_durability


# INTERMEDIATE CLASSES
# Hands Armor (Gloves)
class Gloves(Armor):
    def __init__(self, name, current_durability, max_durability, defense_type, defense, rarity, reforge,
                 armor_type="Gloves"):
        super().__init__(name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type)


# Lower Body Armor (Leggings)
class Leggings(Armor):
    def __init__(self, name, current_durability, max_durability, defense_type, defense, rarity, reforge,
                 armor_type="Leggings"):
        super().__init__(name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type)

    damage_type_altercation = {} #smash
    def take_damage(self, damage, damage_type):
        if damage_type in self.damage_type_altercation['transformable_damage_types']:
            damage_type = self.damage_type_altercation['transformed_damage_type']  # transforms damage-type

            damage -= max(self.defense * (2 + (1 - self.rarities[self.rarity]), 0))  # accesses dictionary to reduce dmg
            return damage, damage_type
            # Handling rarities (Distributing the rarities to variable)

        elif damage_type in self.damage_type_altercation['effective']:
            damage -= max(self.defense * (2 + (1.2 - self.rarities[self.rarity]), 0))  # reduces damage based on rarity
            return damage, damage_type
            # Handling mediocre damage types (bludgeoning, chainmail weakens)

        elif damage_type in self.damage_type_altercation['mediocre']:
            damage -= max(self.defense * (2 + (1.4 - self.rarities[self.rarity]), 0))
            # adjusts damage reduction based on rarity
            return damage, damage_type
            # Handling ineffective damage types (piercing, chainmail barely protects)

        elif damage_type in self.damage_type_altercation['ineffective']:
            damage -= max(self.defense * (
            2 + (1.7 - self.rarities[self.rarity]), 0))  # reduces impact of piercing based on rarity
            return damage, damage_type

        else:
            return damage - 1, damage_type


# Feet Armor (Boots)
class Boots(Armor):
    def __init__(self, name, current_durability, max_durability, defense_type, defense, rarity, reforge,
                 armor_type="Boots"):
        super().__init__(name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type)


# Head Armor (Helmet)
class Helmet(Armor):
    def __init__(self, name, current_durability, max_durability, defense_type, defense, rarity, reforge,
                 armor_type="Helmet"):
        super().__init__(name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type)


# Eyes Armor (Eyewear)
class Eyewear(Armor):
    def __init__(self, name, current_durability, max_durability, defense_type, defense, rarity, reforge,
                 armor_type="Eyewear"):
        super().__init__(name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type)


# Neck Armor (Gorget)
class Gorget(Armor):
    def __init__(self, name, current_durability, max_durability, defense_type, defense, rarity, reforge,
                 armor_type="Gorget"):
        super().__init__(name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type)


# Chest Armor (Shoulder Pads)
class ShoulderPads(Armor):
    def __init__(self, name, current_durability, max_durability, defense_type, defense, rarity, reforge,
                 armor_type="Shoulder Pads"):
        super().__init__(name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type)


# Torso Armor (Cuirass)
class Cuirass(Armor):
    def __init__(self, name, current_durability, max_durability, defense_type, defense, rarity, reforge,
                 armor_type="Cuirass"):
        super().__init__(name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type)


# Back Armor (Backplate)
class Backplate(Armor):
    def __init__(self, name, current_durability, max_durability, defense_type, defense, rarity, reforge,
                 armor_type="Backplate"):
        super().__init__(name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type)


# Arm Armor (Bracers)
class Bracers(Armor):
    def __init__(self, name, current_durability, max_durability, defense_type, defense, rarity, reforge,
                 armor_type="Bracers"):
        super().__init__(name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type)
