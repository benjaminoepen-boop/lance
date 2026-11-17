# The demonstration

## Four minutes: one minute shown, three minutes for the audience to try (call of 17 Nov 2026)

Open with the pain, before the first click: "The start at Nova is chaos: four systems, and nobody tells you what a seat costs or whether your week even works. Our first bidding went wrong for most of us." Then one of us clicks and talks:

| Time | Do | Say |
|---|---|---|
| 0:00 | Choose *Management*. In *Mandatory*, *Pick* Advanced Strategy TXC, Advanced Financial Management TXC, Statistical Analysis TXC | "Three clicks for the sections Nova assigned me. No account, no login." |
| 0:15 | Point at the head of the plan: *points left, estimated* | "My points appear by themselves: an estimate from my mandatory courses, until I type the real balance." |
| 0:25 | Search *Asian Brands*: the row says *Clashes with Statistical Analysis TXC*. Press plus anyway, then *Remove* under the week | "It tells me before the click. Nova's platform would not have." |
| 0:40 | Plus on *Introduction to Programming*, tab *Bids*, type a bid | "One bid per course, and last round's answer next to it: enough or too low." |
| 0:50 | *Course details* of Introduction to Programming | "The course sheet: sections, exams, past prices, and what students say: 4.6 of 5 on Uni Feedback." |
| 1:00 | *Reset*, then hand over | "Reset, and it is yours: try your own semester." |

Clashes that are safe to show, all checked by the tests: Asian Brands against Statistical Analysis TXC (classes), Advanced Strategy TXC against Econometrics TXA (classes), Econometrics against the example plan (an exam, red). *Fits my week* hides every course that would clash.

Questions we must be able to answer: how the estimate works (`estimated_points` in `logic.py`, LN R16), where the ratings come from (`scripts/fetch_ratings.py`, `docs/data.md`), why nobody rates inside Lance (advisor: who is bidding does not want to rate), what *Fits my week* does (`matches` in `static/planner.js`: hides courses whose every section clashes with the week or whose exam clashes).

## The five minutes

For the live demonstration at the deployed address. Press the buttons in this order; every number below is checked by `tests/` and `tests/browser/flow.cjs`.

| Time | Do | Say |
|---|---|---|
| 0:00 | Open the empty address | "Courses on the left, my plan on the right: a week, empty. One sentence says what to do." |
| 0:20 | *Try an example* | "A real plan from Fall 2026: one of us, with the real bids." |
| 0:40 | Search *Asian Brands*. The row says *Clashes with Statistical Analysis TXC*. Press the plus at the right of the row | "Before the click it says what it meets. It does not stop you. The platform would not have told you." |
| 1:00 | Under the week: *You can't attend both*. Press *Remove*, then *Undo*, then *Remove* | "A way out right there, and undo instead of are-you-sure." |
| 1:20 | Search *Econometrics*, plus | "Now an exam clash: red, because Nova blocks that one, and the classes in orange. Date by date, not by weekly pattern." Remove it. |
| 1:50 | Click the row *Introduction to Programming* | "It folds open: three sections, and the same three wait in the week. No extra page." Click tile TXC. "The bid stays." Click TXB. *Course details*, *See all bids*: "298 bids for 72 seats." |
| 2:30 | Tab *Bids* on the right | "One card per course: my bid in its field, and last round's answer at the same place in every card. 165 of 165 points held while bidding. If last round repeats I pay about 132 and 33 come back: that is what the platform really charged this account. (164 + 100) / 2." |
| 3:00 | Click the card *Introduction to Programming* | "The sections in the order Nova tries them, each with last round's bids, darker where they won. The rank lists come from students, without names." |
| 3:30 | *Finish on Nova*, top right | "Nothing has been sent. Only Nova's platform counts. Copy list, calendar file with every class on its real date." |
| 4:00 | *the fall lists are out*: paste a real export, the counter rises. Paste one with a student column | "Refused whole. Only totals are kept." |
| 4:40 | *Open on another device*, then the link on a phone | "The same plan on the phone, without an account." |

Keep a browser window with this plan open as a spare. Do not show the static preview: it is not the deployed app.

Before the day: real rank lists from classmates (Laurin's card), entered on the deployed database. No invented rows. The ratings are real too: read from Uni Feedback on 17 Nov 2026.
