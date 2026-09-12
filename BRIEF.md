# gil-guard

## The pitch

A pytest plugin + standalone context manager that catches silent GIL
regressions on free-threaded Python the moment they happen, instead of
nobody noticing.

On Python 3.13+'s free-threaded build (`python3.14t`, PEP 703), importing a
C extension that hasn't declared free-threading support silently flips the
GIL back on for the rest of the process. No crash, no test failure -- just
quietly-serialized execution from that point forward. The only signal is an
easy-to-miss `RuntimeWarning` emitted once, at import time.

## Evidence this is a real, recurring pain (not hypothetical)

- **NumPy already hand-built exactly this check** into its own test suite
  (`numpy/testing/_private/utils.py` + `numpy/conftest.py`) because no shared
  tool exists. Verified by reading the actual live source at its correct
  path on 2026-09-12:
  - `numpy/testing/_private/utils.py:128`: `NOGIL_BUILD = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))`
  - `numpy/conftest.py:100-123`: captures GIL state at session start, hard-fails
    (`pytest.exit(..., returncode=1)`) via `pytest_terminal_summary` if it
    flips during the run.
- **PyTorch's TorchCodec team independently hit the identical failure.**
  `meta-pytorch/torchcodec#1701`, opened 2026-09-09 (3 days before this brief),
  status OPEN, real `uv run` reproduction showing `sys._is_gil_enabled()`
  flip from `False` to `True` on import, active maintainer discussion
  in progress (not stale, not resolved).
- Two separate, serious engineering teams solved the identical narrow
  problem from scratch, in the same rough window -- the clearest real-world
  signal that this belongs in a shared package, not two bespoke
  reimplementations.

## Market check (verified 2026-09-12)

- GitHub search (`gh api search/repositories`, multiple query variants):
  zero existing tools targeting this specifically.
- PyPI namespace check (direct package-index lookups, not just search):
  `pytest-gil-check`, `gil-guard`, `pytest-nogil-check`,
  `free-threading-check`, `pytest-freethreading`, `gil-regression` --
  all return 404 (unclaimed).
- No competing product found anywhere.

## Technical verification (real, end-to-end, not simulated)

Performed live during this session on Bigboy:

1. Installed a genuine free-threaded Python 3.14.6 build
   (`python3.14t.exe`) via the official python.org installer with
   `Include_freethreaded=1`. Two real installer conflicts were hit and
   fixed along the way:
   - `0x80070666` ("cannot install when a newer version is installed") --
     fixed by targeting a separate `TargetDir` instead of the existing
     system Python's directory.
   - `0x80070659` on the launcher sub-package (conflicted with the existing
     system Python's `py.exe` launcher) -- fixed with `Include_launcher=0`.
2. Confirmed the real interpreter starts with the GIL disabled:
   `sys._is_gil_enabled() == False`, `sysconfig.get_config_var("Py_GIL_DISABLED") == 1`.
3. Found a real, currently-shipping trigger: `lxml==6.1.3` (current stable;
   lxml's free-threading support only landed in the 7.0 beta) genuinely
   flips the GIL on import, with CPython's real documented `RuntimeWarning`:
   > "The global interpreter lock (GIL) has been enabled to load module
   > 'lxml.etree', which has not declared that it can run safely without
   > the GIL."
4. Built `gil_guard.py` (context manager `assert_gil_stays_disabled()` +
   pytest hooks `pytest_configure`/`pytest_terminal_summary`), generalizing
   NumPy's exact pattern.
5. Caught and fixed a real bug during the build: naive
   `hasattr(sys, "_is_gil_enabled")` is NOT a valid free-threading check on
   Python 3.14+ -- the attribute exists on standard (GIL-enabled) builds
   too, always returning `True`. Fixed to use
   `sysconfig.get_config_var("Py_GIL_DISABLED")`, then confirmed this
   exactly matches NumPy's own real production code, line for line.
6. Ran the corrected tool against the real `lxml` trigger on the real
   free-threaded interpreter -- it correctly detected and raised on the
   genuine regression. Full real output:
   ```
   NOGIL_BUILD: True
   SUCCESS: gil_guard correctly caught the REAL regression
   Message: The GIL was silently re-enabled inside this block. A C
   extension imported here likely lacks free-threading support (declares
   no Py_mod_gil slot). Run with PYTHON_GIL=0 or -Xgil=0 to see the
   underlying RuntimeWarning, or import it in a subprocess.
   ```

## Why now

Free-threaded Python is new enough (3.13 GA in 2024, still maturing through
3.14) that most of the C-extension ecosystem hasn't caught up. This exact
failure mode will keep recurring for as long as the ecosystem takes to add
`Py_mod_gil` support broadly -- a multi-year window, not a one-off.

## Product shape

- `pip install gil-guard`
- Drop-in pytest plugin: auto-registers via entry point, fails the test
  session with a clear message the moment any test silently re-enables
  the GIL.
- Standalone context manager for non-pytest use (CI import checks, library
  code, notebooks): `with assert_gil_stays_disabled(): import mymodule`.

## Known open items / next steps

- Not yet packaged (no `pyproject.toml`, no PyPI upload, no pytest entry
  point registration tested end-to-end -- only the raw module + hooks were
  written and manually invoked).
- Only tested against one real trigger (lxml 6.1.3). Worth confirming
  against a second/third real unsupported extension for robustness.
- Naming: `gil-guard` is available on PyPI as of this check but not yet
  reserved/claimed.
- No CI matrix yet across free-threaded Python versions (3.13t vs 3.14t).

## Source material / working files (this session)

- `numpy/conftest.py`, `numpy/testing/_private/utils.py` -- read live from
  numpy/numpy@main via GitHub raw + code search, 2026-09-12.
- `meta-pytorch/torchcodec#1701` -- read live via `gh api`, 2026-09-12.
- Prototype: `gil_guard.py`, built and tested in this session at
  `%LOCALAPPDATA%\Temp\gil_guard_test\` (scratch location, not preserved --
  rebuild from this brief's description if resuming).
