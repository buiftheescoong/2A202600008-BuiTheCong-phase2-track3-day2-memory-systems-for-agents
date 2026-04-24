"""Semantic memory: ChromaDB vector store for knowledge retrieval.

Bonus: Chroma thật +2.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from .base import BaseMemory

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


class SemanticMemory(BaseMemory):
    """Vector-based semantic search using ChromaDB (persistent).

    Documents are chunked and embedded via Chroma's default embedding
    (all-MiniLM-L6-v2) so no external embedding API is needed.
    """

    def __init__(self, collection_name: str = "knowledge_base", persist_dir: str | None = None):
        self.persist_dir = persist_dir or os.path.join(DATA_DIR, "chroma_db")
        os.makedirs(self.persist_dir, exist_ok=True)

        self.client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "ChromaDB collection '%s' ready (%d docs)",
            collection_name,
            self.collection.count(),
        )

    # ---- public interface ----

    def add_document(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        """Add or update a document chunk."""
        self.collection.upsert(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata or {}],
        )

    def add_documents_bulk(self, docs: list[dict[str, Any]]) -> None:
        """Bulk add documents. Each dict needs 'id' and 'text', optional 'metadata'."""
        if not docs:
            return
        self.collection.upsert(
            ids=[d["id"] for d in docs],
            documents=[d["text"] for d in docs],
            metadatas=[d.get("metadata", {}) for d in docs],
        )

    def search(self, query: str, k: int = 3) -> list[dict[str, Any]]:
        """Semantic search. Returns list of {id, text, score, metadata}."""
        if self.collection.count() == 0:
            return []
        results = self.collection.query(query_texts=[query], n_results=min(k, self.collection.count()))

        hits: list[dict[str, Any]] = []
        for i in range(len(results["ids"][0])):
            hits.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "score": 1 - results["distances"][0][i],  # cosine similarity
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
            })
        return hits

    def load_from_file(self, filepath: str, chunk_size: int = 300) -> int:
        """Load and chunk a text file into the collection. Returns chunk count."""
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()

        chunks = self._chunk_text(text, chunk_size)
        basename = os.path.basename(filepath)
        docs = [
            {"id": f"{basename}_chunk_{i}", "text": chunk, "metadata": {"source": basename, "chunk": i}}
            for i, chunk in enumerate(chunks)
        ]
        self.add_documents_bulk(docs)
        logger.info("Loaded %d chunks from %s", len(docs), filepath)
        return len(docs)

    # ---- base overrides ----

    def clear(self) -> None:
        # Delete and recreate collection
        name = self.collection.name
        self.client.delete_collection(name)
        self.collection = self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def get_stats(self) -> dict[str, Any]:
        return {
            "type": "semantic",
            "backend": "chromadb",
            "collection": self.collection.name,
            "document_count": self.collection.count(),
            "persist_dir": self.persist_dir,
        }

    def format_for_prompt(self, hits: list[dict] | None = None) -> str:
        """Format search hits for prompt injection."""
        if not hits:
            return "No relevant knowledge found."
        lines: list[str] = []
        for h in hits:
            score_pct = f"{h.get('score', 0):.0%}"
            lines.append(f"- [{score_pct}] {h['text'][:300]}")
        return "\n".join(lines)

    # ---- internals ----

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 300) -> list[str]:
        """Split text into chunks by paragraphs, respecting chunk_size (chars)."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks: list[str] = []
        current = ""
        for para in paragraphs:
            if len(current) + len(para) + 2 > chunk_size and current:
                chunks.append(current.strip())
                current = para
            else:
                current = current + "\n\n" + para if current else para
        if current.strip():
            chunks.append(current.strip())
        return chunks
