# Where the data comes from

| Table in `seed/` | Source | Made by |
|---|---|---|
| `master_meetings` | SharePoint *Masters Nova SBE*, `04. Schedules`, master timetable v02/10/2026 | `scripts/extract_schedule.py` |
| `programme_meetings` | Same folder, `View per program`, S1T1 and S1T2 | `scripts/extract_programme_schedules.py` |
| `electives` | `03. Electives`, six lists | `scripts/extract_electives.py` |
| `exams` | `05. Exams & Midterms`, regular and make-up calendars, V20260928 | `scripts/extract_exams.py` |
| `syllabi` | Nova's public course sheets, no login | `scripts/fetch_syllabi.py`, `scripts/extract_syllabi.py` |
| `offerings`, `sections`, `meetings`, `sessions`, `programme_offerings`, `calendar` | The above with `spring_mandatory`, plus the academic calendar (holidays, make-up days) and the irregular schedules | `scripts/build_seed.py` |
| `spring_mandatory` | Kept by hand, read on 18 Nov 2026. *Programme page*: the course stands under "Mandatory Courses" on Nova SBE's page of the programme (novasbe.unl.pt, Programs, Masters, the programme, Program). *Offered again*: the course is mandatory in fall by the timetable, and NOVA's programme catalogue 2026-2027 (guia.unl.pt) lists it in a spring term as well. Code, term and ECTS always come from the programme catalogue | by hand |
| `course_ratings` | Uni Feedback (uni-feedback.com), an independent review site: the public course lists of the six master's programmes, read on 17 Nov 2026. Rating, number of reviews and workload per course; no review text | `scripts/fetch_ratings.py` |
| `cutoffs`, `bid_histogram` | One student's rank lists on the bidding platform, totals only | The same reading as the bookmarklet in `static/share-bookmarklet.js` |

Raw PDFs stay in `data/raw/`, which is never committed. Room distribution lists are never downloaded: they contain student numbers.

## How it was checked

- **Two timetables against each other.** Every one of the 429 teaching blocks in the master timetable is covered by the per-programme timetables. The per-programme files are the main source because their cells have exact boxes. Three meetings exist only there: 2174 TXA Tue, 2217 TXA Mon, 2966 TXD Fri, all in B.0.10, plus 2743 TXB Wed.
- **Against a real account.** Sections, times and exams of one real student match the platform's schedule page.
- **Against a real account's money.** See scenario A1.
- **The bookmarklet against the first reading.** Run on the real platform on 6 Nov 2026: 7 of 7 sections identical in seats, bids, winners, cut-off and lowest bid. Every row held exactly three fields: rank value, bid, won.

- **The spring against three sources.** Every course on Nova's six elective lists is in Lance (269 pairs of course and term; only Nova Students Portfolio, a whole-year course, is left out). The mandatory courses of the spring were missing, because they stand on no elective list and the spring timetable is not published: 22 rows in `spring_mandatory`, 20 of them new courses. Building the tables again without that file changes nothing, and with it only adds rows. Left out on purpose, because the sources disagree or name no code: *Empirical Methods for Finance* (mandatory in Finance; the catalogue says Fall 1st Half, the fall timetable does not have it), *Social Entrepreneurship* (mandatory in Impact Entrepreneurship, Term 3; no code in the catalogue), *Statistical Analysis* in spring (the catalogue still lists Statistics II and III under other codes).
- **Ratings against the page.** Introduction to Programming: 4.6 from 18 reviews, Light, as on its page on Uni Feedback. 217 of 220 course names matched by themselves, two more by hand (`OTHER_NAMES` in the script); 153 courses have at least one review, 61 of them exactly one. The site lists a course once per programme: the entry with the most reviews is taken.

## Refresh when Nova publishes something new

1. Put the new PDFs in `data/raw/`.
2. Run the `extract_*` scripts with the paths from their first lines.
3. `uv run python -I scripts/build_seed.py`
4. `uv run pytest`

Ratings change whenever a student writes a review: `uv run python -I scripts/fetch_ratings.py seed/offerings.csv seed/course_ratings.csv`, six requests. `tests/test_ratings.py` names the numbers of 17 Nov 2026 and has to follow.

For spring, `scripts/build_seed.py` needs the class dates of T3 and T4 in `TERM_WEEKS` (from the academic calendar). As of 6 Nov 2026 the spring timetable and the spring course sheets are not published: 0 of 168 sheets could be fetched.
