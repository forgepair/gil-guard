"""End-to-end test of the pytest plugin itself, via pytest's own `pytester`
fixture: runs a real, separate pytest session in a subprocess (so the
plugin auto-registers via its entry point exactly as it would for a real
user, and the GIL-state side effect doesn't leak into this test run) and
checks the session fails with the plugin's own report.
"""

from __future__ import annotations

import pytest

from gil_guard import NOGIL_BUILD

pytestmark = pytest.mark.skipif(
    not NOGIL_BUILD, reason="requires a free-threaded build"
)


def test_plugin_fails_session_on_real_regression(pytester: pytest.Pytester):
    pytester.makepyfile(
        test_regresses="""
        def test_imports_lxml():
            import lxml.etree
            assert True
        """
    )
    result = pytester.runpytest_subprocess()
    # pytest.exit() aborts before the normal outcome-summary line prints
    # (same mechanism numpy's own conftest.py uses) -- that's the point:
    # the terminal reads unmistakably as a hard stop, not a quiet pass.
    # assert_outcomes() has nothing to parse here, so check the exit and
    # the report directly instead.
    result.stdout.fnmatch_lines(["test_regresses.py .*"])
    assert result.ret == 1
    result.stdout.fnmatch_lines(["*GIL re-enabled*"])


def test_plugin_silent_when_nothing_regresses(pytester: pytest.Pytester):
    pytester.makepyfile(
        test_clean="""
        def test_imports_json():
            import json
            assert True
        """
    )
    result = pytester.runpytest_subprocess()
    result.assert_outcomes(passed=1)
    assert result.ret == 0
