# AI Task Assistant (Single File Version)

This project is a simple AI assistant that understands English commands
and schedules meetings using NLP.

## Features
- Intent detection
- Entity extraction using spaCy
- Date and time resolution
- Step-by-step execution plan
- Dataset-based testing

## Dataset
Sample commands are stored in commands.txt

## How to Run
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python ai_task_assistant.py
