# Lance: business requirements

Version 0.2, 7 November 2026. Written in the format of the course's product briefs.

## The opportunity

Nova's course bidding is less complicated than it is opaque. To decide, a student needs four systems and still gets no answer to two questions: *how many points does a seat cost?* and *is the course any good?* The platform does not check class clashes or midterms. St. Gallen shows that a tool built by students can close this gap: Biddit reached almost half of all students in its second semester. Biddit does not collect past prices. That is where Lance goes further.

## First release

One semester with its real timetable (Fall 2026/27) and the catalogue of the next one (Spring 2026/27, timetable not published yet). No login, no connection to Nova's systems: everything works from published documents and from what students choose to share.

## The user journey

Three steps. **Courses:** a student chooses their programme, says which sections Nova assigned them, and presses plus on electives; the week fills up, and anything that would clash says so before the click. **Bids:** they enter their points and one bid per course, next to an answer in words: was that enough last round, and what would it cost? **Finish on Nova:** nothing has been sent; they take the list to Nova's platform and the classes to their calendar. After the round they share their rank lists, so that the next students know the prices.

## Required capabilities

| Id | Capability | Behaviour |
|---|---|---|
| LN01 | Find a course | Search by name, code or lecturer, through all terms. The list shows the half of the semester on show, in groups by how the course counts for the programme. |
| LN02 | Build the week | Add and remove courses, switch sections. One week per half semester. |
| LN03 | See clashes first | Each section shows what it would clash with before it is added. An open course shows its sections in the week; resting on a row previews them. |
| LN04 | Plan the points | One bid per course, a separate bid per section on request. Other sections of the course in order. Show what is left, what a repeat of last round would charge, and what stays after it. |
| LN05 | Read past prices | Cut-off, seats, number of bids and the distribution of bids per section. |
| LN06 | Course sheet | Lecturers, sections, exams, past prices, what counts for the grade, Nova's own sheet, similar courses. |
| LN07 | Rate a course | Fixed questions only. Results appear in aggregate. |
| LN08 | Share rank lists | A bookmarklet reads the student's own rank lists on the platform, without the personal columns. Pasted into Lance, they become totals per section. |
| LN09 | Rules and dates | The rules as short questions, Nova's wording one click deeper, the calendar. The last step says what is missing and has a checklist. |
| LN10 | Take it along | A calendar file with every class on its real date; the list to type into the platform. |
| LN11 | Come back | The plan is saved without an account. A private link continues it on another device. |

## Business rules

| Id | Rule | Source |
|---|---|---|
| LN R1 | Two classes clash when they meet on the same date and each starts before the other ends. Touching is fine. Two sections of one course never clash. | Festival Architect FA R2, applied date by date |
| LN R2 | Overlapping exams are reported as blocked by the platform. A midterm overlapping an exam, a midterm or a class is reported as not checked by the platform. | Bidding Rules; Bidding Overview |
| LN R3 | Primary list price: (bid + lowest winning bid in the course) / 2. | Bidding Rules; the "whole course" reading is checked on two accounts |
| LN R4 | Alternate list price: the smaller of the bid and the remaining balance. | Bidding Rules |
| LN R5 | Add/drop price: the full bid. | Bidding Rules |
| LN R6 | While bidding, the primary list takes the highest bid of each course once. The alternate list takes nothing. | Bidding Rules; account log of one real account |
| LN R7 | Rank value: bid × 1.1 for students who tick the rank bonus, otherwise the bid. Who gets it is not published. | Rank lists; not in Nova's rules |
| LN R8 | At most 31.5 ECTS in mandatory and elective courses; 28 recommended. A course counts once. The alternate list does not count. | Bidding Rules |
| LN R9 | Privacy: student numbers and other students' ECTS are never read, sent or stored. A rank list with such a column is refused whole. Only totals per section are kept. Ratings show from 3 answers, grades from 10. No free text about lecturers. | Team decision; CNPD guideline 1/2018 |
| LN R10 | An empty bid means not interested; 0 is a bid. A bid is a whole number from 0 to the balance. A refused bid leaves the saved bid unchanged. | Bidding Rules |
| LN R11 | Adding an elective without naming a section takes its first section that clashes with nothing in the week, otherwise its first. A course without a timetable stays without a section. A mandatory course is refused: Nova assigned the section, so the student names it. | Team decision |
| LN R12 | Switching gives another section the first place, with its bid, list and position. If it was a backup, the two change places and the bids stay with the places: TXB 164, TXA 100 becomes TXA 164, TXB 100. | Team decision |
| LN R13 | The week is the first section of each course on the mandatory and primary lists. Only the week counts for clashes, for "fits my week" and for LN R11. A backup is checked against the week, an alternate against the mandatory and primary lists, each in its own row. An alternate whose exam meets the week says that Nova will not enroll you in both. | Bidding Rules; team decision |
| LN R14 | A further section of a course starts with the bid of the first. Only the highest is held anyway (LN R6). | Team decision |
| LN R15 | Removing a course removes all its sections and can be undone, including bids and place. Start over empties the plan and keeps the settings. | Team decision |

## What the product must remember

Content: courses, sections, weekly meetings, every class with its date, exams, the academic calendar, course sheets. Progress: each plan (programme, semester, points, bonus, entries, lists, order, bids), ratings, past prices as totals. Accepted changes survive a restart. Rebuilding the content leaves progress untouched.

## Acceptance scenarios

| Id | Scenario | Test file |
|---|---|---|
| A1 | **Two real accounts.** 165 points, Programming 164, Impact Investments 1: seat in Programming TXB for 132, no seat in Impact Investments, 33 left. 218 points, Programming 130, Impact Investments 88: charged 115 and 64, 39 left. | `test_real_accounts.py` |
| A2 | **Clashes.** Advanced Strategy TXC and Econometrics TXA clash. Two sections of one course do not. T1 and T2 at the same hour do not. An S1 course against a T2 course clashes on 6 of its 12 dates. | `test_clashes.py` |
| A3 | **Exams.** Two T2 exams in one slot are reported as blocked. A midterm during a class is reported as not checked. | `test_clashes.py` |
| A4 | **The data is right.** Programming TXB: 12 classes, B.0.04, make-up on Fri 4 Dec. No class on a holiday. Exam dates match the platform. | `test_data.py` |
| A5 | **Restart.** A plan with a bid survives a restart. A refused bid is explained and changes nothing. One visitor cannot touch another's plan. | `test_app.py` |
| A6 | **Take it along.** The calendar file has every class on its real date. The list keeps the order. | `test_app.py` |
| A7 | **Ratings.** Hidden below 3, grades hidden below 10, one answer per visitor, no free text. | `test_app.py` |
| A8 | **Shared data.** A list becomes totals. A personal column refuses the whole list. A shorter list never replaces a longer one. | `test_app.py` |
| A9 | **The simple flow.** Plus takes the first section that fits. A switch keeps the bid. The real plan has no clash in its week. A backup and an alternate report in their own row. Remove and undo restore bids and place. One bid goes to all sections of a course. | `test_simple_flow.py`, `tests/browser/flow.cjs` |

## Scope boundaries

Not in this release: placing bids on Nova's platform, logging in to Nova's systems for anyone, automatic data collection from another person's account, modules, a recommendation of which courses to take, an optimiser. Lance never asks for Nova credentials.

## Open questions

Does a new product count as extending a project? (Ask Ricardo Pereira.) Who gets the rank bonus? What do the terms of use of Nova's systems allow? Spring round and timetable dates may change: the calendar says so itself.
