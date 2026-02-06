from TTS.api import TTS

vits = TTS(
    model_path="vits_outputs/best_model.pth",
    config_path="config/vits_tamil.json",
    gpu=True
)

def vits_tts(text, gender, emotion):
    out = f"output/vits_{gender}.wav"
    vits.tts_to_file(text=text, file_path=out)
    return out
