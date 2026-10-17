import pytest

from queueio.journal_test import BaseJournalTest
from queueio.queueio import QueueIO

from . import PikaBackend


class TestPikaJournal(BaseJournalTest):
    @pytest.fixture
    def journal(self):
        with (
            PikaBackend.connect(QueueIO.broker_uri()) as backend,
            backend.journal() as journal,
        ):
            yield journal
