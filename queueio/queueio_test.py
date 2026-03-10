import os

import pytest

from .queueio import QueueIO
from .registry import ROUTINE_REGISTRY
from .stub import StubBackend


def test_queueio_with_custom_broker():
    """QueueIO with a custom broker."""
    with (
        StubBackend.connect() as backend,
        backend.broker() as broker,
        backend.journal() as journal,
    ):
        queueio = QueueIO(broker=broker, journal=journal)

        try:
            queueio.sync(["queueio"])
            queueio.purge(queue="queueio")

            events = queueio.subscribe({object})
            queueio.unsubscribe(events)
        finally:
            queueio.shutdown()


def test_different_queueio_instances_are_independent():
    """QueueIO instances are independent."""
    with (
        StubBackend.connect() as backend1,
        StubBackend.connect() as backend2,
        backend1.broker() as broker1,
        backend1.journal() as journal1,
        backend2.broker() as broker2,
        backend2.journal() as journal2,
    ):
        queueio1 = QueueIO(broker=broker1, journal=journal1)
        queueio2 = QueueIO(broker=broker2, journal=journal2)

        try:
            queueio1.sync(["queueio"])
            queueio1.purge(queue="queueio")
            queueio2.sync(["queueio"])
            queueio2.purge(queue="queueio")

            events1 = queueio1.subscribe({object})
            events2 = queueio2.subscribe({object})

            queueio1.unsubscribe(events1)
            queueio2.unsubscribe(events2)

        finally:
            queueio1.shutdown()
            queueio2.shutdown()


def test_queueio_loads_configuration_from_pyproject(tmp_path):
    """QueueIO loads broker configuration from pyproject.toml."""

    config_dir = tmp_path / "default_config"
    config_dir.mkdir()
    config_file = config_dir / "pyproject.toml"
    config_content = """
        [project]
        name = "test-project-defaults"
        version = "0.1.0"

        [tool.queueio]
        broker = "amqp://localhost:5672"
        """
    config_file.write_text(config_content)

    original_cwd = os.getcwd()
    os.chdir(config_dir)

    original_registry = dict(ROUTINE_REGISTRY)
    ROUTINE_REGISTRY.clear()

    try:
        with QueueIO.default() as queueio:
            queueio.sync(["test"])
            queueio.purge(queue="test")
            events = queueio.subscribe({object})
            queueio.unsubscribe(events)
    finally:
        os.chdir(original_cwd)
        ROUTINE_REGISTRY.clear()
        ROUTINE_REGISTRY.update(original_registry)


def test_queueio_routines_method():
    """QueueIO.routines() returns registered routines."""
    from .routine import Routine

    with (
        StubBackend.connect() as backend,
        backend.broker() as broker,
        backend.journal() as journal,
    ):
        queueio = QueueIO(broker=broker, journal=journal)

        original_registry = dict(ROUTINE_REGISTRY)
        ROUTINE_REGISTRY.clear()

        try:

            def test_function():
                pass

            test_routine = Routine(
                test_function, name="test_routine", queue="test_queue"
            )
            ROUTINE_REGISTRY["test_routine"] = test_routine

            try:
                routines = queueio.routines()

                assert len(routines) == 1
                assert routines[0].name == "test_routine"
                assert routines[0].queue == "test_queue"
            finally:
                queueio.shutdown()
        finally:
            ROUTINE_REGISTRY.clear()
            ROUTINE_REGISTRY.update(original_registry)


def test_queueio_with_valid_config(tmp_path):
    """QueueIO works with a valid pyproject.toml configuration."""

    config_dir = tmp_path / "valid_config"
    config_dir.mkdir()
    config_file = config_dir / "pyproject.toml"
    config_content = """
        [project]
        name = "test-project"
        version = "0.1.0"

        [tool.queueio]
        register = ["queueio.samples.expanded"]
        broker = "amqp://localhost:5672"
        """
    config_file.write_text(config_content)

    original_cwd = os.getcwd()
    os.chdir(config_dir)

    try:
        with QueueIO.default() as queueio:
            queueio.sync(["test"])
            queueio.purge(queue="test")
            routines = queueio.routines()
            routine_names = {routine.name for routine in routines}
            assert "regular" in routine_names
    finally:
        os.chdir(original_cwd)


def test_queueio_with_unsupported_uri_scheme(tmp_path):
    """QueueIO fails with an unsupported URI scheme."""

    config_dir = tmp_path / "unsupported_scheme"
    config_dir.mkdir()
    config_file = config_dir / "pyproject.toml"
    config_content = """
        [project]
        name = "test-project-unsupported"
        version = "0.1.0"

        [tool.queueio]
        broker = "redis://localhost:6379"
        """
    config_file.write_text(config_content)

    original_cwd = os.getcwd()
    os.chdir(config_dir)

    original_registry = dict(ROUTINE_REGISTRY)
    ROUTINE_REGISTRY.clear()

    try:
        with (
            pytest.raises(ValueError, match="Unsupported URI scheme"),
            QueueIO.default(),
        ):
            pass
    finally:
        os.chdir(original_cwd)
        ROUTINE_REGISTRY.clear()
        ROUTINE_REGISTRY.update(original_registry)


def test_queueio_with_environment_variable(tmp_path, monkeypatch):
    """QueueIO prefers environment variable over config."""

    config_dir = tmp_path / "env_test"
    config_dir.mkdir()
    config_file = config_dir / "pyproject.toml"
    config_content = """
        [project]
        name = "test-project-env"
        version = "0.1.0"

        [tool.queueio]
        broker = "amqp://config:5672"
        """
    config_file.write_text(config_content)

    original_cwd = os.getcwd()
    os.chdir(config_dir)

    original_registry = dict(ROUTINE_REGISTRY)
    ROUTINE_REGISTRY.clear()

    monkeypatch.setenv("QUEUEIO_BROKER", "amqp://localhost:5672")

    try:
        with QueueIO.default() as queueio:
            queueio.sync(["test"])
            queueio.purge(queue="test")
    finally:
        os.chdir(original_cwd)
        ROUTINE_REGISTRY.clear()
        ROUTINE_REGISTRY.update(original_registry)


def test_queueio_with_invalid_environment_variable(monkeypatch):
    """QueueIO fails with unsupported QUEUEIO_BROKER environment variable."""
    monkeypatch.setenv("QUEUEIO_BROKER", "redis://invalid:6379")

    original_registry = dict(ROUTINE_REGISTRY)
    ROUTINE_REGISTRY.clear()

    try:
        with (
            pytest.raises(ValueError, match="Unsupported URI scheme"),
            QueueIO.default(),
        ):
            pass
    finally:
        ROUTINE_REGISTRY.clear()
        ROUTINE_REGISTRY.update(original_registry)


def test_queueio_with_psycopg_not_yet_implemented(tmp_path):
    """QueueIO recognizes psycopg broker but it is not yet implemented."""

    config_dir = tmp_path / "psycopg_config"
    config_dir.mkdir()
    config_file = config_dir / "pyproject.toml"
    config_file.write_text("""
        [project]
        name = "test-project-psycopg"
        version = "0.1.0"

        [tool.queueio]
        broker = "postgresql://localhost:5432"
        """)

    original_cwd = os.getcwd()
    os.chdir(config_dir)

    original_registry = dict(ROUTINE_REGISTRY)
    ROUTINE_REGISTRY.clear()

    try:
        with (
            pytest.raises(ValueError, match="not yet implemented"),
            QueueIO.default(),
        ):
            pass
    finally:
        os.chdir(original_cwd)
        ROUTINE_REGISTRY.clear()
        ROUTINE_REGISTRY.update(original_registry)


def test_queueio_with_no_broker_configured(tmp_path):
    """QueueIO fails when no broker is configured."""

    config_dir = tmp_path / "no_broker"
    config_dir.mkdir()
    config_file = config_dir / "pyproject.toml"
    config_file.write_text("""
        [project]
        name = "test-project-no-broker"
        version = "0.1.0"

        [tool.queueio]
        """)

    original_cwd = os.getcwd()
    os.chdir(config_dir)

    original_registry = dict(ROUTINE_REGISTRY)
    ROUTINE_REGISTRY.clear()

    try:
        with (
            pytest.raises(ValueError, match="No broker configured"),
            QueueIO.default(),
        ):
            pass
    finally:
        os.chdir(original_cwd)
        ROUTINE_REGISTRY.clear()
        ROUTINE_REGISTRY.update(original_registry)
