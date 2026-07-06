"""Extract client and domain context from natural-language staffing requests."""

from __future__ import annotations

INDUSTRIES = (
    "healthcare",
    "finance",
    "retail",
    "manufacturing",
    "automotive",
    "mobility",
    "software",
)

KNOWN_CLIENTS = (
    "BMW",
    "Bosch",
    "Siemens",
    "Siemens Healthineers",
    "Continental",
    "SAP",
    "Mercedes",
    "Volkswagen",
    "Audi",
)


def extract_staffing_context(client_message: str) -> dict[str, str | None]:
    text = (client_message or "").lower()
    domain = next((ind for ind in INDUSTRIES if ind in text), "general")
    client_name = None
    for client in KNOWN_CLIENTS:
        if client.lower() in text:
            client_name = client
            break
    return {"domain": domain, "client_name": client_name}
