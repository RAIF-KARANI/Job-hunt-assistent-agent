"""
Tests for the answer-length cap and the retry rules (12j). No model needed:
the "model" is a stand-in that returns what each test wants.
"""

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from job_agent import llm


@pytest.mark.parametrize("meta, cut", [
    ({"done_reason": "length"}, True),        # Ollama
    ({"stop_reason": "max_tokens"}, True),    # Claude
    ({"finish_reason": "length"}, True),      # OpenAI
    ({"done_reason": "stop"}, False),
    ({"stop_reason": "end_turn"}, False),
    ({}, False),
])
def test_cut_off_is_recognised_for_each_provider(meta, cut):
    assert llm.was_cut_off(AIMessage(content="{", response_metadata=meta)) is cut


def test_a_cut_off_answer_is_reported_not_parsed():
    raw = AIMessage(content='{"points": ["a", "b", "a", "b"', response_metadata={"done_reason": "length"})
    with pytest.raises(llm.AnswerTooLong, match="cut off at"):
        llm._checked({"raw": raw, "parsed": None, "parsing_error": ValueError("bad json")})


def test_a_good_answer_passes_through():
    raw = AIMessage(content="{}", response_metadata={"done_reason": "stop"})
    assert llm._checked({"raw": raw, "parsed": "ok", "parsing_error": None}) == "ok"


def counting(error):
    calls = []

    def fn(_value):
        calls.append(1)
        raise error
    return RunnableLambda(fn), calls


def test_a_bad_answer_is_tried_three_times():
    runnable, calls = counting(ValueError("missing field"))
    with pytest.raises(ValueError):
        llm.with_retries(runnable).invoke("x")
    assert len(calls) == 3


@pytest.mark.parametrize("error", [llm.AnswerTooLong("cut off"), llm.RunStopped("stopped")])
def test_cut_off_and_stopped_are_never_retried(error):
    runnable, calls = counting(error)
    with pytest.raises(type(error)):
        llm.with_retries(runnable).invoke("x")
    assert len(calls) == 1


def test_a_retry_that_succeeds_returns_the_answer():
    calls = []

    def flaky(_value):
        calls.append(1)
        if len(calls) < 2:
            raise ValueError("bad json")
        return "ok"
    assert llm.with_retries(RunnableLambda(flaky)).invoke("x") == "ok"
    assert len(calls) == 2


def test_every_provider_gets_the_cap(monkeypatch):
    monkeypatch.setenv("LLM_MAX_OUTPUT_TOKENS", "1234")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    assert llm.get_llm().num_predict == 1234
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("LLM_MODEL", "claude-haiku-5-5")
    assert llm.get_llm().max_tokens == 1234  # Claude's own default is 128,000
