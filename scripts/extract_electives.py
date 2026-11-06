"""Read Nova's elective lists (one PDF per programme) into one table.

Uses poppler's pdftotext, whose layout mode keeps the columns in place.

Run:  uv run python -I scripts/extract_electives.py seed/electives.csv data/raw/
"""
import csv
import os
import re
import subprocess
import sys

FILES = {
    "MNG_2627_ELECTIVES.pdf": "Management",
    "FIN_2627_ELECTIVES.pdf": "Finance",
    "BA_2627_ELECTIVES.pdf": "Business Analytics",
    "ECON_2627_ELECTIVES.pdf": "Economics",
    "MIEI_2627_ELECTIVES.pdf": "Impact Entrepreneurship",
    "IDPP_202627_Electives.pdf": "Public Policy",
}
TERMS = r"S1|S2|T1|T2|T3|T4|A\d?|Y\d?|ANUAL|ANNUAL"
ROW = re.compile(rf"^\s*(\d{{4}})\s+({TERMS})\s+(.+)$")
TYPE = re.compile(r"\s+(ELECTIVE|OUT_PROGRAM|EXCLUSIVE_ELECTIVE)\s*$")


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def lecturers(text):
    """'1210 - Ricardo Pereira,806 - Martijn Boons' becomes 'Ricardo Pereira, Martijn Boons'."""
    text = re.sub(r"\b(OUT_PROGRAM|EXCLUSIVE_ELECTIVE|ELECTIVE)\b", " ", text)
    names = re.split(r",\s*(?=\d+\s*-)", clean(text))
    return ", ".join(re.sub(r"^\d+\s*-\s*", "", name).strip() for name in names if name.strip())


def read_pdf(path, programme):
    text = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True).stdout
    rows = []
    faculty_column = None
    for line in text.split("\n"):
        if "FACULTY" in line:
            faculty_column = line.index("FACULTY")
            continue
        match = ROW.match(line)
        if match:
            code, term, rest = match.groups()
            row_type = "ELECTIVE"
            type_match = TYPE.search(rest)
            if type_match:
                row_type = type_match.group(1)
                rest = rest[: type_match.start()]
            # name, optional ECTS, then the first lecturer as '1234 - Name' or 'TBD'; columns can touch
            split = re.match(r"^(.*?)\s+(?:(\d+(?:\.\d+)?)\s+)?((?:\d+\s*-\s*\S.*|TBD.*))$", rest.strip())
            if split:
                name, ects, faculty = split.groups()
            else:
                ects_only = re.match(r"^(.*?)\s+(\d+(?:\.\d+)?)\s*$", rest.strip())
                name, ects, faculty = (ects_only.group(1), ects_only.group(2), "") if ects_only else (rest, "", "")
            rows.append({"programme": programme, "code": code, "term": term, "name": clean(name),
                         "ects": ects or "", "lecturers": faculty, "type": row_type})
        elif rows and line.strip() and not re.search(r"ELECTIVES -|Page |COURSE ", line):
            # a wrapped line: it continues the name or the lecturer column of the row above
            indent = len(line) - len(line.lstrip())
            text = line.strip()
            type_match = re.search(r"\b(OUT_PROGRAM|EXCLUSIVE_ELECTIVE|ELECTIVE)\b", text)
            if type_match:
                rows[-1]["type"] = type_match.group(1)
                text = clean(text.replace(type_match.group(1), ""))
            if not text:
                continue
            if faculty_column is not None and indent >= faculty_column - 10:
                rows[-1]["lecturers"] += " " + text
            else:
                rows[-1]["name"] = clean(rows[-1]["name"] + " " + text)
    for row in rows:
        row["lecturers"] = lecturers(row["lecturers"])
    return rows


def main(csv_path, raw_dir):
    rows = []
    for name, programme in FILES.items():
        found = read_pdf(os.path.join(raw_dir, name), programme)
        print(programme, len(found))
        rows.extend(found)
    with open(csv_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["programme", "code", "term", "name", "ects", "lecturers", "type"])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
