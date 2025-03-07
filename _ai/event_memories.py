from abc import abstractmethod


class Memory:
    def __init__(self, event_type, value, bias):
        self.event_type = event_type  #type of memory
        self.value = value  # value associated with the memory
        self.bias = bias  # bias from the memory

    @abstractmethod
    def calculate_bias_effect(self):
        #   modify the value based on the event type and bias
        modified_value = self.value  # base value

        if self.event_type == "fight":
            modified_value *= self.bias * 1.5
        elif self.event_type == "conversation":
            modified_value *= self.bias * 1.1
        elif self.event_type == "training":
            modified_value *= self.bias * 1.2
        elif self.event_type == "exploration":
            modified_value *= self.bias * 1.2
        elif self.event_type == "achievement":
            modified_value *= self.bias * 1.5
        else:
            modified_value *= self.bias

        return modified_value

    @abstractmethod
    def adjust_weight(self):
        #adjust the AI's weight based on memories
        if self.event_type == "fight":
            weight = 0.1
        elif self.event_type == "conversation":
            weight = 0.05
        elif self.event_type == "training":
            weight = 0.1
        elif self.event_type == "exploration":
            weight = 0.05
        elif self.event_type == "achievement":
            weight = 0.2
        else:
            weight = 0.05
        return weight

    def get_bias(self):
        return self.bias

