from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

PDF_PATH = "standard-treatment-guidelines.pdf"

CHROMA_DIR = "./chroma_db"

COLLECTION_NAME = "medical_guidelines"

EMBEDDING_MODEL = (
    "sentence-transformers/all-MiniLM-L6-v2"
)

def main():

    print("=" * 70)
    print("MEDICAL GUIDELINES - PDF INGESTION")
    print("=" * 70)

    pdf_path = Path(
        PDF_PATH
    )

    if not pdf_path.exists():

        raise FileNotFoundError(
            f"PDF not found: {PDF_PATH}"
        )

    print(
        f"\nPDF: {pdf_path}"
    )

    print(
        "\n[1/5] Loading PDF..."
    )

    loader = PyPDFLoader(
        str(pdf_path)
    )

    documents = loader.load()

    print(
        f"Loaded {len(documents)} pages."
    )

    print(
        "\n[2/5] Splitting documents..."
    )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=[
            "\n\n",
            "\n",
            ". ",
            " ",
            "",
        ],
    )

    chunks = splitter.split_documents(
        documents
    )

    print(
        f"Created {len(chunks)} chunks."
    )

    print(
        "\n[3/5] Adding metadata..."
    )

    for index, chunk in enumerate(
        chunks
    ):

        chunk.metadata[
            "chunk_id"
        ] = index

        if "page" in chunk.metadata:

            chunk.metadata[
                "page_number"
            ] = (
                chunk.metadata["page"] + 1
            )

        chunk.metadata[
            "document"
        ] = (
            "Standard Treatment Guidelines"
        )

    print(
        "\n[4/5] Loading embedding model..."
    )

    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={
            "device": "cpu"
        },
        encode_kwargs={
            "normalize_embeddings": True
        },
    )

    print(
        f"Embedding model: {EMBEDDING_MODEL}"
    )

    print(
        "Embedding model loaded."
    )

    print(
        "\n[5/5] Creating Chroma vector database..."
    )

    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DIR,
        collection_name=COLLECTION_NAME,
    )

    print(
        "\n" + "=" * 70
    )

    print(
        "INGESTION COMPLETED SUCCESSFULLY"
    )

    print(
        "=" * 70
    )

    print(
        f"Pages       : {len(documents)}"
    )

    print(
        f"Chunks      : {len(chunks)}"
    )

    print(
        f"Embedding   : {EMBEDDING_MODEL}"
    )

    print(
        f"Vector DB   : {CHROMA_DIR}"
    )

    print(
        f"Collection  : {COLLECTION_NAME}"
    )

    print(
        "\nSample chunk:"
    )

    print(
        "-" * 70
    )

    print(
        chunks[0].page_content[:1000]
    )

    print(
        "\nMetadata:"
    )

    print(
        chunks[0].metadata
    )

if __name__ == "__main__":
    main()