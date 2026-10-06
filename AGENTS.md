# Festival Architect — notes for the coding agent

Solo project for Introduction to Programming (Nova SBE 2026/27). The product brief is `docs/product-brief.md`; the rule ids (FA01, FA R2, A1 …) come from there. The person asking has to explain this code in an exam, so explain, don't just do.

## Running things

- Run the app: `uv run streamlit run app.py`. Never use `pip` or `python -m venv`.
- Tests: `uv run pytest`. Every test must pass before a merge.
- Reset the data: `uv run python seed.py` rebuilds `data/festival.db` from `seed/*.csv` (empty lineup, plan back to draft).

## The project

- `app.py` = the screens, `logic.py` = the rules, `db.py` = the only file that talks to SQLite.
- `seed/` holds the fixed content (stages, artist catalogue). `data/festival.db` holds that content plus the organiser's progress (bookings, draft or final). It is created on first start and never committed.
- Times are stored as text `HH:MM`; the end of a set is always calculated from the start and the artist's duration, never stored.

## Rules for changes

- One branch per task, named after the spec in `specs/`.
- Tests first: write or update the tests from the brief's expected outcomes, have them reviewed, then implement. Never weaken, skip or delete a test to make it pass; if a test is wrong, fix it against the brief and say so.
- A rejected action must not write anything. Every rule check happens in `logic.py` before `db.py` is called.
- Finish with `uv run pytest` output, the list of changed files, and how to check the change in the running app, including stopping and restarting it.
- Every claim about the code comes with file and line.
