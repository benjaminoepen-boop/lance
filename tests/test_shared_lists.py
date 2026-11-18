"""LN R18 and scenario A12: what a shared rank list must look like to count.

Real numbers used here (seed/cutoffs.csv, the rank lists of one account in Fall 2026):
Introduction to Programming 2477-S1: a seat took 120 in TXA, 115.5 in TXB (72 seats, 298 bids) and 109 in TXC;
the lowest winning bid in the course is 100. Banking 2206-S1 has one section, TXA, and no past price yet.
"""
import json

import pytest

import db
import logic

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


# ---------- a section of the catalogue, from a round that is over ----------

@pytest.mark.parametrize("place", [{"code": "2477", "section": "TXZ"}, {"section": "Prof. X is unfair, student 51234"},
                                   {"section": "TXA <b>x</b>"}, {"section": "Z" * 1000}, {"code": "9999"}, {"code": "\uff12\uff12\uff10\uff16"},
                                   {"term": "T1"}, {"code": 2206}, {"section": ["TXA"]}, {"list": "secret"}])
def test_only_a_section_of_the_catalogue_counts(client, place):
    # LN R9: no free text about lecturers or students can reach the course sheet through the section's name
    before = db.load_cutoffs()
    assert share(client, dict(BANKING, **place)).status_code == 400
    assert db.load_cutoffs() == before


def test_a_made_up_section_cannot_change_what_programming_costs(client):
    # A1: 165 points, Programming TXB with 164 pays (164 + 100) / 2 = 132 and keeps 33
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    client.post("/api/bid", json={"offering_id": "2477-S1", "bid": 164})
    share(client, dict(BANKING, code="2477", section="TXD", seats=1, rows=[{"final": 0.0, "bid": 0, "allocated": True}]))
    forecast = client.get("/api/state").get_json()["state"]["forecast"]
    assert (forecast["rows"][0]["price"], forecast["left"]) == (132, 33)


def test_a_course_without_a_timetable_takes_the_section_names_nova_uses(client):
    spring = dict(BANKING, term="S2", year="2025/2026")
    assert share(client, dict(spring, section="TXZ")).status_code == 400
    assert share(client, spring).get_json()["stored"] == 1


@pytest.mark.parametrize("year", ["1999/2000", "0000/0001", "2024/2025", "2027/2028", "2026/2028", "2026", "2026/2027/2028",
                                  "abc", "", "\uff12\uff10\uff12\uff16/\uff12\uff10\uff12\uff17", None, 2026])
def test_only_a_round_that_is_over_counts(client, year):
    assert share(client, dict(BANKING, year=year)).status_code == 400
    assert banking_rows() == []


def test_the_rounds_that_are_over_come_from_the_calendar():
    # the calendar holds 2026/2027: the fall round was in July 2026, the spring round is from 18 to 20 January 2027
    assert logic.shared_rounds(today="2026-11-18") == {"Fall 2025", "Spring 2026", "Fall 2026"}
    assert logic.shared_rounds(today="2027-01-21") == {"Fall 2025", "Spring 2026", "Fall 2026", "Spring 2027"}


def test_made_up_years_cannot_blow_up_a_course_sheet(client):
    # every year used to add a round, and every price row drew the bars of all of them
    lists = [dict(BANKING, code="2477", year=f"{year}/{year + 1}", rows=ROWS * 5) for year in range(1960, 2020)]
    assert share(client, *lists).status_code == 400
    assert len(client.get("/api/sheet/2477-S1").get_data()) < 100_000


# ---------- the lists Lance read from a real account stay ----------

def test_a_shared_list_never_replaces_a_list_from_our_own_account(client):
    # 299 made-up bids for Programming TXB, five winning at 240 and up: one more than our own list of 298
    rows = [{"final": 240.0 + n, "bid": 240, "allocated": True} for n in range(5)] + [{"final": 10.0, "bid": 10, "allocated": False}] * 294
    assert share(client, dict(BANKING, code="2477", section="TXB", seats=72, rows=rows)).get_json()["stored"] == 0
    row = next(r for r in db.load_cutoffs("2477") if r["section"] == "TXB")
    assert (row["min_rank_value"], row["seats"], row["bids"], row["source"]) == (115.5, 72, 298, "rank list, one account")
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    client.post("/api/bid", json={"offering_id": "2477-S1", "bid": 164})
    forecast = client.get("/api/state").get_json()["state"]["forecast"]
    assert (forecast["rows"][0]["status"], forecast["rows"][0]["price"], forecast["left"]) == ("seat", 132, 33)


def test_a_shared_list_still_replaces_a_shorter_shared_one(client):
    # A8 stays as it was between shared lists
    share(client, dict(BANKING, rows=ROWS[:2]))
    assert share(client, BANKING).get_json()["stored"] == 1
    assert banking_rows()[0]["bids"] == 4
