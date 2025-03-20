from _emotions.parent_traits_class import Traits
from _emotions.negative_emotions import *

class Aggressive(Traits):
    def __init__(self, inputs=None, name="Aggressive", description="A vehement and impassioned nature lies dormant.",
                 current_level=0, max_level=10):
        super().__init__(inputs, name, description, current_level, max_level)

        # ? Making this a list for now
        self.emotions_dict = [
            Anger()
        ]


