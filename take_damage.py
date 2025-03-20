from _weapons.damage_types import damage_types as damage_types_dictionary
from _logic.inventory_system import *
from _characters.rogue import *
from _body_parts.body_parts import *
from _armor.leggings import *
import ssl
print(ssl.OPENSSL_VERSION)

armor_001 = ChainmailLeggings()
player_body_parts = HumanoidBodyParts()
player = Rogue(10, 10, 10, 10, 10, 10, 10)
character_inventory = CharacterCarryEquipment(0, 10, 10, 10, player)
character_inventory.equip_armor(armor_001)


class TakeDamage:

    @staticmethod
    def take_damage(character, damage, damage_type, part_of_body):



        # using armor first because it is the first thing weapon should hit

        # Takes characters receive_damage method
        try:
            damage_taken = character.receive_damage(damage)
        except AttributeError as e:
            print(f"Error {e}: {character} does not have a 'receive_damage' method.")
            return
        except Exception as e:
            # Catch any other unexpected exceptions
            print(f"Unexpected error: {e}")
            return

        #calculating the status effects from damage_types_dictionary
        #slash
        for effect in damage_types_dictionary[damage_type].values():  # This ensures effect is Bleed()
            character.body_type.adding_modifiers(part_of_body, effect) # sets the effect equal to bleed but doesn't apply it



        # #body part methods
        damage_taken += character.body_type.handling_effects(damage_taken)[0]
        character.body_type.taking_damage(part_of_body, damage_taken)
        print(f"Total Damage Taken: {damage_taken}")


TakeDamage.take_damage(player, 10, "slash", "legs")
TakeDamage.take_damage(player, 10, "slash", "legs")
TakeDamage.take_damage(player, 10, "slash", "legs")
TakeDamage.take_damage(player, 10, "slash", "legs")
print(player.body_type.parts["legs"]["health"])



