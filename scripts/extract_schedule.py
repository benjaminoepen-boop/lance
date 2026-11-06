"""Read Nova's master timetable PDF into plain rows, one row per weekly class meeting.

The PDF is one big grid: days across, time blocks down, one small band per room inside each block.
Each day has two half columns, T1 on the left and T2 on the right; S1 cells cover the whole day.
Each course cell reads like this:

    T1 2243 Real Estate Finance TXA
    Prof. João Pedra Soares
    Room: D.-1.05

Run:  uv run python -I scripts/extract_schedule.py data/raw/<schedule>.pdf seed/weekly_meetings.csv
"""
import csv
import re
import sys
from collections import Counter

import pdfplumber

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
GRID_LEFT = 68.0
HALF_COLUMN = 56.4          # one day is two half columns
BAND_HEIGHT = 21.72         # one band per room inside a time block
TERMS = "S1|S2|T1|T2|T3|T4"
CELL_START = re.compile(rf"({TERMS}) (\d{{4}})\b")   # no word boundary in front: neighbouring cells can touch
SECTION = re.compile(r"\b(T[A-Z]{1,2}\d?)\s*$")


def time_blocks(page):
    """Find the time blocks of one page from the sideways labels in the margin.

    The labels are printed bottom to top and come out reversed ('03:90' means 09:30). Returns
    [(top, 'HH:MM', 'HH:MM')] from top to bottom. A label with a negative top belongs to a block that
    started on the previous page and still runs at the top of this one.
    """
    words = page.extract_words(x_tolerance=1.5, y_tolerance=2)
    margin = sorted((w for w in words if w["x0"] < GRID_LEFT and w["x1"] > 55), key=lambda w: w["top"])
    blocks = []
    for i, word in enumerate(margin):
        if word["text"] != "|":
            continue
        times = [w["text"] for w in margin[i + 1:i + 4] if re.fullmatch(r"\d\d:\d\d", w["text"])]
        if len(times) == 2:
            blocks.append((word["top"], times[1][::-1], times[0][::-1]))
    return blocks


def block_at(blocks, y):
    """The time block a vertical position belongs to."""
    current = None
    for top, start, end in blocks:
        if top <= y:
            current = (start, end)
    return current


def band_offset(page):
    """The vertical position of the room bands on this page, read from the cell rectangles."""
    tops = [r["top"] for r in page.rects if 15 < r["height"] < 30 and r["width"] > 50]
    return Counter(round(top % BAND_HEIGHT) for top in tops).most_common(1)[0][0]


def lattice(index):
    """The x position of a half column line, 0 being the left edge of Monday."""
    return GRID_LEFT + index * HALF_COLUMN


def text_lines(chars):
    """Group characters into lines. Spaces come from the PDF itself, so letter-spaced text stays whole."""
    lines = {}
    for char in sorted(chars, key=lambda c: c["top"]):
        for top in lines:
            if abs(top - char["top"]) < 1.2:
                lines[top].append(char)
                break
        else:
            lines[char["top"]] = [char]
    result = []
    for top in sorted(lines):
        result.append(sorted(lines[top], key=lambda c: c["x0"]))
    return result


def line_text(chars):
    return "".join(c["text"] for c in chars)


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def parse_cell(text):
    """Split the text of one cell into its fields."""
    match = re.search(rf"({TERMS})\s+(\d{{4}})\s+(.*)$", clean(text))
    if not match:
        return None
    term, code, rest = match.groups()
    room = ""
    room_match = re.search(r"Room:?\s*(.*)$", rest)
    if room_match:
        room = room_match.group(1).strip()
        rest = rest[: room_match.start()].strip()
    lecturer = ""
    prof_match = re.search(r"Prof\.?\s*(.*)$", rest)
    if prof_match:
        lecturer = prof_match.group(1).strip()
        rest = rest[: prof_match.start()].strip()
    section = ""
    section_match = SECTION.search(rest)
    if section_match:
        section = section_match.group(1)
        rest = rest[: section_match.start()].strip()
    delivery = ""
    if lecturer.endswith("#B"):
        delivery = "blended"
        lecturer = lecturer[:-2].strip()
    return {"term": term, "code": code, "name": rest, "section": section, "lecturer": lecturer,
            "room": room, "delivery": delivery}


def read_page(page):
    """Return the course cells of one page."""
    offset = band_offset(page)
    chars = [c for c in page.chars if lattice(0) - 1 <= c["x0"] <= lattice(10) + 1 and c["top"] > 40]

    # Inside a time block the rooms run in a fixed order starting with D.-1.04, and on some pages the
    # label in the margin sits one band below the real start of its block. So a block starts at the
    # band of the D.-1.04 row closest to its label.
    first_room = [line[0]["top"] for line in text_lines(chars) if "Room: D.-1.04" in line_text(line)]
    blocks = []
    for label_top, start, end in time_blocks(page):
        near = [y for y in first_room if abs(y - label_top) <= 22]
        if near:
            band = int((min(near, key=lambda y: abs(y - label_top)) + 3 - offset) // BAND_HEIGHT)
            label_top = offset + band * BAND_HEIGHT
        blocks.append((label_top, start, end))

    # every cell starts with its term and a four-digit code; find those on each line
    starts = []
    for line in text_lines(chars):
        text = line_text(line)
        matches = list(CELL_START.finditer(text))
        for n, match in enumerate(matches):
            end = matches[n + 1].start() if n + 1 < len(matches) else len(line)
            own = line[match.start():end]
            own = [c for c in own if c["text"].strip()]
            starts.append({"x0": own[0]["x0"], "x1": own[-1]["x1"], "top": own[0]["top"]})

    bands = {}
    for start in starts:
        # a few points below the first line: tall cells start right at the edge of their band
        bands.setdefault(int((start["top"] + 3 - offset) // BAND_HEIGHT), []).append(start)

    rows = []
    for band, band_starts in bands.items():
        top = offset + band * BAND_HEIGHT
        bottom = top + BAND_HEIGHT
        in_band = [c for c in chars if top - 0.5 <= (c["top"] + c["bottom"]) / 2 < bottom + 0.5]
        for start in band_starts:
            position = ((start["x0"] + start["x1"]) / 2 - GRID_LEFT) / HALF_COLUMN
            day = max(0, min(4, int(position // 2)))
            # text that crosses the middle of the day belongs to a cell covering the whole day
            middle = lattice(2 * day + 1)
            full_day = start["x0"] < middle - 2 and start["x1"] > middle + 2
            if full_day:
                left, right = lattice(2 * day), lattice(2 * day + 2)
            else:
                half = int(position)
                left, right = lattice(half), lattice(half + 1)
            cell_chars = [c for c in in_band if left - 0.5 <= (c["x0"] + c["x1"]) / 2 <= right + 0.5]
            text = " ".join(line_text(line) for line in text_lines(cell_chars))
            cell = parse_cell(text)
            if cell is None:
                continue
            block = block_at(blocks, top + BAND_HEIGHT / 2)   # the middle of the band, never its edge
            cell["day"] = DAYS[day]
            cell["start"], cell["end"] = block if block else ("", "")
            rows.append(cell)
    return rows


def main(pdf_path, csv_path):
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            rows.extend(read_page(page))
    rows.sort(key=lambda r: (r["code"], r["term"], r["section"], DAYS.index(r["day"]), r["start"]))
    fields = ["code", "name", "term", "section", "day", "start", "end", "room", "lecturer", "delivery"]
    with open(csv_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(len(rows), "meetings written to", csv_path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
