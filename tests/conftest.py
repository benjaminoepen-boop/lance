"""Every test runs on its own throwaway database, built from the real seed/ files."""
import os
import tempfile

# Before db.py is imported: the tests must never touch data/lance.db.
os.environ["LANCE_DB"] = os.path.join(tempfile.mkdtemp(), "start.db")

import pytest

import db
import logic


@pytest.fixture(autouse=True)
def fresh_database(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    logic.forget_catalogue()
    db.init_db()
    yield
    logic.forget_catalogue()


@pytest.fixture
def plan():
    return db.load_plan(db.create_plan("Management", "Fall", 165))


@pytest.fixture
def client():
    import app as lance
    lance.app.config.update(TESTING=True)
    client = lance.app.test_client()
    # A new visitor starts without programme and points. Most tests are about what happens after that.
    client.post("/api/settings", json={"programme": "Management", "points": 165})
    return client


def add_all(plan, *section_ids):
    for section_id in section_ids:
        assert logic.add_to_plan(plan, section_id=section_id) is None


def bid_on(plan, offering_id, bid):
    for item in db.load_items(plan["id"]):
        if item["offering_id"] == offering_id:
            assert logic.set_bid(plan, item["id"], bid) is None
