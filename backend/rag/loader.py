import json
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.rag.store import get_store


def load_legal_knowledge() -> int:
    """Load legal knowledge from JSON file into the vector store.

    Returns the number of documents loaded.
    """
    data_path = Path(__file__).parent.parent / "data" / "legal_knowledge.json"
    with open(data_path, "r", encoding="utf-8") as f:
        documents = json.load(f)

    store = get_store()
    store.add_documents(documents)
    return len(documents)


def load_text_documents() -> int:
    """Load .txt files from data/ directory, chunk them, and store in vector store.

    chunk_size=200, chunk_overlap=40, separators prioritize paragraph/sentence boundaries.
    Returns total number of chunks loaded.
    """
    data_path = Path(__file__).parent.parent / "data"
    txt_files = list(data_path.glob("*.txt"))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=200,
        chunk_overlap=40,
        separators=["\n\n", "\n", "。", "、", ""],
    )

    store = get_store()
    total = 0
    for txt_file in txt_files:
        text = txt_file.read_text(encoding="utf-8")
        chunks = splitter.split_text(text)
        source = txt_file.stem  # e.g. "civil_law"
        store.add_chunks(chunks, source)
        total += len(chunks)
    return total
