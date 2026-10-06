"""Shared test setup. pytest loads this file automatically before the tests."""
import os
import sys

import pytest

# The tests live in tests/ and the app one folder up, so make the app importable.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import db

APP_FILE = os.path.join(REPO, "app.py")

# Artist ids from seed/artists.csv, named so the tests read like the brief.
TIDEWATERS = 1     # 60 min, €3,500
LUNA_FERRO = 2     # 75 min, €3,000
COBALT_AVENUE = 3  # 60 min, €2,500
SALT_STATIC = 4    # 90 min, €2,000
OS_GAIVOTAS = 5    # 45 min, €1,500
MARISOL_VEGA = 6   # 45 min, €1,200
NIGHT_FERRY = 7    # 60 min, €1,000


@pytest.fixture(autouse=True)
def fresh_database(tmp_path, monkeypatch):
    """Give every test its own new database built from seed/, so data/ is never touched."""
    monkeypatch.setattr(db, "DB_PATH", os.path.join(tmp_path, "festival.db"))
    db.create_database()


def lineup():
    """The saved bookings as (artist, stage, start) tuples, sorted, to make comparisons short."""
    rows = []
    for booking in db.load_bookings():
        rows.append((booking["artist_id"], booking["stage_id"], booking["start"]))
    rows.sort()
    return rows
