"""
MINXG RAG System — Retrieval Augmented Generation with vector search.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
import json
import time


@dataclass
class Document:
    """A document in the knowledge base."""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None


class VectorStore:
    """Simple in-memory vector store with cosine similarity."""

    def __init__(self, dimension: int = 1536):
        self.dimension = dimension
        self.vectors: List[Document] = []

    def add(self, document: Document) -> None:
        """Add a document to the store."""
        if document.embedding is None:
            # Generate a random embedding for demo
            import random
            document.embedding = [random.random() for _ in range(self.dimension)]
        self.vectors.append(document)

    def add_batch(self, documents: List[Document]) -> int:
        """Add multiple documents."""
        for doc in documents:
            self.add(doc)
        return len(documents)

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_fn: Optional[callable] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar documents using cosine similarity."""
        if not self.vectors:
            return []

        # Compute cosine similarities
        similarities = []
        for doc in self.vectors:
            if filter_fn and not filter_fn(doc.metadata):
                continue

            sim = self._cosine_similarity(query_embedding, doc.embedding)
            similarities.append((sim, doc))

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[0], reverse=True)

        return [
            {"document": doc, "similarity": sim}
            for sim, doc in similarities[:top_k]
        ]

    def delete(self, doc_id: str) -> bool:
        """Delete a document by ID."""
        for i, doc in enumerate(self.vectors):
            if doc.id == doc_id:
                self.vectors.pop(i)
                return True
        return False

    def clear(self) -> None:
        """Clear all documents."""
        self.vectors = []

    def stats(self) -> Dict[str, Any]:
        """Get store statistics."""
        return {
            "total_documents": len(self.vectors),
            "dimension": self.dimension,
            "memory_mb": sum(
                len(doc.embedding) * 8 if doc.embedding else 0
                for doc in self.vectors
            ) / (1024 * 1024),
        }

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)


class TextSplitter:
    """Split text into chunks for embedding."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separator: str = "\n",
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separator = separator

    def split(self, text: str) -> List[str]:
        """Split text into overlapping chunks."""
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - self.chunk_overlap

        return chunks

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """Split documents into smaller chunks."""
        result = []
        for doc in documents:
            chunks = self.split(doc.content)
            for i, chunk in enumerate(chunks):
                result.append(Document(
                    id=f"{doc.id}_chunk_{i}",
                    content=chunk,
                    metadata={**doc.metadata, "parent_id": doc.id, "chunk_index": i},
                ))
        return result


class RAGPipeline:
    """
    Complete RAG pipeline for question answering.

    Combines document retrieval with LLM generation.
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        text_splitter: Optional[TextSplitter] = None,
        embedding_model: str = "text-embedding-3-small",
        llm_model: str = "gpt-4o",
    ):
        self.vector_store = vector_store or VectorStore()
        self.text_splitter = text_splitter or TextSplitter()
        self.embedding_model = embedding_model
        self.llm_model = llm_model
        self.index_stats: Dict[str, Any] = {}

    def ingest(
        self,
        documents: List[Document],
        batch_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Ingest documents into the knowledge base.

        Args:
            documents: List of documents to ingest.
            batch_size: Number of documents to process at once.

        Returns:
            Ingestion statistics.
        """
        start_time = time.time()

        # Split documents
        chunks = self.text_splitter.split_documents(documents)

        # Generate embeddings (simulated)
        import random
        for chunk in chunks:
            chunk.embedding = [random.random() for _ in range(1536)]

        # Add to vector store
        self.vector_store.add_batch(chunks)

        elapsed = time.time() - start_time
        self.index_stats = {
            "documents_ingested": len(documents),
            "chunks_created": len(chunks),
            "total_documents": len(self.vector_store.vectors),
            "elapsed_seconds": elapsed,
            "docs_per_second": len(documents) / elapsed if elapsed > 0 else 0,
        }

        return self.index_stats

    def ingest_files(
        self,
        file_paths: List[str],
        encoding: str = "utf-8",
    ) -> Dict[str, Any]:
        """Ingest text files from disk."""
        documents = []
        for path in file_paths:
            p = Path(path)
            if p.exists():
                content = p.read_text(encoding=encoding)
                documents.append(Document(
                    id=p.stem,
                    content=content,
                    metadata={"source": str(p), "type": p.suffix},
                ))
        return self.ingest(documents)

    def query(
        self,
        question: str,
        top_k: int = 5,
        include_metadata: bool = True,
    ) -> Dict[str, Any]:
        """
        Query the knowledge base.

        Args:
            question: The query question.
            top_k: Number of documents to retrieve.
            include_metadata: Whether to include document metadata.

        Returns:
            Query results with relevant documents.
        """
        # Generate query embedding (simulated)
        import random
        query_embedding = [random.random() for _ in range(1536)]

        # Search
        results = self.vector_store.search(query_embedding, top_k)

        # Format results
        contexts = []
        for r in results:
            doc = r["document"]
            contexts.append(doc.content)

        return {
            "question": question,
            "contexts": contexts,
            "results": [
                {
                    "content": r["document"].content,
                    "similarity": r["similarity"],
                    "metadata": r["document"].metadata if include_metadata else None,
                }
                for r in results
            ],
            "num_results": len(results),
        }

    def generate_answer(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Generate an answer using RAG.

        Args:
            question: The query question.
            top_k: Number of documents to retrieve.

        Returns:
            Generated answer with sources.
        """
        # Retrieve relevant documents
        query_result = self.query(question, top_k)

        # Build prompt with context
        context_text = "\n\n".join(query_result["contexts"])
        prompt = f"""Based on the following context, answer the question.

Context:
{context_text}

Question: {question}

Answer:"""

        # In production, this would call an LLM
        # For now, return the retrieved context
        return {
            "question": question,
            "answer": f"[RAG Answer based on {len(query_result['results'])} sources]",
            "sources": query_result["results"],
            "prompt": prompt,
            "model": self.llm_model,
        }

    def clear_index(self) -> None:
        """Clear the entire index."""
        self.vector_store.clear()
        self.index_stats = {}


class HybridSearch:
    """Combine keyword and vector search."""

    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store

    def search(
        self,
        query: str,
        query_embedding: List[float],
        top_k: int = 5,
        alpha: float = 0.5,
    ) -> List[Dict]:
        """
        Hybrid search combining keyword and vector similarity.

        Args:
            query: Text query for keyword search.
            query_embedding: Embedding for vector search.
            top_k: Number of results.
            alpha: Weight for vector search (0=keyword only, 1=vector only).

        Returns:
            Combined search results.
        """
        # Vector search
        vector_results = self.vector_store.search(query_embedding, top_k * 2)

        # Keyword search (simple)
        keyword_results = []
        for doc in self.vector_store.vectors:
            score = self._keyword_score(query, doc.content)
            keyword_results.append((score, doc))
        keyword_results.sort(key=lambda x: x[0], reverse=True)

        # Combine using reciprocal rank fusion
        combined = self._reciprocal_rank_fusion(
            vector_results,
            [(doc, score) for score, doc in keyword_results],
            alpha,
            top_k,
        )

        return combined

    @staticmethod
    def _keyword_score(query: str, text: str) -> float:
        """Simple keyword overlap score."""
        query_words = set(query.lower().split())
        text_words = set(text.lower().split())
        if not text_words:
            return 0.0
        return len(query_words & text_words) / len(query_words)

    @staticmethod
    def _reciprocal_rank_fusion(
        vector_results: List[Dict],
        keyword_results: List,
        alpha: float,
        top_k: int,
    ) -> List[Dict]:
        """Combine results using RRF."""
        scores = {}

        for i, r in enumerate(vector_results):
            doc_id = r["document"].id
            scores[doc_id] = scores.get(doc_id, 0) + alpha / (i + 1)

        for i, (doc, _) in enumerate(keyword_results):
            doc_id = doc.id
            scores[doc_id] = scores.get(doc_id, 0) + (1 - alpha) / (i + 1)

        # Sort and return top_k
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [{"doc_id": doc_id, "score": score} for doc_id, score in sorted_docs[:top_k]]
