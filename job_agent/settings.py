"""
Phase 9a: read and write the app's settings (the .env file) from code.

Until now you edited .env by hand. A desktop app's Setup screen must do it
for the user: pick a model, paste an API key, turn tracing on/off.

How it fits together:
    - Settings live in paths.ENV_FILE (repo .env in developer mode,
      %LOCALAPPDATA%\\JobLens\\.env in the installed app).
    - load_settings() copies them into os.environ at startup.
    - get_llm() reads os.environ on EVERY call, so save_settings() takes
      effect immediately - no restart needed.
"""

import os

from dotenv import dotenv_values, load_dotenv, set_key

from job_agent.paths import APP_HOME, ENV_FILE

# What a brand-new install starts with: local, private, free.
DEFAULTS = {
    "LLM_PROVIDER": "ollama",
    "LLM_MODEL": "qwen3:8b",
    "LLM_TEMPERATURE": "0.2",
    "OLLAMA_BASE_URL": "http://localhost:11434",
    "OLLAMA_REASONING": "false",
    "OLLAMA_NUM_CTX": "16384",
    "JUDGE_EVIDENCE": "true",
    "TRACING": "off",
}

# Suggested model per provider for the Setup screen.
DEFAULT_MODELS = {"ollama": "qwen3:8b", "anthropic": "claude-haiku-5-5"}


def load_settings() -> None:
    """Defaults first, then the .env file. Real environment variables win
    (override=False), so a value set in the terminal still beats the file."""
    for key, value in DEFAULTS.items():
        os.environ.setdefault(key, value)
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=False)


def read_settings() -> dict:
    """Current values (file merged over defaults) - for showing in a form."""
    values = dict(DEFAULTS)
    if ENV_FILE.exists():
        values.update({k: v for k, v in dotenv_values(ENV_FILE).items() if v is not None})
    return values


def save_settings(updates: dict) -> None:
    """Write changed values to the .env file AND apply them right away."""
    APP_HOME.mkdir(parents=True, exist_ok=True)
    ENV_FILE.touch(exist_ok=True)
    for key, value in updates.items():
        value = "" if value is None else str(value)
        set_key(str(ENV_FILE), key, value, quote_mode="never")
        os.environ[key] = value


def has_api_key(provider: str) -> bool:
    key_name = {"anthropic": "ANTHROPIC_API_KEY"}.get(provider)
    return bool(key_name and os.getenv(key_name))


# Load once, as soon as any part of the agent imports this module.
load_settings()
