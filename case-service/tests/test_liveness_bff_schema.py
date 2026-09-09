"""Regression — BFF WelfareCaseCreate ต้องคง liveness_reference_id ใน model_dump().

บั๊กที่เคยเกิด: bff-vsmartcare มี schema สำเนาแยกจาก case-service แล้ว create_case()
ทำ body.model_dump() ก่อน forward · pydantic ตัดฟิลด์ที่ schema ไม่รู้จักทิ้งเงียบ
ผลคือ frontend ส่ง reference มาถูก แต่ case-service ได้แถว completed ค้าง + NO_ATTEMPT คู่กัน
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

def _bff_schema_path() -> Path:
    """หา welfare_case_schema ของ BFF ทั้งบน host (sibling ของ case-service) และใน Docker"""
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "bff-vsmartcare" / "app" / "welfare_case_schema.py",
        Path("/opt/bff-vsmartcare/app/welfare_case_schema.py"),
    ]
    for parent in [here.parent, *here.parents]:
        candidates.append(parent / "bff-vsmartcare" / "app" / "welfare_case_schema.py")
        candidates.append(parent / "apps" / "service" / "bff-vsmartcare" / "app" / "welfare_case_schema.py")
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


_BFF_SCHEMA_PATH = _bff_schema_path()


def _load_bff_welfare_case_create():
    spec = importlib.util.spec_from_file_location(
        "bff_welfare_case_schema_for_test",
        _BFF_SCHEMA_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.WelfareCaseCreate.model_rebuild()
    return module.WelfareCaseCreate


class BffWelfareCaseCreateSchemaTests(unittest.TestCase):
    def test_schema_file_exists(self) -> None:
        self.assertTrue(_BFF_SCHEMA_PATH.is_file(), str(_BFF_SCHEMA_PATH))

    def test_liveness_reference_id_is_a_declared_field(self) -> None:
        schema = _load_bff_welfare_case_create()
        self.assertIn("liveness_reference_id", schema.model_fields)

    def test_model_dump_keeps_liveness_reference_id(self) -> None:
        schema = _load_bff_welfare_case_create()
        body = schema(
            applicant={
                "persons_id": 1,
                "requester_relation_id": 1,
                "marital_status_id": 1,
            },
            request_type_ids=[1],
            liveness_reference_id="8b0f4a5c-1111-2222-3333-444455556666",
        )
        dumped = body.model_dump()
        self.assertIn("liveness_reference_id", dumped)
        self.assertEqual(
            dumped["liveness_reference_id"],
            "8b0f4a5c-1111-2222-3333-444455556666",
        )

    def test_case_service_schema_also_declares_the_field(self) -> None:
        from app.schemas.case_welfare import WelfareCaseCreate

        self.assertIn("liveness_reference_id", WelfareCaseCreate.model_fields)
        body = WelfareCaseCreate(
            applicant={
                "persons_id": 1,
                "requester_relation_id": 1,
                "marital_status_id": 1,
            },
            request_type_ids=[1],
            liveness_reference_id="ref-from-session",
        )
        self.assertEqual(body.model_dump()["liveness_reference_id"], "ref-from-session")


if __name__ == "__main__":
    unittest.main()
