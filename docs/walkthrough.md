# Follow the click

Each member is asked about code they did not write. Six clicks, from the button to the database. Pick any two and explain them without notes, then say what a refused bid does.

| Click | In the browser | Address in `app.py` | Rule in `logic.py` | Storage in `db.py` | Test | Rule |
|---|---|---|---|---|---|---|
| The plus at the right of an elective | `addCourse` in `static/planner.js` | `api_add` | `add_to_plan`, `first_fitting_section` | `insert_item` | `test_adding_a_course_skips_a_section_that_clashes_with_the_week` | LN R11 |
| Switch a section | `chooseSection` in `static/planner.js` | `api_switch` | `switch_section` | `update_item` | `test_switching_keeps_the_bid_the_list_and_the_position` | LN R12 |
| Remove and undo | `removeCourse` in `static/planner.js` | `api_remove`, `api_restore` | `remove_course`, `restore_items` | `delete_item`, `insert_item` | `test_removing_a_course_can_be_undone_with_its_bids_and_its_place` | LN R15 |
| A bid in a course's card | `saveLater` in `static/bids.js` | `api_bid` | `set_course_bid`, `checked_bid` | `update_item` | `test_a_refused_course_bid_changes_nothing` | LN R6, R10 |
| Rate a course | form in `templates/_sheet.html` | `rate` | `validate_rating` | `save_rating` | `test_an_incomplete_rating_is_refused` | LN R9 |
| Share a rank list | `static/share.js` | `api_share` | `share_rank_lists`, `read_rank_list` | `save_price_data` | `test_rows_with_personal_columns_are_refused_whole` | LN R9 |

What answers a click: every change returns the whole state (`answer` in `app.py`, `state_of` in `logic.py`), and `Lance.update` in `static/common.js` redraws from it. The page never works anything out for itself.

Who draws what: `/` and `/bids` are one screen (`templates/bids.html` extends `planner.html`). `static/planner.js` draws the courses on the left and the tabs *Week* and *Summary* on the right; `static/bids.js` draws the tab *Bids*, one card per course, and keeps its names inside `Bids` because it shares the page. Both listen to `Lance.onChange`.

How a course keeps its colour: `Lance.colourOf` in `static/common.js`, one function that the list, the week, *Bids* and *Summary* all call. It lines up the courses of the plan in the order they came in (the item id). Each prefers the colour its id points to, a number made from its letters; if an earlier course has that colour already, it steps aside to the next free one. So adding a course never recolours another, and removing one can only recolour a later course that had stepped aside. Nothing is stored: the colour follows from the plan every time it is drawn, and a course not yet in the plan gets the colour it would get if added now (that is the colour of its ghosts in the week). The colours themselves are tokens in `static/app.css` (`--olive`, `--olive-soft`, `--olive-line` ...); `Lance.dot` draws the dot before a name.

How the week knows what to draw: `week_items` in `logic.py` (LN R13) decides what is in the week, `renderWeek` in `static/planner.js` turns that into blocks, `Week.draw` in `static/week.js` puts them on the grid. Ghosts are laid out together with the real blocks, the real ones on the left, so that a ghost never hides the course it clashes with.

What the address does: `location.hash` holds the open course or the tab of your plan (`#week`, `#bids`, `#summary`), `route` in `static/planner.js` reads it. Back, Esc and the back button all go through there; on a phone the address also says which half is on screen.
