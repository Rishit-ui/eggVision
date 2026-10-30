"""Regression coverage for the pinned passlib/bcrypt compatibility pair."""

import bcrypt
import passlib

from app.middleware.auth import hash_password, verify_password


def test_bcrypt_dependency_versions_are_pinned_compatibly() -> None:
    assert passlib.__version__ == "1.7.4"
    assert bcrypt.__version__ == "4.0.1"


def test_new_password_hash_verifies_without_bcrypt_about_error() -> None:
    password = "bootstrap-password-for-test-only"
    password_hash = hash_password(password)

    assert password_hash.startswith("$2")
    assert verify_password(password, password_hash) is True
    assert verify_password("wrong-password", password_hash) is False
