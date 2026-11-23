# Lance

Plan your Nova SBE course bidding: see every clash before you bid, what a seat cost last round, and what your bid will really cost.

*Lance* is Portuguese for a bid. Team project for Introduction to Programming, Nova SBE 2026/27. It grew out of the solo project Festival Architect (see the history of this repository): a stage became a student's week, an artist a course section, a fee a bid, the festival budget the points balance. Not an official Nova SBE system; bids are placed on Nova's platform only.

## Where it runs

**https://lance.152-53-146-182.sslip.io**

One container on a server of our own, behind a proxy that speaks HTTPS. The database file lives in a volume, so plans and shared prices survive a restart and a new version. What runs there is the code on `main` (see *Deploy it* below).

## Team

| Name | Student number | GitHub |
|---|---|---|
| Benjamin Oepen | 80566 | benjaminoepen-boop |
| Niklas Wenzler | 79150 | NikiNOVA1 |
| Laurin Engels | 66495 | Laurinengels0712 |
| Finn Kindler | 80785 | finnkindler |

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
| `docs/tests.md` | What the tests check, what they do not, and how much of the code runs in a test |

Content and progress are separate: `seed/` is rebuilt into the database whenever it changes; plans and shared prices are never touched by that.

## Why it is built this way, and its limits

- **Flask with HTML pages, not Streamlit.** A week grid, two lists to move courses between, and a layout that works on a phone need control over the page. The rules stay in Python (`logic.py`); the JavaScript in `static/` only draws what the server answers.
- **One SQLite file on one server.** A class of students writes one change at a time, which SQLite handles. The file lives in a Docker volume, so plans survive a restart and a new version. *Limit:* everything is on that one server; if it is lost, so are the plans and the shared prices.
- **No accounts.** A plan belongs to a random id in a cookie, and a private link (`/p/<id>`) opens it on another device. Nobody types a password, and Lance holds nothing about a person. *Limit:* whoever has the link has the plan, and a plan without cookie or link cannot be found again. Every visit without the cookie starts a new, empty plan in the database, so a script that never keeps the cookie leaves empty plans behind; nothing limits or clears them yet.
- **No outside service while it runs.** Timetables come from Nova's PDFs and ratings from Uni Feedback, read once by the scripts in `scripts/` into `seed/` (`docs/data.md`). If Nova or Uni Feedback is down, Lance keeps working with the data of the last rebuild. *Limit:* it is only as new as that rebuild.
- **Prices only from rank lists.** Nova publishes no prices. Lance knows what a seat cost from our own accounts and from rank lists that students share; LN R18 refuses every list that could not be real, but it cannot prove that one is. *Limit:* a section nobody shared has no price yet, and a made-up list that looks real could still move a shared price; the prices from our own accounts are never replaced.
- **The spring has no timetable yet.** Nova has not published it; mandatory spring courses are added without a section (A11).
- **Deployed by hand.** A merge to `main` does not reach the server by itself; whoever merges deploys (*Deploy it*).

How it could change: a hosted database (Postgres) when one server is not enough; a login with the Nova account if plans should follow a student; an automatic deploy after every merge; the spring timetable as soon as Nova publishes it.

## Show it without a server

`preview/build_preview.py` renders the real pages into a static folder that works from a plain link. Its rules run in the browser (`preview/lance-local.js`), and `preview/check_parity.py` compares them with `logic.py` on whole plans. This folder is a sharing aid, not part of the app.

## Deploy it

Any host that runs a container, keeps one folder across restarts and puts HTTPS in front of it:

```
docker build -t lance .
docker run -p 127.0.0.1:8000:8000 -v lance-data:/data lance
```

`LANCE_DB` sets where the database file lives. The container runs as the user `lance`, who can write only `/data`. A volume made by an earlier image belongs to root; hand it over once with `docker run --rm --user root -v lance-data:/data lance chown -R lance /data`.

The port is published on 127.0.0.1 only (a proxy in another container reaches it over a shared Docker network instead), so every request comes through the proxy: Lance trusts the one proxy in front of it to say that the browser came over HTTPS. Then the plan cookie is `Secure` and the browser is told to stay on HTTPS.
