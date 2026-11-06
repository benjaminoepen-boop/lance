"""LN R3 to R10: prices, points and limits."""
import db
import logic
from conftest import add_all, bid_on


# ---------- LN R1: the clash rule itself, inherited from Festival Architect ----------

def test_overlapping_slots_clash():
    assert logic.overlaps("16:00", "17:00", "16:30", "17:15")


def test_touching_slots_do_not_clash():
    assert not logic.overlaps("16:00", "17:00", "17:00", "18:00")


# ---------- LN R3 to R5: what a seat costs ----------

def test_primary_price_is_the_middle_of_bid_and_lowest_winning_bid():
    assert logic.price_primary(164, 100) == 132


def test_alternate_price_is_capped_by_the_balance():
    assert logic.price_alternate(50, 33) == 33
    assert logic.price_alternate(20, 33) == 20


def test_add_drop_price_is_the_full_bid():
    assert logic.price_add_drop(70) == 70


# ---------- LN R6: what bidding takes from the balance ----------

def test_several_sections_of_a_course_take_only_the_highest_bid(plan):
    add_all(plan, "2477-S1-TXA", "2477-S1-TXB", "2477-S1-TXC")
    items = db.load_items(plan["id"])
    logic.set_bid(plan, items[0]["id"], 100)
    logic.set_bid(plan, items[1]["id"], 130)
    logic.set_bid(plan, items[2]["id"], 90)
    assert logic.reserved_points(db.load_items(plan["id"])) == 130


def test_the_alternate_list_takes_nothing_while_bidding(plan):
    add_all(plan, "2652-S1-TXA")
    item = db.load_items(plan["id"])[0]
    logic.set_bid(plan, item["id"], 33)
    logic.move_item(plan, item["id"], list_name="alternate")
    assert logic.reserved_points(db.load_items(plan["id"])) == 0


# ---------- LN R7: the rank bonus ----------

def test_rank_value_with_and_without_bonus():
    assert logic.rank_value(210, True) == 231.0
    assert logic.rank_value(210, False) == 210.0


def test_suggested_bid_beats_the_cutoff_by_the_chosen_margin():
    assert logic.suggest_bid(115.5, False, "nice") == 116
    assert logic.suggest_bid(115.5, False, "want") == 128
    assert logic.suggest_bid(115.5, False, "must") == 145
    assert logic.suggest_bid(115.5, True, "nice") == 105
    assert logic.suggest_bid(None, False, "want") is None


# ---------- LN R10: empty is not zero, and a refused bid changes nothing ----------

def test_zero_is_a_bid_and_empty_is_none(plan):
    add_all(plan, "2477-S1-TXB")
    item = db.load_items(plan["id"])[0]
    assert logic.set_bid(plan, item["id"], 0) is None
    assert db.load_item(item["id"])["bid"] == 0
    assert logic.set_bid(plan, item["id"], "") is None
    assert db.load_item(item["id"])["bid"] is None


def test_refused_bids_leave_the_saved_bid_unchanged(plan):
    add_all(plan, "2477-S1-TXB")
    item = db.load_items(plan["id"])[0]
    logic.set_bid(plan, item["id"], 50)
    for bad in (-1, 166, "abc", 3.5):
        error = logic.set_bid(plan, item["id"], bad)
        assert error is not None
        assert db.load_item(item["id"])["bid"] == 50


def test_mandatory_courses_take_no_bid(plan):
    add_all(plan, "2459-S1-TXC")
    item = db.load_items(plan["id"])[0]
    assert item["list"] == "mandatory"
    assert logic.set_bid(plan, item["id"], 10) is not None


# ---------- LN R8: ECTS ----------

def test_a_course_counts_once_however_many_sections_are_listed(plan):
    add_all(plan, "2477-S1-TXA", "2477-S1-TXB")
    assert logic.ects_summary(db.load_items(plan["id"]))["total"] == 7


def test_more_than_the_maximum_is_flagged(plan):
    add_all(plan, "2477-S1-TXB", "2459-S1-TXC", "2581-S1-TXC", "2229-S1-TXG", "2206-S1-TXA")
    summary = logic.ects_summary(db.load_items(plan["id"]))
    assert summary["total"] == 35
    assert summary["over"] is True
    assert any("maximum" in warning["text"] for warning in logic.warnings_for(plan, db.load_items(plan["id"])))


def test_a_plan_cannot_hold_a_course_of_another_semester(plan):
    assert logic.add_to_plan(plan, offering_id="2477-S2") is not None
    assert db.load_items(plan["id"]) == []


def test_the_same_section_cannot_be_added_twice(plan):
    add_all(plan, "2477-S1-TXB")
    assert logic.add_to_plan(plan, section_id="2477-S1-TXB") is not None
    assert len(db.load_items(plan["id"])) == 1
