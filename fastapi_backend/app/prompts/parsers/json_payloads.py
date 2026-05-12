from __future__ import annotations

from typing import Any, Dict
import json
import re


JSON_RE = re.compile(r"\{[\s\S]*\}")


def parse_book_grounding_checker_json(raw: str) -> Dict[str, Any]:
    if raw is None:
        return {}
    s = str(raw).strip()
    if not s:
        return {}
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        m = JSON_RE.search(s)
        if not m:
            return {}
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}


def parse_orid_checker_json(raw: str) -> Dict[str, Any]:
    if raw is None:
        return {}
    s = str(raw).strip()
    if not s:
        return {}
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        m = JSON_RE.search(s)
        if not m:
            return {}
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}


def extract_json_object(raw: str) -> Dict[str, Any]:
    return parse_orid_checker_json(raw)
