"""The screens, clicked through with Streamlit's AppTest. A new AppTest is a fresh start of the app."""
from datetime import time

from streamlit.testing.v1 import AppTest

import logic
from conftest import APP_FILE, OS_GAIVOTAS, TIDEWATERS, lineup

SCREENS = ["Timetable", "Book an artist", "Change a booking"]


def open_app(screen="Timetable"):
    """Start the app like `streamlit run` would, on the given screen."""
    # the first start imports Streamlit and pandas, which can take longer than the 3 s default
    app = AppTest.from_file(APP_FILE, default_timeout=10)
    app.run()
    app.radio(key="screen").set_value(screen).run()
    return app


def metric_values(app):
    """The metrics on screen as {label: value}."""
    values = {}
    for metric in app.metric:
        values[metric.label] = metric.value
    return values


def book_through_the_screen(app, artist_id, stage_id, start):
    """Fill in the booking form and press Book."""
    app.selectbox(key="book_artist").set_value(artist_id)
    app.selectbox(key="book_stage").set_value(stage_id)
    app.time_input(key="book_start").set_value(start)
    app.button(key="book").click().run()


def test_every_screen_opens():
    """Each screen runs without an exception on a fresh database."""
    for screen in SCREENS:
        app = open_app(screen)
        assert not app.exception


def test_booking_on_screen_is_saved_and_confirmed():
    """FA02: a valid booking shows its slot and lands in the database."""
    app = open_app("Book an artist")
    book_through_the_screen(app, TIDEWATERS, "A", time(16, 0))
    assert not app.exception
    assert "16:00–17:00" in app.success[0].value
    assert lineup() == [(TIDEWATERS, "A", "16:00")]


def test_refused_booking_on_screen_explains_why():
    """FA02: a clash is refused with the reason on screen, and nothing is saved."""
    logic.add_booking(TIDEWATERS, "A", "16:00")
    app = open_app("Book an artist")
    book_through_the_screen(app, OS_GAIVOTAS, "A", time(16, 30))
    assert "The Tidewaters" in app.error[0].value
    assert lineup() == [(TIDEWATERS, "A", "16:00")]


def test_a_restart_shows_the_saved_lineup_and_totals():
    """A6: after reopening, the timetable and the budget match the saved bookings."""
    logic.add_booking(TIDEWATERS, "A", "16:00")
    logic.add_booking(OS_GAIVOTAS, "A", "17:00")
    app = open_app("Timetable")
    values = metric_values(app)
    assert values["Fees committed"] == "€5,000"
    assert values["Budget left"] == "€5,000"
    stage_a = app.table[0].value
    assert list(stage_a["Artist"]) == ["The Tidewaters", "Os Gaivotas"]
    assert list(stage_a["End"]) == ["17:00", "17:45"]


def test_a_final_plan_reopens_as_final_and_can_be_returned_to_draft():
    """A6: the final status survives a restart; the Reopen button turns it back into a draft."""
    for artist_id, start in [(1, "14:00"), (2, "15:00"), (3, "16:15"), (7, "17:15")]:
        assert logic.add_booking(artist_id, "A", start) == []
    assert logic.finalise() == []
    app = open_app("Timetable")
    assert app.button(key="reopen")
    app.button(key="reopen").click().run()
    assert not logic.is_final()
