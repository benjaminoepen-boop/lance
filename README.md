# Festival Architect

Solo project for Introduction to Programming (Nova SBE 2026/27), Block 2, Product 03.

A one-day planner for **Carcavelos Sound**: two stages (Beach Stage, Dune Stage), eight fictional artists, 14:00–23:00, €10,000 artist budget. The organiser books artists, sees the timetable and budget, moves or removes bookings, and finalises the plan. The brief is in `docs/product-brief.md`.

## Run it

```
uv run streamlit run app.py
```

The first start creates `data/festival.db` from `seed/`. After that the app keeps whatever was saved.

```
uv run python seed.py     # start over: empty lineup, plan back to draft
uv run pytest             # 27 tests, all green
```

## How it works

**State.** Two kinds of data live in `data/festival.db`:

| | Tables | Changes? |
|---|---|---|
| Fixed content | `stages`, `artists` (from `seed/*.csv`) | never by the app |
| Organiser's progress | `bookings` (artist, stage, start), `plan` (draft or final) | on every accepted action |

A booking stores only the **start**. The end is always calculated: start + the artist's duration (`logic.end_time`). Nothing can get out of sync. `bookings.artist_id` is the primary key, so the database itself also refuses a second booking for the same artist.

**One click, three files.** Pressing *Book* runs:

1. `app.py` `show_booking` reads artist, stage and start and calls `logic.add_booking`.
2. `logic.py` `add_booking` refuses straight away if the plan is final. Otherwise `booking_problems` checks every rule and returns the reasons it is refused.
3. Only when that list is empty does `db.py` `insert_booking` write the row. A refused booking writes nothing.
4. Back in `app.py`, `finish_click` remembers the outcome and redraws the page, so the timetable and budget show the saved data, with the message under the button.

**Edits are replacements (FA R5).** `move_booking` checks the new slot against all bookings *except* the artist's own (`without`). So shifting a set by 30 minutes does not clash with its old slot, and the fee is not counted twice.

**Persistence.** Every accepted action is written to SQLite immediately (`db.execute` commits). The app holds no state of its own between clicks; every screen reads from the database. Stopping and restarting the app therefore shows exactly what was saved.

## Where each rule lives

| Rule | Code |
|---|---|
| FA R1 one booking per artist, fee once | `booking_problems` (first loop), `total_fees` |
| FA R2 14:00–23:00 | `inside_festival_hours` |
| FA R2 no overlap on a stage, touching allowed | `overlaps` (`<`, not `<=`) |
| FA R3 same time on different stages | `booking_problems` skips other stages |
| FA R4 budget, exactly €10,000 allowed | `within_budget` (`<=`) |
| FA R5 edits as replacements, final is read-only | `move_booking` + `without`, `is_final` checks in every action |
| FA05 finalise needs 4 artists and a valid lineup | `finalise`, `lineup_problems` |

## Acceptance scenarios and their tests

| Brief | Test in `tests/test_acceptance.py` |
|---|---|
| A1 same stage conflict | `test_a1_overlap_on_the_same_stage_is_refused`, `test_a1_starting_when_the_previous_set_ends_is_accepted` |
| A2 different stages | `test_a2_same_time_on_different_stages_is_accepted` |
| A3 festival boundaries | `test_a3_sixty_minute_set_at_the_edges_of_the_day` |
| A4 budget and duplicates | `test_a4_spending_exactly_the_budget_is_accepted`, `test_a4_one_euro_over_the_budget_is_refused`, `test_a4_an_artist_already_booked_is_refused_on_any_stage` |
| A5 edit and remove | `test_a5_*` (conflicting edit, valid edit, replacement, fee not charged twice, removal) |
| A6 save and finalise | `test_a6_*` here, plus restart tests in `tests/test_app.py` |

`tests/test_rules.py` checks the calculations alone (times, overlaps, budget boundary). `tests/test_app.py` clicks through the screens with Streamlit's AppTest; a new AppTest is a fresh start of the app. Every test gets its own throwaway database (`tests/conftest.py`), so `data/` is never touched.

## Try it by hand (A1 and restart)

1. *Book an artist*: The Tidewaters, Beach Stage, 16:00 → booked 16:00–17:00, budget left €6,500.
2. Os Gaivotas, Beach Stage, 16:30 → refused: clashes with The Tidewaters.
3. Os Gaivotas, Beach Stage, 17:00 → booked.
4. Stop the app (Ctrl+C in the terminal) and start it again → both bookings and €5,000 left are still there.

## Folder map

```
app.py            the three screens: Timetable, Book an artist, Change a booking
logic.py          the rules: times, clashes, budget, add / move / remove, finalise / reopen
db.py             the only file that talks to SQLite: schema, seed, fetch, execute
seed.py           uv run python seed.py -> fresh database
seed/             fixed content: stages.csv, artists.csv
data/festival.db  the live database (not in git)
docs/             product brief (copy of the BRD)
specs/            first-feature.md, the spec the build started from
tests/            rules, acceptance scenarios A1–A6, screens
AGENTS.md         how a coding agent should work in this repo
```
