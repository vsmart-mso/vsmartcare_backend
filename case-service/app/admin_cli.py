"""CLI จัดการบัญชี admin — สมัคร admin ผ่าน command (ไม่มี UI signup).

ใช้งาน (จากโฟลเดอร์ case-service ที่มี .env ชี้ DATABASE_URL):

    python -m app.admin_cli add-admin --username admin           # แนะนำ — รหัสผ่านถามผ่าน prompt
    python -m app.admin_cli add-admin --username admin --password "SecurePass!123"  # หรือส่งตรง (บันทึกใน history)
    python -m app.admin_cli list-admins

หมายเหตุ: ต้อง migrate ถึง revision 0058 ก่อน (ตาราง admin_users)
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import text

from .core.admin_security import hash_password
from .core.database import SessionLocal


async def _add_admin(username: str, password: str) -> int:
    username = (username or "").strip()
    if not username:
        print("error: --username ต้องไม่ว่าง", file=sys.stderr)
        return 2
    if len(password or "") < 8:
        print("error: --password ต้องยาวอย่างน้อย 8 ตัวอักษร", file=sys.stderr)
        return 2

    async with SessionLocal() as session:
        exists = await session.execute(
            text("SELECT 1 FROM admin_users WHERE username = :u LIMIT 1"),
            {"u": username},
        )
        if exists.scalar() is not None:
            print(f"error: username '{username}' มีอยู่แล้ว", file=sys.stderr)
            return 1

        await session.execute(
            text(
                "INSERT INTO admin_users (username, password_hash) "
                "VALUES (:u, :h)"
            ),
            {"u": username, "h": hash_password(password)},
        )
        await session.commit()
    print(f"ok: สร้าง admin '{username}' สำเร็จ")
    return 0


async def _list_admins() -> int:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, username, is_active, created_at "
                    "FROM admin_users ORDER BY id"
                )
            )
        ).all()
    if not rows:
        print("(ยังไม่มี admin)")
        return 0
    print(f"{'id':>4}  {'username':<20} {'active':<7} created_at")
    for r in rows:
        print(f"{r[0]:>4}  {r[1]:<20} {str(r[2]):<7} {r[3]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="admin_cli", description="จัดการบัญชี admin")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add-admin", help="สร้าง admin ใหม่")
    p_add.add_argument("--username", required=True)
    p_add.add_argument(
        "--password",
        default=None,
        help="ถ้าไม่ระบุ จะถามผ่าน prompt แบบ interactive (แนะนำ — รหัสผ่านไม่ถูกบันทึกใน shell history)",
    )

    sub.add_parser("list-admins", help="แสดงรายการ admin")

    args = parser.parse_args(argv)

    if SessionLocal is None:
        print("error: DATABASE_URL ไม่ได้ตั้งค่า (ดู .env ของ case-service)", file=sys.stderr)
        return 2

    if args.command == "add-admin":
        password = args.password
        if not password:
            try:
                password = getpass.getpass("Password (min 8 chars): ")
                confirm = getpass.getpass("Confirm password: ")
                if password != confirm:
                    print("error: รหัสผ่านไม่ตรงกัน", file=sys.stderr)
                    return 2
            except (EOFError, KeyboardInterrupt):
                print("\nยกเลิก", file=sys.stderr)
                return 2
        return asyncio.run(_add_admin(args.username, password))
    if args.command == "list-admins":
        return asyncio.run(_list_admins())
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
