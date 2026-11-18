# What the tests check, and what they do not

`uv run pytest` runs 143 tests in about half a minute. Every test starts on its own throwaway database, built from the real files in `seed/` (`tests/conftest.py`), so the numbers in the tests are Nova's real courses, times and prices. GitHub runs all of it on every pull request and on every push to `main` (`.github/workflows/tests.yml`): the tests, a check of the dependencies, and the click-through in real browsers.

## The test files

| File | Tests | Accepted actions | Refused actions | Edge cases |
|---|---|---|---|---|
| `test_real_accounts.py` | 3 | Two real accounts from Fall 2026 come out to the point: what bidding holds, what the seat costs, what is left (A1) | | The price uses the lowest winning bid of the whole course, not of the section |
| `test_rules.py` | 16 | Prices on the primary list, the alternate list and in add/drop (LN R3 to R5); the rank bonus (LN R7) | A bid that is negative, not whole or above the balance; the saved bid stays (LN R10) | Touching classes do not clash (LN R1); an empty bid is not a bid of zero; a course counts once for the ECTS, the alternate list not at all (LN R8) |
| `test_clashes.py` | 7 | Real clashes on the real timetable, date by date (A2); overlapping exams and a midterm during a class (A3) | | Two sections of one course never clash; T1 and T2 at the same weekday and time do not clash; a semester course clashes with a T2 course only in T2 |
| `test_data.py` | 9 | The built tables match what is known from other sources: classes, rooms, make-up days, exam dates (A4) | | No class on a holiday; every section has a plausible number of classes |
| `test_simple_flow.py` | 53 | Plus takes the first section that fits (LN R11); switching keeps bid, list and place (LN R12); remove and undo (LN R15); one bid for all sections of a course | A mandatory course without a named section; the same click twice; an unknown programme; a bid before the points | A backup and an alternate report in their own row (LN R13); start over leaves the other semester alone; a new programme changes what is mandatory |
| `test_app.py` | 28 | The same through the requests the browser sends: a plan survives a restart and a rebuild of the content (A5), the calendar file (A6), ratings (A7), shared rank lists become totals (A8) | Another visitor's plan; a post that is not JSON; a rank list with a personal column is refused whole; an incomplete rating | A shorter rank list never replaces a longer one; ratings stay hidden below three answers; spring works without a timetable |
| `test_refusals.py` | 27 | One section taken out alone; a course moved to the alternate list | Unknown sections, courses, lists and semesters; points that are no number; undo with rows that are wrong in any one field, and nothing of such an undo is saved; rank lists that cannot be read | A backup and an alternate that meet during a midterm; bids that hold more than a smaller balance; the days on which a half of the semester and a bidding round begin and end |

`tests/browser/flow.cjs` is not a pytest file. It clicks the whole way a student goes, in Chromium on a laptop and a small laptop, in Safari on an iPhone and in Chrome on an Android phone, and checks more than 90 things per device that only a browser can know: that a click changes what is on the screen, that nothing scrolls sideways, that a course has the same colour in the list, the week and its bid card.

## How much of the code runs in a test

Measured with `uv run pytest --cov=app --cov=logic --cov=db --cov-report=term-missing`:

| File | Before `test_refusals.py` | Now |
|---|---|---|
| `app.py` | 96 % | 99 % |
| `logic.py` | 95 % | 99 % |
| `db.py` | 91 % | 91 % |
| All three | 94 % | 98 % |

The 27 new tests were written for lines that are a rule, a refused input or an edge case. No test exists only to raise the number.

## What no test checks, and why

- **Four readers in `db.py` that nothing calls** (`load_offering`, `load_section`, `load_sessions`, and `load_exams` with a list of courses): the 17 lines missing in `db.py` are mostly these. They hold no rule; they are candidates to delete.
- **A missing seed file and an empty table** (`read_seed`, `insert_rows`): the tests always run on the complete `seed/`.
- **Two rating answers** (a grade that is no number, a rating for an unknown course): the rating form is being replaced by ratings from outside, so no test was added for it.
- **The scripts in `scripts/`** that read Nova's PDFs: they need the PDFs, which are never committed. Their result is checked instead: `test_data.py` compares the built tables with a real account and the academic calendar, and `docs/data.md` says how each table was checked by hand.
- **The static preview in `preview/`**: it is a sharing aid, not the app. `preview/check_parity.py` compares its rules with `logic.py`, by hand, before it is shared.
- **Nova's platform itself**: Lance never logs in anywhere. That a plan can be typed into the platform was checked once by hand (`docs/usability.md`).
- **Many visitors at once**: every test is one visitor after another. SQLite takes one writer at a time, which is enough for a class, not for a campus.
- **What the pages look like**: the browser run checks that things are there and react, not that they look right. That is looked at by hand in a laptop and a phone window before a merge (`AGENTS.md`).
