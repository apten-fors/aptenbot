import os
import sys
from types import SimpleNamespace

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from utils.guest import (
    parse_guest_allowed_user_ids,
    is_guest_allowed,
    build_guest_session_key,
    trim_guest_response,
    extract_guest_caller_user_id,
)


# --- parse_guest_allowed_user_ids ---

def test_parse_allowed_user_ids_basic():
    assert parse_guest_allowed_user_ids("123456789,987654321") == {123456789, 987654321}


def test_parse_allowed_user_ids_handles_whitespace_and_trailing_comma():
    assert parse_guest_allowed_user_ids(" 123 , 456 ,") == {123, 456}


def test_parse_allowed_user_ids_skips_non_numeric():
    assert parse_guest_allowed_user_ids("123,abc,456") == {123, 456}


def test_parse_allowed_user_ids_empty_and_none():
    assert parse_guest_allowed_user_ids("") == set()
    assert parse_guest_allowed_user_ids(None) == set()


# --- is_guest_allowed ---

def test_disabled_mode_denies_even_listed_user():
    assert is_guest_allowed(123, "disabled", {123}) is False


def test_missing_user_id_denied():
    assert is_guest_allowed(None, "allowlist", {123}) is False
    assert is_guest_allowed(None, "public", set()) is False


def test_allowlist_allows_listed_and_denies_unlisted():
    assert is_guest_allowed(123, "allowlist", {123, 456}) is True
    assert is_guest_allowed(999, "allowlist", {123, 456}) is False


def test_allowlist_empty_denies_all_fail_closed():
    assert is_guest_allowed(123, "allowlist", set()) is False


def test_public_allows_any_valid_user_without_allowlist():
    assert is_guest_allowed(123, "public", set()) is True


def test_unknown_mode_denied():
    assert is_guest_allowed(123, "something_else", {123}) is False


# --- build_guest_session_key ---

def test_build_guest_session_key_format():
    assert build_guest_session_key(123, "q-1") == "telegram:guest:123:q-1"


# --- trim_guest_response ---

def test_trim_under_limit_unchanged():
    assert trim_guest_response("hello", 3500) == "hello"


def test_trim_over_limit():
    assert trim_guest_response("a" * 10, 4) == "aaaa"


def test_trim_none_and_empty():
    assert trim_guest_response(None, 100) == ""
    assert trim_guest_response("", 100) == ""


def test_trim_non_positive_limit_no_trim():
    assert trim_guest_response("hello", 0) == "hello"


# --- extract_guest_caller_user_id ---

def test_extract_caller_user_id_present():
    msg = SimpleNamespace(from_user=SimpleNamespace(id=42))
    assert extract_guest_caller_user_id(msg) == 42


def test_extract_caller_user_id_missing_from_user():
    msg = SimpleNamespace(from_user=None)
    assert extract_guest_caller_user_id(msg) is None
    msg2 = SimpleNamespace()
    assert extract_guest_caller_user_id(msg2) is None
