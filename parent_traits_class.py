
"""
* traits should determine how something should react
* eg, a aggressive trait should make somoene angry when they lose in a fight
* while a more passive trait might make them more fearful
* furthermore, traits should be able to be added and removed from entities
* to consider mature-ness into play, some traits can be grown out while others stay.
"""


class Traits:
    def __init__(self, inputs, name, description, current_level, max_level):
        self.inputs = inputs
        self.name = name
        self.description = description
        self.current_level = current_level
        self.max_level = max_level
        self.emotions_dict = {}

    def __str__(self):
        return f"{self.name}: {self.description}"

