"""The brief's acceptance scenarios A1–A6, run against a real (throwaway) database."""
import db
import logic
from conftest import (COBALT_AVENUE, LUNA_FERRO, MARISOL_VEGA, NIGHT_FERRY, OS_GAIVOTAS,
                      SALT_STATIC, TIDEWATERS, lineup)


def book_nine_thousand():
    """Commit exactly €9,000: The Tidewaters, Luna Ferro and Cobalt Avenue, no clashes."""
    assert logic.add_booking(TIDEWATERS, "A", "14:00") == []       # €3,500
    assert logic.add_booking(LUNA_FERRO, "A", "15:00") == []       # €3,000
    assert logic.add_booking(COBALT_AVENUE, "B", "14:00") == []    # €2,500
    assert logic.total_fees() == 9000


# ---------- A1: same stage conflict ----------

def test_a1_overlap_on_the_same_stage_is_refused():
    """16:00–17:00 is booked on Stage A; 16:30–17:15 on Stage A is refused and nothing is saved."""
    assert logic.add_booking(TIDEWATERS, "A", "16:00") == []
    problems = logic.add_booking(OS_GAIVOTAS, "A", "16:30")
    assert len(problems) == 1
    assert "The Tidewaters" in problems[0]
    assert lineup() == [(TIDEWATERS, "A", "16:00")]


def test_a1_starting_when_the_previous_set_ends_is_accepted():
    """The second set may start at 17:00, exactly when the first one ends."""
    assert logic.add_booking(TIDEWATERS, "A", "16:00") == []
    assert logic.add_booking(OS_GAIVOTAS, "A", "17:00") == []
    assert lineup() == [(TIDEWATERS, "A", "16:00"), (OS_GAIVOTAS, "A", "17:00")]


# ---------- A2: different stages ----------

def test_a2_same_time_on_different_stages_is_accepted():
    """FA R3: two artists at 16:00, one per stage."""
    assert logic.add_booking(TIDEWATERS, "A", "16:00") == []
    assert logic.add_booking(COBALT_AVENUE, "B", "16:00") == []
    assert len(lineup()) == 2


# ---------- A3: festival boundaries ----------

def test_a3_sixty_minute_set_at_the_edges_of_the_day():
    """13:59 and 22:01 are refused for a 60-minute set; 22:00 ends at 23:00 and is accepted."""
    assert logic.add_booking(TIDEWATERS, "A", "13:59") != []
    assert logic.add_booking(TIDEWATERS, "A", "22:01") != []
    assert lineup() == []
    assert logic.add_booking(TIDEWATERS, "A", "22:00") == []
    assert logic.timetable("A")[0]["end"] == "23:00"


# ---------- A4: budget and duplicates ----------

def test_a4_spending_exactly_the_budget_is_accepted():
    """With €9,000 committed, a €1,000 artist brings the total to exactly €10,000."""
    book_nine_thousand()
    assert logic.add_booking(NIGHT_FERRY, "B", "16:00") == []
    assert logic.total_fees() == 10000
    assert logic.remaining_budget() == 0


def test_a4_one_euro_over_the_budget_is_refused():
    """With €9,000 committed, a €1,001 artist is refused and the lineup stays as it was."""
    db.execute("INSERT INTO artists (id, name, genre, fee, duration) VALUES (?, ?, ?, ?, ?)",
               (99, "Test Act", "Test", 1001, 60))
    book_nine_thousand()
    before = lineup()
    problems = logic.add_booking(99, "B", "16:00")
    assert len(problems) == 1
    assert "budget" in problems[0]
    assert lineup() == before
    assert logic.total_fees() == 9000


def test_a4_an_artist_already_booked_is_refused_on_any_stage():
    """FA R1: The Tidewaters play once, whatever the stage or time."""
    assert logic.add_booking(TIDEWATERS, "A", "16:00") == []
    assert logic.add_booking(TIDEWATERS, "B", "20:00") != []
    assert logic.add_booking(TIDEWATERS, "A", "20:00") != []
    assert lineup() == [(TIDEWATERS, "A", "16:00")]
    assert logic.total_fees() == 3500


# ---------- A5: edit and remove ----------

def test_a5_a_conflicting_edit_keeps_the_original_booking():
    """Moving Os Gaivotas into The Tidewaters' slot is refused; Os Gaivotas stays at 17:00."""
    logic.add_booking(TIDEWATERS, "A", "16:00")
    logic.add_booking(OS_GAIVOTAS, "A", "17:00")
    assert logic.move_booking(OS_GAIVOTAS, "A", "16:30") != []
    assert lineup() == [(TIDEWATERS, "A", "16:00"), (OS_GAIVOTAS, "A", "17:00")]


def test_a5_a_valid_edit_does_not_duplicate_artist_or_fee():
    """Moving The Tidewaters to Stage B keeps one booking and the same total."""
    logic.add_booking(TIDEWATERS, "A", "16:00")
    assert logic.move_booking(TIDEWATERS, "B", "18:00") == []
    assert lineup() == [(TIDEWATERS, "B", "18:00")]
    assert logic.total_fees() == 3500


def test_a5_an_edit_is_checked_as_a_replacement():
    """FA R5: shifting a set by 30 minutes overlaps its old slot, which is not a clash with itself."""
    logic.add_booking(TIDEWATERS, "A", "16:00")
    assert logic.move_booking(TIDEWATERS, "A", "16:30") == []
    assert lineup() == [(TIDEWATERS, "A", "16:30")]


def test_a5_an_edit_into_the_budget_limit_is_not_charged_twice():
    """At exactly €10,000, moving a booked artist must not count its fee a second time."""
    book_nine_thousand()
    logic.add_booking(NIGHT_FERRY, "B", "16:00")
    assert logic.move_booking(NIGHT_FERRY, "B", "18:00") == []
    assert logic.total_fees() == 10000


def test_a5_removing_releases_slot_and_fee():
    """After removing The Tidewaters, their €3,500 and their 16:00 slot are free again."""
    logic.add_booking(TIDEWATERS, "A", "16:00")
    assert logic.remove_booking(TIDEWATERS) == []
    assert logic.remaining_budget() == 10000
    assert logic.add_booking(COBALT_AVENUE, "A", "16:00") == []


# ---------- A6: save and finalise ----------

def test_a6_finalising_needs_four_artists():
    """Three artists: refused and still a draft. Four valid bookings: the plan becomes final."""
    book_nine_thousand()
    problems = logic.finalise()
    assert len(problems) == 1
    assert "4" in problems[0]
    assert not logic.is_final()
    logic.add_booking(NIGHT_FERRY, "B", "16:00")
    assert logic.finalise() == []
    assert logic.is_final()


def test_a6_a_final_plan_is_read_only_until_reopened():
    """No booking can be added, moved or removed while final; reopening makes it a draft again."""
    book_nine_thousand()
    logic.add_booking(NIGHT_FERRY, "B", "16:00")
    logic.finalise()
    before = lineup()
    assert logic.add_booking(MARISOL_VEGA, "B", "20:00") != []
    assert logic.move_booking(TIDEWATERS, "B", "20:00") != []
    assert logic.remove_booking(TIDEWATERS) != []
    assert lineup() == before
    logic.reopen()
    assert not logic.is_final()
    assert logic.remove_booking(TIDEWATERS) == []


def test_a6_finalising_rechecks_the_saved_lineup():
    """A lineup that breaks a rule (here: edited by hand in the database) cannot be finalised."""
    logic.add_booking(TIDEWATERS, "A", "16:00")
    logic.add_booking(OS_GAIVOTAS, "A", "17:00")
    logic.add_booking(MARISOL_VEGA, "B", "16:00")
    logic.add_booking(SALT_STATIC, "B", "17:00")
    db.execute("UPDATE bookings SET start = ? WHERE artist_id = ?", ("16:30", OS_GAIVOTAS))
    assert logic.finalise() != []
    assert not logic.is_final()
