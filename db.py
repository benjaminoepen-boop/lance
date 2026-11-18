"""The whole database layer: one SQLite file, data/lance.db. No rules live here, only reading and writing.

Two kinds of data, as in the course:
  content   what Nova publishes: courses, sections, sessions, exams. Rebuilt from seed/ whenever seed/ changes.
  progress  what people do here: plans, bids, the steps of undo and redo, shared price data. Never touched by a rebuild.
"""
import csv
import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SEED_DIR = os.path.join(HERE, "seed")
# The live database. Tests and deployments point this somewhere else.
DB_PATH = os.environ.get("LANCE_DB", os.path.join(HERE, "data", "lance.db"))

CONTENT_SCHEMA = """
CREATE TABLE offerings (
    id           TEXT PRIMARY KEY,   -- '2477-S1': a course in one term
    code         TEXT NOT NULL,
    name         TEXT NOT NULL,
    term         TEXT NOT NULL,      -- S1, T1, T2, S2, T3, T4
    semester     TEXT NOT NULL,      -- Fall or Spring
    ects         REAL NOT NULL,
    lecturers    TEXT NOT NULL,
    has_schedule INTEGER NOT NULL    -- 0 while Nova has not published the timetable
);
CREATE TABLE sections (
    id          TEXT PRIMARY KEY,    -- '2477-S1-TXB'
    offering_id TEXT NOT NULL REFERENCES offerings (id),
    section     TEXT NOT NULL,
    lecturers   TEXT NOT NULL,
    delivery    TEXT NOT NULL        -- 'on campus' or 'blended'
);
CREATE TABLE meetings (              -- the weekly pattern, for the week view
    section_id TEXT NOT NULL REFERENCES sections (id),
    day        TEXT NOT NULL,        -- Mon .. Fri
    start      TEXT NOT NULL,        -- 'HH:MM'
    end        TEXT NOT NULL,
    room       TEXT NOT NULL
);
CREATE TABLE sessions (              -- every single class with its date, for clash checks and the calendar file
    section_id TEXT NOT NULL REFERENCES sections (id),
    date       TEXT NOT NULL,        -- 'YYYY-MM-DD'
    start      TEXT NOT NULL,
    end        TEXT NOT NULL,
    room       TEXT NOT NULL,
    note       TEXT NOT NULL
);
CREATE TABLE exams (
    code  TEXT NOT NULL,
    term  TEXT NOT NULL,
    kind  TEXT NOT NULL,             -- exam, midterm, presentation, makeup, none
    date  TEXT NOT NULL,
    start TEXT NOT NULL,
    end   TEXT NOT NULL,
    name  TEXT NOT NULL,
    note  TEXT NOT NULL
);
CREATE TABLE programme_offerings (
    programme   TEXT NOT NULL,
    offering_id TEXT NOT NULL,
    kind        TEXT NOT NULL,       -- mandatory, elective, outside
    PRIMARY KEY (programme, offering_id)
);
CREATE TABLE calendar (
    key       TEXT PRIMARY KEY,
    first_day TEXT NOT NULL,
    last_day  TEXT NOT NULL,
    label     TEXT NOT NULL
);
CREATE TABLE syllabi (
    code       TEXT NOT NULL,
    term       TEXT NOT NULL,
    url        TEXT NOT NULL,
    synopsis   TEXT NOT NULL,
    assessment TEXT NOT NULL,
    weights    TEXT NOT NULL,        -- JSON: [{"label": "Final exam", "percent": 60}, ...]
    PRIMARY KEY (code, term)
);
CREATE TABLE course_ratings (         -- what students say on Uni Feedback, an independent review site
    code      TEXT PRIMARY KEY,
    rating    REAL NOT NULL,         -- the average of all reviews, 1 to 5
    reviews   INTEGER NOT NULL,      -- how many reviews the average rests on
    workload  TEXT NOT NULL,         -- Very light, Light, Moderate, Heavy, Very heavy
    source_id TEXT NOT NULL          -- the course's number on uni-feedback.com, for the link to its reviews
);
CREATE INDEX sessions_by_section ON sessions (section_id);
CREATE INDEX meetings_by_section ON meetings (section_id);
CREATE INDEX sections_by_offering ON sections (offering_id);
"""

PROGRESS_SCHEMA = """
CREATE TABLE IF NOT EXISTS plans (
    id         TEXT PRIMARY KEY,
    programme  TEXT NOT NULL,
    semester   TEXT NOT NULL,
    points     INTEGER NOT NULL,     -- the Balance the student typed; 0 while they have not (then LN R17 estimates)
    has_bonus  INTEGER NOT NULL,     -- 1 when the student expects the 10 % rank bonus
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS plan_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id     TEXT NOT NULL REFERENCES plans (id),
    offering_id TEXT NOT NULL,
    section_id  TEXT,                -- empty while the timetable is not published
    list        TEXT NOT NULL,       -- mandatory, primary, alternate
    position    INTEGER NOT NULL,    -- the order on the bidding list, 1 on top
    bid         INTEGER,             -- empty means no bid yet, 0 is a real bid
    UNIQUE (plan_id, offering_id, section_id)
);
CREATE INDEX IF NOT EXISTS items_by_plan ON plan_items (plan_id);
-- LN R19: what the arrows can go back and forth to. A step is a copy of the entries of one semester of one plan.
CREATE TABLE IF NOT EXISTS plan_steps (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,   -- the newest step has the highest id
    plan_id  TEXT NOT NULL REFERENCES plans (id),
    semester TEXT NOT NULL,                       -- Fall or Spring: each semester has steps of its own
    kind     TEXT NOT NULL,                       -- undo: the entries before a change; redo: what an undo took back
    entries  TEXT NOT NULL                        -- JSON: [{"id": 7, "offering_id": "2477-S1", "section_id": ..., "list": ..., "position": 1, "bid": 120}, ...]
);
CREATE INDEX IF NOT EXISTS steps_by_plan ON plan_steps (plan_id, semester, kind);
-- Past prices. Only totals per section: no row here can point to a student.
CREATE TABLE IF NOT EXISTS cutoffs (
    code           TEXT NOT NULL,
    term           TEXT NOT NULL,
    section        TEXT NOT NULL,
    round          TEXT NOT NULL,
    list           TEXT NOT NULL,
    seats          INTEGER NOT NULL,
    bids           INTEGER NOT NULL,
    allocated      INTEGER NOT NULL,
    min_rank_value REAL,
    max_rank_value REAL,
    min_bid        REAL,
    zero_bids      INTEGER NOT NULL,
    source         TEXT NOT NULL,
    PRIMARY KEY (code, term, section, round, list)
);
CREATE TABLE IF NOT EXISTS bid_histogram (
    code        TEXT NOT NULL,
    term        TEXT NOT NULL,
    section     TEXT NOT NULL,
    round       TEXT NOT NULL,
    list        TEXT NOT NULL,
    bucket_from INTEGER NOT NULL,
    bucket_to   INTEGER NOT NULL,
    bids        INTEGER NOT NULL,
    allocated   INTEGER NOT NULL,
    PRIMARY KEY (code, term, section, round, list, bucket_from)
);
"""

CONTENT_TABLES = ["offerings", "sections", "meetings", "sessions", "exams", "programme_offerings", "calendar", "syllabi",
                  "course_ratings"]


def connect():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = OFF")
    return connection


def rows_as_dicts(cursor):
    return [dict(row) for row in cursor.fetchall()]


# ---------- creating the database ----------

def read_seed(name):
    """Read one CSV file from seed/ and return its rows as a list of dicts. A missing file is no rows."""
    path = os.path.join(SEED_DIR, name + ".csv")
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def seed_fingerprint():
    """Changes whenever a file in seed/ changes, so the content is rebuilt exactly then."""
    digest = hashlib.sha256()
    for name in sorted(os.listdir(SEED_DIR)):
        if name.endswith(".csv"):
            with open(os.path.join(SEED_DIR, name), "rb") as file:
                digest.update(name.encode() + file.read())
    return digest.hexdigest()


def insert_rows(connection, table, rows):
    if not rows:
        return
    columns = list(rows[0].keys())
    marks = ", ".join("?" for _ in columns)
    connection.executemany(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({marks})",
                           [[row[column] for column in columns] for row in rows])


def init_db():
    """Create what is missing. Content is rebuilt when seed/ changed; progress always stays."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with closing(connect()) as connection:
        connection.executescript(PROGRESS_SCHEMA)
        connection.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        fingerprint = seed_fingerprint()
        row = connection.execute("SELECT value FROM meta WHERE key = 'seed'").fetchone()
        if row is None or row["value"] != fingerprint:
            load_content(connection)
            connection.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('seed', ?)", (fingerprint,))
        connection.commit()


def load_content(connection):
    for table in CONTENT_TABLES:
        connection.execute(f"DROP TABLE IF EXISTS {table}")
    connection.executescript(CONTENT_SCHEMA)
    for table in CONTENT_TABLES:
        insert_rows(connection, table, read_seed(table))
    # Past prices from seed/ are starting values: shared data with more bids must survive a rebuild.
    for row in read_seed("cutoffs"):
        row = {key: (None if value == "" else value) for key, value in row.items()}
        connection.execute("""
            INSERT INTO cutoffs (code, term, section, round, list, seats, bids, allocated, min_rank_value,
                                 max_rank_value, min_bid, zero_bids, source)
            VALUES (:code, :term, :section, :round, :list, :seats, :bids, :allocated, :min_rank_value,
                    :max_rank_value, :min_bid, :zero_bids, :source)
            ON CONFLICT (code, term, section, round, list) DO UPDATE SET
                seats = excluded.seats, bids = excluded.bids, allocated = excluded.allocated,
                min_rank_value = excluded.min_rank_value, max_rank_value = excluded.max_rank_value,
                min_bid = excluded.min_bid, zero_bids = excluded.zero_bids, source = excluded.source
            WHERE excluded.bids >= cutoffs.bids""", row)
    for row in read_seed("bid_histogram"):
        connection.execute("""
            INSERT OR IGNORE INTO bid_histogram (code, term, section, round, list, bucket_from, bucket_to, bids, allocated)
            VALUES (:code, :term, :section, :round, :list, :bucket_from, :bucket_to, :bids, :allocated)""", row)


# ---------- reading the content ----------

def load_offerings(semester=None):
    with closing(connect()) as connection:
        if semester:
            cursor = connection.execute("SELECT * FROM offerings WHERE semester = ? ORDER BY name", (semester,))
        else:
            cursor = connection.execute("SELECT * FROM offerings ORDER BY name")
        return rows_as_dicts(cursor)


def load_offering(offering_id):
    with closing(connect()) as connection:
        row = connection.execute("SELECT * FROM offerings WHERE id = ?", (offering_id,)).fetchone()
        return dict(row) if row else None


def load_offerings_by_code(code):
    with closing(connect()) as connection:
        return rows_as_dicts(connection.execute("SELECT * FROM offerings WHERE code = ? ORDER BY term", (code,)))


def load_sections(offering_id=None):
    with closing(connect()) as connection:
        if offering_id:
            return rows_as_dicts(connection.execute(
                "SELECT * FROM sections WHERE offering_id = ? ORDER BY section", (offering_id,)))
        return rows_as_dicts(connection.execute("SELECT * FROM sections ORDER BY offering_id, section"))


def load_section(section_id):
    with closing(connect()) as connection:
        row = connection.execute("SELECT * FROM sections WHERE id = ?", (section_id,)).fetchone()
        return dict(row) if row else None


def load_meetings():
    with closing(connect()) as connection:
        return rows_as_dicts(connection.execute("SELECT * FROM meetings ORDER BY section_id, day, start"))


def load_all_sessions():
    with closing(connect()) as connection:
        return rows_as_dicts(connection.execute("SELECT * FROM sessions ORDER BY date, start"))


def load_sessions(section_ids):
    if not section_ids:
        return []
    marks = ", ".join("?" for _ in section_ids)
    with closing(connect()) as connection:
        return rows_as_dicts(connection.execute(
            f"SELECT * FROM sessions WHERE section_id IN ({marks}) ORDER BY date, start", list(section_ids)))


def load_exams(code_term_pairs=None):
    with closing(connect()) as connection:
        rows = rows_as_dicts(connection.execute("SELECT * FROM exams ORDER BY date, start"))
    if code_term_pairs is None:
        return rows
    wanted = set(code_term_pairs)
    return [row for row in rows if (row["code"], row["term"]) in wanted]


def load_programme_kinds(programme):
    """{offering id: 'mandatory' | 'elective' | 'outside'} for one programme."""
    with closing(connect()) as connection:
        rows = connection.execute("SELECT offering_id, kind FROM programme_offerings WHERE programme = ?", (programme,)).fetchall()
    return {row["offering_id"]: row["kind"] for row in rows}


def load_programmes():
    with closing(connect()) as connection:
        rows = connection.execute("SELECT DISTINCT programme FROM programme_offerings ORDER BY programme").fetchall()
    return [row["programme"] for row in rows]


def load_calendar():
    with closing(connect()) as connection:
        return rows_as_dicts(connection.execute("SELECT * FROM calendar ORDER BY first_day"))


def load_syllabus(code, term):
    with closing(connect()) as connection:
        row = connection.execute("SELECT * FROM syllabi WHERE code = ? AND term = ?", (code, term)).fetchone()
    if row is None:
        return None
    syllabus = dict(row)
    syllabus["weights"] = json.loads(syllabus["weights"] or "[]")
    return syllabus


def load_all_syllabi():
    with closing(connect()) as connection:
        return rows_as_dicts(connection.execute("SELECT code, term, synopsis FROM syllabi"))


def load_course_ratings():
    with closing(connect()) as connection:
        return rows_as_dicts(connection.execute("SELECT * FROM course_ratings"))


# ---------- past prices ----------

def load_cutoffs(code=None):
    with closing(connect()) as connection:
        if code:
            cursor = connection.execute("SELECT * FROM cutoffs WHERE code = ? ORDER BY round, term, section", (code,))
        else:
            cursor = connection.execute("SELECT * FROM cutoffs ORDER BY code, term, section")
        return rows_as_dicts(cursor)


def load_histograms(code=None):
    with closing(connect()) as connection:
        if code:
            cursor = connection.execute("SELECT * FROM bid_histogram WHERE code = ? ORDER BY section, bucket_from", (code,))
        else:
            cursor = connection.execute("SELECT * FROM bid_histogram ORDER BY code, section, bucket_from")
        return rows_as_dicts(cursor)


def save_price_data(cutoff, histogram):
    """Store the totals of one shared rank list. A list with at least as many bids replaces an older one."""
    with closing(connect()) as connection:
        existing = connection.execute(
            "SELECT bids FROM cutoffs WHERE code = ? AND term = ? AND section = ? AND round = ? AND list = ?",
            (cutoff["code"], cutoff["term"], cutoff["section"], cutoff["round"], cutoff["list"])).fetchone()
        if existing is not None and existing["bids"] > cutoff["bids"]:
            return False
        connection.execute("""
            INSERT OR REPLACE INTO cutoffs (code, term, section, round, list, seats, bids, allocated, min_rank_value,
                                            max_rank_value, min_bid, zero_bids, source)
            VALUES (:code, :term, :section, :round, :list, :seats, :bids, :allocated, :min_rank_value,
                    :max_rank_value, :min_bid, :zero_bids, :source)""", cutoff)
        connection.execute("DELETE FROM bid_histogram WHERE code = ? AND term = ? AND section = ? AND round = ? AND list = ?",
                           (cutoff["code"], cutoff["term"], cutoff["section"], cutoff["round"], cutoff["list"]))
        for row in histogram:
            connection.execute("""
                INSERT INTO bid_histogram (code, term, section, round, list, bucket_from, bucket_to, bids, allocated)
                VALUES (:code, :term, :section, :round, :list, :bucket_from, :bucket_to, :bids, :allocated)""", row)
        connection.commit()
    return True


# ---------- plans: a visitor's progress ----------

def create_plan(programme, semester, points, has_bonus=False):
    plan_id = uuid.uuid4().hex
    with closing(connect()) as connection:
        connection.execute("INSERT INTO plans (id, programme, semester, points, has_bonus, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                           (plan_id, programme, semester, points, 1 if has_bonus else 0, now()))
        connection.commit()
    return plan_id


def load_plan(plan_id):
    with closing(connect()) as connection:
        row = connection.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
    return dict(row) if row else None


def update_plan(plan_id, programme, semester, points, has_bonus):
    with closing(connect()) as connection:
        connection.execute("UPDATE plans SET programme = ?, semester = ?, points = ?, has_bonus = ? WHERE id = ?",
                           (programme, semester, points, 1 if has_bonus else 0, plan_id))
        connection.commit()


def load_items(plan_id):
    with closing(connect()) as connection:
        return rows_as_dicts(connection.execute(
            "SELECT * FROM plan_items WHERE plan_id = ? ORDER BY list, position, id", (plan_id,)))


def load_item(item_id):
    with closing(connect()) as connection:
        row = connection.execute("SELECT * FROM plan_items WHERE id = ?", (item_id,)).fetchone()
    return dict(row) if row else None


def insert_item(plan_id, offering_id, section_id, list_name, position, bid=None):
    with closing(connect()) as connection:
        cursor = connection.execute(
            "INSERT INTO plan_items (plan_id, offering_id, section_id, list, position, bid) VALUES (?, ?, ?, ?, ?, ?)",
            (plan_id, offering_id, section_id, list_name, position, bid))
        connection.commit()
        return cursor.lastrowid


def delete_item(item_id):
    with closing(connect()) as connection:
        connection.execute("DELETE FROM plan_items WHERE id = ?", (item_id,))
        connection.commit()


def update_item(item_id, **fields):
    allowed = {"bid", "list", "position", "section_id"}
    assignments = ", ".join(f"{name} = ?" for name in fields if name in allowed)
    values = [value for name, value in fields.items() if name in allowed]
    with closing(connect()) as connection:
        connection.execute(f"UPDATE plan_items SET {assignments} WHERE id = ?", values + [item_id])
        connection.commit()


def replace_items(plan_id, old_ids, rows):
    """Take these entries out and put those in, each with its own id, so that a course keeps its colour.
    One transaction: if anything fails, nothing has changed."""
    with closing(connect()) as connection:
        connection.executemany("DELETE FROM plan_items WHERE id = ? AND plan_id = ?", [(item_id, plan_id) for item_id in old_ids])
        connection.executemany(
            "INSERT INTO plan_items (id, plan_id, offering_id, section_id, list, position, bid) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(row["id"], plan_id, row["offering_id"], row["section_id"], row["list"], row["position"], row["bid"]) for row in rows])
        connection.commit()


# ---------- steps: what the arrows go back and forth to (LN R19) ----------

def push_step(plan_id, semester, kind, entries, keep):
    """Save the entries of one semester as the newest step of its kind. Only the newest `keep` steps stay."""
    with closing(connect()) as connection:
        connection.execute("INSERT INTO plan_steps (plan_id, semester, kind, entries) VALUES (?, ?, ?, ?)",
                           (plan_id, semester, kind, json.dumps(entries)))
        connection.execute("""
            DELETE FROM plan_steps WHERE plan_id = ? AND semester = ? AND kind = ? AND id NOT IN (
                SELECT id FROM plan_steps WHERE plan_id = ? AND semester = ? AND kind = ? ORDER BY id DESC LIMIT ?)""",
                           (plan_id, semester, kind, plan_id, semester, kind, keep))
        connection.commit()


def pop_step(plan_id, semester, kind):
    """Take the newest step of its kind out and return its entries, or None when there is none."""
    with closing(connect()) as connection:
        row = connection.execute("SELECT id, entries FROM plan_steps WHERE plan_id = ? AND semester = ? AND kind = ? ORDER BY id DESC LIMIT 1",
                                 (plan_id, semester, kind)).fetchone()
        if row is None:
            return None
        connection.execute("DELETE FROM plan_steps WHERE id = ?", (row["id"],))
        connection.commit()
    return json.loads(row["entries"])


def clear_steps(plan_id, semester, kind):
    with closing(connect()) as connection:
        connection.execute("DELETE FROM plan_steps WHERE plan_id = ? AND semester = ? AND kind = ?", (plan_id, semester, kind))
        connection.commit()


def count_steps(plan_id, semester):
    """{'undo': how many steps back, 'redo': how many forward} for one semester of a plan."""
    with closing(connect()) as connection:
        rows = connection.execute("SELECT kind, COUNT(*) AS steps FROM plan_steps WHERE plan_id = ? AND semester = ? GROUP BY kind",
                                  (plan_id, semester)).fetchall()
    counts = {"undo": 0, "redo": 0}
    counts.update({row["kind"]: row["steps"] for row in rows})
    return counts


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
