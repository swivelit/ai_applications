from TTS.api import TTS

xtts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=True)

def xtts_tts(text, gender):
    speaker = f"data/{gender}_reference.wav"
    out = f"output/xtts_{gender}.wav"
    xtts.tts_to_file(text=text, speaker_wav=speaker, language="ta", file_path=out)
    return out
