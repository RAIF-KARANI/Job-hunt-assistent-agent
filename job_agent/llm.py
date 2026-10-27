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
