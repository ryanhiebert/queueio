import pytest

from queueio.broker_test import BaseBrokerTest
from queueio.queueio import QueueIO

from . import PikaBackend


def test_global_qos_supported():
    with PikaBackend.connect(QueueIO.broker_uri()) as backend, backend.broker():
        pass


@pytest.mark.no_global_qos
def test_global_qos_required():
    with (
        PikaBackend.connect(QueueIO.broker_uri()) as backend,
        pytest.raises(RuntimeError) as caught,
        backend.broker(),
    ):
        pytest.fail("Broker opened without channel-wide QoS support")

    assert "Could not verify channel-wide QoS support" in str(caught.value)
    assert "On RabbitMQ, set" in str(caught.value)
    assert "deprecated_features.permit.global_qos = true" in str(caught.value)


class TestPikaBroker(BaseBrokerTest):
    supports_multiple_queues = True
    supports_weighted_queue_subscriptions = False

    @pytest.fixture
    def broker(self):
        with (
            PikaBackend.connect(QueueIO.broker_uri()) as backend,
            backend.broker() as broker,
        ):
            yield broker
