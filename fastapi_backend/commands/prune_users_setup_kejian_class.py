"""
整理使用者與班級：
- 只保留 kejian01..kejian10 與 display_name=張伃涵 的帳號
- 刪除其餘 user 及相關 ORID 資料
- 清空所有班級後建立「蚵間國小」，並將 10 位 kejian 學生加入

執行（prod 範例）：
  docker compose -p orid-prod -f docker-compose.prod.yml exec -T backend sh -c \\
    "export DATABASE_URL='postgresql+asyncpg://postgres:PASS@db:5432/orid_prod' && \\
     uv run python commands/prune_users_setup_kejian_class.py --apply"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

_backend_root = Path(__file__).resolve().parents[1]
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from dotenv import load_dotenv
from sqlalchemy import delete, select

from app.database import async_session_maker
from app.models import (
    ClassRoom,
    Item,
    OridChatMessage,
    OridFeedbackEvent,
    OridPostTestScore,
    OridSession,
    OridStageAttempt,
    OridWeekSubmission,
    StudentClassMembership,
    TeacherClassAssignment,
    User,
)

load_dotenv()

KEJIAN_LOGINS = [f"kejian{i:02d}" for i in range(1, 11)]
CLASS_NAME = "蚵間國小"
CLASS_EXTERNAL_CODE = "kejian-guo-xiao"
KEEP_DISPLAY_NAME = "張伃涵"


async def _keep_user_ids(db) -> set[uuid.UUID]:
    ids: set[uuid.UUID] = set()
    for login in KEJIAN_LOGINS:
        r = await db.execute(select(User.id).where(User.email == login))
        row = r.scalar_one_or_none()
        if row:
            ids.add(row)
    r = await db.execute(select(User.id).where(User.display_name == KEEP_DISPLAY_NAME))
    for uid in r.scalars().all():
        ids.add(uid)
    return ids


async def run(*, apply: bool) -> None:
    async with async_session_maker() as db:
        keep_ids = await _keep_user_ids(db)
        if len(keep_ids) < 1:
            print("[error] 找不到任何要保留的帳號（kejian01-10 或 張伃涵）")
            return

        all_users = await db.execute(select(User.id, User.email, User.display_name))
        to_delete = [
            (uid, em, dn)
            for uid, em, dn in all_users.all()
            if uid not in keep_ids
        ]
        print(f"[plan] 保留 {len(keep_ids)} 位使用者，刪除 {len(to_delete)} 位")
        for uid, em, dn in to_delete[:20]:
            print(f"  - delete user {em!r} display_name={dn!r}")
        if len(to_delete) > 20:
            print(f"  ... 另有 {len(to_delete) - 20} 位")

        if not apply:
            print("[dry-run] 加上 --apply 才會寫入資料庫")
            return

        keep_list = list(keep_ids)

        await db.execute(
            delete(OridFeedbackEvent).where(OridFeedbackEvent.user_id.not_in(keep_list))
        )
        await db.execute(
            delete(OridStageAttempt).where(OridStageAttempt.user_id.not_in(keep_list))
        )
        await db.execute(
            delete(OridChatMessage).where(
                OridChatMessage.session_id.in_(
                    select(OridSession.id).where(OridSession.user_id.not_in(keep_list))
                )
            )
        )
        await db.execute(
            delete(OridWeekSubmission).where(OridWeekSubmission.user_id.not_in(keep_list))
        )
        await db.execute(delete(OridSession).where(OridSession.user_id.not_in(keep_list)))
        await db.execute(delete(OridPostTestScore))
        await db.execute(delete(StudentClassMembership))
        await db.execute(delete(TeacherClassAssignment))
        await db.execute(delete(ClassRoom))
        await db.execute(delete(Item).where(Item.user_id.not_in(keep_list)))
        await db.execute(delete(User).where(User.id.not_in(keep_list)))

        cls = ClassRoom(
            id=uuid.uuid4(),
            name=CLASS_NAME,
            year=2026,
            external_code=CLASS_EXTERNAL_CODE,
        )
        db.add(cls)
        await db.flush()

        linked = 0
        for login in KEJIAN_LOGINS:
            r = await db.execute(select(User).where(User.email == login))
            st = r.scalars().first()
            if not st:
                print(f"[warn] 找不到 {login}，略過班級綁定")
                continue
            db.add(StudentClassMembership(student_id=st.id, class_id=cls.id))
            linked += 1

        await db.commit()
        print(f"[done] 班級「{CLASS_NAME}」id={cls.id}，已加入 {linked} 位學生")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="實際寫入（預設僅 dry-run）")
    args = p.parse_args()
    asyncio.run(run(apply=args.apply))


if __name__ == "__main__":
    main()
