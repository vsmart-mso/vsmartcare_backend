"""เพิ่มฟิลด์ผลการเยี่ยมบ้านใน applicants, addresses, economic_infos

- applicants.family_distress       — สภาพปัญหาความเดือดร้อน
- addresses.nearby_landmark        — สถานที่ตั้งใกล้เคียงที่มองเห็นง่าย
- economic_infos.housing_shelter   — สภาพที่อยู่อาศัย

Revision ID: 0073_home_visit_fields
Revises: 0072_existing_case_detected_sources
Create Date: 2026-07-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0073_home_visit_fields"
down_revision = "0072_existing_case_detected_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "applicants",
        sa.Column("family_distress", sa.Text(), nullable=True, comment="สภาพปัญหาความเดือดร้อน"),
    )
    op.add_column(
        "address",
        sa.Column("nearby_landmark", sa.String(length=500), nullable=True, comment="สถานที่ตั้งใกล้เคียงที่มองเห็นง่าย"),
    )
    op.add_column(
        "economic_infos",
        sa.Column("housing_shelter", sa.Text(), nullable=True, comment="สภาพที่อยู่อาศัย"),
    )


def downgrade() -> None:
    op.drop_column("economic_infos", "housing_shelter")
    op.drop_column("address", "nearby_landmark")
    op.drop_column("applicants", "family_distress")
