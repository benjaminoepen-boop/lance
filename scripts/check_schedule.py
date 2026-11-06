"""Cross-check the master timetable against Nova's second layout, the per-programme PDFs.

Those PDFs print each course on a half-hour grid as four centred lines:

    Name, 2772
    [(Lecturer)]
    [Room B.0.04]
    TXA

Because the four lines share one centre, a cell can be read back without guessing, which makes these
PDFs an independent witness for code, section, weekday, time and room.

Run:  uv run python -I scripts/check_schedule.py seed/weekly_meetings.csv data/raw/MSc_Schedules_S1T1.pdf data/raw/MSc_Schedules_S1T2.pdf
"""
import csv
import re
import sys
from collections import defaultdict

import pdfplumber

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")


def minutes(clock):
    hours, mins = clock.split(":")
    return int(hours) * 60 + int(mins)


def segments(page):
    """Cut the page into runs of text on one line, split wherever the gap is too wide for a space."""
    lines = defaultdict(list)
    for char in page.chars:
        lines[round(char["top"] * 2) / 2].append(char)
    # merge lines that differ by half a point
    runs = []
    for top in sorted(lines):
        chars = sorted(lines[top], key=lambda c: c["x0"])
        current = [chars[0]]
        for char in chars[1:]:
            if char["x0"] - current[-1]["x1"] > 3.5:
                runs.append(current)
                current = [char]
            else:
                current.append(char)
        runs.append(current)
    result = []
    for run in runs:
        text = "".join(c["text"] for c in run).strip()
        if text:
            result.append({"text": text, "x0": run[0]["x0"], "x1": run[-1]["x1"], "top": run[0]["top"],
                           "bottom": run[0]["bottom"], "center": (run[0]["x0"] + run[-1]["x1"]) / 2})
    return result


def programme_cells(pdf_path):
    """Yield one dict per course cell found in a per-programme PDF."""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            runs = segments(page)
            heads = [(r["text"][:3], r["center"]) for r in runs if r["text"] in WEEKDAYS]
            if len(heads) < 5:
                continue
            labels = sorted((r["top"], r["text"][:5]) for r in runs if re.match(r"^\d\d:\d\d - \d\d:\d\d$", r["text"]))
            for run in runs:
                if not re.fullmatch(r"TX[A-Z]", run["text"]):
                    continue
                above = sorted((r for r in runs if abs(r["center"] - run["center"]) < 1.6
                                and 0 < run["top"] - r["top"] < 40), key=lambda r: -r["top"])
                room = next((r["text"] for r in above if r["text"].startswith("[Room")), "")
                title = next((r for r in above if re.search(r",\s*\d{4}$", r["text"])), None)
                if title is None:
                    continue
                code = title["text"][-4:]
                day = min(heads, key=lambda h: abs(h[1] - run["center"]))[0]
                middle = (title["top"] + run["bottom"]) / 2
                clock = None
                for top, label in labels:
                    if top <= middle:
                        clock = label
                yield {"code": code, "section": run["text"], "day": day, "clock": clock,
                       "room": room.replace("[Room", "").replace("]", "").strip()}


def main(csv_path, *pdfs):
    master = defaultdict(list)
    for row in csv.DictReader(open(csv_path, encoding="utf-8")):
        master[(row["code"], row["section"])].append(row)
    seen = set()
    wrong = set()
    checked = set()
    for pdf_path in pdfs:
        for cell in programme_cells(pdf_path):
            if cell["clock"] is None:
                continue
            key = (cell["code"], cell["section"])
            fingerprint = (cell["code"], cell["section"], cell["day"], cell["clock"], cell["room"])
            if fingerprint in checked:
                continue
            checked.add(fingerprint)
            seen.add(key)
            meetings = master.get(key, [])
            match = [m for m in meetings if m["day"] == cell["day"] and m["room"].replace(" ", "") == cell["room"].replace(" ", "")
                     and minutes(m["start"]) - 30 <= minutes(cell["clock"]) <= minutes(m["end"])]
            if not match:
                wrong.add((cell["code"], cell["section"], cell["day"], cell["clock"], cell["room"],
                           tuple((m["day"], m["start"], m["end"], m["room"]) for m in meetings)))
    print("different cells checked:", len(checked))
    print("cells that do not match the master:", len(wrong))
    for item in sorted(wrong)[:60]:
        print("  ", item)
    print("master sections never seen per programme:", len(set(master) - seen), sorted(set(master) - seen)[:60])


if __name__ == "__main__":
    main(sys.argv[1], *sys.argv[2:])
