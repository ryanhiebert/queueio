import subprocess
import sys

import pytest

from queueio.invocation import Invocation
from queueio.queueio import QueueIO
from queueio.result import Ok

from .queuevar import demonstrate_queuevar


@pytest.mark.timeout(10)
def test_queuevar_propagation():
    """QueueVar values propagate through the full invocation chain."""
    queueio = QueueIO()

    with queueio.activate():
        queueio.create(queue="queuevar")
        queueio.purge(queue="queuevar")
        events = queueio.subscribe({Invocation.Completed})
        invocation = demonstrate_queuevar()
        queueio.submit(invocation)

        proc = subprocess.Popen(
            [sys.executable, "-m", "queueio", "run", "queuevar=2"],
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
