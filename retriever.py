from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from flashrank import Ranker, RerankRequest


CHROMA_DIR = "./chroma_db"

COLLECTION_NAME = "medical_guidelines"

EMBEDDING_MODEL = (
    "sentence-transformers/all-MiniLM-L6-v2"
)


# ============================================================
# EMBEDDINGS
# ============================================================

print("Loading embedding model...")

embeddings = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL,
    model_kwargs={
        "device": "cpu"
    },
    encode_kwargs={
        "normalize_embeddings": True
    },
)

print("Embedding model loaded.")


# ============================================================
# CHROMA
# ============================================================

print("Loading Chroma database...")

vectorstore = Chroma(
    persist_directory=CHROMA_DIR,
    collection_name=COLLECTION_NAME,
    embedding_function=embeddings,
)

print("Chroma database loaded.")


# ============================================================
# MEDICAL RETRIEVER
# ============================================================

retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={
        "k": 15
    },
)


# ============================================================
# FLASHRANK
# ============================================================

print("Loading FlashRank reranker...")

ranker = Ranker(
    model_name="ms-marco-MiniLM-L-12-v2",
    cache_dir="./flashrank_cache",
)

print("FlashRank loaded.")


# ============================================================
# RERANK
# ============================================================

def rerank_documents(
    query: str,
    documents,
    top_n: int = 5,
    min_score: float = 0.0,
):

    if not documents:
        return []

    passages = []

    for index, document in enumerate(documents):

        passages.append(
            {
                "id": str(index),
                "text": document.page_content,
                "meta": document.metadata,
            }
        )

    rerank_request = RerankRequest(
        query=query,
        passages=passages,
    )

    reranked_results = ranker.rerank(
        rerank_request
    )

    final_documents = []

    for result in reranked_results:

        score = float(
            result["score"]
        )

        if score < min_score:
            continue

        index = int(
            result["id"]
        )

        document = documents[index]

        document.metadata[
            "rerank_score"
        ] = score

        final_documents.append(
            document
        )

        if len(final_documents) >= top_n:
            break

    return final_documents


# ============================================================
# MEDICAL GUIDELINE SEARCH
# ============================================================

def search_guidelines(
    query: str,
    retrieval_k: int = 15,
    rerank_k: int = 5,
    min_score: float = 0.30,
):

    print("\nSearching Chroma...")

    documents = retriever.invoke(
        query
    )

    print(
        f"Retrieved {len(documents)} chunks."
    )

    print(
        "Reranking results..."
    )

    documents = rerank_documents(
        query=query,
        documents=documents,
        top_n=rerank_k,
        min_score=min_score,
    )

    print(
        f"Returning top "
        f"{len(documents)} "
        f"relevant reranked chunks."
    )

    return documents