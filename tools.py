from langchain_core.tools import tool

from retriever import search_guidelines

@tool
def search_medical_guidelines(query: str) -> str:
    """
    Search only the provided Standard Treatment Guidelines PDF.

    This tool should be used for medical questions that need to be
    answered from the provided PDF.
    """

    documents = search_guidelines(
        query=query,
        retrieval_k=15,
        rerank_k=2,
        min_score=0.40,
    )

    if not documents:

        return (
            "NO_RELEVANT_INFORMATION_FOUND: "
            "The provided Standard Treatment Guidelines PDF "
            "does not contain enough relevant information to "
            "answer this question."
        )

    results = []

    for index, document in enumerate(
        documents,
        start=1,
    ):

        content = document.page_content.strip()

        results.append(
            f"""
RESULT {index}

CONTENT:
{content}
"""
        )

    return "\n".join(results)