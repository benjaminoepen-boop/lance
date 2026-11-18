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
