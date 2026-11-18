"""LN R11 to R15: the rules behind the simple flow (specs/simple-flow.md).

Real timetable used here:
Programming 2477-S1: TXA Tue 11:00, TXB Tue 12:30, TXC Tue 15:30.
Advanced Strategy 2459-S1: TXB Tue 11:00, TXF Thu 15:30 (mandatory for Management).
Impact Investments 2277-T2: TXA Wed 15:30-18:30, TXB Thu 15:30-18:30.
Fundamentals on Environment 2652-S1: TXA Wed 15:30-18:30.
Family Business 2416-T1: TXA Wed 08:00 and Fri 12:30. Advanced Financial Management 2581-S1: TXA Wed 08:00.
"""
import sqlite3

import db
import logic
from conftest import add_all, bid_on


def entries(plan, offering_id):
    rows = [item for item in db.load_items(plan["id"]) if item["offering_id"] == offering_id]
    return sorted(rows, key=lambda item: item["position"])


def sections_of(plan, offering_id):
    return [item["section_id"] for item in entries(plan, offering_id)]


# ---------- LN R11: adding a course without naming a section ----------

def test_adding_a_course_takes_its_first_section_in_an_empty_week(plan):
    assert logic.add_to_plan(plan, offering_id="2477-S1") is None
    assert sections_of(plan, "2477-S1") == ["2477-S1-TXA"]


def test_adding_a_course_skips_a_section_that_clashes_with_the_week(plan):
    add_all(plan, "2459-S1-TXB")   # Tuesday 11:00, the same as Programming TXA
    assert logic.add_to_plan(plan, offering_id="2477-S1") is None
    assert sections_of(plan, "2477-S1") == ["2477-S1-TXB"]


def test_adding_a_course_that_clashes_everywhere_takes_its_first_section(plan):
    add_all(plan, "2652-S1-TXA", "2459-S1-TXF")   # Wednesday and Thursday 15:30, both sections of Impact Investments
    assert logic.add_to_plan(plan, offering_id="2277-T2") is None
    assert sections_of(plan, "2277-T2") == ["2277-T2-TXA"]


def test_a_mandatory_course_is_not_guessed(plan):
    # Nova assigned the section, so Lance asks. Advanced Strategy is mandatory for Management.
    assert logic.add_to_plan(plan, offering_id="2459-S1") == "Pick the section Nova assigned you."
    assert logic.add_to_plan(plan, section_id="2459-S1-TXC") is None


def test_a_course_without_a_timetable_stays_without_a_section(plan):
    assert logic.add_to_plan(plan, offering_id="2784-S1") is None
    assert sections_of(plan, "2784-S1") == [None]


def test_adding_a_course_that_is_already_in_the_plan_is_refused(plan):
    add_all(plan, "2477-S1-TXC")
    assert logic.add_to_plan(plan, offering_id="2477-S1") == "Already in your plan."
    assert sections_of(plan, "2477-S1") == ["2477-S1-TXC"]


# ---------- LN R12: switching a section ----------

def test_switching_keeps_the_bid_the_list_and_the_position(plan):
    add_all(plan, "2277-T2-TXA", "2477-S1-TXB")
    bid_on(plan, "2477-S1", 120)
    before = entries(plan, "2477-S1")[0]
    assert logic.switch_section(plan, "2477-S1-TXC") is None
    after = entries(plan, "2477-S1")
    assert [item["section_id"] for item in after] == ["2477-S1-TXC"]
    assert after[0]["bid"] == 120
    assert after[0]["list"] == before["list"]
    assert after[0]["position"] == before["position"]


def test_switching_to_a_backup_makes_the_two_change_places(plan):
    add_all(plan, "2477-S1-TXB", "2477-S1-TXA")
    first, backup = entries(plan, "2477-S1")
    logic.set_bid(plan, first["id"], 100)
    logic.set_bid(plan, backup["id"], 80)
    assert logic.switch_section(plan, "2477-S1-TXA") is None
    after = entries(plan, "2477-S1")
    assert [item["section_id"] for item in after] == ["2477-S1-TXA", "2477-S1-TXB"]
    assert [item["bid"] for item in after] == [100, 80]   # the bids stay with the places


def test_switching_on_a_course_that_is_not_in_the_plan_adds_it(plan):
    assert logic.switch_section(plan, "2477-S1-TXC") is None
    assert sections_of(plan, "2477-S1") == ["2477-S1-TXC"]


def test_switching_to_an_unknown_section_is_refused(plan):
    assert logic.switch_section(plan, "nope") == "Unknown section."


# ---------- LN R13: what the week is ----------

def test_the_week_is_the_first_section_of_each_mandatory_and_primary_course(plan):
    add_all(plan, "2459-S1-TXC", "2477-S1-TXB", "2477-S1-TXA", "2652-S1-TXA")
    logic.move_item(plan, entries(plan, "2652-S1")[0]["id"], list_name="alternate")
    week = logic.week_items(db.load_items(plan["id"]))
    assert sorted(item["section_id"] for item in week) == ["2459-S1-TXC", "2477-S1-TXB"]


def test_a_backup_and_an_alternate_do_not_clash_with_the_week(plan):
    # Impact Investments TXA is only a backup; Fundamentals is only an alternate. They meet at the same time.
    add_all(plan, "2277-T2-TXB", "2277-T2-TXA", "2652-S1-TXA")
    logic.move_item(plan, entries(plan, "2652-S1")[0]["id"], list_name="alternate")
    assert logic.state_of(plan)["clashes"] == []


def test_a_backup_that_meets_with_the_week_says_so_in_its_own_row(plan):
    add_all(plan, "2459-S1-TXB", "2477-S1-TXB", "2477-S1-TXA")
    rows = {item["section_id"]: item for item in logic.state_of(plan)["items"]}
    assert [note["text"] for note in rows["2477-S1-TXA"]["conflicts"]] == ["Clashes with Advanced Strategy TXB"]
    assert rows["2477-S1-TXB"]["conflicts"] == []


def test_an_alternate_that_meets_with_the_week_says_so_in_its_own_row(plan):
    add_all(plan, "2277-T2-TXA", "2652-S1-TXA")
    logic.move_item(plan, entries(plan, "2652-S1")[0]["id"], list_name="alternate")
    rows = {item["section_id"]: item for item in logic.state_of(plan)["items"]}
    assert [note["text"] for note in rows["2652-S1-TXA"]["conflicts"]] == ["Clashes with Impact Investments TXA"]


def test_an_alternate_that_meets_a_backup_says_so(plan):
    # The real plan: Fundamentals is an alternate, Impact Investments TXA a backup. Wednesday 15:30, six times.
    add_all(plan, "2277-T2-TXB", "2277-T2-TXA", "2652-S1-TXA")
    logic.move_item(plan, entries(plan, "2652-S1")[0]["id"], list_name="alternate")
    rows = {item["section_id"]: item for item in logic.state_of(plan)["items"]}
    assert [note["text"] for note in rows["2652-S1-TXA"]["conflicts"]] == ["Clashes with Impact Investments TXA (if you land there)"]


def test_an_alternate_whose_exam_meets_the_week_says_nova_blocks_it(plan):
    # Nova: "The same happens with the courses placed on the Alternate List." Both exams are on Mon 7 Dec, 11:30.
    assert logic.add_to_plan(plan, section_id="2329-T2-TXA") is None
    assert logic.add_to_plan(plan, section_id="2388-T2-TXA", list_name="alternate") is None
    state = logic.state_of(plan)
    rows = {item["section_id"]: item for item in state["items"]}
    assert state["clashes"] == []
    levels = [note["level"] for note in rows["2388-T2-TXA"]["conflicts"]]
    assert "exam" in levels


def test_the_worst_clash_comes_first(plan):
    # Econometrics: its classes meet Advanced Strategy TXC, its exam meets Advanced Financial Management.
    add_all(plan, "2459-S1-TXC", "2581-S1-TXC", "2175-S1-TXA")
    kinds = [clash["kind"] for clash in logic.state_of(plan)["clashes"]]
    assert kinds[0] == "exam" and "class" in kinds


def test_two_courses_of_the_week_still_clash(plan):
    add_all(plan, "2459-S1-TXC", "2175-S1-TXA")
    state = logic.state_of(plan)
    assert len(state["clashes"]) == 1


def test_fits_my_week_looks_only_at_the_week(plan):
    add_all(plan, "2477-S1-TXB", "2477-S1-TXA")   # TXA, Tuesday 11:00, is only a backup
    per_section, _ = logic.section_warnings(db.load_items(plan["id"]), "Fall")
    assert "2459-S1-TXB" not in per_section       # Advanced Strategy TXB, Tuesday 11:00, fits the week


def test_the_calendar_file_holds_the_week_only(plan):
    # A student sits in the first section. A calendar with all three Programming sections would be useless.
    add_all(plan, "2477-S1-TXB", "2477-S1-TXA", "2652-S1-TXA")
    logic.move_item(plan, entries(plan, "2652-S1")[0]["id"], list_name="alternate")
    body = logic.calendar_file(plan)
    assert "Introduction to Programming TXB" in body
    assert "Introduction to Programming TXA" not in body
    assert "Fundamentals" not in body


def test_the_real_plan_has_no_clash_in_its_week(client):
    state = client.post("/api/example", json={}).get_json()["state"]
    assert state["clashes"] == []


# ---------- LN R14: a backup starts with the bid of the first section ----------

def test_a_backup_section_starts_with_the_bid_of_the_first(plan):
    add_all(plan, "2477-S1-TXB")
    bid_on(plan, "2477-S1", 150)
    assert logic.add_to_plan(plan, section_id="2477-S1-TXA") is None
    assert [item["bid"] for item in entries(plan, "2477-S1")] == [150, 150]
    assert logic.reserved_points(db.load_items(plan["id"])) == 150


def test_a_first_section_starts_without_a_bid(plan):
    add_all(plan, "2477-S1-TXB")
    assert entries(plan, "2477-S1")[0]["bid"] is None


# ---------- LN R15: removing, undoing, starting over ----------

def keep(rows):
    return [(row["offering_id"], row["section_id"], row["list"], row["position"], row["bid"]) for row in rows]


def test_removing_a_course_removes_all_its_sections(plan):
    add_all(plan, "2477-S1-TXB", "2477-S1-TXA", "2277-T2-TXB")
    removed, error = logic.remove_course(plan, "2477-S1")
    assert error is None
    assert len(removed) == 2
    assert sections_of(plan, "2477-S1") == []
    assert sections_of(plan, "2277-T2") == ["2277-T2-TXB"]


def test_removing_a_course_can_be_undone_with_its_bids_and_its_place(plan):
    add_all(plan, "2477-S1-TXB", "2477-S1-TXA", "2277-T2-TXB")
    bid_on(plan, "2477-S1", 90)
    logic.move_item(plan, entries(plan, "2277-T2")[0]["id"], direction="up")
    before = keep(sorted(db.load_items(plan["id"]), key=lambda row: row["position"]))
    removed, _ = logic.remove_course(plan, "2477-S1")
    assert logic.restore_items(plan, removed) is None
    assert keep(sorted(db.load_items(plan["id"]), key=lambda row: row["position"])) == before


def test_removing_a_course_that_is_not_in_the_plan_is_refused(plan):
    assert logic.remove_course(plan, "2477-S1") == ([], "This course is not in your plan.")


def test_restoring_nonsense_is_refused_and_changes_nothing(plan):
    rows = [{"offering_id": "nope", "section_id": None, "list": "primary", "position": 1, "bid": None}]
    assert logic.restore_items(plan, rows)
    assert logic.restore_items(plan, "hello")
    assert logic.restore_items(plan, [{"offering_id": "2477-S1", "section_id": "2477-S1-TXB", "list": "secret", "position": 1, "bid": None}])
    assert db.load_items(plan["id"]) == []


def test_start_over_empties_the_plan_and_keeps_the_settings(plan):
    add_all(plan, "2477-S1-TXB", "2277-T2-TXB")
    removed = logic.start_over(plan)
    assert [row["section_id"] for row in removed] == ["2477-S1-TXB", "2277-T2-TXB"]
    assert db.load_items(plan["id"]) == []
    assert db.load_plan(plan["id"])["programme"] == plan["programme"]


def test_start_over_can_be_undone_with_every_bid_and_place(plan):
    add_all(plan, "2459-S1-TXC", "2477-S1-TXB", "2477-S1-TXA", "2277-T2-TXB")
    bid_on(plan, "2477-S1", 90)
    before = keep(sorted(db.load_items(plan["id"]), key=lambda row: (row["list"], row["position"])))
    removed = logic.start_over(plan)
    assert logic.restore_items(plan, removed) is None
    assert keep(sorted(db.load_items(plan["id"]), key=lambda row: (row["list"], row["position"]))) == before


def test_start_over_leaves_the_other_semester_alone(plan):
    add_all(plan, "2477-S1-TXB")
    logic.update_settings(plan, plan["programme"], "Spring", plan["points"], False)
    spring = db.load_plan(plan["id"])
    assert logic.add_to_plan(spring, offering_id="2477-S2") is None
    assert [row["offering_id"] for row in logic.start_over(spring)] == ["2477-S2"]
    assert [item["offering_id"] for item in db.load_items(plan["id"])] == ["2477-S1"]


def test_the_same_click_twice_is_not_a_crash(plan, monkeypatch):
    # Two clicks can pass the check at the same time. The database refuses the second, the plan stays right.
    add_all(plan, "2477-S1-TXA")
    def already(*_):
        raise sqlite3.IntegrityError("UNIQUE constraint failed")
    monkeypatch.setattr(db, "insert_item", already)
    assert logic.add_to_plan(plan, section_id="2477-S1-TXB") == "Already in your plan."


def test_a_new_programme_changes_what_is_mandatory(plan):
    # Advanced Strategy is mandatory in Management, not in Finance. Corporate Finance is the other way round.
    add_all(plan, "2459-S1-TXC", "2652-S1-TXA")
    logic.move_item(plan, entries(plan, "2652-S1")[0]["id"], list_name="alternate")
    assert entries(plan, "2459-S1")[0]["list"] == "mandatory"
    assert logic.update_settings(plan, "Finance", "Fall", 165, False) is None
    assert entries(plan, "2459-S1")[0]["list"] == "primary"
    assert entries(plan, "2652-S1")[0]["list"] == "alternate"


def test_the_sheet_of_an_alternate_only_course_shows_its_prices(plan):
    sheet = logic.course_page("2652-S1", plan)
    assert sheet["prices_list"] == "alternate"
    assert sheet["prices"][0]["min_rank_value"] == 20
    assert logic.course_page("2477-S1", plan)["prices_list"] == "primary"
    assert logic.course_page("2477-S1", plan)["lowest_in_course"] == 100


# ---------- the same through the pages ----------

def test_removing_through_the_page_answers_with_what_undo_needs(client):
    client.post("/api/add", json={"offering_id": "2477-S1"})
    answer = client.post("/api/remove", json={"offering_id": "2477-S1"}).get_json()
    assert answer["error"] is None
    assert answer["state"]["items"] == []
    assert answer["removed"][0]["section_id"] == "2477-S1-TXA"
    back = client.post("/api/restore", json={"rows": answer["removed"]}).get_json()
    assert back["error"] is None
    assert back["state"]["items"][0]["section_id"] == "2477-S1-TXA"


def test_switching_and_starting_over_through_the_page(client):
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    answer = client.post("/api/switch", json={"section_id": "2477-S1-TXC"}).get_json()
    assert [item["section_id"] for item in answer["state"]["items"]] == ["2477-S1-TXC"]
    answer = client.post("/api/start-over", json={}).get_json()
    assert answer["state"]["items"] == []


def test_the_sheet_of_a_course_opens_and_an_unknown_one_does_not(client):
    assert client.get("/api/sheet/2477-S1").status_code == 200
    assert client.get("/api/sheet/nope").status_code == 404


# ---------- one bid per course: only the highest counts anyway (LN R6), so one number is the normal case ----------

def test_a_course_bid_goes_to_all_its_sections(plan):
    add_all(plan, "2477-S1-TXB", "2477-S1-TXA", "2477-S1-TXC")
    assert logic.set_course_bid(plan, "2477-S1", 164) is None
    assert [item["bid"] for item in entries(plan, "2477-S1")] == [164, 164, 164]
    assert logic.reserved_points(db.load_items(plan["id"])) == 164


def test_a_course_bid_can_be_emptied(plan):
    add_all(plan, "2477-S1-TXB", "2477-S1-TXA")
    logic.set_course_bid(plan, "2477-S1", 164)
    assert logic.set_course_bid(plan, "2477-S1", "") is None
    assert [item["bid"] for item in entries(plan, "2477-S1")] == [None, None]


def test_a_refused_course_bid_changes_nothing(plan):
    add_all(plan, "2477-S1-TXB", "2477-S1-TXA")
    logic.set_course_bid(plan, "2477-S1", 50)
    assert "cannot exceed" in logic.set_course_bid(plan, "2477-S1", 99999)
    assert logic.set_course_bid(plan, "2477-S1", -1) == "A bid cannot be negative."
    assert [item["bid"] for item in entries(plan, "2477-S1")] == [50, 50]


def test_a_course_bid_for_a_course_outside_the_plan_is_refused(plan):
    assert logic.set_course_bid(plan, "2477-S1", 10) == "This course is not in your plan."


def test_a_mandatory_course_needs_no_bid(plan):
    add_all(plan, "2459-S1-TXC")
    assert logic.set_course_bid(plan, "2459-S1", 10) == "Mandatory courses need no bid."


def test_the_course_bid_through_the_page(client):
    client.post("/api/add", json={"section_id": "2477-S1-TXB"})
    client.post("/api/add", json={"section_id": "2477-S1-TXA"})
    answer = client.post("/api/bid", json={"offering_id": "2477-S1", "bid": 100}).get_json()
    assert answer["error"] is None
    assert [item["bid"] for item in answer["state"]["items"]] == [100, 100]


# ---------- the alternate list has its own way in ----------

def test_a_course_can_go_straight_to_the_alternate_list(client):
    answer = client.post("/api/add", json={"offering_id": "2652-S1", "list": "alternate"}).get_json()
    assert answer["error"] is None
    item = answer["state"]["items"][0]
    assert item["list"] == "alternate"
    assert item["in_week"] is False
    assert answer["state"]["ects"]["total"] == 0


def test_an_unknown_list_is_refused(client):
    answer = client.post("/api/add", json={"offering_id": "2652-S1", "list": "secret"}).get_json()
    assert answer["error"] == "Unknown list."
    assert answer["state"]["items"] == []


# ---------- which round this plan is for ----------

def test_a_round_that_is_over_says_so(plan):
    round_ = logic.round_of("Fall", today="2026-11-07")
    assert round_["status"] == "closed"
    assert round_["range"] == "Tue 21 Jul – Thu 23 Jul"


def test_the_next_round_counts_the_days(plan):
    round_ = logic.round_of("Spring", today="2026-11-07")
    assert round_["status"] == "upcoming"
    assert round_["days"] == 72


def test_a_round_that_is_running_says_so(plan):
    assert logic.round_of("Spring", today="2027-01-19")["status"] == "open"


# ---------- what we know about prices, for the rows without one ----------

def test_the_known_prices_give_the_range(plan):
    known = logic.known_prices()
    assert known == {"sections": 5, "total": 245, "low": 40, "high": 120}


def test_the_semester_menu_says_what_can_still_be_bid_on(plan):
    assert logic.semester_label("Fall", today="2026-11-07") == "Fall · closed"
    assert logic.semester_label("Spring", today="2026-11-07") == "Spring · opens 18 Jan"


def test_a_new_visitor_starts_without_programme_and_points():
    plan = db.load_plan(logic.default_plan_id())
    assert plan["programme"] == "" and plan["points"] == 0
    assert logic.update_settings(plan, "", "Fall", 100, False) is None
    assert logic.set_course_bid(db.load_plan(plan["id"]), "2477-S1", 10) == "This course is not in your plan."
    assert logic.update_settings(plan, "Nonsense", "Fall", 100, False) == "Unknown programme."


def test_a_bid_before_the_points_says_what_to_do():
    plan = db.load_plan(logic.default_plan_id())
    add_all(plan, "2477-S1-TXB")
    assert logic.set_course_bid(plan, "2477-S1", 10) == "Enter your points first."
    assert logic.set_course_bid(plan, "2477-S1", 0) is None


def test_an_alternate_pays_its_bid_not_the_middle():
    # LN R4 against LN R3: 88 on the alternate list costs 88, on the primary list it would cost 64.
    plan = db.load_plan(db.create_plan("Management", "Fall", 218))
    add_all(plan, "2277-T2-TXA")
    item = entries(plan, "2277-T2")[0]
    logic.set_bid(plan, item["id"], 88)
    assert logic.state_of(plan)["items"][0]["analysis"]["price"] == 64
    logic.move_item(plan, item["id"], list_name="alternate")
    assert logic.state_of(plan)["items"][0]["analysis"]["price"] == 88


def test_a_course_in_t1_and_t2_counts_its_ects_once(plan):
    # LN R8: "A course counts once". 2329 runs in both halves.
    assert logic.add_to_plan(plan, section_id="2329-T1-TXA") is None
    assert logic.add_to_plan(plan, section_id="2329-T2-TXA") is None
    assert logic.ects_summary(db.load_items(plan["id"]))["total"] == 3.5


def test_warnings_say_where_to_fix_it(plan):
    add_all(plan, "2477-S1-TXB")
    warnings = logic.warnings_for(plan, db.load_items(plan["id"]))
    assert {"bids"} == {warning["where"] for warning in warnings}
    assert any("not interested" in warning["text"] for warning in warnings)
    assert any("alternate list is empty" in warning["text"] for warning in warnings)
