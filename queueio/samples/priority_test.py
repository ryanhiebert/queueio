import subprocess
import sys

import pytest

from queueio.invocation import Invocation
from queueio.queueio import QueueIO
from queueio.result import Ok

from .priority import demonstrate_priorities


@pytest.mark.timeout(10)
def test_priority_propagation():
    """Priority propagates through the full invocation chain."""
    queueio = QueueIO()

    with queueio.activate():
        queueio.create(queue="priority")
        queueio.purge(queue="priority")
        events = queueio.subscribe({Invocation.Completed})
        invocation = demonstrate_priorities()
        queueio.submit(invocation)

        proc = subprocess.Popen(
            [sys.executable, "-m", "queueio", "run", "priority=2"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            while event := events.get():
                if event.id == invocation.id:
                    assert isinstance(event.result, Ok)
                    break
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
