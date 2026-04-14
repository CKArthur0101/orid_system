from __future__ import annotations

import math
from typing import Iterable


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def hash_embed_text(text: str, dim: int = 256) -> list[float]:
    d = max(8, int(dim))
    vec = [0.0] * d
    t = (text or "").strip()
    if not t:
        return vec
    for idx, ch in enumerate(t):
        bucket = (ord(ch) * 131 + idx * 17) % d
        vec[bucket] += 1.0
    return _normalize(vec)


def hash_embed_texts(texts: Iterable[str], dim: int = 256) -> list[list[float]]:
    return [hash_embed_text(t, dim=dim) for t in texts]
