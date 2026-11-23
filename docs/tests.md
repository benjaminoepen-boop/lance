# What the tests check, and what they do not

`uv run pytest` runs 359 tests in about a minute. Every test starts on its own throwaway database, built from the real files in `seed/` (`tests/conftest.py`), so the numbers in the tests are Nova's real courses, times and prices. GitHub runs the tests and a check of the dependencies on every pull request and on every push to `main` (`.github/workflows/tests.yml`). The click-through in real browsers needs a running server and four browsers, so it is run by hand before a merge (`AGENTS.md`).

## The test files

| File | Tests | Accepted actions | Refused actions | Edge cases |
|---|---|---|---|---|
| `test_real_accounts.py` | 3 | Two real accounts from Fall 2026 come out to the point: what bidding holds, what the seat costs, what is left (A1) | | The price uses the lowest winning bid of the whole course, not of the section |
| `test_rules.py` | 16 | Prices on the primary list, the alternate list and in add/drop (LN R3 to R5); the rank bonus (LN R7) | A bid that is negative, not whole or above the balance; the saved bid stays (LN R10) | Touching classes do not clash (LN R1); an empty bid is not a bid of zero; a course counts once for the ECTS, the alternate list not at all (LN R8) |
| `test_clashes.py` | 12 | Real clashes on the real timetable, date by date (A2); overlapping exams and a midterm during a class (A3); two exams on one day are a hard day (LN R16) | | Two sections of one course never clash; T1 and T2 at the same weekday and time do not clash; exams in one slot are a clash, not a hard day |
| `test_data.py` | 9 | The built tables match what is known from other sources: classes, rooms, make-up days, exam dates (A4) | | No class on a holiday; every section has a plausible number of classes |
| `test_simple_flow.py` | 59 | Plus takes the first section that fits (LN R11); switching keeps bid, list and place (LN R12); remove and undo (LN R15); one bid for all sections of a course | A mandatory course without a named section; the same course twice; an unknown section; a bid before the points | A backup and an alternate report in their own row (LN R13); the worst clash comes first; a new programme changes what is mandatory |
| `test_app.py` | 31 | The same through the requests the browser sends: a plan survives a restart and a rebuild of the content (A5), the calendar file (A6), shared rank lists become totals (A8), the example plan | Another visitor's plan; a post that is not JSON; a rank list with a personal column is refused whole; something else pasted | No table can hold a student number; a shorter rank list never replaces a longer one; spring works without a timetable |
| `test_refusals.py` | 27 | One section taken out alone; a course moved to the alternate list | Unknown sections, courses, lists and semesters; points that are no number; undo with rows that are wrong in any one field, and nothing of such an undo is saved; rank lists that cannot be read | A backup and an alternate that meet during a midterm; bids that hold more than a smaller balance; the days on which a half of the semester and a bidding round begin and end |
| `test_shared_lists.py` | 19 | A real rank list counts; the highest bid with the rank bonus is taken (LN R18, A12) | A field beside final, bid and allocated; an endless bid; a section or a round that is not real; more than 1000 rows or 60 lists | Made-up years cannot blow up a course sheet; a shared list never replaces our own; an older round never hides the newest |
| `test_undo.py` | 22 | The left arrow takes back adding, switching, bids, moves, removals, Reset and the example; the right arrow does it again (LN R19, A13) | Nothing to undo is said in words; a refused change leaves no step | Fifty steps and no more; a new change drops what could be done again; never the other semester or another plan; the steps survive a restart |
| `test_points.py` | 9 | Without typed points, an estimate from the mandatory courses (LN R17) | The estimate is never saved as if it had been typed | Never below zero; a course counts once; typed points win, an empty field brings the estimate back |
| `test_areas.py` | 21 | An area of expertise is chosen, saved and marked in the course list; its progress is counted (LN R20) | An area of another programme changes nothing | Changing the programme clears the area; only the primary list counts; courses taught elsewhere are named, not counted |
| `test_calendar.py` | 10 | Every bidding and add/drop window as an all-day event with a reminder the day before (LN R21, A6) | Windows that have ended are left out | No line longer than 75 bytes; every event keeps its UID; summer and winter time match the time zone database |
| `test_spring_mandatory.py` | 9 | The mandatory courses of the spring are in the catalogue (A11) | | Without a timetable a mandatory course is added without a section; the fall is untouched |
| `test_ratings.py` | 7 | Rating, number of reviews and workload from Uni Feedback (A7, LN07) | Lance takes no ratings itself | A course nobody reviewed has no rating |
| `test_finish_share.py` | 7 | The last step asks students who bid before for their rank lists | | A first-semester student is told there is nothing to share yet |
| `test_dark_mode.py` | 10 | A dark scheme for every colour, chosen by the system or by the switch | | Text, course colours and status colours stay readable on every surface |
| `test_skin.py` | 5 | The look loads after the base styles | The look loads nothing from outside and never changes what a colour means | It keeps still when less motion is asked for; no control moves under the mouse |
| `test_logo.py` | 4 | The envelope in the top bar, the browser tab and on a home screen | | Picture sizes for an iPhone and an installed app |
| `test_share_video.py` | 2 | The share page plays the video with captions (LN08) | | The files come with their types |

`tests/browser/flow.cjs` is not a pytest file. It clicks the whole way a student goes, in Chromium on a laptop and a small laptop, in Safari on an iPhone and in Chrome on an Android phone, and checks more than 90 things per device that only a browser can know: that a click changes what is on the screen, that nothing scrolls sideways, that a course has the same colour in the list, the week and its bid card.

## How much of the code runs in a test

Measured with `uv run pytest --cov=app --cov=logic --cov=db --cov-report=term-missing`:

| File | Before `test_refusals.py` (18 Nov) | 23 Nov, all tests |
|---|---|---|
| `app.py` | 96 % | 100 % |
| `logic.py` | 95 % | 99 % |
| `db.py` | 91 % | 93 % |
| All three | 94 % | 98 % |

The 27 new tests were written for lines that are a rule, a refused input or an edge case. No test exists only to raise the number.

## What no test checks, and why

- **Four readers in `db.py` that nothing calls** (`load_offering`, `load_section`, `load_sessions`, and `load_exams` with a list of courses): the 17 lines missing in `db.py` are mostly these. They hold no rule; they are candidates to delete.
- **A missing seed file and an empty table** (`read_seed`, `insert_rows`): the tests always run on the complete `seed/`.
- **The scripts in `scripts/`** that read Nova's PDFs: they need the PDFs, which are never committed. Their result is checked instead: `test_data.py` compares the built tables with a real account and the academic calendar, and `docs/data.md` says how each table was checked by hand.
- **The static preview in `preview/`**: it is a sharing aid, not the app. `preview/check_parity.py` compares its rules with `logic.py`, by hand, before it is shared.
- **Nova's platform itself**: Lance never logs in anywhere. That a plan can be typed into the platform was checked once by hand (`docs/usability.md`).
- **Many visitors at once**: every test is one visitor after another. SQLite takes one writer at a time, which is enough for a class, not for a campus.
- **What the pages look like**: the browser run checks that things are there and react, not that they look right. That is looked at by hand in a laptop and a phone window before a merge (`AGENTS.md`).
