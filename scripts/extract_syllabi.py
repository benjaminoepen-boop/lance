"""Pull the useful parts out of the public course sheets: synopsis, assessment and exam weights.

Run:  uv run python -I scripts/extract_syllabi.py data/raw/syllabi seed/syllabi.csv
"""
import csv
import glob
import json
import os
import re
import sys

import pdfplumber

def shorten(label, limit=60):
    """A long label ends at a whole word, and says that it goes on."""
    label = label.strip()
    if len(label) <= limit:
        return label
    return label[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-(") + "…"


URL = "https://apps.novasbe.pt/SigesAutomations/controlador?modo=FUC&CD_LECTIVO=202627&CD_DISCIP={code}&CD_DURACAO={term}"
FOOTER = re.compile(r"Nova SBE \| SYLLABUS.*|COURSE SYLLABUS|^\d{4} - .* ECTS$|^(Fall|Spring) Semester$|^\d{6}$", re.M)
HEADS = ["COURSE INSTRUCTOR", "SHORT BIOGRAPHY", "INSTITUTIONAL EMAIL", "OFFICE HOURS", "COURSE SYNOPSIS",
         "PREREQUISITE(S) / PRÉ-REQUISITO(S)", "COURSE UNIT AIMS", "COURSE UNIT CONTENT", "LESSON PLAN",
         "LEARNING OBJECTIVES", "TEACHING AND LEARNING METHODS", "ASSESSMENT", "BIBLIOGRAPHY", "ADDITIONAL INFORMATION"]


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def section_text(text, head):
    """The text between one heading and the next heading of the sheet."""
    start = text.find(head)
    if start < 0:
        return ""
    start += len(head)
    ends = [text.find(other, start) for other in HEADS if other != head]
    ends = [end for end in ends if end >= 0]
    return text[start: min(ends) if ends else len(text)].strip()


def weights_in(assessment):
    """Find 'Final exam - 60%' style pairs. Only returned when they add up to about 100."""
    # First the strict reading: one item per line, name first, then its share.
    strict = []
    for line in assessment.split("\n"):
        match = re.match(r"^[\s•·\-–\d.)]*([A-Za-z][^%:\n]{2,60}?)\s*(?:[-–:(]|\s)\s*\(?(\d{1,3})\s*%", clean(line))
        if match and 3 <= int(match.group(2)) <= 100:
            label = clean(match.group(1)).strip(" -–:,.(")
            label += ")" if label.count("(") > label.count(")") else ""
            strict.append({"label": label[0].upper() + label[1:], "percent": int(match.group(2))})
    if 95 <= sum(item["percent"] for item in strict) <= 105:
        return strict
    # Then the loose reading for sheets that write it as running text.
    found = []
    for line in re.split(r"\n|;|•|·|\. ", assessment):
        line = clean(line)
        match = re.search(r"(\d{1,3})\s*%", line)
        if not match or not 3 <= int(match.group(1)) <= 100:
            continue
        label = clean(re.sub(r"\(?\d{1,3}\s*%\)?", " ", line))
        label = re.sub(r"^[\-–:,.\s]+|[\-–:,.\s]+$", "", label)
        label = shorten(re.split(r":|, |\s[–-]\s", label)[0])
        if label:
            found.append({"label": label[0].upper() + label[1:], "percent": int(match.group(1))})
    total = sum(item["percent"] for item in found)
    return found if 95 <= total <= 105 else []


def read_sheet(path):
    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    text = FOOTER.sub("", text)
    return text


def main(folder, csv_path):
    rows = []
    for path in sorted(glob.glob(os.path.join(folder, "*.pdf"))):
        code, term = os.path.basename(path)[:-4].split("_")
        text = read_sheet(path)
        assessment_raw = section_text(text, "ASSESSMENT")
        rows.append({"code": code, "term": term, "url": URL.format(code=code, term=term),
                     "synopsis": clean(section_text(text, "COURSE SYNOPSIS") or section_text(text, "COURSE UNIT AIMS"))[:1200],
                     "assessment": clean(assessment_raw)[:1200],
                     "weights": json.dumps(weights_in(assessment_raw), ensure_ascii=False)})
    with open(csv_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["code", "term", "url", "synopsis", "assessment", "weights"])
        writer.writeheader()
        writer.writerows(rows)
    with_weights = sum(1 for row in rows if row["weights"] != "[]")
    print(len(rows), "sheets,", with_weights, "with exam weights")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
