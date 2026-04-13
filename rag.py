"""
RAG (Retrieval-Augmented Generation) module for knowledge base.

Parses knowledge.md into Q&A chunks, embeds them via OpenAI,
and retrieves top-K relevant chunks for any user query.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

import numpy as np
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_KNOWLEDGE_PATH = Path(__file__).parent / "knowledge.md"
_CACHE_PATH = Path(__file__).parent / "embeddings_cache.json"

EMBED_MODEL = "text-embedding-3-small"
TOP_K = 5


def _strip_md(text: str) -> str:
    """Remove markdown formatting from knowledge base text."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'\*(.+?)\*', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = text.replace('**', '')
    return text


def _parse_qa_chunks(text: str) -> list[dict]:
    """Parse knowledge.md into Q&A chunks with section context."""
    chunks = []
    current_section = ""
    current_subsection = ""

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Track section headers
        if line.startswith("## "):
            current_section = line.lstrip("# ").strip()
            current_subsection = ""
            i += 1
            continue
        if line.startswith("### "):
            current_subsection = line.lstrip("# ").strip()
            i += 1
            continue

        # Find Q&A pairs
        if line.startswith("**Сұрақ:**"):
            question = line.replace("**Сұрақ:**", "").strip()

            # Collect answer lines
            answer_lines = []
            i += 1
            while i < len(lines):
                aline = lines[i].strip()
                if aline.startswith("**Сұрақ:**") or aline.startswith("## ") or aline.startswith("### "):
                    break
                if aline.startswith("**Жауап:**"):
                    aline = aline.replace("**Жауап:**", "").strip()
                if aline or answer_lines:
                    answer_lines.append(lines[i])
                i += 1

            while answer_lines and not answer_lines[-1].strip():
                answer_lines.pop()

            answer = _strip_md("\n".join(answer_lines))
            question = _strip_md(question)

            section_label = current_section
            if current_subsection:
                section_label = f"{current_section} > {current_subsection}"
            section_label = _strip_md(section_label)

            chunk_text = f"[{section_label}]\nСұрақ: {question}\nЖауап: {answer}"

            chunks.append({
                "section": section_label,
                "question": question,
                "answer": answer,
                "text": chunk_text,
            })
            continue

        i += 1

    return chunks


class KnowledgeRAG:
    """Vector-search over the knowledge base."""

    def __init__(self, client: AsyncOpenAI):
        self.client = client
        self.chunks: list[dict] = []
        self.embeddings: Optional[np.ndarray] = None
        self._ready = False

    async def init(self) -> None:
        """Parse knowledge base and build/load embeddings."""
        knowledge_text = _KNOWLEDGE_PATH.read_text(encoding="utf-8")
        self.chunks = _parse_qa_chunks(knowledge_text)
        logger.info("Parsed %d Q&A chunks from knowledge.md", len(self.chunks))

        if self._load_cache():
            logger.info("Loaded embeddings from cache (%d vectors)", len(self.chunks))
            self._ready = True
            return

        logger.info("Building embeddings for %d chunks...", len(self.chunks))
        texts = [chunk["text"] for chunk in self.chunks]

        response = await self.client.embeddings.create(
            model=EMBED_MODEL,
            input=texts,
        )

        vectors = [item.embedding for item in response.data]
        self.embeddings = np.array(vectors, dtype=np.float32)

        self._save_cache()
        logger.info("Embeddings built and cached.")
        self._ready = True

    def _load_cache(self) -> bool:
        if not _CACHE_PATH.exists():
            return False
        try:
            cache = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
            if len(cache["vectors"]) != len(self.chunks):
                logger.info("Cache invalidated: chunk count changed")
                return False
            if (cache.get("first_q") != self.chunks[0]["question"] or
                    cache.get("last_q") != self.chunks[-1]["question"]):
                logger.info("Cache invalidated: questions changed")
                return False
            self.embeddings = np.array(cache["vectors"], dtype=np.float32)
            return True
        except Exception as e:
            logger.warning("Failed to load cache: %s", e)
            return False

    def _save_cache(self) -> None:
        if self.embeddings is None:
            return
        cache = {
            "first_q": self.chunks[0]["question"] if self.chunks else "",
            "last_q": self.chunks[-1]["question"] if self.chunks else "",
            "vectors": self.embeddings.tolist(),
        }
        _CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    async def search(self, query: str, top_k: int = TOP_K) -> str:
        """Find top_k most relevant Q&A chunks for the query."""
        if not self._ready or self.embeddings is None:
            logger.warning("RAG not initialized, returning empty context")
            return ""

        response = await self.client.embeddings.create(
            model=EMBED_MODEL,
            input=[query],
        )
        query_vec = np.array(response.data[0].embedding, dtype=np.float32)

        # Cosine similarity
        norms = np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_vec)
        norms = np.where(norms == 0, 1, norms)
        similarities = self.embeddings @ query_vec / norms

        top_indices = np.argsort(similarities)[-top_k:][::-1]

        results = []
        for idx in top_indices:
            score = similarities[idx]
            if score < 0.3:
                continue
            results.append(self.chunks[idx]["text"])

        if not results:
            return ""

        return "\n\n---\n\n".join(results)
