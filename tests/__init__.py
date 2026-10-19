"""Test suite for hawkes-engine.

This file exists so that ``tests`` is a regular package. Without it, pytest's
default ``prepend`` import mode puts ``tests/`` itself on ``sys.path``, so
``from tests._simulate_reference import ...`` fails under a bare ``pytest``
invocation even though it works under ``python -m pytest``, which adds the
working directory. That difference is invisible locally and fails on every CI
platform, which is exactly how it was found.

With the package marker, pytest resolves the import against the repository root
instead, and both invocations agree.
"""
