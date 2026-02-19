# -----------------------------------
# Optimized Hybrid RAG + OpenAI LLM
# SAFE VS CODE VERSION
# -----------------------------------

import time
import logging
import os
import numpy as np
import pandas as pd
from dotenv import load_dotenv

from deep_translator import GoogleTranslator
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

from sentence_transformers import SentenceTransformer
from openai import OpenAI


# -------------------------
# LOAD ENV VARIABLES
# -------------------------

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("❌ OPENAI_API_KEY not found in .env file")

client = OpenAI(api_key=OPENAI_API_KEY)

logging.getLogger("transformers").setLevel(logging.ERROR)


# -------------------------
# CONFIGURATION
# -------------------------

CSV_PATH = "voice_assistant_dataset_10000.csv"
EMBEDDING_CACHE = "cached_embeddings.npy"

HIGH_THRESHOLD = 0.85
MEDIUM_THRESHOLD = 0.65
TOP_K = 3


# -------------------------
# LOAD EMBEDDING MODEL
# -------------------------

print("🔄 Loading embedding model...")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
print("✅ Embedding model loaded.\n")


# -------------------------
# LANGUAGE CONVERSION
# -------------------------

def convert_to_english(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        return None

    text = text.strip()

    try:
        language = detect(text)
    except LangDetectException:
        return text

    try:
        if language == "ta":
            print("🌐 Translating Tamil → English")
            return GoogleTranslator(source="ta", target="en").translate(text)
        return text
    except:
        return text


# -------------------------
# LOAD DATASET
# -------------------------

def load_dataset(csv_path: str):
    if not os.path.exists(csv_path):
        raise FileNotFoundError("❌ CSV file not found.")

    for encoding in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
        try:
            df = pd.read_csv(csv_path, encoding=encoding)
            print(f"✅ Loaded CSV using encoding: {encoding}")
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("❌ Could not decode CSV file.")

    if "question" not in df.columns or "answer" not in df.columns:
        raise ValueError("❌ CSV must contain 'question' and 'answer' columns.")

    return df


# -------------------------
# SAFE EMBEDDING LOADER
# -------------------------

def create_or_load_embeddings(df):

    # If cache exists → try loading safely
    if os.path.exists(EMBEDDING_CACHE):
        print("📦 Loading cached embeddings...")

        try:
            embeddings = np.load(EMBEDDING_CACHE)

            # Validate shape
            if embeddings.shape[0] != len(df):
                print("⚠ Cache size mismatch. Rebuilding embeddings...")
                raise ValueError("Shape mismatch")

            print("✅ Cached embeddings loaded successfully.\n")
            return embeddings

        except Exception as e:
            print(f"❌ Corrupted cache detected: {e}")
            print("🗑 Deleting corrupted cache...")
            os.remove(EMBEDDING_CACHE)
            print("🔁 Regenerating embeddings...\n")

    # Create new embeddings
    print("⚡ Creating dataset embeddings (one-time process)...")

    questions = df["question"].astype(str).tolist()

    embeddings = embedding_model.encode(
        questions,
        normalize_embeddings=True,
        show_progress_bar=True
    )

    np.save(EMBEDDING_CACHE, embeddings)
    print("✅ Embeddings cached successfully.\n")

    return embeddings


# -------------------------
# FAST SIMILARITY SEARCH
# -------------------------

def compute_similarity(query_embedding, embeddings):
    return np.dot(embeddings, query_embedding)


# -------------------------
# LLM CALL
# -------------------------

def generate_with_llm(query: str, context: str = None):

    llm_start = time.time()

    if context:
        system_prompt = (
            "You are a helpful voice assistant. "
            "Use the provided context only if relevant."
        )

        user_prompt = f"""
Context:
{context}

Question:
{query}
"""
    else:
        system_prompt = "You are a helpful voice assistant."
        user_prompt = query

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.5,
    )

    print(f"🧠 LLM time: {time.time() - llm_start:.2f}s")

    return response.choices[0].message.content


# -------------------------
# HYBRID RAG PIPELINE
# -------------------------

def hybrid_rag_pipeline(query, df, embeddings):

    rag_start = time.time()

    query_embedding = embedding_model.encode(
        [query],
        normalize_embeddings=True
    )[0]

    similarities = compute_similarity(query_embedding, embeddings)

    best_index = np.argmax(similarities)
    best_score = similarities[best_index]

    print(f"🔎 Similarity Score: {best_score:.4f}")

    if best_score >= HIGH_THRESHOLD:
        print("⚡ Direct RAG Answer")
        print(f"⏱ RAG time: {time.time() - rag_start:.2f}s\n")
        return df.iloc[best_index]["answer"]

    if best_score < MEDIUM_THRESHOLD:
        print("➡ Routing: Pure LLM\n")
        print(f"⏱ RAG time: {time.time() - rag_start:.2f}s\n")
        return generate_with_llm(query)

    top_indices = similarities.argsort()[-TOP_K:][::-1]
    context = "\n".join(df.iloc[i]["answer"] for i in top_indices)

    print("➡ Routing: LLM + Context\n")
    print(f"⏱ RAG time: {time.time() - rag_start:.2f}s\n")

    return generate_with_llm(query, context)


# -------------------------
# MAIN LOOP
# -------------------------

def main():

    df = load_dataset(CSV_PATH)
    embeddings = create_or_load_embeddings(df)

    while True:
        user_input = input("\n🎤 Enter your query (or type 'exit'): ").strip()

        if user_input.lower() == "exit":
            print("👋 Exiting...")
            break

        english_query = convert_to_english(user_input)

        total_start = time.time()

        response = hybrid_rag_pipeline(english_query, df, embeddings)

        print("\n💬 Final Response:\n")
        print(response)

        print(f"\n⏳ Total time: {time.time() - total_start:.2f}s")


if __name__ == "__main__":
    main()
