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
