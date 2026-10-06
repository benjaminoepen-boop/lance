"""Business rules of Festival Architect: festival hours, clashes, the budget, draft or final."""
import db

FESTIVAL_NAME = "Carcavelos Sound"
DOORS_OPEN = "14:00"
CURFEW = "23:00"
BUDGET = 10000
ARTISTS_NEEDED_TO_FINALISE = 4
FINAL_PLAN = "The plan is final. Reopen it as a draft to change the lineup."


# ---------- times and money ----------

def to_minutes(clock):
    """Turn '16:30' into minutes after midnight (990), so times can be compared and added."""
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def to_clock(minutes):
    """Turn minutes after midnight back into 'HH:MM' text: 990 -> '16:30'."""
    return str(minutes // 60).zfill(2) + ":" + str(minutes % 60).zfill(2)


def end_time(start, duration):
    """FA02: a set ends its duration (in minutes) after it starts."""
    return to_clock(to_minutes(start) + duration)


def overlaps(start_a, end_a, start_b, end_b):
    """FA R2: two slots clash when each one starts before the other ends. Touching is fine."""
    return to_minutes(start_a) < to_minutes(end_b) and to_minutes(start_b) < to_minutes(end_a)


def inside_festival_hours(start, end):
    """FA R2: start at or after doors open, end at or before the curfew."""
    return to_minutes(start) >= to_minutes(DOORS_OPEN) and to_minutes(end) <= to_minutes(CURFEW)


def within_budget(total):
    """FA R4: spending exactly the budget is allowed, one euro more is not."""
    return total <= BUDGET


def euros(amount):
    """Format money the same way everywhere: 10000 -> '€10,000'."""
    return "€" + format(amount, ",")


# ---------- reading the plan ----------

def artists_by_id():
    """The catalogue as {artist id: artist}, so a booking can find its artist."""
    artists = {}
    for artist in db.load_artists():
        artists[artist["id"]] = artist
    return artists


def stage_names():
    """The stages as {stage id: name}, e.g. {'A': 'Beach Stage', 'B': 'Dune Stage'}."""
    names = {}
    for stage in db.load_stages():
        names[stage["id"]] = stage["name"]
    return names


def all_bookings():
    """Every saved booking: {'artist_id': 1, 'stage_id': 'A', 'start': '16:00'}."""
    return db.load_bookings()


def booking_for(artist_id):
    """The saved booking of one artist, or None when the artist is not booked."""
    for booking in all_bookings():
        if booking["artist_id"] == artist_id:
            return booking
    return None


def without(artist_id, bookings):
    """The same bookings minus the one of this artist."""
    others = []
    for booking in bookings:
        if booking["artist_id"] != artist_id:
            others.append(booking)
    return others


def is_final():
    """True when the plan is final and therefore read-only (FA05)."""
    return db.load_status() == "final"


def total_fees(bookings=None):
    """FA R1: each booked artist's fee counts once. Without an argument: the saved lineup."""
    if bookings is None:
        bookings = all_bookings()
    artists = artists_by_id()
    total = 0
    for booking in bookings:
        total = total + artists[booking["artist_id"]]["fee"]
    return total


def remaining_budget():
    """FA03: what is left of the artist budget after the saved bookings."""
    return BUDGET - total_fees()


def slot_start(row):
    """Sort key: the start of a slot in minutes."""
    return to_minutes(row["start"])


def timetable(stage_id):
    """FA03: the performances on one stage in time order, each with its end time and artist."""
    artists = artists_by_id()
    rows = []
    for booking in all_bookings():
        if booking["stage_id"] != stage_id:
            continue
        artist = artists[booking["artist_id"]]
        rows.append({
            "artist_id": artist["id"],
            "start": booking["start"],
            "end": end_time(booking["start"], artist["duration"]),
            "name": artist["name"],
            "genre": artist["genre"],
            "fee": artist["fee"],
        })
    rows.sort(key=slot_start)
    return rows


def catalogue():
    """FA01: every artist, with the slot they are booked in, or '' while they are still free."""
    names = stage_names()
    rows = []
    for artist in db.load_artists():
        row = dict(artist)
        row["booked"] = ""
        booking = booking_for(artist["id"])
        if booking is not None:
            row["booked"] = (names[booking["stage_id"]] + ", " + booking["start"] + "–"
                             + end_time(booking["start"], artist["duration"]))
        rows.append(row)
    return rows


# ---------- the rules ----------

def booking_problems(artist_id, stage_id, start, other_bookings):
    """Check one performance against the rest of the lineup and return every reason to refuse it.

    An empty list means the booking is fine. other_bookings must not contain the booking that
    is being edited: an edit is checked as a replacement of the old booking (FA R5).
    """
    artists = artists_by_id()
    names = stage_names()
    artist = artists[artist_id]
    end = end_time(start, artist["duration"])
    problems = []

    # FA R1: an artist plays at most once
    for booking in other_bookings:
        if booking["artist_id"] == artist_id:
            problems.append(artist["name"] + " is already in the lineup.")

    # FA R2: inside festival hours
    if not inside_festival_hours(start, end):
        problems.append(start + "–" + end + " is outside festival hours (" + DOORS_OPEN + "–"
                        + CURFEW + ").")

    # FA R2 and R3: no overlap on the same stage; the other stage does not matter
    for booking in other_bookings:
        if booking["stage_id"] != stage_id:
            continue
        other = artists[booking["artist_id"]]
        other_end = end_time(booking["start"], other["duration"])
        if overlaps(start, end, booking["start"], other_end):
            problems.append("Clashes with " + other["name"] + " on " + names[stage_id] + " ("
                            + booking["start"] + "–" + other_end + ").")

    # FA R4: fees stay within the budget
    total = total_fees(other_bookings) + artist["fee"]
    if not within_budget(total):
        problems.append("Fees would reach " + euros(total) + ", over the " + euros(BUDGET)
                        + " budget.")

    return problems


def lineup_problems(bookings):
    """Re-check a whole lineup, each booking against the ones before it. Empty for any lineup this app saved."""
    problems = []
    checked = []
    for booking in bookings:
        problems.extend(booking_problems(booking["artist_id"], booking["stage_id"],
                                         booking["start"], checked))
        checked.append(booking)
    return problems


# ---------- the actions: check first, write only when nothing is wrong ----------

def add_booking(artist_id, stage_id, start):
    """FA02: book an artist. Returns the reasons it was refused; an empty list means it was saved."""
    if is_final():
        return [FINAL_PLAN]
    problems = booking_problems(artist_id, stage_id, start, all_bookings())
    if len(problems) == 0:
        db.insert_booking(artist_id, stage_id, start)
    return problems


def move_booking(artist_id, stage_id, start):
    """FA04: give a booked artist another stage or start time. A refused edit keeps the old booking."""
    if is_final():
        return [FINAL_PLAN]
    if booking_for(artist_id) is None:
        return ["This artist is not booked."]
    others = without(artist_id, all_bookings())
    problems = booking_problems(artist_id, stage_id, start, others)
    if len(problems) == 0:
        db.update_booking(artist_id, stage_id, start)
    return problems


def remove_booking(artist_id):
    """FA04: take an artist out of the lineup, which frees the slot and the whole fee (FA R1)."""
    if is_final():
        return [FINAL_PLAN]
    db.delete_booking(artist_id)
    return []


def finalise():
    """FA05: lock the plan. Needs at least four artists and a lineup that passes every rule."""
    if is_final():
        return ["The plan is already final."]
    bookings = all_bookings()
    problems = []
    if len(bookings) < ARTISTS_NEEDED_TO_FINALISE:
        problems.append("Book at least " + str(ARTISTS_NEEDED_TO_FINALISE)
                        + " artists before finalising. The lineup has " + str(len(bookings)) + ".")
    problems.extend(lineup_problems(bookings))
    if len(problems) == 0:
        db.save_status("final")
    return problems


def reopen():
    """FA05: turn a final plan back into a draft that can be changed."""
    db.save_status("draft")
