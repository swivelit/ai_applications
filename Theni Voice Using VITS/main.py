from dialect.phonemizer import phonemize_with_emotion, apply_learned_rules
from tts.hybrid_selector import synthesize
from audio.postprocess import polish

text = "டேய் இன்னைக்கு வர்றியா"
gender = "male"      # male / female
emotion = "casual"   # casual / teasing / angry / calm

# phoneme steering
text = phonemize_with_emotion(text, emotion)
text = apply_learned_rules(text, gender)

audio = synthesize(text, gender, emotion)
final = polish(audio)

print("✅ Generated:", final)
