"""16d: the cost of a run from the prices you enter, and the data behind the
new Evals charts. No model, no network."""

import pytest

from desktop_web.bridge import Api
from job_agent import monitoring, pricing, runlog, settings, tracker


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "jobs.db")
    monkeypatch.setattr(settings, "APP_HOME", tmp_path)
    monkeypatch.setattr(settings, "ENV_FILE", tmp_path / ".env")
    monkeypatch.delenv(pricing.SETTING, raising=False)   # save_settings() writes os.environ: restored after the test


# ---- prices -------------------------------------------------------------------------

def test_prices_are_read_and_written_as_one_setting():
    prices = pricing.parse("gpt-x=0.15/0.6;claude-haiku-5-5=1/5")
    assert prices == {"gpt-x": (0.15, 0.6), "claude-haiku-5-5": (1.0, 5.0)}
    assert pricing.parse(pricing.dump(prices)) == prices
    assert pricing.dump(prices) == "claude-haiku-5-5=1/5;gpt-x=0.15/0.6"
    assert pricing.parse("models/gemini-x=0.1/0.4") == {"models/gemini-x": (0.1, 0.4)}   # a "/" in the name is fine
    assert pricing.parse("") == {} and pricing.parse(None) == {}
    assert pricing.parse("gpt-x=cheap/0.6;=1/2;ok=1/2;neg=-1/2;half=1") == {"ok": (1.0, 2.0)}   # nonsense is skipped


def test_cost_is_tokens_times_price_per_million():
    prices = {"gpt-x": (0.15, 0.6)}
    assert pricing.cost(prices, "gpt-x", 1_000_000, 1_000_000) == pytest.approx(0.75)
    assert pricing.cost(prices, "gpt-x", 46_833, 12_643) == pytest.approx(46_833 * 0.15 / 1e6 + 12_643 * 0.6 / 1e6)
    assert pricing.cost(prices, "gpt-x", None, None) == 0
    assert pricing.cost(prices, "qwen3:8b", 50_000, 10_000) is None      # no price: no cost, never a guess
    assert pricing.cost({}, None, 1, 1) is None


def test_setting_and_removing_a_price():
    prices = pricing.with_price({}, "gpt-x", "0.15", 0.6)
    assert prices == {"gpt-x": (0.15, 0.6)}
    assert pricing.with_price(prices, "gpt-x", None, "") == {}             # both empty: forgotten
    assert pricing.with_price(prices, " gpt-x ", 1, 2) == {"gpt-x": (1.0, 2.0)}
    for bad in [("gpt-x", "cheap", 1), ("gpt-x", 1, None), ("gpt-x", -1, 1), ("gpt-x", 150_000, 1), ("", 1, 1), ("a=b", 1, 1), ("a;b", 1, 1)]:
        with pytest.raises(ValueError):
            pricing.with_price({}, *bad)


# ---- what Evals shows ------------------------------------------------------------------

def seed():
    """Two full local runs, a 1-call run, and two full API runs."""
    runlog.init_db()
    with tracker._db() as conn:
        runs = [  # run, start, model, provider, status, decision, seconds, calls, in, out
            ("q1", "2026-10-01 10:00:00", "qwen3:8b", "ollama", "done", "approve", 180, 9, 15_000, 4_000),
            ("q2", "2026-10-02 10:00:00", "qwen3:8b", "ollama", "done", "reject", 240, 9, 30_000, 6_000),
            ("q3", "2026-10-03 10:00:00", "qwen3:8b", "ollama", "done", "approve", 10, 1, 2_000, 400),
            ("g1", "2026-10-04 10:00:00", "gpt-x", "openai", "done", "approve", 40, 8, 20_000, 5_000),
            ("g2", "2026-10-05 10:00:00", "gpt-x", "openai", "error", None, 60, 8, 40_000, 10_000),
        ]
        conn.executemany(
            """INSERT INTO runs (run_id, started_at, updated_at, model, provider, status, decision, agent_seconds,
               llm_calls, input_tokens, output_tokens, tool_calls, tool_failures) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)""",
            [(r[0], r[1], r[1], *r[2:]) for r in runs])
        conn.executemany("INSERT INTO run_quality VALUES (?, 'evidence_pass_rate', ?)",
                         [("q1", 0.5), ("q2", 0.7), ("g1", 0.9)])


def evals(prices=None, model=None):
    if prices is not None:
        settings.save_settings({pricing.SETTING: pricing.dump(prices)})
    return monitoring.local_evals(model)


def test_without_a_price_no_cost_is_shown():
    seed()
    data = evals()
    assert data["kpis"]["cost_total"] is None and data["kpis"]["cost_runs"] == 0 and data["kpis"]["cost_per_run"] is None
    assert all(r["cost"] is None for r in data["recent"]) and all(p["cost"] is None for p in data["run_points"])
    assert all(m["cost_per_run"] is None for m in data["models"])


def test_cost_per_run_and_in_total_match_a_hand_sum():
    seed()
    data = evals({"gpt-x": (0.5, 2.0)})
    g1 = 20_000 * 0.5 / 1e6 + 5_000 * 2.0 / 1e6        # 0.02
    g2 = 40_000 * 0.5 / 1e6 + 10_000 * 2.0 / 1e6       # 0.04: it failed, but it was billed
    assert g1 == pytest.approx(0.02) and g2 == pytest.approx(0.04)
    recent = {r["run_id"]: r["cost"] for r in data["recent"]}
    assert recent["g1"] == pytest.approx(g1) and recent["g2"] == pytest.approx(g2) and recent["q1"] is None
    assert data["kpis"]["cost_total"] == pytest.approx(g1 + g2) and data["kpis"]["cost_runs"] == 2
    assert data["kpis"]["cost_per_run"] == pytest.approx((g1 + g2) / 2)
    models = {m["model"]: m for m in data["models"]}
    assert models["gpt-x"]["cost_per_run"] == pytest.approx((g1 + g2) / 2) and models["qwen3:8b"]["cost_per_run"] is None
    # one model chosen: only its runs are counted
    assert evals(model="qwen3:8b")["kpis"]["cost_total"] is None
    assert evals(model="gpt-x")["kpis"]["cost_total"] == pytest.approx(g1 + g2)


def test_the_charts_get_full_runs_oldest_first():
    seed()
    points = evals()["run_points"]
    assert [p["run_id"] for p in points] == ["q1", "q2", "g1", "g2"]            # q3 (1 call) is not a full run
    assert points[1] == {"run_id": "q2", "started_at": "2026-10-02 10:00:00", "model": "qwen3:8b",
                         "seconds": 240.0, "tokens_in": 30_000, "tokens_out": 6_000, "cost": None}
    assert [p["run_id"] for p in evals(model="gpt-x")["run_points"]] == ["g1", "g2"]


def test_pass_rate_by_model_is_always_every_model():
    seed()
    for chosen in (None, "gpt-x"):
        trend = evals(model=chosen)["model_trend"]
        assert [(m["model"], m["runs"]) for m in trend] == [("qwen3:8b", 2), ("gpt-x", 1)]   # most runs first
        assert [p["rate"] for p in trend[0]["points"]] == [0.5, 0.7]                         # oldest first
    assert evals()["models_not_charted"] == 0


def test_only_four_models_are_charted():
    runlog.init_db()
    with tracker._db() as conn:
        for n in range(6):
            conn.execute("INSERT INTO runs (run_id, started_at, updated_at, model, provider, status, llm_calls, input_tokens, "
                         "output_tokens, tool_calls, tool_failures, agent_seconds) VALUES (?, ?, ?, ?, 'ollama', 'done', 9, 1, 1, 0, 0, 1)",
                         (f"r{n}", f"2026-10-0{n + 1} 10:00:00", f"2026-10-0{n + 1} 10:00:00", f"model-{n}"))
            conn.execute("INSERT INTO run_quality VALUES (?, 'evidence_pass_rate', 0.5)", (f"r{n}",))
    data = evals()
    assert len(data["model_trend"]) == 4 and data["models_not_charted"] == 2


# ---- the bridge ---------------------------------------------------------------------------

def test_the_page_can_set_and_clear_a_price():
    api = Api(send=lambda e: None, graph=object())
    assert api.set_model_price("gpt-x", 0.15, 0.6)["MODEL_PRICES"] == "gpt-x=0.15/0.6"
    assert api.set_model_price("claude-haiku-5-5", 1, 5)["MODEL_PRICES"] == "claude-haiku-5-5=1/5;gpt-x=0.15/0.6"
    assert pricing.saved() == {"gpt-x": (0.15, 0.6), "claude-haiku-5-5": (1.0, 5.0)}
    assert api.set_model_price("gpt-x", None, None)["MODEL_PRICES"] == "claude-haiku-5-5=1/5"
    with pytest.raises(ValueError):
        api.set_model_price("gpt-x", "a lot", 1)
    with pytest.raises(ValueError):
        api.save_settings({"MODEL_PRICES": "x=1/1"})                              # only through set_model_price
    seed()
    api.set_model_price("gpt-x", 0.5, 2.0)
    assert api.evals(None)["kpis"]["cost_total"] == pytest.approx(0.06)
