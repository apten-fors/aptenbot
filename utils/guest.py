"""Pure helpers for Telegram Guest Mode.

These functions are intentionally dependency-light: they must NOT import
``config`` (``config`` imports ``parse_guest_allowed_user_ids`` from here) and
they must not touch aiogram or any AI client. This keeps them trivially
unit-testable and free of import cycles.
"""
from typing import Optional, Set


def parse_guest_allowed_user_ids(raw: Optional[str]) -> Set[int]:
    """Parse a comma-separated list of caller user ids into a set of ints.

    Mirrors the comma-list parsing style used in ``config.py`` for ``CHANNEL_ID``.
    Blank and non-numeric tokens are skipped (fail-soft) so a stray entry cannot
    break startup.
    """
    if not raw:
        return set()
    ids: Set[int] = set()
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            ids.add(int(token))
        except ValueError:
            # Skip non-numeric entries rather than crashing on a typo.
            continue
    return ids


def is_guest_allowed(
    user_id: Optional[int], access_mode: str, allowed_user_ids: Set[int]
) -> bool:
    """Decide whether a guest request is allowed, based ONLY on the caller user id.

    Rules (see TECHNICAL_SPECIFICATION.md):
      - access mode ``disabled`` -> deny.
      - missing ``user_id`` -> deny.
      - ``allowlist`` -> allow only if ``user_id`` is in ``allowed_user_ids``.
        An empty allowlist therefore denies everyone (fail closed).
      - ``public`` -> allow any valid caller user id.
      - any other / unknown mode -> deny.

    The source chat id is deliberately NOT a parameter: it must never gate access.
    """
    if access_mode == "disabled":
        return False
    if user_id is None:
        return False
    if access_mode == "allowlist":
        return user_id in allowed_user_ids
    if access_mode == "public":
        return True
    return False


def build_guest_session_key(caller_user_id: int, guest_query_id: str) -> str:
    """Build the isolated, one-shot session key for a guest request."""
    return f"telegram:guest:{caller_user_id}:{guest_query_id}"


def trim_guest_response(text: Optional[str], max_chars: int) -> str:
    """Trim a guest answer to ``max_chars`` characters.

    Guards against ``None``/empty input. A non-positive ``max_chars`` leaves the
    text untouched (no trimming requested).
    """
    if not text:
        return ""
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars]


def extract_guest_caller_user_id(message) -> Optional[int]:
    """Return the caller user id for a guest message: ``message.from_user.id``.

    Defensive against a missing ``from_user``. Per the spec, this must NOT fall
    back to ``guest_bot_caller_user`` for authorization.
    """
    user = getattr(message, "from_user", None)
    if user is None:
        return None
    return getattr(user, "id", None)
