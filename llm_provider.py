"""
LLM Provider — unified interface for Anthropic, OpenAI, and Ollama backends.
Reads config from data/config.json. Falls back to first available provider.
"""

import json
import os
import time
import requests as http_requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

# Default models per provider
DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
    "ollama": "llama3.1:latest",
}

# Known models per provider (for settings UI)
KNOWN_MODELS = {
    "anthropic": [
        ("claude-sonnet-4-20250514", "Claude Sonnet 4"),
        ("claude-haiku-4-5-20251001", "Claude Haiku 4.5"),
    ],
    "openai": [
        ("gpt-4o", "GPT-4o"),
        ("gpt-4o-mini", "GPT-4o Mini"),
        ("gpt-4.1", "GPT-4.1"),
        ("gpt-4.1-mini", "GPT-4.1 Mini"),
    ],
}


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_config() -> dict:
    """Load provider config from data/config.json."""
    _ensure_data_dir()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_config(config: dict):
    """Save provider config to data/config.json."""
    _ensure_data_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def _check_anthropic_available() -> bool:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    return bool(key and key != "your_api_key_here")


def _check_openai_available() -> bool:
    key = os.environ.get("OPENAI_API_KEY", "")
    return bool(key and key != "your_api_key_here")


def _check_ollama_available() -> bool:
    try:
        resp = http_requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


def get_ollama_models() -> list[str]:
    """Fetch list of models from Ollama."""
    try:
        resp = http_requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        pass
    return []


def get_available_providers() -> list[dict]:
    """Return list of providers with availability status."""
    providers = []

    providers.append({
        "id": "anthropic",
        "name": "Anthropic (Claude)",
        "available": _check_anthropic_available(),
        "models": [{"id": m[0], "name": m[1]} for m in KNOWN_MODELS["anthropic"]],
        "icon": "🟣",
    })

    providers.append({
        "id": "openai",
        "name": "OpenAI (GPT)",
        "available": _check_openai_available(),
        "models": [{"id": m[0], "name": m[1]} for m in KNOWN_MODELS["openai"]],
        "icon": "🟢",
    })

    ollama_available = _check_ollama_available()
    ollama_models = get_ollama_models() if ollama_available else []
    providers.append({
        "id": "ollama",
        "name": "Ollama (Local)",
        "available": ollama_available,
        "models": [{"id": m, "name": m} for m in ollama_models],
        "icon": "🦙",
    })

    return providers


def get_current_provider_info() -> dict:
    """Get currently configured provider and model."""
    config = load_config()
    provider = config.get("provider", "")
    model = config.get("model", "")

    # Auto-detect if not configured
    if not provider:
        if _check_ollama_available():
            provider = "ollama"
            model = DEFAULT_MODELS["ollama"]
        elif _check_anthropic_available():
            provider = "anthropic"
            model = DEFAULT_MODELS["anthropic"]
        elif _check_openai_available():
            provider = "openai"
            model = DEFAULT_MODELS["openai"]
        else:
            provider = "ollama"
            model = DEFAULT_MODELS["ollama"]

    if not model:
        model = DEFAULT_MODELS.get(provider, "")

    return {"provider": provider, "model": model}


# ---------------------------------------------------------------------------
# Core LLM call — the single function all features use
# ---------------------------------------------------------------------------

def call_llm(system_prompt: str, user_message: str, max_tokens: int = 500) -> str:
    """Call the configured LLM provider and return raw text response."""
    info = get_current_provider_info()
    provider = info["provider"]
    model = info["model"]

    if provider == "anthropic":
        return _call_anthropic(system_prompt, user_message, model, max_tokens)
    elif provider == "openai":
        return _call_openai(system_prompt, user_message, model, max_tokens)
    elif provider == "ollama":
        return _call_ollama(system_prompt, user_message, model, max_tokens)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def _call_anthropic(system_prompt: str, user_message: str, model: str, max_tokens: int) -> str:
    import anthropic
    client = anthropic.Anthropic()
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text.strip()


def _call_openai(system_prompt: str, user_message: str, model: str, max_tokens: int) -> str:
    import openai
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content.strip()


def _call_ollama(system_prompt: str, user_message: str, model: str, max_tokens: int) -> str:
    resp = http_requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
            "options": {"num_predict": max_tokens},
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("message", {}).get("content", "").strip()
