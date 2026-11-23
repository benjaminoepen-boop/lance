# Lance

Course bidding planner, team project for Introduction to Programming at Nova SBE. Python, Flask, SQLite, pytest, run with uv.

## Commands

- Run: `uv run flask --app app run --port 8770`
- Test: `uv run pytest`
- Click through in real browsers: `tests/browser/flow.cjs` (how to start it is in its first lines)
- Count what a student sees: `scripts/measure.cjs`
- Rebuild the content after new PDFs: see `docs/data.md`

## Structure

Screens in `app.py`, rules in `logic.py`, storage in `db.py`. Rules never go into `db.py` or the JavaScript. JavaScript in `static/` only draws what the server answers. Requirements and rule ids (LN01, LN R1 ...) are in `docs/product-brief.md`; name the rule in the docstring of the function that implements it.

## Rules for changes

- Work on a branch, merge when the tests pass.
- Write the test first and state the expected result from the brief. Never weaken a test to get green output.
- Check changes to pages in a browser, on a phone-sized window too.
- Keep the code readable for someone who did not write it: every team member is asked about it in the walkthrough.

## Privacy, no exceptions

Other students' numbers and ECTS are never read, sent, stored or printed; only the team's own student numbers stand in `README.md`, because the course asks for them. Lance needs no keys: never create or commit `.env` files or other files with secrets. `data/raw/` is never committed. Room distribution lists are never downloaded.
