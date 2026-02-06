import ffmpeg

def polish(input_audio):
    out = "output/final.wav"
    (
        ffmpeg
        .input(input_audio)
        .filter("loudnorm", I=-14)
        .output(out)
        .run(overwrite_output=True)
    )
    return out
