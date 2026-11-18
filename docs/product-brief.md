# Lance: business requirements

Version 0.3, 17 November 2026. Written in the format of the course's product briefs.

## The opportunity

Nova's course bidding is less complicated than it is opaque. To decide, a student needs four systems and still gets no answer to two questions: *how many points does a seat cost?* and *is the course any good?* The platform does not check class clashes or midterms. St. Gallen shows that a tool built by students can close this gap: Biddit reached almost half of all students in its second semester. Biddit does not collect past prices. That is where Lance goes further.

## First release

One semester with its real timetable (Fall 2026/27) and the catalogue of the next one (Spring 2026/27, timetable not published yet). No login, no connection to Nova's systems: everything works from published documents, from the public course ratings on Uni Feedback and from what students choose to share.

## The user journey

Three steps. **Courses:** a student chooses their programme, says which sections Nova assigned them, and presses plus on electives; the week fills up, and anything that would clash says so before the click. Each course shows what students say about it. **Bids:** their points are estimated from their mandatory courses until they type the real balance; they enter one bid per course, next to an answer in words: was that enough last round, and what would it cost? **Finish on Nova:** nothing has been sent; they take the list to Nova's platform and the classes to their calendar. After the round they share their rank lists, so that the next students know the prices.

## Required capabilities

| Id | Capability | Behaviour |
|---|---|---|
| LN01 | Find a course | Search by name, code or lecturer, through all terms. The list shows the half of the semester on show, in groups by how the course counts for the programme. |
| LN02 | Build the week | Add and remove courses, switch sections, up to 40 entries in a semester. One week per half semester. |
| LN03 | See clashes first | Each section shows what it would clash with before it is added. An open course shows its sections in the week; resting on a row previews them. |
| LN04 | Plan the points | One bid per course, a separate bid per section on request. Other sections of the course in order. Show what is left, what a repeat of last round would charge, and what stays after it. |
| LN05 | Read past prices | Cut-off, seats, number of bids and the distribution of bids per section. |
| LN06 | Course sheet | Lecturers, sections, exams, past prices, the rating, what counts for the grade, Nova's own sheet, similar courses. |
| LN07 | See a course's rating | The average rating, the number of reviews and the workload from Uni Feedback, an independent review site, in the list and on the course sheet, with a link to the reviews. Lance collects no ratings itself: nobody wants to rate while they bid. |
| LN08 | Share rank lists | A bookmarklet reads the student's own rank lists on the platform, without the personal columns. Pasted into Lance, they become totals per section. A video of 40 seconds on the share page shows the five steps, with captions. |
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
| LN R9 | Privacy: student numbers and other students' ECTS are never read, sent or stored. A rank list with such a column is refused whole. Only totals per section are kept. No free text about lecturers. | Team decision; CNPD guideline 1/2018 |
| LN R10 | An empty bid means not interested; 0 is a bid. A bid is a whole number from 0 to the balance. A refused bid leaves the saved bid unchanged. | Bidding Rules |
| LN R11 | Adding an elective without naming a section takes its first section that clashes with nothing in the week, otherwise its first. A course without a timetable stays without a section. A mandatory course is refused: Nova assigned the section, so the student names it. | Team decision |
| LN R12 | Switching gives another section the first place, with its bid, list and position. If it was a backup, the two change places and the bids stay with the places: TXB 164, TXA 100 becomes TXA 164, TXB 100. | Team decision |
| LN R13 | The week is the first section of each course on the mandatory and primary lists. Only the week counts for clashes, for "fits my week" and for LN R11. A backup is checked against the week, an alternate against the mandatory and primary lists, each in its own row. An alternate whose exam meets the week says that Nova will not enroll you in both. | Bidding Rules; team decision |
| LN R14 | A further section of a course starts with the bid of the first. Only the highest is held anyway (LN R6). | Team decision |
| LN R15 | Removing a course removes all its sections and can be undone, including bids and place. Reset empties the semester on show, keeps the settings and can be undone the same way. A course can be removed in the list, on its sheet, in its bid card and in its row of the summary. | Team decision; advisor's feedback, 17 Nov 2026 |
| LN R16 | Two exams of different courses in the week on one date, one after the other, are not a clash (the platform allows it) but a hard day: Lance says so in the list before adding, under the week and in the Summary. It is not counted as a clash. Midterms and presentations do not count. | Team decision |
| LN R17 | Points the student has not typed are an estimate from the mandatory courses in the plan: a straight line through 140 points at 20 ECTS and 120 points at 23 ECTS, never below 0, a course counted once. Without mandatory courses there is no estimate. Typed points always win; an empty field brings the estimate back. The estimate is never saved as if it had been typed. | Team decision, 17 Nov 2026: rough values from our own accounts. Nova does not publish the rule |
| LN R18 | A shared rank list counts only if it could be real. It names a section of Lance's catalogue (a course without a timetable takes the section names Nova uses) and a round that is over: the calendar's rounds once they have closed, and the two rounds of the year before. Each row holds only final, bid and allocated. Bids are whole numbers from 0 to 5000, rank values run from 0 to 5500, seats are whole numbers from 1 to 400 (0 on an alternate list with no seat left). A list has at most 1000 rows, a share at most 60 lists. Anything else refuses the whole share. A list read from our own account (`seed/`) is never replaced by a shared one. Prices are read from the newest round of each course. | Team decision, 18 Nov 2026, after the security review |
| LN R19 | The left arrow in the top bar takes back the last change to the semester on show, the right arrow does it again. A change is one action on its courses, sections, lists, order or bids: adding, removing a section or a course, the Undo after a removal, switching a section, a bid on a section or a course, moving within or between lists, Reset, loading the example. Programme, semester, typed points and the bonus are settings, not changes: the arrows leave them as they are, and a course that comes back takes the list its programme gives it. The server keeps the last 50 changes of each semester of a plan, so they survive a reload. A new change drops what could be done again. A step never touches the other semester or another plan. With nothing to take back the arrow is switched off; asked anyway, the answer says there is nothing to undo. | Team decision, 18 Nov 2026 |

## What the product must remember

Content: courses, sections, weekly meetings, every class with its date, exams, the academic calendar, course sheets, course ratings. Progress: each plan (programme, semester, typed points, bonus, entries, lists, order, bids, and the last 50 changes of each semester for undo and redo), past prices as totals. Accepted changes survive a restart. Rebuilding the content leaves progress untouched.

## Acceptance scenarios

| Id | Scenario | Test file |
|---|---|---|
| A1 | **Two real accounts.** 165 points, Programming 164, Impact Investments 1: seat in Programming TXB for 132, no seat in Impact Investments, 33 left. 218 points, Programming 130, Impact Investments 88: charged 115 and 64, 39 left. | `test_real_accounts.py` |
| A2 | **Clashes.** Advanced Strategy TXC and Econometrics TXA clash. Two sections of one course do not. T1 and T2 at the same hour do not. An S1 course against a T2 course clashes on 6 of its 12 dates. | `test_clashes.py` |
| A3 | **Exams.** Two T2 exams in one slot are reported as blocked. A midterm during a class is reported as not checked. Two exams on one day, one after the other, are reported as a hard day and not as a clash. | `test_clashes.py` |
| A4 | **The data is right.** Programming TXB: 12 classes, B.0.04, make-up on Fri 4 Dec. No class on a holiday. Exam dates match the platform. | `test_data.py` |
| A5 | **Restart.** A plan with a bid survives a restart. A refused bid is explained and changes nothing. One visitor cannot touch another's plan. | `test_app.py` |
| A6 | **Take it along.** The calendar file has every class on its real date. The list keeps the order. | `test_app.py` |
| A7 | **Ratings.** Introduction to Programming shows 4.6 of 5 from 18 reviews, workload Light, with a link to its reviews. A course nobody reviewed says so. There is no form to rate. | `test_ratings.py` |
| A8 | **Shared data.** A list becomes totals. A personal column refuses the whole list. A shorter list never replaces a longer one. | `test_app.py` |
| A10 | **Estimated points.** Management, nothing typed: Advanced Strategy alone gives 227 points, the four mandatory courses of the example (21 ECTS) give 133. Typing 165 replaces the estimate, an empty field brings it back. Reset and undo bring back a bid of 100 together with the course that gives the points for it. | `test_points.py` |
| A11 | **The spring's mandatory courses.** Business Analytics: Machine Learning, Data Ecosystems and Governance in Organizations, Digital Experimentation & Causal Analysis in T3. Public Policy: three in T3. Economics: Microeconometrics or Macroeconometrics. Management and Finance: their mandatory courses offered again. Without a timetable such a course is added without a section and counts for the estimated points. The fall keeps its 137 courses and 245 sections. | `test_spring_mandatory.py` |
| A12 | **Shared lists that count.** A list for Programming TXZ, for the year 1999/2000, with a bid of Infinity or with a column Ects Sum is refused whole. A list of 299 bids for Programming TXB does not replace our own list of 298: 164 still pays 132 and 33 stay (A1). A list for 2025/2026 is kept, but the price stays the one of Fall 2026. | `test_shared_lists.py` |
| A9 | **The simple flow.** Plus takes the first section that fits. A switch keeps the bid. The real plan has no clash in its week. A backup and an alternate report in their own row. Remove and undo restore bids and place. One bid goes to all sections of a course. | `test_simple_flow.py`, `tests/browser/flow.cjs` |
| A13 | **Undo and redo.** Add Introduction to Programming, then the left arrow: it is gone from the list and the week; the right arrow: it is back in TXA. Undo also takes back a switch to TXC, a bid of 120, a move to the alternate list, a removal and its Undo, Reset (every course and bid comes back) and the example (the plan is empty again, the programme stays). After a course and 60 bids on it, 50 steps go back, to the bid of 10, and no more. A new change leaves nothing to redo. Undo in Fall leaves Spring and other plans alone. With nothing to undo, the answer says so. | `test_undo.py`, `tests/browser/flow.cjs` |

## Scope boundaries

Not in this release: accounts, reading a student's mandatory courses or points from Nova (they click them, three clicks), collecting ratings, placing bids on Nova's platform, logging in to Nova's systems for anyone, automatic data collection from another person's account, modules, a recommendation of which courses to take, an optimiser. Lance never asks for Nova credentials.

## Open questions

Does a new product count as extending a project? (Ask Ricardo Pereira.) How does Nova set the points? LN R17 is an estimate: one real account had 165 points with 21 mandatory ECTS, the estimate says 133. May the ratings stay in a public repository? Ask Uni Feedback before the repository is made public. Which courses of other programmes may a student really take? When is Empirical Methods for Finance taught, and which code has Social Entrepreneurship (both mandatory, both missing: `docs/data.md`)? Who gets the rank bonus? What do the terms of use of Nova's systems allow? Spring round and timetable dates may change: the calendar says so itself.
