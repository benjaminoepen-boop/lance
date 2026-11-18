"""LN R18 and scenario A12: what a shared rank list must look like to count.

Real numbers used here (seed/cutoffs.csv, the rank lists of one account in Fall 2026):
Introduction to Programming 2477-S1: a seat took 120 in TXA, 115.5 in TXB (72 seats, 298 bids) and 109 in TXC;
the lowest winning bid in the course is 100. Banking 2206-S1 has one section, TXA, and no past price yet.
"""
import json

import pytest

import db

ROWS = [{"final": 120.0, "bid": 120, "allocated": True}, {"final": 110.0, "bid": 100, "allocated": True},
        {"final": 90.0, "bid": 90, "allocated": False}, {"final": 0.0, "bid": 0, "allocated": False}]
BANKING = {"code": "2206", "term": "S1", "section": "TXA", "list": "primary", "seats": 2, "year": "2026/2027", "rows": ROWS}


def share(client, *lists, **beside):
    """Send an export the way share.js does. json.dumps writes Infinity and NaN, as a made-up export could."""
    export = json.dumps({"lists": list(lists), **beside})
    return client.post("/api/share", data=json.dumps({"export": export}), content_type="application/json")


def banking_rows():
    return [row for row in db.load_cutoffs("2206") if row["section"] == "TXA"]


# ---------- only the three numbers per row, nothing beside them (LN R9) ----------

@pytest.mark.parametrize("column", ["Ects Sum", "ECTS Sum", "Student Number", "student number", "Student ", "Aluno",
                                    "E-mail", "Nome", "id"])
def test_a_row_may_carry_only_final_bid_and_allocated(client, column):
    # "Ects Sum" is what the platform calls the ECTS column: a list with it, or any other column, is refused whole
    rows = ROWS + [{"final": 1.0, "bid": 1, "allocated": False, column: "51234"}]
    response = share(client, dict(BANKING, rows=rows))
    assert response.status_code == 400
    assert "personal" in response.get_json()["error"]
    assert banking_rows() == []


def test_a_list_and_an_export_carry_nothing_beside_the_rank_list(client):
    assert share(client, dict(BANKING, student="51234")).status_code == 400
    assert share(client, BANKING, student="51234").status_code == 400
    assert banking_rows() == []
    assert share(client, BANKING).get_json()["stored"] == 1


# ---------- whole, finite numbers in range ----------

def strict_json(text):
    """Read JSON as strictly as the browser does: Infinity and NaN are no JSON there."""
    def refuse(constant):
        raise ValueError(constant + " is not JSON")
    return json.loads(text, parse_constant=refuse)


@pytest.mark.parametrize("change", [{"bid": float("inf")}, {"bid": float("nan")}, {"bid": "120"}, {"bid": 120.5}, {"bid": 5001},
                                    {"bid": -1}, {"bid": True}, {"final": float("inf")}, {"final": float("nan")}, {"final": "90"},
                                    {"final": 5500.5}, {"final": -1.0}, {"allocated": "yes"}, {"allocated": 1}, {"bid": None}])
def test_a_row_holds_a_whole_bid_and_a_finite_rank_value_in_range(client, change):
    rows = [dict(ROWS[0], **change)] + ROWS[1:]
    assert share(client, dict(BANKING, rows=rows)).status_code == 400
    assert banking_rows() == []


def test_the_highest_bid_with_the_rank_bonus_is_taken(client):
    # LN R7: a bid of 5000 ranks with 5500 for a student with the bonus
    rows = [{"final": 5500.0, "bid": 5000, "allocated": True}] + ROWS[1:]
    assert share(client, dict(BANKING, rows=rows)).get_json()["stored"] == 1


def test_an_endless_bid_never_reaches_a_plan(client):
    # a single bid of Infinity used to make the planner of everyone with Banking unreadable for the browser
    share(client, dict(BANKING, rows=[{"final": 100.0, "bid": float("inf"), "allocated": True}]))
    client.post("/api/add", json={"section_id": "2206-S1-TXA"})
    state = strict_json(client.get("/api/state").get_data(as_text=True))["state"]
    assert state["items"][0]["analysis"]["lowest_in_course"] is None


@pytest.mark.parametrize("seats", [float("inf"), 10 ** 30, -5, 0, 401, 2.5, "2", True, None])
def test_seats_are_a_whole_number_from_1_to_400(client, seats):
    assert share(client, dict(BANKING, seats=seats)).status_code == 400
    assert banking_rows() == []


def test_an_alternate_list_may_have_no_seat_left(client):
    # the platform shows 0 vacancies when no seat was left for the alternate list, as for Family Business TXA in seed/
    empty = dict(BANKING, list="alternate", seats=0, rows=[dict(row, allocated=False) for row in ROWS])
    assert share(client, empty).get_json()["stored"] == 1


def test_a_list_has_at_most_1000_rows(client):
    assert share(client, dict(BANKING, rows=ROWS * 251)).status_code == 400
    assert banking_rows() == []
    assert share(client, dict(BANKING, rows=ROWS * 250)).get_json()["stored"] == 1


def test_a_share_holds_at_most_60_lists(client):
    assert share(client, *[BANKING] * 61).status_code == 400
    assert banking_rows() == []
    assert share(client, *[BANKING] * 60).status_code == 200
