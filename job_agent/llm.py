"""
LLM factory: the ONE place in the project that decides which model we talk to.

Why a factory?
    Every other file just calls `get_llm()` and gets back a LangChain chat model.
    All LangChain chat models share the same interface (.invoke, .bind_tools,
    .with_structured_output), so the rest of the agent never needs to know
    whether it's talking to a local Qwen or to Claude in the cloud.

How to switch models:
    Edit `.env` — change LLM_PROVIDER and LLM_MODEL. No code changes needed.
    (For a cloud provider, also `pip install` its package and set its API key.)
"""

import os

from langchain_core.language_models.chat_models import BaseChatModel

# Read settings (defaults + the .env file from paths.ENV_FILE) into
# environment variables. Phase 9a: no longer depends on the current folder.
from job_agent import settings  # noqa: F401  (loads on import)


def get_llm() -> BaseChatModel:
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    model = os.getenv("LLM_MODEL", "qwen3:8b")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))

    # ---- Local model via Ollama (current choice) ----
    # Runs on your machine: free, private, no API key. Ollama must be running.
    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=model,
            temperature=temperature,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            # qwen3 "thinking mode": True = it reasons step by step first
            # (slower, but you can inspect its reasoning). False = direct answer.
            reasoning=os.getenv("OLLAMA_REASONING", "false").lower() == "true",
            # Context window (tokens). Too small and long job pages get cut off
            # silently, so the model "forgets" the start of the text.
            num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "16384")),
        )

    # ---- Claude (Anthropic) ----
    # pip install langchain-anthropic ; set ANTHROPIC_API_KEY in .env
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model, temperature=temperature)

    # ---- OpenAI (GPT) ----
    # pip install langchain-openai ; set OPENAI_API_KEY in .env
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, temperature=temperature)

    # ---- Google Gemini ----
    # pip install langchain-google-genai ; set GOOGLE_API_KEY in .env
    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model=model, temperature=temperature)

    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}'. Use: ollama, anthropic, openai, google."
    )


# ---------------------------------------------------------------------------
# Phase 7: reliability helpers
# ---------------------------------------------------------------------------


def structured_llm(schema):
    """get_llm().with_structured_output(schema), retried up to 3 times.

    Small models occasionally return JSON that doesn't match the schema
    (a missing field, a string instead of a list). Pydantic rejects it, and
    .with_retry() simply asks again. Because temperature > 0, the next answer
    is usually valid. Every structured LLM call in the project goes through
    this function.
    """
    return get_llm().with_structured_output(schema).with_retry(stop_after_attempt=3)


def llm_status() -> tuple[bool, str]:
    """Can the configured model be used right now? Returns (ok, message).

    Returns the answer instead of exiting, so a GUI can show it (Phase 9b);
    the CLI wraps it in check_llm_ready() below.
    """
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    model = os.getenv("LLM_MODEL", "qwen3:8b")

    if provider == "anthropic":
        if not os.getenv("ANTHROPIC_API_KEY"):
            return False, "No Anthropic API key set. Add one in Settings."
        return True, f"Using Claude ({model}) with your API key."
    if provider != "ollama":
        return True, f"Using {provider} ({model})."

    import requests

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        tags = requests.get(f"{base_url}/api/tags", timeout=5).json()
    except requests.RequestException:
        return False, (f"Can't reach Ollama at {base_url}. Install it from "
                       "https://ollama.com and start the Ollama app.")
    installed = {m["name"] for m in tags.get("models", [])}
    if model not in installed:
        return False, (f"Model '{model}' isn't installed in Ollama. Run "
                       f"`ollama pull {model}`. Installed: "
                       f"{', '.join(sorted(installed)) or 'none'}")
    return True, f"Ollama is running and '{model}' is installed."


def check_llm_ready() -> None:
    """Fail fast with a clear message if the model can't be reached.

    Without this, a stopped Ollama shows up minutes later as a long
    'connection refused' traceback in the middle of the run.
    """
    ok, message = llm_status()
    if not ok:
        raise SystemExit(message)
