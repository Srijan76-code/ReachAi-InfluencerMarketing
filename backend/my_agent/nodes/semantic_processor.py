import numpy as np
import re
from rank_bm25 import BM25Okapi
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from dotenv import load_dotenv


from utils.state import LLMState

load_dotenv()


def cosine_similarity(a, b):
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return np.dot(a, b) / (norm_a * norm_b)


def tokenize(text):
    return re.findall(r"\w+", text.lower())


def semantic_processor(state: LLMState):
    print("\n--- 4. SEMANTIC FILTER (Pure Math) ---")

    candidates = state.get("enriched_candidates", [])
    query = " ".join(state.get("search_keywords", []))

    print(f"   > Input: {len(candidates)} enriched profiles.")

    if not candidates:
        return {"analyzed_leads": []}

    docs = []
    for c in candidates:
        semantic_string = (
            f"{c['title']} "
            f"{c.get('description', '')[:300]} "
            f"{' '.join([v['title'] for v in c['recent_videos']])}"
        )
        docs.append(semantic_string)

    try:
        embeddings = GoogleGenerativeAIEmbeddings(
            model="gemini-embedding-001", task_type="SEMANTIC_SIMILARITY"
        )
        vectors = embeddings.embed_documents(docs)
        query_vec = embeddings.embed_query(query)

        vec_scores = [cosine_similarity(query_vec, v) for v in vectors]
    except Exception as e:
        print(f"   [!] Embedding Error: {e}")
        vec_scores = [0.5] * len(docs)

    tokenized_corpus = [tokenize(d) for d in docs]
    bm25 = BM25Okapi(tokenized_corpus)
    bm25_scores = bm25.get_scores(tokenize(query))

    if max(bm25_scores) > 0:
        bm25_scores = [s / max(bm25_scores) for s in bm25_scores]

    final_ranked = []

    for i, candidate in enumerate(candidates):
        v_score = vec_scores[i]
        k_score = bm25_scores[i]

        if v_score < 0.45:
            continue

        hybrid_score = (v_score * 0.7) + (k_score * 0.3)

        candidate["semantic_score"] = round(hybrid_score, 3)
        final_ranked.append(candidate)

    final_ranked.sort(key=lambda x: x["semantic_score"], reverse=True)

    top_picks = final_ranked[:30]

    print(f"   > Filtered to top {len(top_picks)} relevant channels.")
    return {"analyzed_leads": top_picks}
