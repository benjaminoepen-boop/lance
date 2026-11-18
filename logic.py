"""Business rules of Lance: clashes, prices, points, shared price data.

The rule ids (LN R1 ...) point to docs/product-brief.md. The clash check and the budget check grew out of
the solo project Festival Architect: a stage became a student's week, an artist became a course section,
a fee became a bid and the festival budget became the points balance.
"""
import math
import re
import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, datetime, timezone
from functools import lru_cache

import db

MAX_ECTS = 31.5            # LN R8: mandatory and elective courses per semester
RECOMMENDED_ECTS = 28.0
# LN02: what a plan holds in one semester. LN R8 leaves room for 9 courses of 3.5 ECTS on the mandatory and primary
# lists; 40 entries add backup sections and a long alternate list, and keep every answer fast.
MAX_ENTRIES = 40
FULL = f"A plan holds at most {MAX_ENTRIES} entries in a semester."
BONUS = 1.1                # LN R7: rank value of part of the students with 45 or more ECTS passed
# LN R17: two rough reference values from the team's own accounts, as (ECTS in mandatory courses, points).
# Nova does not publish how it sets the points, so this is an estimate until the student types the real number.
POINTS_AT = ((20, 140), (23, 120))
RATING_PAGE = "https://uni-feedback.com/en/courses/"   # LN07: where a course's reviews can be read
BID_MARGIN = {"exact": 1.00, "plus10": 1.10, "plus25": 1.25}   # on top of last round's cut-off
WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# ---------- requests no page sends ----------

class Malformed(ValueError):
    """A request no page of Lance sends, like a list where an id belongs or Infinity as points. It is refused before
    anything is written, and app.py answers it with 400 and this sentence, where it used to fail with 500."""


def checked_id(value):
    """Course and section ids arrive as text, or not at all."""
    if value is None or isinstance(value, str):
        return value
    raise Malformed("An id is text.")


def checked_entry(value):
    """An entry is named by its number from the state. True is no number here, and SQLite holds at most 2**63 - 1."""
    if value is None or (type(value) is int and 0 < value < 2 ** 63):
        return value
    raise Malformed("An entry is named by its number.")


def checked_points(value):
    """Points arrive as typed, as text or as a number, or not at all. Infinity and NaN are no points."""
    if value is None or isinstance(value, str) or type(value) is int or (type(value) is float and math.isfinite(value)):
        return value
    raise Malformed("Points are a number.")


# ---------- times (from Festival Architect) ----------

def to_minutes(clock):
    """Turn '16:30' into minutes after midnight (990), so times can be compared and added."""
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def to_clock(minutes):
    """Turn minutes after midnight back into 'HH:MM' text: 990 -> '16:30'."""
    return str(minutes // 60).zfill(2) + ":" + str(minutes % 60).zfill(2)


def overlaps(start_a, end_a, start_b, end_b):
    """LN R1: two slots clash when each one starts before the other ends. Touching is fine."""
    return to_minutes(start_a) < to_minutes(end_b) and to_minutes(start_b) < to_minutes(end_a)


def day_label(iso_date):
    """'2026-12-04' becomes 'Fri 4 Dec'."""
    day = date.fromisoformat(iso_date)
    return WEEKDAY_NAMES[day.weekday()] + " " + str(day.day) + " " + day.strftime("%b")


# ---------- the catalogue (content never changes while the app runs) ----------

@lru_cache(maxsize=1)
def all_meetings():
    """{section id: its weekly meetings}."""
    grouped = defaultdict(list)
    for meeting in sorted(db.load_meetings(), key=lambda row: (WEEKDAY_NAMES.index(row["day"]), row["start"])):
        grouped[meeting["section_id"]].append(meeting)
    return dict(grouped)


@lru_cache(maxsize=1)
def all_sessions():
    """{section id: every single class of that section with its date}."""
    grouped = defaultdict(list)
    for session in db.load_all_sessions():
        grouped[session["section_id"]].append(session)
    return dict(grouped)


@lru_cache(maxsize=1)
def all_offerings():
    return {offering["id"]: offering for offering in db.load_offerings()}


@lru_cache(maxsize=1)
def all_sections():
    return {section["id"]: section for section in db.load_sections()}


@lru_cache(maxsize=1)
def all_exams():
    """{(code, term): its exams, midterms and presentations}; make-up exams are kept apart."""
    grouped = defaultdict(list)
    for exam in db.load_exams():
        grouped[(exam["code"], exam["term"])].append(exam)
    return dict(grouped)


@lru_cache(maxsize=1)
def all_ratings():
    """LN07: {course code: its rating on Uni Feedback}, with the address of its reviews there."""
    return {row["code"]: {"rating": row["rating"], "reviews": row["reviews"], "workload": row["workload"],
                          "url": RATING_PAGE + row["source_id"]}
            for row in db.load_course_ratings()}


def course_rating(code):
    """LN07: what students say about a course on Uni Feedback, or None while nobody has reviewed it there."""
    return all_ratings().get(code)


def forget_catalogue():
    """Used by the tests after they rebuild the database."""
    for function in (all_meetings, all_sessions, all_offerings, all_sections, all_exams, all_ratings):
        function.cache_clear()


def label_of(offering_id, section_id=None):
    """'Introduction to Programming TXB': how a plan entry reads in a message."""
    name = all_offerings()[offering_id]["name"]
    if section_id:
        return name + " " + all_sections()[section_id]["section"]
    return name


def regular_exams(offering):
    """The dated exams, midterms and presentations of one offering, without make-up exams."""
    return [exam for exam in all_exams().get((offering["code"], offering["term"]), [])
            if exam["kind"] in ("exam", "midterm", "presentation") and exam["date"]]


# ---------- LN R1: class clashes, date by date ----------

def sessions_by_date(section_id):
    grouped = defaultdict(list)
    for session in all_sessions().get(section_id, []):
        grouped[session["date"]].append(session)
    return grouped


def clashing_dates(section_a, section_b):
    """Every date on which two sections meet at the same time: [(date, start, end), ...]."""
    dates_b = sessions_by_date(section_b)
    found = []
    for session in all_sessions().get(section_a, []):
        for other in dates_b.get(session["date"], []):
            if overlaps(session["start"], session["end"], other["start"], other["end"]):
                start = max(session["start"], other["start"])
                end = min(session["end"], other["end"])
                found.append((session["date"], start, end))
    return found


def week_of(iso_date):
    """Which half of the semester a date falls in: the planner shows one half at a time."""
    if iso_date <= "2026-10-21":
        return "T1"
    if iso_date <= "2026-12-31":
        return "T2"
    return "T3" if iso_date <= "2027-03-31" else "T4"


def chosen_sections(items):
    """The plan entries that have a timetable."""
    return [item for item in items if item["section_id"]]


def week_items(items):
    """LN R13: what the student would really sit in: the first section of each course on the mandatory and primary lists.

    Backup sections and the alternate list only matter if something else falls through.
    """
    first = {}
    for item in sorted(items, key=lambda entry: entry["position"]):
        if item["list"] in ("mandatory", "primary") and item["offering_id"] not in first:
            first[item["offering_id"]] = item
    return list(first.values())


def conflicts_with_week(item, items, week):
    """LN R13: what a backup or an alternate runs into. It is said in its own row and is not a clash of the week.

    An alternate is checked against everything on the mandatory and primary lists, a backup against the week.
    Nova: "the system will not allow enrollments in courses that have overlapping exams. The same happens with
    the courses placed on the Alternate List."
    """
    in_week = {entry["id"] for entry in week}
    others = [entry for entry in items if entry["offering_id"] != item["offering_id"] and entry["list"] in ("mandatory", "primary")]
    if item["list"] != "alternate":
        others = [entry for entry in others if entry["id"] in in_week]
    found = []
    if item["section_id"]:
        for entry in chosen_sections(others):
            if clashing_dates(item["section_id"], entry["section_id"]):
                suffix = "" if entry["id"] in in_week else " (if you land there)"
                found.append({"level": "class", "text": "Clashes with " + label_of(entry["offering_id"], entry["section_id"]) + suffix})
    firm = [entry for entry in week if entry["offering_id"] != item["offering_id"]]
    if item["list"] == "alternate":
        for clash in exam_clashes(firm + [item]):
            if item["offering_id"] in clash["offerings"]:
                other = next(oid for oid in clash["offerings"] if oid != item["offering_id"])
                name = all_offerings()[other]["name"]
                if clash["kind"] == "exam":
                    found.append({"level": "exam", "text": "Exam at the same time as " + name + ". Nova will not enroll you in both."})
                else:
                    found.append({"level": "midterm", "text": "Midterm clash with " + name + ". Nova does not check this."})
    else:
        for clash in midterm_class_clashes(firm + [item]):
            if clash["second"] == label_of(item["offering_id"], item["section_id"]) and item["section_id"]:
                found.append({"level": "midterm", "text": "Meets during the midterm of " + clash["first"].replace(" (midterm)", "") + "."})
    return found


def class_clashes(items):
    """LN R1: every pair of different courses in the plan that meet at the same time.

    Two sections of one course never clash: bidding on TXA and TXB means taking only one of them.
    """
    clashes = []
    entries = chosen_sections(items)
    for i, first in enumerate(entries):
        for second in entries[i + 1:]:
            if first["offering_id"] == second["offering_id"]:
                continue
            dates = clashing_dates(first["section_id"], second["section_id"])
            if dates:
                total = len(all_sessions().get(first["section_id"], []))
                clashes.append({
                    "kind": "class",
                    "severity": "class",
                    "items": [first["id"], second["id"]],
                    "offerings": [first["offering_id"], second["offering_id"]],
                    "first": label_of(first["offering_id"], first["section_id"]),
                    "second": label_of(second["offering_id"], second["section_id"]),
                    "times": len(dates),
                    "of": total,
                    "when": day_label(dates[0][0]) + ", " + dates[0][1] + "–" + dates[0][2],
                    "dates": [day_label(d[0]) for d in dates],
                    "weeks": sorted({week_of(d[0]) for d in dates}),
                })
    return clashes


# ---------- LN R2: exams and midterms ----------

def exam_clashes(items):
    """LN R2: exams that overlap (the platform blocks these) and midterms that overlap (it does not check them)."""
    offerings = []
    for offering_id in sorted({item["offering_id"] for item in items}):
        offerings.append(all_offerings()[offering_id])
    clashes = []
    for i, first in enumerate(offerings):
        for second in offerings[i + 1:]:
            for exam_a in regular_exams(first):
                for exam_b in regular_exams(second):
                    if exam_a["date"] != exam_b["date"]:
                        continue
                    if overlaps(exam_a["start"], exam_a["end"], exam_b["start"], exam_b["end"]):
                        both_exams = exam_a["kind"] == "exam" and exam_b["kind"] == "exam"
                        clashes.append({
                            "kind": "exam" if both_exams else "midterm",
                            "severity": "exam" if both_exams else "midterm",
                            "offerings": [first["id"], second["id"]],
                            "first": first["name"] + " (" + exam_a["kind"] + ")",
                            "second": second["name"] + " (" + exam_b["kind"] + ")",
                            "when": day_label(exam_a["date"]) + ", " + exam_a["start"],
                        })
    clashes.extend(midterm_class_clashes(items))
    return clashes


def exam_days(items):
    """LN R16: two exams of different courses on one date, one after the other. The platform allows it, so it is not
    a clash and is not counted as one; it is a hard day, and Lance says so. Midterms and presentations do not count."""
    offerings = [all_offerings()[offering_id] for offering_id in sorted({item["offering_id"] for item in items})]
    days = []
    for i, first in enumerate(offerings):
        for second in offerings[i + 1:]:
            for exam_a in regular_exams(first):
                for exam_b in regular_exams(second):
                    if exam_a["kind"] == "exam" and exam_b["kind"] == "exam" and exam_a["date"] == exam_b["date"] \
                            and not overlaps(exam_a["start"], exam_a["end"], exam_b["start"], exam_b["end"]):
                        days.append({"offerings": [first["id"], second["id"]], "first": first["name"], "second": second["name"],
                                     "date": exam_a["date"], "when": day_label(exam_a["date"])})
    return sorted(days, key=lambda day: day["date"])


def exam_day_warnings(items, semester):
    """LN R16 before adding: {course not in the plan: the names of the week's courses it would share an exam day with}."""
    planned = {item["offering_id"] for item in items}
    week = [all_offerings()[item["offering_id"]] for item in week_items(items)]
    warnings = {}
    for offering_id, offering in all_offerings().items():
        if offering["semester"] != semester or offering_id in planned:
            continue
        names = set()
        for other in week:
            for exam_a in regular_exams(offering):
                for exam_b in regular_exams(other):
                    if exam_a["kind"] == "exam" and exam_b["kind"] == "exam" and exam_a["date"] == exam_b["date"] \
                            and not overlaps(exam_a["start"], exam_a["end"], exam_b["start"], exam_b["end"]):
                        names.add(other["name"])
        if names:
            warnings[offering_id] = sorted(names)
    return warnings


def midterm_class_clashes(items):
    """LN R2: a midterm of one course during a class of another. The platform does not check these either."""
    clashes = []
    entries = chosen_sections(items)
    for offering_id in sorted({item["offering_id"] for item in items}):
        offering = all_offerings()[offering_id]
        for exam in regular_exams(offering):
            if exam["kind"] != "midterm":
                continue
            for entry in entries:
                if entry["offering_id"] == offering_id:
                    continue
                for session in all_sessions().get(entry["section_id"], []):
                    if session["date"] == exam["date"] and overlaps(session["start"], session["end"], exam["start"], exam["end"]):
                        clashes.append({
                            "kind": "midterm",
                            "severity": "midterm",
                            "offerings": [offering_id, entry["offering_id"]],
                            "first": offering["name"] + " (midterm)",
                            "second": label_of(entry["offering_id"], entry["section_id"]),
                            "when": day_label(exam["date"]) + ", " + exam["start"],
                        })
    return clashes


def section_warnings(items, semester):
    """For the course list, before anything is added: what would each section clash with?

    Returns {section id: ['Advanced Strategy TXC', ...]} and {offering id: ['Exam clash with ...', ...]}.
    """
    week = week_items(items)
    entries = chosen_sections(week)
    per_section = {}
    per_offering = {}
    planned = {item["offering_id"] for item in items}
    in_week = {item["offering_id"] for item in week}
    for section_id, section in all_sections().items():
        offering = all_offerings()[section["offering_id"]]
        if offering["semester"] != semester:
            continue
        names = []
        for entry in entries:
            if entry["offering_id"] == section["offering_id"]:
                continue
            dates = clashing_dates(section_id, entry["section_id"])
            if dates:
                halves = sorted({week_of(date_[0]) for date_ in dates})
                only = " (" + halves[0] + ")" if len(halves) == 1 and offering["term"] in ("S1", "S2") else ""
                names.append(label_of(entry["offering_id"], entry["section_id"]) + only)
        if names:
            per_section[section_id] = names
    for offering_id, offering in all_offerings().items():
        if offering["semester"] != semester or offering_id in planned:
            continue
        notes = []
        for other_id in in_week:
            other = all_offerings()[other_id]
            for exam_a in regular_exams(offering):
                for exam_b in regular_exams(other):
                    if exam_a["kind"] == "exam" and exam_b["kind"] == "exam" and exam_a["date"] == exam_b["date"] \
                            and overlaps(exam_a["start"], exam_a["end"], exam_b["start"], exam_b["end"]):
                        notes.append(other["name"])
        if notes:
            per_offering[offering_id] = sorted(set(notes))
    return per_section, per_offering


# ---------- LN R3 to R7: prices and points ----------

def price_primary(bid, lowest_successful_bid):
    """LN R3: 'the average between the points allocated to the bid and those given by the last student
    who successfully gets a seat'. The last student is counted across the whole course, not the section."""
    return (bid + lowest_successful_bid) / 2


def price_alternate(bid, balance):
    """LN R4: 'the smaller number between the points allocated to the bid and the remaining points'."""
    return min(bid, balance)


def price_add_drop(bid):
    """LN R5: 'the actual points allocated to the bid'."""
    return bid


def rank_value(bid, has_bonus):
    """LN R7: part of the students with 45 or more ECTS passed rank with their bid times 1.1."""
    return round(bid * BONUS, 2) if has_bonus else float(bid)


def reserved_points(items):
    """LN R6: what the primary list takes from the balance: the highest bid per course, once."""
    highest = {}
    for item in items:
        if item["list"] != "primary" or item["bid"] is None:
            continue
        highest[item["offering_id"]] = max(highest.get(item["offering_id"], 0), item["bid"])
    return sum(highest.values())


def round_order(name):
    """LN R18: when a round ran, to tell the newest. 'Spring 2026' ran in January 2026, 'Fall 2026' in July 2026.
    A name Lance does not write itself counts as the oldest."""
    season, _, year = name.partition(" ")
    if season not in ("Spring", "Fall") or not (year.isascii() and year.isdigit()):
        return (0, 0)
    return (int(year), 0 if season == "Spring" else 1)


def last_round(rows):
    """LN04 and LN R18: only the newest round is last round. A list of an older year stays stored but never mixes in."""
    newest = max((round_order(row["round"]) for row in rows), default=None)
    return [row for row in rows if round_order(row["round"]) == newest]


def last_rounds(rows):
    """last_round for each course, term and list on its own."""
    groups = defaultdict(list)
    for row in rows:
        groups[(row["code"], row["term"], row["list"])].append(row)
    return [row for group in groups.values() for row in last_round(group)]


def past_prices(code, term, list_name="primary"):
    """The cut-offs of last round for a course: this term first, otherwise any other term as a rough hint.

    Returns (rows, exact) where exact is False when the numbers come from another term.
    """
    rows = [row for row in db.load_cutoffs(code) if row["list"] == list_name]
    same_term = [row for row in rows if row["term"] == term]
    return (last_round(same_term), True) if same_term else (last_round(rows), False)


def lowest_bid_in_course(code, term):
    """The lowest successful bid across all known sections of a course: what the price is measured against."""
    rows, _ = past_prices(code, term)
    bids = [row["min_bid"] for row in rows if row["min_bid"] is not None]
    return min(bids) if bids else None


def cutoff_for(code, term, section):
    """The rank value that just got a seat in this section last round, or None without data."""
    rows, _ = past_prices(code, term)
    for row in rows:
        if row["section"] == section and row["min_rank_value"] is not None:
            return row["min_rank_value"]
    return None


def suggest_bid(cutoff, has_bonus, margin):
    """A bid that would have beaten last round's cut-off with a margin for how much the course matters."""
    if cutoff is None:
        return None
    needed = cutoff / (BONUS if has_bonus else 1)
    return math.ceil(needed * BID_MARGIN[margin])


def bid_analysis(item, plan):
    """What one bid would have meant last round, for the bids page."""
    offering = all_offerings()[item["offering_id"]]
    section = all_sections()[item["section_id"]]["section"] if item["section_id"] else None
    list_name = "alternate" if item["list"] == "alternate" else "primary"
    rows, exact = past_prices(offering["code"], offering["term"], list_name)
    if list_name == "alternate" and not rows:
        rows, exact = past_prices(offering["code"], offering["term"], "primary")
    row = next((r for r in rows if r["section"] == section), None)
    lowest = lowest_bid_in_course(offering["code"], offering["term"])
    has_bonus = bool(plan["has_bonus"])
    result = {
        "known": row is not None or (not section and bool(rows)),
        "exact": exact,
        "round": rows[0]["round"] if rows else None,
        "cutoff": row["min_rank_value"] if row else None,
        "top": row["max_rank_value"] if row else None,
        "seats": row["seats"] if row else None,
        "bids": row["bids"] if row else None,
        "zero_bids": row["zero_bids"] if row else None,
        "lowest_in_course": lowest,
        "suggestions": {},
    }
    if row is not None:
        result["histogram"] = [{"from": h["bucket_from"], "to": h["bucket_to"], "bids": h["bids"], "allocated": h["allocated"]}
                               for h in db.load_histograms(offering["code"])
                               if h["term"] == row["term"] and h["section"] == section and h["list"] == row["list"] and h["round"] == row["round"]]
    if not section and rows:
        result["cutoff"] = min((r["min_rank_value"] for r in rows if r["min_rank_value"] is not None), default=None)
        result["cutoff_high"] = max((r["min_rank_value"] for r in rows if r["min_rank_value"] is not None), default=None)
        result["top"] = max((r["max_rank_value"] for r in rows if r["max_rank_value"] is not None), default=None)
    for margin in BID_MARGIN:
        result["suggestions"][margin] = suggest_bid(result["cutoff"], has_bonus, margin)
    bid = item["bid"]
    if bid is not None:
        result["rank_value"] = rank_value(bid, has_bonus)
        if result["cutoff"] is not None:
            result["would_win"] = result["rank_value"] >= result["cutoff"]
        if list_name == "alternate":
            result["price"] = price_alternate(bid, plan["points"])     # LN R4
        elif lowest is not None:
            result["price"] = price_primary(bid, min(lowest, bid))     # LN R3
    return result


def forecast(plan, items):
    """What the plan would cost if last round repeated itself.

    For each course on the primary list: the first section in the bidding order whose cut-off the bid beats.
    Returns the rows, the expected total and the points left for the alternate list and add/drop.
    """
    has_bonus = bool(plan["has_bonus"])
    courses = defaultdict(list)
    for item in items:
        if item["list"] == "primary":
            courses[item["offering_id"]].append(item)
    rows = []
    expected = 0.0
    for offering_id, entries in courses.items():
        offering = all_offerings()[offering_id]
        entries.sort(key=lambda entry: entry["position"])
        lowest = lowest_bid_in_course(offering["code"], offering["term"])
        outcome = {"offering_id": offering_id, "name": offering["name"], "status": "no data", "section": None, "price": None}
        bids = [entry["bid"] for entry in entries if entry["bid"] is not None]
        if not bids:
            outcome["status"] = "no bid"
        for entry in entries:
            if entry["bid"] is None or not entry["section_id"]:
                continue
            section = all_sections()[entry["section_id"]]["section"]
            cutoff = cutoff_for(offering["code"], offering["term"], section)
            if cutoff is None:
                continue
            outcome["status"] = "no seat"
            if rank_value(entry["bid"], has_bonus) >= cutoff and lowest is not None:
                outcome["status"] = "seat"
                outcome["section"] = section
                outcome["price"] = price_primary(entry["bid"], min(lowest, entry["bid"]))
                expected += outcome["price"]
                break
        rows.append(outcome)
    return {"rows": rows, "expected": expected, "left": plan["points"] - expected}


# ---------- LN R8: ECTS ----------

def ects_summary(items):
    """Each course counts once, however many sections are on the list. The alternate list does not count."""
    seen = {}
    for item in items:
        if item["list"] in ("mandatory", "primary"):
            offering = all_offerings()[item["offering_id"]]
            seen[offering["code"]] = offering["ects"]
    total = sum(seen.values())
    return {"total": total, "recommended": RECOMMENDED_ECTS, "maximum": MAX_ECTS, "over": total > MAX_ECTS}


# ---------- the plan ----------

def default_plan_id(programme="", semester="Fall", points=0):
    """A new plan: no programme and no points yet, because those are the student's own. Fall has the only timetable so far."""
    return db.create_plan(programme, semester, points)


def mandatory_ects(items):
    """The ECTS of the mandatory courses among these entries. A course counts once, however many sections are listed."""
    seen = {}
    for item in items:
        if item["list"] == "mandatory":
            offering = all_offerings()[item["offering_id"]]
            seen[offering["code"]] = offering["ects"]
    return sum(seen.values())


def estimated_points(ects):
    """LN R17: the points a student gets for this many mandatory ECTS: a straight line through the two
    reference values, because more mandatory courses leave fewer electives to bid on. Never below zero.
    Without mandatory courses there is nothing to go by, so there is no estimate."""
    if ects <= 0:
        return 0
    (first_ects, first_points), (second_ects, second_points) = POINTS_AT
    per_ects = (second_points - first_points) / (second_ects - first_ects)
    return max(0, round(first_points + (ects - first_ects) * per_ects))


def points_with(plan, items):
    """LN R17: the points of a plan that holds these entries: the number the student typed, otherwise the estimate."""
    typed = db.load_plan(plan["id"])["points"]
    return typed or estimated_points(mandatory_ects(items))


def load_plan(plan_id):
    """The plan as every page and every check uses it. LN R17: while the student has not typed their points,
    'points' is the estimate from their mandatory courses and 'points_estimated' says so."""
    plan = db.load_plan(plan_id)
    if plan is None:
        return None
    typed = plan["points"]
    plan["points"] = points_with(plan, plan_items(plan))
    plan["points_estimated"] = typed == 0 and plan["points"] > 0
    return plan


def in_semester(items, semester):
    """The entries among these that belong to one semester."""
    return [item for item in items if all_offerings()[item["offering_id"]]["semester"] == semester]


def next_position(items, list_name):
    positions = [item["position"] for item in items if item["list"] == list_name]
    return max(positions) + 1 if positions else 1


def kind_for(plan, offering_id):
    return db.load_programme_kinds(plan["programme"]).get(offering_id, "outside")


def first_fitting_section(items, offering_id):
    """LN R11: the first section of a course that clashes with nothing in the week, otherwise simply its first.

    Only for electives. Nova assigned the section of a mandatory course, so Lance does not guess it.
    """
    sections = sorted((section for section in all_sections().values() if section["offering_id"] == offering_id),
                      key=lambda section: section["section"])
    if not sections:
        return None
    week = [entry for entry in chosen_sections(week_items(items)) if entry["offering_id"] != offering_id]
    for section in sections:
        if not any(clashing_dates(section["id"], entry["section_id"]) for entry in week):
            return section["id"]
    return sections[0]["id"]


def add_to_plan(plan, section_id=None, offering_id=None, list_name=None):
    """Add a section, or a whole course: then LN R11 picks the section. A semester holds at most MAX_ENTRIES (LN02).
    Returns an error text or None."""
    section_id, offering_id = checked_id(section_id), checked_id(offering_id)
    items = db.load_items(plan["id"])
    if section_id:
        section = all_sections().get(section_id)
        if section is None:
            return "Unknown section."
        offering_id = section["offering_id"]
    offering = all_offerings().get(offering_id)
    if offering is None:
        return "Unknown course."
    if offering["semester"] != plan["semester"]:
        return "This course is not offered in the semester of your plan."
    if list_name not in (None, "mandatory", "primary", "alternate"):
        return "Unknown list."
    same_course = sorted((item for item in items if item["offering_id"] == offering_id), key=lambda item: item["position"])
    if not section_id:
        if same_course:
            return "Already in your plan."
        section_id = first_fitting_section(items, offering_id)
        if section_id and kind_for(plan, offering_id) == "mandatory":
            return "Pick the section Nova assigned you."
    if any(item["section_id"] == section_id for item in same_course):
        return "Already in your plan."
    if list_name is None:
        if same_course:
            list_name = same_course[0]["list"]
        elif kind_for(plan, offering_id) == "mandatory":
            list_name = "mandatory"
        else:
            list_name = "primary"
    if len(in_semester(items, plan["semester"])) >= MAX_ENTRIES:
        return FULL
    bid = same_course[0]["bid"] if same_course else None   # LN R14: only the highest is held anyway (LN R6)
    try:
        db.insert_item(plan["id"], offering_id, section_id, list_name, next_position(items, list_name), bid)
    except sqlite3.IntegrityError:     # the same click twice, faster than the check above
        return "Already in your plan."
    return None


def switch_section(plan, section_id):
    """LN R12: another section takes over the first place with its bid, the list and the position.

    If it was a backup, the two change places and the bids stay with the places: TXB 164, TXA 100 becomes TXA 164, TXB 100.
    """
    section = all_sections().get(checked_id(section_id))
    if section is None:
        return "Unknown section."
    same_course = sorted((item for item in db.load_items(plan["id"]) if item["offering_id"] == section["offering_id"]),
                         key=lambda item: item["position"])
    if not same_course:
        return add_to_plan(plan, section_id=section_id)
    first = same_course[0]
    backup = next((item for item in same_course if item["section_id"] == section_id), None)
    if backup is None:
        db.update_item(first["id"], section_id=section_id)
    elif backup["id"] != first["id"]:
        db.update_item(first["id"], position=backup["position"], bid=backup["bid"])
        db.update_item(backup["id"], position=first["position"], bid=first["bid"])
    return None


def remove_course(plan, offering_id):
    """LN R15: take a whole course out. Returns what undo needs to put it back, and an error text or None."""
    checked_id(offering_id)
    rows = [item for item in db.load_items(plan["id"]) if item["offering_id"] == offering_id]
    if not rows:
        return [], "This course is not in your plan."
    for row in rows:
        db.delete_item(row["id"])
    return undo_rows(rows), None


def undo_rows(rows):
    """What the browser keeps of removed entries, so that Undo can put them back."""
    return [{name: row[name] for name in ("offering_id", "section_id", "list", "position", "bid")} for row in rows]


def restore_items(plan, rows):
    """LN R15: put back what remove_course took out. The rows come from the browser, so each one is checked first,
    and then they are written all together or not at all."""
    if not isinstance(rows, list) or not rows:
        return "Nothing to put back."
    items = db.load_items(plan["id"])
    if len(in_semester(items, plan["semester"])) + len(rows) > MAX_ENTRIES:     # LN02
        return FULL
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            return "Nothing to put back."
        offering_id, section_id = checked_id(row.get("offering_id")), checked_id(row.get("section_id"))
        offering = all_offerings().get(offering_id)
        section = all_sections().get(section_id) if section_id else None
        if offering is None or offering["semester"] != plan["semester"]:
            return "Unknown course."
        if section_id and (section is None or section["offering_id"] != offering["id"]):
            return "Unknown section."
        if row.get("list") not in ("mandatory", "primary", "alternate"):
            return "Unknown list."
        # positions only grow while you click (removing does not count them again): 2**31 is far beyond that,
        # and far below what SQLite holds. True is no place, although Python counts it as 1.
        position = row.get("position")
        if type(position) is not int or not 1 <= position < 2 ** 31:
            return "Unknown place."
        if any(item["offering_id"] == offering["id"] for item in items):
            return "Already in your plan."
        if (offering["id"], section_id) in seen:
            return "The same entry is in the list twice."
        seen.add((offering["id"], section_id))
    # LN R17: a mandatory course that comes back brings its points along, so the bids are held against the plan as it will be
    points = points_with(plan, items + rows)
    for row in rows:
        bid = row.get("bid")
        if bid is not None and type(bid) is not int:
            return "A bid is a whole number."
        if bid is not None and not 0 <= bid <= points:
            return "A bid cannot exceed your " + str(points) + " points."
    try:
        db.insert_items(plan["id"], rows)
    except sqlite3.IntegrityError:     # the same undo twice, faster than the check above
        return "Already in your plan."
    return None


def start_over(plan):
    """LN R15: empty the semester on show and return what undo needs to put it all back.
    The programme, the typed points and the plan for the other semester stay."""
    rows = plan_items(plan)
    for row in rows:
        db.delete_item(row["id"])
    return undo_rows(rows)


def remove_from_plan(plan, item_id):
    item = db.load_item(checked_entry(item_id))
    if item is None or item["plan_id"] != plan["id"]:
        return "This entry is not in your plan."
    db.delete_item(item_id)
    return None


def checked_bid(plan, bid):
    """LN R10: empty means no bid, zero is a real bid. A bid is a whole number from 0 up to the balance."""
    if bid in ("", None):
        return None, None
    if isinstance(bid, float) and not bid.is_integer():
        return None, "A bid is a whole number."
    try:
        value = int(bid)
    except (TypeError, ValueError):
        return None, "A bid is a whole number."
    if value < 0:
        return None, "A bid cannot be negative."
    if value > 0 and plan["points"] == 0:
        return None, "Enter your points first."
    if value > plan["points"]:
        return None, "A bid cannot exceed your " + str(plan["points"]) + " points."
    return value, None


def set_bid(plan, item_id, bid):
    """The bid of one section."""
    item = db.load_item(checked_entry(item_id))
    if item is None or item["plan_id"] != plan["id"]:
        return "This entry is not in your plan."
    if item["list"] == "mandatory":
        return "Mandatory courses need no bid."
    value, error = checked_bid(plan, bid)
    if error:
        return error
    db.update_item(item_id, bid=value)
    return None


def set_course_bid(plan, offering_id, bid):
    """One bid for all sections of a course: only the highest counts anyway (LN R6), so this is the normal case."""
    checked_id(offering_id)
    rows = [item for item in db.load_items(plan["id"]) if item["offering_id"] == offering_id]
    if not rows:
        return "This course is not in your plan."
    if rows[0]["list"] == "mandatory":
        return "Mandatory courses need no bid."
    value, error = checked_bid(plan, bid)
    if error:
        return error
    for row in rows:
        db.update_item(row["id"], bid=value)
    return None


def move_item(plan, item_id, list_name=None, direction=None):
    """Move an entry to the other list, or up and down inside its list. Sections of a course move together."""
    item = db.load_item(checked_entry(item_id))
    if item is None or item["plan_id"] != plan["id"]:
        return "This entry is not in your plan."
    items = db.load_items(plan["id"])
    if list_name and list_name != item["list"]:
        if list_name not in ("primary", "alternate", "mandatory"):
            return "Unknown list."
        position = next_position(items, list_name)
        for entry in items:
            if entry["offering_id"] == item["offering_id"]:
                db.update_item(entry["id"], list=list_name, position=position)
                position += 1
        return None
    if direction in ("up", "down"):
        order = [entry for entry in items if entry["list"] == item["list"]]
        order.sort(key=lambda entry: entry["position"])
        courses = []
        for entry in order:
            if entry["offering_id"] not in courses:
                courses.append(entry["offering_id"])
        index = courses.index(item["offering_id"])
        swap = index - 1 if direction == "up" else index + 1
        if 0 <= swap < len(courses):
            courses[index], courses[swap] = courses[swap], courses[index]
        position = 1
        for offering_id in courses:
            for entry in order:
                if entry["offering_id"] == offering_id:
                    db.update_item(entry["id"], position=position)
                    position += 1
    return None


def update_settings(plan, programme, semester, points, has_bonus):
    """Save the plan's settings. Entries of another semester stay saved but do not show.
    Points of None mean: not typed now, keep what is saved. Zero means: back to the estimate (LN R17)."""
    if not isinstance(programme, str):
        raise Malformed("The programme is text.")
    points = checked_points(points)
    if programme and programme not in db.load_programmes():
        return "Unknown programme."
    if semester not in ("Fall", "Spring"):
        return "Unknown semester."
    if points is None:
        points = db.load_plan(plan["id"])["points"]
    try:
        value = int(points)
    except (TypeError, ValueError):
        return "Points are a whole number."
    if value < 0 or value > 2000:
        return "Points must be between 0 and 2000."
    db.update_plan(plan["id"], programme, semester, value, has_bonus)
    if programme != plan["programme"]:
        relist_for_programme(db.load_plan(plan["id"]))
    return None


def relist_for_programme(plan, items=None):
    """What is mandatory depends on the programme: a course follows its new status. An alternate stays an alternate.
    Without entries named, all entries of the plan follow."""
    for item in db.load_items(plan["id"]) if items is None else items:
        mandatory = kind_for(plan, item["offering_id"]) == "mandatory"
        if item["list"] == "mandatory" and not mandatory:
            move_item(plan, item["id"], list_name="primary")
        elif item["list"] == "primary" and mandatory:
            move_item(plan, item["id"], list_name="mandatory")


def plan_items(plan):
    """The entries of this plan that belong to its semester."""
    return in_semester(db.load_items(plan["id"]), plan["semester"])


def warnings_for(plan, items):
    """Things to fix before going to Nova. Each one names what is wrong and where to fix it; none of them blocks the plan."""
    found = []
    reserved = reserved_points(items)
    electives = [item for item in items if item["list"] == "primary"]
    if electives and plan["points"] == 0:
        found.append({"level": "stop", "where": "bids", "text": "Enter your points: they are the Balance on Nova's platform."})
    elif reserved > plan["points"]:
        found.append({"level": "stop", "where": "bids", "text": f"Your primary bids hold {reserved} points, you have {plan['points']}."})
    no_bid = sorted({all_offerings()[item["offering_id"]]["name"] for item in electives if item["bid"] is None})
    if no_bid:
        found.append({"level": "note", "where": "bids", "text": "No bid yet: " + ", ".join(no_bid) + ". Nova reads an empty field as not interested."})
    if electives and not any(item["list"] == "alternate" for item in items):
        found.append({"level": "note", "where": "bids", "text": "Your alternate list is empty. Nova strongly recommends filling it."})
    summary = ects_summary(items)
    if summary["over"]:
        found.append({"level": "stop", "where": "courses", "text": f"{summary['total']:g} ECTS is above the maximum of {MAX_ECTS:g}."})
    return found


# A real plan from Fall 2026, with real bids: section, list, bid.
EXAMPLE_PLAN = [
    ("2459-S1-TXC", "mandatory", None), ("2581-S1-TXC", "mandatory", None),
    ("2966-T1-TXC", "mandatory", None), ("2463-T2-TXE", "mandatory", None),
    ("2477-S1-TXB", "primary", 164), ("2477-S1-TXA", "primary", 164), ("2477-S1-TXC", "primary", 164),
    ("2277-T2-TXB", "primary", 1), ("2277-T2-TXA", "primary", 1),
    ("2652-S1-TXA", "alternate", 33), ("2416-T1-TXA", "alternate", 1),
]


def load_example(plan):
    """Fill an empty plan with an example, so that a first visit shows what the tool does."""
    if plan_items(plan):
        return "Your plan already has courses."
    db.update_plan(plan["id"], "Management", "Fall", 165, False)
    positions = defaultdict(int)
    for section_id, list_name, bid in EXAMPLE_PLAN:
        positions[list_name] += 1
        db.insert_item(plan["id"], all_sections()[section_id]["offering_id"], section_id, list_name, positions[list_name], bid)
    return None


# ---------- LN R19: the arrows, one step back and forward again ----------

MAX_STEPS = 50   # how many changes the left arrow can take back, per plan and semester
STEP_FIELDS = ("id", "offering_id", "section_id", "list", "position", "bid")   # what a step keeps of each entry


def entries_by_semester(plan_id):
    """The entries of a plan as a step keeps them: one list per semester, in the order they came into the plan."""
    entries = {"Fall": [], "Spring": []}
    for item in sorted(db.load_items(plan_id), key=lambda item: item["id"]):
        semester = all_offerings()[item["offering_id"]]["semester"]
        entries[semester].append({name: item[name] for name in STEP_FIELDS})
    return entries


@contextmanager
def undoable(plan):
    """LN R19: what happens inside is one change, which the left arrow can take back.

    The entries are copied first. A semester whose entries are different afterwards keeps the copy as its newest step,
    and what could be done again there is dropped. A refused change leaves the entries alone, so it leaves no step.
    Settings never come through here: the programme, the semester, typed points and the bonus are no change."""
    before = entries_by_semester(plan["id"])
    yield
    after = entries_by_semester(plan["id"])
    for semester, entries in before.items():
        if after[semester] != entries:
            db.push_step(plan["id"], semester, "undo", entries, MAX_STEPS)
            db.clear_steps(plan["id"], semester, "redo")


def undo(plan):
    """LN R19: one step back in the semester on show. Returns an error text or None."""
    return take_step(plan, "undo", "redo", "Nothing to undo.")


def redo(plan):
    """LN R19: one step forward again, after an undo. Returns an error text or None."""
    return take_step(plan, "redo", "undo", "Nothing to redo.")


def take_step(plan, way, back, nothing):
    """Put back the newest step kept for `way` and keep the entries as they are now as a step for `back`,
    so that the other arrow can return to them. Only the semester on show changes.
    The programme is not part of a step: a course that comes back takes the list its programme gives it now."""
    entries = db.pop_step(plan["id"], plan["semester"], way)
    if entries is None:
        return nothing
    now = entries_by_semester(plan["id"])[plan["semester"]]
    db.push_step(plan["id"], plan["semester"], back, now, MAX_STEPS)
    db.replace_items(plan["id"], [entry["id"] for entry in now], entries)
    relist_for_programme(plan, plan_items(plan))
    return None


def state_of(plan):
    """Everything the planner and the bids page show, as one dict."""
    items = plan_items(plan)
    week = week_items(items)
    week_ids = {item["id"] for item in week}
    enriched = []
    for item in items:
        offering = all_offerings()[item["offering_id"]]
        row = dict(item)
        row["name"] = offering["name"]
        row["code"] = offering["code"]
        row["term"] = offering["term"]
        row["ects"] = offering["ects"]
        row["section"] = all_sections()[item["section_id"]]["section"] if item["section_id"] else None
        row["meetings"] = all_meetings().get(item["section_id"], []) if item["section_id"] else []
        row["analysis"] = bid_analysis(item, plan) if item["list"] != "mandatory" else None
        row["in_week"] = item["id"] in week_ids
        row["conflicts"] = [] if row["in_week"] else conflicts_with_week(item, items, week)
        enriched.append(row)
    clashes = sorted(class_clashes(week) + exam_clashes(week), key=lambda clash: ["exam", "class", "midterm"].index(clash["kind"]))
    per_section, per_offering = section_warnings(items, plan["semester"])
    exams = []
    for offering_id in sorted({item["offering_id"] for item in items}):
        offering = all_offerings()[offering_id]
        for exam in regular_exams(offering):
            exams.append({"offering_id": offering_id, "name": offering["name"], "kind": exam["kind"], "date": exam["date"], "start": exam["start"],
                          "end": exam["end"], "label": day_label(exam["date"]), "note": exam["note"]})
    exams.sort(key=lambda exam: (exam["date"], exam["start"]))
    steps = db.count_steps(plan["id"], plan["semester"])
    return {
        "plan": plan,
        "items": enriched,
        "ects": ects_summary(items),
        "mandatory_ects": mandatory_ects(items),
        "reserved": reserved_points(items),
        "forecast": forecast(plan, items),
        "clashes": clashes,
        "section_warnings": per_section,
        "exam_warnings": per_offering,
        "exam_days": exam_days(week),
        "day_warnings": exam_day_warnings(items, plan["semester"]),
        "exams": exams,
        "warnings": warnings_for(plan, items),
        "next_deadline": next_deadline(),
        "round": round_of(plan["semester"]),
        "known_prices": known_prices(plan["semester"]),
        "platform_list": platform_list(plan),
        # LN R19: an arrow is switched off when there is nothing to take back or to do again
        "can_undo": steps["undo"] > 0,
        "can_redo": steps["redo"] > 0,
    }


def next_deadline(today=None):
    """The next bidding or add/drop window from the academic calendar."""
    today = today or date.today().isoformat()
    upcoming = [row for row in db.load_calendar()
                if ("bidding" in row["key"] or "add-drop" in row["key"]) and row["last_day"] >= today]
    if not upcoming:
        return None
    row = upcoming[0]
    days = (date.fromisoformat(row["first_day"]) - date.fromisoformat(today)).days
    return {"label": row["label"], "first_day": row["first_day"], "last_day": row["last_day"], "days": max(days, 0),
            "range": day_label(row["first_day"]) + " – " + day_label(row["last_day"])}


def round_of(semester, today=None):
    """The bidding round of a semester: when it is, and whether it is over, running or still to come."""
    today = today or date.today().isoformat()
    row = next((row for row in db.load_calendar() if row["key"] == semester.lower() + "-bidding"), None)
    if row is None:
        return None
    status = "closed" if today > row["last_day"] else "open" if today >= row["first_day"] else "upcoming"
    return {"label": row["label"], "range": day_label(row["first_day"]) + " – " + day_label(row["last_day"]),
            "first_day": day_label(row["first_day"]).split(" ", 1)[1], "last_day": day_label(row["last_day"]), "status": status,
            "days": max((date.fromisoformat(row["first_day"]) - date.fromisoformat(today)).days, 0)}


def known_prices(semester="Fall"):
    """What we know so far, as an anchor for sections without a past price."""
    prices = [row["min_rank_value"] for row in last_rounds(db.load_cutoffs())
              if row["list"] == "primary" and row["min_rank_value"] is not None]
    if not prices:
        return None
    return {"sections": len(prices), "total": coverage("Fall")["total"], "low": math.floor(min(prices)), "high": math.ceil(max(prices))}


def semester_label(semester, today=None):
    """What the semester menu says: which round it is, and whether it can still be bid on."""
    round_ = round_of(semester, today)
    name = semester
    if round_ is None:
        return name
    if round_["status"] == "closed":
        return name + " · closed"
    if round_["status"] == "open":
        return name + " · open now"
    return name + " · opens " + round_["first_day"]


def catalogue(plan):
    """The course list of one semester for one programme, ready to send to the page."""
    kinds = db.load_programme_kinds(plan["programme"])
    cut_rows = defaultdict(list)
    for row in last_rounds(db.load_cutoffs()):     # LN R18: each term's newest round only
        if row["list"] == "primary":
            cut_rows[row["code"]].append(row)
    sections_by_offering = defaultdict(list)
    for section in all_sections().values():
        sections_by_offering[section["offering_id"]].append(section)
    rows = []
    for offering in all_offerings().values():
        if offering["semester"] != plan["semester"]:
            continue
        sections = []
        for section in sorted(sections_by_offering[offering["id"]], key=lambda s: s["section"]):
            price = next((r for r in cut_rows[offering["code"]] if r["term"] == offering["term"] and r["section"] == section["section"]), None)
            sections.append({"id": section["id"], "section": section["section"], "delivery": section["delivery"],
                             "meetings": all_meetings().get(section["id"], []),
                             "cutoff": price["min_rank_value"] if price else None, "seats": price["seats"] if price else None,
                             "bids": price["bids"] if price else None})
        exam = next((e for e in regular_exams(offering) if e["kind"] == "exam"), None)
        prices = [r["min_rank_value"] for r in cut_rows[offering["code"]] if r["min_rank_value"] is not None]
        rating = course_rating(offering["code"])
        rows.append({
            "id": offering["id"], "code": offering["code"], "name": offering["name"], "term": offering["term"],
            "ects": offering["ects"], "lecturers": offering["lecturers"], "kind": kinds.get(offering["id"], "outside"),
            "has_schedule": offering["has_schedule"], "sections": sections,
            "exam": day_label(exam["date"]) if exam else None,
            "cutoff_low": min(prices) if prices else None, "cutoff_high": max(prices) if prices else None,
            "rating": rating["rating"] if rating else None, "reviews": rating["reviews"] if rating else 0,
        })
    order = {"mandatory": 0, "elective": 1, "outside": 2}
    rows.sort(key=lambda row: (order[row["kind"]], row["name"]))
    return rows


# ---------- LN R9 and LN R18: shared price data ----------

# LN R18: exactly what the bookmarklet writes (static/share-bookmarklet.js). Anything else that comes along refuses the
# whole share (LN R9): a list of forbidden names missed the platform's own "Ects Sum", a list of allowed ones misses nothing.
LIST_KEYS = {"code", "term", "section", "list", "seats", "year", "rows"}
ROW_KEYS = {"final", "bid", "allocated"}
PERSONAL = "This export contains personal columns. Nothing was stored."
NOT_A_LIST = "This does not look like a rank list from the export."
SHARED = "shared rank list"   # the source of every list that came in through the share page
# LN R18: how big the numbers of a real rank list can be, with room to spare.
MAX_BID = 5000             # a plan takes at most 2000 points (update_settings)
MAX_RANK_VALUE = 5500      # the highest bid with the rank bonus of LN R7
MAX_SEATS = 400            # the largest section so far had 72 seats
MAX_ROWS = 1000            # one row per bid: the fullest section so far had 298
MAX_LISTS = 60             # one list per section a student bid on


def plain_number(value, highest, whole=False):
    """LN R18: a number as the bookmarklet writes it, from 0 to highest; otherwise None.

    Text, true and false are no numbers here. Infinity and NaN fail the range check by themselves: comparing with NaN
    is always false, and Infinity is above any highest. A whole number may not have a fraction.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= highest:
        return None
    if whole and value != int(value):
        return None
    return value


def has_personal_columns(payload):
    """LN R9: anything beyond what the bookmarklet writes, in the list itself or in one of its rows."""
    rows = payload.get("rows")
    extra_in_rows = isinstance(rows, list) and any(not isinstance(row, dict) or set(row) - ROW_KEYS for row in rows)
    return bool(set(payload) - LIST_KEYS) or extra_in_rows


def read_rows(rows):
    """LN R18: the rows of one rank list as plain numbers, or None when a row cannot be read."""
    clean = []
    for row in rows:
        final, bid = plain_number(row.get("final"), MAX_RANK_VALUE), plain_number(row.get("bid"), MAX_BID, whole=True)
        if final is None or bid is None or not isinstance(row.get("allocated"), bool):
            return None
        clean.append({"final": float(final), "bid": float(bid), "allocated": row["allocated"]})
    return clean


def round_name(year, term):
    """The bidding round of a rank list: academic year '2026/2027' and term S1 mean 'Fall 2026', term S2 'Spring 2027'.
    None when the year is not written the way the platform writes it."""
    match = re.fullmatch(r"(\d{4})/(\d{4})", year, re.ASCII)
    if match is None or int(match[2]) != int(match[1]) + 1:
        return None
    return ("Fall " + match[1]) if term in ("S1", "T1", "T2") else ("Spring " + match[2])


def shared_rounds(today=None):
    """LN R18: the rounds a shared rank list may come from. Rank lists exist only once a round is over, so these are
    the rounds of the calendar's academic year that have closed, and the two rounds of the year before."""
    fall = next((row for row in db.load_calendar() if row["key"] == "fall-bidding"), None)
    if fall is None:
        return set()
    year = int(fall["first_day"][:4])
    rounds = {f"Fall {year - 1}", f"Spring {year}"}
    for semester, name in (("Fall", f"Fall {year}"), ("Spring", f"Spring {year + 1}")):
        round_ = round_of(semester, today)
        if round_ is not None and round_["status"] == "closed":
            rounds.add(name)
    return rounds


def known_section(code, term, section):
    """LN R18: a shared list counts for a section of Lance's catalogue only, so no free text reaches the course sheet.
    While a course has no timetable Lance knows none of its sections: then the name must be one Nova uses (TXA, TXB ...)."""
    offering = all_offerings().get(code + "-" + term)
    if offering is None:
        return False
    names = {row["section"] for row in all_sections().values() if row["offering_id"] == offering["id"]}
    return section in (names or {row["section"] for row in all_sections().values()})


def read_rank_list(payload):
    """LN R9 and LN R18: check one shared rank list and boil it down to totals. Nothing about a single student is kept.

    Only totals per section leave this function. A field beyond the ones the bookmarklet writes rejects the whole
    upload, so a broken export can never store personal data by accident.
    """
    if not isinstance(payload, dict):
        return None, NOT_A_LIST
    if has_personal_columns(payload):
        return None, PERSONAL
    texts = [payload.get("code"), payload.get("term"), payload.get("section"), payload.get("list", "primary"),
             payload.get("year", "2026/2027")]
    if not all(isinstance(text, str) for text in texts) or "rows" not in payload:
        return None, NOT_A_LIST
    code, term, section, list_name, year = (text.strip() for text in texts)
    rows = payload["rows"]
    if not known_section(code, term, section):
        return None, "Lance does not know this course or section."
    if list_name not in ("primary", "alternate"):
        return None, "Unknown list."
    round_ = round_name(year, term)
    if round_ not in shared_rounds():
        return None, "Lance takes rank lists only from the last rounds that are over."
    seats = plain_number(payload.get("seats"), MAX_SEATS, whole=True)
    if seats is None or seats < (0 if list_name == "alternate" else 1):   # an alternate list can have no seat left
        return None, "The number of seats could not be read."
    if not isinstance(rows, list) or not rows:
        return None, "The rank list is empty."
    if len(rows) > MAX_ROWS:
        return None, f"A rank list has at most {MAX_ROWS} rows."
    clean = read_rows(rows)
    if clean is None:
        return None, "A row of the rank list could not be read."
    allocated = [row for row in clean if row["allocated"]]
    cutoff = {
        "code": code, "term": term, "section": section, "round": round_, "list": list_name,
        "seats": int(seats), "bids": len(clean), "allocated": len(allocated),
        "min_rank_value": min((row["final"] for row in allocated), default=None),
        "max_rank_value": max((row["final"] for row in allocated), default=None),
        "min_bid": min((row["bid"] for row in allocated), default=None),
        "zero_bids": sum(1 for row in clean if row["bid"] == 0),
        "source": SHARED,
    }
    buckets = defaultdict(lambda: {"bids": 0, "allocated": 0})
    for row in clean:
        low = int(row["final"] // 20) * 20
        buckets[low]["bids"] += 1
        buckets[low]["allocated"] += 1 if row["allocated"] else 0
    histogram = [{"code": code, "term": term, "section": section, "round": cutoff["round"], "list": list_name,
                  "bucket_from": low, "bucket_to": low + 20, "bids": value["bids"], "allocated": value["allocated"]}
                 for low, value in sorted(buckets.items())]
    return (cutoff, histogram), None


def from_our_own_data(cutoff):
    """LN R18: does Lance hold a list for this section, round and list from its own seed data? A shared list never
    replaces it: that one was read from a real account, a pasted one could be made up."""
    key = ("term", "section", "round", "list")
    return any(row["source"] != SHARED and all(row[name] == cutoff[name] for name in key)
               for row in db.load_cutoffs(cutoff["code"]))


def share_rank_lists(payload):
    """LN08 and LN R18: store a whole export, one or more rank lists. Every list is checked before anything is stored,
    so one that does not count refuses the whole share. Returns (how many were new or better, error)."""
    if isinstance(payload, dict) and "lists" in payload:
        if set(payload) != {"lists"}:      # LN R9: nothing travels beside the lists
            return 0, PERSONAL
        lists = payload["lists"]
    else:
        lists = [payload]
    if not isinstance(lists, list) or not lists:
        return 0, NOT_A_LIST
    if len(lists) > MAX_LISTS:
        return 0, f"One share takes at most {MAX_LISTS} rank lists."
    prepared = []
    for one in lists:
        result, error = read_rank_list(one)
        if error:
            return 0, error
        prepared.append(result)
    stored = 0
    for cutoff, histogram in prepared:
        if not from_our_own_data(cutoff) and db.save_price_data(cutoff, histogram):
            stored += 1
    return stored, None


def coverage(semester="Fall"):
    """How much of the semester has price data, for the share page."""
    sections = [s for s in all_sections().values() if all_offerings()[s["offering_id"]]["semester"] == semester]
    known = {(row["code"], row["term"], row["section"]) for row in db.load_cutoffs() if row["list"] == "primary"}
    covered = []
    for section in sections:
        offering = all_offerings()[section["offering_id"]]
        if (offering["code"], offering["term"], section["section"]) in known:
            covered.append(section["id"])
    return {"covered": len(covered), "total": len(sections), "percent": round(100 * len(covered) / max(len(sections), 1))}


# ---------- course pages ----------

STOPWORDS = set("""a about across all also an and any are as at be been both but by can course courses do does each for
from has have how in into is it its learn learning main more most not of on or our such students student that the their
them these they this those through to understand using we what when which who will with within you your""".split())


def words_of(text):
    cleaned = "".join(ch.lower() if ch.isalpha() else " " for ch in text)
    return {word for word in cleaned.split() if len(word) > 3 and word not in STOPWORDS}


def similar_courses(offering, limit=4):
    """Courses of the same semester whose name and synopsis share the most words with this one."""
    synopses = {(row["code"], row["term"]): row["synopsis"] for row in db.load_all_syllabi()}
    own = words_of(offering["name"]) | words_of(synopses.get((offering["code"], offering["term"]), ""))
    scored = []
    for other in all_offerings().values():
        if other["semester"] != offering["semester"] or other["code"] == offering["code"]:
            continue
        theirs = words_of(other["name"]) | words_of(synopses.get((other["code"], other["term"]), ""))
        shared = own & theirs
        if shared:
            scored.append((len(shared) / (len(own | theirs) or 1), other["name"], other))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [row[2] for row in scored[:limit]]


def course_page(offering_id, plan):
    """Everything the course sheet shows."""
    offering = all_offerings().get(offering_id)
    if offering is None:
        return None
    sections = []
    for section in db.load_sections(offering_id):
        meetings = all_meetings().get(section["id"], [])
        sections.append(dict(section, meetings=meetings, sessions=len(all_sessions().get(section["id"], []))))
    rows, exact = past_prices(offering["code"], offering["term"])
    prices_list = "primary"
    if not rows:
        rows, exact = past_prices(offering["code"], offering["term"], "alternate")
        prices_list = "alternate"
    histograms = defaultdict(list)
    for row in db.load_histograms(offering["code"]):
        if row["list"] == prices_list:
            histograms[(row["term"], row["section"], row["round"])].append(row)    # each price row draws its own round
    prices = []
    for row in rows:
        prices.append(dict(row, histogram=histograms.get((row["term"], row["section"], row["round"]), [])))
    exams = [dict(exam, label=day_label(exam["date"])) for exam in all_exams().get((offering["code"], offering["term"]), []) if exam["date"]]
    no_exam = any(exam["kind"] == "none" for exam in all_exams().get((offering["code"], offering["term"]), []))
    other_terms = [row for row in db.load_offerings_by_code(offering["code"]) if row["id"] != offering_id]
    items = plan_items(plan)
    return {
        "offering": offering, "sections": sections, "prices": prices, "prices_exact": exact, "prices_list": prices_list,
        "lowest_in_course": lowest_bid_in_course(offering["code"], offering["term"]), "exams": exams, "no_exam": no_exam,
        "syllabus": db.load_syllabus(offering["code"], offering["term"]),
        "syllabus_url": syllabus_url(offering["code"], offering["term"]),
        "rating": course_rating(offering["code"]), "similar": similar_courses(offering), "other_terms": other_terms,
        "kind": kind_for(plan, offering_id),
        "in_plan": {item["section_id"]: item["id"] for item in items if item["offering_id"] == offering_id},
    }


def syllabus_url(code, term):
    return ("https://apps.novasbe.pt/SigesAutomations/controlador?modo=FUC&CD_LECTIVO=202627"
            f"&CD_DISCIP={code}&CD_DURACAO={term}")


# ---------- LN10: the calendar file ----------

def ics_escape(text):
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def calendar_file(plan):
    """Every class and exam of the week as a calendar file, with make-up days on their real dates (LN R13)."""
    items = week_items(plan_items(plan))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Lance//Nova bidding planner//EN", "CALSCALE:GREGORIAN",
             "X-WR-CALNAME:Lance plan", "X-WR-TIMEZONE:Europe/Lisbon"]

    def event(uid, day, start, end, summary, location="", note=""):
        compact = day.replace("-", "")
        lines.extend(["BEGIN:VEVENT", f"UID:{uid}@lance", f"DTSTAMP:{stamp}",
                      f"DTSTART;TZID=Europe/Lisbon:{compact}T{start.replace(':', '')}00",
                      f"DTEND;TZID=Europe/Lisbon:{compact}T{end.replace(':', '')}00",
                      "SUMMARY:" + ics_escape(summary)])
        if location:
            lines.append("LOCATION:" + ics_escape(location))
        if note:
            lines.append("DESCRIPTION:" + ics_escape(note))
        lines.append("END:VEVENT")

    for item in chosen_sections(items):
        label = label_of(item["offering_id"], item["section_id"])
        for number, session in enumerate(all_sessions().get(item["section_id"], [])):
            event(f"{item['section_id']}-{number}", session["date"], session["start"], session["end"], label, session["room"], session["note"])
    seen = set()
    for item in items:
        if item["offering_id"] in seen:
            continue
        seen.add(item["offering_id"])
        offering = all_offerings()[item["offering_id"]]
        for number, exam in enumerate(regular_exams(offering)):
            event(f"{offering['id']}-exam-{number}", exam["date"], exam["start"], exam["end"], offering["name"] + " " + exam["kind"])
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


# ---------- LN10: the list to type into the platform ----------

def platform_list(plan):
    """The bids in the order the platform asks for them, as plain text to keep next to it."""
    items = plan_items(plan)
    lines = []
    for list_name, title in (("primary", "PRIMARY LIST"), ("alternate", "ALTERNATE LIST")):
        entries = [item for item in items if item["list"] == list_name]
        if not entries:
            continue
        lines.append(title)
        order = []
        for item in sorted(entries, key=lambda entry: entry["position"]):
            if item["offering_id"] not in order:
                order.append(item["offering_id"])
        for number, offering_id in enumerate(order, start=1):
            offering = all_offerings()[offering_id]
            sections = []
            for item in sorted((e for e in entries if e["offering_id"] == offering_id), key=lambda e: e["position"]):
                section = all_sections()[item["section_id"]]["section"] if item["section_id"] else "section to choose"
                sections.append(section + " " + ("no bid" if item["bid"] is None else str(item["bid"])))
            lines.append(f"{number}. {offering['code']} {offering['name']} ({offering['term']}): " + ", ".join(sections))
        lines.append("")
    return "\n".join(lines).strip()
