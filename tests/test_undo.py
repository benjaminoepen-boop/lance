"""LN R19, scenario A13: the left arrow takes back the last change to the semester on show, the right arrow does it again.

Expected, from docs/product-brief.md: a change is adding, removing a section or a course, the Undo after a removal,
switching a section, a bid, moving within or between lists, Reset and the example. Programme, semester, typed points
and the bonus are settings, not changes. The server keeps the last 50 changes of each semester of a plan; a new change
drops what could be done again; a step never touches the other semester or another plan.

Real timetable used here: Introduction to Programming 2477-S1 has TXA, TXB and TXC, Impact Investments is 2277-T2,
Family Business 2416-T1. Advanced Strategy 2459-S1 is mandatory for Management and an elective for Finance.
"""
import re

import db
import logic


def state_of(client):
    return client.get("/api/state").get_json()["state"]


def undo(client):
    return client.post("/api/undo", json={}).get_json()


def redo(client):
    return client.post("/api/redo", json={}).get_json()


def entries(state):
    """What the student sees of each entry: its section, list, place and bid."""
    return [(item["section_id"], item["list"], item["position"], item["bid"]) for item in state["items"]]


def bids(state):
    return [item["bid"] for item in state["items"]]


# ---------- nothing to do ----------

def test_a_new_plan_has_nothing_to_undo_and_settings_are_no_change(client):
    # the client has chosen a programme and typed its points already; the bonus and the semester are settings as well
    client.post("/api/settings", json={"has_bonus": True})
    client.post("/api/settings", json={"semester": "Spring"})
    state = client.post("/api/settings", json={"semester": "Fall"}).get_json()["state"]
    assert state["can_undo"] is False and state["can_redo"] is False


def test_nothing_to_undo_or_redo_is_said_in_words(client):
    answer = undo(client)
    assert answer["error"] == "Nothing to undo."
    assert answer["state"]["items"] == []
    assert redo(client)["error"] == "Nothing to redo."


# ---------- every kind of change can be taken back ----------

def test_undo_takes_back_an_added_course_and_redo_brings_it_back(client):
    added = client.post("/api/add", json={"offering_id": "2477-S1"}).get_json()["state"]
    assert added["can_undo"] is True and added["can_redo"] is False
    answer = undo(client)
    assert answer["error"] is None
    assert answer["state"]["items"] == []
    assert answer["state"]["can_undo"] is False and answer["state"]["can_redo"] is True
    answer = redo(client)
    assert answer["error"] is None
    assert entries(answer["state"]) == [("2477-S1-TXA", "primary", 1, None)]
    # the same entry comes back, so the course keeps its colour: Lance.colourOf goes by the entry's id
    assert answer["state"]["items"][0]["id"] == added["items"][0]["id"]
    assert answer["state"]["can_undo"] is True and answer["state"]["can_redo"] is False


def test_undo_takes_back_a_switch_with_its_bid(client):
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    client.post("/api/bid", json={"offering_id": "2477-S1", "bid": 120})
    client.post("/api/switch", json={"section_id": "2477-S1-TXC"})
    assert entries(undo(client)["state"]) == [("2477-S1-TXB", "primary", 1, 120)]
    assert entries(redo(client)["state"]) == [("2477-S1-TXC", "primary", 1, 120)]


def test_undo_takes_back_a_bid_on_a_course_and_on_one_section(client):
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    client.post("/api/add", json={"section_id": "2477-S1-TXA"})
    client.post("/api/bid", json={"offering_id": "2477-S1", "bid": 120})
    backup = state_of(client)["items"][1]
    client.post("/api/bid", json={"item_id": backup["id"], "bid": 100})
    assert bids(undo(client)["state"]) == [120, 120]
    assert bids(undo(client)["state"]) == [None, None]
    assert bids(redo(client)["state"]) == [120, 120]


def test_undo_takes_back_a_move_within_and_between_lists(client):
    for section in ("2477-S1-TXB", "2277-T2-TXB"):
        client.post("/api/add", json={"section_id": section})
    impact = next(item for item in state_of(client)["items"] if item["offering_id"] == "2277-T2")
    client.post("/api/move", json={"item_id": impact["id"], "direction": "up"})
    client.post("/api/move", json={"item_id": impact["id"], "list": "alternate"})
    assert entries(undo(client)["state"]) == [("2277-T2-TXB", "primary", 1, None), ("2477-S1-TXB", "primary", 2, None)]
    assert entries(undo(client)["state"]) == [("2477-S1-TXB", "primary", 1, None), ("2277-T2-TXB", "primary", 2, None)]


def test_undo_takes_back_a_removal_and_the_undo_after_it(client):
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    client.post("/api/bid", json={"offering_id": "2477-S1", "bid": 90})
    removed = client.post("/api/remove", json={"offering_id": "2477-S1"}).get_json()["removed"]
    client.post("/api/restore", json={"rows": removed})      # the Undo in the toast (LN R15) is a change as well
    assert undo(client)["state"]["items"] == []               # takes back that Undo
    assert entries(undo(client)["state"]) == [("2477-S1-TXB", "primary", 1, 90)]   # takes back the removal


def test_undo_brings_back_a_section_removed_alone(client):
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    client.post("/api/add", json={"section_id": "2477-S1-TXA"})
    backup = state_of(client)["items"][1]
    client.post("/api/remove", json={"item_id": backup["id"]})
    assert [item["section_id"] for item in undo(client)["state"]["items"]] == ["2477-S1-TXB", "2477-S1-TXA"]


def test_undo_takes_back_reset_with_every_bid_and_place(client):
    for section in ("2459-S1-TXC", "2477-S1-TXB", "2477-S1-TXA", "2277-T2-TXB"):
        client.post("/api/add", json={"section_id": section})
    client.post("/api/bid", json={"offering_id": "2477-S1", "bid": 90})
    before = state_of(client)
    assert client.post("/api/start-over", json={}).get_json()["state"]["items"] == []
    after = undo(client)["state"]
    assert entries(after) == entries(before)
    assert [item["id"] for item in after["items"]] == [item["id"] for item in before["items"]]


def test_undo_takes_back_the_example_and_leaves_the_settings(client):
    client.post("/api/settings", json={"programme": "Finance", "points": 100})
    assert len(client.post("/api/example", json={}).get_json()["state"]["items"]) == 11
    state = undo(client)["state"]
    assert state["items"] == []
    # the example chose Management and 165 points: settings, so they stay
    assert state["plan"]["programme"] == "Management" and state["plan"]["points"] == 165


def test_points_typed_after_a_change_stay_when_it_is_taken_back(client):
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    client.post("/api/settings", json={"points": 200, "has_bonus": True})
    state = undo(client)["state"]
    assert state["items"] == []
    assert state["plan"]["points"] == 200 and state["plan"]["has_bonus"] == 1
    assert state["can_undo"] is False


def test_a_course_that_comes_back_takes_the_list_its_programme_gives_it(client):
    # Advanced Strategy is mandatory in Management, an elective in Finance (test_a_new_programme_changes_what_is_mandatory)
    client.post("/api/add", json={"section_id": "2459-S1-TXC"})
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    client.post("/api/settings", json={"programme": "Finance"})
    state = undo(client)["state"]
    assert [(item["section_id"], item["list"]) for item in state["items"]] == [("2459-S1-TXC", "primary")]


def test_a_refused_change_leaves_no_step(client):
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    assert "cannot exceed" in client.post("/api/bid", json={"offering_id": "2477-S1", "bid": 99999}).get_json()["error"]
    assert client.post("/api/add", json={"section_id": "2477-S1-TXB"}).get_json()["error"] == "Already in your plan."
    answer = undo(client)
    assert answer["state"]["items"] == []           # one step back takes back the course itself
    assert answer["state"]["can_undo"] is False


def test_a_change_made_inside_another_is_one_step(plan):
    # switching to a section of a course that is not in the plan yet adds the course: one click, one step
    with logic.undoable(plan):
        assert logic.switch_section(plan, "2477-S1-TXC") is None
    assert logic.undo(plan) is None
    assert db.load_items(plan["id"]) == []
    assert logic.undo(plan) == "Nothing to undo."


# ---------- how far back, and what stays out of it ----------

def test_fifty_changes_can_be_taken_back_and_no_more(client):
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    for bid in range(1, 61):                          # 61 changes in all: the course and 60 bids
        client.post("/api/bid", json={"offering_id": "2477-S1", "bid": bid})
    for _ in range(50):
        assert undo(client)["error"] is None
    answer = undo(client)
    assert answer["error"] == "Nothing to undo."
    assert bids(answer["state"]) == [10]              # the oldest step kept: the plan before the bid of 11
    assert bids(redo(client)["state"]) == [11]


def test_a_new_change_drops_what_could_be_done_again(client):
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    client.post("/api/add", json={"section_id": "2277-T2-TXB"})
    assert undo(client)["state"]["can_redo"] is True
    state = client.post("/api/add", json={"section_id": "2416-T1-TXA"}).get_json()["state"]
    assert state["can_redo"] is False
    answer = redo(client)
    assert answer["error"] == "Nothing to redo."
    assert sorted(item["offering_id"] for item in answer["state"]["items"]) == ["2416-T1", "2477-S1"]


def test_undo_in_one_semester_leaves_the_other_alone(client):
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})                     # fall
    client.post("/api/settings", json={"semester": "Spring"})
    spring = client.post("/api/add", json={"offering_id": "2477-S2"}).get_json()["state"]
    plan_id = spring["plan"]["id"]
    assert spring["can_undo"] is True
    assert undo(client)["state"]["items"] == []
    assert [item["offering_id"] for item in db.load_items(plan_id)] == ["2477-S1"]  # the fall entry is still there
    assert undo(client)["error"] == "Nothing to undo."                              # the fall step is not the spring's
    fall = client.post("/api/settings", json={"semester": "Fall"}).get_json()["state"]
    assert fall["can_undo"] is True and fall["can_redo"] is False
    assert undo(client)["state"]["items"] == []
    client.post("/api/settings", json={"semester": "Spring"})
    assert [item["offering_id"] for item in redo(client)["state"]["items"]] == ["2477-S2"]
    assert [item["offering_id"] for item in db.load_items(plan_id)] == ["2477-S2"]  # the fall stays empty


def test_undo_never_touches_another_plan(client):
    import app as lance
    other = lance.app.test_client()
    other.post("/api/settings", json={"programme": "Management", "points": 165})
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    other.post("/api/add", json={"section_id": "2277-T2-TXB"})
    assert undo(other)["state"]["items"] == []
    assert [item["section_id"] for item in state_of(client)["items"]] == ["2477-S1-TXB"]
    assert undo(other)["error"] == "Nothing to undo."
    assert undo(client)["error"] is None
    assert state_of(other)["can_redo"] is True          # its own step forward is still there


def test_the_steps_survive_a_restart(client):
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    # a restart: everything held in memory is forgotten, only the database file remains
    logic.forget_catalogue()
    db.init_db()
    assert state_of(client)["can_undo"] is True
    assert undo(client)["state"]["items"] == []


def test_undo_and_redo_take_only_what_a_page_sends(client):
    assert client.post("/api/undo", data="x").status_code == 415
    assert client.post("/api/redo", data="x").status_code == 415


# ---------- the two arrows in the top bar ----------

def arrow(html, name):
    """The button of one arrow, as the page arrives."""
    found = re.search(rf'<button[^>]*id="{name}"[^>]*>', html)
    return found.group(0) if found else None


def test_the_arrows_are_on_the_pages_that_show_the_plan(client):
    for path in ("/", "/bids", "/course/2477-S1"):
        html = client.get(path).get_data(as_text=True)
        assert 'title="Undo"' in arrow(html, "undo") and 'aria-label="Undo"' in arrow(html, "undo"), path
        assert 'title="Redo"' in arrow(html, "redo") and 'aria-label="Redo"' in arrow(html, "redo"), path
        assert html.index('id="undo"') < html.index('id="redo"') < html.index(">Rules<"), path
    for path in ("/rules", "/nova", "/share"):
        assert arrow(client.get(path).get_data(as_text=True), "undo") is None, path


def test_an_arrow_is_switched_off_when_there_is_nothing_to_do(client):
    html = client.get("/").get_data(as_text=True)
    assert " disabled" in arrow(html, "undo") and " disabled" in arrow(html, "redo")
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    html = client.get("/bids").get_data(as_text=True)
    assert " disabled" not in arrow(html, "undo") and " disabled" in arrow(html, "redo")
