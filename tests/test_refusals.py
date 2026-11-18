"""What Lance refuses, and the edges around it: every answer names what was wrong, and nothing changes.

Written after measuring which lines the other test files reach (docs/tests.md): none of these ran in a test before.
"""
import db
import logic
from conftest import add_all, bid_on


def items_of(plan):
    return db.load_items(plan["id"])


# ---------- adding and removing ----------

def test_a_section_or_course_that_does_not_exist_is_refused(plan):
    assert logic.add_to_plan(plan, section_id="2477-S1-TXZ") == "Unknown section."
    assert logic.add_to_plan(plan, offering_id="0000-S1") == "Unknown course."
    assert items_of(plan) == []


def test_one_section_can_be_taken_out_alone(plan):
    add_all(plan, "2477-S1-TXB", "2477-S1-TXA")
    backup = next(item for item in items_of(plan) if item["section_id"] == "2477-S1-TXA")
    assert logic.remove_from_plan(plan, backup["id"]) is None
    assert [item["section_id"] for item in items_of(plan)] == ["2477-S1-TXB"]


def test_nobody_removes_or_moves_an_entry_of_another_plan(plan):
    add_all(plan, "2477-S1-TXB")
    entry = items_of(plan)[0]
    stranger = db.load_plan(db.create_plan("Management", "Fall", 165))
    assert logic.remove_from_plan(stranger, entry["id"]) == "This entry is not in your plan."
    assert logic.move_item(stranger, entry["id"], list_name="alternate") == "This entry is not in your plan."
    assert items_of(plan) == [entry]


def test_an_entry_cannot_move_to_a_list_that_does_not_exist(plan):
    add_all(plan, "2477-S1-TXB")
    entry = items_of(plan)[0]
    assert logic.move_item(plan, entry["id"], list_name="waiting") == "Unknown list."
    assert items_of(plan) == [entry]


# ---------- undo: the rows come from the browser, so each one is checked ----------

ROW = {"offering_id": "2477-S1", "section_id": "2477-S1-TXB", "list": "primary", "position": 1, "bid": 10}


def test_undo_refuses_rows_that_are_not_rows(plan):
    assert logic.restore_items(plan, []) == "Nothing to put back."
    assert logic.restore_items(plan, ["2477-S1"]) == "Nothing to put back."


def test_undo_refuses_a_section_of_another_course(plan):
    assert logic.restore_items(plan, [dict(ROW, section_id="2277-T2-TXB")]) == "Unknown section."


def test_undo_refuses_a_place_that_is_not_a_number(plan):
    assert logic.restore_items(plan, [dict(ROW, position="first")]) == "Unknown place."


def test_undo_refuses_a_bid_above_the_points(plan):
    assert logic.restore_items(plan, [dict(ROW, bid=166)]) == "A bid cannot exceed your 165 points."
    assert logic.restore_items(plan, [dict(ROW, bid=-1)]) == "A bid cannot exceed your 165 points."


def test_undo_refuses_a_course_that_is_already_back(plan):
    add_all(plan, "2477-S1-TXA")
    assert logic.restore_items(plan, [ROW]) == "Already in your plan."
    assert [item["section_id"] for item in items_of(plan)] == ["2477-S1-TXA"]


def test_nothing_of_a_refused_undo_is_saved(plan):
    # the second row is wrong: the first, correct one must not be saved either
    assert logic.restore_items(plan, [ROW, dict(ROW, offering_id="2277-T2", section_id="2277-T2-TXB", list="secret")]) == "Unknown list."
    assert items_of(plan) == []


# ---------- settings ----------

def test_settings_refuse_an_unknown_semester_and_points_that_are_no_number(plan):
    assert logic.update_settings(plan, "Management", "Summer", 165, False) == "Unknown semester."
    assert logic.update_settings(plan, "Management", "Fall", "many", False) == "Points are a whole number."
    assert logic.update_settings(plan, "Management", "Fall", -1, False) == "Points must be between 0 and 2000."
    assert logic.update_settings(plan, "Management", "Fall", 2001, False) == "Points must be between 0 and 2000."
    assert db.load_plan(plan["id"])["points"] == 165


def test_an_elective_becomes_mandatory_when_the_new_programme_says_so(plan):
    # Corporate Finance is an elective in Management and mandatory in Finance
    add_all(plan, "2253-S1-TXA")
    assert items_of(plan)[0]["list"] == "primary"
    assert logic.update_settings(plan, "Finance", "Fall", 165, False) is None
    assert items_of(plan)[0]["list"] == "mandatory"


# ---------- what the last step warns about ----------

def test_bids_without_points_are_named_before_going_to_nova():
    plan = db.load_plan(db.create_plan("Management", "Fall", 0))
    add_all(plan, "2477-S1-TXB")
    texts = [warning["text"] for warning in logic.warnings_for(plan, items_of(plan))]
    assert "Enter your points: they are the Balance on Nova's platform." in texts


def test_bids_that_hold_more_than_the_points_are_named(plan):
    add_all(plan, "2477-S1-TXB", "2277-T2-TXB")
    bid_on(plan, "2477-S1", 100)
    bid_on(plan, "2277-T2", 60)
    # the balance turned out smaller than planned: the bids stay, the warning names both numbers
    logic.update_settings(plan, "Management", "Fall", 150, False)
    smaller = db.load_plan(plan["id"])
    texts = [warning["text"] for warning in logic.warnings_for(smaller, items_of(plan))]
    assert "Your primary bids hold 160 points, you have 150." in texts


# ---------- shared rank lists: what does not look like one is refused whole ----------

LIST = {"code": "2206", "term": "S1", "section": "TXA", "list": "primary", "seats": 2,
        "rows": [{"final": 120.0, "bid": 120, "allocated": True}, {"final": 90.0, "bid": 90, "allocated": False}]}


def test_a_rank_list_without_course_term_or_section_is_refused():
    assert logic.read_rank_list(dict(LIST, code="Programming")) == (None, "Course, term or section is missing.")
    assert logic.read_rank_list(dict(LIST, term="Q1")) == (None, "Course, term or section is missing.")
    assert logic.read_rank_list(dict(LIST, section="")) == (None, "Course, term or section is missing.")


def test_a_rank_list_of_an_unknown_list_or_without_rows_is_refused():
    assert logic.read_rank_list(dict(LIST, list="waiting")) == (None, "Unknown list.")
    assert logic.read_rank_list(dict(LIST, rows=[])) == (None, "The rank list is empty.")


def test_a_rank_list_with_a_row_that_cannot_be_read_is_refused():
    broken = "A row of the rank list could not be read."
    assert logic.read_rank_list(dict(LIST, rows=[{"final": "high", "bid": 1, "allocated": True}])) == (None, broken)
    assert logic.read_rank_list(dict(LIST, rows=[{"final": 100.0, "allocated": True}])) == (None, broken)
    assert logic.read_rank_list(dict(LIST, rows=[{"final": -5.0, "bid": 1, "allocated": True}])) == (None, broken)
    assert logic.read_rank_list(dict(LIST, rows=[{"final": 5001.0, "bid": 1, "allocated": True}])) == (None, broken)


def test_one_rank_list_alone_is_stored_like_an_export_with_one_list():
    assert logic.share_rank_lists(LIST) == (1, None)
    assert logic.share_rank_lists({"lists": []}) == (0, "This does not look like a rank list from the export.")
    assert [row["bids"] for row in db.load_cutoffs("2206") if row["section"] == "TXA" and row["list"] == "primary"] == [2]


# ---------- LN R13: a backup and an alternate report a midterm in their own row ----------

def conflicts_of(plan, section_id):
    return next(item["conflicts"] for item in logic.state_of(plan)["items"] if item["section_id"] == section_id)


def test_a_backup_that_meets_during_a_midterm_of_the_week_says_so(plan):
    # Banking has a midterm on Fri 9 Oct at 8:00. Investments TXB has class then, TXA has not.
    add_all(plan, "2206-S1-TXA", "2229-S1-TXA", "2229-S1-TXB")
    assert conflicts_of(plan, "2229-S1-TXA") == []
    assert conflicts_of(plan, "2229-S1-TXB") == [{"level": "midterm", "text": "Meets during the midterm of Banking."}]
    # it is said in the row of the backup and is not a clash of the week
    assert logic.state_of(plan)["clashes"] == []


def test_an_alternate_that_meets_during_a_midterm_says_that_nova_does_not_check_it(plan):
    add_all(plan, "2206-S1-TXA")
    assert logic.add_to_plan(plan, section_id="2229-S1-TXB", list_name="alternate") is None
    assert conflicts_of(plan, "2229-S1-TXB") == [{"level": "midterm", "text": "Midterm clash with Banking. Nova does not check this."}]


# ---------- dates ----------

def test_a_date_belongs_to_one_half_of_the_semester():
    assert logic.week_of("2026-10-21") == "T1"
    assert logic.week_of("2026-10-22") == "T2"
    assert logic.week_of("2027-03-31") == "T3"
    assert logic.week_of("2027-04-01") == "T4"


def test_after_the_last_window_there_is_no_next_deadline():
    assert logic.next_deadline("2026-09-01")["label"]
    assert logic.next_deadline("2030-01-01") is None


def test_a_bidding_round_is_upcoming_open_or_closed():
    assert logic.round_of("Spring", "2027-01-17")["status"] == "upcoming"
    assert logic.round_of("Spring", "2027-01-18")["status"] == "open"
    assert logic.round_of("Spring", "2027-01-21")["status"] == "closed"
    assert logic.semester_label("Spring", "2027-01-19") == "Spring · open now"
    # a semester the calendar does not know has no round, and its name stands alone
    assert logic.round_of("Summer") is None
    assert logic.semester_label("Summer") == "Summer"


def test_minutes_turn_back_into_a_clock_time():
    assert logic.to_clock(990) == "16:30"
    assert logic.to_clock(logic.to_minutes("09:05")) == "09:05"


# ---------- through the page ----------

def test_the_last_step_opens_with_the_private_link_and_the_list_for_nova(client):
    answer = client.post("/api/add", json={"section_id": "2477-S1-TXB"}).get_json()
    page = client.get("/nova")
    assert page.status_code == 200
    # the page carries the link that continues this plan on another device; the list itself is drawn from the state
    assert "/p/" + answer["state"]["plan"]["id"] in page.data.decode()
    assert "Introduction to Programming" in answer["state"]["platform_list"]


def test_a_link_to_a_plan_that_does_not_exist_is_a_404(client):
    assert client.get("/p/nobody").status_code == 404


def test_a_course_moves_to_the_alternate_list_through_the_page(client):
    answer = client.post("/api/add", json={"section_id": "2477-S1-TXB"}).get_json()
    item = answer["state"]["items"][0]
    moved = client.post("/api/move", json={"item_id": item["id"], "list": "alternate"}).get_json()
    assert moved["error"] is None
    assert moved["state"]["items"][0]["list"] == "alternate"
    refused = client.post("/api/move", json={"item_id": item["id"], "list": "waiting"}).get_json()
    assert refused["error"] == "Unknown list."
