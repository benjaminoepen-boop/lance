"""Scenarios A5 to A8, through the same requests the browser sends."""
import json

import pytest

import db
import logic


def state_of(client):
    return client.get("/api/state").get_json()["state"]


def test_every_page_opens(client):
    for path in ("/", "/bids", "/rules", "/share", "/course/2477-S1", "/course/2477-S2", "/plan.ics"):
        assert client.get(path).status_code == 200, path


def test_an_unknown_course_is_a_404(client):
    assert client.get("/course/does-not-exist").status_code == 404


def test_a_new_visitor_gets_a_plan_without_an_account(client):
    response = client.get("/")
    assert "lance_plan=" in response.headers["Set-Cookie"]
    assert "HttpOnly" in response.headers["Set-Cookie"]


# ---------- A5: accepted changes survive, refused ones change nothing ----------

def test_a_plan_survives_a_restart(client):
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    before = state_of(client)
    item = before["items"][0]
    client.post("/api/bid", json={"item_id": item["id"], "bid": 120})
    # a restart: everything held in memory is forgotten, only the database file remains
    logic.forget_catalogue()
    db.init_db()
    after = state_of(client)
    assert after["items"][0]["section_id"] == "2477-S1-TXB"
    assert after["items"][0]["bid"] == 120


def test_a_refused_bid_is_explained_and_changes_nothing(client):
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    item = state_of(client)["items"][0]
    client.post("/api/bid", json={"item_id": item["id"], "bid": 40})
    answer = client.post("/api/bid", json={"item_id": item["id"], "bid": 99999}).get_json()
    assert "cannot exceed" in answer["error"]
    assert answer["state"]["items"][0]["bid"] == 40


def test_one_visitor_cannot_touch_the_plan_of_another(client):
    import app as lance
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    item = state_of(client)["items"][0]
    stranger = lance.app.test_client()
    assert stranger.post("/api/remove", json={"item_id": item["id"]}).get_json()["error"]
    assert stranger.post("/api/bid", json={"item_id": item["id"], "bid": 1}).get_json()["error"]
    assert state_of(client)["items"][0]["bid"] is None


def test_a_plan_link_opens_the_same_plan_on_another_device(client):
    import app as lance
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    plan_id = state_of(client)["plan"]["id"]
    phone = lance.app.test_client()
    phone.get(f"/p/{plan_id}")
    assert state_of(phone)["items"][0]["section_id"] == "2477-S1-TXB"


def test_rebuilding_the_content_keeps_the_plans(client):
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    plan_id = state_of(client)["plan"]["id"]
    with db.connect() as connection:
        connection.execute("UPDATE meta SET value = 'old' WHERE key = 'seed'")
        connection.commit()
    db.init_db()
    logic.forget_catalogue()
    assert db.load_items(plan_id)[0]["section_id"] == "2477-S1-TXB"


def test_non_json_posts_are_refused(client):
    assert client.post("/api/add", data={"section_id": "2477-S1-TXB"}).status_code == 415


def test_spring_works_without_a_timetable(client):
    client.post("/api/settings", json={"semester": "Spring"})
    catalogue = client.get("/api/catalogue").get_json()
    assert catalogue and all(course["term"] in ("S2", "T3", "T4") for course in catalogue)
    answer = client.post("/api/add", json={"offering_id": "2477-S2"}).get_json()
    assert answer["error"] is None
    item = answer["state"]["items"][0]
    assert item["section_id"] is None
    # the fall prices of the same course show as a rough hint
    assert item["analysis"]["exact"] is False
    assert item["analysis"]["cutoff"] == 109


# ---------- A6: the calendar file ----------

def test_the_calendar_file_has_every_class_on_its_real_date(client):
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    body = client.get("/plan.ics").data.decode()
    assert body.count("BEGIN:VEVENT") == 13     # 12 classes and the exam
    assert "DTSTART;TZID=Europe/Lisbon:20261204T123000" in body
    assert "Make-up for 1 Dec" in body
    assert "DTSTART;TZID=Europe/Lisbon:20261219T173000" in body


def test_the_list_for_the_platform_keeps_the_order(client):
    for section in ("2477-S1-TXB", "2477-S1-TXA", "2277-T2-TXB"):
        client.post("/api/add", json={"section_id": section})
    state = state_of(client)
    for item in state["items"]:
        client.post("/api/bid", json={"item_id": item["id"], "bid": 10})
    text = state_of(client)["platform_list"]
    assert text.index("Introduction to Programming") < text.index("Impact Investments")
    assert "TXB 10, TXA 10" in text


# ---------- A8: shared price data keeps no personal data ----------

ROWS = [{"final": 120.0, "bid": 120, "allocated": True}, {"final": 110.0, "bid": 100, "allocated": True},
        {"final": 90.0, "bid": 90, "allocated": False}, {"final": 0.0, "bid": 0, "allocated": False}]
EXPORT = {"lists": [{"code": "2206", "term": "S1", "section": "TXA", "list": "primary", "seats": 2, "year": "2026/2027", "rows": ROWS}]}


def share(client, export):
    return client.post("/api/share", json={"export": json.dumps(export)})


def test_a_shared_rank_list_becomes_totals(client):
    answer = share(client, EXPORT).get_json()
    assert answer["stored"] == 1
    row = next(r for r in db.load_cutoffs("2206") if r["section"] == "TXA")
    assert row["round"] == "Fall 2026"
    assert (row["bids"], row["allocated"], row["min_rank_value"], row["min_bid"], row["zero_bids"]) == (4, 2, 110.0, 100, 1)


def test_rows_with_personal_columns_are_refused_whole(client):
    bad = {"lists": [dict(EXPORT["lists"][0], rows=ROWS + [{"final": 1, "bid": 1, "allocated": False, "student": "12345"}])]}
    response = share(client, bad)
    assert response.status_code == 400
    assert "personal" in response.get_json()["error"]
    assert not [r for r in db.load_cutoffs("2206") if r["section"] == "TXA"]


def test_no_table_can_hold_a_student_number():
    with db.connect() as connection:
        tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
        for table in tables:
            columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
            assert not set(columns) & {"student", "student_number", "ects_sum"}, table


def test_a_shorter_list_never_replaces_a_longer_one(client):
    share(client, EXPORT)
    shorter = {"lists": [dict(EXPORT["lists"][0], rows=ROWS[:2])]}
    assert share(client, shorter).get_json()["stored"] == 0
    assert next(r for r in db.load_cutoffs("2206") if r["section"] == "TXA")["bids"] == 4


def test_something_else_pasted_is_refused(client):
    assert client.post("/api/share", json={"export": "hello"}).status_code == 400
    assert share(client, {"lists": []}).status_code == 400
    assert share(client, {"lists": [{"code": "2206"}]}).status_code == 400


def test_a_rank_list_from_an_earlier_year_keeps_its_own_round(client):
    earlier = {"lists": [dict(EXPORT["lists"][0], term="S2", year="2025/2026")]}
    share(client, earlier)
    assert any(r["round"] == "Spring 2026" and r["term"] == "S2" for r in db.load_cutoffs("2206"))


def test_coverage_counts_only_this_semester(client):
    before = logic.coverage()["covered"]
    share(client, EXPORT)
    assert logic.coverage()["covered"] == before + 1


def test_the_bookmarklet_never_reads_a_personal_column():
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "share-bookmarklet.js")
    with open(path, encoding="utf-8") as file:
        code = file.read()
    assert "Ects Sum" not in code
    assert '"Student"' not in code and "data-student" not in code
    for wanted in ('"Final Bid"', '"Bid"', '"Alocated"'):
        assert wanted in code


# ---------- the example plan ----------

def test_the_example_plan_reproduces_a_real_result(client):
    answer = client.post("/api/example", json={}).get_json()
    assert answer["error"] is None
    state = answer["state"]
    assert state["reserved"] == 165
    assert state["forecast"]["expected"] == 132
    assert state["forecast"]["left"] == 33


def test_the_example_never_overwrites_a_plan(client):
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    assert client.post("/api/example", json={}).get_json()["error"]
    assert len(state_of(client)["items"]) == 1


# ---------- the semester menu ----------

def test_a_round_that_is_over_is_offered_as_practice(client):
    # The first-time user test (10 Nov): "Fall · closed" read as if Fall could not be chosen. Planning still works.
    import app as lance
    assert lance.semester_option("Fall", today="2026-11-07") == "Fall · practice"
    assert lance.semester_option("Spring", today="2026-11-07") == "Spring · opens 18 Jan"
    assert lance.semester_option("Spring", today="2027-01-19") == "Spring · open now"


# ---------- requests no page sends ----------

def test_a_body_larger_than_any_export_is_refused_unread(client):
    # a real export is a few hundred KB at most; three uploads of 47 MB once held 1.3 GB of memory
    response = client.post("/api/share", data=json.dumps({"export": "x" * 512 * 1024}), content_type="application/json")
    assert response.status_code == 413
    assert response.get_json()["error"]
    assert client.post("/api/restore", data=json.dumps({"rows": ["x" * 600 * 1024]}), content_type="application/json").status_code == 413
    assert share(client, EXPORT).status_code == 200


ROW = {"offering_id": "2477-S1", "section_id": None, "list": "primary", "position": 1, "bid": None}


@pytest.mark.parametrize("path, body", [
    ("/api/add", {"section_id": ["2477-S1-TXA"]}), ("/api/add", {"offering_id": {"a": 1}}),
    ("/api/switch", {"section_id": ["2477-S1-TXA"]}), ("/api/remove", {"item_id": []}), ("/api/remove", {"item_id": {"a": 1}}),
    ("/api/remove", {"offering_id": ["2477-S1"]}), ("/api/bid", {"item_id": 10 ** 30, "bid": 1}),
    ("/api/bid", {"offering_id": ["2477-S1"], "bid": 1}), ("/api/move", {"item_id": "\ud800", "direction": "up"}),
    ("/api/move", {"item_id": True, "direction": "down"}), ("/api/settings", {"points": float("inf")}),
    ("/api/settings", {"points": float("nan")}), ("/api/settings", {"programme": None}), ("/api/settings", {"programme": 0}),
    ("/api/restore", {"rows": [dict(ROW, offering_id=["2477-S1"])]}), ("/api/restore", {"rows": [dict(ROW, section_id=[])]}),
])
def test_a_value_of_the_wrong_kind_is_a_bad_request_not_a_crash(client, path, body):
    # lists or objects as ids, Infinity or NaN as points, no programme: no page sends that, so it is answered with 400
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    client.post("/api/add", json={"section_id": "2277-T2-TXA"})
    before = state_of(client)
    response = client.post(path, data=json.dumps(body), content_type="application/json")
    assert response.status_code == 400
    assert response.get_json()["error"]
    after = state_of(client)
    assert (after["plan"], after["items"]) == (before["plan"], before["items"])


@pytest.mark.parametrize("body", ["[1]", '"x"', "5", "true", "null", "[" * 100_000 + "]" * 100_000])
def test_a_share_that_is_not_an_object_is_refused_not_a_crash(client, body):
    response = client.post("/api/share", data=body, content_type="application/json")
    assert response.status_code == 400
    assert response.get_json()["error"]
    nested = client.post("/api/share", data=json.dumps({"export": body}), content_type="application/json")
    assert nested.status_code == 400


def test_brackets_nested_thousands_deep_are_refused_not_a_crash(client):
    deep = "[" * 100_000 + "]" * 100_000
    response = client.post("/api/add", data=deep, content_type="application/json")
    assert response.status_code == 415
    assert response.get_json()["error"]
