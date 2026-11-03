import faulthandler
import os
import threading
from contextlib import nullcontext
from typing import TextIO

import pytest
from _pytest.capture import CaptureManager

# Grace beyond the per-test timeout for pytest-timeout to fail the test.
WATCHDOG_MARGIN = 15
# Inactivity limit when per-test timeouts are disabled.
WATCHDOG_DEFAULT = 60
# How long the process may take to exit after pytest finishes.
WATCHDOG_EXIT = 10

_watchdog_file: TextIO | None = None
_watchdog_limit: float = WATCHDOG_DEFAULT


def _watchdog(seconds: float):
    """Exit with all thread stacks if no progress is made within ``seconds``.

    Each call resets the deadline. The timer runs in a C-level thread,
    so it fires even if Python code is stuck.
    """
    if _watchdog_file is not None:
        faulthandler.dump_traceback_later(seconds, exit=True, file=_watchdog_file)


def pytest_configure(config: pytest.Config):
    """Ensure the test suite always exits, even when nobody is watching.

    pytest-timeout only covers individual tests. The watchdog also covers
    collection and interpreter exit, and dumps every thread's stack before
    exiting so that the hang can be diagnosed afterwards.
    """
    global _watchdog_file, _watchdog_limit

    try:
        timeout = float(config.getoption("timeout", None) or config.getini("timeout"))
    except ValueError:
        timeout = 0
    _watchdog_limit = timeout + WATCHDOG_MARGIN if timeout > 0 else WATCHDOG_DEFAULT

    # Write to the real stderr, not pytest's capture of it.
    capman = config.pluginmanager.getplugin("capturemanager")
    if isinstance(capman, CaptureManager):
        suspended = capman.global_and_fixture_disabled()
    else:
        suspended = nullcontext()
    with suspended:
        _watchdog_file = os.fdopen(os.dup(2), "w")
    _watchdog(_watchdog_limit)


def pytest_collectstart():
    _watchdog(_watchdog_limit)


def pytest_collectreport():
    _watchdog(_watchdog_limit)


def pytest_runtest_logstart():
    _watchdog(_watchdog_limit)


def pytest_runtest_logreport():
    _watchdog(_watchdog_limit)


def pytest_sessionfinish():
    _watchdog(_watchdog_limit)


def pytest_unconfigure():
    _watchdog(WATCHDOG_EXIT)


@pytest.fixture(autouse=True)
def check_thread_cleanup():
    """Ensure that threads are not left running."""
    initial_threads = set(threading.enumerate())
    yield
    final_threads = {t for t in threading.enumerate() if t.is_alive()}
    new_threads = final_threads - initial_threads

    if new_threads:
        thread_info = []
        for thread in new_threads:
            daemon = "daemon" if thread.daemon else "non-daemon"
            thread_info.append(f"  - {thread.name} ({daemon})")

        pytest.fail(
            f"Test left {len(new_threads)} thread(s) running:\n"
            + "\n".join(thread_info)
        )
