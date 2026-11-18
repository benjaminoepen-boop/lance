"""Read the course ratings of Nova SBE's master's programmes from Uni Feedback and write seed/course_ratings.csv.

Uni Feedback (uni-feedback.com) is an independent site where students review courses of Portuguese universities.
Lance takes three public numbers per course from its course lists: the average rating, the number of reviews
and the workload. No review text and nothing about a person is read.

Six requests, one per programme, with a pause between them: the site's robots.txt asks for one second.

Run:  uv run python -I scripts/fetch_ratings.py seed/offerings.csv seed/course_ratings.csv
"""
import csv
import html
import re
import sys
import time
import unicodedata
import urllib.request

LIST_URL = "https://uni-feedback.com/en/nova-sbe/{degree}/courses"
DEGREES = ["mm", "mf", "me", "ba", "miei", "midpp"]
WORKLOADS = ["Very light", "Light", "Moderate", "Heavy", "Very heavy"]
# Courses whose name is written differently on the two sides: Nova's code -> the name on Uni Feedback.
OTHER_NAMES = {"2741": "Markets Incentives and Behaviour",
               "2971": "Investor Relations & Global Disclosure 3.5 Mark Oberle"}


def plain(name):
    """A course name without accents, brackets and punctuation, so that both sides can be compared."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower().replace("&", " and ")
    text = re.sub(r"\([^)]*\)", " ", text)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def courses_on(page):
    """Every course row of one list page: its id on Uni Feedback, name, rating, number of reviews and workload."""
    found = []
    for block in page.split('<a href="/en/courses/')[1:]:
        block = block.split("</a>")[0]
        number = re.match(r"(\d+)\"", block)
        name = re.search(r'<span class="truncate font-medium[^"]*">(.*?)</span>', block)
        if not number or not name:
            continue
        rated = re.search(r'title="(\d+) feedback">([\d.]+)', block)
        workload = [word for word in re.findall(r">([A-Za-z ]+)</span>", block) if word in WORKLOADS]
        found.append({
            "source_id": number.group(1), "name": html.unescape(name.group(1)).strip(),
            "rating": float(rated.group(2)) if rated else None, "reviews": int(rated.group(1)) if rated else 0,
            "workload": workload[-1] if rated and workload else "",
        })
    return found


def download(degree):
    request = urllib.request.Request(LIST_URL.format(degree=degree), headers={"User-Agent": "lance-student-project"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def main(offerings_path, out_path):
    by_name = {}
    for degree in DEGREES:
        for course in courses_on(download(degree)):
            key = plain(course["name"])
            # the same course is listed once per programme: the entry with the most reviews speaks for it
            if key not in by_name or course["reviews"] > by_name[key]["reviews"]:
                by_name[key] = course
        time.sleep(1.2)
    names = {}
    with open(offerings_path, encoding="utf-8") as file:
        for row in csv.DictReader(file):
            names.setdefault(row["code"], row["name"])
    rows = []
    for code, name in sorted(names.items()):
        course = by_name.get(plain(OTHER_NAMES.get(code, name)))
        if course and course["reviews"]:
            rows.append({"code": code, "rating": course["rating"], "reviews": course["reviews"],
                         "workload": course["workload"], "source_id": course["source_id"]})
    with open(out_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["code", "rating", "reviews", "workload", "source_id"])
        writer.writeheader()
        writer.writerows(rows)
    print(len(names), "courses in Lance,", len(rows), "with a rating on Uni Feedback")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
