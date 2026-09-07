"""A deterministic document-retrieval worker; it deliberately has no LLM.

Features a resilient dual-mode architecture:
1. Production Mode: Full BGE-M3 dense + sparse hybrid vector search in Qdrant
   with BGE-Reranker-v2-M3 cross-encoder scoring and Docling document conversion.
2. Dev / Sovereign Local Mode: When Qdrant or heavy neural models are offline,
   transparently uses PyMuPDF, markdown/text parsers, and SQLite BM25/token
   scoring so document search and grounding work reliably without multi-gigabyte models.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf as fitz  # PyMuPDF for reliable local PDF extraction

try:
    from docling.document_converter import DocumentConverter
    _DOCLING_AVAILABLE = True
except ImportError:
    _DOCLING_AVAILABLE = False

try:
    from FlagEmbedding import BGEM3FlagModel, FlagReranker
    _FLAG_EMBEDDING_AVAILABLE = True
except ImportError:
    _FLAG_EMBEDDING_AVAILABLE = False

try:
    from qdrant_client import QdrantClient, models
    _QDRANT_AVAILABLE = True
except ImportError:
    _QDRANT_AVAILABLE = False


@dataclass(frozen=True)
class Settings:
    """Runtime settings, all controllable without code changes."""
    data_dir: Path = Path(os.getenv("DATA_DIR", "./data"))
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    collection: str = "knowledge_chunks"
    embed_model_name: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    rerank_model_name: str = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
    chunk_size: int = 1200
    chunk_overlap: int = 180
    candidate_limit: int = 20


class DuplicateFileError(RuntimeError):
    pass


class RetrievalWorker:
    """Ingests files and returns ranked evidence chunks; source of truth for RAG."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.settings.data_dir / "registry.sqlite3"
        
        # 1. Document Converter
        self.converter = DocumentConverter() if _DOCLING_AVAILABLE else None
        
        # 2. Embedding & Reranker Models
        self.embedder = None
        self.reranker = None
        if _FLAG_EMBEDDING_AVAILABLE:
            try:
                self.embedder = BGEM3FlagModel(self.settings.embed_model_name, use_fp16=True)
                self.reranker = FlagReranker(self.settings.rerank_model_name, use_fp16=True)
            except Exception:
                self.embedder = None
                self.reranker = None

        # 3. Qdrant Client
        self.qdrant = None
        if _QDRANT_AVAILABLE and self.embedder is not None:
            try:
                client = QdrantClient(url=self.settings.qdrant_url, timeout=2.0)
                client.get_collections()  # Test connection
                self.qdrant = client
            except Exception:
                self.qdrant = None

        self._initialize_sqlite()
        if self.qdrant is not None:
            self._initialize_collection()

    # ------------------------------------------------------------------ #
    # SQLite: registry, chunk cache & local fallback index
    # ------------------------------------------------------------------ #

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_sqlite(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL UNIQUE,
                    sha256 TEXT NOT NULL UNIQUE,
                    media_type TEXT,
                    chunk_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_files_sha256 ON files(sha256);

                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    media_type TEXT,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_file_id ON chunks(file_id);
                """
            )

    def _initialize_collection(self) -> None:
        if self.qdrant is not None:
            try:
                if not self.qdrant.collection_exists(self.settings.collection):
                    self.qdrant.create_collection(
                        collection_name=self.settings.collection,
                        vectors_config={
                            "dense": models.VectorParams(size=1024, distance=models.Distance.COSINE)
                        },
                        sparse_vectors_config={
                            "sparse": models.SparseVectorParams()
                        },
                    )
            except Exception:
                self.qdrant = None

    @staticmethod
    def _sha256(file_path: Path) -> str:
        digest = hashlib.sha256()
        with file_path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def _delete_file_records(self, file_id: str) -> None:
        if self.qdrant is not None:
            try:
                self.qdrant.delete(
                    collection_name=self.settings.collection,
                    points_selector=models.FilterSelector(
                        filter=models.Filter(must=[models.FieldCondition(key="file_id", match=models.MatchValue(value=file_id))])
                    ),
                    wait=True,
                )
            except Exception:
                pass

        with self._connection() as connection:
            connection.execute("DELETE FROM chunks WHERE file_id = ?", (file_id,))
            connection.execute("DELETE FROM files WHERE id = ?", (file_id,))

    # ------------------------------------------------------------------ #
    # Extraction + chunking
    # ------------------------------------------------------------------ #

    def _extract_text(self, file_path: Path) -> str:
        # 1. Try Docling if available
        if self.converter is not None:
            try:
                result = self.converter.convert(str(file_path))
                text = result.document.export_to_markdown()
                if text.strip():
                    return text
            except Exception:
                pass

        # 2. PyMuPDF for PDFs
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            try:
                with fitz.open(file_path) as pdf:
                    text = "\n".join(page.get_text("text") for page in pdf)
                if text.strip():
                    return text
            except Exception as err:
                raise RuntimeError(f"PyMuPDF failed on {file_path.name}: {err}") from err

        # 3. Direct text / markdown / notes read
        if suffix in {".md", ".txt", ".json", ".log"}:
            try:
                return file_path.read_text(encoding="utf-8", errors="replace")
            except Exception as err:
                raise RuntimeError(f"Could not read text file {file_path.name}: {err}") from err

        # 4. Fallback for docx
        if suffix == ".docx":
            try:
                from docx import Document
                doc = Document(str(file_path))
                lines = [p.text for p in doc.paragraphs if p.text.strip()]
                for t in doc.tables:
                    for row in t.rows:
                        lines.append(" | ".join(cell.text.strip() for cell in row.cells))
                text = "\n".join(lines)
                if text.strip():
                    return text
            except Exception as err:
                raise RuntimeError(f"Could not extract docx {file_path.name}: {err}") from err

        raise RuntimeError(f"No extractable text found in {file_path.name}")

    def _text_chunks(self, text: str) -> list[str]:
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if not text:
            return []
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self.settings.chunk_size, len(text))
            if end < len(text):
                boundary = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
                if boundary > start + self.settings.chunk_size // 2:
                    end = boundary + 1
            chunks.append(text[start:end].strip())
            if end == len(text):
                break
            start = end - self.settings.chunk_overlap
        return [chunk for chunk in chunks if chunk]

    # ------------------------------------------------------------------ #
    # Ingestion
    # ------------------------------------------------------------------ #

    def ingest(self, file_path: str | Path, media_type: str | None = None) -> dict[str, Any]:
        path = Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Not a readable file: {path}")
        source_name = path.name
        file_hash = self._sha256(path)

        with self._connection() as connection:
            hash_match = connection.execute(
                "SELECT source_name FROM files WHERE sha256 = ?", (file_hash,)
            ).fetchone()
            if hash_match:
                raise DuplicateFileError(f"Identical content already indexed as {hash_match['source_name']}")
            name_match = connection.execute(
                "SELECT id FROM files WHERE source_name = ?", (source_name,)
            ).fetchone()

        if name_match:
            self._delete_file_records(name_match["id"])

        text = self._extract_text(path)
        chunks = self._text_chunks(text)

        if not chunks:
            raise RuntimeError(f"No searchable content in {source_name}")

        file_id = str(uuid.uuid4())
        m_type = media_type or "document"

        # 1. Always store chunks into SQLite for local durability & fallback search
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO files(id, source_name, sha256, media_type, chunk_count) VALUES (?, ?, ?, ?, ?)",
                (file_id, source_name, file_hash, m_type, len(chunks)),
            )
            for idx, c_text in enumerate(chunks):
                connection.execute(
                    "INSERT INTO chunks(id, file_id, source_name, chunk_index, media_type, text) VALUES (?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), file_id, source_name, idx, m_type, c_text),
                )

        # 2. If Qdrant + BGE-M3 available, also write vector embeddings
        if self.qdrant is not None and self.embedder is not None:
            try:
                res = self.embedder.encode(chunks, batch_size=8, max_length=8192, return_dense=True, return_sparse=True)
                dense_vectors = [v.tolist() for v in res["dense_vecs"]]
                sparse_weights = res["lexical_weights"]

                points = []
                for index, chunk in enumerate(chunks):
                    weights = sparse_weights[index]
                    s_vec = models.SparseVector(
                        indices=[int(k) for k in weights.keys()] if weights else [0],
                        values=[float(v) for v in weights.values()] if weights else [0.0]
                    )
                    points.append(
                        models.PointStruct(
                            id=str(uuid.uuid4()),
                            vector={"dense": dense_vectors[index], "sparse": s_vec},
                            payload={
                                "file_id": file_id,
                                "source_name": source_name,
                                "chunk_index": index,
                                "media_type": m_type,
                                "text": chunk,
                            },
                        )
                    )
                self.qdrant.upsert(collection_name=self.settings.collection, points=points, wait=True)
            except Exception:
                pass  # Fallback to SQLite chunks intact

        return {
            "file_id": file_id,
            "source_name": source_name,
            "chunks_indexed": len(chunks),
            "updated": bool(name_match),
        }

    # ------------------------------------------------------------------ #
    # Retrieval: hybrid neural or resilient local BM25 scoring
    # ------------------------------------------------------------------ #

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        if not query.strip():
            return []

        # Mode A: High-end Qdrant + BGE-M3 + Cross-Reranker (if GPU server environment ready)
        if self.qdrant is not None and self.embedder is not None and self.reranker is not None:
            try:
                res = self.embedder.encode([query], batch_size=1, max_length=8192, return_dense=True, return_sparse=True)
                dense_vector = res["dense_vecs"][0].tolist()
                weights = res["lexical_weights"][0]
                sparse_vector = models.SparseVector(
                    indices=[int(k) for k in weights.keys()] if weights else [0],
                    values=[float(v) for v in weights.values()] if weights else [0.0]
                )

                hits = self.qdrant.query_points(
                    collection_name=self.settings.collection,
                    prefetch=[
                        models.Prefetch(query=dense_vector, using="dense", limit=self.settings.candidate_limit),
                        models.Prefetch(query=sparse_vector, using="sparse", limit=self.settings.candidate_limit),
                    ],
                    query=models.FusionQuery(fusion=models.Fusion.RRF),
                    limit=self.settings.candidate_limit,
                    with_payload=True,
                ).points

                if hits:
                    pairs = [[query, hit.payload["text"]] for hit in hits]
                    scores = self.reranker.compute_score(pairs, normalize=True)
                    if isinstance(scores, float):
                        scores = [scores]
                    ranked = sorted(zip(hits, scores), key=lambda pair: pair[1], reverse=True)
                    top = ranked[: max(1, min(limit, self.settings.candidate_limit))]
                    return [
                        {
                            "source_name": hit.payload["source_name"],
                            "chunk_index": hit.payload["chunk_index"],
                            "media_type": hit.payload.get("media_type"),
                            "text": hit.payload["text"],
                            "hybrid_score": hit.score,
                            "rerank_score": float(score),
                        }
                        for hit, score in top
                    ]
            except Exception:
                pass

        # Mode B: Resilient Local BM25 / Keyword Scoring over SQLite chunks
        return self._search_sqlite_local(query, limit=limit)

    def _search_sqlite_local(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Fast keyword/token scoring over indexed chunks in local SQLite."""
        tokens = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
        if not tokens:
            return []

        with self._connection() as connection:
            rows = connection.execute("SELECT source_name, chunk_index, media_type, text FROM chunks").fetchall()

        if not rows:
            return []

        scored: list[tuple[dict[str, Any], float]] = []
        for r in rows:
            text = r["text"]
            text_lower = text.lower()
            score = 0.0
            for token in tokens:
                count = text_lower.count(token)
                if count > 0:
                    score += 1.0 + (0.3 * count)
            if score > 0:
                scored.append((
                    {
                        "source_name": r["source_name"],
                        "chunk_index": r["chunk_index"],
                        "media_type": r["media_type"],
                        "text": text,
                        "hybrid_score": round(score, 2),
                        "rerank_score": round(min(score / (len(tokens) * 2.0), 1.0), 3),
                    },
                    score,
                ))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in scored[:limit]]

    def list_files(self) -> list[dict[str, Any]]:
        with closing(self._connection()) as connection:
            rows = connection.execute(
                "SELECT source_name, sha256, media_type, chunk_count, created_at FROM files ORDER BY created_at"
            ).fetchall()
        return [dict(row) for row in rows]