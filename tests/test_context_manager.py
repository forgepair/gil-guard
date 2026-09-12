"""Tests for gil_guard.assert_gil_stays_disabled().

Anything that actually flips the GIL needs a fresh subprocess: once the GIL
is re-enabled it stays enabled for the rest of that process, so import
order and prior tests would otherwise contaminate the result. This is the
same isolation the tool's own error message recommends for bisecting a
real regression -- the test suite uses it for the same reason.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from gil_guard import NOGIL_BUILD, assert_gil_stays_disabled


def _run(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_noop_on_standard_build_regardless_of_import():
    """On a standard (GIL-enabled) build there's nothing to regress from --
    the context manager must never raise, no matter what's imported. This
    runs on every interpreter, not just free-threaded ones."""
    with assert_gil_stays_disabled():
        import json  # noqa: F401

    if not NOGIL_BUILD:
        # Even a real trigger is a no-op off the free-threaded build --
        # but don't require lxml to be installed just for this bonus check.
        pytest.importorskip("lxml.etree")
        with assert_gil_stays_disabled():
            import lxml.etree  # noqa: F401


@pytest.mark.skipif(not NOGIL_BUILD, reason="requires a free-threaded build")
def test_silent_on_nonregressing_import():
    script = (
        "from gil_guard import assert_gil_stays_disabled\n"
        "with assert_gil_stays_disabled():\n"
        "    import json\n"
        "print('OK')\n"
    )
    result = _run(script)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


@pytest.mark.skipif(not NOGIL_BUILD, reason="requires a free-threaded build")
def test_catches_real_lxml_regression():
    """lxml < 7.0 (currently-shipping stable, confirmed 6.1.3) genuinely
    re-enables the GIL on import -- no free-threading support declared
    yet. This is the tool's own confirmed real-world trigger, not a
    simulation."""
    script = (
        "import sys\n"
        "from gil_guard import assert_gil_stays_disabled, GilReenabledError\n"
        "try:\n"
        "    with assert_gil_stays_disabled():\n"
        "        import lxml.etree\n"
        "    print('NOT CAUGHT')\n"
        "except GilReenabledError as e:\n"
        "    print('CAUGHT:', e)\n"
    )
    result = _run(script)
    assert "CAUGHT:" in result.stdout, result.stdout + result.stderr
    assert "NOT CAUGHT" not in result.stdout


@pytest.mark.skipif(not NOGIL_BUILD, reason="requires a free-threaded build")
def test_exception_message_names_the_mechanism():
    # Subprocess, same as the other real-regression tests -- doing this
    # in-process would flip the GIL inside the *outer* test run itself
    # (which is dogfooding this same plugin against its own suite) and
    # trip a real regression report on the whole session, not just this
    # one test.
    script = (
        "from gil_guard import assert_gil_stays_disabled, GilReenabledError\n"
        "try:\n"
        "    with assert_gil_stays_disabled():\n"
        "        import lxml.etree\n"
        "    print('NOT CAUGHT')\n"
        "except GilReenabledError as e:\n"
        "    assert 'Py_mod_gil' in str(e), str(e)\n"
        "    print('CAUGHT')\n"
    )
    result = _run(script)
    assert "CAUGHT" in result.stdout, result.stdout + result.stderr
    assert "NOT CAUGHT" not in result.stdout
