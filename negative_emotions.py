from _emotions.parent_emotions_class import Emotions

"""
def __init__(self, name, description, current_level, max_level, bias_per_level):
"""



class Anger(Emotions):
    def __init__(self, name="anger",
                 description="A storm brews in silence, sharp and suffocating.",
                 current_level=0, max_level=10, bias_per_level=0.1, character=None):

        super().__init__(name, description, current_level, max_level, bias_per_level, character=None)

        self.entity_intimidation_change = 1.2 # ? these values change how much this emotion alter the perspective of the inputs of the character
        self.entity_severity_change = 1.2
        self.character = character # ? this should be the AI or the character of the AI whatever makes more sense
        self.inputs = {}

    def alter_anger(self, inputs): # ? The inputs for this should be the same for the AI itself 3/6/2025
        # * This gets other entities inputs
        # * This is different from the characters as in this is more temporary and not permanent, this resets everytime
        self.inputs = {} #resets
        for entity in inputs:
            self.inputs[entity] = {
                "intimidation": entity.intimidation,
                "state": entity.body_parts.get_severity(),
                "other": None
            }

        # * This gets own characters inputs
        self_severity = self.character.body_parts.get_severity()
        health = self.character.health
        self.inputs.update({self.character: {
            "severity": self_severity,
            "state": health,
            "intimidation": self.character.body_parts.get_intimidation(),
        }
        })

        # * determine how angry it is after inputs
        self_severity = self.inputs[self.character]["severity"]
        self_intimidation = self.inputs[self.character]["intimidation"]

        other_total_severity = sum(self.inputs[entity]["severity"] for entity
                                   in self.inputs if entity != self.character)

        other_total_intimidation = sum(self.inputs[entity]["intimidation"] for entity in
                                       self.inputs if entity != self.character)

        # * scenario one, opponents are stronger than itself
        # ! PLEASE BALANCE THIS I forgot the numbers for this so IDK but right now im assuming its from 10-100
        if self_severity > other_total_severity and self_intimidation > other_total_intimidation:
            # * for a certain amount, increase by a level
            while other_total_severity > self_severity:
                self.current_level += 2
                other_total_severity -= 10

        elif (self_severity < other_total_severity and self_intimidation > other_total_intimidation
        ) or (self_severity > other_total_severity and self_intimidation < other_total_intimidation):
            while other_total_severity > self_severity:
                self.current_level += 1
                other_total_severity -= 10


