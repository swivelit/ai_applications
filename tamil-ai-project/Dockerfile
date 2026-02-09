FROM python:3.11-slim

WORKDIR /app

# Install system deps (important for faster-whisper)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (layer caching)
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# NOW copy your app code (this is what was missing earlier)
COPY . .

ENV PORT=5001
EXPOSE 5001

CMD ["python", "main.py"]
