# Second team feature: the simple flow

## Why

The first version showed the whole data model on every screen. A student should understand Lance without reading: what do I take, how much do I bid, what do I do now. Measured on the first screen with a plan: 70 controls and 302 words, close to CourseTable's catalogue (71 and 399), the densest screen we looked at. Semester.ly has 24 and 108, NUSMods 35 and 119.

## What

One screen in two halves: **courses** on the left, **your plan** on the right with the tabs *Week*, *Bids* and *Summary*. Then **Finish on Nova**. `/bids` is the same screen with *Bids* open. The rules of the brief stay; five are added (LN R11 to R15). The side navigation, the head card, the filter chips, the section chips in the list, the exam cards and the colour per course are gone.

**Courses.** Above the list: programme, semester, `T1 | T2`. The half is one switch for both halves; a search looks through everything. Courses come in groups: Mandatory, Electives, Other programmes. Every row starts with the same add control: a plus adds an elective with the first section that fits and folds the row open, so another section is one click away; a tick says it is in, × under the mouse takes it out. On a mandatory course the same square opens the sections (*Pick your section*), because Nova assigned the section. A click anywhere else on the row folds it open in place: its sections as tiles with day and time, each saying whether it clashes, and the same sections as ghosts in the week, standing beside what they clash with. One click on a tile or a ghost picks or switches the section. *Course details* opens the whole course in the same half.

**Your plan.** The head says where you stand (ECTS, points left, clashes); a tab names what needs a look ("1 clash", "1 too low"). *Week*: your week, the clashes under it with a way out, the worst first. *Summary*: every course in one table with section, time, ECTS, exam and bid, the totals below, and *Start over*. A phone shows one half at a time; the summary sits under the week.

**Bids.** Your points on top, the only field there, next to "165 of 165 in bids · 0 left" with a slim bar, and one quiet line: if last round repeats, what you pay and what comes back. Then one card per course with one number, because only the highest is held, and last round's answer in words at the same place in every card: "Enough · pays ~132", "Too low · from 116". A click opens the card in place: three amounts, the sections in the order Nova tries them with a bid each, other sections to try if full, and a row of actions (*Move up*, *To alternate list*, *Remove* ...). The alternate list ends in a dashed card that adds to it, and never promises a seat.

**Finish on Nova.** "Nothing has been sent." The round of this semester, what is missing, the lists, the calendar file and the plan link.

Decisions taken from other tools, with what we changed:

| Decision | Seen at |
|---|---|
| Choose on the left, see the result on the right | Biddit since 2023 |
| The first screen is the result: an empty week, no tour | NUSMods, Semester.ly |
| A row is two lines and one action; sections one level deeper, in the same column | Semester.ly, Penn Course Plan (we fold them open in the row, the whole course comes with Back) |
| One click adds with a sensible section. See first, correct later | NUSMods, Semester.ly (we also avoid clashes, NUSMods does not) |
| Other sections wait in the week at their real time; one click switches | NUSMods (it does not mark clashes, we do) |
| Your plan in one place beside the list; the list only ticks what is in it | Biddit |
| Each row has one action, the same square: add, or pick where Nova assigned the section; then switch in the row | AfterClass |
| Clash visible before the click, never blocking, two levels | Biddit (orange for classes, red for exams) |
| The empty state is the only instruction | Biddit, Penn Course Plan |
| Three buttons with the amount and one field. No slider | Catawiki, Yahoo, ESPN (Wharton went from a slider to a number) |
| A few numbers in one place, red only when it goes wrong | Yahoo, AfterClass, Kellogg (ours sit on top of the bids) |
| The answer first, the distribution on request | AfterClass (what to avoid), Catawiki |
| Undo instead of "are you sure"; only start over asks | NUSMods |
| Say where planning ends and bidding starts | Biddit, eBay's final review |
| Empty alternate list is a warning, with its own way in | Columbia, Kellogg |
| Phone: one surface at a time, all five days in view | Biddit, Penn Course Plan, NUSMods' vertical mode |

## One language (10 Nov)

Beni chose the two halves and asked for one visual language: obvious what can be clicked, every course on *Bids* clearly on its own. The same job always looks the same, everything clickable looks clickable, nothing else does. Functions, rules and texts stay.

| Rule | Seen at |
|---|---|
| Blue means clickable or selected, nothing else. Orange and red only say how things stand; charts are grey | NUSMods (the accent colour marks what can be clicked), Apple HIG (one colour, one meaning), Nielsen Norman Group (flat UI signifiers) |
| Three buttons, one height and one radius: primary (one per screen, *Finish on Nova*), secondary (white with a border), tertiary (blue words) | Apple HIG (rank by style, not by size; one or two prominent buttons per view) |
| One add control in a fixed column left of every name: plus when out, tick when in, × under the mouse | NUSMods (one button per job, its state shown by its fill) |
| The whole row opens; one 12 px chevron at the right edge, down when closed, up when open, group headings included | Google Flights, Nielsen Norman Group (accordion icons) |
| No lines between items: space and a light surface separate them. On *Bids* every course is a white card | NUSMods (whitespace between entries), Nielsen Norman Group (common region), Google Flights (an open row becomes a card) |
| A bid card has fixed places: rank, name and facts, the field with "pts", the status, the chevron. The budget is one value on top | HSG Biddit, page *Bidding* ("Points available 820/1000"), Monarch Money's budget (name, a bordered field, the state at the end) |
| Status is one component in one place: the verdict first, then the number ("Too low · from 40"); ok, warning, problem, unknown | HSG Biddit, Monarch Money |
| Fields look like fields: selects and inputs white with a border; what is only shown has no frame | Monarch Money, Apple HIG (pop-up buttons, text fields) |
| One link style: blue, underlined in running text, a chevron after a link that stands alone | GOV.UK, Nielsen Norman Group (Beyond Blue Links) |
| One state system: paper under the mouse, a blue border on outlined controls, one focus ring, 38 % when switched off, the pointing hand only where a click does something | Nielsen Norman Group (button states, consistency) |
| Fewer text styles, nothing above 600; named colours, three control heights, two radii | Nielsen Norman Group (consistency) |

Not in this round, Beni decides first: course colours and picking a section by clicking blocks in the week, both as in NUSMods.

**First-time user test (10 Nov).** A fresh agent, playing a Management student on a laptop and an iPhone, lost time where the page moved by itself (a + on the phone jumped to the top and left the sections under the bar; on the laptop the week previewed whatever course slid under the still mouse), where a field added digits instead of replacing them (0 became 1100), and where words read wrong: "Fall · closed" as not selectable, "seats from 109" as a seat count, "held", a red 42 ECTS without a reason.

What changed: the row that opens stays under the finger and comes up above the bar; a preview waits until the mouse moves; a click selects the number in a field; opening a course leaves *Bids* or *Summary* open; the ECTS say "31.5 ECTS · 28 recommended" or "42 ECTS · max 31.5" in the head and in the totals; "Fall · practice", "a seat took 109 to 120", "165 of 165 in bids · 0 left", "Needs a bid, holds no points"; the (?) opens the price rule; a phone shows the figures of your plan above the list; hover only for a real mouse. Measured afterwards: first screen with the example 42 controls and 189 words, a course 26 and 221, *Bids* 49 and 299, the rest unchanged.

## Out of scope

Everything the brief excludes. A wizard or a tour. A slider. Hiding what Nova blocks. A new plan starts in Fall because that is the only semester with a timetable; when Nova publishes spring, the default moves.

## Done when

- `uv run pytest` is green, including all earlier scenarios, unchanged in what they expect.
- `tests/browser/flow.cjs` is green on a laptop, a small laptop, an iPhone and an Android phone.
- The page does not scroll on a laptop (1440 × 900 and 1280 × 720).
- `scripts/measure.cjs` shows, same counter before and after:

| Screen | Before | After | Sections in the row (9 Nov) | Two halves, one language (10 Nov) |
|---|---|---|---|---|
| First screen, empty | 53 controls, 247 words | 38, 139 | 38, 139 | 38, 152 |
| First screen, example plan | 70, 302 | 45, 154 | 41, 178 (each row names its section and time) | 42, 186 |
| A course | 36, 300 (own page) | 24, 190 (week stays) | 27, 210 | 26, 218 |
| Bids, example plan | 47, 240 | 33, 222 | 23, 188 | 49, 291 (the courses stay on the left) |
| Rules | 16, 479 | 13, 105 | 13, 105 | 11, 102 |
| Phone, first screen | 38, 113 | 28, 89 | 28, 89 | 26, 78 |

- First-time users get from nothing to a list they could type into the platform without help, and can then say: are my bids at Nova yet? What do I pay? What is the difference between another section and the alternate list? Played by fresh agents first; three students who have never seen it are still to come. Results in `docs/usability.md`.
