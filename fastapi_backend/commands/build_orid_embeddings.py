from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

import faiss
import numpy as np
from openai import AsyncOpenAI

from app.services.embedding_fallback import hash_embed_texts

EMBEDDING_MODEL = "text-embedding-3-small"
META_SCHEMA = "orid_faiss_meta_v1"
DEFAULT_OUTPUT_ROOT = "/app/shared-data/embeddings"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _extract_page(text: str) -> Optional[int]:
    m = re.search(r"(?:第\s*(\d+)\s*頁|[【\[]?\s*P\s*(\d+)\s*[】\]]?)", text, flags=re.IGNORECASE)
    if not m:
        return None
    return _safe_int(m.group(1) or m.group(2), 0) or None


def _normalize_chunk_text(text: str) -> str:
    out = (text or "").strip()
    out = re.sub(r"\s+", " ", out).strip()
    out = re.sub(r"^(第\s*\d+\s*頁[:：]?)", "", out).strip()
    out = re.sub(r"^[【\[]\s*P\s*\d+\s*[】\]][:：]?", "", out, flags=re.IGNORECASE).strip()
    return out


def _chunk_from_plain_text(raw_text: str) -> list[dict[str, Any]]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n+", raw_text) if b.strip()]
    chunks: list[dict[str, Any]] = []
    for i, block in enumerate(blocks):
        page = _extract_page(block)
        text = _normalize_chunk_text(block)
        if not text:
            continue
        chunks.append(
            {
                "chunk_id": f"chunk_{i + 1:04d}",
                "text": text,
                "page": page,
                "source": "text",
            }
        )
    return chunks


def _chunks_from_book_pack(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("book_pack must be a JSON object")

    chunks: list[dict[str, Any]] = []
    seq = 1
    for i, ex in enumerate(obj.get("story_excerpts") or []):
        text = _normalize_chunk_text(str(ex or ""))
        if not text:
            continue
        page = _extract_page(text) or (i + 1)
        chunks.append(
            {
                "chunk_id": f"excerpt_{seq:04d}",
                "text": text,
                "page": page,
                "source": "story_excerpts",
            }
        )
        seq += 1

    for ev in obj.get("key_events") or []:
        text = _normalize_chunk_text(str(ev or ""))
        if not text:
            continue
        chunks.append(
            {
                "chunk_id": f"event_{seq:04d}",
                "text": text,
                "page": _extract_page(text),
                "source": "key_events",
            }
        )
        seq += 1
    return obj, chunks


def _resolve_bundle_id(week: Optional[int], bundle_id: Optional[str]) -> str:
    if bundle_id and bundle_id.strip():
        return bundle_id.strip()
    if week and week > 0:
        return f"week_{week}"
    raise ValueError("bundle_id is required when week is not provided")


async def _embed_chunks(texts: list[str], *, provider: str, hash_dim: int) -> tuple[list[list[float]], str]:
    if provider == "hash":
        return hash_embed_texts(texts, dim=hash_dim), "hash"

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for openai embedding generation")
    client = AsyncOpenAI(api_key=api_key)
    resp = await client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in resp.data], "openai"


async def _build_index(
    *,
    chunks: list[dict[str, Any]],
    output_dir: Path,
    version: int,
    bundle_id: str,
    source_path: str,
    provider: str,
    hash_dim: int,
) -> None:
    texts = [str(c.get("text") or "").strip() for c in chunks if str(c.get("text") or "").strip()]
    if not texts:
        raise ValueError("No valid chunks to embed")

    vecs, provider_name = await _embed_chunks(texts, provider=provider, hash_dim=hash_dim)
    arr = np.asarray(vecs, dtype="float32")
    faiss.normalize_L2(arr)
    dim = int(arr.shape[1])

    index = faiss.IndexFlatIP(dim)
    index.add(arr)

    output_dir.mkdir(parents=True, exist_ok=True)
    index_path = output_dir / "index.faiss"
    meta_path = output_dir / "meta.json"
    faiss.write_index(index, str(index_path))

    payload = {
        "schema": META_SCHEMA,
        "bundle_id": bundle_id,
        "embedding_provider": provider_name,
        "embedding_model": EMBEDDING_MODEL if provider_name == "openai" else "hash",
        "embedding_dim": dim,
        "metric": "cosine_via_inner_product",
        "version": int(version),
        "source_path": source_path,
        "chunks": chunks,
    }
    meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"index written: {index_path}")
    print(f"meta written : {meta_path}")
    print(f"   chunks       : {len(chunks)}")
    print(f"   dim          : {dim}")
    print(f"   version      : {version}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Build ORID FAISS embedding bundle.")
    parser.add_argument("--week", type=int, default=None, help="Week number used for default bundle_id.")
    parser.add_argument("--bundle-id", type=str, default=None, help="Explicit embedding bundle id.")
    parser.add_argument("--book-pack", type=str, default=None, help="Path to book_pack JSON.")
    parser.add_argument("--input", type=str, default=None, help="Path to plain text source file.")
    parser.add_argument("--version", type=int, default=None, help="Optional metadata version override.")
    parser.add_argument("--output-root", type=str, default=DEFAULT_OUTPUT_ROOT, help="Embedding root directory.")
    parser.add_argument(
        "--provider",
        type=str,
        choices=["openai", "hash"],
        default="openai",
        help="Embedding provider. Use hash for local/offline bootstrap.",
    )
    parser.add_argument("--hash-dim", type=int, default=256, help="Vector dimension for hash provider.")
    args = parser.parse_args()

    if not args.book_pack and not args.input:
        raise ValueError("Either --book-pack or --input must be provided")

    bundle_id = _resolve_bundle_id(args.week, args.bundle_id)
    output_dir = Path(args.output_root) / bundle_id

    source_path = ""
    version = 1
    chunks: list[dict[str, Any]] = []

    if args.book_pack:
        p = Path(args.book_pack)
        if not p.exists():
            raise FileNotFoundError(f"book_pack not found: {p}")
        obj, chunks = _chunks_from_book_pack(p)
        source_path = str(p)
        version = _safe_int(args.version, _safe_int(obj.get("version") or obj.get("book_pack_version"), 1))
    else:
        p = Path(args.input)
        if not p.exists():
            raise FileNotFoundError(f"input file not found: {p}")
        source_path = str(p)
        version = _safe_int(args.version, 1)
        chunks = _chunk_from_plain_text(p.read_text(encoding="utf-8"))

    if args.version is not None:
        version = _safe_int(args.version, version)
    if version <= 0:
        version = 1

    await _build_index(
        chunks=chunks,
        output_dir=output_dir,
        version=version,
        bundle_id=bundle_id,
        source_path=source_path,
        provider=args.provider,
        hash_dim=args.hash_dim,
    )


if __name__ == "__main__":
    asyncio.run(main())
