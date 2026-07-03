"""CLI จัดการบัญชี staff — สมัครผ่าน command (HI-01).

    python -m app.staff_cli add-staff --username staff1 --province-id 1
    python -m app.staff_cli list-staff
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import text

from .core.admin_security import hash_password
from .core.database import SessionLocal


async def _add_staff(username: str, password: str, province_id: int, display_name: str) -> int:
    username = (username or "").strip()
    if not username:
        print("error: --username ต้องไม่ว่าง", file=sys.stderr)
        return 2
    if province_id < 1:
        print("error: --province-id ต้อง >= 1", file=sys.stderr)
        return 2
    if len(password or "") < 8:
        print("error: --password ต้องยาวอย่างน้อย 8 ตัวอักษร", file=sys.stderr)
        return 2

    async with SessionLocal() as session:
        exists = await session.execute(
            text("SELECT 1 FROM staff_users WHERE username = :u LIMIT 1"),
            {"u": username},
        )
        if exists.scalar() is not None:
            print(f"error: username '{username}' มีอยู่แล้ว", file=sys.stderr)
            return 1

        prov = await session.execute(
            text("SELECT 1 FROM province WHERE id = :pid LIMIT 1"),
            {"pid": province_id},
        )
        if prov.scalar() is None:
            print(f"error: province_id {province_id} ไม่พบ", file=sys.stderr)
            return 1

        await session.execute(
            text(
                "INSERT INTO staff_users (username, password_hash, province_id, display_name) "
                "VALUES (:u, :h, :p, :d)"
            ),
            {
                "u": username,
                "h": hash_password(password),
                "p": province_id,
                "d": (display_name or username).strip(),
            },
        )
        await session.commit()
    print(f"ok: สร้าง staff '{username}' (province_id={province_id}) สำเร็จ")
    return 0


async def _list_staff() -> int:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, username, province_id, display_name, is_active, created_at "
                    "FROM staff_users ORDER BY id"
                )
            )
        ).all()
    if not rows:
        print("(ยังไม่มี staff)")
        return 0
    print(f"{'id':>4}  {'username':<16} {'prov':>4}  {'display_name':<20} active  created_at")
    for r in rows:
        print(f"{r[0]:>4}  {r[1]:<16} {r[2]:>4}  {(r[3] or ''):<20} {str(r[4]):<6} {r[5]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="staff_cli", description="จัดการบัญชี staff")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add-staff", help="สร้าง staff ใหม่")
    p_add.add_argument("--username", required=True)
    p_add.add_argument("--province-id", type=int, required=True)
    p_add.add_argument("--display-name", default="")
    p_add.add_argument("--password", default=None)

    sub.add_parser("list-staff", help="แสดงรายการ staff")

    args = parser.parse_args(argv)

    if SessionLocal is None:
        print("error: DATABASE_URL ไม่ได้ตั้งค่า", file=sys.stderr)
        return 2

    if args.command == "add-staff":
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
        return asyncio.run(
            _add_staff(args.username, password, args.province_id, args.display_name)
        )
    if args.command == "list-staff":
        return asyncio.run(_list_staff())
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
