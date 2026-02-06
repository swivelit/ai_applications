import json, random, os

with open("dialect/phoneme_emotions.json", encoding="utf-8") as f:
    EMO_RULES = json.load(f)

def phonemize_with_emotion(text, emotion="casual"):
    rules = EMO_RULES.get(emotion, {})
    for k, v in rules.items():
        text = text.replace(k, v)
    if emotion in ["casual", "teasing"] and random.random() < 0.3:
        text = "அட " + text
    return text

def apply_learned_rules(text, gender):
    path = f"dialect/learned_rules_{gender}.json"
    if not os.path.exists(path):
        return text
    with open(path, encoding="utf-8") as f:
        rules = json.load(f)
    for k, v in rules.items():
        text = text.replace(k, v)
    return text
