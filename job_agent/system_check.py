"""
Phase 10a: look at the user's PC and recommend local models that will run well.

Two parts, kept separate on purpose:
    detect_system()     reads the hardware (RAM, GPU memory, disk) - messy,
                        Windows-specific, hard to test
    recommend_models()  pure rules: hardware numbers in, advice out -
                        easy to unit-test with made-up PCs

The rules of thumb (for Ollama, quantized models, 16k context):
    memory a model needs  ≈ download size + 1.2 GB (context + overhead)
        measured: `ollama ps` shows qwen3:8b (5.2 GB download) using 6.3 GB
    fits in GPU memory    -> "fast"     (all layers on the graphics card;
                                         0.5 GB kept free for the display)
    fits in GPU + free RAM-> "slower"   (Ollama splits it between GPU and CPU)
    otherwise             -> "too big"
These are estimates, not guarantees; the Dashboard tab shows real timings.
"""

import ctypes
import os
import shutil
import subprocess
from dataclasses import dataclass

# Tool-calling models that work with JobLens (download sizes as shown by
# `ollama list`; the smaller two are approximate).
MODELS = [
    # (name, download GB, short description)
    ("qwen3:14b", 9.3, "Highest quality of the local options"),
    ("qwen3:8b", 5.2, "Best balance - JobLens was built and tested with it"),
    ("qwen3:4b", 2.6, "Lighter, for 8 GB PCs; noticeably less accurate"),
    # 'llama3.2' (= llama3.2:latest = the 3B model): written without a tag so
    # it matches what `ollama pull llama3.2` installs.
    ("llama3.2", 2.0, "Smallest (3B); weakest at the structured answers JobLens needs"),
]
DEFAULT_MODEL = "qwen3:8b"
OS_RESERVE_GB = 4.0   # RAM left for Windows and other apps
GPU_RESERVE_GB = 0.5  # graphics memory left for the display (laptops share it)
CONTEXT_OVERHEAD_GB = 1.2  # measured: qwen3:8b = 5.2 GB download, 6.3 GB loaded
MIN_RAM_GB = 8.0      # below this, local AI isn't practical -> suggest the API


@dataclass
class SystemInfo:
    ram_gb: float
    gpu_name: str | None
    vram_gb: float | None      # None = unknown (no NVIDIA tools / no GPU)
    vram_exact: bool           # False = Windows' number, which caps at 4 GB
    disk_free_gb: float
    cpu_threads: int


@dataclass
class ModelAdvice:
    name: str
    download_gb: float
    description: str
    verdict: str               # "fast" | "slower" | "too big" | "no disk space"
    reason: str
    recommended: bool = False


# ---------------------------------------------------------------------------
# Detection (Windows)
# ---------------------------------------------------------------------------


def _ram_gb() -> float:
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    return stat.ullTotalPhys / 1024**3


def _run(cmd: list[str]) -> str:
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # no flashing console window
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10,
                              creationflags=flags).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _gpu() -> tuple[str | None, float | None, bool]:
    # 1) NVIDIA's own tool: exact memory.
    out = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
    if out:
        best = max((line.rsplit(",", 1) for line in out.splitlines()),
                   key=lambda parts: float(parts[1]))
        return best[0].strip(), float(best[1]) / 1024, True
    # 2) Windows' generic query. AdapterRAM is a 32-bit number, so it can't
    #    report more than 4 GB - treat it as "at least".
    out = _run(["powershell", "-NoProfile", "-Command",
                "Get-CimInstance Win32_VideoController | "
                "ForEach-Object { \"$($_.Name)|$($_.AdapterRAM)\" }"])
    gpus = [line.split("|") for line in out.splitlines() if "|" in line]
    gpus = [(n.strip(), float(r or 0) / 1024**3) for n, r in gpus]
    if gpus:
        name, vram = max(gpus, key=lambda g: g[1])
        return name, (vram or None), False
    return None, None, False


def detect_system() -> SystemInfo:
    from job_agent import paths

    paths.APP_HOME.mkdir(parents=True, exist_ok=True)
    gpu_name, vram, exact = _gpu()
    return SystemInfo(
        ram_gb=_ram_gb(),
        gpu_name=gpu_name,
        vram_gb=vram,
        vram_exact=exact,
        disk_free_gb=shutil.disk_usage(paths.APP_HOME).free / 1024**3,
        cpu_threads=os.cpu_count() or 1,
    )


# ---------------------------------------------------------------------------
# Recommendation (pure - unit-tested)
# ---------------------------------------------------------------------------


def memory_needed_gb(download_gb: float) -> float:
    return download_gb + CONTEXT_OVERHEAD_GB


def recommend_models(info: SystemInfo) -> tuple[list[ModelAdvice], str]:
    """Advice for every model + a one-line summary for the user."""
    # Only count GPU memory we trust for "fast": an exact NVIDIA number.
    # Integrated / unknown GPUs: Ollama runs on the CPU.
    vram = max(info.vram_gb - GPU_RESERVE_GB, 0.0) if (info.vram_gb and info.vram_exact) else 0.0
    free_ram = max(info.ram_gb - OS_RESERVE_GB, 0.0)

    advice = []
    for name, size, description in MODELS:
        need = memory_needed_gb(size)
        if info.disk_free_gb < size + 2:
            verdict, reason = "no disk space", f"needs {size + 2:.0f} GB free disk"
        elif vram >= need:
            verdict, reason = "fast", f"fits in your {info.vram_gb:.0f} GB graphics memory"
        elif vram + free_ram >= need:
            verdict = "slower"
            reason = (f"needs ~{need:.0f} GB; split between GPU and RAM" if vram
                      else f"needs ~{need:.0f} GB; runs on the CPU (no supported GPU)")
        else:
            verdict, reason = "too big", f"needs ~{need:.0f} GB memory"
        advice.append(ModelAdvice(name, size, description, verdict, reason))

    # Pick one: the tested default if it runs fast; else the best model that
    # runs fast; else the default if it at least runs; else anything that runs.
    by_name = {a.name: a for a in advice}
    usable = [a for a in advice if a.verdict in ("fast", "slower")]
    fast = [a for a in advice if a.verdict == "fast"]
    if info.ram_gb < MIN_RAM_GB or not usable:
        summary = (f"This PC has {info.ram_gb:.0f} GB RAM - local AI would be very slow or "
                   "won't fit. We recommend the API option (about $0.01 per job).")
        return advice, summary

    if by_name[DEFAULT_MODEL].verdict == "fast":
        pick = by_name[DEFAULT_MODEL]
    elif fast:
        pick = fast[0]
    elif by_name[DEFAULT_MODEL].verdict == "slower":
        pick = by_name[DEFAULT_MODEL]
    else:
        pick = usable[0]
    pick.recommended = True

    gpu = (f"{info.gpu_name} ({info.vram_gb:.0f} GB)" if info.gpu_name and info.vram_exact
           else (info.gpu_name or "no dedicated GPU"))
    speed = "runs fast on your graphics card" if pick.verdict == "fast" else "will run, but slowly"
    summary = f"{info.ram_gb:.0f} GB RAM · {gpu}. Recommended: {pick.name} - {speed}."
    return advice, summary
