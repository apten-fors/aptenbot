"""Provider registry: single source of truth for chat providers.

Built-in providers (openai, anthropic, gemini, grok) are derived from the
constants in ``config.py``. Additional self-hosted, OpenAI-compatible providers
are declared via the ``CUSTOM_PROVIDERS`` env var (comma-separated prefixes).
For each prefix ``X`` the following env vars are read:

    X_API_KEY         required  - API key for the endpoint
    X_BASE_URL        required  - OpenAI-compatible base URL (.../v1)
    X_MODELS          required  - comma-separated model ids the server exposes
    X_DEFAULT_MODEL   optional  - defaults to the first entry of X_MODELS
    X_NAME            optional  - display name shown in the /provider menu
    X_SUPPORTS_IMAGES optional  - "true" to enable vision (default: text only)

Custom providers use the ``/v1/chat/completions`` API (api_style "openai_chat"),
exactly like Grok. A provider only becomes *enabled* once its required
credentials are present, so the /provider menu and message dispatch
automatically reflect what is actually configured.

This module reads the environment once at import time, consistent with
``config.py``. It must not import client classes or ``managers`` (no cycles).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

from config import (
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    GEMINI_API_KEY,
    GROK_API_KEY,
    GROK_BASE_URL,
    OPENAI_MODEL,
    ANTHROPIC_MODEL,
    GEMINI_MODEL,
    GROK_MODEL,
    OPENAI_ALLOWED_MODELS,
    ANTHROPIC_ALLOWED_MODELS,
    GEMINI_ALLOWED_MODELS,
    GROK_ALLOWED_MODELS,
    DEFAULT_MODEL_PROVIDER,
)

# Supported API styles. The first three keep the existing per-provider logic in
# managers.session_manager; "openai_chat" is the generic /v1/chat/completions
# path shared by Grok and all custom providers.
OPENAI_RESPONSES = "openai_responses"
ANTHROPIC_STYLE = "anthropic"
GEMINI_STYLE = "gemini"
OPENAI_CHAT = "openai_chat"

_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ProviderConfig:
    id: str
    name: str
    api_style: str
    api_key: Optional[str]
    base_url: Optional[str]
    models: List[str]
    default_model: str
    supports_images: bool = True

    @property
    def is_enabled(self) -> bool:
        """A provider is usable only when its required credentials exist."""
        if not self.api_key:
            return False
        if self.api_style == OPENAI_CHAT and not self.base_url:
            return False
        if not self.models:
            return False
        return True


def _split_csv(value: Optional[str]) -> List[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def _builtin_providers() -> List[ProviderConfig]:
    return [
        ProviderConfig(
            id="openai", name="OpenAI", api_style=OPENAI_RESPONSES,
            api_key=OPENAI_API_KEY, base_url=None,
            models=OPENAI_ALLOWED_MODELS, default_model=OPENAI_MODEL,
            supports_images=True,
        ),
        ProviderConfig(
            id="anthropic", name="Claude (Anthropic)", api_style=ANTHROPIC_STYLE,
            api_key=ANTHROPIC_API_KEY, base_url=None,
            models=ANTHROPIC_ALLOWED_MODELS, default_model=ANTHROPIC_MODEL,
            supports_images=True,
        ),
        ProviderConfig(
            id="gemini", name="Gemini (Google)", api_style=GEMINI_STYLE,
            api_key=GEMINI_API_KEY, base_url=None,
            models=GEMINI_ALLOWED_MODELS, default_model=GEMINI_MODEL,
            supports_images=True,
        ),
        ProviderConfig(
            id="grok", name="Grok", api_style=OPENAI_CHAT,
            api_key=GROK_API_KEY, base_url=GROK_BASE_URL,
            models=GROK_ALLOWED_MODELS, default_model=GROK_MODEL,
            supports_images=True,
        ),
    ]


def _custom_providers() -> List[ProviderConfig]:
    providers: List[ProviderConfig] = []
    for prefix in _split_csv(os.getenv("CUSTOM_PROVIDERS", "")):
        pid = prefix.lower()
        env = prefix.upper()
        models = _split_csv(os.getenv(f"{env}_MODELS"))
        default_model = os.getenv(f"{env}_DEFAULT_MODEL") or (models[0] if models else "")
        supports_images = (
            os.getenv(f"{env}_SUPPORTS_IMAGES", "").strip().lower() in _TRUE_VALUES
        )
        providers.append(ProviderConfig(
            id=pid,
            name=os.getenv(f"{env}_NAME", prefix.capitalize()),
            api_style=OPENAI_CHAT,
            api_key=os.getenv(f"{env}_API_KEY"),
            base_url=os.getenv(f"{env}_BASE_URL"),
            models=models,
            default_model=default_model,
            supports_images=supports_images,
        ))
    return providers


# Built once at import. Order is deterministic (built-ins first, then the
# CUSTOM_PROVIDERS order) — the numbered /provider menu relies on this stability.
ALL_PROVIDERS: List[ProviderConfig] = _builtin_providers() + _custom_providers()
_BY_ID = {p.id: p for p in ALL_PROVIDERS}


def all_providers() -> List[ProviderConfig]:
    """Every declared provider, regardless of whether credentials are present."""
    return list(ALL_PROVIDERS)


def enabled_providers() -> List[ProviderConfig]:
    """Providers that are actually usable (credentials present)."""
    return [p for p in ALL_PROVIDERS if p.is_enabled]


def get_provider(provider_id: str) -> Optional[ProviderConfig]:
    return _BY_ID.get(provider_id)


def provider_ids() -> List[str]:
    """Ordered ids of enabled providers (the order the /provider menu uses)."""
    return [p.id for p in enabled_providers()]


def default_provider_id() -> str:
    """The configured default provider if enabled, else the first enabled one.

    Falls back to the raw DEFAULT_MODEL_PROVIDER when nothing is enabled (e.g.
    tests/dev without credentials), keeping behavior stable.
    """
    enabled = enabled_providers()
    for p in enabled:
        if p.id == DEFAULT_MODEL_PROVIDER:
            return p.id
    if enabled:
        return enabled[0].id
    return DEFAULT_MODEL_PROVIDER


def models_for(provider_id: str) -> List[str]:
    p = get_provider(provider_id)
    return list(p.models) if p else []


def default_model_for(provider_id: str) -> str:
    """Default model id for a provider, with a safe fallback."""
    p = get_provider(provider_id)
    if p and p.default_model:
        return p.default_model
    fallback = get_provider(default_provider_id())
    return fallback.default_model if fallback else ""


def is_image_capable(provider_id: str) -> bool:
    p = get_provider(provider_id)
    return bool(p and p.supports_images)
