import pytest

from queueio.journal_test import BaseJournalTest

from . import PikaBackend


class TestPikaJournal(BaseJournalTest):
    @pytest.fixture
    def journal(self):
        with (
            PikaBackend.connect("amqp://localhost:5672") as backend,
            backend.journal() as journal,
        ):
            yield journal
