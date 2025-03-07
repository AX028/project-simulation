
#This should tie to the characters class eventually
""""""
"""
Eventually should check armor to see if they give extra capacity 

Unlike the name suggests, this isn't just the inventory system, this will also
be the stamina system dealing with overweight and stuff. better name?
"""

class CarryEquipment:
    def __init__(self, max_weight, max_stamina, character, body_type, storage_slots=10):
        self.current_weight = 0
        self.max_weight = max_weight
        self.current_stamina = max_stamina
        self.max_stamina = max_stamina
        self.inventory = {

            #EXAMPLE
            """
            "itemName" : {
                "item_quantity" : 1
                "item_id" : 129083
                "item_weight" : 10
                "stackable" : True
            }
            
            """

        }  # Dictionary to store items with quantities
        self.character = character
        self.body_type = body_type
        self.storage_slots = storage_slots

    def add_item(self, item, quantity=1):
        weight = item.weight
        total_weight = weight * quantity
        if self.current_weight + weight > self.max_weight:
            return f" Cannot add{quantity} {item} to inventory. Overweight."
        if len(self.inventory) >= self.storage_slots and item not in self.inventory:
            return f"No available slots for {item}."

        self.inventory[item] = self.inventory[item]["item_quantity"] + quantity
        self.current_weight += total_weight



    def retrieve_item(self, item, quantity_retrieved = 1):
        if item in self.inventory:
            if self.inventory[item] <= quantity_retrieved: #if item is wanted is greater than the amount has
                self.inventory[item] -= quantity_retrieved
                self.current_weight -= item.weight * quantity_retrieved
                return f"Removed {quantity_retrieved} {item}(s) from inventory."
            elif self.inventory[item] > quantity_retrieved:
                quantity_retrieved = self.inventory[item] #this gets all that is available
                self.inventory[item] = 0
                self.current_weight -= item.weight * quantity_retrieved
                return f"Retrieved all {quantity_retrieved} {item}(s) from inventory."
        return f"{item} not found in inventory."


class CharacterCarryEquipment(CarryEquipment):
    def __init__(self, current_weight, max_weight, current_stamina, max_stamina, character):
        super().__init__(current_weight, max_weight, current_stamina, max_stamina)

        self.character = character

    armor_matching = {
        "Helmet" : "head",
        "Gloves" : "arms",
        "Leggings" : "legs",
        "Boots" : "feet",
        "ShoulderPads" : "shoulders",
        "Eyewear" : "eyes",
        "Gorget" : "neck",
        "Bracers" : "arms",
        "Backplate" : "back",
        "Cuirass" : "chest"
    }

    def equip_armor(self, armor):
        armor_slot = self.character.body_type.parts[ self.armor_matching[armor.armor_type] ]["armor"]
        if armor_slot is None:
            self.character.body_type.parts[self.armor_matching[armor.armor_type]]["armor"] = armor
            return f"Equipped armor: {armor}"
        elif armor_slot is not None:
            super().add_item(armor_slot, 1)
            self.character.body_type.parts[self.armor_matching[armor.armor_type]]["armor"] = armor
            return f"Replaced old armor with: {armor}"



