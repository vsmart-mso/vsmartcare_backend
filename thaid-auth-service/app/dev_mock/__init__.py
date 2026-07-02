"""Dev-only mock ThaiD OIDC helpers (profile generation, seed data)."""

from .profile import (
    describe_birthdate_scenario,
    estimate_age_years,
    generate_fixed_mock_profile,
    generate_mock_profile,
    generate_mock_thai_cid,
    get_max_mock_age,
    get_mock_addresses,
    get_mock_provinces_from_seed,
    load_mock_seed,
    mock_profile_preview_fields,
    parse_province_from_profile,
    random_mock_birthdate,
    strip_internal_profile_keys,
    validate_thai_cid,
)

__all__ = [
    "describe_birthdate_scenario",
    "estimate_age_years",
    "generate_fixed_mock_profile",
    "generate_mock_profile",
    "generate_mock_thai_cid",
    "get_max_mock_age",
    "get_mock_addresses",
    "get_mock_provinces_from_seed",
    "load_mock_seed",
    "mock_profile_preview_fields",
    "parse_province_from_profile",
    "random_mock_birthdate",
    "strip_internal_profile_keys",
    "validate_thai_cid",
]
