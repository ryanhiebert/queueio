import json
import os
import socket
import subprocess
import sys
import time
from urllib.request import Request
from urllib.request import urlopen

import pytest


def _wait_for_port(port, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.1)
    raise TimeoutError(f"Port {port} not ready")


@pytest.mark.timeout(10)
@pytest.mark.parametrize(
    "settings",
    [
        pytest.param("queueio.samples.django.settings", id="explicit"),
        pytest.param("queueio.samples.django.settings_djp", id="djp"),
    ],
)
def test_django(tmp_path, settings):
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": settings}

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        f"[tool.django]\n"
        f'settings = "{settings}"\n'
        f"\n"
        f"[tool.queueio]\n"
        f'register = ["queueio.samples.django.job"]\n'
        f'pika = "amqp://localhost:5672"\n'
    )

    subprocess.run(
        [sys.executable, "-m", "django", "migrate", "--run-syncdb"],
        cwd=str(tmp_path),
        env=env,
        check=True,
        capture_output=True,
    )

    subprocess.run(
        [sys.executable, "-m", "queueio", "sync"],
        cwd=str(tmp_path),
        env=env,
        check=True,
        capture_output=True,
    )

    server = subprocess.Popen(
        [sys.executable, "-m", "django", "runserver", "--noreload", "127.0.0.1:8642"],
        cwd=str(tmp_path),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    worker = subprocess.Popen(
        [sys.executable, "-m", "queueio", "run", "django=1"],
        cwd=str(tmp_path),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        _wait_for_port(8642)

        urlopen(Request("http://127.0.0.1:8642/", method="POST"))

        while True:
            assert worker.poll() is None, (
                f"Worker exited early with code {worker.returncode}"
            )
            response = urlopen("http://127.0.0.1:8642/")
            data = json.loads(response.read())
            if data["status"] == "complete":
                break
            time.sleep(0.1)
    finally:
        for proc in [server, worker]:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
