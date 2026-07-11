"""
Phase 1 - Environment verification test.

Purpose:
    Confirms that pytest is correctly installed and discoverable
    within the project's virtual environment. This is a smoke test,
    not a functional test of any application logic (there is none yet).

    This test must pass before any later phase begins, as it validates
    the foundation all other automated tests depend on.
"""

import sys


def test_python_version_is_311_or_higher() -> None:
    """Environment must run on Python 3.11+ to match target deployment (Pi/Bookworm)."""
    assert sys.version_info >= (
        3,
        11,
    ), f"Expected Python 3.11+, found {sys.version_info.major}.{sys.version_info.minor}"


def test_pytest_is_operational() -> None:
    """Trivial assertion confirming pytest itself runs and reports correctly."""
    assert 1 + 1 == 2
