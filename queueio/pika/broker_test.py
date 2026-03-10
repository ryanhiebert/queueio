import pytest

from queueio.broker_test import BaseBrokerTest

from . import PikaBackend


class TestPikaBroker(BaseBrokerTest):
    supports_multiple_queues = True
    supports_weighted_queue_subscriptions = False

    @pytest.fixture
    def broker(self):
        with (
            PikaBackend.connect("amqp://localhost:5672") as backend,
            backend.broker() as broker,
        ):
            yield broker
