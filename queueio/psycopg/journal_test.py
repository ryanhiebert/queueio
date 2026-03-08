import os

import pytest

psycopg = pytest.importorskip(
    "psycopg", reason="psycopg not available", exc_type=ImportError
)

from queueio.journal_test import BaseJournalTest  # noqa: E402

from .journal import PsycopgJournal  # noqa: E402

PSYCOPG_TEST_URI = os.environ.get(
    "QUEUEIO_PSYCOPG_TEST", "postgresql://postgres@localhost/queueio_test"
)


def psycopg_available() -> bool:
    try:
        conn = psycopg.connect(PSYCOPG_TEST_URI)
        conn.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not psycopg_available(), reason="PostgreSQL not available"
)


class TestPsycopgJournal(BaseJournalTest):
    @pytest.fixture
    def journal(self):
        journal = PsycopgJournal.from_uri(PSYCOPG_TEST_URI)

        # Truncate to isolate tests
        with psycopg.connect(PSYCOPG_TEST_URI, autocommit=True) as conn:
            conn.execute("TRUNCATE queueio_journal")

        yield journal
        journal.shutdown()
