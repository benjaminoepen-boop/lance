"""The settings take only what the page sends: the bonus box says true or false, and points are whole.

Found in the Codex review of 23 Nov: {"points": 1.9, "has_bonus": "false"} was saved as one point with the bonus
switched on, because 1.9 was cut to 1 and any text counted as yes. The page itself sends the points as typed text and
the bonus as true or false, so nothing changes for it.

Expected: a bonus that is not true or false is refused with 400 and changes nothing; points with a fraction are refused
and change nothing; whole points count, also when they arrive as 120.0; no bonus sent keeps the saved one.
"""
import db


def plan_of(client):
    return db.load_plan(client.get_cookie("lance_plan").value)


def test_the_bonus_is_true_or_false_and_nothing_else(client):
    for wrong in ["false", "true", "", 1, 0, [], {}]:
        answer = client.post("/api/settings", json={"has_bonus": wrong})
        assert answer.status_code == 400, wrong
        assert plan_of(client)["has_bonus"] == 0, wrong
    assert client.post("/api/settings", json={"has_bonus": True}).status_code == 200
    assert plan_of(client)["has_bonus"] == 1


def test_no_bonus_sent_keeps_the_saved_one(client):
    client.post("/api/settings", json={"has_bonus": True})
    assert client.post("/api/settings", json={"points": 150}).status_code == 200
    assert plan_of(client)["has_bonus"] == 1 and plan_of(client)["points"] == 150


def test_points_with_a_fraction_are_refused_and_change_nothing(client):
    assert client.post("/api/settings", json={"points": 1.9}).status_code == 400
    assert plan_of(client)["points"] == 165
    answer = client.post("/api/settings", json={"points": "1.9"})
    assert answer.get_json()["error"] == "Points are a whole number."
    assert plan_of(client)["points"] == 165


def test_whole_points_count_also_as_a_whole_float(client):
    assert client.post("/api/settings", json={"points": 120.0}).status_code == 200
    assert plan_of(client)["points"] == 120
