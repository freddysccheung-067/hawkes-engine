"""Test that hawkes_engine imports successfully."""

import hawkes_engine


def test_import():
    """Package imports without error."""
    assert hawkes_engine is not None


def test_version():
    """Version string exists."""
    assert hasattr(hawkes_engine, "__version__")
    assert isinstance(hawkes_engine.__version__, str)
    assert hawkes_engine.__version__ == "0.1.0.dev0"


def test_module_attributes():
    """Module has expected metadata."""
    assert hasattr(hawkes_engine, "__author__")
    assert hasattr(hawkes_engine, "__license__")
    assert hawkes_engine.__license__ == "MIT"
