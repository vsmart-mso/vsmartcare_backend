"""allow multiple 037 payment rounds per DDA

Revision ID: 0044_allow_multiple_037_rounds
Revises: 0043_mso_type_send
Create Date: 2026-05-25 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0044_allow_multiple_037_rounds"
down_revision: str | Sequence[str] | None = "0043_mso_type_send"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UQ_037_PER_DDA = "uq_welfare_payment_applicant_dda_037"


def upgrade() -> None:
    op.drop_index(UQ_037_PER_DDA, table_name="welfare_payment")


def downgrade() -> None:
    op.create_index(
        UQ_037_PER_DDA,
        "welfare_payment",
        ["applicant_id", "dda_ref_id"],
        unique=True,
        postgresql_where=sa.text("is_037_or_038 IS FALSE"),
    )
