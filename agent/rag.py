"""
agent/rag.py — RAG pipeline: chunking, embedding, FAISS retrieval.

Documents are loaded once at startup, chunked, embedded with a local
sentence-transformer model, and stored in an in-memory FAISS index.
Each user query is embedded at request time and the top-k most similar
chunks are retrieved and injected into the LLM context window.

Embedding model: all-MiniLM-L6-v2 (~80 MB, CPU-only, no API key needed).
Vector index: FAISS IndexFlatIP (cosine similarity on L2-normalised vectors).
"""

import json
import logging
import re
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHUNK_SIZE      = 500    # characters per chunk
CHUNK_OVERLAP   = 60     # character overlap between adjacent chunks
PARA_MAX_SIZE   = 600    # max characters per paragraph chunk
MIN_SCORE       = 0.25   # minimum cosine similarity to include a chunk


# ── Data class ────────────────────────────────────────────────────────────────

@dataclass
class Chunk:
    """A single text chunk with its source label."""
    text:   str
    source: str   # e.g. "linkedin", "summary", "cv", "project:VRP Engine"


# ── RAG index ─────────────────────────────────────────────────────────────────

class RAGIndex:
    """In-memory FAISS vector index over all profile documents.

    Usage::

        rag = RAGIndex()
        rag.build(linkedin_text, summary_text, cv_pdf_path, projects_json_path)
        chunks = rag.retrieve("vehicle routing optimization", top_k=4)
    """

    def __init__(self) -> None:
        self._model  = None
        self._index  = None
        self._chunks: list[Chunk] = []

    # ── Lazy model loader ──────────────────────────────────────────────────────

    @property
    def model(self):
        """Load the embedding model on first access (cached after that)."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model: %s", EMBEDDING_MODEL)
            self._model = SentenceTransformer(EMBEDDING_MODEL)
            logger.info("Embedding model ready.")
        return self._model

    # ── Build ──────────────────────────────────────────────────────────────────

    def build(
        self,
        linkedin_text:      str,
        summary_text:       str,
        cv_pdf_path:        str,
        projects_json_path: str,
    ) -> None:
        """Chunk, embed, and index all documents.

        Safe to call even if some documents are missing — each source is
        loaded with an independent try/except so one failure doesn't abort
        the whole index.

        Args:
            linkedin_text:      Pre-extracted text from the LinkedIn PDF.
            summary_text:       Plain-text career summary.
            cv_pdf_path:        Path to the CV/resume PDF (may not exist).
            projects_json_path: Path to projects.json.
        """
        import faiss

        chunks: list[Chunk] = []

        # ── LinkedIn ───────────────────────────────────────────────────────
        if linkedin_text and linkedin_text.strip():
            added = self._chunk_text(linkedin_text, source="linkedin")
            chunks.extend(added)
            logger.info("LinkedIn: %d chunks", len(added))

        # ── Summary ────────────────────────────────────────────────────────
        if summary_text and summary_text.strip():
            added = self._chunk_paragraphs(summary_text, source="summary")
            chunks.extend(added)
            logger.info("Summary: %d chunks", len(added))

        # ── CV PDF (optional) ──────────────────────────────────────────────
        try:
            from pypdf import PdfReader
            reader   = PdfReader(cv_pdf_path)
            cv_text  = "".join(page.extract_text() or "" for page in reader.pages)
            if cv_text.strip():
                added = self._chunk_text(cv_text, source="cv")
                chunks.extend(added)
                logger.info("CV PDF: %d chunks", len(added))
        except FileNotFoundError:
            logger.info("CV PDF not found at %s — skipping.", cv_pdf_path)
        except Exception as exc:
            logger.warning("CV PDF load error: %s", exc)

        # ── Projects JSON ──────────────────────────────────────────────────
        try:
            with open(projects_json_path, encoding="utf-8") as fh:
                projects = json.load(fh)
            for p in projects:
                text = self._format_project(p)
                if text.strip():
                    label = f"project:{p.get('name', 'unknown')}"
                    chunks.append(Chunk(text=text, source=label))
            logger.info("Projects JSON: %d project chunks", len(projects))
        except FileNotFoundError:
            logger.info("projects.json not found at %s — skipping.", projects_json_path)
        except Exception as exc:
            logger.warning("projects.json load error: %s", exc)

        if not chunks:
            logger.warning("RAG: no chunks to index — retrieval will be disabled.")
            return

        self._chunks = chunks

        # ── Embed all chunks ───────────────────────────────────────────────
        texts      = [c.text for c in chunks]
        embeddings = self.model.encode(
            texts,
            show_progress_bar=False,
            normalize_embeddings=True,   # normalise → inner product = cosine sim
            batch_size=32,
        )
        embeddings = np.array(embeddings, dtype=np.float32)

        # ── Build FAISS index ──────────────────────────────────────────────
        dim          = embeddings.shape[1]
        self._index  = faiss.IndexFlatIP(dim)   # exact cosine search
        self._index.add(embeddings)

        sources = sorted(set(c.source for c in chunks))
        logger.info(
            "RAG index ready: %d chunks — sources: %s",
            len(chunks), ", ".join(sources),
        )

    # ── Retrieve ───────────────────────────────────────────────────────────────

    def retrieve(
        self,
        query:     str,
        top_k:     int   = 4,
        min_score: float = MIN_SCORE,
    ) -> list[Chunk]:
        """Return the top-k chunks most relevant to *query*.

        Args:
            query:     The user's message or a derived search query.
            top_k:     Maximum number of chunks to return.
            min_score: Minimum cosine similarity threshold (0–1).

        Returns:
            List of matching Chunk objects, ordered by relevance.
            Empty list if the index hasn't been built or nothing passes
            the score threshold.
        """
        if self._index is None or not self._chunks:
            return []

        q_emb = self.model.encode(
            [query],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        q_emb = np.array(q_emb, dtype=np.float32)

        scores, indices = self._index.search(q_emb, top_k)

        results: list[Chunk] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and float(score) >= min_score:
                results.append(self._chunks[int(idx)])

        logger.debug(
            "RAG retrieved %d/%d chunks for query: %.60s…",
            len(results), top_k, query,
        )
        return results

    # ── Chunking helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _chunk_text(
        text:    str,
        source:  str,
        size:    int = CHUNK_SIZE,
        overlap: int = CHUNK_OVERLAP,
    ) -> list[Chunk]:
        """Split *text* into overlapping fixed-size character chunks."""
        text = text.strip()
        if not text:
            return []
        chunks: list[Chunk] = []
        start = 0
        while start < len(text):
            chunk = text[start:start + size].strip()
            if chunk:
                chunks.append(Chunk(text=chunk, source=source))
            start += size - overlap
        return chunks

    @staticmethod
    def _chunk_paragraphs(
        text:     str,
        source:   str,
        max_size: int = PARA_MAX_SIZE,
    ) -> list[Chunk]:
        """Split *text* by blank lines, merging short paragraphs."""
        paras  = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
        chunks: list[Chunk] = []
        buf    = ""
        for para in paras:
            if len(buf) + len(para) + 2 <= max_size:
                buf = (buf + "\n\n" + para).strip()
            else:
                if buf:
                    chunks.append(Chunk(text=buf, source=source))
                buf = para
        if buf:
            chunks.append(Chunk(text=buf, source=source))
        return chunks

    @staticmethod
    def _format_project(p: dict) -> str:
        """Render a project dict as a plain-text paragraph for embedding."""
        parts: list[str] = [f"Project: {p.get('name', '')}"]
        if p.get("description"):
            parts.append(f"Description: {p['description']}")
        if p.get("tech"):
            parts.append(f"Technologies: {', '.join(p['tech'])}")
        if p.get("highlights"):
            parts.append("Key highlights:")
            parts.extend(f"  - {h}" for h in p["highlights"])
        if p.get("demo"):
            parts.append(f"Live demo: {p['demo']}")
        if p.get("url") and not p.get("private", True):
            parts.append(f"GitHub: {p['url']}")
        return "\n".join(parts)