# Lance: business requirements

Version 0.1, 7 November 2026. Written in the format of the course's product briefs.

## The opportunity

Nova's course bidding is less complicated than it is opaque. To decide, a student needs four systems and still gets no answer to two questions: *how many points does a seat cost?* and *is the course any good?* The platform does not check class clashes or midterms. St. Gallen shows that a tool built by students can close this gap: Biddit reached almost half of all students in its second semester. Biddit does not collect past prices. That is where Lance goes further.

## First release

One semester with its real timetable (Fall 2026/27) and the catalogue of the next one (Spring 2026/27, timetable not published yet). No login, no connection to Nova's systems: everything works from published documents and from what students choose to share.

## The user journey

A student chooses their programme and enters their points. They search the courses, see each section's times, and see before adding it what it would clash with. They build their week, then move to the bids: last round's cut-off, a suggested bid, what the bid would cost. They take the list to Nova's platform and the classes to their calendar. After the round they share their rank lists, so that the next students know the prices.

## Required capabilities

| Id | Capability | Behaviour |
|---|---|---|
| LN01 | Find a course | Search by name, code or lecturer. Filter by term and by how the course counts for the programme. |
| LN02 | Build the week | Add and remove sections. One week per half semester. Several sections of a course can be listed, the first counts as first choice. |
| LN03 | See clashes first | Each section shows what it would clash with before it is added, and a preview in the week on hover. |
| LN04 | Plan the points | A bid per section. Show what bidding takes, what a repeat of last round would charge, and what is left. |
| LN05 | Read past prices | Cut-off, seats, number of bids and the distribution of bids per section. |
| LN06 | Course sheet | Lecturers, sections, exams, past prices, what counts for the grade, Nova's own sheet, similar courses. |
| LN07 | Rate a course | Fixed questions only. Results appear in aggregate. |
| LN08 | Share rank lists | A bookmarklet reads the student's own rank lists on the platform, without the personal columns. Pasted into Lance, they become totals per section. |
| LN09 | Rules and dates | The rules in plain language next to Nova's wording, the calendar, a checklist. |
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

## Scope boundaries

Not in this release: placing bids on Nova's platform, logging in to Nova's systems for anyone, automatic data collection from another person's account, modules, a recommendation of which courses to take, an optimiser. Lance never asks for Nova credentials.

## Open questions

Does a new product count as extending a project? (Ask Ricardo Pereira.) Who gets the rank bonus? What do the terms of use of Nova's systems allow? Spring round and timetable dates may change: the calendar says so itself.
