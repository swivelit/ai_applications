import gradio as gr
import pandas as pd
import os

records = []

def rate(audio_a, audio_b, score):
    records.append({"A": audio_a, "B": audio_b, "MOS": score})
    return "Saved"

with gr.Blocks() as demo:
    a = gr.Audio(label="Sample A")
    b = gr.Audio(label="Sample B")
    s = gr.Slider(1,5,step=1,label="MOS Score")
    out = gr.Textbox()
    btn = gr.Button("Submit")
    btn.click(rate, [a,b,s], out)

demo.launch()
