"""LN R16: without typed points, the points are an estimate from the mandatory courses in the plan."""
import pytest

import db
import logic


@pytest.fixture
def visitor():
    """A visitor who chose Management and has not typed any points."""
    import app as lance
    lance.app.config.update(TESTING=True)
    client = lance.app.test_client()
    client.post("/api/settings", json={"programme": "Management"})
    return client


def plan_of(client):
    return client.get("/api/state").get_json()["state"]["plan"]


def test_the_estimate_goes_through_the_two_reference_values():
    assert logic.estimated_points(20) == 140
    assert logic.estimated_points(23) == 120
    assert logic.estimated_points(21) == 133      # a third of the way down from 140 to 120


def test_more_mandatory_ects_mean_fewer_points_but_never_less_than_none():
    assert logic.estimated_points(17.5) > logic.estimated_points(24.5)
    assert logic.estimated_points(60) == 0


def test_without_mandatory_courses_there_is_no_estimate(visitor):
    assert logic.estimated_points(0) == 0
    visitor.post("/api/add", json={"offering_id": "2477-S1"})       # an elective
    plan = plan_of(visitor)
    assert plan["points"] == 0 and plan["points_estimated"] is False


def test_picking_mandatory_sections_fills_in_the_points(visitor):
    visitor.post("/api/add", json={"section_id": "2459-S1-TXC"})     # Advanced Strategy, 7 ECTS
    plan = plan_of(visitor)
    assert plan["points"] == logic.estimated_points(7) and plan["points_estimated"] is True
    for section in ("2581-S1-TXC", "2966-T1-TXC", "2463-T2-TXE"):     # 21 ECTS in all
        visitor.post("/api/add", json={"section_id": section})
    assert plan_of(visitor)["points"] == 133


def test_a_mandatory_course_counts_once_however_many_sections(visitor):
    visitor.post("/api/add", json={"section_id": "2459-S1-TXC"})
    visitor.post("/api/add", json={"section_id": "2459-S1-TXA"})
    assert plan_of(visitor)["points"] == logic.estimated_points(7)


def test_typed_points_beat_the_estimate_and_an_empty_field_brings_it_back(visitor):
    visitor.post("/api/add", json={"section_id": "2459-S1-TXC"})
    visitor.post("/api/settings", json={"points": 165})
    plan = plan_of(visitor)
    assert plan["points"] == 165 and plan["points_estimated"] is False
    visitor.post("/api/settings", json={"points": 0})
    plan = plan_of(visitor)
    assert plan["points"] == logic.estimated_points(7) and plan["points_estimated"] is True


def test_the_estimate_is_never_saved_as_if_it_had_been_typed(visitor):
    visitor.post("/api/add", json={"section_id": "2459-S1-TXC"})
    visitor.post("/api/settings", json={"semester": "Fall"})         # any setting that is not the points
    plan = plan_of(visitor)
    assert plan["points_estimated"] is True
    assert db.load_plan(plan["id"])["points"] == 0


def test_a_bid_is_checked_against_the_estimate(visitor):
    visitor.post("/api/add", json={"section_id": "2459-S1-TXC"})
    visitor.post("/api/add", json={"section_id": "2477-S1-TXB"})
    points = plan_of(visitor)["points"]
    assert visitor.post("/api/bid", json={"offering_id": "2477-S1", "bid": points}).get_json()["error"] is None
    assert "cannot exceed" in visitor.post("/api/bid", json={"offering_id": "2477-S1", "bid": points + 1}).get_json()["error"]


def test_start_over_and_undo_work_with_estimated_points(visitor):
    visitor.post("/api/add", json={"section_id": "2459-S1-TXC"})
    visitor.post("/api/add", json={"section_id": "2477-S1-TXB"})
    visitor.post("/api/bid", json={"offering_id": "2477-S1", "bid": 100})
    answer = visitor.post("/api/start-over", json={}).get_json()
    assert answer["state"]["items"] == [] and answer["state"]["plan"]["points"] == 0
    # the bid of 100 comes back together with the mandatory course that gives the points for it
    back = visitor.post("/api/restore", json={"rows": answer["removed"]}).get_json()
    assert back["error"] is None
    assert sorted(item["section_id"] for item in back["state"]["items"]) == ["2459-S1-TXC", "2477-S1-TXB"]
    assert [item["bid"] for item in back["state"]["items"] if item["offering_id"] == "2477-S1"] == [100]
