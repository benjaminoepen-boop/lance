"""Scenario A1: two real bidding accounts from Fall 2026 must come out to the point.

Account one: 165 points. Programming 164 on all three sections, Impact Investments 1 on two sections,
alternate Fundamentals on Environment 33. The platform's log: Programming charged 132, Impact Investments
refunded, balance 33.

Account two: 218 points. Programming 130, Impact Investments 88. Charged 115 and 64, balance 39.
"""
import db
import logic
from conftest import add_all, bid_on


def test_first_account(plan):
    add_all(plan, "2477-S1-TXB", "2477-S1-TXA", "2477-S1-TXC", "2277-T2-TXB", "2277-T2-TXA")
    bid_on(plan, "2477-S1", 164)
    bid_on(plan, "2277-T2", 1)
    items = db.load_items(plan["id"])
    assert logic.reserved_points(items) == 165
    result = logic.forecast(plan, items)
    outcome = {row["offering_id"]: row for row in result["rows"]}
    assert outcome["2477-S1"]["status"] == "seat"
    assert outcome["2477-S1"]["section"] == "TXB"
    assert outcome["2477-S1"]["price"] == 132
    assert outcome["2277-T2"]["status"] == "no seat"
    assert result["left"] == 33


def test_second_account():
    plan = db.load_plan(db.create_plan("Management", "Fall", 218))
    add_all(plan, "2477-S1-TXC", "2277-T2-TXA")
    bid_on(plan, "2477-S1", 130)
    bid_on(plan, "2277-T2", 88)
    result = logic.forecast(plan, db.load_items(plan["id"]))
    outcome = {row["offering_id"]: row for row in result["rows"]}
    assert outcome["2477-S1"]["price"] == 115
    assert outcome["2277-T2"]["price"] == 64
    assert result["left"] == 39


def test_the_price_uses_the_lowest_winning_bid_of_the_whole_course():
    # In section TXB the lowest winning bid was 105, in TXC 100. The platform charged against 100.
    assert logic.lowest_bid_in_course("2477", "S1") == 100
