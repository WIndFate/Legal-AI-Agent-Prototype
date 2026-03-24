import logging
import os

import asyncpg
import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.config import get_settings

logger = logging.getLogger(__name__)

# Embedding model config
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


def _get_engine():
    """Create async engine for RAG store (separate from main app engine)."""
    settings = get_settings()
    return create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)


def _get_embedding_sync(text_input: str) -> list[float]:
    """Get embedding from OpenAI API (synchronous for tool calls)."""
    api_key = os.getenv("OPENAI_API_KEY") or get_settings().OPENAI_API_KEY
    response = httpx.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"input": text_input, "model": EMBEDDING_MODEL},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]


def _get_embeddings_batch_sync(texts: list[str]) -> list[list[float]]:
    """Get embeddings for a batch of texts (synchronous)."""
    api_key = os.getenv("OPENAI_API_KEY") or get_settings().OPENAI_API_KEY
    response = httpx.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"input": texts, "model": EMBEDDING_MODEL},
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()["data"]
    # Sort by index to maintain order
    data.sort(key=lambda x: x["index"])
    return [d["embedding"] for d in data]


class LegalKnowledgeStore:
    """Vector store for legal knowledge using PostgreSQL pgvector."""

    def __init__(self):
        self._engine = _get_engine()
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._initialized = False

    async def _ensure_table(self):
        """Create the embeddings table and pgvector extension if not exists."""
        if self._initialized:
            return
        async with self._engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS legal_knowledge_embeddings (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    embedding vector({EMBEDDING_DIM}),
                    metadata JSONB NOT NULL DEFAULT '{{}}'
                )
            """))
        self._initialized = True

    def add_documents(self, documents: list[dict]) -> None:
        """Add legal knowledge documents (sync, for startup loading)."""
        if not documents:
            return
        import asyncio
        asyncio.get_event_loop().run_until_complete(self._add_documents_async(documents))

    async def _add_documents_async(self, documents: list[dict]) -> None:
        await self._ensure_table()
        texts = [
            f"{doc['title']}\n{doc['content']}\n審査ポイント: {doc['review_point']}"
            for doc in documents
        ]
        embeddings = _get_embeddings_batch_sync(texts)

        async with self._session_factory() as session:
            for doc, doc_text, emb in zip(documents, texts, embeddings):
                emb_str = "[" + ",".join(str(x) for x in emb) + "]"
                await session.execute(
                    text("""
                        INSERT INTO legal_knowledge_embeddings (id, content, embedding, metadata)
                        VALUES (:id, :content, CAST(:embedding AS vector), CAST(:metadata AS jsonb))
                        ON CONFLICT (id) DO UPDATE SET
                            content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding,
                            metadata = EXCLUDED.metadata
                    """),
                    {
                        "id": doc["id"],
                        "content": doc_text,
                        "embedding": emb_str,
                        "metadata": f'{{"category": "{doc["category"]}", "title": "{doc["title"]}"}}',
                    },
                )
            await session.commit()
        logger.info("Upserted %d documents to pgvector", len(documents))

    def add_chunks(self, chunks: list[str], source: str) -> None:
        """Add plain text chunks (sync, for startup loading)."""
        if not chunks:
            return
        import asyncio
        asyncio.get_event_loop().run_until_complete(self._add_chunks_async(chunks, source))

    async def _add_chunks_async(self, chunks: list[str], source: str) -> None:
        await self._ensure_table()
        embeddings = _get_embeddings_batch_sync(chunks)

        async with self._session_factory() as session:
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                doc_id = f"{source}_{i:03d}"
                emb_str = "[" + ",".join(str(x) for x in emb) + "]"
                import json
                metadata = json.dumps({"category": "text_document", "title": source})
                await session.execute(
                    text("""
                        INSERT INTO legal_knowledge_embeddings (id, content, embedding, metadata)
                        VALUES (:id, :content, CAST(:embedding AS vector), CAST(:metadata AS jsonb))
                        ON CONFLICT (id) DO UPDATE SET
                            content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding,
                            metadata = EXCLUDED.metadata
                    """),
                    {
                        "id": doc_id,
                        "content": chunk,
                        "embedding": emb_str,
                        "metadata": metadata,
                    },
                )
            await session.commit()
        logger.info("Upserted %d chunks from %s to pgvector", len(chunks), source)

    def search(self, query: str, n_results: int = 5) -> list[dict]:
        """Search for relevant legal knowledge (sync, called from tools)."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # LangChain tools are sync, but may be called from an async graph.
                # Use a fresh store inside a worker thread so asyncpg connections
                # are created and consumed on the same event loop.
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(_search_with_fresh_store, query, n_results).result()
            return loop.run_until_complete(self._search_async(query, n_results))
        except RuntimeError:
            return asyncio.run(self._search_async(query, n_results))

    async def _search_async(self, query: str, n_results: int = 5) -> list[dict]:
        await self._ensure_table()
        query_embedding = _get_embedding_sync(query)
        emb_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        dsn = get_settings().DATABASE_URL.replace("+asyncpg", "")

        conn = await asyncpg.connect(dsn)
        try:
            rows = await conn.fetch(
                """
                    SELECT id, content, metadata,
                           embedding <-> $1::vector AS distance
                    FROM legal_knowledge_embeddings
                    ORDER BY distance
                    LIMIT $2
                """,
                emb_str,
                n_results,
            )
        finally:
            await conn.close()

        output = []
        for row in rows:
            metadata = row["metadata"]
            if isinstance(metadata, str):
                import json

                metadata = json.loads(metadata)
            output.append({
                "id": row["id"],
                "content": row["content"],
                "metadata": metadata,
                "distance": float(row["distance"]),
            })
        return output


# Singleton instance
_store: LegalKnowledgeStore | None = None


def get_store() -> LegalKnowledgeStore:
    global _store
    if _store is None:
        _store = LegalKnowledgeStore()
    return _store


def _search_with_fresh_store(query: str, n_results: int) -> list[dict]:
    """Run search on a fresh store bound to the worker thread's event loop."""
    import asyncio

    fresh_store = LegalKnowledgeStore()
    return asyncio.run(fresh_store._search_async(query, n_results))
