"""Unit tests for the provider registry (providers.py).

The registry reads the environment once at import time, so these tests reload
the module under a patched os.environ to exercise CUSTOM_PROVIDERS parsing,
enablement filtering, and the stable index->provider mapping the /provider menu
relies on.
"""
import importlib
import os
import sys
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _load_providers(env):
    """Import a fresh providers module with the given environment."""
    with patch.dict(os.environ, env, clear=True):
        import config
        import providers
        importlib.reload(config)
        importlib.reload(providers)
        return providers


def _custom_env():
    return {
        "OPENAI_API_KEY": "x",
        "ANTHROPIC_API_KEY": "y",
        "CUSTOM_PROVIDERS": "kimi,glm,deepseek",
        "KIMI_API_KEY": "k",
        "KIMI_BASE_URL": "https://kimi.local/v1",
        "KIMI_MODELS": "kimi26,kimi-vl",
        "KIMI_NAME": "Kimi",
        "GLM_API_KEY": "g",
        "GLM_BASE_URL": "https://glm.local/v1",
        "GLM_MODELS": "glm-4",
        # deepseek deliberately has NO api key -> must be excluded
        "DEEPSEEK_BASE_URL": "https://ds.local/v1",
        "DEEPSEEK_MODELS": "deepseek-chat",
    }


def test_custom_providers_parsed_and_enabled():
    P = _load_providers(_custom_env())
    ids = P.provider_ids()
    # openai + anthropic (keys present) and kimi + glm (key+url+models present)
    assert ids == ["openai", "anthropic", "kimi", "glm"]


def test_custom_provider_fields():
    P = _load_providers(_custom_env())
    kimi = P.get_provider("kimi")
    assert kimi.name == "Kimi"
    assert kimi.api_style == P.OPENAI_CHAT
    assert kimi.base_url == "https://kimi.local/v1"
    assert P.models_for("kimi") == ["kimi26", "kimi-vl"]
    assert P.default_model_for("kimi") == "kimi26"  # first model by default
    assert P.is_image_capable("kimi") is False       # text-only by default


def test_provider_missing_credentials_excluded():
    P = _load_providers(_custom_env())
    # deepseek is declared but has no API key, so it must not be enabled.
    assert P.get_provider("deepseek") is not None
    assert P.get_provider("deepseek").is_enabled is False
    assert "deepseek" not in P.provider_ids()


def test_menu_index_mapping_is_stable():
    P = _load_providers(_custom_env())
    enabled = P.enabled_providers()
    # The numbered /provider menu maps (index+1) -> enabled_providers()[index].
    menu = {i + 1: p.id for i, p in enumerate(enabled)}
    assert menu == {1: "openai", 2: "anthropic", 3: "kimi", 4: "glm"}


def test_default_provider_falls_back_when_default_disabled():
    env = _custom_env()
    env["DEFAULT_MODEL_PROVIDER"] = "grok"  # grok has no key -> not enabled
    P = _load_providers(env)
    # Falls back to the first enabled provider.
    assert P.default_provider_id() == "openai"


def test_supports_images_flag_can_be_enabled():
    env = _custom_env()
    env["KIMI_SUPPORTS_IMAGES"] = "true"
    P = _load_providers(env)
    assert P.is_image_capable("kimi") is True


def test_builtin_image_capability_preserved():
    P = _load_providers(_custom_env())
    assert P.is_image_capable("openai") is True
    assert P.is_image_capable("anthropic") is True
