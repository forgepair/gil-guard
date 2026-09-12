# gil-guard

A pytest plugin + standalone context manager that catches silent GIL
regressions on free-threaded Python the moment they happen.

## The problem

On CPython's free-threaded build (`python3.14t`, PEP 703), importing a C
extension that hasn't declared free-threading support silently flips the
GIL back on for the rest of the process. There's no crash and no test
failure — just quietly-serialized execution from that point forward. The
only signal is a single, easy-to-miss `RuntimeWarning` at import time.

NumPy already built this exact check into its own test suite because no
shared tool existed (`numpy/conftest.py` + `numpy/testing/_private/
utils.py`). `gil-guard` generalizes that pattern into an installable
package.

## Install

```
pip install gil-guard
```

## Use as a pytest plugin

Nothing to configure — installing the package registers it automatically.
If any test in the session silently re-enables the GIL, the session fails
with a clear report naming what happened, even if every individual test
still passed.

## Use as a standalone context manager

```python
from gil_guard import assert_gil_stays_disabled, GilReenabledError

with assert_gil_stays_disabled():
    import some_c_extension  # raises GilReenabledError if it flips the GIL
```

A no-op on a standard (GIL-enabled) build — there's nothing to regress
from, so nothing to check.

## Known real-world trigger

`lxml < 7.0` (current stable, confirmed against 6.1.3) genuinely
re-enables the GIL on import — free-threading support only landed in the
7.0 beta. This is the confirmed trigger the test suite runs against, not a
simulation.

## Why this exists

Two serious engineering teams hit this same failure independently and
built their own detection from scratch within days of each other: NumPy's
in-house test-suite check, and PyTorch's TorchCodec team
(`meta-pytorch/torchcodec#1701`, filed 2026-09-09). Free-threaded Python is
new enough that most of the C-extension ecosystem hasn't caught up yet —
this will keep recurring for as long as that takes.

## License

MIT
