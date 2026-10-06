"""Festival Architect: every screen lives here. Start it with `uv run streamlit run app.py`."""
from datetime import time

import streamlit as st

import db
import logic

SCREENS = ["Timetable", "Book an artist", "Change a booking"]


# ---------- small helpers ----------

def to_time(clock):
    """Turn stored 'HH:MM' text into the time object Streamlit's time picker expects."""
    hours, minutes = clock.split(":")
    return time(int(hours), int(minutes))


def to_text(value):
    """Turn the time picker's value back into 'HH:MM' text, the way logic.py and the database use it."""
    return value.strftime("%H:%M")


def finish_click(problems, success_text):
    """Remember what a click did and redraw the page, so every number on it shows the saved data."""
    if len(problems) == 0:
        st.session_state["message"] = ("success", success_text)
    else:
        st.session_state["message"] = ("error", "Nothing was changed:\n\n- " + "\n- ".join(problems))
    st.rerun()


def show_message():
    """Show, once, the outcome of the last click. It sits at the end of the page, under the buttons."""
    if "message" not in st.session_state:
        return
    kind, text = st.session_state.pop("message")
    if kind == "success":
        st.success(text)
    else:
        st.error(text)


def show_budget():
    """FA03: the numbers to check after every change."""
    left, middle, right = st.columns(3)
    left.metric("Artists booked", len(logic.all_bookings()))
    middle.metric("Fees committed", logic.euros(logic.total_fees()))
    right.metric("Budget left", logic.euros(logic.remaining_budget()))


def show_end(start, artist):
    """FA02: show where a set ends before it is saved."""
    end = logic.end_time(start, artist["duration"])
    st.caption("Ends at " + end + " · " + str(artist["duration"]) + " min · "
               + logic.euros(artist["fee"]))


# ---------- screen 1: timetable ----------

def show_timetable():
    """Home screen: the budget, each stage's performances in time order, finalise or reopen."""
    st.title("Timetable")
    show_budget()

    names = logic.stage_names()
    for stage_id in names:
        st.subheader(names[stage_id])
        rows = []
        for slot in logic.timetable(stage_id):
            rows.append({"Start": slot["start"], "End": slot["end"], "Artist": slot["name"],
                         "Genre": slot["genre"], "Fee": logic.euros(slot["fee"])})
        if len(rows) == 0:
            st.caption("Nothing booked on this stage yet.")
        else:
            st.table(rows, hide_index=True, border="horizontal")

    st.divider()
    if logic.is_final():
        st.success("This plan is final. It stays read-only until you reopen it as a draft.")
        if st.button("Reopen as draft", key="reopen"):
            logic.reopen()
            finish_click([], "The plan is a draft again.")
    else:
        st.caption("Finalise once at least " + str(logic.ARTISTS_NEEDED_TO_FINALISE)
                   + " artists are booked. A final plan is read-only.")
        if st.button("Finalise plan", key="finalise", type="primary"):
            finish_click(logic.finalise(), "The plan is final.")


# ---------- screen 2: book an artist ----------

def show_booking():
    """FA01 and FA02: the catalogue, then the form to book one artist on a stage."""
    st.title("Book an artist")
    show_budget()

    st.subheader("Catalogue")
    rows = []
    labels = {}
    for artist in logic.catalogue():
        rows.append({"Artist": artist["name"], "Genre": artist["genre"],
                     "Fee": logic.euros(artist["fee"]), "Set": str(artist["duration"]) + " min",
                     "Booked": artist["booked"]})
        labels[artist["id"]] = artist["name"]
        if artist["booked"] != "":
            labels[artist["id"]] = artist["name"] + " (booked)"
    st.table(rows, hide_index=True, border="horizontal")

    st.subheader("New booking")
    if logic.is_final():
        st.info(logic.FINAL_PLAN)
        return

    names = logic.stage_names()
    artist_id = st.selectbox("Artist", list(labels), format_func=labels.get, key="book_artist")
    stage_id = st.selectbox("Stage", list(names), format_func=names.get, key="book_stage")
    start = to_text(st.time_input("Start", value=time(14, 0), step=60, key="book_start"))
    artist = logic.artists_by_id()[artist_id]
    show_end(start, artist)

    if st.button("Book", key="book", type="primary"):
        end = logic.end_time(start, artist["duration"])
        finish_click(logic.add_booking(artist_id, stage_id, start),
                     artist["name"] + " booked on " + names[stage_id] + ", " + start + "–" + end + ".")


# ---------- screen 3: change a booking ----------

def show_change():
    """FA04: move a booking to another stage or time, or remove it."""
    st.title("Change a booking")

    bookings = logic.all_bookings()
    if len(bookings) == 0:
        st.info("Nothing booked yet. Book an artist first.")
        return
    if logic.is_final():
        st.info(logic.FINAL_PLAN)
        return

    artists = logic.artists_by_id()
    names = logic.stage_names()
    labels = {}
    for booking in bookings:
        labels[booking["artist_id"]] = artists[booking["artist_id"]]["name"]
    artist_id = st.selectbox("Booking", list(labels), format_func=labels.get, key="change_booking")
    booking = logic.booking_for(artist_id)
    artist = artists[artist_id]
    st.markdown("Now: **" + names[booking["stage_id"]] + ", " + booking["start"] + "–"
                + logic.end_time(booking["start"], artist["duration"]) + "**")

    # The keys contain the artist, so the fields start from this booking when you pick another one.
    stage_ids = list(names)
    stage_id = st.selectbox("Stage", stage_ids, index=stage_ids.index(booking["stage_id"]),
                            format_func=names.get, key="change_stage_" + str(artist_id))
    start = to_text(st.time_input("Start", value=to_time(booking["start"]), step=60,
                                  key="change_start_" + str(artist_id)))
    show_end(start, artist)

    left, right = st.columns(2)
    if left.button("Save change", key="move", type="primary"):
        end = logic.end_time(start, artist["duration"])
        finish_click(logic.move_booking(artist_id, stage_id, start),
                     artist["name"] + " moved to " + names[stage_id] + ", " + start + "–" + end + ".")
    if right.button("Remove booking", key="remove"):
        finish_click(logic.remove_booking(artist_id),
                     artist["name"] + " removed. " + logic.euros(artist["fee"]) + " back in the budget.")


# ---------- this part runs on every click ----------

st.set_page_config(page_title="Festival Architect")
db.ensure_database()

st.sidebar.title(logic.FESTIVAL_NAME)
st.sidebar.caption("Festival Architect · one day, " + logic.DOORS_OPEN + "–" + logic.CURFEW
                   + " · " + logic.euros(logic.BUDGET) + " artist budget")
screen = st.sidebar.radio("Screen", SCREENS, key="screen")
if logic.is_final():
    st.sidebar.success("Plan: final")
else:
    st.sidebar.info("Plan: draft")
st.sidebar.caption("Saved in data/festival.db. Start over with `uv run python seed.py`.")

if screen == "Timetable":
    show_timetable()
elif screen == "Book an artist":
    show_booking()
else:
    show_change()
show_message()
