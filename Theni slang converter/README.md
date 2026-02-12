# Theni Slang Tamil Converter

This project trains a text-to-text model to convert **Normal Slang Tamil**
into **Theni Slang Tamil** using your dataset (~2000 lines).

## Features
- Trainable ML model (TF‑IDF + Linear SVM baseline)
- Works fully offline
- Simple GUI (Tkinter) for sharing
- Easy to improve later with Transformer models

## Dataset Format
Place your dataset in:
```
data/theni_dataset.csv
```

CSV format:
```
normal,theni
என்ன பண்ணுற,என்ன பண்ணுறடா
```

## Setup
```bash
pip install -r requirements.txt
```

## Train
```bash
python train.py
```

## Run GUI
```bash
python app.py
```

## Output
Converted Theni slang will appear in the GUI output box.
