"""Read Nova's per-programme timetable PDFs. These are real tables, so every cell has an exact box.

A cell's box gives its weekday (from the column heads) and its start and end (from the half-hour
rows). Its fill colour tells how the course counts for that programme.

Run:  uv run python -I scripts/extract_programme_schedules.py seed/programme_meetings.csv data/raw/MSc_Schedules_S1T1.pdf data/raw/MSc_Schedules_S1T2.pdf
"""
import csv
import re
import sys

import pdfplumber

WEEKDAYS = {"Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed", "Thursday": "Thu", "Friday": "Fri", "Saturday": "Sat"}
TITLE = re.compile(r"^(.*?),\s*(\d{4})$")


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def colour_name(colour):
    """Name the three fill colours Nova uses. Yellow is an elective, blue and orange are not."""
    if colour is None:
        return "white"
    if isinstance(colour, (int, float)):
        colour = (colour, colour, colour)
    if len(colour) == 1:
        colour = (colour[0],) * 3
    r, g, b = colour[:3]
    if b > r + 0.2:
        return "blue"
    if r > 0.9 and g > 0.9 and b < 0.85:
        return "yellow"
    if r > 0.9 and 0.5 < g < 0.8:
        return "orange"
    return f"{r:.2f},{g:.2f},{b:.2f}"


def read_page(page):
    words = page.extract_words(x_tolerance=1.5, y_tolerance=2)
    heads = [w for w in words if w["text"] in WEEKDAYS]
    if len(heads) < 5:
        return None, []
    # the programme name stands at the top, right of the logo
    programme = ""
    for line in page.extract_text_lines():
        match = re.match(r"^(\d{2}\s+[A-Z].*?)(\s+Period.*)?$", clean(line["text"]))
        if match and line["top"] < 60:
            programme = match.group(1)
            break
    tables = page.find_tables()
    if not tables:
        return programme, []
    table = max(tables, key=lambda t: (t.bbox[2] - t.bbox[0]) * (t.bbox[3] - t.bbox[1]))
    cells = [c for c in table.cells]
    # the time rows: cells of the first column that hold '08:00 - 08:30'
    rows = []
    for box in cells:
        text = clean(page.crop(box).extract_text(x_tolerance=1.5, y_tolerance=2) or "")
        match = re.fullmatch(r"(\d\d:\d\d) - (\d\d:\d\d)", text)
        if match:
            rows.append((box[1], box[3], match.group(1), match.group(2)))
    rows.sort()
    # the day columns: the header cells holding the weekday names
    columns = []
    for box in cells:
        text = clean(page.crop(box).extract_text(x_tolerance=1.5, y_tolerance=2) or "")
        if text in WEEKDAYS:
            columns.append((box[0], box[2], WEEKDAYS[text]))
    columns.sort()
    meetings = []
    for box in cells:
        text = page.crop(box).extract_text(x_tolerance=1.5, y_tolerance=2) or ""
        lines = [clean(x) for x in text.split("\n") if clean(x)]
        joined = " ".join(lines)
        match = re.search(r"^(.*?),\s*(\d{4})\s+\[\((.*?)\)\]\s+\[Room\s*(.*?)\]\s*(TX[A-Z]|T[A-Z]{1,2}\d?)?$", joined)
        if not match:
            if re.search(r",\s*\d{4}\b", joined):
                print("not understood:", repr(joined), file=sys.stderr)
            continue
        name, code, lecturer, room, section = match.groups()
        lecturer = re.sub(r"\)?;\s*\(?", ", ", lecturer)
        x_middle = (box[0] + box[2]) / 2
        day = next((d for x0, x1, d in columns if x0 - 1 <= x_middle <= x1 + 1), "")
        y_top, y_bottom = box[1], box[3]
        inside = [r for r in rows if r[0] >= y_top - 2 and r[1] <= y_bottom + 2]
        if not inside:
            print("no time rows for:", joined, file=sys.stderr)
            continue
        # fill colour: the rectangle behind the middle of the cell
        fill = None
        x_c, y_c = x_middle, (y_top + y_bottom) / 2
        for rect in page.rects:
            if rect.get("fill") and rect["x0"] - 1 <= x_c <= rect["x1"] + 1 and rect["top"] - 1 <= y_c <= rect["bottom"] + 1:
                if rect["width"] < 900:
                    fill = rect.get("non_stroking_color")
        meetings.append({"programme": programme, "code": code, "name": name, "section": section or "",
                         "day": day, "start": inside[0][2], "end": inside[-1][3], "room": room,
                         "lecturer": lecturer, "colour": colour_name(fill)})
    return programme, meetings


def main(csv_path, *pdfs):
    rows = []
    for pdf_path in pdfs:
        period = "T1" if "S1T1" in pdf_path else "T2"
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                programme, meetings = read_page(page)
                for meeting in meetings:
                    meeting["period"] = period
                    rows.append(meeting)
    fields = ["period", "programme", "code", "name", "section", "day", "start", "end", "room", "lecturer", "colour"]
    with open(csv_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(len(rows), "programme cells written to", csv_path)


if __name__ == "__main__":
    main(sys.argv[1], *sys.argv[2:])
