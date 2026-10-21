"""The public surface, pinned.

``__all__`` is the contract a user reads in ``help(hawkes_engine)`` and the one a
``from hawkes_engine import *`` obeys, so it is asserted rather than described.
The list below is the surface documented in README.md; a name added to one
without the other is the defect this test exists to catch.
"""

from __future__ import annotations

import inspect

import hawkes_engine
import pytest

DOCUMENTED = [
    "__version__",
    "fit",
    "FitResult",
    "simulate",
    "simulate_many",
    "loglik",
    "LoglikResult",
    "time_rescale",
    "ks_test",
    "qq_data",
    "report",
    "trust_lookup",
    "MapAnswer",
    "spectral_radius",
    "stationary_mean",
]


def test_all_matches_the_documented_surface():
    assert sorted(hawkes_engine.__all__) == sorted(DOCUMENTED)
    assert len(hawkes_engine.__all__) == len(set(hawkes_engine.__all__))


def test_every_documented_name_resolves():
    for name in DOCUMENTED:
        assert hasattr(hawkes_engine, name), f"hawkes_engine.{name} is missing"


def test_private_internals_are_not_exported():
    for name in ("_core", "_arrays", "_layout", "_boot", "_simulate", "_selftest"):
        assert name not in hawkes_engine.__all__, f"{name} leaks into the public surface"
    # Names removed from the surface are still importable from their own module,
    # which is deliberate: the log-space objective is the optimizer's, and a
    # caller who wants it knows where to look.
    from hawkes_engine.loglik import loglik_grad_log_space  # noqa: F401


def test_every_public_callable_has_a_docstring_with_a_constraint():
    """A docstring that only restates the signature is filler.

    Every public function states what it returns and at least one constraint
    that a caller could violate, which is what the parameters section alone does
    not convey. This asserts the presence and the length, not the wording.
    """
    for name in DOCUMENTED:
        obj = getattr(hawkes_engine, name)
        if not inspect.isfunction(obj):
            continue
        doc = inspect.getdoc(obj) or ""
        assert len(doc) > 120, f"{name}'s docstring is too short to say anything"
        assert "Parameters" in doc, f"{name} does not document its parameters"
        assert "Returns" in doc or "Return" in doc, f"{name} does not document its return"


@pytest.mark.parametrize("name", ["fit", "simulate", "loglik", "time_rescale", "report"])
def test_public_functions_do_not_leak_generic_object_types(name):
    """The annotation is part of the surface; ``object`` is not an annotation."""
    sig = inspect.signature(getattr(hawkes_engine, name))
    for param in sig.parameters.values():
        annotation = str(param.annotation)
        assert annotation != "object", f"{name}({param.name}: object) tells the caller nothing"
