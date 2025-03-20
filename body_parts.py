class BodyParts:
    def __init__(self, ):
        """"""

        """Initialize body parts with health and empty status effects."""
        self.parts = {
            "head": {"armor": None, "health": 100, "alive": True, "attached": True, "status1": None, "status2": None, "status3": None, "status4": None, "status5": None},
            "arms": {"armor": None, "health": 100, "alive": True,"attached": True, "status1": None, "status2": None, "status3": None, "status4": None, "status5": None},
            "legs": {"armor": None, "health": 100, "alive": True,"attached": True, "status1": None, "status2": None, "status3": None, "status4": None, "status5": None},
            "torso": {"armor": None, "health": 100,"alive": True, "attached": True, "status1": None, "status2": None, "status3": None, "status4": None, "status5": None},
            "hands": {"armor": None, "health": 100,"alive": True, "attached": True, "status1": None, "status2": None, "status3": None, "status4": None, "status5": None},
            "feet": {"armor": None, "health": 100, "alive": True,"attached": True, "status1": None, "status2": None, "status3": None, "status4": None, "status5": None},
            "eyes": {"armor": None, "health": 100, "alive": True,"attached": True, "status1": None, "status2": None, "status3": None, "status4": None, "status5": None},
            "shoulders": {"armor": None, "health": 100, "alive": True,"attached": True, "status1": None, "status2": None, "status3": None, "status4": None, "status5": None},
            "neck": {"armor": None, "health": 100, "alive": True,"attached": True, "status1": None, "status2": None, "status3": None, "status4": None, "status5": None},
            "back": {"armor": None, "health": 100, "alive": True,"attached": True, "status1": None, "status2": None, "status3": None, "status4": None, "status5": None},

        }

    def handling_effects(self, damage):
        previous_damage = damage
        for body_part in self.parts:
            for key, value in self.parts[body_part].items():
                if key in ["status1", "status2", "status3", "status4", "status5"] and value is not None:
                    # ! print(f"Applying {value} on {body_part} ({key})")
                    damage = value.apply_effect(damage)

        return [damage, damage - previous_damage]

    def taking_damage(self, body_part, damage):
        if body_part in self.parts:
            self.parts[body_part]["health"] -= damage
            print(f"{body_part} took {damage} damage. Health now: {self.parts[body_part]['health']}")
        else:
            print(f"Error: {body_part} is not a valid body part.")

    def adding_modifiers(self, body_part, modifier):
        try:
            body_part_data = self.parts[body_part]
            for key, value in body_part_data.items(): #loops through the dict and applies modifier to first available slot
                if key != "armor" and value is None:
                    body_part_data[key] = modifier
        except KeyError:  # body part not found
            print(f"Error: {body_part} is not a valid body part.")
        except Exception as e:  # other  exceptions
            print(f"Unexpected error: {str(e)}")

    def get_intimidation(self):
        intimidation = 0
        for body_part in self.parts:
            for key, value in self.parts[body_part].items():
                if key == "armor":
                    intimidation += value.intimidation
        return intimidation

    def get_severity(self):
        severity = 0
        for body_part in self.parts:
            for key, value in self.parts[body_part].items():
                if key in ["status1", "status2", "status3", "status4", "status5"] and value is not None:
                    severity += value.severity  # adds severity to total counter by first seeing if its a status effect
        return severity  # visible severity, really only used for AI input rn


#child class here just cause
class HumanoidBodyParts(BodyParts):
    def __init__(self):
        super().__init__()


