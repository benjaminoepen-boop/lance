"""Read Nova's exam and midterm calendars into one table.

The bidding platform lists exams with a duration of two hours, so a plain start time means two hours.

Run:  uv run python -I scripts/extract_exams.py seed/exams.csv <exams.pdf> <makeup.pdf>
"""
import csv
import re
import sys

import pdfplumber

LINE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})\s+\w+\s+(\d{2}:\d{2})(?:-(\d{2}:\d{2}))?\s+(S1|T1|T2|A)\s+(\d{4})\s+(.*)$")
NO_EXAM = re.compile(r"^No exam\s+(S1|T1|T2|A)\s+(\d{4})\s+(.*)$")


def plus_two_hours(clock):
    hours, minutes = clock.split(":")
    return str(int(hours) + 2).zfill(2) + ":" + minutes


def read_pdf(path, kind):
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for line in (page.extract_text() or "").split("\n"):
                line = line.strip()
                match = LINE.match(line)
                if match:
                    day, month, year, start, end, term, code, rest = match.groups()
                    note = ""
                    bracket = re.search(r"\(([^)]*)\)\s*$", rest)
                    if bracket:
                        note = bracket.group(1)
                        rest = rest[: bracket.start()].strip()
                    this_kind = kind
                    if "midterm" in note:
                        this_kind = "midterm"
                    elif "presentation" in note:
                        this_kind = "presentation"
                    rows.append({"code": code, "term": term, "kind": this_kind, "date": f"{year}-{month}-{day}",
                                 "start": start, "end": end or plus_two_hours(start), "name": rest, "note": note})
                    continue
                match = NO_EXAM.match(line)
                if match:
                    term, code, rest = match.groups()
                    rows.append({"code": code, "term": term, "kind": "none", "date": "", "start": "", "end": "", "name": rest, "note": "No exam"})
    return rows


def main(csv_path, exams_pdf, makeup_pdf):
    rows = read_pdf(exams_pdf, "exam") + read_pdf(makeup_pdf, "makeup")
    with open(csv_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["code", "term", "kind", "date", "start", "end", "name", "note"])
        writer.writeheader()
        writer.writerows(rows)
    print(len(rows), "exam rows")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
