import json

import faiss
import numpy as np
import pytest

from app.services import rag, rag_faiss


def _build_tiny_index(vectors: list[list[float]], path):
    arr = np.asarray(vectors, dtype="float32")
    faiss.normalize_L2(arr)
    index = faiss.IndexFlatIP(arr.shape[1])
    index.add(arr)
    faiss.write_index(index, str(path))


@pytest.mark.asyncio
async def test_get_relevant_context_faiss_reads_bundle_and_formats_pages(monkeypatch, tmp_path):
    bundle_dir = tmp_path / "week_1"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    index_path = bundle_dir / "index.faiss"
    meta_path = bundle_dir / "meta.json"

    _build_tiny_index(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        index_path,
    )
    meta = {
        "schema": "orid_faiss_meta_v1",
        "bundle_id": "week_1",
        "version": 3,
        "chunks": [
            {"chunk_id": "c1", "text": "第一段內容", "page": 3, "source": "fixture"},
            {"chunk_id": "c2", "text": "第二段內容", "page": 5, "source": "fixture"},
            {"chunk_id": "c3", "text": "第三段內容", "page": 8, "source": "fixture"},
        ],
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setenv("ORID_EMBEDDINGS_DIR", str(tmp_path))
    monkeypatch.setattr(rag_faiss, "_BUNDLE_CACHE", {})

    async def fake_embed_query(_query: str, **_kwargs):
        return [1.0, 0.0, 0.0]

    monkeypatch.setattr(rag_faiss, "_embed_query", fake_embed_query)
    out = await rag_faiss.get_relevant_context_faiss(
        {"embedding_bundle_id": "week_1", "version": 3},
        "測試問題",
        top_k=2,
    )
    assert "【P3】第一段內容" in out
    assert "第二段內容" not in out


@pytest.mark.asyncio
async def test_get_relevant_context_auto_falls_back_to_memory(monkeypatch):
    book_pack = {
        "book_title": "測試書",
        "version": 1,
        "key_events": ["小明先看見了柿子樹", "後來大家一起分享柿子"],
        "story_excerpts": ["柿子樹很高，葉子很多。"],
    }

    monkeypatch.setattr(rag, "ORID_RAG_BACKEND", "auto")
    monkeypatch.setattr(rag, "is_faiss_ready", lambda: False)

    async def fake_embed_texts(texts):
        vecs = []
        for text in texts:
            if "柿子樹" in text:
                vecs.append([1.0, 0.0])
            else:
                vecs.append([0.0, 1.0])
        return vecs

    async def fake_embed_query(_query: str):
        return [1.0, 0.0]

    monkeypatch.setattr(rag, "_embed_texts", fake_embed_texts)
    monkeypatch.setattr(rag, "_embed_query", fake_embed_query)
    monkeypatch.setattr(rag, "_embed_cache", {})

    out = await rag.get_relevant_context(book_pack, "柿子樹", top_k=1)
    assert "柿子樹" in out
