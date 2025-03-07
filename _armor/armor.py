# Base Armor class
class Armor:
    def __init__(self, name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type,
                 intimidation):
        self.name = name
        self.current_durability = current_durability
        self.max_durability = max_durability
        self.defense_type = defense_type
        self.defense = defense
        self.rarity = rarity
        self.reforge = reforge
        self.armor_type = armor_type
        self.intimidation = intimidation
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


#INTERMEDIATE CLASSES
# Hands Armor (Gloves)
class Gloves(Armor):
    def __init__(self, name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type="Gloves"):
        super().__init__(name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type)


# Lower Body Armor (Leggings)
class Leggings(Armor):
    def __init__(self, name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type = "Leggings"):
        super().__init__(name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type)


# Feet Armor (Boots)
class Boots(Armor):
    def __init__(self, name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type = "Boots"):
        super().__init__(name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type)


# Head Armor (Helmet)
class Helmet(Armor):
    def __init__(self, name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type = "Helmet"):
        super().__init__(name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type)


# Eyes Armor (Eyewear)
class Eyewear(Armor):
    def __init__(self, name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type = "Eyewear"):
        super().__init__(name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type)


# Neck Armor (Gorget)
class Gorget(Armor):
    def __init__(self, name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type = "Gorget"):
        super().__init__(name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type)


# Chest Armor (Shoulder Pads)
class ShoulderPads(Armor):
    def __init__(self, name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type = "Shoulder Pads"):
        super().__init__(name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type)


# Torso Armor (Cuirass)
class Cuirass(Armor):
    def __init__(self, name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type = "Cuirass"):
        super().__init__(name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type)


# Back Armor (Backplate)
class Backplate(Armor):
    def __init__(self, name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type = "Backplate"):
        super().__init__(name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type)


# Arm Armor (Bracers)
class Bracers(Armor):
    def __init__(self, name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type = "Bracers"):
        super().__init__(name, current_durability, max_durability, defense_type, defense, rarity, reforge, armor_type)
