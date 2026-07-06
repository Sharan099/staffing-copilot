"""Per-manager LLM provider credentials (encrypted at rest)."""

from __future__ import annotations

import datetime

from api.encryption import decrypt_api_key, encrypt_api_key
from api.llm_providers import is_valid_model, is_valid_provider
from data.db import get_users_conn


def ensure_manager_credentials_schema(conn) -> None:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS manager_credentials (
        manager_id TEXT PRIMARY KEY,
        provider TEXT NOT NULL,
        model_name TEXT NOT NULL,
        encrypted_api_key TEXT NOT NULL,
        iv TEXT NOT NULL,
        key_last4 TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)
    conn.commit()


def get_credentials_masked(manager_id: str) -> dict | None:
    conn = get_users_conn()
    ensure_manager_credentials_schema(conn)
    row = conn.execute(
        """
        SELECT provider, model_name, key_last4, updated_at
        FROM manager_credentials WHERE manager_id = ?
        """,
        (manager_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "configured": True,
        "provider": row[0],
        "model_name": row[1],
        "key_last4": row[2],
        "updated_at": row[3],
    }


def get_credentials_for_call(manager_id: str) -> dict | None:
    """Load encrypted row and decrypt API key in-memory for LLM calls only."""
    conn = get_users_conn()
    ensure_manager_credentials_schema(conn)
    row = conn.execute(
        """
        SELECT provider, model_name, encrypted_api_key, iv, key_last4
        FROM manager_credentials WHERE manager_id = ?
        """,
        (manager_id,),
    ).fetchone()
    if row is None:
        return None
    provider, model_name, encrypted_api_key, iv, key_last4 = row
    api_key = decrypt_api_key(encrypted_api_key, iv)
    return {
        "provider": provider,
        "model_name": model_name,
        "api_key": api_key,
        "key_last4": key_last4,
    }


def save_credentials(
    manager_id: str,
    provider: str,
    model_name: str,
    api_key: str,
) -> dict:
    if not is_valid_provider(provider):
        raise ValueError(f"Unsupported provider: {provider}")
    if not is_valid_model(provider, model_name):
        raise ValueError(f"Unsupported model for {provider}: {model_name}")

    key = (api_key or "").strip()
    if len(key) < 8:
        raise ValueError("API key is too short")

    ciphertext, iv = encrypt_api_key(key)
    key_last4 = key[-4:]
    updated_at = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")

    conn = get_users_conn()
    ensure_manager_credentials_schema(conn)
    conn.execute(
        """
        INSERT INTO manager_credentials
        (manager_id, provider, model_name, encrypted_api_key, iv, key_last4, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(manager_id) DO UPDATE SET
            provider = excluded.provider,
            model_name = excluded.model_name,
            encrypted_api_key = excluded.encrypted_api_key,
            iv = excluded.iv,
            key_last4 = excluded.key_last4,
            updated_at = excluded.updated_at
        """,
        (manager_id, provider, model_name, ciphertext, iv, key_last4, updated_at),
    )
    conn.commit()

    return {
        "configured": True,
        "provider": provider,
        "model_name": model_name,
        "key_last4": key_last4,
        "updated_at": updated_at,
    }
