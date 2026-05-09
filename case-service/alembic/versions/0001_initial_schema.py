"""initial schema - 28 tables (ER ใหม่: persons, screening, consents, ...)

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-08 00:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) Master/lookup
    op.create_table(
        "prefix_type",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prefix_type")),
    )
    op.create_table(
        "marital_status_types",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_marital_status_types")),
    )
    op.create_table(
        "request_types",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_request_types")),
    )
    op.create_table(
        "attachment_types",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attachment_types")),
    )
    op.create_table(
        "received_welfare_types",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_received_welfare_types")),
    )
    op.create_table(
        "dependency_types",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dependency_types")),
    )
    op.create_table(
        "housing_types",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_housing_types")),
    )
    op.create_table(
        "income_source_types",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_income_source_types")),
    )
    op.create_table(
        "address_type",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_address_type")),
    )
    op.create_table(
        "current_status",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_current_status")),
    )

    # 2) Geo
    op.create_table(
        "province",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=10), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_province")),
    )
    op.create_index(op.f("ix_province_code"), "province", ["code"], unique=False)

    op.create_table(
        "postcode",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=10), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_postcode")),
    )
    op.create_index(op.f("ix_postcode_name"), "postcode", ["name"], unique=False)

    op.create_table(
        "districts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("province_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["province_id"],
            ["province.id"],
            name=op.f("fk_districts_province_id_province"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_districts")),
    )
    op.create_index(
        op.f("ix_districts_province_id"), "districts", ["province_id"], unique=False
    )

    op.create_table(
        "sub_districts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("district_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["district_id"],
            ["districts.id"],
            name=op.f("fk_sub_districts_district_id_districts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sub_districts")),
    )
    op.create_index(
        op.f("ix_sub_districts_district_id"),
        "sub_districts",
        ["district_id"],
        unique=False,
    )

    op.create_table(
        "sub_districts_postcode",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sub_district_id", sa.Integer(), nullable=False),
        sa.Column("postcode_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["sub_district_id"],
            ["sub_districts.id"],
            name=op.f("fk_sub_districts_postcode_sub_district_id_sub_districts"),
        ),
        sa.ForeignKeyConstraint(
            ["postcode_id"],
            ["postcode.id"],
            name=op.f("fk_sub_districts_postcode_postcode_id_postcode"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sub_districts_postcode")),
    )
    op.create_index(
        op.f("ix_sub_districts_postcode_sub_district_id"),
        "sub_districts_postcode",
        ["sub_district_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sub_districts_postcode_postcode_id"),
        "sub_districts_postcode",
        ["postcode_id"],
        unique=False,
    )

    # 3) persons + applicants + screening
    op.create_table(
        "persons",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prefix_id", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=False),
        sa.Column("last_name", sa.String(length=255), nullable=False),
        sa.Column(
            "cid",
            sa.String(length=13),
            nullable=False,
            comment="เลขบัตรประจำตัวประชาชน 13 หลัก",
        ),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(
            ["prefix_id"],
            ["prefix_type.id"],
            name=op.f("fk_persons_prefix_id_prefix_type"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_persons")),
        sa.UniqueConstraint("cid", name=op.f("uq_persons_cid")),
    )
    op.create_index(op.f("ix_persons_cid"), "persons", ["cid"], unique=False)

    op.create_table(
        "applicants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("persons_id", sa.Integer(), nullable=False),
        sa.Column("requester_relation", sa.String(length=100), nullable=True),
        sa.Column("marital_status_id", sa.Integer(), nullable=False),
        sa.Column("mobile_phone", sa.String(length=20), nullable=True),
        sa.Column("home_phone", sa.String(length=20), nullable=True),
        sa.Column("fax_number", sa.String(length=20), nullable=True),
        sa.Column("email_address", sa.String(length=255), nullable=True),
        sa.Column(
            "is_government_officer",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("problem_details", sa.Text(), nullable=True),
        sa.Column("bank_account_name", sa.String(length=255), nullable=True),
        sa.Column("bank_account_no", sa.String(length=50), nullable=True),
        sa.Column("time_count_process", sa.Integer(), nullable=True),
        sa.Column(
            "is_emergency",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_existing_case",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.ForeignKeyConstraint(
            ["persons_id"],
            ["persons.id"],
            name=op.f("fk_applicants_persons_id_persons"),
        ),
        sa.ForeignKeyConstraint(
            ["marital_status_id"],
            ["marital_status_types.id"],
            name=op.f("fk_applicants_marital_status_id_marital_status_types"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_applicants")),
    )
    op.create_index(
        op.f("ix_applicants_persons_id"), "applicants", ["persons_id"], unique=False
    )

    op.create_table(
        "screening_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("criteria_version", sa.String(length=50), nullable=True),
        sa.Column("screening_result", sa.String(length=100), nullable=True),
        sa.Column("failure_reason_code", sa.String(length=100), nullable=True),
        sa.Column(
            "screening_status",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("input_data_snapshot", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["persons.id"],
            name=op.f("fk_screening_logs_person_id_persons"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_screening_logs")),
    )
    op.create_index(
        op.f("ix_screening_logs_person_id"),
        "screening_logs",
        ["person_id"],
        unique=False,
    )

    op.create_table(
        "welfare_request_consents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("consent_type", sa.String(length=100), nullable=True),
        sa.Column(
            "initial_pdpa_accepted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "initial_terms_accepted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "initial_warning_accepted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "final_data_correct_accepted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["persons.id"],
            name=op.f("fk_welfare_request_consents_person_id_persons"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_welfare_request_consents")),
    )
    op.create_index(
        op.f("ix_welfare_request_consents_person_id"),
        "welfare_request_consents",
        ["person_id"],
        unique=False,
    )

    # 4) address + economic + dependency
    op.create_table(
        "address",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sub_district_postcode_id", sa.Integer(), nullable=False),
        sa.Column("applicant_id", sa.Integer(), nullable=False),
        sa.Column("address_type_id", sa.Integer(), nullable=False),
        sa.Column("address_detail", sa.String(length=500), nullable=True),
        sa.Column(
            "sub_lane_road",
            sa.String(length=255),
            nullable=True,
            comment="ซอย/ถนน",
        ),
        sa.Column(
            "mobile_phone",
            sa.String(length=20),
            nullable=True,
            comment="เบอร์ติดต่อตามที่อยู่นี้",
        ),
        sa.Column("latitude", sa.String(length=50), nullable=True),
        sa.Column("longitude", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(
            ["sub_district_postcode_id"],
            ["sub_districts_postcode.id"],
            name=op.f("fk_address_sub_district_postcode_id_sub_districts_postcode"),
        ),
        sa.ForeignKeyConstraint(
            ["applicant_id"],
            ["applicants.id"],
            name=op.f("fk_address_applicant_id_applicants"),
        ),
        sa.ForeignKeyConstraint(
            ["address_type_id"],
            ["address_type.id"],
            name=op.f("fk_address_address_type_id_address_type"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_address")),
    )
    op.create_index(
        op.f("ix_address_sub_district_postcode_id"),
        "address",
        ["sub_district_postcode_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_address_applicant_id"), "address", ["applicant_id"], unique=False
    )

    op.create_table(
        "economic_infos",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("applicant_id", sa.Integer(), nullable=False),
        sa.Column("housing_types_id", sa.Integer(), nullable=True),
        sa.Column("occupation", sa.String(length=255), nullable=True),
        sa.Column("monthly_income", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column(
            "household_members",
            sa.Integer(),
            nullable=True,
            comment="จำนวนสมาชิกในครัวเรือน",
        ),
        sa.Column("family_occupation", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["applicant_id"],
            ["applicants.id"],
            name=op.f("fk_economic_infos_applicant_id_applicants"),
        ),
        sa.ForeignKeyConstraint(
            ["housing_types_id"],
            ["housing_types.id"],
            name=op.f("fk_economic_infos_housing_types_id_housing_types"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_economic_infos")),
    )
    op.create_index(
        op.f("ix_economic_infos_applicant_id"),
        "economic_infos",
        ["applicant_id"],
        unique=False,
    )

    op.create_table(
        "economic_income_sources",
        sa.Column("economic_id", sa.Integer(), nullable=False),
        sa.Column("income_source_type_id", sa.Integer(), nullable=False),
        sa.Column(
            "other_details",
            sa.String(length=500),
            nullable=True,
            comment="กรอกเพิ่มเมื่อเลือกประเภท 'อื่น ๆ'",
        ),
        sa.ForeignKeyConstraint(
            ["economic_id"],
            ["economic_infos.id"],
            name=op.f("fk_economic_income_sources_economic_id_economic_infos"),
        ),
        sa.ForeignKeyConstraint(
            ["income_source_type_id"],
            ["income_source_types.id"],
            name=op.f(
                "fk_economic_income_sources_income_source_type_id_income_source_types"
            ),
        ),
        sa.PrimaryKeyConstraint(
            "economic_id",
            "income_source_type_id",
            name=op.f("pk_economic_income_sources"),
        ),
    )

    op.create_table(
        "dependency_loads",
        sa.Column("applicant_id", sa.Integer(), nullable=False),
        sa.Column("dependency_type_id", sa.Integer(), nullable=False),
        sa.Column(
            "dependency_other_text",
            sa.String(length=500),
            nullable=True,
            comment="ระบุรายละเอียดเมื่อเลือก dependency แบบ 'อื่น ๆ'",
        ),
        sa.ForeignKeyConstraint(
            ["applicant_id"],
            ["applicants.id"],
            name=op.f("fk_dependency_loads_applicant_id_applicants"),
        ),
        sa.ForeignKeyConstraint(
            ["dependency_type_id"],
            ["dependency_types.id"],
            name=op.f("fk_dependency_loads_dependency_type_id_dependency_types"),
        ),
        sa.PrimaryKeyConstraint(
            "applicant_id", "dependency_type_id", name=op.f("pk_dependency_loads")
        ),
    )

    # 5) welfare
    op.create_table(
        "welfare_histories",
        sa.Column("applicant_id", sa.Integer(), nullable=False),
        sa.Column(
            "received_count", sa.Integer(), nullable=True, comment="จำนวนครั้งที่เคยได้รับ"
        ),
        sa.Column(
            "has_received_welfare",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "total_received_amount", sa.Numeric(precision=12, scale=2), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["applicant_id"],
            ["applicants.id"],
            name=op.f("fk_welfare_histories_applicant_id_applicants"),
        ),
        sa.PrimaryKeyConstraint("applicant_id", name=op.f("pk_welfare_histories")),
    )

    op.create_table(
        "welfare_histories_detail",
        sa.Column("welfare_history_id", sa.Integer(), nullable=False),
        sa.Column("received_welfare_type_id", sa.Integer(), nullable=False),
        sa.Column(
            "received_other",
            sa.String(length=500),
            nullable=True,
            comment="ระบุสวัสดิการเพิ่มเติมเมื่อเลือก 'อื่น ๆ'",
        ),
        sa.ForeignKeyConstraint(
            ["received_welfare_type_id"],
            ["received_welfare_types.id"],
            name=op.f(
                "fk_welfare_histories_detail_received_welfare_type_id_received_welfare_types"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["welfare_history_id"],
            ["welfare_histories.applicant_id"],
            name=op.f(
                "fk_welfare_histories_detail_welfare_history_id_welfare_histories"
            ),
        ),
        sa.PrimaryKeyConstraint(
            "welfare_history_id",
            "received_welfare_type_id",
            name=op.f("pk_welfare_histories_detail"),
        ),
    )

    op.create_table(
        "welfare_request_types",
        sa.Column("applicant_id", sa.Integer(), nullable=False),
        sa.Column("request_type_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["applicant_id"],
            ["applicants.id"],
            name=op.f("fk_welfare_request_types_applicant_id_applicants"),
        ),
        sa.ForeignKeyConstraint(
            ["request_type_id"],
            ["request_types.id"],
            name=op.f("fk_welfare_request_types_request_type_id_request_types"),
        ),
        sa.PrimaryKeyConstraint(
            "applicant_id", "request_type_id", name=op.f("pk_welfare_request_types")
        ),
    )

    op.create_table(
        "welfare_evidences",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("attachment_type_id", sa.Integer(), nullable=False),
        sa.Column("applicant_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.ForeignKeyConstraint(
            ["attachment_type_id"],
            ["attachment_types.id"],
            name=op.f("fk_welfare_evidences_attachment_type_id_attachment_types"),
        ),
        sa.ForeignKeyConstraint(
            ["applicant_id"],
            ["applicants.id"],
            name=op.f("fk_welfare_evidences_applicant_id_applicants"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_welfare_evidences")),
    )
    op.create_index(
        op.f("ix_welfare_evidences_applicant_id"),
        "welfare_evidences",
        ["applicant_id"],
        unique=False,
    )

    op.create_table(
        "welfare_request_status",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("applicant_id", sa.Integer(), nullable=False),
        sa.Column("current_status_id", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_by_firstname", sa.String(length=255), nullable=True),
        sa.Column("updated_by_lastname", sa.String(length=255), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["applicant_id"],
            ["applicants.id"],
            name=op.f("fk_welfare_request_status_applicant_id_applicants"),
        ),
        sa.ForeignKeyConstraint(
            ["current_status_id"],
            ["current_status.id"],
            name=op.f("fk_welfare_request_status_current_status_id_current_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_welfare_request_status")),
    )
    op.create_index(
        op.f("ix_welfare_request_status_applicant_id"),
        "welfare_request_status",
        ["applicant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_welfare_request_status_applicant_id"),
        table_name="welfare_request_status",
    )
    op.drop_table("welfare_request_status")

    op.drop_index(
        op.f("ix_welfare_evidences_applicant_id"), table_name="welfare_evidences"
    )
    op.drop_table("welfare_evidences")

    op.drop_table("welfare_request_types")
    op.drop_table("welfare_histories_detail")
    op.drop_table("welfare_histories")

    op.drop_table("dependency_loads")
    op.drop_table("economic_income_sources")

    op.drop_index(
        op.f("ix_economic_infos_applicant_id"), table_name="economic_infos"
    )
    op.drop_table("economic_infos")

    op.drop_index(op.f("ix_address_applicant_id"), table_name="address")
    op.drop_index(op.f("ix_address_sub_district_postcode_id"), table_name="address")
    op.drop_table("address")

    op.drop_index(
        op.f("ix_welfare_request_consents_person_id"),
        table_name="welfare_request_consents",
    )
    op.drop_table("welfare_request_consents")

    op.drop_index(op.f("ix_screening_logs_person_id"), table_name="screening_logs")
    op.drop_table("screening_logs")

    op.drop_index(op.f("ix_applicants_persons_id"), table_name="applicants")
    op.drop_table("applicants")

    op.drop_index(op.f("ix_persons_cid"), table_name="persons")
    op.drop_table("persons")

    op.drop_index(
        op.f("ix_sub_districts_postcode_postcode_id"),
        table_name="sub_districts_postcode",
    )
    op.drop_index(
        op.f("ix_sub_districts_postcode_sub_district_id"),
        table_name="sub_districts_postcode",
    )
    op.drop_table("sub_districts_postcode")

    op.drop_index(op.f("ix_sub_districts_district_id"), table_name="sub_districts")
    op.drop_table("sub_districts")

    op.drop_index(op.f("ix_districts_province_id"), table_name="districts")
    op.drop_table("districts")

    op.drop_index(op.f("ix_postcode_name"), table_name="postcode")
    op.drop_table("postcode")

    op.drop_index(op.f("ix_province_code"), table_name="province")
    op.drop_table("province")

    op.drop_table("current_status")
    op.drop_table("address_type")
    op.drop_table("income_source_types")
    op.drop_table("housing_types")
    op.drop_table("dependency_types")
    op.drop_table("received_welfare_types")
    op.drop_table("attachment_types")
    op.drop_table("request_types")
    op.drop_table("marital_status_types")
    op.drop_table("prefix_type")
