"""
16c: the cloud providers JobLens can use, in ONE place.

Until 1.2.0 only Claude could be chosen in the app; get_llm() had code for
OpenAI and Gemini, but their packages weren't shipped, Settings had no key
field for them, and nothing checked a key. This file is what Settings, the
key check and llm_status() all read, so adding a provider is one entry here.

No model names are built in for OpenAI and Gemini: they change every few
months, and a name that was right when this was written would be wrong by
the time you read it. The key check asks the provider which models YOUR key
can use, and Settings offers those.

Tests: tests/test_providers.py (no network: requests is replaced).
"""

import os
import re

import requests

CLOUD = {
    "anthropic": {
        "label": "Claude", "company": "Anthropic", "key": "ANTHROPIC_API_KEY", "key_hint": "sk-ant-…",
        "keys_url": "https://console.anthropic.com/settings/keys",
    },
    "openai": {
        "label": "OpenAI", "company": "OpenAI", "key": "OPENAI_API_KEY", "key_hint": "sk-…",
        "keys_url": "https://platform.openai.com/api-keys",
    },
    "google": {
        "label": "Gemini", "company": "Google", "key": "GOOGLE_API_KEY", "key_hint": "AIza…",
        "keys_url": "https://aistudio.google.com/apikey",
    },
}
PROVIDERS = ("ollama", *CLOUD)
KEY_NAMES = tuple(p["key"] for p in CLOUD.values())


def is_cloud(provider: str) -> bool:
    return provider in CLOUD


def key_name(provider: str) -> str | None:
    return CLOUD[provider]["key"] if provider in CLOUD else None


def saved_key(provider: str) -> str:
    name = key_name(provider)
    return os.getenv(name, "") if name else ""


# ---- which models can this key use? ------------------------------------------------

# Models that answer in text and can call tools. The lists the providers
# return also hold image, speech, embedding and other models.
_OPENAI_CHAT = re.compile(r"^(gpt-|o\d|chatgpt-)")
_NOT_CHAT = re.compile(r"embed|audio|realtime|tts|whisper|image|dall|transcribe|moderation|search|instruct|"
                       r"vision|live|imagen|veo|aqa|computer-use|robotics|codex", re.I)


def _openai_models(key: str, timeout: float) -> list[str]:
    r = requests.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {key}"}, timeout=timeout)
    r.raise_for_status()
    ids = [m.get("id", "") for m in r.json().get("data", [])]
    return sorted(i for i in ids if _OPENAI_CHAT.match(i) and not _NOT_CHAT.search(i))


def _google_models(key: str, timeout: float) -> list[str]:
    # The key goes in a header, not in the address: an address ends up in logs and error messages.
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", params={"pageSize": 200},
                     headers={"x-goog-api-key": key}, timeout=timeout)
    r.raise_for_status()
    names = [m.get("name", "").removeprefix("models/") for m in r.json().get("models", [])
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    return sorted(n for n in names if n.startswith("gemini") and not _NOT_CHAT.search(n))


def _anthropic_models(key: str, timeout: float) -> list[str]:
    r = requests.get("https://api.anthropic.com/v1/models", params={"limit": 100},
                     headers={"x-api-key": key, "anthropic-version": "2023-06-01"}, timeout=timeout)
    r.raise_for_status()
    return sorted(m.get("id", "") for m in r.json().get("data", []) if m.get("id"))


_LISTERS = {"openai": _openai_models, "google": _google_models, "anthropic": _anthropic_models}


def _plain(error: Exception, provider: str) -> str:
    """A provider's error in words you can act on. Never the key itself."""
    status = getattr(getattr(error, "response", None), "status_code", None)
    who = CLOUD[provider]["company"]
    if status in (401, 403) or (status == 400 and provider == "google"):
        return f"{who} didn't accept this key. Check that it was copied whole, and that it is a key for {who}."
    if status == 429:
        return f"{who} says this key is out of credit or over its limit. Check billing on your {who} account."
    if isinstance(error, requests.Timeout):
        return f"{who} didn't answer in time. Check your internet connection and try again."
    if isinstance(error, requests.ConnectionError):
        return f"Couldn't reach {who}. Check your internet connection."
    return f"{who} answered with an error" + (f" ({status})." if status else f": {type(error).__name__}.")


def list_models(provider: str, key: str = "", timeout: float = 15.0) -> dict:
    """Ask the provider which models this key can use. This is also the key
    check: a wrong key is refused here. Returns {"ok", "message", "models"}."""
    if provider not in CLOUD:
        raise ValueError(f"Unknown provider '{provider}'. Use: {', '.join(CLOUD)}.")
    key = (key or "").strip() or saved_key(provider)
    if not key:
        return {"ok": False, "message": "Paste an API key first.", "models": []}
    try:
        models = _LISTERS[provider](key, timeout)
    except Exception as e:  # wrong key, no network, a changed API...
        return {"ok": False, "message": _plain(e, provider), "models": []}
    if not models:
        return {"ok": False, "message": f"The key works, but {CLOUD[provider]['company']} lists no chat model for it.", "models": []}
    return {"ok": True, "message": f"The key works: {len(models)} models to choose from.", "models": models}
