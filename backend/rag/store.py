import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv
import os

load_dotenv()


class LegalKnowledgeStore:
    """Vector store for legal knowledge using ChromaDB."""

    def __init__(self, persist_dir: str = "./chroma_data"):
        self.embedding_fn = OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name="text-embedding-3-small",
        )
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name="legal_knowledge",
            embedding_function=self.embedding_fn,
        )

    def add_documents(self, documents: list[dict]) -> None:
        """Add legal knowledge documents to the vector store."""
        if not documents:
            return
        self.collection.upsert(
            ids=[doc["id"] for doc in documents],
            documents=[
                f"{doc['title']}\n{doc['content']}\n審査ポイント: {doc['review_point']}"
                for doc in documents
            ],
            metadatas=[
                {"category": doc["category"], "title": doc["title"]}
                for doc in documents
            ],
        )

    def search(self, query: str, n_results: int = 5) -> list[dict]:
        """Search for relevant legal knowledge."""
        results = self.collection.query(query_texts=[query], n_results=n_results)
        output = []
        for i, doc in enumerate(results["documents"][0]):
            output.append(
                {
                    "id": results["ids"][0][i],
                    "content": doc,
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if results.get("distances") else None,
                }
            )
        return output


# Singleton instance
_store: LegalKnowledgeStore | None = None


def get_store() -> LegalKnowledgeStore:
    global _store
    if _store is None:
        _store = LegalKnowledgeStore()
    return _store
