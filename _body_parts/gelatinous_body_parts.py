from body_parts import  BodyParts


class GelatinousBodyParts(BodyParts):
    def __init__(self, ):
        super().__init__()


        self.parts = {
            "membrane": {"armor": None, "health": 100, "alive": True, "status1": None, "status2": None, "status3": None,
                 "status4": None, "status5": None},
            "core": {"armor": None, "health": 100, "alive": True, "status1": None, "status2": None, "status3": None,
                 "status4": None, "status5": None},
            "pseudopods": {"armor": None, "health": 100, "alive": True, "status1": None, "status2": None, "status3": None,
                 "status4": None, "status5": None},
        }


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