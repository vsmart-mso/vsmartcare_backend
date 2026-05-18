"""backfill bank_account_type + case_payment.bank_account_type_id ถ้า DB ข้าม 0027

Revision ID: 0032_bank_acct_type_fix
Revises: 0031_add_remarks_review_field
Create Date: 2026-05-18 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032_bank_acct_type_fix"
down_revision: str | Sequence[str] | None = "0031_add_remarks_review_field"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEED_ROWS = [
    {"id": 1, "name": "เงินฝากออมทรัพย์", "sort_order": 1},
    {"id": 2, "name": "เงินฝากประจำ", "sort_order": 2},
    {"id": 3, "name": "เงินฝากกระแสรายวัน", "sort_order": 3},
]

FK_NAME = "fk_case_payment_bank_account_type_id_bank_account_type"
IX_NAME = "ix_case_payment_bank_account_type_id"


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS bank_account_type (
                id SERIAL NOT NULL,
                name VARCHAR(100) NOT NULL,
                sort_order INTEGER,
                CONSTRAINT pk_bank_account_type PRIMARY KEY (id)
            )
            """
        )
    )

    for row in SEED_ROWS:
        bind.execute(
            sa.text(
                "INSERT INTO bank_account_type (id, name, sort_order) "
                "VALUES (:id, :name, :sort_order) "
                "ON CONFLICT (id) DO UPDATE SET "
                "name = EXCLUDED.name, sort_order = EXCLUDED.sort_order"
            ),
            row,
        )

    bind.execute(
        sa.text(
            "SELECT setval(pg_get_serial_sequence('bank_account_type', 'id'), "
            "(SELECT COALESCE(MAX(id), 1) FROM bank_account_type))"
        )
    )

    bind.execute(
        sa.text(
            "ALTER TABLE case_payment "
            "ADD COLUMN IF NOT EXISTS bank_account_type_id INTEGER"
        )
    )

    bind.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = '{FK_NAME}'
                ) THEN
                    ALTER TABLE case_payment
                    ADD CONSTRAINT {FK_NAME}
                    FOREIGN KEY (bank_account_type_id)
                    REFERENCES bank_account_type (id);
                END IF;
            END $$;
            """
        )
    )

    bind.execute(
        sa.text(f'CREATE INDEX IF NOT EXISTS "{IX_NAME}" ON case_payment (bank_account_type_id)')
    )

    bind.execute(sa.text("ALTER TABLE case_payment DROP COLUMN IF EXISTS account_type"))


def downgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            "ALTER TABLE case_payment ADD COLUMN IF NOT EXISTS account_type VARCHAR(100)"
        )
    )

    bind.execute(sa.text(f'DROP INDEX IF EXISTS "{IX_NAME}"'))
    bind.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = '{FK_NAME}'
                ) THEN
                    ALTER TABLE case_payment DROP CONSTRAINT {FK_NAME};
                END IF;
            END $$;
            """
        )
    )
    bind.execute(
        sa.text("ALTER TABLE case_payment DROP COLUMN IF EXISTS bank_account_type_id")
    )
