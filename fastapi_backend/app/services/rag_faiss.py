"""
FAISS-backed retrieval for ORID chatbot.

Loads persisted index + metadata from shared-data and returns context snippets
compatible with existing `get_relevant_context` output style.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from openai import AsyncOpenAI
from app.services.embedding_fallback import hash_embed_text

try:
    import faiss  # type: ignore
    import numpy as np
except Exception:  # pragma: no cover - optional dependency/runtime
    faiss = None
    np = None


OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
_client: Optional[AsyncOpenAI] = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

EMBEDDING_MODEL = "text-embedding-3-small"
META_SCHEMA = "orid_faiss_meta_v1"
DEFAULT_EMBEDDINGS_DIR = "/app/shared-data/embeddings"
DEFAULT_MIN_SIMILARITY = float(os.getenv("ORID_RAG_FAISS_MIN_SIMILARITY", "0.15"))
ORID_RAG_FAISS_TOP_K_MAX = max(1, int(os.getenv("ORID_RAG_FAISS_TOP_K_MAX", "8")))


@dataclass
class _FaissBundle:
    index: Any
    chunks: list[dict[str, Any]]
    version: int
    embedding_provider: str
    embedding_model: str
    embedding_dim: int
    index_mtime_ns: int
    meta_mtime_ns: int


_BUNDLE_CACHE: dict[str, _FaissBundle] = {}


def is_faiss_ready() -> bool:
    return bool(faiss is not None and np is not None)


def _embeddings_root() -> Path:
    custom = (os.getenv("ORID_EMBEDDINGS_DIR") or "").strip()
    if custom:
        return Path(custom)
    return Path(DEFAULT_EMBEDDINGS_DIR)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _extract_week_from_book_pack(book_pack: dict[str, Any]) -> Optional[int]:
    week = _safe_int(book_pack.get("week"), 0)
    if week > 0:
        return week
    title = str(book_pack.get("reading_title") or "")
    m = re.search(r"第\s*(\d+)\s*週", title)
    if m:
        return _safe_int(m.group(1), 0) or None
    return None


def _resolve_bundle_id(book_pack: dict[str, Any]) -> Optional[str]:
    explicit = str(book_pack.get("embedding_bundle_id") or "").strip()
    if explicit:
        return explicit
    week = _extract_week_from_book_pack(book_pack)
    if week and week > 0:
        return f"week_{week}"
    return None


def _bundle_paths(bundle_id: str) -> tuple[Path, Path]:
    bundle_dir = _embeddings_root() / bundle_id
    return bundle_dir / "index.faiss", bundle_dir / "meta.json"


def _parse_meta(meta_path: Path) -> tuple[list[dict[str, Any]], int, str, str, int]:
    obj = json.loads(meta_path.read_text(encoding="utf-8"))
    if isinstance(obj, dict) and isinstance(obj.get("chunks"), list):
        chunks = [c for c in obj.get("chunks", []) if isinstance(c, dict)]
        return (
            chunks,
            _safe_int(obj.get("version"), 1),
            str(obj.get("embedding_provider") or "openai").strip().lower(),
            str(obj.get("embedding_model") or EMBEDDING_MODEL).strip(),
            _safe_int(obj.get("embedding_dim"), 1536),
        )
    if isinstance(obj, list):
        chunks: list[dict[str, Any]] = []
        for row in obj:
            if not isinstance(row, dict):
                continue
            text = str(row.get("text") or "").strip()
            if not text:
                continue
            chunks.append(
                {
                    "text": text,
                    "page": _safe_int(row.get("page"), 0) or None,
                    "chunk_id": str(row.get("chunk_id") or "").strip(),
                    "source": str(row.get("source") or "").strip(),
                }
            )
        return chunks, 1, "openai", EMBEDDING_MODEL, 1536
    return [], 1, "openai", EMBEDDING_MODEL, 1536


def _get_bundle(bundle_id: str) -> Optional[_FaissBundle]:
    if faiss is None:
        return None
    index_path, meta_path = _bundle_paths(bundle_id)
    if not index_path.exists() or not meta_path.exists():
        return None

    index_mtime_ns = index_path.stat().st_mtime_ns
    meta_mtime_ns = meta_path.stat().st_mtime_ns

    cached = _BUNDLE_CACHE.get(bundle_id)
    if cached and cached.index_mtime_ns == index_mtime_ns and cached.meta_mtime_ns == meta_mtime_ns:
        return cached

    try:
        index = faiss.read_index(str(index_path))
        chunks, version, provider, model_name, embedding_dim = _parse_meta(meta_path)
        if not chunks:
            return None
        # Keep index / metadata aligned.
        count = min(len(chunks), int(index.ntotal))
        if count <= 0:
            return None
        trimmed = chunks[:count]
        bundle = _FaissBundle(
            index=index,
            chunks=trimmed,
            version=version,
            embedding_provider=provider,
            embedding_model=model_name,
            embedding_dim=max(8, embedding_dim),
            index_mtime_ns=index_mtime_ns,
            meta_mtime_ns=meta_mtime_ns,
        )
        _BUNDLE_CACHE[bundle_id] = bundle
        return bundle
    except Exception as e:
        print(f"[RAG][faiss] load bundle failed ({bundle_id}): {e}")
        return None


async def _embed_query(query: str, *, provider: str, embedding_model: str, embedding_dim: int) -> Optional[list[float]]:
    if provider == "hash":
        return hash_embed_text(query, dim=embedding_dim)
    if not _client:
        return None
    q = (query or "").strip()
    if not q:
        return None
    try:
        model = embedding_model or EMBEDDING_MODEL
        resp = await _client.embeddings.create(model=model, input=[q])
        return resp.data[0].embedding
    except Exception as e:
        print(f"[RAG][faiss] query embedding failed: {e}")
        return None


def _format_context(rows: list[dict[str, Any]]) -> str:
    out: list[str] = []
    for row in rows:
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        page = _safe_int(row.get("page"), 0)
        if page > 0:
            out.append(f"「【P{page}】{text}」")
        else:
            out.append(f"「{text}」")
    return "\n".join(out)


async def get_relevant_context_faiss(
    book_pack: Optional[dict[str, Any]],
    query: str,
    top_k: int = 3,
) -> str:
    if faiss is None or np is None:
        return ""
    if not isinstance(book_pack, dict):
        return ""
    if not (query or "").strip():
        return ""

    bundle_id = _resolve_bundle_id(book_pack)
    if not bundle_id:
        return ""
    bundle = _get_bundle(bundle_id)
    if not bundle:
        return ""

    pack_version = _safe_int(book_pack.get("version") or book_pack.get("book_pack_version"), bundle.version)
    if pack_version > 0 and bundle.version > 0 and pack_version != bundle.version:
        # Keep deterministic behavior: fallback to memory path when versions mismatch.
        return ""

    query_vec = await _embed_query(
        query,
        provider=bundle.embedding_provider,
        embedding_model=bundle.embedding_model,
        embedding_dim=bundle.embedding_dim,
    )
    if not query_vec:
        return ""

    q_np = np.asarray(query_vec, dtype="float32").reshape(1, -1)
    faiss.normalize_L2(q_np)
    search_k = max(1, min(max(top_k, 1) * 3, ORID_RAG_FAISS_TOP_K_MAX))
    sims, idxs = bundle.index.search(q_np, search_k)

    picked: list[dict[str, Any]] = []
    for score, idx in zip(sims[0], idxs[0]):
        if idx < 0:
            continue
        if float(score) < DEFAULT_MIN_SIMILARITY:
            continue
        if idx >= len(bundle.chunks):
            continue
        picked.append(bundle.chunks[int(idx)])
        if len(picked) >= max(1, top_k):
            break
    return _format_context(picked)
