import numpy as np
from _ai.event_memories import Memory
from _ai.DQN import DQN
import torch  #pytorch, used to train and build networks
import torch.nn as nn  #nn stands for neural networks, module for classes
import torch.optim as optim     #optimization algorithms
import random
from collections import deque   #efficiently manage memory, specifically replay
from _emotions.traits import Aggressive
from _emotions.negative_emotions import Anger
from _emotions.parent_emotions_class import Emotions
"""asd"""

class AI:
    def __init__(self, character, other_entities, inputs, epsilon,
                 intimidation_weight, state_weight, other_weight,
                 self_severity_weight, self_intimidation_weight, self_state_weight,
                  state_size, hidden_size, action_size, traits, learning_rate=0.001):

        self.traits = traits # * supposed to get a list of traits character has
        self.character = character
        self.other_entities = other_entities
        self.inputs = inputs # ! Look and code and fix this
        self.epsilon = epsilon
        self.intimidation_weight = intimidation_weight
        self.state_weight = state_weight
        self.other_weight = other_weight
        self.self_severity_weight = self_severity_weight
        self.self_intimidation_weight = self_intimidation_weight
        self.self_state_weight = self_state_weight

        self.q_table = {}
        self.memories = []
        self.inputs = {} # ? Which one is right?



        #deep learning things
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu") #checks for GPU otherwise defaults to CPU
        self.dqn = DQN(state_size, hidden_size, action_size).to(self.device) #mvoes DQN model to device
        self.optimizer = optim.Adam(self.dqn.parameters(), lr=learning_rate) #ADAM optimizer for weights
        self.criterion = nn.MSELoss() #MSELoss used to compute error in training

        #memory efficiency/memories
        self.memory = deque(maxlen=10000) #when memory exceeds this limit it will be forgotten
        self.memory_list = []


    def store_memory(self, event_type, value, bias):
        new_memory = Memory(event_type, value, bias)
        self.memory_list.append(new_memory) #creates and stores info based on events


    def adjust_behavior_based_on_memory(self):
        #using memories
        for memory in self.memory_list:
            bias_effect = memory.bias * memory.calculate_bias_effect()
            weight = memory.adjust_weight()

        # * implement code here later in order to modify AI behavior



    # more information if they have been previously exposed
    # or if information has been told to them



    def get_state_vector(self):  # ! This code be too simple consider changing it refer to __init__ for more details (1)
        #converts AI state into numerical tensor and moves it to device
        state_vector = []

        for entity in self.other_entities:
            state_vector.extend([
                entity.intimidation,
                entity.body_parts.get_severity()
            ])

        state_vector.extend([
            self.character.body_parts.get_intimidation(),
            self.character.body_parts.get_severity(),
            self.character.health # ! CHANGE THIS LATER

        ])

        return torch.tensor(state_vector, dtype=torch.float32).to(self.device)

    def choose_action(self, action_size):
        # ? chooses action based on epsilon greedy algorithm
        if random.random() > self.epsilon:
            return random.choice(range(action_size))  #exploration

        state_vector = self.get_state_vector().unsqueeze(0)
        q_values = self.dqn(state_vector)

        return torch.argmax(q_values).item()

    def store_experience(self, state, action, reward, next_state, done):
        #stores a transition in memories
        self.memory.append((state, action, reward, next_state, done))

    def train(self, batch_size, gamma=0.99):
        #training DQN using experience replaying

        if len(self.memory) < batch_size:
            return # ! NO SAMPLES YET CHANGE THIS LATER

        #randomly sample from a batch of experiences
        batch = random.sample(self.memory, batch_size)

        states, actions, rewards, next_states, dones = zip(*batch)

        states = torch.stack(states).to(self.device)
        next_states = torch.stack(next_states).to(self.device)
        actions = torch.tensor(actions).to(self.device)
        rewards = torch.tensor(rewards, dtype=torch.float32).to(self.device)
        dones = torch.tensor(dones, dtype=torch.float32).to(self.device)

        #compute q values for current state
        q_values = self.dqn(states).gather(1, actions.unsqueeze(1)).squeeze(1)

        #compute target q-values
        next_q_values = self.dqn(next_states).max(1)[0]
        target_q_values = rewards + gamma * next_q_values * (1 - dones)

        # computing the loss update networks
        loss = self.criterion(q_values, target_q_values.detach()) #preventing gradient degradation
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()


    def step(self, action_size, reward, done):
        # uses all the functions, action, store experience, trains

        state = self.get_state_vector() #getting state
        action = self.choose_action(action_size) #choosing an action
        next_state = self.get_state_vector() # ! YOU MAY NEED A FUNCTION TO UPDATE THIS
        self.store_experience(state, action, reward, next_state, done) #stores the experience
        self.train(batch_size=32) #trains the DQN

        return action





    # it only considers entity inputs. Add more
    def get_inputs(self, other_entities):  # we could alter this dictionary to include weight. nested dict

        # * This gets other entities inputs
        for entity in other_entities:
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

    def calculate_weight(self):
        """Applies weighted decision-making based on inputs and emotions."""

        input_values = []
        weights = []

        # inputs fromall other entites
        for entity in self.inputs:
            if entity == self.character:
                continue #skips self

            data = self.inputs[entity]
            input_values.extend([
                data.get("intimidation", 0),
                data.get("state", 0)
            ])
            weights.extend([
                self.intimidation_weight,
                self.state_weight
            ])

        #inputs from self
        self_data = self.inputs.get(self.character, {})
        input_values.extend([
            self_data.get("intimidation", 0),
            self_data.get("state", 0),
            self_data.get("severity", 0)
        ])
        weights.extend([
            self.self_intimidation_weight,
            self.self_state_weight,
            self.self_severity_weight
        ])


        input_values = np.array(input_values)
        weights = np.array(weights)

        weighted_values = input_values * weights
        weight_sum = sum(emotion.get_bias() for emotion in self.emotion) # ! FIX THIS TO USE TRAITS

        return weight_sum + weighted_values.sum()

    def add_memory(self, event_type, value, bias):

        new_memory = Memory(event_type, value, bias)
        self.memories.append(new_memory)

    def adjust_weights(self, new_weights):
        # weights of the ai
        self.intimidation_weight = new_weights.get('intimidation_weight', self.intimidation_weight)
        self.state_weight = new_weights.get('state_weight', self.state_weight)
        self.self_severity_weight = new_weights.get('self_severity_weight', self.self_severity_weight)
        self.self_intimidation_weight = new_weights.get('self_intimidation_weight', self.self_intimidation_weight)
        self.self_state_weight = new_weights.get('self_state_weight', self.self_state_weight)
        self.other_weight = new_weights.get('other_weight', self.other_weight)




# ai = AI(None, None, None, 0.1, 0.1
#         , 0.1, 0.1, 0.1, 0.1
#         , 0.1, 10, 10, 10, [Aggressive()])
#
#
# trait = ai.traits
# print(trait[0])

# * IT WORKS !!!