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

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel

# Read key=value pairs from .env into environment variables.
load_dotenv()


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


def check_llm_ready() -> None:
    """Fail fast with a clear message if the model can't be reached.

    Without this, a stopped Ollama shows up minutes later as a long
    'connection refused' traceback in the middle of the run.
    """
    if os.getenv("LLM_PROVIDER", "ollama").lower() != "ollama":
        return  # cloud providers: a missing API key fails fast on its own

    import requests

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.getenv("LLM_MODEL", "qwen3:8b")
    try:
        tags = requests.get(f"{base_url}/api/tags", timeout=5).json()
    except requests.RequestException:
        raise SystemExit(
            f"Can't reach Ollama at {base_url}. Start the Ollama app "
            "(or run `ollama serve`) and try again."
        )
    installed = {m["name"] for m in tags.get("models", [])}
    if model not in installed:
        raise SystemExit(
            f"Model '{model}' isn't installed in Ollama. Run `ollama pull {model}` "
            f"or change LLM_MODEL in .env. Installed: {', '.join(sorted(installed))}"
        )
