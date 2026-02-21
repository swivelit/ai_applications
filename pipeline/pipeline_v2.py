# ============================================================
# COLAB NOTEBOOK: Text (EN/Tamil) -> English -> (RAG or LLM) -> Answer (+ optional TTS)
# ============================================================

# -----------------------
# 0) Install dependencies
# -----------------------
!pip -q install openai faiss-cpu langdetect

import os, re
from getpass import getpass
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
import faiss
from langdetect import detect

from IPython.display import Audio, display
from openai import OpenAI

# -----------------------
# 1) Set your OpenAI API key
# -----------------------
if not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass("Paste your OPENAI_API_KEY and press Enter: ").strip()

client = OpenAI()

# ----------------------------------------
# 2) Convert text to English (if needed)
# ----------------------------------------
def to_english(text: str) -> str:
    """
    If text looks non-English (e.g., Tamil), translate to English via a small model.
    """
    text_stripped = (text or "").strip()
    if not text_stripped:
        return ""

    try:
        lang = detect(text_stripped)
    except Exception:
        lang = "unknown"

    if lang == "en":
        return text_stripped

    resp = client.responses.create(
        model="gpt-4o-mini",
        input=[
            {"role": "system", "content": "Translate the user's text to clear English. Preserve meaning; do not add extra info."},
            {"role": "user", "content": text_stripped},
        ],
    )
    return resp.output_text.strip()

# ---------------------------------------------------------
# 3) Minimal RAG: build a local FAISS index over documents
# ---------------------------------------------------------
def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> List[str]:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        return []
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i:i + chunk_size])
        i += max(1, chunk_size - overlap)
    return chunks

def embed_texts(texts: List[str]) -> np.ndarray:
    """
    Create embeddings using text-embedding-3-small.
    Returns (n, d) float32 numpy array.
    """
    emb = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts
    )
    vectors = [item.embedding for item in emb.data]
    return np.array(vectors, dtype=np.float32)

@dataclass
class RAGStore:
    index: faiss.Index
    chunks: List[str]
    chunk_sources: List[str]

def build_rag_store(docs: List[Tuple[str, str]]) -> RAGStore:
    all_chunks: List[str] = []
    sources: List[str] = []

    for src, content in docs:
        cs = chunk_text(content)
        all_chunks.extend(cs)
        sources.extend([src] * len(cs))

    if not all_chunks:
        raise ValueError("No chunks to index. Provide non-empty docs.")

    vecs = embed_texts(all_chunks)
    d = vecs.shape[1]

    # Cosine similarity via inner product on normalized vectors
    faiss.normalize_L2(vecs)
    index = faiss.IndexFlatIP(d)
    index.add(vecs)

    return RAGStore(index=index, chunks=all_chunks, chunk_sources=sources)

def rag_retrieve(store: RAGStore, query: str, k: int = 5) -> List[Tuple[str, str, float]]:
    qv = embed_texts([query])
    faiss.normalize_L2(qv)
    scores, idxs = store.index.search(qv, k)

    results = []
    for score, idx in zip(scores[0], idxs[0]):
        if idx == -1:
            continue
        results.append((store.chunk_sources[idx], store.chunks[idx], float(score)))
    return results

# ---------------------------------------------------------
# 4) Router: decide RAG vs direct LLM based on user query
# ---------------------------------------------------------
def route_query(user_english_query: str) -> str:
    """
    Returns: "rag" or "llm"
    """
    router_prompt = f"""
Decide how to answer the user query.

Choose "rag" if the user is asking about information that should come from the project's documents/knowledge base
(e.g., policies, internal docs, specifications, FAQs we indexed).
Choose "llm" if it is general knowledge, brainstorming, writing help, coding help, or doesn't need the docs.

Return ONLY one token: rag or llm.

User query:
{user_english_query}
""".strip()

    r = client.responses.create(
        model="gpt-4o-mini",
        input=router_prompt
    )
    decision = (r.output_text or "").strip().lower()
    return "rag" if "rag" in decision else "llm"

# ---------------------------------------------------------
# 5) Answer generation: RAG answer or direct LLM answer
# ---------------------------------------------------------
def answer_with_rag(store: RAGStore, user_query_en: str) -> str:
    retrieved = rag_retrieve(store, user_query_en, k=5)

    if not retrieved:
        return "I don't know based on the available documents."

    context_blocks = []
    for src, chunk, score in retrieved:
        context_blocks.append(f"[Source: {src} | score={score:.3f}]\n{chunk}")

    context = "\n\n---\n\n".join(context_blocks)

    resp = client.responses.create(
        model="gpt-4o-mini",
        input=[
            {"role": "system", "content": "You are a helpful assistant. Use ONLY the provided context to answer. If missing, say you don't know."},
            {"role": "user", "content": f"Context:\n{context}\n\nUser question:\n{user_query_en}\n\nAnswer:"},
        ],
    )
    return resp.output_text.strip()

def answer_direct(user_query_en: str) -> str:
    resp = client.responses.create(
        model="gpt-4o-mini",
        input=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": user_query_en},
        ],
    )
    return resp.output_text.strip()

# ---------------------------------------------------------
# 6) Optional: Text-to-Speech (Speak the final answer)
# ---------------------------------------------------------
def tts_speak(text: str, voice: str = "alloy") -> bytes:
    """
    Generate speech audio bytes (mp3) from text.
    """
    audio = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=voice,
        input=text,
        format="mp3",
    )
    # Handle common SDK response types
    if hasattr(audio, "read"):
        return audio.read()
    if isinstance(audio, (bytes, bytearray)):
        return bytes(audio)
    if hasattr(audio, "content"):
        return audio.content
    raise RuntimeError("Unexpected TTS response type")

# ---------------------------------------------------------
# 7) Provide your docs for RAG (EDIT THIS)
# ---------------------------------------------------------
drishyam_doc = r"""
Drishyam (transl. Visual) is a 2013 Indian Malayalam-language crime thriller film written and directed by Jeethu Joseph. It stars Mohanlal alongside Meena, Ansiba Hassan, Esther Anil, Asha Sharath, Siddique, Kalabhavan Shajohn, Roshan Basheer and Neeraj Madhav. The film was produced by Antony Perumbavoor under Aashirvad Cinemas. The film follows the struggle of Georgekutty and his family, who come under suspicion when Varun Prabhakar, the son of the IG Geetha Prabhakar, goes missing. A sequel titled Drishyam 2 was released in 2021.[5]

Principal photography commenced in October 2013 in Thodupuzha, where the film was extensively shot. The cinematography was handled by Sujith Vaassudev whilst the film was edited by Ayoob Khan. The soundtrack was composed by Anil Johnson and Vinu Thomas.

Drishyam was released on 19 December 2013. The film received widespread critical acclaim with critics praising the cast performance, story, screenplay, and direction. It was the first Malayalam film to collect ₹50 crore. The film grossed over ₹62 crore worldwide.[6] It ran in theatres for more than 150 days. It also became the longest-running film in the United Arab Emirates, running for 125 days. The film remained the highest-grossing Malayalam film of all time until it was surpassed by Pulimurugan in 2016. It remained among the top 10 highest-grossing Malayalam films of all time for a decade.

Drishyam won numerous accolades, including the Kerala State Film Award for Best Film with Popular Appeal and Aesthetic Value and the Filmfare Award for Best Film – Malayalam. The film was also screened at the 45th International Film Festival of India and the 8th Asian Film Festival. Drishyam has been remade into several languages including four regional languages which were Drishya (2014) in Kannada, Drushyam (2014) in Telugu, Papanasam (2015) in Tamil and Drishyam (2015) in Hindi. Internationally, it was remade in Sinhala language as Dharmayuddhaya (2017) and in Chinese as Sheep Without a Shepherd (2019). A Korean remake was announced,[7][8][9] making it the first Indian film to be remade in that language.[10] An English language remake has been announced by Panorama Studios with U.S. companies Gulfstream Pictures and JOAT Films.[11]

Plot
Georgekutty started out as an orphan who had dropped out of school after his 4th grade. He is now a businessman running a cable television service in the village of Rajakkad. He is married to Rani and they have two daughters Anju and Anu. His only interest apart from his family is watching films, as he spends most of his time in front of the TV in his small office. Due to his knowledge of the films, he is respected by the locals.

During a nature camp, Anju gets photographed in the bathroom by a hidden cell phone held by Varun Prabhakar, who is the spoiled son of Inspector General of Police Geetha Prabhakar. Varun meets Anju and blackmails her to get nude with him and have sex with him. That same night, he arrives at their house, but Rani is informed by Anju and pleads Varun to leave Anju alone. He agrees on the condition that Rani have sex with him instead. In an attempt to destroy Varun's phone, Anju accidentally strikes Varun in the head, killing him. They bury his body in a compost pit, which is witnessed by Anu. Rani informs Georgekutty about the incident and he devises a way to save his family from the police. He removes the broken phone and disposes of Varun's car, which is seen by the local police constable Sahadevan, who holds a grudge against Georgekutty. As Georgekutty takes his family on a trip to attend a religious retreat, a movie and a restaurant, Geetha starts an investigation upon learning that Varun has gone missing.

After a preliminary investigation, Geetha calls Georgekutty and his family for questioning. Georgekutty had predicted that this would happen and coached his family about their alibi at the time of murder. When questioned individually, they reply the same thing and they had also shown the bill of the restaurant, the movie's and bus journey's tickets as a proof of their alibi. Geetha questions the owners of the establishments they have been to and their statements prove Georgekutty's alibi. However, Geetha realises that on the day of the incident, Georgekutty had taken the tickets and the bill, made acquaintance with the owners and had gone for the trip with his family the next day, thus proving his alibi and making the owners unwittingly tell the lie.

Georgekutty and his family are arrested and Sahadevan brutally tortures them, including Anu to make the truth come out. Geetha learns from Varun's friend Alex about Anju's video created by Varun. Eventually, Anu gives in and reveals the place where the body is buried. After digging the compost pit, they find the carcass of a cow, indicating that Georgekutty had moved the body. Before Geetha and Sahadevan could react to it, Georgekutty and Anu go to the media and complain of Sahadevan's torture against his family. Enraged, Sahadevan tries to attack the family again, but Rani's brother Rajesh and the villagers saves them and subdue Sahadevan, who later ends up being suspended while Geetha resigns from her post. Geetha and her husband Prabhakar meet Georgekutty to ask forgiveness for their rude and violent behavior and of their son's perverted behaviour, but Georgekutty suspects there might be foul play involved and still does not reveal directly about Varun's death. Georgekutty, now on remand, signs a register at the newly constructed local police station and leaves. As the police inspector tells him that he will find the body and that the police are not fools, Georgekutty replies by telling the officer he believes that the police are there to help the people.
"""

docs_for_rag = [
    ("doc:product_overview", """
Our product supports Tamil or English TEXT input.
We translate to English for routing and answering.
We use RAG for answers that should come from indexed docs.
We use direct LLM for everything else.
"""),
    ("doc:drishyam_full_text", drishyam_doc),
]

rag_store = build_rag_store(docs_for_rag)
print("✅ RAG store built with", len(rag_store.chunks), "chunks")

# ---------------------------------------------------------
# 8) End-to-end run function (TEXT input)
# ---------------------------------------------------------
def run_once_text(user_text: str, speak_answer: bool = False, voice: str = "alloy"):
    """
    user_text: Tamil or English
    speak_answer: if True, plays TTS mp3 in Colab
    """
    print("\n🧾 INPUT (raw):")
    print(user_text)

    print("\n🌐 Converting to English (if needed)...")
    query_en = to_english(user_text)
    print("\n--- QUERY (English) ---")
    print(query_en)

    print("\n🧭 Routing (RAG vs LLM)...")
    route = route_query(query_en)
    print("Route =", route)

    print("\n🤖 Generating answer...")
    if route == "rag":
        answer = answer_with_rag(rag_store, query_en)
    else:
        answer = answer_direct(query_en)

    print("\n=== ANSWER ===")
    print(answer)

    if speak_answer:
        print("\n🔊 Speaking answer...")
        mp3 = tts_speak(answer, voice=voice)
        display(Audio(mp3, autoplay=False))

    return answer

# ---------------------------------------------------------
# 9) Example runs
# ---------------------------------------------------------
# English example:
run_once_text("Who is Georgekutty and what does he do?", speak_answer=False)

# Tamil example (you can replace with your own):
run_once_text("ஜார்ஜ்குட்டி யார்? அவர் என்ன வேலை செய்கிறார்?", speak_answer=False)
