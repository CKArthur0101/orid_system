from __future__ import annotations

from functools import lru_cache
from pathlib import Path


_TEXT_DIR = Path(__file__).resolve().parent / "text"


def read_prompt_file(name: str) -> str:
    """Read a prompt file that contains only the words sent to the model."""
    path = _TEXT_DIR / name
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()


@lru_cache(maxsize=8)
def read_prompt_pieces(name: str) -> dict[str, str]:
    """Read a text file of labeled paragraphs. Labels look like [O] and are not sent to the model."""
    raw = (_TEXT_DIR / name).read_text(encoding="utf-8").replace("\r\n", "\n")
    pieces: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in raw.split("\n"):
        if len(line) >= 3 and line.startswith("[") and line.endswith("]") and " " not in line:
            if current is not None:
                pieces[current] = "\n".join(buf).strip()
            current = line[1:-1]
            buf = []
            continue
        if current is not None:
            buf.append(line)
    if current is not None:
        pieces[current] = "\n".join(buf).strip()
    return pieces


def fill_prompt(template: str, values: dict[str, str]) -> str:
    """Replace {空位} markers. The markers are the only non-sentence parts of a prompt file."""
    out = template
    for key, value in values.items():
        out = out.replace("{" + key + "}", value or "")
    return out.strip()
