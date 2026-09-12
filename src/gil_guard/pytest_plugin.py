"""pytest plugin: fails the test session if the GIL is silently re-enabled
at any point during the run, on a free-threaded build.

Same detection pattern as numpy's own ``numpy/conftest.py``
(``pytest_sessionstart`` capture + ``pytest_terminal_summary`` check),
generalized into a standalone, installable plugin -- auto-registered via
the ``pytest11`` entry point the moment ``gil-guard`` is installed, no
project-specific conftest.py required.
"""

from __future__ import annotations

import sys

import pytest

from gil_guard import NOGIL_BUILD

_gil_enabled_at_start = True


def pytest_sessionstart(session: pytest.Session) -> None:
    global _gil_enabled_at_start
    if NOGIL_BUILD:
        _gil_enabled_at_start = sys._is_gil_enabled()


def pytest_terminal_summary(
    terminalreporter: "pytest.TerminalReporter",
    exitstatus: int,
    config: pytest.Config,
) -> None:
    if not NOGIL_BUILD:
        return
    if _gil_enabled_at_start or not sys._is_gil_enabled():
        return

    tr = terminalreporter
    tr.ensure_newline()
    tr.section("GIL re-enabled", sep="=", red=True, bold=True)
    tr.line("The GIL was silently re-enabled at some point during this test session.")
    tr.line("This can happen with no test failures if the RuntimeWarning raised by")
    tr.line("Python when this happens was filtered, or just went unnoticed in the")
    tr.line("output.")
    tr.line("")
    tr.line("A C extension imported during the run likely lacks free-threading")
    tr.line("support (declares no Py_mod_gil slot). Run with PYTHON_GIL=0 or")
    tr.line("-Xgil=0 to see the underlying RuntimeWarning and find the culprit, or")
    tr.line("bisect by importing suspect modules one at a time in isolation.")
    pytest.exit("gil-guard: GIL re-enabled during test session", returncode=1)
