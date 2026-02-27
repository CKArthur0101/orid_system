import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import select

from app.database import async_session_maker
from app.models import Reading

DEFAULT_READING_TITLE_TEMPLATE = "第 {week} 週（暫定教材）"


def _load_json(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("JSON file is empty")
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("book_pack must be a JSON object")
    return obj


def _validate_book_pack(obj: Dict[str, Any]) -> None:
    # Minimal validation: enough to prevent wrong data being seeded
    schema = obj.get("schema")
    if schema != "book_pack_v1":
        raise ValueError(f"Invalid schema: {schema!r} (expected 'book_pack_v1')")

    required_keys = ["book_title", "key_events", "orid_prompt_bank", "writing_guide"]
    missing = [k for k in required_keys if k not in obj]
    if missing:
        raise ValueError(f"book_pack missing required keys: {missing}")

    if not isinstance(obj.get("key_events"), list) or not obj["key_events"]:
        raise ValueError("book_pack.key_events must be a non-empty list")

    if not isinstance(obj.get("orid_prompt_bank"), dict):
        raise ValueError("book_pack.orid_prompt_bank must be an object")

    if not isinstance(obj.get("writing_guide"), dict):
        raise ValueError("book_pack.writing_guide must be an object")


async def _insert_reading(*, week: int, title: str, content: str) -> Reading:
    async with async_session_maker() as db:
        reading = Reading(title=title, content=content)
        db.add(reading)
        await db.commit()
        await db.refresh(reading)
        return reading


async def _find_latest_reading_id(title: str) -> Optional[str]:
    async with async_session_maker() as db:
        stmt = (
            select(Reading)
            .where(Reading.title == title)
            .order_by(Reading.created_at.desc())
            .limit(1)
        )
        res = await db.execute(stmt)
        r = res.scalars().first()
        return str(r.id) if r else None


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo book_pack into readings table.")
    parser.add_argument("--week", type=int, required=True, help="Week number (1-6)")
    parser.add_argument(
        "--path",
        type=str,
        required=True,
        help="Path to book_pack json (inside container), e.g. /app/shared-data/book_pack_week1.json",
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Optional custom reading title. Default: 第 {week} 週（暫定教材）",
    )
    args = parser.parse_args()

    if args.week < 1 or args.week > 6:
        raise ValueError("week must be between 1 and 6")

    title = args.title or DEFAULT_READING_TITLE_TEMPLATE.format(week=args.week)

    pack = _load_json(args.path)
    _validate_book_pack(pack)

    # Store as JSON string in readings.content (text column)
    content_str = json.dumps(pack, ensure_ascii=False)

    reading = await _insert_reading(week=args.week, title=title, content=content_str)
    latest_id = await _find_latest_reading_id(title)

    print("✅ Seeded demo book_pack into DB")
    print(f"   title      : {title}")
    print(f"   reading_id : {reading.id}")
    print(f"   latest_id  : {latest_id}")
    print(f"   book_title : {pack.get('book_title')}")
    print(f"   key_events : {len(pack.get('key_events', []))} items")


if __name__ == "__main__":
    asyncio.run(main())