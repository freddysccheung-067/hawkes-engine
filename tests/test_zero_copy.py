"""The H5 zero-copy contract, tested from Python.

The library's claim is that a conforming array reaches the C++ core without
being copied. That claim is false the moment a binding forcecasts, and no
functional test can see the difference: a copied array produces the same
likelihood as the original. These tests therefore look at addresses and at
residency rather than at values.

Addresses are read through ``_core._view_addresses``, a private hook that runs
the same argument resolution as the compute path and reports the pointers the
core would receive. If a conversion happened, those pointers belong to a new
buffer and do not match ``arr.ctypes.data``.
"""

from __future__ import annotations

import gc
import os
import sys

import hawkes_engine
import numpy as np
import pytest
from hawkes_engine import _core

# One million events is enough for an accidental copy to be visible in RSS while
# keeping the suite fast; the 2e6 case in test_inputs_are_not_copied is not
# repeated in every test.
BIG_N = 2_000_000
SIM_N = 1_000_000


def _params(M: int = 2) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(7)
    gamma = rng.uniform(0.1, 0.4, (M, M))
    beta = np.full((M, M), 1.5)
    mu = np.full(M, 0.5)
    return mu, gamma * beta, beta


def _stream(n: int, M: int = 2) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(11)
    times = np.sort(rng.uniform(0.0, 100.0, n))
    types = rng.integers(0, M, n).astype(np.uint8)
    return times, types


def _peak_rss_bytes() -> int:
    """Peak resident set size of this process, or 0 where it cannot be read.

    ``resource`` is POSIX-only; Windows reports the peak through psapi. Both are
    peak values, so the measurement is monotone within a process and a leak
    shows up as growth between two readings around a loop.
    """
    if sys.platform == "win32":
        import ctypes
        import ctypes.wintypes as wt

        psapi = ctypes.WinDLL("psapi")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wt.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD]
        psapi.GetProcessMemoryInfo.restype = wt.BOOL

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wt.DWORD),
                ("PageFaultCount", wt.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        if not psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            return 0
        return int(counters.PeakWorkingSetSize)
    try:
        import resource
    except ImportError:  # pragma: no cover - not reachable on a supported platform
        return 0
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux reports kilobytes, macOS bytes.
    return int(peak) * (1024 if sys.platform.startswith("linux") else 1)


def _addresses(times, types, mu, alpha, beta, T=200.0):
    M = int(mu.shape[0])
    return _core._view_addresses(times, types, mu, alpha, beta, T, M, False)


def _python_addresses(times, types, mu, alpha, beta):
    return (
        times.ctypes.data,
        types.ctypes.data,
        mu.ctypes.data,
        alpha.ctypes.data,
        beta.ctypes.data,
    )


# --------------------------------------------------------------- inputs


def test_inputs_are_not_copied():
    """The core resolves every argument to the caller's own buffer.

    Two million events: a copy would be 16 MB for times alone. If any entry
    differed, the binding would be computing on a buffer the caller cannot see,
    which is exactly the class of defect that leaves the answer correct and the
    guarantee false.
    """
    times, types = _stream(BIG_N)
    mu, alpha, beta = _params()
    seen = _addresses(times, types, mu, alpha, beta)
    assert seen == _python_addresses(times, types, mu, alpha, beta)
    assert bytes(types.dtype.str, "ascii")[:2] == b"|u"
    assert times.flags["C_CONTIGUOUS"] and mu.flags["C_CONTIGUOUS"]


def test_public_wrappers_do_not_copy_conforming_inputs():
    """The Python face does not copy either, which is where a copy is likelier.

    ``np.ascontiguousarray`` returns its argument when it already conforms, so
    the wrapper is a pass-through. This pins that, because a change to
    ``np.array(..., copy=True)`` in the wrapper would be invisible in results.
    """
    times, types = _stream(10_000)
    mu, alpha, beta = _params()
    # The wrapper flattens alpha and beta for the core; a reshape of a
    # C-contiguous array is a view, so the address is the block's own.
    assert hawkes_engine.loglik(times, types, mu, alpha, beta, 200.0)["value"] == pytest.approx(
        _core.loglik(
            times,
            types,
            mu,
            alpha.reshape(-1),
            beta.reshape(-1),
            200.0,
            2,
            False,
            False,
        )["value"]
    )
    assert np.shares_memory(alpha.reshape(-1), alpha)


@pytest.mark.parametrize(
    ("name", "mutate", "expected"),
    [
        ("times", lambda a: a[::2], "C-contiguous"),
        ("types", lambda a: a[::2], "C-contiguous"),
        ("mu", lambda a: a.astype(np.float32), "dtype float64"),
        ("alpha", lambda a: np.asfortranarray(a), "C-contiguous"),
        ("beta", lambda a: a.astype(np.float32), "dtype float64"),
    ],
)
def test_a_non_conforming_input_raises_and_names_itself(name, mutate, expected):
    """A strided slice or a float32 block is refused, not copied.

    This is the negative half of the contract and the one the old binding got
    wrong: it forcecast the input and returned a correct number from a copy.
    The assertion on the argument name matters as much as the exception type,
    because "could not be viewed" does not tell the caller which one to fix.
    """
    times, types = _stream(1_000)
    mu, alpha, beta = _params()
    kwargs = {"times": times, "types": types, "mu": mu, "alpha": alpha, "beta": beta}
    kwargs[name] = mutate(kwargs[name])
    # Passed unreshaped: reshaping an F-ordered block would copy it to C order
    # here and the core would then correctly accept the copy.
    with pytest.raises((TypeError, ValueError), match=rf"{name}.*{expected}"):
        _core.loglik(
            kwargs["times"],
            kwargs["types"],
            kwargs["mu"],
            kwargs["alpha"],
            kwargs["beta"],
            200.0,
            2,
            False,
            False,
        )


def test_byte_swapped_float64_is_refused():
    """A big-endian float64 would be read bit for bit and give a wrong answer.

    This one is not a copy question: the reinterpreted double is finite and the
    likelihood of it is a perfectly plausible number, so nothing downstream can
    notice. Before this check the binding returned a value for it.
    """
    times, types = _stream(100)
    mu, alpha, beta = _params()
    swapped = times.astype(">f8")
    assert swapped.dtype.byteorder == ">"
    with pytest.raises(ValueError, match="times.*byte order"):
        _core.loglik(swapped, types, mu, alpha.reshape(-1), beta.reshape(-1), 200.0, 2)


def test_type_codes_are_checked_before_the_uint8_cast():
    """np.asarray(256, dtype=uint8) wraps to 0, which is a valid type index."""
    times = np.array([1.0, 2.0])
    mu, alpha, beta = _params()
    with pytest.raises(ValueError, match="types.*256"):
        hawkes_engine.loglik(times, np.array([0, 256]), mu, alpha, beta, 3.0)
    with pytest.raises(ValueError, match="types.*1.5"):
        hawkes_engine.loglik(times, np.array([0.0, 1.5]), mu, alpha, beta, 3.0)


# --------------------------------------------------------------- outputs


@pytest.mark.parametrize("method", ["thinning", "cluster"])
def test_adopted_outputs_own_their_memory_and_outlive_the_source(method):
    """Overwriting the caller's parameters leaves the simulated path intact.

    The returned array borrows a heap vector through a capsule, so it does not
    own its own memory; what it must do is keep that vector alive. Mutating the
    input arrays would reuse the memory if the vector had been a view of them.
    """
    mu, alpha, beta = _params(1)
    times, types = hawkes_engine.simulate(mu, alpha, beta, 200.0, method=method, seed=3)
    assert times.size > 0
    before_times = times.copy()
    before_types = types.copy()
    mu[:] = 1e9
    alpha[:] = 1e9
    beta[:] = 1e9
    gc.collect()
    np.testing.assert_array_equal(times, before_times)
    np.testing.assert_array_equal(types, before_types)


@pytest.mark.parametrize("method", ["thinning", "cluster"])
def test_adopted_outputs_are_writable_and_do_not_affect_the_next_call(method):
    mu, alpha, beta = _params(2)
    times, types = hawkes_engine.simulate(mu, alpha, beta, 100.0, method=method, seed=5)
    assert times.flags["WRITEABLE"] and types.flags["WRITEABLE"]
    assert times.flags["C_CONTIGUOUS"] and types.flags["C_CONTIGUOUS"]
    first = times.sum()
    times[:] = -1.0
    types[:] = 255
    assert np.all(times == -1.0)
    again, _ = hawkes_engine.simulate(mu, alpha, beta, 100.0, method=method, seed=5)
    assert again.sum() == pytest.approx(first)


def test_gradient_outputs_are_documented_shape_dtype_and_writable():
    times, types = _stream(500)
    mu, alpha, beta = _params(3)
    out = _core.loglik(times, types, mu, alpha.reshape(-1), beta.reshape(-1), 200.0, 3, False, True)
    for key, shape in (("dmu", (3,)), ("dalpha", (3, 3)), ("dbeta", (3, 3))):
        arr = out[key]
        assert arr.dtype == np.float64, key
        assert arr.shape == shape, key
        assert arr.flags["C_CONTIGUOUS"] and arr.flags["WRITEABLE"], key
        assert arr.flags["OWNDATA"], key
        copy = arr.copy()
        arr[...] = -7.0
        assert np.all(arr == -7.0)
        assert np.all(copy != -7.0)


def test_an_empty_simulated_path_is_a_genuine_empty_array():
    """adopt() must not hand NumPy the data pointer of an empty vector."""
    mu, alpha, beta = _params(1)
    for method in ("thinning", "cluster"):
        times, types = hawkes_engine.simulate(
            np.array([0.0]), np.zeros((1, 1)), np.ones((1, 1)), 1.0, method=method, seed=1
        )
        assert times.shape == (0,) and types.shape == (0,)
        assert times.dtype == np.float64 and types.dtype == np.uint8


# --------------------------------------------------------------- residency


@pytest.mark.slow
def test_repeated_simulation_does_not_grow_the_heap():
    """Twenty large simulations must not accumulate memory.

    A leak in the capsule owner -- a vector that is not deleted, or one deleted
    twice -- shows up here and nowhere else, because each individual call is
    correct. The bound is generous on purpose: allocator behaviour differs
    between platforms and the point is to catch a whole path per call, not to
    pin the allocator's bookkeeping.
    """
    mu, alpha, beta = _params(1)
    # This parameter set produces about 0.66 events per unit of time, so T =
    # 1.5e6 gives roughly one million events per call.
    T = 1_500_000.0
    # Warm up so that the first call's allocation is not counted as growth.
    hawkes_engine.simulate(mu, alpha, beta, T, seed=1)
    gc.collect()
    baseline = _peak_rss_bytes()
    if baseline == 0:  # pragma: no cover - no supported platform lacks this
        pytest.skip("peak RSS is not readable on this platform")
    for k in range(20):
        times, types = hawkes_engine.simulate(mu, alpha, beta, T, seed=k)
        assert times.size > SIM_N // 2
        del times, types
    gc.collect()
    growth = _peak_rss_bytes() - baseline
    # One path of ~1e6 events is 9 MB (8 bytes of time + 1 of type); twenty of
    # them leaking would be 180 MB. 40 MB admits allocator slack and no leak.
    assert growth < 40_000_000, f"peak RSS grew by {growth / 1e6:.1f} MB over 20 calls"


def test_architecture_is_known():
    """The RSS test above reads a platform-specific counter; say where we run."""
    assert sys.platform in {"win32", "linux", "darwin"}
    assert os.sep in {"\\", "/"}
