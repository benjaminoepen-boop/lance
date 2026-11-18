"""Scenarios A2 and A3: clashes checked on Nova's real timetable, date by date."""
import db
import logic
from conftest import add_all


def test_two_courses_at_the_same_time_clash(plan):
    add_all(plan, "2459-S1-TXC", "2175-S1-TXA")
    clashes = logic.class_clashes(db.load_items(plan["id"]))
    assert len(clashes) == 1
    assert "Advanced Strategy" in clashes[0]["first"] + clashes[0]["second"]


def test_two_sections_of_one_course_never_clash(plan):
    add_all(plan, "2229-S1-TXF", "2229-S1-TXA")
    assert logic.class_clashes(db.load_items(plan["id"])) == []


def test_t1_and_t2_at_the_same_weekday_and_time_do_not_clash(plan):
    # Same room band, same weekday, but one runs until October and the other starts afterwards.
    assert logic.clashing_dates("2446-T1-TXA", "2446-T2-TXA") == []


def test_an_s1_course_clashes_with_t2_only_in_t2(plan):
    add_all(plan, "2652-S1-TXA", "2277-T2-TXA")
    clashes = logic.class_clashes(db.load_items(plan["id"]))
    assert clashes[0]["weeks"] == ["T2"]
    assert clashes[0]["times"] == 6
    assert clashes[0]["of"] == 12


def test_section_warnings_name_what_a_section_would_clash_with(plan):
    add_all(plan, "2459-S1-TXC")
    per_section, _ = logic.section_warnings(db.load_items(plan["id"]), "Fall")
    assert "Advanced Strategy TXC" in per_section["2175-S1-TXA"]
    assert "2459-S1-TXC" not in per_section


def test_overlapping_exams_are_reported():
    plan = db.load_plan(db.create_plan("Management", "Fall", 165))
    # Two T2 courses with an exam at the same hour on the same day, taken from the real calendar.
    exams = db.load_exams()
    by_slot = {}
    pair = None
    for exam in exams:
        if exam["kind"] == "exam" and exam["term"] == "T2":
            slot = (exam["date"], exam["start"])
            if slot in by_slot and by_slot[slot] != exam["code"]:
                pair = (by_slot[slot], exam["code"])
                break
            by_slot[slot] = exam["code"]
    assert pair is not None
    for code in pair:
        assert logic.add_to_plan(plan, offering_id=f"{code}-T2") is None
    clashes = logic.exam_clashes(db.load_items(plan["id"]))
    assert any(clash["kind"] == "exam" for clash in clashes)


def test_a_midterm_during_a_class_is_reported():
    plan = db.load_plan(db.create_plan("Management", "Fall", 165))
    # Integrated Marketing Communications has a midterm on Thu 19 Nov at 18:30.
    midterm = next(e for e in db.load_exams() if e["code"] == "2337" and e["kind"] == "midterm" and e["date"] == "2026-11-19")
    assert midterm["start"] == "18:30"
    evening = None
    for section_id, sessions in logic.all_sessions().items():
        code = section_id.split("-")[0]
        if code != "2337" and any(s["date"] == midterm["date"] and logic.overlaps(s["start"], s["end"], midterm["start"], midterm["end"]) for s in sessions):
            evening = section_id
            break
    assert evening is not None
    assert logic.add_to_plan(plan, offering_id="2337-T2") is None
    assert logic.add_to_plan(plan, section_id=evening) is None
    assert any(clash["kind"] == "midterm" for clash in logic.exam_clashes(db.load_items(plan["id"])))


# ---------- LN R16: two exams on one day ----------

def same_day_pair(term="T1"):
    """Two courses of one term with an exam on the same date, one after the other, taken from the real calendar."""
    exams = [e for e in db.load_exams() if e["kind"] == "exam" and e["term"] == term and e["date"]]
    for i, a in enumerate(exams):
        for b in exams[i + 1:]:
            if a["code"] != b["code"] and a["date"] == b["date"] and not logic.overlaps(a["start"], a["end"], b["start"], b["end"]):
                return a, b
    raise AssertionError("no such pair in the calendar")


def test_two_exams_on_one_day_are_a_hard_day_and_not_a_clash(plan):
    a, b = same_day_pair()
    for exam in (a, b):
        assert logic.add_to_plan(plan, offering_id=f"{exam['code']}-T1") is None
    items = db.load_items(plan["id"])
    days = logic.exam_days(items)
    assert len(days) == 1
    assert days[0]["when"] == logic.day_label(a["date"])
    assert {days[0]["first"], days[0]["second"]} == {logic.all_offerings()[f"{a['code']}-T1"]["name"], logic.all_offerings()[f"{b['code']}-T1"]["name"]}
    assert not any(clash["kind"] == "exam" for clash in logic.exam_clashes(items))


def test_exams_on_different_days_say_nothing(plan):
    a, _ = same_day_pair()
    other = next(e for e in db.load_exams() if e["kind"] == "exam" and e["term"] == "T1" and e["date"] and e["date"] != a["date"] and e["code"] != a["code"])
    for exam in (a, other):
        assert logic.add_to_plan(plan, offering_id=f"{exam['code']}-T1") is None
    assert logic.exam_days(db.load_items(plan["id"])) == []


def test_exams_in_one_slot_are_a_clash_and_not_a_hard_day(plan):
    exams = [e for e in db.load_exams() if e["kind"] == "exam" and e["term"] == "T2"]
    pair = next((a, b) for i, a in enumerate(exams) for b in exams[i + 1:]
                if a["code"] != b["code"] and a["date"] == b["date"] and a["start"] == b["start"])
    for exam in pair:
        assert logic.add_to_plan(plan, offering_id=f"{exam['code']}-T2") is None
    items = db.load_items(plan["id"])
    assert any(clash["kind"] == "exam" for clash in logic.exam_clashes(items))
    assert logic.exam_days(items) == []


def test_a_course_not_yet_in_the_plan_warns_about_the_hard_day(plan):
    a, b = same_day_pair()
    assert logic.add_to_plan(plan, offering_id=f"{a['code']}-T1") is None
    warnings = logic.exam_day_warnings(db.load_items(plan["id"]), "Fall")
    assert logic.all_offerings()[f"{a['code']}-T1"]["name"] in warnings[f"{b['code']}-T1"]
    assert f"{a['code']}-T1" not in warnings


def test_the_state_carries_the_hard_days_and_leaves_the_clash_count_alone(client):
    a, b = same_day_pair()
    for exam in (a, b):
        client.post("/api/add", json={"offering_id": f"{exam['code']}-T1"})
    state = client.get("/api/state").get_json()["state"]
    assert len(state["exam_days"]) == 1
    assert state["clashes"] == []
