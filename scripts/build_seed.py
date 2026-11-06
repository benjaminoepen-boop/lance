"""Build the tables the app loads from the extracted rows. Run after the extract_* scripts.

  offerings.csv             a course in one term ('2477-S1')
  sections.csv              a section of an offering ('2477-S1-TXB')
  meetings.csv              the weekly pattern of a section, for the week view
  sessions.csv              every single class with its date, for exact clash checks and the calendar file
  programme_offerings.csv   which programme takes which offering, and how it counts
  calendar.csv              the dates from Nova's academic calendar

Run:  uv run python -I scripts/build_seed.py
"""
import csv
import datetime as dt
import os
import re
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, "..", "seed")

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

# Each programme has its own colour for mandatory courses in Nova's per-programme timetables.
# Yellow is an elective. Another programme's colour means the course is mandatory there, elective here.
OWN_COLOUR = {
    "14 Economics": "blue",
    "15 Management": "0.74,0.99,0.79",
    "16 Finance": "orange",
    "37 Business Analytics": "0.56,0.74,0.55",
    "38 Impact Entrepreneurship": "blue",
    "39 Public Policy": "0.73,0.47,0.47",
}
PROGRAMME_NAME = {key.split(" ", 1)[1]: key for key in OWN_COLOUR}

# Nova's academic calendar 2026/27 (AC_202627_MSc.pdf, last update 29/04/2026)
TERM_WEEKS = {
    # weekday -> class dates, written out so that holidays and their make-up days stay visible
    "T1": {
        "Mon": ["2026-08-31", "2026-09-07", "2026-09-14", "2026-09-21", "2026-09-28", "2026-10-12"],  # 5 Oct: holiday, made up 12 Oct
        "Tue": ["2026-09-01", "2026-09-08", "2026-09-15", "2026-09-22", "2026-09-29", "2026-10-06"],
        "Wed": ["2026-09-02", "2026-09-09", "2026-09-16", "2026-09-23", "2026-09-30", "2026-10-07"],
        "Thu": ["2026-09-03", "2026-09-10", "2026-09-17", "2026-09-24", "2026-10-01", "2026-10-08"],
        "Fri": ["2026-09-04", "2026-09-11", "2026-09-18", "2026-09-25", "2026-10-02", "2026-10-09"],
    },
    "T2": {
        "Mon": ["2026-10-26", "2026-11-02", "2026-11-09", "2026-11-16", "2026-11-23", "2026-11-30"],
        "Tue": ["2026-10-27", "2026-11-03", "2026-11-10", "2026-11-17", "2026-11-24", "2026-12-04"],  # 1 Dec: holiday, made up Fri 4 Dec
        "Wed": ["2026-10-28", "2026-11-04", "2026-11-11", "2026-11-18", "2026-11-25", "2026-12-02"],
        "Thu": ["2026-10-22", "2026-11-05", "2026-11-12", "2026-11-19", "2026-11-26", "2026-12-03"],  # 29 Oct: Estoril Conferences, made up 3 Dec
        "Fri": ["2026-10-23", "2026-10-30", "2026-11-06", "2026-11-13", "2026-11-20", "2026-11-27"],
    },
}
MADE_UP = {"2026-10-12": "Make-up for 5 Oct", "2026-12-04": "Make-up for 1 Dec", "2026-12-03": "Make-up for 29 Oct"}

CALENDAR = [
    # key, first day, last day, label
    ("fall-bidding", "2026-07-21", "2026-07-23", "Fall enrolments (bidding)"),
    ("t1-add-drop", "2026-07-29", "2026-07-31", "Add/drop T1"),
    ("t1-classes", "2026-08-31", "2026-10-12", "T1 classes"),
    ("t2-add-drop", "2026-10-07", "2026-10-09", "Add/drop T2"),
    ("t1-exams", "2026-10-14", "2026-10-20", "T1 exams"),
    ("t2-classes", "2026-10-22", "2026-12-04", "T2 classes"),
    ("t1-makeup-exams", "2026-10-26", "2026-10-30", "T1 make-up exams"),
    ("s1-t2-exams", "2026-12-07", "2026-12-21", "T2 and S1 exams"),
    ("s1-t2-makeup-exams", "2027-01-04", "2027-01-16", "S1 and T2 make-up exams"),
    ("spring-bidding", "2027-01-18", "2027-01-20", "Spring enrolments (bidding)"),
    ("t3-add-drop", "2027-01-26", "2027-01-28", "Add/drop T3"),
    ("t3-classes", "2027-02-01", "2027-03-16", "T3 classes"),
    ("t3-exams", "2027-03-18", "2027-03-25", "T3 exams"),
    ("t4-add-drop", "2027-03-22", "2027-03-24", "Add/drop T4"),
    ("t4-classes", "2027-04-05", "2027-05-14", "T4 classes"),
    ("s2-t4-exams", "2027-05-17", "2027-06-02", "T4 and S2 exams"),
]

# MSc Fall 202627 Irregular Schedules_07092026.pdf: these sections keep their own dates.
IRREGULAR = {
    "2389-T1-TXA": [("2026-08-31", "08:00", "11:00", "D.-1.06", ""), ("2026-09-07", "08:00", "11:00", "D.-1.06", ""),
                    ("2026-09-14", "08:00", "11:00", "D.-1.06", ""), ("2026-09-21", "08:00", "11:00", "D.-1.06", ""),
                    ("2026-09-28", "08:00", "11:00", "Online", ""), ("2026-10-12", "08:00", "11:00", "Online", "Make-up for 5 Oct")],
    "2232-S1-TXA": [(day, "11:00", "14:00", "B.0.05" if day == "2026-11-10" else "D.-1.14", "Make-up for 1 Dec" if day == "2026-12-04" else "")
                    for day in ("2026-09-08", "2026-09-15", "2026-09-22", "2026-09-29", "2026-10-06", "2026-10-27",
                                "2026-11-03", "2026-11-10", "2026-11-17", "2026-11-24", "2026-12-04")],
    "2232-S1-TXB": [(day, "15:30", "18:30", "B.0.02", "Make-up for 1 Dec" if day == "2026-12-04" else "")
                    for day in ("2026-09-08", "2026-09-15", "2026-09-22", "2026-09-29", "2026-10-06", "2026-10-27",
                                "2026-11-03", "2026-11-10", "2026-11-17", "2026-11-24", "2026-12-04")],
}
# MSc Fall202627 Planned MakeUp classes.pdf: this class moves, the rest of the section stays.
MOVED = {"2473-T1-TXA": {"from": "2026-08-31", "to": ("2026-09-07", "15:30", "18:30", "D.-1.05", "Replaces 31 Aug")}}


def read(name):
    with open(os.path.join(SEED, name + ".csv"), newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def write(name, rows, fields):
    with open(os.path.join(SEED, name + ".csv"), "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{name}: {len(rows)}")


def room(text):
    return re.sub(r"\s+", "", text or "")


def semester_of(term):
    return "Fall" if term in ("S1", "T1", "T2") else "Spring"


def default_ects(code, term):
    if code.startswith("96") or code.startswith("95"):
        return 0.5
    return 7.0 if term in ("S1", "S2") else 3.5


def most_common_clean(values):
    """Prefer the most frequent spelling. Stray lecturer text in a name loses because it is rare."""
    cleaned = [re.sub(r"\s+\d+(\.\d+)?\s+.*$", "", v) for v in values if v]
    return Counter(cleaned).most_common(1)[0][0] if cleaned else ""


def tidy_names(names):
    """Wrapped PDF cells leave fragments like 'Pranav' beside 'Pranav Desai F': keep the real names."""
    cleaned = {re.sub(r"\s+[A-Z]$", "", name).strip() for name in names if name.strip()}
    return sorted(name for name in cleaned if not any(other != name and other.startswith(name + " ") for other in cleaned))


def main():
    electives = read("electives")
    master = read("master_meetings")
    programme_rows = read("programme_meetings")

    # 1. which term does each weekly meeting belong to? The master timetable prints it in the cell.
    master_terms = defaultdict(set)
    delivery = {}
    for row in master:
        master_terms[(row["code"], row["section"], row["day"], row["start"], room(row["room"]))].add(row["term"])
        delivery[(row["code"], row["term"], row["section"])] = row["delivery"]
    weekly = {}
    seen_in_file = defaultdict(set)
    for row in programme_rows:
        key = (row["code"], row["section"], row["day"], row["start"], row["end"], room(row["room"]))
        seen_in_file[key].add(row["period"])
        weekly[key] = row
    meetings = []
    names = defaultdict(list)
    lecturers = {}
    for key, row in weekly.items():
        code, section, day, start, end, where = key
        # The per-programme files limit the term: S1 is printed in both files, T1 and T2 in one each.
        periods = seen_in_file[key]
        allowed = set(periods) | ({"S1"} if len(periods) == 2 else set())
        # The master prints the term in each cell; a long class is looked up by its first block.
        terms = master_terms.get((code, section, day, start, where), set()) & allowed
        if not terms:
            terms = {"S1"} if len(periods) == 2 else set(periods)
        for term in sorted(terms):
            section_id = f"{code}-{term}-{section}"
            meetings.append({"section_id": section_id, "day": day, "start": start, "end": end, "room": where})
            names[(code, term)].append(row["name"])
            lecturers[section_id] = row["lecturer"]
    # same section, same term: a class printed in two rooms keeps one row per room
    meetings.sort(key=lambda m: (m["section_id"], WEEKDAYS.index(m["day"]), m["start"]))

    # 2. offerings: every course in the timetable plus every course on an elective list
    offering_lecturers = defaultdict(list)
    ects = {}
    for row in electives:
        if row["term"] not in ("S1", "T1", "T2", "S2", "T3", "T4"):
            continue
        key = (row["code"], row["term"])
        names[key].append(row["name"])
        if row["lecturers"]:
            offering_lecturers[key].append(row["lecturers"])
        if row["ects"]:
            ects[key] = float(row["ects"])
    scheduled = {tuple(m["section_id"].split("-")[:2]) for m in meetings}
    offerings = []
    for key in sorted(names):
        code, term = key
        # The timetable spells names best; the elective lists fill in the terms without a timetable.
        people = sorted({name.strip() for sid, text in lecturers.items() if sid.startswith(f"{code}-{term}-") for name in text.split(",")})
        if not people:
            people = tidy_names(name.strip() for group in offering_lecturers[key] for name in group.split(","))
        offerings.append({"id": f"{code}-{term}", "code": code, "name": most_common_clean(names[key]), "term": term,
                          "semester": semester_of(term), "ects": ects.get(key, default_ects(code, term)),
                          "lecturers": ", ".join(people), "has_schedule": 1 if key in scheduled else 0})

    # 3. sections
    sections = []
    for section_id in sorted({m["section_id"] for m in meetings}):
        code, term, section = section_id.split("-")
        sections.append({"id": section_id, "offering_id": f"{code}-{term}", "section": section,
                         "lecturers": lecturers.get(section_id, ""),
                         "delivery": delivery.get((code, term, section), "") or "on campus"})

    # 4. every single class with its date
    sessions = []
    per_section = defaultdict(list)
    for meeting in meetings:
        per_section[meeting["section_id"]].append(meeting)
    for section_id, its_meetings in per_section.items():
        if section_id in IRREGULAR:
            for date, start, end, where, note in IRREGULAR[section_id]:
                sessions.append({"section_id": section_id, "date": date, "start": start, "end": end, "room": where, "note": note})
            continue
        term = section_id.split("-")[1]
        calendars = [TERM_WEEKS["T1"], TERM_WEEKS["T2"]] if term == "S1" else [TERM_WEEKS[term]]
        for meeting in its_meetings:
            for weeks in calendars:
                for date in weeks.get(meeting["day"], []):
                    moved = MOVED.get(section_id)
                    if moved and date == moved["from"]:
                        continue
                    sessions.append({"section_id": section_id, "date": date, "start": meeting["start"], "end": meeting["end"],
                                     "room": meeting["room"], "note": MADE_UP.get(date, "")})
        moved = MOVED.get(section_id)
        if moved:
            date, start, end, where, note = moved["to"]
            sessions.append({"section_id": section_id, "date": date, "start": start, "end": end, "room": where, "note": note})
    sessions.sort(key=lambda s: (s["section_id"], s["date"], s["start"]))

    # 5. how each offering counts for each programme
    kinds = {}
    for row in programme_rows:
        programme = row["programme"].split(" ", 1)[1]
        code = row["code"]
        for term in {m.split("-")[1] for m in per_section if m.startswith(code + "-")}:
            if row["colour"] == OWN_COLOUR[row["programme"]] and row["period"] in ("T1", "T2"):
                # mandatory only where the period file fits the term
                if term == "S1" or term == row["period"]:
                    kinds[(programme, f"{code}-{term}")] = "mandatory"
    for row in electives:
        if row["term"] not in ("S1", "T1", "T2", "S2", "T3", "T4"):
            continue
        key = (row["programme"], f"{row['code']}-{row['term']}")
        kind = "outside" if row["type"] == "OUT_PROGRAM" else "elective"
        kinds.setdefault(key, kind)
    programme_offerings = [{"programme": p, "offering_id": o, "kind": k} for (p, o), k in sorted(kinds.items())]

    write("offerings", offerings, ["id", "code", "name", "term", "semester", "ects", "lecturers", "has_schedule"])
    write("sections", sections, ["id", "offering_id", "section", "lecturers", "delivery"])
    write("meetings", meetings, ["section_id", "day", "start", "end", "room"])
    write("sessions", sessions, ["section_id", "date", "start", "end", "room", "note"])
    write("programme_offerings", programme_offerings, ["programme", "offering_id", "kind"])
    write("calendar", [{"key": a, "first_day": b, "last_day": c, "label": d} for a, b, c, d in CALENDAR],
          ["key", "first_day", "last_day", "label"])


if __name__ == "__main__":
    main()
