"""
Tests for the model recommendations (Phase 10a) with made-up PCs.

recommend_models() is pure, so we can test hardware we don't have.
"""

import pytest

from job_agent.system_check import SystemInfo, recommend_3d, recommend_models


def pc(ram, vram=None, exact=True, disk=200, gpu="NVIDIA RTX"):
    return SystemInfo(ram_gb=ram, gpu_name=gpu if vram else None, vram_gb=vram,
                      vram_exact=exact, disk_free_gb=disk, cpu_threads=8)


def verdicts(advice):
    return {a.name: a.verdict for a in advice}


def recommended(advice):
    return [a.name for a in advice if a.recommended]


def test_this_laptop_rtx4060_8gb_16gb_ram():
    # The real machine JobLens was built on. nvidia-smi says 8188 MB = 7.996 GB,
    # NOT a round 8.0 - the first version of the rules failed on exactly this.
    advice, summary = recommend_models(pc(ram=15.6, vram=8188 / 1024))
    v = verdicts(advice)
    assert v["qwen3:8b"] == "fast"          # 5.2 GB model fits in 8 GB VRAM
    assert v["qwen3:14b"] == "slower"       # GPU + RAM split (matches the 3.8x slower measurement)
    assert recommended(advice) == ["qwen3:8b"]
    assert "fast" in summary


def test_big_gpu_still_prefers_the_tested_default():
    advice, _ = recommend_models(pc(ram=64, vram=24))
    assert verdicts(advice)["qwen3:14b"] == "fast"
    assert recommended(advice) == ["qwen3:8b"]   # tested default, and fast


def test_no_gpu_16gb_ram_runs_on_cpu():
    advice, summary = recommend_models(pc(ram=16))
    assert verdicts(advice)["qwen3:8b"] == "slower"
    assert recommended(advice) == ["qwen3:8b"]
    assert "slowly" in summary


def test_small_gpu_picks_a_model_that_fits_fast():
    advice, _ = recommend_models(pc(ram=16, vram=5))
    assert verdicts(advice)["qwen3:8b"] == "slower"   # needs ~6.4 GB, only 4.5 usable
    assert recommended(advice) == ["qwen3:4b"]        # ~3.8 GB: the best model that runs fast


def test_low_ram_suggests_the_api():
    advice, summary = recommend_models(pc(ram=6))
    assert recommended(advice) == []
    assert "API" in summary


def test_windows_capped_vram_is_not_trusted_for_speed():
    # Win32_VideoController reports at most 4 GB: don't promise "fast" on it.
    advice, _ = recommend_models(pc(ram=16, vram=4.0, exact=False))
    assert "fast" not in verdicts(advice).values()


def test_not_enough_disk():
    advice, _ = recommend_models(pc(ram=32, vram=12, disk=5))
    v = verdicts(advice)
    assert v["qwen3:14b"] == "no disk space" and v["qwen3:8b"] == "no disk space"


# ---- 12g: which 3D level suits the PC (D14) ------------------------------------

@pytest.mark.parametrize("machine, provider, model, level", [
    (pc(16, 8), "anthropic", "claude-haiku-5-5", "animated"),   # GPU free: the AI is in the cloud
    (pc(16), "ollama", "qwen3:8b", "off"),                       # no graphics card at all
    (pc(16, 2, exact=False, gpu="Intel Iris Xe"), "ollama", "qwen3:8b", "still"),  # memory unknown
    (pc(16, 8), "ollama", "qwen3:8b", "still"),                 # this laptop: ~1.1 GB left over
    (pc(32, 12), "ollama", "qwen3:8b", "animated"),             # ~5 GB left over
    (pc(16, 8), "ollama", "qwen3:14b", "off"),                  # the model doesn't fit: GPU is busy
    (pc(16, 8), "ollama", "qwen3:4b", "animated"),              # small model, ~3.7 GB left
    (pc(16, 8), "ollama", "some-custom:7b", "still"),           # unknown model: sized like the default
])
def test_3d_level_for_the_pc(machine, provider, model, level):
    got, reason = recommend_3d(machine, provider, model)
    assert got == level and reason
