# parent class emotions

"""
* making emotions scalable based on surrounding env and others intimidation.
*
*
"""


class Emotions:
    def __init__(self, name, description, current_level, max_level, bias_per_level, character=None):
        self.name = name
        self.description = description
        self.current_level = current_level
        self.max_level = max_level
        self.bias_per_level = bias_per_level
        self.character = character

    def __str__(self):
        return f"{self.name}: {self.description}"

    def get_bias(self):
        return self.bias_per_level * self.current_level

