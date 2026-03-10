import subprocess
import sys

import pytest

from queueio.invocation import Invocation
from queueio.queueio import QueueIO
from queueio.result import Ok

from .expanded import irregular


@pytest.mark.timeout(10)
def test_integration():
    # Prefers a clean environment and queue
    with QueueIO.default() as queueio, queueio.activate():
        queueio.sync(["expanded"])
        queueio.purge(queue="expanded")
        events = queueio.subscribe({Invocation.Completed})
        invocation = irregular()
        queueio.submit(invocation)

        # 1. Start worker process in the background
        proc = subprocess.Popen(
            [sys.executable, "-m", "queueio", "run", "expanded=1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            while event := events.get():
                if event.id == invocation.id:
                    assert isinstance(event.result, Ok)
                    break
        finally:
            if proc.poll() is None:  # Process is still running
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't terminate gracefully
                    proc.kill()
                    proc.wait()
