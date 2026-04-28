import os
import tempfile

os.environ["RESOLVEDESK_RUNTIME"] = tempfile.mkdtemp(prefix="resolvedesk-test-")
os.environ["AGENT_MODE"] = "demo"

import pytest
from resolvedesk import store


@pytest.fixture(autouse=True)
def clean_store():
    store.init_db()
    with store.connection() as db:
        for table in (
            "events",
            "approvals",
            "receipts",
            "runs",
            "tickets",
            "orders",
            "inventory",
            "products",
            "sessions",
        ):
            db.execute(f"DELETE FROM {table}")
    store.init_db()
