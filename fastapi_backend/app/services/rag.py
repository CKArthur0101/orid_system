"""
RAG service for ORID chatbot.
Embeds book_pack content and retrieves relevant chunks for each student message.
Uses OpenAI text-embedding-3-small + in-memory cosine similarity (pure Python, no numpy).
"""
from __future__ import annotations

import math
import os
from typing import Any, Optional

from openai import AsyncOpenAI
from app.services.rag_faiss import get_relevant_context_faiss, is_faiss_ready

OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
_client: Optional[AsyncOpenAI] = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

EMBEDDING_MODEL = "text-embedding-3-small"
ORID_RAG_BACKEND = (os.getenv("ORID_RAG_BACKEND") or "auto").strip().lower()


def rag_in_feedback_enabled() -> bool:
    """Whether genai feedback prompts should call vector retrieval."""
    v = (os.getenv("ORID_RAG_IN_FEEDBACK") or "true").strip().lower()
    return v not in {"0", "false", "off", "no"}


def format_rag_context_for_prompt(rag_text: str) -> str:
    raw = (rag_text or "").strip()
    if not raw:
        return ""
    return (
        "【與本則草稿最相關的教材片段（向量檢索；須與上方摘要一致，不可編造新情節）】\n"
        f"{raw}"
    ).strip()


_embed_cache: dict[str, tuple[list[str], list[list[float]]]] = {}


def _embed_cache_key(book_pack: dict[str, Any]) -> str:
    """Invalidate cache when title or versioned content changes."""
    title = str(book_pack.get("book_title") or "unknown").strip()
    ver = str(book_pack.get("version") or book_pack.get("book_pack_version") or "1")
    return f"{title}::v{ver}"


def _build_chunks_from_book_pack(book_pack: dict[str, Any]) -> list[str]:
    """Break a book_pack into meaningful text chunks for embedding."""
    chunks: list[str] = []
    title = str(book_pack.get("book_title") or "").strip()

    excerpts = book_pack.get("story_excerpts") or []
    if isinstance(excerpts, list):
        for i, ex in enumerate(excerpts):
            s = str(ex or "").strip()
            if s:
                chunks.append(f"【故事摘錄{i + 1}】{s}")

    for char in book_pack.get("characters") or []:
        if isinstance(char, dict):
            name = str(char.get("name") or "").strip()
            role = str(char.get("role") or "").strip()
            if name and role:
                chunks.append(f"角色「{name}」：{role}。")
            elif name:
                chunks.append(f"角色「{name}」。")

    for event in book_pack.get("key_events") or []:
        e = str(event or "").strip()
        if e:
            chunks.append(e)

    themes = book_pack.get("core_theme") or []
    if isinstance(themes, list) and themes:
        theme_str = "、".join(str(t).strip() for t in themes if str(t).strip())
        if theme_str:
            chunks.append(f"故事的核心主題包括：{theme_str}。")

    settings = book_pack.get("setting") or []
    if isinstance(settings, list) and settings:
        setting_str = "、".join(str(s).strip() for s in settings if str(s).strip())
        if setting_str:
            chunks.append(f"故事場景：{setting_str}。")

    if title:
        chunks.append(f"這本書叫做《{title}》。")

    writing_guide = book_pack.get("writing_guide") or {}
    if isinstance(writing_guide, dict):
        for stage_key in ("O", "R", "I", "D"):
            guide = str(writing_guide.get(stage_key) or "").strip()
            if guide:
                chunks.append(f"{stage_key}階段寫作提示：{guide}")

    return [c for c in chunks if c.strip()]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v)) or 1e-9


def _cosine_sim(a: list[float], b: list[float]) -> float:
    return _dot(a, b) / (_norm(a) * _norm(b))


async def _embed_texts(texts: list[str]) -> Optional[list[list[float]]]:
    if not _client or not texts:
        return None
    try:
        resp = await _client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
        return [item.embedding for item in resp.data]
    except Exception as e:
        print(f"[RAG] embedding failed: {e}")
        return None


async def _embed_query(query: str) -> Optional[list[float]]:
    if not _client or not query.strip():
        return None
    try:
        resp = await _client.embeddings.create(model=EMBEDDING_MODEL, input=[query.strip()])
        return resp.data[0].embedding
    except Exception as e:
        print(f"[RAG] query embedding failed: {e}")
        return None


async def _ensure_book_embedded(
    book_pack: dict[str, Any],
) -> tuple[list[str], Optional[list[list[float]]]]:
    key = _embed_cache_key(book_pack)
    if key in _embed_cache:
        return _embed_cache[key]

    chunks = _build_chunks_from_book_pack(book_pack)
    if not chunks:
        return [], None

    vecs = await _embed_texts(chunks)
    if vecs is not None:
        _embed_cache[key] = (chunks, vecs)
    return chunks, vecs


async def get_relevant_context(
    book_pack: Optional[dict[str, Any]],
    query: str,
    top_k: int = 3,
) -> str:
    """
    Retrieve the most relevant book chunks for a student's message.
    Returns formatted context string, or empty string on failure.
    """
    if not book_pack or not isinstance(book_pack, dict):
        return ""
    if not query or not query.strip():
        return ""

    backend = ORID_RAG_BACKEND
    if backend not in {"auto", "memory", "faiss"}:
        backend = "auto"

    if backend in {"auto", "faiss"} and is_faiss_ready():
        try:
            faiss_ctx = await get_relevant_context_faiss(book_pack, query, top_k=top_k)
            if faiss_ctx:
                return faiss_ctx
            if backend == "faiss":
                return ""
        except Exception as e:
            print(f"[RAG] faiss backend failed: {e}")
            if backend == "faiss":
                return ""

    chunks, doc_vecs = await _ensure_book_embedded(book_pack)
    if not chunks or doc_vecs is None:
        return ""

    query_vec = await _embed_query(query)
    if query_vec is None:
        return ""

    scored = [(i, _cosine_sim(query_vec, dv)) for i, dv in enumerate(doc_vecs)]
    scored.sort(key=lambda x: x[1], reverse=True)

    results: list[str] = []
    for idx, sim in scored[:top_k]:
        if sim > 0.15:
            results.append(f"「{chunks[idx]}」")

    return "\n".join(results)


async def get_feedback_rag_context(
    book_pack: Optional[dict[str, Any]],
    student_text: str,
    *,
    stage: str,
    top_k: int = 3,
) -> str:
    """Retrieve book chunks for the writing-feedback LLM (O/R/I only)."""
    if not rag_in_feedback_enabled():
        return ""
    stage_up = (stage or "O").strip().upper()
    if stage_up == "D" or not book_pack:
        return ""
    query = (student_text or "").strip()
    if not query:
        return ""
    return await get_relevant_context(book_pack, query, top_k=top_k)
