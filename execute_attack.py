from _status_effects.damage_status_effects import *
from _weapons.child_class_weapons import *
from _characters.rogue import *


#takes into consideration
"""
Characters damage method
Weapons damage method
"""

# ATTACK CLASS METHOD
class AttackExecutor:
    @staticmethod
    def execute_attack(character, weapon):
        # Step 1: Calculate damage using the character's attack method
        damage = character.attack_enemy()  # character damage output
        if damage is None:
            print("Error: Character's attack did not return valid damage")
            return

        print(f"Initial damage: {damage}")

        """IMPORTANT THE ERROR IS HERE, WEAPON DOES NOT RETURN DAMAGE PROPERLY"""
        damage = weapon.use(damage)  # weapon damage output
        if damage is None:
            print("Error: Weapon returned invalid damage")
            return

        damage, damage_type = damage
        print(f"Weapon damage: {damage}, damage_type: {damage_type}")

        print(f"Final damage after effect: {damage}")

        return damage, damage_type


# Creating objects for the necessary components
my_weapon = Sword()  # change this
bleed_effect = Bleed()  # we need a lot of these
rogue_character = Rogue(name="test", strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10)
AttackExecutor.execute_attack(rogue_character, my_weapon)
