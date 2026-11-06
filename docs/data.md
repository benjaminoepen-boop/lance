# Where the data comes from

| Table in `seed/` | Source | Made by |
|---|---|---|
| `master_meetings` | SharePoint *Masters Nova SBE*, `04. Schedules`, master timetable v02/10/2026 | `scripts/extract_schedule.py` |
| `programme_meetings` | Same folder, `View per program`, S1T1 and S1T2 | `scripts/extract_programme_schedules.py` |
| `electives` | `03. Electives`, six lists | `scripts/extract_electives.py` |
| `exams` | `05. Exams & Midterms`, regular and make-up calendars, V20260928 | `scripts/extract_exams.py` |
| `syllabi` | Nova's public course sheets, no login | `scripts/fetch_syllabi.py`, `scripts/extract_syllabi.py` |
| `offerings`, `sections`, `meetings`, `sessions`, `programme_offerings`, `calendar` | The above, plus the academic calendar (holidays, make-up days) and the irregular schedules | `scripts/build_seed.py` |
| `cutoffs`, `bid_histogram` | One student's rank lists on the bidding platform, totals only | The same reading as the bookmarklet in `static/share-bookmarklet.js` |

Raw PDFs stay in `data/raw/`, which is never committed. Room distribution lists are never downloaded: they contain student numbers.

## How it was checked

- **Two timetables against each other.** Every one of the 429 teaching blocks in the master timetable is covered by the per-programme timetables. The per-programme files are the main source because their cells have exact boxes. Three meetings exist only there: 2174 TXA Tue, 2217 TXA Mon, 2966 TXD Fri, all in B.0.10, plus 2743 TXB Wed.
- **Against a real account.** Sections, times and exams of one real student match the platform's schedule page.
- **Against a real account's money.** See scenario A1.
- **The bookmarklet against the first reading.** Run on the real platform on 6 Nov 2026: 7 of 7 sections identical in seats, bids, winners, cut-off and lowest bid. Every row held exactly three fields: rank value, bid, won.

## Refresh when Nova publishes something new

1. Put the new PDFs in `data/raw/`.
2. Run the `extract_*` scripts with the paths from their first lines.
3. `uv run python -I scripts/build_seed.py`
4. `uv run pytest`

For spring, `scripts/build_seed.py` needs the class dates of T3 and T4 in `TERM_WEEKS` (from the academic calendar). As of 6 Nov 2026 the spring timetable and the spring course sheets are not published: 0 of 168 sheets could be fetched.
