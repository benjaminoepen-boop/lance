"""LN R21 and scenario A6: the calendar file reminds of every bidding and add/drop window, and every calendar app reads it the same way."""
import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest

import logic
from conftest import add_all

NOV_11 = "2026-11-11"


def unfolded(body):
    """The lines of the file as a calendar app reads them: a line that starts with a space goes on from the one before."""
    return body.replace("\r\n ", "").split("\r\n")


def events_of(body):
    """Every event of the file as {name: value}. Its reminder is a {name: value} of its own, under "VALARM"."""
    events, event, alarm = [], None, None
    for line in unfolded(body):
        if line == "BEGIN:VEVENT":
            event = {}
        elif line == "BEGIN:VALARM":
            alarm = {}
        elif line == "END:VALARM":
            event["VALARM"], alarm = alarm, None
        elif line == "END:VEVENT":
            events.append(event)
            event = None
        elif event is not None:
            name, value = line.split(":", 1)
            (event if alarm is None else alarm)[name] = value
    return events


def windows(body):
    """The all-day events of the file: the bidding and add/drop windows."""
    return [event for event in events_of(body) if "DTSTART;VALUE=DATE" in event]


def window(body, label):
    return next(event for event in windows(body) if event["SUMMARY"] == label)


def reminder(event):
    """When the reminder of an all-day event rings: its trigger, counted from midnight of the first day."""
    sign, days, hours, minutes = re.fullmatch(r"(-?)P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?", event["VALARM"]["TRIGGER"]).groups()
    shift = timedelta(days=int(days or 0), hours=int(hours or 0), minutes=int(minutes or 0))
    return datetime.strptime(event["DTSTART;VALUE=DATE"], "%Y%m%d") + (-shift if sign else shift)


# ---------- LN R21: the windows to bid in ----------

def test_on_11_november_the_spring_bidding_is_an_all_day_event_with_a_reminder_the_day_before(plan):
    spring = window(logic.calendar_file(plan, today=NOV_11), "Spring enrolments (bidding)")
    assert spring["DTSTART;VALUE=DATE"] == "20270118"
    assert spring["DTEND;VALUE=DATE"] == "20270121"     # the standard ends an all-day event on the day after the last
    assert reminder(spring) == datetime(2027, 1, 17, 9, 0)
    assert spring["VALARM"]["ACTION"] == "DISPLAY"
    assert spring["TRANSP"] == "TRANSPARENT"            # a window is not a meeting: the student is not busy


def test_windows_that_have_ended_are_not_in_the_file(plan):
    # On 11 November the fall bidding (21 to 23 July) and the add/drop of T1 and T2 are over.
    labels = [event["SUMMARY"] for event in windows(logic.calendar_file(plan, today=NOV_11))]
    assert labels == ["Spring enrolments (bidding)", "Add/drop T3", "Add/drop T4"]


def test_a_window_stays_in_the_file_until_its_last_day(plan):
    def labels(today):
        return [event["SUMMARY"] for event in windows(logic.calendar_file(plan, today=today))]
    assert "Spring enrolments (bidding)" in labels("2027-01-20")
    assert "Spring enrolments (bidding)" not in labels("2027-01-21")


def test_a_window_says_that_bids_only_count_on_novas_platform(plan):
    note = window(logic.calendar_file(plan, today=NOV_11), "Add/drop T3")["DESCRIPTION"]
    assert "Nova's platform" in note
    assert "https://bidding.novasbe.pt/" in note


# ---------- A6: the classes and exams stay as they were ----------

def test_every_class_and_exam_is_still_in_the_file(plan):
    add_all(plan, "2477-S1-TXB")
    events = events_of(logic.calendar_file(plan, today=NOV_11))
    assert len([event for event in events if "DTSTART;TZID=Europe/Lisbon" in event]) == 13   # 12 classes and the exam, as before
    assert len(events) == 13 + 3                                                             # and the three windows to come


def test_every_event_keeps_its_uid_from_one_file_to_the_next(plan):
    # A calendar app knows an event by its UID: the same UID again replaces it instead of adding it twice.
    add_all(plan, "2477-S1-TXB")
    first = [event["UID"] for event in events_of(logic.calendar_file(plan, today=NOV_11))]
    later = [event["UID"] for event in events_of(logic.calendar_file(plan, today="2027-01-19"))]
    assert len(set(first)) == len(first)
    assert later == first


# ---------- every calendar app reads the file the same way (RFC 5545) ----------

def test_no_line_is_longer_than_75_bytes(plan):
    assert logic.load_example(plan) is None
    body = logic.calendar_file(plan, today=NOV_11)
    assert max(len(line.encode()) for line in body.split("\r\n")) <= 75
    assert max(len(line.encode()) for line in unfolded(body)) > 75      # the note of a window had to be folded


def test_folding_counts_bytes_and_keeps_the_text():
    line = "LOCATION:" + "Auditório Alfredo de Sousa, Nova SBE, Carcavelos. " * 4
    folded = logic.ics_fold(line)
    assert all(len(part.encode()) <= 75 for part in folded.split("\r\n"))   # ó is two bytes
    assert folded.replace("\r\n ", "") == line


def test_lisbon_is_defined_exactly_once(plan):
    lines = unfolded(logic.calendar_file(plan, today=NOV_11))
    assert lines.count("BEGIN:VTIMEZONE") == 1
    assert lines[lines.index("BEGIN:VTIMEZONE") + 1] == "TZID:Europe/Lisbon"


def test_summer_and_winter_time_in_the_file_match_the_time_zone_database(plan):
    """Lisbon's clock is typed into logic.py by hand. It must switch at the moments Python's time zone database knows."""
    try:
        lisbon = ZoneInfo("Europe/Lisbon")
    except ZoneInfoNotFoundError:
        pytest.skip("this computer has no time zone database")
    lines = unfolded(logic.calendar_file(plan, today=NOV_11))
    for part in ("DAYLIGHT", "STANDARD"):
        rule = dict(line.split(":", 1) for line in lines[lines.index("BEGIN:" + part) + 1:lines.index("END:" + part)])
        month = int(re.search(r"BYMONTH=(\d+)", rule["RRULE"]).group(1))
        assert "BYDAY=-1SU" in rule["RRULE"]                                  # the last Sunday of that month
        before, after = int(rule["TZOFFSETFROM"][:3]), int(rule["TZOFFSETTO"][:3])
        for year in (2026, 2027):
            last_day = date(year, month + 1, 1) - timedelta(days=1)
            sunday = last_day - timedelta(days=(last_day.weekday() + 1) % 7)
            local = datetime.combine(sunday, datetime.strptime(rule["DTSTART"][9:], "%H%M%S").time())
            switch = (local - timedelta(hours=before)).replace(tzinfo=timezone.utc)
            assert (switch - timedelta(minutes=1)).astimezone(lisbon).utcoffset() == timedelta(hours=before)
            assert switch.astimezone(lisbon).utcoffset() == timedelta(hours=after)
