"""16c: OpenAI and Gemini beside Claude. No network and no real key:
`requests.get` is replaced, and the chat models are only built, never called."""

import pytest
import requests
from langchain_core.messages import AIMessage

from desktop_web import bridge
from desktop_web.bridge import Api
from job_agent import llm, paths, providers, settings, system_check


class Answer:
    def __init__(self, data=None, status=200):
        self.data, self.status_code = data or {}, status

    def json(self):
        return self.data

    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError(f"{self.status_code} error")
            error.response = self
            raise error


def web(monkeypatch, answer):
    """Every requests.get returns `answer` (or raises it); the calls are kept."""
    calls = []

    def get(url, **kwargs):
        calls.append({"url": url, **kwargs})
        if isinstance(answer, Exception):
            raise answer
        return answer
    monkeypatch.setattr(providers.requests, "get", get)
    return calls


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A settings file of its own, and no provider key from the real one."""
    monkeypatch.setattr(settings, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(settings, "APP_HOME", tmp_path)
    for name in (*providers.KEY_NAMES, "LLM_PROVIDER", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path / ".env"


# ---- which models can this key use? ----------------------------------------------------

def test_openai_lists_only_chat_models(monkeypatch):
    calls = web(monkeypatch, Answer({"data": [{"id": i} for i in (
        "gpt-x-mini", "gpt-x", "o9-mini", "text-embedding-3-small", "whisper-1", "gpt-x-realtime-preview",
        "gpt-image-1", "tts-1", "omni-moderation-latest", "gpt-x-search-preview", "davinci-002", "chatgpt-x-latest")]}))
    result = providers.list_models("openai", "sk-test")
    assert result["ok"] and result["models"] == ["chatgpt-x-latest", "gpt-x", "gpt-x-mini", "o9-mini"]
    assert calls[0]["headers"] == {"Authorization": "Bearer sk-test"}


def test_gemini_lists_only_models_that_generate_text(monkeypatch):
    calls = web(monkeypatch, Answer({"models": [
        {"name": "models/gemini-x-flash", "supportedGenerationMethods": ["generateContent", "countTokens"]},
        {"name": "models/gemini-x-pro", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-embedding-001", "supportedGenerationMethods": ["embedContent"]},
        {"name": "models/gemini-x-flash-image", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-x-flash-live", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/imagen-9", "supportedGenerationMethods": ["predict"]},
        {"name": "models/gemma-9", "supportedGenerationMethods": ["generateContent"]}]}))
    result = providers.list_models("google", "AIza-test")
    assert result["models"] == ["gemini-x-flash", "gemini-x-pro"]
    assert calls[0]["headers"] == {"x-goog-api-key": "AIza-test"}
    assert "AIza-test" not in calls[0]["url"] and "AIza-test" not in str(calls[0].get("params"))   # never in the address


@pytest.mark.parametrize("provider, status, says", [
    ("openai", 401, "OpenAI didn't accept this key"),
    ("google", 400, "Google didn't accept this key"),      # Gemini answers 400 to a wrong key
    ("anthropic", 401, "Anthropic didn't accept this key"),
    ("openai", 429, "out of credit or over its limit"),
    ("google", 500, "answered with an error (500)"),
])
def test_a_refused_key_is_explained_without_showing_it(monkeypatch, provider, status, says):
    web(monkeypatch, Answer(status=status))
    result = providers.list_models(provider, "sk-secret-123")
    assert not result["ok"] and says in result["message"] and result["models"] == []
    assert "sk-secret-123" not in result["message"]


def test_no_network_and_no_key(monkeypatch, env):
    web(monkeypatch, requests.ConnectionError("dns"))
    assert "Couldn't reach OpenAI" in providers.list_models("openai", "sk-test")["message"]
    web(monkeypatch, requests.Timeout())
    assert "didn't answer in time" in providers.list_models("google", "k")["message"]
    calls = web(monkeypatch, Answer())
    assert providers.list_models("openai")["message"] == "Paste an API key first." and calls == []   # nothing to ask with
    with pytest.raises(ValueError):
        providers.list_models("ollama", "k")


def test_the_saved_key_is_used_when_none_is_typed(monkeypatch, env):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-saved")
    calls = web(monkeypatch, Answer({"data": [{"id": "gpt-x"}]}))
    assert providers.list_models("openai", "")["ok"]
    assert calls[0]["headers"]["Authorization"] == "Bearer sk-saved"


# ---- the chat models are built with the right options ----------------------------------

def test_openai_and_gemini_are_built_with_the_answer_limit(monkeypatch, env):
    monkeypatch.setenv("LLM_MAX_OUTPUT_TOKENS", "4096")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-x-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    model = llm.get_llm(max_tokens=600)
    assert type(model).__name__ == "ChatOpenAI" and model.max_tokens == 600 and model.temperature == 0.2

    monkeypatch.setenv("LLM_PROVIDER", "google")
    monkeypatch.setenv("LLM_MODEL", "gemini-x-flash")
    monkeypatch.setenv("GOOGLE_API_KEY", "AIza-test")
    model = llm.get_llm()
    assert type(model).__name__ == "ChatGoogleGenerativeAI" and model.max_output_tokens == 4096


def test_reasoning_models_get_no_temperature():
    assert llm.openai_temperature("gpt-4.1-mini", 0.2) == {"temperature": 0.2}
    assert llm.openai_temperature("o3-mini", 0.2) == {} and llm.openai_temperature("gpt-5-mini", 0.2) == {}
    assert llm.openai_temperature("O4-mini", 0.2) == {}


def test_a_cut_off_answer_is_seen_for_every_provider():
    cut = lambda **meta: llm.was_cut_off(AIMessage(content="", response_metadata=meta))  # noqa: E731
    assert cut(done_reason="length") and cut(stop_reason="max_tokens") and cut(finish_reason="length")
    assert cut(finish_reason="MAX_TOKENS")                                      # Gemini
    assert not cut(finish_reason="stop") and not cut(finish_reason="STOP") and not cut(stop_reason="end_turn")


def test_model_status_needs_a_key_and_a_model(monkeypatch, env):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-x")
    assert llm.llm_status() == (False, "No OpenAI API key set. Add one in Settings.")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert llm.llm_status() == (True, "Using OpenAI (gpt-x) with your API key.")
    monkeypatch.setenv("LLM_MODEL", "")
    assert llm.llm_status() == (False, "No OpenAI model chosen. Pick one in Settings.")
    monkeypatch.setenv("LLM_PROVIDER", "google")
    monkeypatch.setenv("LLM_MODEL", "gemini-x")
    assert llm.llm_status()[1] == "No Google API key set. Add one in Settings."
    monkeypatch.setenv("LLM_PROVIDER", "mystery")
    assert llm.llm_status()[0] is False


def test_3d_stays_on_for_any_cloud_model():
    info = system_check.SystemInfo.__new__(system_check.SystemInfo)
    for provider in ("anthropic", "openai", "google"):
        assert system_check.recommend_3d(info, provider, "x")[0] == "animated"


# ---- the bridge ------------------------------------------------------------------------------

def test_each_provider_has_its_own_key_and_the_page_never_reads_one(env):
    api = Api(send=lambda e: None, graph=object())
    api.set_api_key("sk-openai-1", "openai")
    api.set_api_key("AIza-google-1", "google")
    shown = api.get_settings()
    assert shown["OPENAI_API_KEY_SET"] and shown["GOOGLE_API_KEY_SET"] and not shown["ANTHROPIC_API_KEY_SET"]
    assert "sk-openai-1" not in str(shown) and "AIza-google-1" not in str(shown)
    saved = settings.read_settings()
    assert saved["OPENAI_API_KEY"] == "sk-openai-1" and saved["GOOGLE_API_KEY"] == "AIza-google-1"
    api.set_api_key("", "openai")                                               # cleared
    assert not api.get_settings()["OPENAI_API_KEY_SET"]
    with pytest.raises(ValueError):
        api.set_api_key("x", "ollama")
    with pytest.raises(ValueError):
        api.set_api_key("sk-1\nLLM_PROVIDER=evil", "openai")                    # would add a line to the settings file
    with pytest.raises(ValueError):
        api.save_settings({"OPENAI_API_KEY": "sk-x"})                           # keys only through set_api_key


def test_the_provider_can_be_switched_to_openai_and_gemini(env):
    api = Api(send=lambda e: None, graph=object())
    assert api.save_settings({"LLM_PROVIDER": "openai", "LLM_MODEL": "gpt-x"})["LLM_PROVIDER"] == "openai"
    assert api.save_settings({"LLM_PROVIDER": "google", "LLM_MODEL": "gemini-x"})["LLM_MODEL"] == "gemini-x"
    with pytest.raises(ValueError):
        api.save_settings({"LLM_PROVIDER": "skynet"})


def test_the_key_test_calls_the_chosen_provider_and_hides_the_key(monkeypatch, env):
    built = []

    class Fake:
        def __init__(self, fail=None):
            self.fail = fail

        def invoke(self, text):
            if self.fail:
                raise RuntimeError(self.fail)

    def make(provider, model, key, fail=None):
        built.append((provider, model, key))
        return Fake(fail)
    api = Api(send=lambda e: None, graph=object())
    monkeypatch.setattr(bridge, "_test_model", make)
    assert api.test_api_key("sk-typed", "gpt-x", "openai") == {"ok": True, "message": "The key works."}
    monkeypatch.setenv("GOOGLE_API_KEY", "AIza-saved")
    assert api.test_api_key(None, "gemini-x", "google")["ok"]
    assert built == [("openai", "gpt-x", "sk-typed"), ("google", "gemini-x", "AIza-saved")]
    assert api.test_api_key(None, "gpt-x", "openai")["message"] == "Paste an API key first."
    assert api.test_api_key("sk-typed", "", "openai")["message"] == "Choose a model first."
    monkeypatch.setattr(bridge, "_test_model", lambda p, m, k: Fake(f"401: bad key {k} for you"))
    answer = api.test_api_key("sk-secret-9", "gpt-x", "openai")
    assert not answer["ok"] and "sk-secret-9" not in answer["message"] and "(your key)" in answer["message"]
    with pytest.raises(ValueError):
        api.test_api_key("k", "m", "ollama")


def test_the_test_models_are_the_real_classes():
    assert type(bridge._test_model("openai", "gpt-x", "sk-x")).__name__ == "ChatOpenAI"
    assert type(bridge._test_model("google", "gemini-x", "AIza-x")).__name__ == "ChatGoogleGenerativeAI"
    assert type(bridge._test_model("anthropic", "claude-x", "sk-ant-x")).__name__ == "ChatAnthropic"


def test_the_bundled_app_checks_that_both_packages_load():
    import inspect

    from desktop_web import selftest
    source = inspect.getsource(selftest)
    assert "langchain_openai" in source and "langchain_google_genai" in source
    spec = (paths.resource_path("joblens.spec")).read_text(encoding="utf-8")
    for name in ("langchain-openai", "langchain-google-genai", "langchain_openai", "langchain_google_genai", "tiktoken_ext.openai_public"):
        assert name in spec
