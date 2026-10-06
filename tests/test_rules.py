"""The rules as small calculations, without the database: times, overlaps and the budget."""
import logic


def test_clock_text_and_minutes_convert_both_ways():
    """16:30 is 990 minutes after midnight, and back."""
    assert logic.to_minutes("16:30") == 990
    assert logic.to_clock(990) == "16:30"
    assert logic.to_clock(840) == "14:00"


def test_end_time_is_start_plus_duration():
    """FA02: the end is calculated from the artist's set duration."""
    assert logic.end_time("16:00", 60) == "17:00"
    assert logic.end_time("16:30", 45) == "17:15"
    assert logic.end_time("22:45", 90) == "24:15"


def test_slots_that_share_a_minute_overlap():
    """FA R2: 16:00–17:00 and 16:30–17:15 clash, so do a slot and one inside it."""
    assert logic.overlaps("16:00", "17:00", "16:30", "17:15")
    assert logic.overlaps("16:30", "17:15", "16:00", "17:00")
    assert logic.overlaps("16:00", "18:00", "16:30", "17:00")


def test_slots_that_only_touch_do_not_overlap():
    """FA R2: a set may start exactly when the previous one ends."""
    assert not logic.overlaps("16:00", "17:00", "17:00", "17:45")
    assert not logic.overlaps("17:00", "17:45", "16:00", "17:00")


def test_inside_festival_hours():
    """FA R2 / A3: start at or after 14:00, end at or before 23:00."""
    assert logic.inside_festival_hours("14:00", "15:00")
    assert logic.inside_festival_hours("22:00", "23:00")
    assert not logic.inside_festival_hours("13:59", "14:59")
    assert not logic.inside_festival_hours("22:01", "23:01")


def test_budget_boundary():
    """FA R4 / A4: €9,000 committed plus €1,000 is exactly the budget and allowed; plus €1,001 is not."""
    assert logic.within_budget(9000 + 1000)
    assert not logic.within_budget(9000 + 1001)


def test_euros_are_shown_with_thousands_separator():
    """Money is shown the same way everywhere on screen."""
    assert logic.euros(10000) == "€10,000"
    assert logic.euros(800) == "€800"
