import pytest

from queueio.broker_test import BaseBrokerTest

from . import StubBackend


class TestStubBroker(BaseBrokerTest):
    supports_multiple_queues = True
    supports_weighted_queue_subscriptions = True

    @pytest.fixture
    def broker(self):
        with StubBackend.connect() as backend, backend.broker() as broker:
            yield broker
