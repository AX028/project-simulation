from _status_effects.damage_status_effects import * #imports all damage status effects
# from _status_effects.debuff_status_effect import PhysicalWeakness
# ! I commented the line above out bc of warning u can undo the change
""""""
#the format should go like:
#damage_type : {1 : status_effect, 2 : status_effect}




damage_types = {
    "slash": {
        1: Bleed(),
    },
    # "crush": {
    #     1: PhysicalWeakness(),
    #     2: InternalBleed(),
    #     3: ArmorPenetration(),
    # },
    # "pierce": {
    #     1: ArmorPenetration(),
    #     2: Bleed(),
    #     3: InternalBleed(),
    #     4: Disorientation(),
    # },
    # "acid": {
    #     1: Bleed(),
    #     2: PhysicalWeakness(),
    #     3: Corrosion(),
    # },
    # "fire": {
    #     1: Burn(),
    #     2: PhysicalWeakness(),
    #     3: ArmorPenetration(),
    # },
    # "electric": {
    #     1: Shock(),
    #     2: Paralysis(),
    #     3: InternalBurn(),
    # },
    # "frost": {
    #     1: Freeze(),
    #     2: Slowness(),
    #     3: ArmorPenetration(),
    # },
    # "poison": {
    #     1: Poisoned(),
    #     2: Slowness()
    # },
}


