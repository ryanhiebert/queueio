import os

import pytest

from queueio.stub.journal import StubJournal

from .queueio import QueueIO
from .registry import ROUTINE_REGISTRY
from .stub.broker import StubBroker


def test_queueio_with_custom_broker_and_journal():
    """QueueIO custom broker and journal implementations."""
    broker = StubBroker()
    journal = StubJournal()
    queueio = QueueIO(broker=broker, journal=journal)

    try:
        # Test purge (uses broker)
        queueio.sync(["queueio"])
        queueio.purge(queue="queueio")

        # Test subscriptions (uses journal)
        events = queueio.subscribe({object})
        queueio.unsubscribe(events)
    finally:
        queueio.shutdown()


def test_different_queueio_instances_are_independent():
    """QueueIO instances are independent."""
    # Create two QueueIO instances with different stub implementations
    broker1 = StubBroker()
    journal1 = StubJournal()
    queueio1 = QueueIO(broker=broker1, journal=journal1)

    broker2 = StubBroker()
    journal2 = StubJournal()
    queueio2 = QueueIO(broker=broker2, journal=journal2)

    try:
        # Both should work independently
        queueio1.sync(["queueio"])
        queueio1.purge(queue="queueio")
        queueio2.sync(["queueio"])
        queueio2.purge(queue="queueio")

        # Test that they can have independent subscriptions
        events1 = queueio1.subscribe({object})
        events2 = queueio2.subscribe({object})

        queueio1.unsubscribe(events1)
        queueio2.unsubscribe(events2)

    finally:
        queueio1.shutdown()
        queueio2.shutdown()


def test_queueio_loads_configuration_from_pyproject(tmp_path):
    """QueueIO loads pika configuration from pyproject.toml."""

    # Create config with default settings
    config_dir = tmp_path / "default_config"
    config_dir.mkdir()
    config_file = config_dir / "pyproject.toml"
    config_content = """
        [project]
        name = "test-project-defaults"
        version = "0.1.0"

        [tool.queueio]
        pika = "amqp://localhost:5672"
        """
    config_file.write_text(config_content)

    # Change to config directory
    original_cwd = os.getcwd()
    os.chdir(config_dir)

    # Clear registry to isolate test
    original_registry = dict(ROUTINE_REGISTRY)
    ROUTINE_REGISTRY.clear()

    try:
        queueio = QueueIO()
        try:
            # Should be able to perform basic operations
            queueio.sync(["test"])
            queueio.purge(queue="test")
            events = queueio.subscribe({object})
            queueio.unsubscribe(events)
        finally:
            queueio.shutdown()
    finally:
        os.chdir(original_cwd)
        # Restore registry
        ROUTINE_REGISTRY.clear()
        ROUTINE_REGISTRY.update(original_registry)


def test_queueio_allows_pika_override(tmp_path):
    """QueueIO allows override of pika configuration via environment variable."""

    # Create config for default pika
    config_dir = tmp_path / "override_test"
    config_dir.mkdir()
    config_file = config_dir / "pyproject.toml"
    config_content = """
        [project]
        name = "test-project-override"
        version = "0.1.0"

        [tool.queueio]
        pika = "amqp://localhost:5672"
        """
    config_file.write_text(config_content)

    # Change to config directory
    original_cwd = os.getcwd()
    os.chdir(config_dir)

    # Clear registry to isolate test
    original_registry = dict(ROUTINE_REGISTRY)
    ROUTINE_REGISTRY.clear()

    try:
        stub_broker = StubBroker()
        stub_journal = StubJournal()

        # Override just broker, journal should use default
        queueio1 = QueueIO(broker=stub_broker)

        # Override just journal, broker should use default
        queueio2 = QueueIO(journal=stub_journal)

        try:
            # Both should work
            queueio1.sync(["test"])
            queueio1.purge(queue="test")
            queueio2.sync(["test"])
            queueio2.purge(queue="test")
        finally:
            queueio1.shutdown()
            queueio2.shutdown()
    finally:
        os.chdir(original_cwd)
        # Restore registry
        ROUTINE_REGISTRY.clear()
        ROUTINE_REGISTRY.update(original_registry)


def test_queueio_routines_method():
    """QueueIO.routines() returns registered routines."""
    from .routine import Routine

    queueio = QueueIO(broker=StubBroker(), journal=StubJournal())

    # Clear registry to isolate test
    original_registry = dict(ROUTINE_REGISTRY)
    ROUTINE_REGISTRY.clear()

    try:
        # Manually add a test routine
        def test_function():
            pass

        test_routine = Routine(test_function, name="test_routine", queue="test_queue")
        ROUTINE_REGISTRY["test_routine"] = test_routine

        try:
            routines = queueio.routines()

            # Should have our test routine
            assert len(routines) == 1
            assert routines[0].name == "test_routine"
            assert routines[0].queue == "test_queue"
        finally:
            queueio.shutdown()
    finally:
        # Restore registry
        ROUTINE_REGISTRY.clear()
        ROUTINE_REGISTRY.update(original_registry)


def test_queueio_with_valid_config(tmp_path):
    """QueueIO works with a valid pyproject.toml configuration."""

    # Create valid config
    config_dir = tmp_path / "valid_config"
    config_dir.mkdir()
    config_file = config_dir / "pyproject.toml"
    config_content = """
        [project]
        name = "test-project"
        version = "0.1.0"

        [tool.queueio]
        register = ["queueio.samples.expanded"]
        pika = "amqp://localhost:5672"
        """
    config_file.write_text(config_content)

    # Change to config directory
    original_cwd = os.getcwd()
    os.chdir(config_dir)

    try:
        queueio = QueueIO()
        try:
            # Should load configuration successfully
            queueio.sync(["test"])
            queueio.purge(queue="test")
            routines = queueio.routines()
            routine_names = {routine.name for routine in routines}
            assert "regular" in routine_names
        finally:
            queueio.shutdown()
    finally:
        os.chdir(original_cwd)


def test_queueio_with_invalid_config(tmp_path):
    """QueueIO fails with unknown broker/journal types."""

    # Create config with unknown broker/journal
    config_dir = tmp_path / "invalid_config"
    config_dir.mkdir()
    config_file = config_dir / "pyproject.toml"
    config_content = """
        [project]
        name = "test-project-invalid"
        version = "0.1.0"

        [tool.queueio]
        pika = "unknown://localhost:5672"
        """
    config_file.write_text(config_content)

    # Change to config directory
    original_cwd = os.getcwd()
    os.chdir(config_dir)

    # Clear registry to isolate test
    original_registry = dict(ROUTINE_REGISTRY)
    ROUTINE_REGISTRY.clear()

    try:
        # Should raise ValueError for unknown broker URI scheme
        with pytest.raises(
            ValueError,
            match="URI scheme must be 'amqp:', got: unknown://localhost:5672",
        ):
            QueueIO()
    finally:
        os.chdir(original_cwd)
        # Restore registry
        ROUTINE_REGISTRY.clear()
        ROUTINE_REGISTRY.update(original_registry)


def test_queueio_with_invalid_broker_uri_scheme(tmp_path):
    """QueueIO fails with invalid URI scheme for broker."""

    # Create config with invalid broker URI scheme
    config_dir = tmp_path / "invalid_broker_uri"
    config_dir.mkdir()
    config_file = config_dir / "pyproject.toml"
    config_content = """
        [project]
        name = "test-project-invalid-broker-uri"
        version = "0.1.0"

        [tool.queueio]
        pika = "redis://localhost:6379"
        """
    config_file.write_text(config_content)

    # Change to config directory
    original_cwd = os.getcwd()
    os.chdir(config_dir)

    # Clear registry to isolate test
    original_registry = dict(ROUTINE_REGISTRY)
    ROUTINE_REGISTRY.clear()

    try:
        # Should raise ValueError for invalid URI scheme
        with pytest.raises(
            ValueError, match="URI scheme must be 'amqp:', got: redis://localhost:6379"
        ):
            QueueIO()
    finally:
        os.chdir(original_cwd)
        # Restore registry
        ROUTINE_REGISTRY.clear()
        ROUTINE_REGISTRY.update(original_registry)


def test_queueio_with_environment_variable(tmp_path, monkeypatch):
    """QueueIO prefers environment variable over config."""

    # Create config with different pika URI
    config_dir = tmp_path / "env_both_test"
    config_dir.mkdir()
    config_file = config_dir / "pyproject.toml"
    config_content = """
        [project]
        name = "test-project-env-both"
        version = "0.1.0"

        [tool.queueio]
        pika = "amqp://config:5672"
        """
    config_file.write_text(config_content)

    # Change to config directory
    original_cwd = os.getcwd()
    os.chdir(config_dir)

    # Clear registry to isolate test
    original_registry = dict(ROUTINE_REGISTRY)
    ROUTINE_REGISTRY.clear()

    # Set environment variable to use localhost (which works)
    monkeypatch.setenv("QUEUEIO_PIKA", "amqp://localhost:5672")

    try:
        queueio = QueueIO()
        try:
            # Should work with environment variables taking precedence
            queueio.sync(["test"])
            queueio.purge(queue="test")
        finally:
            queueio.shutdown()
    finally:
        os.chdir(original_cwd)
        # Restore registry
        ROUTINE_REGISTRY.clear()
        ROUTINE_REGISTRY.update(original_registry)


def test_queueio_with_invalid_environment_pika(monkeypatch):
    """QueueIO fails with invalid QUEUEIO_PIKA environment variable."""
    # Set invalid environment variable
    monkeypatch.setenv("QUEUEIO_PIKA", "redis://invalid:6379")

    # Clear registry to isolate test
    original_registry = dict(ROUTINE_REGISTRY)
    ROUTINE_REGISTRY.clear()

    try:
        # Should raise ValueError for invalid URI scheme
        with pytest.raises(
            ValueError, match="URI scheme must be 'amqp:', got: redis://invalid:6379"
        ):
            QueueIO()
    finally:
        # Restore registry
        ROUTINE_REGISTRY.clear()
        ROUTINE_REGISTRY.update(original_registry)


def test_queueio_with_psycopg_not_yet_implemented(tmp_path):
    """QueueIO recognizes psycopg config but backend is not yet implemented."""

    config_dir = tmp_path / "psycopg_config"
    config_dir.mkdir()
    config_file = config_dir / "pyproject.toml"
    config_file.write_text("""
        [project]
        name = "test-project-psycopg"
        version = "0.1.0"

        [tool.queueio]
        broker = "psycopg"
        journal = "psycopg"
        psycopg = "postgresql://localhost:5432"
        """)

    original_cwd = os.getcwd()
    os.chdir(config_dir)

    original_registry = dict(ROUTINE_REGISTRY)
    ROUTINE_REGISTRY.clear()

    try:
        with pytest.raises(ValueError, match="not yet implemented"):
            QueueIO()
    finally:
        os.chdir(original_cwd)
        ROUTINE_REGISTRY.clear()
        ROUTINE_REGISTRY.update(original_registry)


def test_queueio_with_invalid_psycopg_uri_scheme(tmp_path):
    """QueueIO fails with invalid URI scheme for psycopg."""

    config_dir = tmp_path / "invalid_psycopg_uri"
    config_dir.mkdir()
    config_file = config_dir / "pyproject.toml"
    config_file.write_text("""
        [project]
        name = "test-project-invalid-psycopg-uri"
        version = "0.1.0"

        [tool.queueio]
        broker = "psycopg"
        psycopg = "mysql://localhost:3306"
        """)

    original_cwd = os.getcwd()
    os.chdir(config_dir)

    original_registry = dict(ROUTINE_REGISTRY)
    ROUTINE_REGISTRY.clear()

    try:
        with pytest.raises(ValueError, match="URI scheme must be 'postgresql:'"):
            QueueIO()
    finally:
        os.chdir(original_cwd)
        ROUTINE_REGISTRY.clear()
        ROUTINE_REGISTRY.update(original_registry)


def test_queueio_with_explicit_broker_config(tmp_path):
    """QueueIO works with explicit broker selection in config."""

    config_dir = tmp_path / "explicit_broker"
    config_dir.mkdir()
    config_file = config_dir / "pyproject.toml"
    config_file.write_text("""
        [project]
        name = "test-project-explicit-broker"
        version = "0.1.0"

        [tool.queueio]
        broker = "pika"
        journal = "pika"
        pika = "amqp://localhost:5672"
        """)

    original_cwd = os.getcwd()
    os.chdir(config_dir)

    original_registry = dict(ROUTINE_REGISTRY)
    ROUTINE_REGISTRY.clear()

    try:
        queueio = QueueIO()
        try:
            queueio.sync(["test"])
            queueio.purge(queue="test")
        finally:
            queueio.shutdown()
    finally:
        os.chdir(original_cwd)
        ROUTINE_REGISTRY.clear()
        ROUTINE_REGISTRY.update(original_registry)


def test_queueio_with_explicit_backend_via_env(tmp_path, monkeypatch):
    """QueueIO works with QUEUEIO_BROKER and QUEUEIO_JOURNAL env vars."""

    config_dir = tmp_path / "explicit_env"
    config_dir.mkdir()
    config_file = config_dir / "pyproject.toml"
    config_file.write_text("""
        [project]
        name = "test-project-explicit-env"
        version = "0.1.0"

        [tool.queueio]
        pika = "amqp://localhost:5672"
        """)

    original_cwd = os.getcwd()
    os.chdir(config_dir)

    original_registry = dict(ROUTINE_REGISTRY)
    ROUTINE_REGISTRY.clear()

    monkeypatch.setenv("QUEUEIO_BROKER", "pika")
    monkeypatch.setenv("QUEUEIO_JOURNAL", "pika")

    try:
        queueio = QueueIO()
        try:
            queueio.sync(["test"])
            queueio.purge(queue="test")
        finally:
            queueio.shutdown()
    finally:
        os.chdir(original_cwd)
        ROUTINE_REGISTRY.clear()
        ROUTINE_REGISTRY.update(original_registry)


def test_queueio_with_invalid_backend_name(tmp_path):
    """QueueIO fails with an invalid backend name."""

    config_dir = tmp_path / "invalid_backend"
    config_dir.mkdir()
    config_file = config_dir / "pyproject.toml"
    config_file.write_text("""
        [project]
        name = "test-project-invalid-backend"
        version = "0.1.0"

        [tool.queueio]
        broker = "redis"
        pika = "amqp://localhost:5672"
        """)

    original_cwd = os.getcwd()
    os.chdir(config_dir)

    original_registry = dict(ROUTINE_REGISTRY)
    ROUTINE_REGISTRY.clear()

    try:
        with pytest.raises(ValueError, match="Invalid broker backend 'redis'"):
            QueueIO()
    finally:
        os.chdir(original_cwd)
        ROUTINE_REGISTRY.clear()
        ROUTINE_REGISTRY.update(original_registry)


def test_queueio_with_backend_selected_but_no_uri(tmp_path):
    """QueueIO fails when backend is selected but no URI is configured."""

    config_dir = tmp_path / "no_uri"
    config_dir.mkdir()
    config_file = config_dir / "pyproject.toml"
    config_file.write_text("""
        [project]
        name = "test-project-no-uri"
        version = "0.1.0"

        [tool.queueio]
        broker = "pika"
        journal = "pika"
        """)

    original_cwd = os.getcwd()
    os.chdir(config_dir)

    original_registry = dict(ROUTINE_REGISTRY)
    ROUTINE_REGISTRY.clear()

    try:
        with pytest.raises(ValueError, match="no URI configured"):
            QueueIO()
    finally:
        os.chdir(original_cwd)
        ROUTINE_REGISTRY.clear()
        ROUTINE_REGISTRY.update(original_registry)
