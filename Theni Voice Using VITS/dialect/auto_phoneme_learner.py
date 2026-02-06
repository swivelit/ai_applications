import librosa, json, numpy as np

def learn_from_audio(wav_path, gender):
    y, sr = librosa.load(wav_path, sr=22050)
    energy = librosa.feature.rms(y=y)[0]

    rules = {}
    if np.max(energy) > 0.06:
        rules["டா"] = "DAA"
    if librosa.get_duration(y=y, sr=sr) > 4.0:
        rules["இ"] = "II"

    with open(f"dialect/learned_rules_{gender}.json", "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)

    return rules
