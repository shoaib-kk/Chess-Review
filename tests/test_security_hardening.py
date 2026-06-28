"""Tests for the fail-closed DB credential guard and device-id validation.

These exercise pure functions only — no live database. The credential guard runs
at import time but never connects (``create_engine`` is lazy), so we test the
extracted ``_assert_strong_credentials`` directly with synthetic URLs.
"""

from __future__ import annotations

import os

import pytest

# backend.db creates an engine at import (no connect); needs a URL unless dev.
os.environ.setdefault("APP_ENV", "dev")

from fastapi import HTTPException  # noqa: E402

from backend.auth import current_device  # noqa: E402
from backend.db import _assert_strong_credentials  # noqa: E402

STRONG_URL = "postgresql+psycopg://chess:S0me-Str0ng-Secret@db:5432/chess"
WEAK_URL = "postgresql+psycopg://chess:chess@db:5432/chess"
NO_PASSWORD_URL = "postgresql+psycopg://chess@db:5432/chess"
# Strong password that merely *contains* the substring "chess" must NOT trip.
CHESSY_BUT_STRONG_URL = "postgresql+psycopg://chess:chess-7f3a9b2c1d@db:5432/chess"


def test_weak_credentials_rejected_in_prod():
    with pytest.raises(RuntimeError):
        _assert_strong_credentials(WEAK_URL, "production")


def test_missing_password_rejected_in_prod():
    with pytest.raises(RuntimeError):
        _assert_strong_credentials(NO_PASSWORD_URL, "production")


def test_strong_credentials_accepted_in_prod():
    # Must not raise.
    _assert_strong_credentials(STRONG_URL, "production")


def test_chessy_but_strong_password_not_false_positive():
    # Substring "chess" in a strong password must not be flagged.
    _assert_strong_credentials(CHESSY_BUT_STRONG_URL, "production")


def test_weak_credentials_exempt_in_dev():
    # Dev is allowed to use the weak local default.
    _assert_strong_credentials(WEAK_URL, "dev")


def test_nil_uuid_device_rejected():
    with pytest.raises(HTTPException):
        current_device("00000000-0000-0000-0000-000000000000")


def test_junk_device_rejected():
    with pytest.raises(HTTPException):
        current_device("not-a-uuid")


def test_valid_device_canonicalized():
    # Mixed case is canonicalised to lowercase.
    raw = "ABCDEF12-3456-7890-ABCD-EF1234567890"
    assert current_device(raw) == raw.lower()
