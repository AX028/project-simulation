#_weapons
""""""
"""WEAPONS NEEDED"""
"""
BONE SWORD
SHORT SWORD
DAGGER
BOW
STAFF
"""

#BALANCE CHANGES
"""child_class_waepons / 25
changed broken sword use from 0.2 -> 0.5
"""



#ill need to add damage types to this
"""
Include the damage properties like sharp, pierce, stab etc in the parent _weapons class
then in the child classes, I will interpret the damage and only call on one of the methods
to only include the base damage type. 
"""

"""
damage types:

Stabbing damage
    Bleeding:lose health over time
    Infection:weakens health regen (maybe more if it isnt treated?)
    Wounded:reduces movement speed
    
Piercing damage
    Armor pen: reduces _armor effectiveness
    Staggared: Reduce ability to perform actions effectively
    
Slashing damage
    Bleeding:
    Weakened defense:
    Body specific? : legs can decrease movement, arms can decrease physical damage, neck can cause more dmg etc. 

Bludgeoning damage
    Bleeding:
    Weakened defense:
    Body part specific


#status effect
Internal Bleeding: Causes hidden damage over time
    Broken Bones: Severely reduces movement or limb effectiveness
    Winded: Temporary stamina loss and slowed recovery
    Piercing Damage (expanding on _armor pen concepts)

Deep Wound: Harder to heal, persists longer
    Punctured Organ: Causes internal bleeding and health degeneration
    Weak Spot Hit: Bypasses _armor and deals increased damage
    Slashing Damage (additional effects)

Severed: Can outright disable a limb if damage is extreme
    Tendon Cut: Reduces movement or attack speed drastically
    Exposed Flesh: Reduces natural _armor/protection in the area
    Penetrating Damage (specific to projectiles, high-speed impacts)

piercing trust : Can hit multiple targets or damage exit wounds
    Lodged Projectile: Increases pain, risk of infection if not removed
    Vital Strike: Higher chance of one-hit lethal damage if vital organs are hit
    Elemental & Special Damage Types
    Acid Damage

Poison damage:
    Adds poison status effect (DOT)
    Lessen your accuracy
    Less stamina
    Poison specific (some do more damage some debuff more)
    
Fire damage:
    Adds fire status effect (DOT)
    """


