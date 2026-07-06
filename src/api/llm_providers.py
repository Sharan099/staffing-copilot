"""Server-side provider and model catalog — frontend must not invent model names."""

from __future__ import annotations

SUPPORTED_PROVIDERS: dict[str, dict] = {
    "anthropic": {
        "label": "Anthropic (Claude)",
        "models": [
            {"id": "claude-sonnet-4-6", "label": "Claude Sonnet 4.6"},
            {"id": "claude-haiku-4-5", "label": "Claude Haiku 4.5"},
            {"id": "claude-opus-4-6", "label": "Claude Opus 4.6"},
        ],
    },
    "groq": {
        "label": "Groq (free tier)",
        "models": [
            {"id": "llama-3.1-8b-instant", "label": "Llama 3.1 8B Instant"},
            {"id": "llama-3.3-70b-versatile", "label": "Llama 3.3 70B Versatile"},
            {"id": "llama-4-scout-17b-16e-instruct", "label": "Llama 4 Scout 17B"},
            {"id": "gpt-oss-120b", "label": "GPT-OSS 120B"},
            {"id": "qwen3-32b", "label": "Qwen3 32B"},
        ],
    },
}


def list_providers_payload() -> dict:
    return {
        "providers": [
            {
                "id": provider_id,
                "label": meta["label"],
                "models": meta["models"],
            }
            for provider_id, meta in SUPPORTED_PROVIDERS.items()
        ]
    }


def is_valid_provider(provider: str) -> bool:
    return provider in SUPPORTED_PROVIDERS


def is_valid_model(provider: str, model_name: str) -> bool:
    if provider not in SUPPORTED_PROVIDERS:
        return False
    valid_ids = {m["id"] for m in SUPPORTED_PROVIDERS[provider]["models"]}
    return model_name in valid_ids
