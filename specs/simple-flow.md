# Second team feature: the simple flow

## Why

The first version showed the whole data model on every screen. A student should understand Lance without reading: what do I take, how much do I bid, what do I do now. Measured on the first screen with a plan: 70 controls and 302 words, close to CourseTable's catalogue (71 and 399), the densest screen we looked at. Semester.ly has 24 and 108, NUSMods 35 and 119.

## What

Three steps, one job each: **Courses**, **Bids**, **Finish on Nova**. The rules of the brief stay; five are added (LN R11 to R15). The side navigation, the head card, the filter chips, the section chips in the list, the exam cards and the colour per course are gone.

**Courses.** Choose on the left, see the result on the right. Above the list: programme, semester, `T1 | T2`. The half is one switch for both columns; a search looks through everything. Courses come in groups: My courses (folded, with the ECTS total and all exams), Mandatory, Electives, Other programmes. A click on a row folds it open in place: its sections as tiles with day and time, each saying whether it clashes, and the same sections as ghosts in the week, standing beside what they clash with. One click on a tile or a ghost picks or switches the section. A mandatory row has *Pick* instead of a plus, because Nova assigned the section. An elective row has a plus, which adds it with the first section that fits and folds the row open, so another section is one click away. *Course details* opens the whole course in the same column. Clashes are named under the week with a way out, the worst first.

**Bids.** One row per course with one number, because only the highest is held, and next to it last round's answer in words: "Enough · pays ~132", "Too low · from 116". Two columns, *Your bid* and *Last round*, so the list reads from top to bottom. The points sit in one card beside the list (on a phone above it): held while bidding, left now, and if last round repeats what you pay and what comes back. A click on a course folds it open: three amounts, the sections in the order Nova tries them with a bid each, and other sections to try if full. The alternate list has its own way in and never promises a seat.

**Finish on Nova.** "Nothing has been sent." The round of this semester, what is missing, the lists, the calendar file and the plan link.

Decisions taken from other tools, with what we changed:

| Decision | Seen at |
|---|---|
| Choose on the left, see the result on the right | Biddit since 2023 |
| The first screen is the result: an empty week, no tour | NUSMods, Semester.ly |
| A row is two lines and one action; sections one level deeper, in the same column | Semester.ly, Penn Course Plan (we fold them open in the row, the whole course comes with Back) |
| One click adds with a sensible section. See first, correct later | NUSMods, Semester.ly (we also avoid clashes, NUSMods does not) |
| Other sections wait in the week at their real time; one click switches | NUSMods (it does not mark clashes, we do) |
| Selected courses on top of the same list, no second place | Biddit |
| Each row has one action: add or pick, then switch in the row | AfterClass |
| Clash visible before the click, never blocking, two levels | Biddit (orange for classes, red for exams) |
| The empty state is the only instruction | Biddit, Penn Course Plan |
| Three buttons with the amount and one field. No slider | Catawiki, Yahoo, ESPN (Wharton went from a slider to a number) |
| A few numbers in one place, red only when it goes wrong | Yahoo, AfterClass, Kellogg (ours sit beside the list) |
| The answer first, the distribution on request | AfterClass (what to avoid), Catawiki |
| Undo instead of "are you sure"; only start over asks | NUSMods |
| Say where planning ends and bidding starts | Biddit, eBay's final review |
| Empty alternate list is a warning, with its own way in | Columbia, Kellogg |
| Phone: one surface at a time, all five days in view | Biddit, Penn Course Plan, NUSMods' vertical mode |

## Out of scope

Everything the brief excludes. A wizard or a tour. A slider. Hiding what Nova blocks. A new plan starts in Fall because that is the only semester with a timetable; when Nova publishes spring, the default moves.

## Done when

- `uv run pytest` is green, including all earlier scenarios, unchanged in what they expect.
- `tests/browser/flow.cjs` is green on a laptop, a small laptop, an iPhone and an Android phone.
- The page does not scroll on a laptop (1440 × 900 and 1280 × 720).
- `scripts/measure.cjs` shows, same counter before and after:

| Screen | Before | After | Sections in the row (9 Nov) |
|---|---|---|---|
| First screen, empty | 53 controls, 247 words | 38, 139 | 38, 139 |
| First screen, example plan | 70, 302 | 45, 154 | 41, 178 (each row names its section and time) |
| A course | 36, 300 (own page) | 24, 190 (week stays) | 27, 210 |
| Bids, example plan | 47, 240 | 33, 222 | 23, 188 |
| Rules | 16, 479 | 13, 105 | 13, 105 |
| Phone, first screen | 38, 113 | 28, 89 | 28, 89 |

- First-time users get from nothing to a list they could type into the platform without help, and can then say: are my bids at Nova yet? What do I pay? What is the difference between another section and the alternate list? Played by fresh agents first; three students who have never seen it are still to come. Results in `docs/usability.md`.
