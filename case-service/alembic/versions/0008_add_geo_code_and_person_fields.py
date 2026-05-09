"""add geo code columns + person address/gender fields

Revision ID: 0008_geo_person_fields
Revises: 0003_seed_master_geo_data
Create Date: 2026-05-09 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_geo_person_fields"
down_revision: str | Sequence[str] | None = "0003_seed_master_geo_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # geo: add code columns (nullable for backward compatibility)
    op.add_column("districts", sa.Column("code", sa.String(length=50), nullable=True))
    op.create_index(op.f("ix_districts_code"), "districts", ["code"], unique=False)

    op.add_column("sub_districts", sa.Column("code", sa.String(length=50), nullable=True))
    op.create_index(op.f("ix_sub_districts_code"), "sub_districts", ["code"], unique=False)

    # persons: store raw-ish address parts and selected geo FK (optional)
    op.add_column(
        "persons",
        sa.Column("sub_district_postcode_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_persons_sub_district_postcode_id"),
        "persons",
        ["sub_district_postcode_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_persons_sub_district_postcode_id_sub_districts_postcode"),
        "persons",
        "sub_districts_postcode",
        ["sub_district_postcode_id"],
        ["id"],
    )

    op.add_column("persons", sa.Column("gender", sa.String(length=50), nullable=True))
    op.add_column("persons", sa.Column("adr_moo", sa.String(length=50), nullable=True))
    op.add_column(
        "persons", sa.Column("adr_house_num", sa.String(length=100), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("persons", "adr_house_num")
    op.drop_column("persons", "adr_moo")
    op.drop_column("persons", "gender")

    op.drop_constraint(
        op.f("fk_persons_sub_district_postcode_id_sub_districts_postcode"),
        "persons",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_persons_sub_district_postcode_id"), table_name="persons")
    op.drop_column("persons", "sub_district_postcode_id")

    op.drop_index(op.f("ix_sub_districts_code"), table_name="sub_districts")
    op.drop_column("sub_districts", "code")

    op.drop_index(op.f("ix_districts_code"), table_name="districts")
    op.drop_column("districts", "code")

