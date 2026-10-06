"""The whole database layer: one SQLite file, data/festival.db. No rules live here, only reading and writing."""
import csv
import os
import sqlite3
from contextlib import closing

HERE = os.path.dirname(os.path.abspath(__file__))
SEED_DIR = os.path.join(HERE, "seed")
# The live database. The tests point this at a throwaway file instead.
DB_PATH = os.path.join(HERE, "data", "festival.db")

# stages and artists are fixed content from seed/. bookings and plan are the organiser's progress.
SCHEMA = """
CREATE TABLE stages (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE artists (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL,
    genre    TEXT NOT NULL,
    fee      INTEGER NOT NULL,   -- euros
    duration INTEGER NOT NULL    -- minutes
);
CREATE TABLE bookings (
    artist_id INTEGER PRIMARY KEY REFERENCES artists (id),   -- one booking per artist
    stage_id  TEXT NOT NULL REFERENCES stages (id),
    start     TEXT NOT NULL                                  -- 'HH:MM'; the end is calculated
);
CREATE TABLE plan (
    status TEXT NOT NULL         -- 'draft' or 'final', exactly one row
);
"""


# ---------- creating the database ----------

def read_seed(name):
    """Read one CSV file from seed/ and return its rows as a list of dicts."""
    with open(os.path.join(SEED_DIR, name + ".csv"), newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def create_database():
    """Build a new database at DB_PATH: the tables, the seed content, an empty draft plan."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    # closing() shuts the file again when the block ends, even if something fails
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.executescript(SCHEMA)
        for stage in read_seed("stages"):
            connection.execute("INSERT INTO stages (id, name) VALUES (?, ?)",
                               (stage["id"], stage["name"]))
        for artist in read_seed("artists"):
            connection.execute(
                "INSERT INTO artists (id, name, genre, fee, duration) VALUES (?, ?, ?, ?, ?)",
                (int(artist["id"]), artist["name"], artist["genre"],
                 int(artist["fee"]), int(artist["duration"])))
        connection.execute("INSERT INTO plan (status) VALUES ('draft')")
        connection.commit()


def ensure_database():
    """Create the database on the very first start; afterwards keep what is saved."""
    if not os.path.exists(DB_PATH):
        create_database()


# ---------- the two ways to talk to SQLite ----------

def fetch(sql, params=()):
    """Run a SELECT and return every row as a plain dict, e.g. {'id': 1, 'name': '...'}."""
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(sql, params).fetchall()
    result = []
    for row in rows:
        result.append(dict(row))
    return result


def execute(sql, params=()):
    """Run one INSERT, UPDATE or DELETE and write it to disk straight away."""
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.execute(sql, params)
        connection.commit()


# ---------- reading ----------

def load_stages():
    """Every stage, Stage A first."""
    return fetch("SELECT id, name FROM stages ORDER BY id")


def load_artists():
    """The whole artist catalogue, in catalogue order."""
    return fetch("SELECT id, name, genre, fee, duration FROM artists ORDER BY id")


def load_bookings():
    """Every saved booking: which artist, on which stage, starting when."""
    return fetch("SELECT artist_id, stage_id, start FROM bookings ORDER BY start, stage_id")


def load_status():
    """'draft' or 'final'."""
    return fetch("SELECT status FROM plan")[0]["status"]


# ---------- writing ----------

def insert_booking(artist_id, stage_id, start):
    """Save a new booking."""
    execute("INSERT INTO bookings (artist_id, stage_id, start) VALUES (?, ?, ?)",
            (artist_id, stage_id, start))


def update_booking(artist_id, stage_id, start):
    """Move an existing booking to another stage or start time."""
    execute("UPDATE bookings SET stage_id = ?, start = ? WHERE artist_id = ?",
            (stage_id, start, artist_id))


def delete_booking(artist_id):
    """Remove an artist's booking."""
    execute("DELETE FROM bookings WHERE artist_id = ?", (artist_id,))


def save_status(status):
    """Mark the plan as 'draft' or 'final'."""
    execute("UPDATE plan SET status = ?", (status,))
