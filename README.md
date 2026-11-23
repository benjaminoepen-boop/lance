# Lance

Plan your Nova SBE course bidding: see every clash before you bid, what a seat cost last round, and what your bid will really cost.

*Lance* is Portuguese for a bid. Team project for Introduction to Programming, Nova SBE 2026/27. It grew out of the solo project Festival Architect (see the history of this repository): a stage became a student's week, an artist a course section, a fee a bid, the festival budget the points balance. Not an official Nova SBE system; bids are placed on Nova's platform only.

## Run it

```
uv sync
uv run flask --app app run --port 8770
```

Open http://127.0.0.1:8770 and press *Try an example*, or choose your programme and press plus on a course.

## Test it

```
uv run pytest
```

The tests run on a throwaway database built from the real data. `tests/test_real_accounts.py` checks the money against two real bidding accounts from Fall 2026.

`tests/browser/flow.cjs` clicks the whole way through in real browsers: a laptop, a small laptop, an iPhone and an Android phone. `scripts/measure.cjs` counts the controls and words a student sees on each screen. Both need Playwright; how to start them is in their first lines.

## How it is built

| File | What lives there |
|---|---|
| `app.py` | The screens: every address the browser can ask for |
| `logic.py` | The rules: clashes, prices, points, shared price data |
| `db.py` | Storage: one SQLite file, no rules |
| `templates/`, `static/` | What the pages look like; JavaScript only draws what `logic.py` answers |
| `seed/` | The content: courses, sections, sessions, exams, course ratings and past prices |
| `scripts/` | How the content is made from Nova's PDFs and from Uni Feedback (`docs/data.md`) |
| `tests/` | One test file per group of rules |
| `docs/product-brief.md` | Requirements, rules and acceptance scenarios |
| `docs/walkthrough.md` | Six clicks from the button to the database |
| `docs/demo.md` | The five minutes of the live demonstration |
| `docs/usability.md` | Who used it without help, and what changed because of it |

Content and progress are separate: `seed/` is rebuilt into the database whenever it changes; plans and shared prices are never touched by that.

## Show it without a server

`preview/build_preview.py` renders the real pages into a static folder that works from a plain link. Its rules run in the browser (`preview/lance-local.js`), and `preview/check_parity.py` compares them with `logic.py` on whole plans. This folder is a sharing aid, not part of the app.

## Deploy it

Any host that runs a container, keeps one folder across restarts and puts HTTPS in front of it:

```
docker build -t lance .
docker run -p 8000:8000 -v lance-data:/data lance
```

`LANCE_DB` sets where the database file lives. The container runs as the user `lance`, who can write only `/data`. A volume made by an earlier image belongs to root; hand it over once with `docker run --rm --user root -v lance-data:/data lance chown -R lance /data`.

Lance trusts the one proxy in front of it to say that the browser came over HTTPS. Then the plan cookie is `Secure` and the browser is told to stay on HTTPS.
