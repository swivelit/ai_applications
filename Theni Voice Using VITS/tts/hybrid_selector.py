from tts.vits_engine import vits_tts
from tts.xtts_engine import xtts_tts

def synthesize(text, gender, emotion):
    if len(text.split()) < 8:
        return xtts_tts(text, gender)
    return vits_tts(text, gender, emotion)
