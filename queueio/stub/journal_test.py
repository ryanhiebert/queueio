import pytest

from queueio.journal_test import BaseJournalTest

from . import StubBackend


class TestStubJournal(BaseJournalTest):
    @pytest.fixture
    def journal(self):
        with StubBackend.connect() as backend, backend.journal() as journal:
            yield journal
