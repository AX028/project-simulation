import json
import os
import torch
from datasets import Dataset, Sequence, Value
from transformers import (
    DistilBertConfig,
    DistilBertTokenizer,
    DistilBertForSequenceClassification,
    Trainer,
    TrainingArguments,
    pipeline
)
from sklearn.model_selection import train_test_split

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# 1) Define multi-intent label space
intent_to_label = {
    "ask_for_directions": 0,
    "ask_about_quests": 1,
    "greet": 2,
    "shop": 3,
    "ask_for_help": 4,
    "say_goodbye": 5,
    "thank": 6,
    "apologize": 7,
    "introduce_self": 8,
    "ask_about_weather": 9,
    "ask_about_location": 10,
    "ask_about_npc": 11,
    "ask_about_story": 12,
    "ask_about_rules": 13,
    "compliment": 14,
    "insult": 15,
    "express_confusion": 16,
    "express_surprise": 17,
    "express_happiness": 18,
    "express_sadness": 19,
    "express_anger": 20,
    "negotiate": 21,
    "joke": 22,
    "flirt": 23,
    "talk_about_past": 24,
    "talk_about_future": 25,
    "talk_about_family": 26,
    "talk_about_hobbies": 27,
    "talk_about_food": 28,
    "talk_about_travel": 29,
    "talk_about_work": 30,
    "talk_about_friends": 31,
    "talk_about_music": 32,
    "talk_about_books": 33,
    "talk_about_magic": 34,
    "talk_about_combat": 35,
    "talk_about_training": 36,
    "talk_about_politics": 37,
    "talk_about_history": 38,
    "talk_about_rumors": 39,
    "give_advice": 40,
    "ask_for_advice": 41,
    "ask_for_favor": 42,
    "offer_help": 43,
    "incoherent": 44,
    "ask_for_name": 45,
    "ask_for_age": 46,
    "ask_for_gender": 47,
    "ask_for_job": 48,
    "ask_for_hometown": 49,
    "ask_about_race": 50,
    "ask_about_class": 51,
    "discuss_battle_strategy": 52,
    "discuss_item_usage": 53,
    "discuss_weapon_choice": 54,
    "ask_about_armor": 55,
    "talk_about_pet": 56,
    "talk_about_allies": 57,
    "talk_about_enemies": 58,
    "talk_about_dungeon": 59,
    "talk_about_villages": 60,
    "talk_about_world": 61,
    "request_quest": 62,
    "accept_quest": 63,
    "complete_quest": 64,
    "report_progress": 65,
    "express_disappointment": 66,
    "express_joy": 67,
    "complain": 68,
    "offer_trade": 69,
    "decline_trade": 70,
    "ask_for_reward": 71,
    "accept_reward": 72,
    "recruit_for_party": 73,
    "refuse_party_invite": 74,
    "examine_item": 75,
    "ask_for_spell": 76,
    "cast_spell": 77,
    "ask_for_mana": 78,
    "talk_about_tavern": 79,
    "gather_resources": 80,
    "forge_item": 81,
    "use_healing_potion": 82,
    "ask_for_food": 83,
    "find_merchant": 84,
    "ask_for_training": 85,
    "respond_to_threat": 86,
    "discuss_skills": 87,
    "discuss_class_upgrades": 88,
    "talk_about_reputation": 89,
    "complain_about_enemy": 90,
    "respond_to_challenge": 91,
    "talk_about_tactics": 92,
    "ask_for_travel_guide": 93,
    "ask_for_navigation": 94,
    # Additional
    "express_fear": 95,
    "express_regret": 96,
    "express_excitement": 97,
    "ask_about_feelings": 98,
    "talk_about_culture": 99,
    "talk_about_technology": 100,
    "roleplay_action": 101,
    "request_clarification": 102
}
num_labels = len(intent_to_label)

# 2) Load your multi-intent JSON data
with open('training_data/training_data_10000_xx4.json', 'r') as f:
    data = json.load(f)

# 3) Convert list-of-intents to multi-hot
def encode_multi_hot(intents):
    v = [0]*num_labels
    for i in intents:
        if i in intent_to_label:
            idx = intent_to_label[i]
            v[idx] = 1
    return v

dataset_dict = {"text": [], "labels": []}
for item in data:
    dataset_dict["text"].append(item["text"])
    dataset_dict["labels"].append(encode_multi_hot(item["intents"]))

dataset = Dataset.from_dict(dataset_dict)

# 4) Split train/test
split_dataset = dataset.train_test_split(test_size=0.2)
train_dataset = split_dataset["train"]
eval_dataset = split_dataset["test"]

# 5) Tokenization
tokenizer = DistilBertTokenizer.from_pretrained("distilbert-base-uncased")

def tokenize_function(examples):
    enc = tokenizer(
        examples["text"],
        truncation=True,
        padding="max_length",
        max_length=512
    )
    # Keep 'labels' as-is for now (int list)
    enc["labels"] = examples["labels"]
    return enc

train_dataset = train_dataset.map(tokenize_function, batched=True)
eval_dataset = eval_dataset.map(tokenize_function, batched=True)

# 6) Force 'labels' to float with cast_column + set_format
train_dataset = train_dataset.cast_column("labels", Sequence(Value("float32")))
eval_dataset = eval_dataset.cast_column("labels", Sequence(Value("float32")))

train_dataset.set_format(type="torch", columns=["input_ids", "attention_mask", "labels"])
eval_dataset.set_format(type="torch", columns=["input_ids", "attention_mask", "labels"])

# 7) Configure DistilBERT for multi-label classification
config = DistilBertConfig.from_pretrained(
    "distilbert-base-uncased",
    num_labels=num_labels,
    problem_type="multi_label_classification"
)

model = DistilBertForSequenceClassification.from_pretrained(
    "distilbert-base-uncased",
    config=config
)

# 8) Trainer setup
training_args = TrainingArguments(
    output_dir="./results_multi_intent",
    evaluation_strategy="epoch",  # Evaluate each epoch
    logging_dir="./logs",
    logging_steps=50,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    num_train_epochs=3
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset
)

# 9) Train
trainer.train()


