"""Festival Architect: every screen lives here. Start it with `uv run streamlit run app.py`."""
import html
from datetime import time
from pathlib import Path

import streamlit as st

import db
import logic

SCREENS = ["Timetable", "Book an artist", "Change a booking"]
ICONS = {
    "Timetable": ":material/view_timeline:",
    "Book an artist": ":material/add_circle:",
    "Change a booking": ":material/edit_calendar:",
}
# Colours, cards and the timeline are styled here; the screens below only say what goes where.
STYLE_FILE = Path(__file__).parent / "style.css"


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
    """Show, once, the outcome of the last click. Each screen calls this right under its buttons."""
    if "message" not in st.session_state:
        return
    kind, text = st.session_state.pop("message")
    if kind == "success":
        st.success(text)
    else:
        st.error(text)


def screen_label(name):
    """The sidebar text for a screen: its icon, then its name."""
    return ICONS[name] + " " + name


def card(name):
    """A white card. style.css paints every container whose key starts with 'card'."""
    return st.container(border=True, key="card_" + name)


def card_title(text, note=""):
    """The bold first line of a card, with an optional grey note after it."""
    extra = ""
    if note != "":
        extra = " <span>· " + html.escape(note) + "</span>"
    st.html('<p class="card-title">' + html.escape(text) + extra + "</p>")


def show_end(start, artist):
    """FA02: show where a set ends before it is saved."""
    end = logic.end_time(start, artist["duration"])
    st.caption("Plays " + start + "–" + end + " · " + str(artist["duration"]) + " min · "
               + logic.euros(artist["fee"]))


# ---------- the building blocks ----------

def show_summary():
    """FA03: the numbers to check after every change, and how much of the budget is used."""
    with card("summary"):
        left, middle, right = st.columns(3)
        left.metric("Artists booked", len(logic.all_bookings()))
        middle.metric("Fees committed", logic.euros(logic.total_fees()))
        right.metric("Budget left", logic.euros(logic.remaining_budget()))
        used = round(logic.total_fees() / logic.BUDGET * 100)
        st.html('<div class="budget-bar"><div style="width:' + str(used) + '%"></div></div>'
                + '<div class="budget-text">' + str(used) + " % of the " + logic.euros(logic.BUDGET)
                + " artist budget</div>")


def position(clock):
    """Where a time sits on the timeline, in percent: doors open at 0, curfew at 100."""
    opening = logic.to_minutes(logic.DOORS_OPEN)
    length = logic.to_minutes(logic.CURFEW) - opening
    return round((logic.to_minutes(clock) - opening) / length * 100, 2)


def timeline_html():
    """FA03 at a glance: one lane per stage, one block per performance, from doors open to curfew."""
    hours = ""
    for minutes in range(logic.to_minutes(logic.DOORS_OPEN), logic.to_minutes(logic.CURFEW) + 1, 60):
        clock = logic.to_clock(minutes)
        hours = hours + '<span style="left:' + str(position(clock)) + '%">' + clock + "</span>"
    rows = '<div class="tl-row"><div class="tl-stage"></div><div class="tl-hours">' + hours + "</div></div>"

    names = logic.stage_names()
    for stage_id in names:
        blocks = ""
        for slot in logic.timetable(stage_id):
            left = position(slot["start"])
            width = position(slot["end"]) - left
            hint = (slot["name"] + " · " + slot["start"] + "–" + slot["end"] + " · " + slot["genre"]
                    + " · " + logic.euros(slot["fee"]))
            css_class = "tl-slot"
            if width < 7:
                css_class = "tl-slot short"
            blocks = (blocks + '<div class="' + css_class + '" style="left:' + str(left) + "%;width:" + str(width)
                      + '%" title="' + html.escape(hint) + '"><b>' + html.escape(slot["name"]) + "</b></div>")
        rows = (rows + '<div class="tl-row"><div class="tl-stage">' + html.escape(names[stage_id])
                + '</div><div class="tl-track">' + blocks + "</div></div>")
    return '<div class="timeline"><div class="tl-inner">' + rows + "</div></div>"


def show_timeline():
    """The timeline in its own card."""
    with card("timeline"):
        card_title("Lineup", logic.DOORS_OPEN + "–" + logic.CURFEW)
        st.html(timeline_html())


def catalogue_html():
    """FA01: one small card per artist with genre, fee, set length and whether they are booked."""
    cards = ""
    for artist in logic.catalogue():
        if artist["booked"] == "":
            status = '<span class="dot"></span>Free'
        else:
            status = '<span class="dot ok"></span>' + html.escape(artist["booked"])
        cards = (cards + '<div class="artist"><div class="artist-name">' + html.escape(artist["name"])
                 + '</div><div class="artist-genre">' + html.escape(artist["genre"])
                 + '</div><div class="artist-facts">' + logic.euros(artist["fee"]) + " <span>· "
                 + str(artist["duration"]) + ' min</span></div><div class="artist-status">' + status
                 + "</div></div>")
    return '<div class="artists">' + cards + "</div>"


# ---------- screen 1: timetable ----------

def show_timetable():
    """Home screen: the budget, the timeline, each stage in time order, finalise or reopen."""
    st.title("Timetable")
    show_summary()
    show_timeline()

    names = logic.stage_names()
    columns = st.columns(len(names))
    number = 0
    for stage_id in names:
        with columns[number]:
            with card("stage_" + stage_id):
                slots = logic.timetable(stage_id)
                card_title(names[stage_id], str(len(slots)) + " sets")
                rows = []
                for slot in slots:
                    rows.append({"Start": slot["start"], "End": slot["end"], "Artist": slot["name"],
                                 "Genre": slot["genre"], "Fee": logic.euros(slot["fee"])})
                if len(rows) == 0:
                    st.caption("Nothing booked on this stage yet.")
                else:
                    st.table(rows, hide_index=True, border="horizontal")
        number = number + 1

    with card("plan"):
        if logic.is_final():
            card_title("The plan is final", "read-only until you reopen it as a draft")
            if st.button("Reopen as draft", key="reopen"):
                logic.reopen()
                finish_click([], "The plan is a draft again.")
        else:
            card_title("Draft", "finalise once at least " + str(logic.ARTISTS_NEEDED_TO_FINALISE)
                       + " artists are booked; a final plan is read-only")
            if st.button("Finalise plan", key="finalise", type="primary"):
                finish_click(logic.finalise(), "The plan is final.")
        show_message()


# ---------- screen 2: book an artist ----------

def show_booking():
    """FA01 and FA02: the catalogue, and next to it the form to book one artist on a stage."""
    st.title("Book an artist")
    show_summary()

    left, right = st.columns([3, 2], gap="medium")
    with left:
        st.html('<p class="card-title">Catalogue <span>· ' + str(len(logic.artists_by_id()))
                + " artists</span></p>")
        st.html(catalogue_html())

    with right:
        with card("book"):
            card_title("New booking")
            if logic.is_final():
                st.info(logic.FINAL_PLAN)
                return

            labels = {}
            free_ids = []
            for artist in logic.catalogue():
                labels[artist["id"]] = artist["name"]
                if artist["booked"] == "":
                    free_ids.append(artist["id"])
                else:
                    labels[artist["id"]] = artist["name"] + " (booked)"
            # Booked artists stay in the list, so trying one shows why it is refused (FA R1).
            # The form starts on the first artist who is still free.
            ids = list(labels)
            first = 0
            if len(free_ids) > 0:
                first = ids.index(free_ids[0])
            names = logic.stage_names()
            artist_id = st.selectbox("Artist", ids, index=first, format_func=labels.get, key="book_artist")
            stage_id = st.segmented_control("Stage", list(names), format_func=names.get,
                                            default=list(names)[0], required=True, key="book_stage")
            start = to_text(st.time_input("Start", value=time(14, 0), step=60, key="book_start"))
            artist = logic.artists_by_id()[artist_id]
            show_end(start, artist)

            if st.button("Book", key="book", type="primary"):
                end = logic.end_time(start, artist["duration"])
                finish_click(logic.add_booking(artist_id, stage_id, start),
                             artist["name"] + " booked on " + names[stage_id] + ", " + start + "–" + end + ".")
            show_message()


# ---------- screen 3: change a booking ----------

def show_change():
    """FA04: move a booking to another stage or time, or remove it, under the timeline."""
    st.title("Change a booking")

    bookings = logic.all_bookings()
    if len(bookings) == 0:
        st.info("Nothing booked yet. Book an artist first.")
        show_message()
        return
    if logic.is_final():
        st.info(logic.FINAL_PLAN)
        return

    show_timeline()
    with card("change"):
        artists = logic.artists_by_id()
        names = logic.stage_names()
        labels = {}
        for booking in bookings:
            labels[booking["artist_id"]] = artists[booking["artist_id"]]["name"]

        pick, where, when = st.columns(3)
        artist_id = pick.selectbox("Booking", list(labels), format_func=labels.get, key="change_booking")
        booking = logic.booking_for(artist_id)
        artist = artists[artist_id]
        # The keys contain the artist, so the fields start from this booking when you pick another one.
        stage_id = where.segmented_control("Stage", list(names), format_func=names.get,
                                           default=booking["stage_id"], required=True,
                                           key="change_stage_" + str(artist_id))
        start = to_text(when.time_input("Start", value=to_time(booking["start"]), step=60,
                                        key="change_start_" + str(artist_id)))

        now = (names[booking["stage_id"]] + ", " + booking["start"] + "–"
               + logic.end_time(booking["start"], artist["duration"]))
        st.html('<span class="badge">Now: ' + html.escape(now) + "</span>")
        show_end(start, artist)

        with st.container(horizontal=True):
            if st.button("Save change", key="move", type="primary"):
                end = logic.end_time(start, artist["duration"])
                finish_click(logic.move_booking(artist_id, stage_id, start),
                             artist["name"] + " moved to " + names[stage_id] + ", " + start + "–" + end + ".")
            if st.button("Remove booking", key="remove"):
                finish_click(logic.remove_booking(artist_id),
                             artist["name"] + " removed. " + logic.euros(artist["fee"])
                             + " back in the budget.")
        show_message()


# ---------- this part runs on every click ----------

st.set_page_config(page_title="Festival Architect", page_icon=":material/festival:", layout="wide")
st.html(STYLE_FILE)
db.ensure_database()

with st.sidebar:
    st.html('<div class="brand">' + logic.FESTIVAL_NAME + '</div><div class="brand-sub">Festival Architect · '
            + logic.DOORS_OPEN + "–" + logic.CURFEW + "</div>")
    screen = st.radio("Screen", SCREENS, format_func=screen_label,
                      key="screen", label_visibility="collapsed")
    if logic.is_final():
        st.html('<span class="badge"><span class="dot ok"></span>Final plan</span>')
    else:
        st.html('<span class="badge"><span class="dot warn"></span>Draft plan</span>')
    st.caption("Saved in data/festival.db. Start over with `uv run python seed.py`.")

if screen == "Timetable":
    show_timetable()
elif screen == "Book an artist":
    show_booking()
else:
    show_change()
