import json
from pathlib import Path

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
