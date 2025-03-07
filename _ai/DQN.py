import torch  #pytorch, used to train and build networks
import torch.nn as nn  #nn stands for neural networks, module for classes
import torch.optim as optim     #optimization algorithms
import random
from collections import deque   #efficiently manage memory, specifically replay

class DQN(nn.Module): #enherits from the nn module
    def __init__(self, state_size, action_size, hidden_size=64):
    # * DQN deep q network
    # * :param state_size: # of features in the state representation (input neurons)
    # * :param action_size: # of possible actions (output neurons)
    # * :param hidden_size: # of neurons in the hidden layers
        super(DQN, self).__init__()

        # * different layers we have 3 rn

        #first input layer
        self.fc1 = nn.Linear(state_size, hidden_size)

        #extracting deeper patterns
        self.fc2 = nn.Linear(hidden_size, hidden_size)

        #q layer prediction for actions
        self.fc3 = nn.Linear(hidden_size, action_size)

    def forward(self, state):
        x = torch.relu(self.fc1(state))
        x = torch.relu(self.fc2(x))
        return self.fc3(x)  # final activation layer


