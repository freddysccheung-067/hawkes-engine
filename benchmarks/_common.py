"""Shared pieces of the H7 capability benchmarks.

The machine header, the problem generator and the child-process memory probe
live here so that every capability script records the same machine and draws its
data the same way.
"""

from __future__ import annotations

import ctypes
import datetime as dt
import os
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "benchmarks" / "results"
CACHE = ROOT / "benchmarks" / ".cache"


def today() -> str:
    return dt.date.today().isoformat()


def _cpu_name() -> str:
    if sys.platform == "win32":
        try:
            out = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-CimInstance Win32_Processor).Name",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
            ).stdout.strip()
            if out:
                return out
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        try:
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
        except OSError:
            pass
    return platform.processor() or "unknown"


def _total_ram_gib() -> float:
    if sys.platform == "win32":

        class _Status(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        s = _Status()
        s.dwLength = ctypes.sizeof(_Status)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))  # type: ignore[attr-defined]
        return s.ullTotalPhys / 2**30
    pages = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    return pages / 2**30


def machine_lines() -> list[str]:
    """The machine, exactly, as comment lines for the head of a results file."""
    import hawkes_engine
    from hawkes_engine import _core

    info = _core.build_info()
    return [
        f"# date: {today()}",
        f"# cpu: {_cpu_name()}",
        f"# logical_cores: {os.cpu_count()}",
        f"# ram_gib: {_total_ram_gib():.1f}",
        f"# os: {platform.platform()} (build {platform.version()})",
        f"# compiler: {info['compiler']} {info['compiler_version']}, C++{info['cxx_standard']}",
        f"# python: {platform.python_version()}",
        f"# numpy: {np.__version__}",
        f"# hawkes_engine: {getattr(hawkes_engine, '__version__', 'unknown')}",
    ]


def problem(M: int, rho: float, shared: bool = False):
    """Pair (or shared) decay parameters at a target branching ratio."""
    from hawkes_engine import _core

    rng = np.random.default_rng(M)
    beta = rng.uniform(0.8, 2.0, (M, M))
    if shared:
        beta = np.tile(rng.uniform(0.8, 2.0, M)[:, None], (1, M))
    mu = rng.uniform(0.3, 0.7, M)
    gamma = rng.uniform(0.3, 1.0, (M, M))
    alpha = gamma * beta
    alpha *= rho / _core.spectral_radius(mu, alpha, beta)
    return mu, alpha, beta


def simulate_n(M: int, rho: float, n: int, seed: int = 0, method: str = "thinning"):
    """Simulate about ``n`` events from ``problem(M, rho)``; return times, types, T."""
    import hawkes_engine
    from hawkes_engine import _core

    mu, alpha, beta = problem(M, rho)
    rate = float(_core.stationary_mean(mu, alpha, beta).sum())
    T = n / rate
    times, types = hawkes_engine.simulate(mu, alpha, beta, T, method=method, seed=seed)
    return times, types, T


def cached_data(M: int, rho: float, n: int, seed: int = 0) -> Path:
    """Simulate once and keep the arrays on disk so a child can load them."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"sim_M{M}_rho{rho}_N{n}_s{seed}.npz"
    if not path.exists():
        times, types, T = simulate_n(M, rho, n, seed)
        np.savez(path, times=times, types=types, T=np.float64(T))
    return path


# --- peak working set of a child process --------------------------------------


def peak_working_set_self() -> int:
    """Peak working set of this process in bytes (Windows or Linux)."""
    if sys.platform == "win32":

        class _Counters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        c = _Counters()
        c.cb = ctypes.sizeof(_Counters)
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        ok = psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
        if not ok:
            raise OSError(ctypes.get_last_error(), "GetProcessMemoryInfo failed")
        return int(c.PeakWorkingSetSize)
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1]) * 1024
    raise OSError("VmHWM not found")


def run_child(args: list[str], timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(ROOT),
        check=False,
    )
