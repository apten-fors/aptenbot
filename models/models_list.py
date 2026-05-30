from providers import enabled_providers, get_provider, default_provider_id

# Provider-selection list, generated from the registry so it always reflects the
# providers that are actually configured (built-ins + CUSTOM_PROVIDERS).
MODELS = [
    {"id": p.id, "name": p.name, "provider": p.id}
    for p in enabled_providers()
]

# Default provider as a model dict. ``default_provider_id`` always returns a
# valid id (falling back to the configured default), so DEFAULT_MODEL is safe
# even when nothing is enabled (e.g. tests without credentials).
_default_id = default_provider_id()
_default_provider = get_provider(_default_id)
DEFAULT_MODEL = {
    "id": _default_id,
    "name": _default_provider.name if _default_provider else _default_id,
    "provider": _default_id,
}
