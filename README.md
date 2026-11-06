# Lance

Plan your Nova SBE course bidding: see every clash before you bid, what a seat cost last round, and what your bid will really cost.

*Lance* is Portuguese for a bid. Team project for Introduction to Programming, Nova SBE 2026/27. It grew out of the solo project Festival Architect (see the history of this repository): a stage became a student's week, an artist a course section, a fee a bid, the festival budget the points balance. Not an official Nova SBE system; bids are placed on Nova's platform only.

## Run it

```
uv sync
uv run flask --app app run --port 8770
```

Open http://127.0.0.1:8770 and press *Load an example*, or pick sections on the left.

## Test it

```
uv run pytest
```

The tests run on a throwaway database built from the real data. `tests/test_real_accounts.py` checks the money against two real bidding accounts from Fall 2026.

## How it is built

| File | What lives there |
|---|---|
| `app.py` | The screens: every address the browser can ask for |
| `logic.py` | The rules: clashes, prices, points, ratings, shared price data |
| `db.py` | Storage: one SQLite file, no rules |
| `templates/`, `static/` | What the pages look like; JavaScript only draws what `logic.py` answers |
| `seed/` | The content: courses, sections, sessions, exams and past prices |
| `scripts/` | How the content is made from Nova's PDFs (`docs/data.md`) |
| `tests/` | One test file per group of rules |
| `docs/product-brief.md` | Requirements, rules and acceptance scenarios |

Content and progress are separate: `seed/` is rebuilt into the database whenever it changes; plans, ratings and shared prices are never touched by that.

## Deploy it

Any host that runs a container and keeps one folder across restarts:

```
docker build -t lance .
docker run -p 8000:8000 -v lance-data:/data lance
```

`LANCE_DB` sets where the database file lives.
