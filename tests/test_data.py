"""Scenario A4: the data built from Nova's PDFs must match what is known from other sources."""
from datetime import date

import db
import logic


def sessions_of(section_id):
    return logic.all_sessions()[section_id]


def test_programming_txb_runs_twelve_tuesdays_with_the_make_up_on_friday():
    sessions = sessions_of("2477-S1-TXB")
    assert len(sessions) == 12
    assert {s["room"] for s in sessions} == {"B.0.04"}
    assert {(s["start"], s["end"]) for s in sessions} == {("12:30", "14:00")}
    last = sessions[-1]
    assert last["date"] == "2026-12-04"
    assert date.fromisoformat(last["date"]).weekday() == 4
    assert "1 Dec" in last["note"]
    # the course page lists these class dates: 29 Sep, 6 Oct, a pause, then 27 Oct and 3 Nov
    dates = [s["date"] for s in sessions]
    for known in ("2026-09-29", "2026-10-06", "2026-10-27", "2026-11-03"):
        assert known in dates
    assert "2026-10-13" not in dates and "2026-10-20" not in dates


def test_no_class_on_a_holiday():
    holidays = {"2026-10-05", "2026-12-01", "2026-12-08", "2026-10-29"}
    for sessions in logic.all_sessions().values():
        for session in sessions:
            assert session["date"] not in holidays


def test_each_section_has_a_plausible_number_of_classes():
    for section_id, sessions in logic.all_sessions().items():
        term = section_id.split("-")[1]
        assert len(sessions) in ({6, 12} if term in ("T1", "T2") else {11, 12, 24}), section_id


def test_a_block_is_never_listed_twice():
    seen = set()
    for meetings in logic.all_meetings().items():
        section_id, rows = meetings
        for row in rows:
            key = (section_id, row["day"], row["start"])
            assert key not in seen
            seen.add(key)


def test_exam_dates_match_the_bidding_platform():
    # The platform's own schedule page for one account, read on 6 Nov 2026.
    exams = logic.all_exams()
    assert any(e["kind"] == "exam" and e["date"] == "2026-12-19" and e["start"] == "17:30" for e in exams[("2477", "S1")])
    assert any(e["kind"] == "exam" and e["date"] == "2026-10-20" and e["start"] == "08:30" for e in exams[("2966", "T1")])
    assert any(e["kind"] == "makeup" and e["date"] == "2026-10-30" and e["start"] == "18:30" for e in exams[("2966", "T1")])


def test_mandatory_courses_of_one_real_student_are_mandatory_here():
    kinds = db.load_programme_kinds("Management")
    for offering_id in ("2459-S1", "2463-T2", "2581-S1", "2966-T1"):
        assert kinds[offering_id] == "mandatory"
    assert kinds["2477-S1"] == "elective"


def test_spring_bidding_date_comes_from_the_academic_calendar():
    row = next(r for r in db.load_calendar() if r["key"] == "spring-bidding")
    assert (row["first_day"], row["last_day"]) == ("2027-01-18", "2027-01-20")


def test_next_deadline_counts_down():
    assert logic.next_deadline("2026-11-07")["days"] == 72
    assert logic.next_deadline("2026-11-07")["label"].startswith("Spring")
    assert logic.next_deadline("2027-01-19")["days"] == 0


def test_rank_lists_contain_no_personal_columns():
    for row in db.read_seed("cutoffs") + db.read_seed("bid_histogram"):
        assert not set(row) & {"student", "student_number", "ects", "ects_sum", "name"}
