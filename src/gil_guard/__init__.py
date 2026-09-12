"""gil-guard -- catch silent GIL re-enablement on free-threaded Python.

On CPython's free-threaded build (PEP 703, 3.13+), importing a C extension
that has not declared free-threading support (no ``Py_mod_gil`` slot)
silently re-enables the GIL for the rest of the process. There is no
crash and no test failure -- only a single, easy-to-miss ``RuntimeWarning``
at import time. From that point on, the process is quietly serialized.

This module is a small, direct generalization of the pattern NumPy already
built into its own test suite (``numpy/conftest.py`` +
``numpy/testing/_private/utils.py``), packaged so other projects don't have
to reinvent it.
"""

from __future__ import annotations

import sys
import sysconfig
from contextlib import contextmanager
from typing import Iterator

__version__ = "0.1.0"

__all__ = ["NOGIL_BUILD", "GilReenabledError", "assert_gil_stays_disabled"]

# NOTE: hasattr(sys, "_is_gil_enabled") is NOT a valid free-threading check --
# the attribute exists on the STANDARD (GIL-enabled) 3.13+ build too, where it
# always returns True. Py_GIL_DISABLED (from sysconfig, baked in at compile
# time) is the only reliable signal, matching numpy's own NOGIL_BUILD constant
# exactly.
NOGIL_BUILD: bool = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))


class GilReenabledError(RuntimeError):
    """Raised when the GIL was silently re-enabled inside a guarded block."""


@contextmanager
def assert_gil_stays_disabled() -> Iterator[None]:
    """Raise :class:`GilReenabledError` if the GIL flips from disabled to
    enabled anywhere inside this block.

    A no-op on a standard (GIL-enabled) build -- there is nothing to
    regress from, so nothing to check.

    Example::

        from gil_guard import assert_gil_stays_disabled

        with assert_gil_stays_disabled():
            import some_c_extension  # raises if it re-enables the GIL
    """
    if not NOGIL_BUILD:
        yield
        return

    before = sys._is_gil_enabled()
    yield
    after = sys._is_gil_enabled()
    if not before and after:
        raise GilReenabledError(
            "The GIL was silently re-enabled inside this block. A C "
            "extension imported here likely lacks free-threading support "
            "(declares no Py_mod_gil slot). Run with PYTHON_GIL=0 or "
            "-Xgil=0 to see the underlying RuntimeWarning, or import "
            "suspect modules one at a time in a subprocess to isolate "
            "which one triggered it."
        )
