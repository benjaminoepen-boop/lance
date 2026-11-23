/* One screen, two halves: find courses on the left, your plan on the right (Week, Bids, Summary).
   Every rule lives on the server; this file only draws what logic.py answered and sends what was clicked.
   bids.js draws the Bids tab; this file draws everything else of the screen. */
const { el } = Lance;

const view = {
  catalogue: [],
  half: null,          /* which half of the semester both columns show */
  query: "",
  fits: false,
  closed: { outside: true },   /* list groups that are folded */
  tab: "week",         /* what the right half shows: week, bids or summary */
  open: null,          /* the course open in the left column with all its details */
  expanded: null,      /* the course folded open in the list, to pick a section right there */
  unfolding: null,     /* the course whose row a click has just folded open: it glides open once, then stands still */
  preview: null,       /* the course under the mouse in the list */
  hot: null,           /* the section under the mouse */
  fresh: null,         /* the section that was just added: it pops in */
  backTo: "",          /* where the Back button of an open course leads: the list, or a tab of your plan on a phone */
  allClashes: false,
  alternates: false,   /* the alternate list is being filled: a plus puts a course there, and the week shows that list too */
  pausedUntil: 0,      /* a double click must not hit the row that has just moved under the mouse */
};
const HALVES = {
  Fall: [["T1", "T1: until 12 Oct"], ["T2", "T2: from 22 Oct"]],
  Spring: [["T3", "T3: from 1 Feb"], ["T4", "T4: from 5 Apr"]],
};
const TERMS_OF = { T1: ["S1", "T1"], T2: ["S1", "T2"], T3: ["S2", "T3"], T4: ["S2", "T4"] };
const TABS = ["week", "bids", "summary"];
const canHover = window.matchMedia("(hover: hover)").matches;
const onPhone = () => window.matchMedia("(max-width: 860px)").matches;   /* one half at a time */
const hasWeek = (state) => state.plan.semester === "Fall";   /* Nova has not published the spring timetable yet */
const courseById = (id) => view.catalogue.find((course) => course.id === id);
const entriesOf = (state, offeringId) => state.items.filter((item) => item.offering_id === offeringId).sort((a, b) => a.position - b.position);
const compact = (time) => time.replace(/^0/, "");
const meetingsText = (meetings) => meetings.map((m) => `${m.day} ${compact(m.start)}`).join(" · ");

/* ---- doing things ---- */

function tooSoon() {
  if (Date.now() < view.pausedUntil) return true;
  view.pausedUntil = Date.now() + 400;
  return false;
}

/* while the alternate list is filled, a new course goes there instead of the primary list. A mandatory course never does:
   Nova assigned its section, so it keeps its Pick and its own list. What an alternate may clash with stays the server's rule (LN R13) */
const listFor = (course) => (view.alternates && course.kind !== "mandatory" ? { list: "alternate" } : {});

async function addCourse(course) {
  bringForward(course);
  const where = listFor(course);
  const answer = await Lance.send("/api/add", { offering_id: course.id, ...where });
  if (answer.error) return;
  const entry = entriesOf(Lance.state, course.id)[0];
  view.fresh = entry.section_id;
  if (course.sections.length > 1) {
    if (view.expanded !== course.id) view.unfolding = course.id;
    view.expanded = course.id;
    renderKeeping(course.id);
  } else {
    render(Lance.state);
  }
  Lance.toast(`Added ${course.name}${course.sections.length > 1 ? ` ${entry.section}` : ""}${where.list ? " to your alternate list" : ""}`);
}

async function removeCourse(offeringId, name) {
  const answer = await Lance.send("/api/remove", { offering_id: offeringId });
  if (answer.error) return;
  Lance.toast(`Removed ${name}`, { label: "Undo", run: () => Lance.send("/api/restore", { rows: answer.removed }) });
}

/* LN R15: everything out at once, so that nobody has to look for each course again. Undo puts it all back */
async function resetPlan() {
  const answer = await Lance.send("/api/start-over", {});
  if (answer.error || !answer.removed || !answer.removed.length) return;
  const courses = new Set(answer.removed.map((row) => row.offering_id)).size;
  Lance.toast(`Removed ${courses === 1 ? "1 course" : `all ${courses} courses`}`, { label: "Undo", run: () => Lance.send("/api/restore", { rows: answer.removed }) });
}

async function chooseSection(course, section) {
  view.hot = null;
  bringForward(course);
  view.fresh = section.id;
  if (entriesOf(Lance.state, course.id).length) await Lance.send("/api/switch", { section_id: section.id });
  else await Lance.send("/api/add", { section_id: section.id, ...listFor(course) });
}

/* the section under the mouse lights up in the list and in the week at once, without drawing anything again */
function markHot(sectionId) {
  view.hot = sectionId;
  document.querySelectorAll("[data-section]").forEach((node) => node.classList.toggle("hot", node.dataset.section === sectionId));
}

function toggleExpanded(course) {
  /* a click beats the mouse: the week shows the row just opened, not the one hovered a moment ago.
     The right half stays where it is: on Bids or Summary it stays there, on Week the sections wait there as ghosts */
  clearTimeout(previewTimer);
  view.preview = null;
  view.expanded = view.expanded === course.id ? null : course.id;
  view.unfolding = view.expanded;
  if (view.expanded) bringForward(course);
  renderKeeping(course.id);
}

/* a row that folds open or shut stays where it was under the finger or the mouse, even when another row above it folds shut.
   Then it shows all of itself: above the bar at the bottom on a phone, inside the list on a laptop.
   Only as far as needed, and never so far that its head leaves the top */
function renderKeeping(courseId) {
  const rowOf = () => {
    const main = document.querySelector(`#courses [data-key="main-${courseId}"]`);
    return main ? main.closest(".course") : null;
  };
  const old = rowOf();
  const before = old ? old.getBoundingClientRect().top : null;
  holdPreviews();
  render(Lance.state);
  const row = rowOf();
  if (!row || before === null) return;
  const phone = onPhone();
  const scroller = phone ? document.scrollingElement : document.getElementById("courses");
  scroller.scrollTop += row.getBoundingClientRect().top - before;
  if (!row.classList.contains("open")) return;
  const [top, bottom] = visibleArea(phone);
  const box = row.getBoundingClientRect();
  const move = Math.min(box.bottom - bottom, box.top - top);
  if (move > 0) scroller.scrollBy({ top: move, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
}

/* the part of the list that can be seen: on a phone between the bars at the top and the bar at the bottom */
function visibleArea(phone) {
  if (!phone) {
    const list = document.getElementById("courses").getBoundingClientRect();
    return [list.top + 4, list.bottom - 12];
  }
  /* what stays in sight under the top bar: the figures of your plan, or in their place the band of the alternate list */
  const stuck = document.getElementById(view.alternates ? "alternate-banner" : "list-figures");
  const top = document.querySelector(".topbar").getBoundingClientRect().bottom + (stuck.hidden ? 0 : stuck.offsetHeight);
  return [top + 8, document.querySelector(".tabbar").getBoundingClientRect().top - 8];
}

/* after a row opens or shuts, the list moves under a mouse that stood still. Until the mouse really moves,
   a row or a section it lands on is not shown in the week: only the one that was clicked */
const pointer = { x: -1, y: -1, still: null };
function holdPreviews() {
  if (canHover) pointer.still = { x: pointer.x, y: pointer.y };
}
document.addEventListener("mousemove", (event) => {
  pointer.x = event.clientX;
  pointer.y = event.clientY;
  if (!pointer.still || Math.abs(event.clientX - pointer.still.x) + Math.abs(event.clientY - pointer.still.y) < 3) return;
  pointer.still = null;
  /* it moved: what is under it now counts, as if the mouse had just come in */
  const target = event.target instanceof Element ? event.target : null;
  const row = target && target.closest("#courses .course[data-row]");
  if (row) previewCourse(row.dataset.row);
  const tile = target && target.closest(".tile[data-section]");
  if (tile) markHot(tile.dataset.section);
}, { passive: true });

/* the week of a T1 or T2 course comes forward; an S1 course is in both */
function bringForward(course) {
  if (hasWeek(Lance.state) && TERMS_OF[course.term]) view.half = course.term;
}

/* ---- the address: nothing is the list, #week, #bids or #summary a tab of your plan, anything else a course.
   On a laptop both halves are always there; on a phone the address also says which half is on screen. ---- */

function go(target) {
  location.hash = target;
}

function goBack() {
  /* a tab chosen while the course was open stays chosen */
  location.hash = TABS.includes(view.backTo) ? view.tab : view.backTo;
}

/* a tab of the right half: on a laptop a click, on a phone the bar at the bottom */
function setTab(key) {
  view.tab = key;
  const target = decodeURIComponent(location.hash.slice(1));
  if (TABS.includes(target) && target !== key) {
    try { history.replaceState(null, "", `#${key}`); } catch (error) { /* a sandboxed preview keeps its address */ }
  }
  showTab();
}

function showTab() {
  const planner = document.getElementById("planner");
  /* filling the alternate list ends where it began: with the Bids tab on show again, however one got there */
  if (view.alternates && view.tab === "bids") { view.alternates = false; render(Lance.state); }
  planner.dataset.view = view.tab;
  document.querySelectorAll("#plan-tabs [role=tab]").forEach((tab) => {
    const on = tab.dataset.view === view.tab;
    tab.setAttribute("aria-selected", on ? "true" : "false");
    tab.tabIndex = on ? 0 : -1;
  });
  const shown = planner.dataset.zone === "courses" ? "courses" : view.tab === "bids" ? "bids" : "week";
  document.querySelectorAll(".tabbar [data-tab]").forEach((link) => link.classList.toggle("on", link.dataset.tab === shown));
}

function route() {
  const target = decodeURIComponent(location.hash.slice(1));
  const planner = document.getElementById("planner");
  const tab = TABS.includes(target) ? target : null;
  const opening = target && !tab ? target : null;
  if (opening && !view.open) view.backTo = planner.dataset.zone === "plan" ? view.tab : "";
  if (tab) view.tab = tab;
  planner.dataset.zone = tab ? "plan" : "courses";
  showTab();
  if (opening === view.open) return;
  view.open = opening;
  view.preview = null;
  showOpenCourse();
}

async function showOpenCourse() {
  const list = document.getElementById("list-view");
  const box = document.getElementById("course-view");
  list.hidden = Boolean(view.open);
  box.hidden = !view.open;
  if (!view.open) { renderWeek(Lance.state); return; }
  const wanted = view.open;
  const course = courseById(wanted);
  if (course) bringForward(course);
  render(Lance.state);
  /* the last course goes at once: its links must not be clickable while the next one loads */
  box.replaceChildren(el("button", {
    type: "button", class: "btn tertiary flush back", html: `${Lance.icons.back} Courses`, onclick: goBack,
  }));
  const response = await fetch(`/api/sheet/${encodeURIComponent(wanted)}`);
  if (view.open !== wanted) return;
  box.append(el("div", { style: "display:contents", html: response.ok ? await response.text() : '<p class="muted">This course does not exist.</p>' }));
  box.scrollTop = 0;
  renderSections(Lance.state);
}

/* ---- filling the alternate list in the week: "Add alternate course" in the Bids tab starts it (bids.js), Done or Esc ends it.
   The list on the left works as always, but a plus puts the course on the alternate list; the week on the right shows
   the mandatory courses as always, the primary ones stepped back, and the alternates in full. A phone shows one half
   at a time: there it starts on the list, and the week is one tap away in the bar at the bottom. ---- */

/* Nova has not published the spring timetable yet: without a week, the Bids tab keeps its search for the alternate list */
const canFillAlternatesInWeek = () => hasWeek(Lance.state);

/* the list or Bids as the surface on show, where the address says which one it is (see route).
   Shown at once; the browser's own "the address changed" then finds nothing left to do */
function showAddress(target) {
  if (decodeURIComponent(location.hash.slice(1)) !== target) location.hash = target;
  route();
}

function startAlternates() {
  view.alternates = true;
  view.tab = "week";
  /* the list on the left: a phone shows one half at a time, so it goes to the list; on a laptop only a course open there gives way.
     Then the week on the right, like a click on its tab */
  if (onPhone() || view.open) showAddress("");
  setTab("week");
  render(Lance.state);
  /* the band and the search are at the top of the list: a page that was scrolled (a phone, a low window) goes there.
     With a keyboard at hand the cursor waits in the search, as it did in the search this replaces;
     on a phone that would only bring up the keyboard over the list */
  window.scrollTo(0, 0);
  if (!onPhone()) document.getElementById("search").focus({ preventScroll: true });
}

function stopAlternates() {
  if (!view.alternates) return;
  view.alternates = false;
  /* on a laptop a course open on the left may stay open; a phone shows one half, so there the address leads to Bids */
  if (onPhone()) showAddress("bids"); else setTab("bids");
  render(Lance.state);
  /* back in Bids, the list that was just filled is what to look at: a phone scrolls to it,
     and the cursor is back on the card it started from */
  const filled = document.querySelector('#bid-lists [aria-label="Alternate list"]');
  if (!filled) return;
  if (onPhone()) filled.scrollIntoView({ block: "start" });
  const card = filled.querySelector(".add-card");
  if (card) card.focus({ preventScroll: true });
}

/* ---- the list ---- */

function matches(course, state) {
  if (view.query) {
    /* a search looks through everything, so that it never hides a course because of the half on show */
    const haystack = `${course.name} ${course.code} ${course.lecturers}`.toLowerCase();
    if (!view.query.toLowerCase().split(/\s+/).every((word) => haystack.includes(word))) return false;
  } else if (TERMS_OF[view.half] && !TERMS_OF[view.half].includes(course.term)) {
    return false;
  }
  if (view.fits && !entriesOf(state, course.id).length) {
    if (!course.sections.length) return false;
    if (state.exam_warnings[course.id]) return false;
    if (course.sections.every((section) => state.section_warnings[section.id])) return false;
  }
  return true;
}

let previewTimer = null;
function previewCourse(id) {
  if (id && pointer.still) return;   /* the row came to the mouse, not the mouse to the row */
  clearTimeout(previewTimer);
  previewTimer = setTimeout(() => {
    if (view.preview === id) return;
    view.preview = id;
    renderWeek(Lance.state);
  }, id ? 180 : 0);
}

/* the control at the right edge of every row. A plus adds an elective; a tick says the course is in,
   and under the mouse it turns into × because a click takes it out again.
   A mandatory course says "Pick" instead: Nova assigned its section, so Lance does not guess one, the row opens on its sections. */
function pickButton(course, planned) {
  const key = `pick-${course.id}`;
  if (planned) {
    return el("button", {
      type: "button", class: "pick", "aria-pressed": "true", "aria-label": `Remove ${course.name}`, title: "Remove", "data-key": key,
      html: `<span class="is-in">${Lance.icons.tick}</span><span class="to-out">${Lance.icons.close}</span>`,
      onclick: () => { if (!tooSoon()) removeCourse(course.id, course.name); },
    });
  }
  if (course.kind === "mandatory") {
    return el("button", {
      type: "button", class: "btn small", "aria-label": `Pick your section of ${course.name}`, "data-key": key,
      "aria-expanded": course.sections.length ? String(view.expanded === course.id) : null,
      /* without a timetable there are no sections to show yet: then it opens the whole course */
      onclick: () => (course.sections.length ? toggleExpanded(course) : go(course.id)),
    }, "Pick");
  }
  const where = view.alternates ? " to the alternate list" : "";
  return el("button", {
    type: "button", class: "pick", "aria-pressed": "false", "aria-label": `Add ${course.name}${where}`, title: `Add${where}`, html: Lance.icons.plus, "data-key": key,
    onclick: () => { if (!tooSoon()) addCourse(course); },
  });
}

/* what a row has to say about a clash, also once the course is in the plan */
function clashNote(course, state) {
  const entry = entriesOf(state, course.id)[0];
  const sections = entry ? course.sections.filter((section) => section.id === entry.section_id) : course.sections;
  if (!sections.length || !sections.every((section) => state.section_warnings[section.id])) return null;
  return `Clashes with ${state.section_warnings[sections[0].id][0]}`;
}

/* the sections of a course as small tiles: one click picks one, the week shows where they lie */
function sectionTiles(course, state) {
  const entries = entriesOf(state, course.id);
  return el("div", { class: "tiles", role: "group", "aria-label": `Sections of ${course.name}` }, ...course.sections.map((section) => {
    const at = entries.findIndex((entry) => entry.section_id === section.id);
    const clash = state.section_warnings[section.id];
    const known = section.cutoff !== null && section.cutoff !== undefined;
    const note = clash ? Lance.status("warn", "clashes", { cls: "tile-note" })
      : at > 0 ? el("span", { class: "tile-note", text: "backup" })
        : known ? el("span", { class: "tile-note", text: `from ${Math.ceil(section.cutoff)}` }) : null;
    const where = section.meetings.map((m) => `${m.day} ${compact(m.start)}–${compact(m.end)}, ${m.room}`).join("; ");
    return el("button", {
      type: "button",
      class: `tile${at === 0 ? " on" : ""}${view.hot === section.id ? " hot" : ""}`,
      "aria-pressed": at === 0 ? "true" : "false",
      "data-section": section.id, "data-key": `tile-${section.id}`,
      title: [where, section.delivery === "blended" ? "blended" : null, clash ? `Clashes with ${clash.join(", ")}` : null,
        known ? `Last round: a seat took ${Math.ceil(section.cutoff)}, ${section.seats} seats, ${section.bids} bids` : null].filter(Boolean).join(". "),
      onclick: () => { if (at !== 0) chooseSection(course, section); },
      onmouseenter: canHover ? () => { if (!pointer.still) markHot(section.id); } : null,
      onmouseleave: canHover ? () => markHot(null) : null,
      onfocus: () => markHot(section.id),
      onblur: () => markHot(null),
    },
      el("span", { class: "tile-top" }, el("b", { text: section.section }), at === 0 ? el("span", { class: "tile-tick", html: Lance.icons.tick }) : null),
      ...section.meetings.map((m) => el("span", { class: "tile-time", text: `${m.day} ${compact(m.start)}` })),
      note);
  }));
}

/* the facts under a name: term and ECTS, then the section it has in your plan, or what a seat cost last round */
function metaLine(course, first) {
  const chosen = first && first.section ? ` · ${first.section} ${meetingsText(first.meetings)}` : "";
  /* "a seat took", because "seats from 109" read like a number of seats */
  const price = first || course.cutoff_low === null ? ""
    : course.cutoff_low === course.cutoff_high ? ` · a seat took ${Math.ceil(course.cutoff_low)}`
      : ` · a seat took ${Math.ceil(course.cutoff_low)} to ${Math.ceil(course.cutoff_high)}`;
  /* a phone has no week beside the list, so a course with one section says its time here */
  const time = !first && course.sections.length === 1 ? el("span", { class: "time", text: ` · ${meetingsText(course.sections[0].meetings)}` }) : null;
  /* LN07: what students say on Uni Feedback, as one number; the course sheet has the rest */
  const rating = course.rating === null ? null
    : el("span", { title: `${course.rating.toFixed(1)} of 5 from ${course.reviews} ${course.reviews === 1 ? "review" : "reviews"} on Uni Feedback`, text: ` · ★ ${course.rating.toFixed(1)}` });
  /* a course on the alternate list has the tick like every course of your plan, and says which list it is on.
     It stands in the line of the facts, so that the row is as high as before and the plus stays where it was pressed */
  const alternate = first && first.list === "alternate" ? el("span", {}, " · ", el("b", { class: "on-alternate", text: "alternate" })) : null;
  return el("span", { class: "course-sub" }, `${course.term} · ${course.ects} ECTS`, rating, alternate, chosen, time, price);
}

/* the one thing to know before adding, as a status line: an exam at the same time is worst, then a class, then the same course in the other half */
function noteLine(course, state) {
  const exam = state.exam_warnings[course.id];
  if (exam) return Lance.status("bad", `Exam at the same time as ${exam.join(", ")}`, { cls: "course-note" });
  const clash = clashNote(course, state);
  if (clash) return Lance.status("warn", clash, { cls: "course-note" });
  const twin = state.items.find((item) => item.code === course.code && item.offering_id !== course.id);
  if (twin) return Lance.status("warn", `In your plan in ${twin.term}`, { cls: "course-note" });
  /* two exams on one day are no clash, but a hard day: said last, because the other notes block or double the course */
  const day = state.day_warnings[course.id];
  if (day) return Lance.status("warn", `Exam on the same day as ${day.join(", ")}`, { cls: "course-note" });
  return null;
}

/* a row of the list: name and facts, the chevron, and the control at the right edge. A click anywhere but the control
   folds the row open on its sections. A course in your plan has a dot in its colour before the name, as in the week. */
function courseRow(course, state) {
  const first = entriesOf(state, course.id)[0];
  const planned = Boolean(first);
  const sections = course.sections.length > 0;
  const open = view.expanded === course.id && sections;
  const exam = state.exams.find((item) => item.offering_id === course.id && item.kind === "exam");
  return el("article", {
    class: `course${open ? " open" : ""}${planned ? " in" : ""}`, "data-row": course.id,
    onmouseenter: canHover ? () => previewCourse(course.id) : null,
    onmouseleave: canHover ? () => previewCourse(null) : null,
  },
    el("div", { class: "course-head" },
      el("button", {
        type: "button", class: "course-main", title: course.name, "aria-expanded": sections ? String(open) : null, "data-key": `main-${course.id}`,
        /* without a timetable there is nothing to fold open, so the row leads to the whole course */
        onclick: () => (sections ? toggleExpanded(course) : go(course.id)),
      },
        /* every row keeps the place of the dot, so that all names start on one line */
        planned ? Lance.dot(state, course.id) : el("span", { class: "dot" }),
        el("span", { class: "course-text" }, el("span", { class: "course-name" }, course.name, areaTag(course)), metaLine(course, first), noteLine(course, state)),
        Lance.icon(sections ? "chev" : "next")),
      /* one column of one width: every plus, tick and Pick ends on the same line */
      el("span", { class: "control" }, pickButton(course, planned))),
    open ? el("div", { class: `course-more${view.unfolding === course.id ? " unfold" : ""}` },
      /* the hint stays after the pick: taken away, the tiles would jump up from under the mouse that has just pressed one */
      course.kind === "mandatory" ? el("p", { class: "hint", text: "Pick the section Nova assigned you." }) : null,
      sectionTiles(course, state),
      el("div", { class: "course-foot" },
        el("span", { class: "meta", text: [exam ? `Exam ${exam.label}` : course.exam ? `Exam ${course.exam}` : null, course.lecturers].filter(Boolean).join(" · ") }),
        el("a", { class: "go", href: `#${course.id}` }, "Course details"))) : null);
}

/* LN R20: what a course is in the chosen area of expertise. Only core courses say so: the group already says the rest */
function areaTag(course) {
  const words = { core: "Core", core_optional: "Core option" }[course.area_role];
  return words ? el("span", { class: "area-tag", title: course.area_role === "core" ? "Every core course is needed for the area" : "One core option is needed for the area", text: words }) : null;
}

/* LN R20: under the heading of the area, how far your plan is: a bar, the ECTS, and what is still needed.
   The server counts both semesters, so the bar does not drop when you switch to spring */
const AREA_RULE = { core: ", including every core course", core_optional: ", including one core option", none: "" };

function areaProgress(area) {
  const needs = [...area.core_missing, area.core_options.length ? `one of ${area.core_options.join(", ")}` : null].filter(Boolean);
  const ects = `${area.ects} of ${area.needed} ECTS`;
  /* first what counts, then how far you are; once the area is complete the rule has nothing left to say */
  const rule = area.done ? null : el("span", { class: "area-rule" },
    `Needs ${area.needed} ECTS of electives from this list${AREA_RULE[area.core_rule]}. `,
    el("a", { class: "go", href: "/rules?about=areas#areas" }, "How areas work"));
  return el("div", { class: "area-progress" }, rule,
    el("span", { class: "area-bar", "aria-hidden": "true" }, el("span", { style: `width: ${Math.min(100, (area.ects / area.needed) * 100)}%` })),
    area.done ? Lance.status("ok", `Area complete · ${ects}`)
      : el("span", { class: "area-words", text: needs.length ? `${ects} · still needed: ${needs.join(", ")}` : ects }),
    area.elsewhere.length ? el("span", { class: "area-words", text: `Not in Lance, counts too: ${area.elsewhere.map((course) => `${course.name} (${course.ects} ECTS)`).join(", ")}` }) : null);
}

function renderList(state) {
  const list = document.getElementById("courses");
  const scroll = list.scrollTop;
  const focused = document.activeElement && list.contains(document.activeElement) ? document.activeElement.dataset.key : null;
  list.replaceChildren();
  const shown = view.catalogue.filter((course) => matches(course, state));
  if (!shown.length) {
    const other = state.plan.semester === "Fall" ? "Spring" : "Fall";
    list.append(el("div", { class: "empty-note" },
      el("p", { text: view.fits ? "Nothing else fits your week." : `No course matches in ${state.plan.semester}.` }),
      view.fits ? null : el("button", { type: "button", class: "btn tertiary", onclick: () => changeSetting({ semester: other }) }, `Look in ${other}`)));
    view.unfolding = null;
    return;
  }
  const noProgramme = !state.plan.programme;
  /* LN R20: with an area of expertise chosen, its courses leave Electives and Other programmes for a group of their own,
     right under the mandatory courses. Its heading stays while no course of it is on show, for the progress under it */
  const area = state.area;
  const inArea = (course) => Boolean(area && course.area_role && course.kind !== "mandatory");
  const titles = { mandatory: "Mandatory", ...(area ? { area: area.name } : {}), elective: "Electives", outside: noProgramme ? "All courses" : "Other programmes" };
  Object.keys(titles).forEach((kind) => {
    const courses = shown.filter((course) => (kind === "area" ? inArea(course) : course.kind === kind && !inArea(course)));
    if (!courses.length && !(kind === "area" && !view.query && !view.fits)) return;
    const folded = !view.query && !noProgramme && view.closed[kind];
    /* a group heading folds like a row: the whole line is the button, the chevron at the right edge */
    list.append(el("button", {
      type: "button", class: `group${kind === "area" ? " area-group" : ""}`, "aria-expanded": folded ? "false" : "true",
      onclick: () => { view.closed[kind] = !view.closed[kind]; holdPreviews(); renderList(Lance.state); },
    }, el("span", { class: "group-name", text: titles[kind] }), el("span", { class: "count", text: String(courses.length) }), Lance.icon("chev")));
    if (kind === "area") list.append(areaProgress(area));
    if (!folded) courses.forEach((course) => list.append(courseRow(course, state)));
  });
  list.scrollTop = scroll;
  view.unfolding = null;   /* drawn once with its glide; from the next drawing on the open row stands still */
  if (focused) {
    const again = list.querySelector(`[data-key="${focused}"]`);
    if (again) again.focus({ preventScroll: true });
  }
}

/* ---- the sections of the open course: the same tiles as in the list ---- */

function renderSections(state) {
  const box = document.getElementById("sheet-sections");
  if (!box || !view.open || box.dataset.offering !== view.open) return;
  const course = courseById(view.open);
  const title = el("h2", { text: "Sections" });
  if (!course) {
    const other = state.plan.semester === "Fall" ? "Spring" : "Fall";
    box.replaceChildren(title, el("p", { class: "meta" }, `This course runs in ${other}. `,
      el("button", { type: "button", class: "inline-link", onclick: async () => { await changeSetting({ semester: other }); renderSections(Lance.state); } }, `Plan for ${other.toLowerCase()}`)));
    return;
  }
  const entries = entriesOf(state, course.id);
  /* taking a course out is a small extra here, so it is a tertiary button; putting it in is the secondary one */
  const remove = entries.length ? el("button", { type: "button", class: "btn tertiary flush", onclick: () => removeCourse(course.id, course.name) }, "Remove from my plan") : null;
  if (!course.sections.length) {
    box.replaceChildren(title, el("p", { class: "meta", text: "Nova has not published the timetable yet." }),
      remove || el("button", { type: "button", class: "btn", style: "align-self:flex-start", onclick: () => Lance.send("/api/add", { offering_id: course.id }) }, "Add to my plan"));
    return;
  }
  const examClash = state.exam_warnings[course.id];
  box.replaceChildren(...[
    title,
    course.kind === "mandatory" ? el("p", { class: "hint", text: "Pick the section Nova assigned you." }) : null,
    examClash ? Lance.status("bad", `Exam at the same time as ${examClash.join(", ")}`) : null,
    sectionTiles(course, state),
    remove,
  ].filter(Boolean));
}

/* ---- the week ---- */

function clashingItems(state) {
  const ids = new Set();
  state.clashes.forEach((clash) => {
    if (clash.items && clash.weeks.includes(view.half)) clash.items.forEach((id) => ids.add(id));
  });
  return ids;
}

/* the other sections of the course in view wait in the week as ghosts: a dashed outline in the colour of their course */
function ghostBlocks(state) {
  const course = courseById(view.open || view.preview || view.expanded);
  if (!course || !TERMS_OF[view.half] || !TERMS_OF[view.half].includes(course.term)) return [];
  const chosen = entriesOf(state, course.id)[0];
  const colour = `colour-${Lance.colourOf(state, course.id)}`;
  const blocks = [];
  course.sections.forEach((section) => {
    if (chosen && chosen.section_id === section.id) return;
    const clash = state.section_warnings[section.id];
    section.meetings.forEach((m) => {
      blocks.push({
        day: m.day, start: m.start, end: m.end,
        name: section.section, section: clash ? "clashes" : m.room, sectionId: section.id,
        class: `ghost ${colour}${clash ? " bad" : ""}${view.hot === section.id ? " hot" : ""}`,
        title: `${course.name} ${section.section}, ${m.day} ${compact(m.start)}–${compact(m.end)}, ${m.room}${clash ? `. Clashes with ${clash.join(", ")}` : ""}`,
        onclick: () => chooseSection(course, section),
        onmouseenter: () => markHot(section.id),
        onmouseleave: () => markHot(null),
      });
    });
  });
  return blocks;
}

function renderWeek(state) {
  if (!state) return;
  const onWeek = hasWeek(state);
  document.getElementById("week-wrap").hidden = !onWeek;
  document.getElementById("no-timetable").hidden = onWeek;
  if (!onWeek) return;
  const clashing = clashingItems(state);
  const blocks = [];
  state.items.forEach((item) => {
    /* while the alternate list is filled, the week also shows what is on it: the entries the server marks for that.
       They are drawn beside the week and are not part of it (LN R13); what they meet is said in their own row */
    const alternate = view.alternates && item.in_alternate_week;
    if (!(item.in_week || alternate) || !TERMS_OF[view.half].includes(item.term)) return;
    /* then a primary course steps back, to a dashed outline: it stays, because an alternate is checked against it */
    const faded = view.alternates && item.list === "primary";
    /* a block wears the colour of its course, the same as the dot before its name in the list, in Bids and in Summary */
    const colour = `colour-${Lance.colourOf(state, item.offering_id)}`;
    /* resting on a block says which list it is on, and for an alternate what the server found it to meet */
    const notes = alternate ? ["On your alternate list", ...item.conflicts.map((note) => note.text.replace(/\.$/, ""))].join(". ") : faded ? "On your primary list" : "";
    item.meetings.forEach((m) => {
      blocks.push({
        day: m.day, start: m.start, end: m.end,
        /* an alternate says so where the others name their section and room: one word, so that it fits a phone's narrow day too */
        name: item.name, section: alternate ? "alternate" : item.section, room: alternate ? null : m.room, sectionId: item.section_id,
        clashing: clashing.has(item.id),
        class: [colour, alternate && "alt", faded && "faded", (view.open || view.expanded) === item.offering_id && "open", view.fresh === item.section_id && "fresh", view.hot === item.section_id && "hot"].filter(Boolean).join(" "),
        title: `${item.name} ${item.section}, ${m.day} ${compact(m.start)}–${compact(m.end)}, ${m.room}${notes ? `. ${notes}` : ""}`,
        onclick: () => go(item.offering_id),
      });
    });
  });
  view.fresh = null;
  const ghosts = ghostBlocks(state);
  Week.draw(document.getElementById("week-days"), document.getElementById("week"), blocks, ghosts, view.half);
  const empty = document.getElementById("week-empty");
  empty.hidden = state.items.length > 0 || ghosts.length > 0;
  empty.replaceChildren(el("span", { text: state.plan.programme ? "Pick your mandatory sections, then press + on an elective." : "Choose your programme, then press + on a course." }),
    el("button", { type: "button", class: "btn", onclick: tryExample }, "Try an example"));
}

async function tryExample() {
  await Lance.send("/api/example", {});
  await loadCatalogue();
  Lance.update(Lance.state);
  Lance.toast("An example: a real Management plan from Fall 2026.", { label: "Reset", run: resetPlan });
}

/* ---- above the list, and the lines about clashes ---- */

function renderTabs(state) {
  const halves = HALVES[state.plan.semester];
  if (!TERMS_OF[view.half] || !halves.some(([key]) => key === view.half)) view.half = halves[0][0];
  Lance.remember("half", view.half);
  document.getElementById("half-tabs").replaceChildren(...halves.map(([key, when]) => el("button", {
    type: "button", class: view.half === key ? "on" : "", title: when, onclick: () => { view.half = key; render(Lance.state); },
  }, key)));
  const note = document.getElementById("round-note");
  note.hidden = !state.round || state.round.status !== "closed";
  if (!note.hidden) {
    const next = state.next_deadline;
    note.replaceChildren(`The ${state.plan.semester} round closed on ${state.round.last_day}: this is practice. ${next ? `Next: ${next.range.split(" – ")[0].split(" ").slice(1).join(" ")}. ` : ""}`,
      state.plan.semester === "Fall" ? el("button", { type: "button", class: "inline-link", onclick: () => changeSetting({ semester: "Spring" }) }, "Plan for spring") : null);
  }
  document.getElementById("fits").hidden = !hasWeek(state) || !state.items.some((item) => item.in_week);
  /* the way to Nova turns blue once there is something to bid on */
  document.getElementById("next").classList.toggle("primary", state.items.some((item) => item.list !== "mandatory"));
}

/* the way out of a clash: another section that fits, or take the elective out */
function clashActions(clash, state) {
  const offerings = clash.offerings.map((id) => entriesOf(state, id)[0]).filter(Boolean);
  const target = offerings.slice().reverse().find((entry) => entry.list !== "mandatory") || offerings[offerings.length - 1];
  if (!target) return [];
  const course = courseById(target.offering_id);
  const other = course && clash.kind === "class" ? course.sections.find((section) => section.id !== target.section_id && !state.section_warnings[section.id]) : null;
  return [
    clash.weeks && !clash.weeks.includes(view.half) ? el("button", { type: "button", class: "btn tertiary", onclick: () => { view.half = clash.weeks[0]; render(Lance.state); } }, `Show ${clash.weeks[0]}`) : null,
    other ? el("button", { type: "button", class: "btn tertiary", title: `Switch ${target.name} to ${other.section}`, onclick: () => chooseSection(course, other) }, `Switch to ${other.section}`) : null,
    el("button", { type: "button", class: "btn tertiary", title: `Remove ${target.name}`, onclick: () => removeCourse(target.offering_id, target.name) }, `Remove ${target.name}`),
  ];
}

function clashText(clash) {
  if (clash.kind === "class") {
    const count = clash.times === clash.of ? `all ${clash.of} classes` : `${clash.times} of ${clash.of} classes`;
    return [`${clash.weeks.join(", ")}: `, `${clash.first} × ${clash.second}`, `, ${clash.when}, ${count}. You can't attend both.`];
  }
  if (clash.kind === "exam") return ["Exams: ", `${clash.first} × ${clash.second}`, `, ${clash.when}. Nova blocks this.`];
  return ["Midterm: ", `${clash.first} × ${clash.second}`, `, ${clash.when}. Nova does not check this.`];
}

/* a clash under the week is a status line, worst first: an exam is red, a class or a midterm orange */
function renderClashes(state) {
  const shown = state.clashes.slice(0, view.allClashes ? undefined : 2);
  const box = document.getElementById("clashes");
  box.replaceChildren(...shown.map((clash) => {
    const [before, pair, after] = clashText(clash);
    const tone = clash.kind === "exam" ? "bad" : "warn";
    return el("div", { class: `clash-line ${clash.severity}` },
      el("p", { class: `status ${tone}` }, Lance.icon(tone), el("span", {}, before, el("b", { text: pair }), after)),
      ...clashActions(clash, state).filter(Boolean));
  }));
  if (state.clashes.length > 2 && !view.allClashes) {
    box.append(el("button", { type: "button", class: "btn tertiary flush", onclick: () => { view.allClashes = true; renderClashes(Lance.state); } }, `${state.clashes.length - 2} more`));
  }
  /* a hard day, two exams one after the other: an orange line under the clashes, never counted as a clash */
  state.exam_days.forEach((day) => box.append(el("div", { class: "clash-line exam-day" },
    el("p", { class: "status warn" }, Lance.icon("warn"), el("span", {}, `Two exams on ${day.when}: `, el("b", { text: `${day.first} × ${day.second}` }), ". Nova allows it, but it is a long day.")))));
}

/* ---- the head of your plan: where you stand, whatever tab is open ---- */

/* the ECTS say what they are measured against, in words and not only in a tooltip:
   above Nova's recommendation "31.5 ECTS · 28 recommended" in orange, above the maximum "42 ECTS · max 31.5" in red */
function ectsWords(ects) {
  if (ects.over) return { tone: "bad", label: `ECTS · max ${ects.maximum}` };
  if (ects.total > ects.recommended) return { tone: "warn", label: `ECTS · ${ects.recommended} recommended` };
  return { tone: null, label: "ECTS" };
}

/* where you stand: the number dark, the word grey; a tone (warn, bad) adds colour and an icon.
   The head of your plan has them, and a phone shows the same above the list, without the ids */
function figuresOf(state, head) {
  const points = state.plan.points;
  const left = points - state.reserved;
  const electives = state.items.some((item) => item.list === "primary");
  const clashes = state.clashes.length;
  const exam = state.clashes.some((clash) => clash.kind === "exam");
  const ects = ectsWords(state.ects);
  const figure = (value, label, tone, title, id) => el("span", { class: tone ? `status ${tone}` : null, title, id: head ? id : null },
    tone ? Lance.icon(tone) : null, el("b", { class: "num", text: value }), ` ${label}`);
  return [
    figure(String(state.ects.total), ects.label, ects.tone, `Nova recommends ${state.ects.recommended} ECTS, the maximum is ${state.ects.maximum}`, "ects"),
    /* LN R17: points nobody typed are an estimate from the mandatory courses, and "about" says so */
    points ? figure(String(left), state.plan.points_estimated ? "points left, estimated" : "points left", left < 0 ? "bad" : null,
      state.plan.points_estimated ? `About ${points} points for ${state.mandatory_ects} mandatory ECTS. Type your Balance in Bids to replace the estimate`
        : `${state.reserved} of your ${points} points are in bids`)
      : electives ? Lance.status("warn", "No points yet") : el("span", { text: "No points yet" }),
    clashes ? figure(String(clashes), clashes === 1 ? "clash" : "clashes", exam ? "bad" : "warn") : el("span", { text: "No clash" }),
  ];
}

function renderHead(state) {
  const clashes = state.clashes.length;
  const exam = state.clashes.some((clash) => clash.kind === "exam");
  document.getElementById("figures").replaceChildren(...figuresOf(state, true));
  document.getElementById("reset").hidden = state.items.length === 0;
  /* above the list only once there is something in the plan: then a + shows what it changed */
  const line = document.getElementById("list-figures");
  const shown = state.items.length > 0;
  const list = document.getElementById("courses");
  const before = line.hidden === shown && onPhone() ? list.getBoundingClientRect().top : null;
  line.hidden = !shown;
  line.replaceChildren(...figuresOf(state, false));
  /* when it comes or goes while the list is scrolled past it, the list stays where it is */
  if (before !== null && before < document.querySelector(".topbar").getBoundingClientRect().bottom) window.scrollBy(0, list.getBoundingClientRect().top - before);
  badge("week", clashes ? { cls: exam ? "bad" : "", text: `${clashes} ${clashes === 1 ? "clash" : "clashes"}` } : null);
  badge("bids", typeof Bids === "undefined" ? null : Bids.problem(state));
}

/* a tab names what needs a look there, in two words at most */
function badge(key, found) {
  const node = document.getElementById(`badge-${key}`);
  node.hidden = !found;
  if (!found) return;
  node.className = `badge${found.cls ? ` ${found.cls}` : ""}`;
  node.textContent = found.text;
}

/* ---- the Summary tab: every course of the plan in one table, the totals at the bottom ---- */

/* a table cell that can carry a status: the plain value, or the same value in the colour and with the icon of its tone */
function cellValue(text, tone, title) {
  return tone ? Lance.status(tone, text, { title }) : text;
}

function planRow(entries, state, classClash, examClash) {
  const first = entries[0];
  const alternate = first.list === "alternate";
  const backups = entries.slice(1).map((item) => item.section).filter(Boolean);
  const exam = state.exams.find((item) => item.offering_id === first.offering_id && item.kind === "exam");
  const clash = classClash.get(first.id);
  const examLevel = examClash.get(first.offering_id) || (state.exam_days.some((day) => day.offerings.includes(first.offering_id)) ? "day" : null);
  const bid = entries.some((item) => item.bid !== null) ? Math.max(...entries.map((item) => item.bid || 0)) : null;
  const time = first.section ? meetingsText(first.meetings) : "Not published";
  /* like every list: the whole row opens the course on the left, the chevron at the right edge says so.
     The name stays a link for the keyboard, in ink like the names in the other lists */
  return el("tr", {
    class: `go-row${alternate ? " alt" : ""}`,
    onclick: (event) => { if (!event.target.closest("a, button")) go(first.offering_id); },
  },
    el("td", { class: "name" }, el("span", { class: "named" },
      Lance.dot(state, first.offering_id),
      el("span", { class: "course-text" },
        el("a", { class: "name-link", href: `#${first.offering_id}`, title: first.name }, first.name),
        el("span", { class: "plan-sub", text: [first.term, first.section ? `${first.section} ${time}` : null, exam ? `Exam ${exam.label}` : null].filter(Boolean).join(" · ") })))),
    el("td", { class: "opt" }, first.section || "–", backups.length ? el("span", { class: "faint", title: `If full: ${backups.join(", ")}`, text: ` +${backups.length}` }) : null),
    el("td", { class: "opt" }, clash ? cellValue(`${first.term} · ${time}`, "warn", `Clashes: ${clash}`) : el("span", { class: "faint", text: `${first.term} · ` }), clash ? null : time),
    el("td", { class: `r num${alternate ? " faint" : ""}`, title: alternate ? "The alternate list does not count" : null, text: alternate ? `(${first.ects})` : String(first.ects) }),
    el("td", { class: "opt" }, cellValue(exam ? exam.label : "–", examLevel === "exam" ? "bad" : examLevel ? "warn" : null, examLevel === "day" ? "Two exams on one day" : null)),
    el("td", { class: `r num${alternate ? " faint" : ""}` },
      first.list === "mandatory" ? "–" : bid === null ? cellValue("No bid", first.list === "primary" ? "warn" : null) : String(bid)),
    /* out of the plan right here: nobody has to find the course in the list again */
    el("td", { class: "act" }, el("button", {
      type: "button", class: "icon-btn", title: `Remove ${first.name}`, "aria-label": `Remove ${first.name}`, html: Lance.icons.close,
      onclick: () => removeCourse(first.offering_id, first.name),
    })),
    el("td", { class: "chev" }, Lance.icon("next")));
}

/* the totals under the table: numbers dark, words grey, a tone only where something needs a look.
   One line in the order of the columns (courses, Time, ECTS, Exam, Bid) that wraps between its parts, and not one cell
   per column: "31.5 ECTS · 28 recommended", in the words of the head of your plan, does not fit under the narrow column ECTS.
   A phone, without the columns Time and Exam, leaves out their two checks as well */
function totalsRow(state, counted, alternates) {
  const classClashes = state.clashes.filter((clash) => clash.kind === "class").length;
  const examClashes = state.clashes.filter((clash) => clash.kind !== "class");
  const ects = ectsWords(state.ects);
  const many = (count, word) => `${count} ${word}${count === 1 ? "" : word.endsWith("sh") ? "es" : "s"}`;
  return el("tr", {}, el("td", { colspan: 8 }, el("div", { class: "plan-totals" },
    el("span", {}, el("b", { class: "num", text: String(counted) }), counted === 1 ? " course" : " courses", alternates ? ` + ${alternates} alternate` : null),
    el("span", { class: "opt" }, classClashes ? cellValue(many(classClashes, "class clash"), "warn") : "No class clash"),
    el("span", { title: `Nova recommends ${state.ects.recommended} ECTS, the maximum is ${state.ects.maximum}` },
      ...(ects.tone ? [cellValue(`${state.ects.total} ${ects.label}`, ects.tone)] : [el("b", { class: "num", text: String(state.ects.total) }), " ECTS"])),
    el("span", { class: "opt" }, examClashes.length ? cellValue(many(examClashes.length, "exam clash"), examClashes.some((clash) => clash.kind === "exam") ? "bad" : "warn") : "No exam clash"),
    el("span", {}, el("b", { class: "num", text: String(state.reserved) }), " in bids"))));
}

function renderPlanTable(state) {
  const box = document.getElementById("plan-table");
  const offerings = [...new Set(state.items.slice().sort((a, b) => a.position - b.position).map((item) => item.offering_id))];
  if (!offerings.length) {
    box.replaceChildren(el("p", { class: "empty-note", text: "Nothing in your plan yet." }));
    return;
  }
  const classClash = new Map();   /* item -> the pair it clashes in */
  const examClash = new Map();    /* course -> exam or midterm */
  state.clashes.forEach((clash) => {
    if (clash.kind === "class") clash.items.forEach((id) => classClash.set(id, `${clash.first} × ${clash.second}`));
    else (clash.offerings || []).forEach((id) => { if (examClash.get(id) !== "exam") examClash.set(id, clash.kind); });
  });
  const body = el("tbody");
  [["mandatory", "Mandatory"], ["primary", "Primary list"], ["alternate", "Alternate list"]].forEach(([list, title]) => {
    const ids = offerings.filter((id) => entriesOf(state, id)[0].list === list);
    if (!ids.length) return;
    body.append(el("tr", { class: "plan-group" }, el("th", { colspan: 8, scope: "colgroup", text: title })));
    ids.forEach((id) => body.append(planRow(entriesOf(state, id), state, classClash, examClash)));
  });
  const counted = offerings.filter((id) => entriesOf(state, id)[0].list !== "alternate").length;
  const head = (label, cls) => el("th", { scope: "col", class: cls || null, text: label });
  box.replaceChildren(
    el("table", { class: "plan-table" },
      el("thead", {}, el("tr", {}, head("Course"), head("Section", "opt"), head("Time", "opt"), head("ECTS", "r"), head("Exam", "opt"), head("Bid", "r"),
        el("th", { class: "act" }, el("span", { class: "sr", text: "Remove" })), el("th", { class: "chev" }, el("span", { class: "sr", text: "Open" })))),
      body,
      el("tfoot", {}, totalsRow(state, counted, offerings.length - counted))));
}

/* ---- LN R19: the two arrows in the top bar. The server keeps the steps; the page asks for one step back or
   forward and redraws from the answer, as after any other change ---- */

let stepping = false;   /* one step at a time: a second press waits until the first has its answer */
async function takeStep(way) {
  const possible = Lance.state && (way === "undo" ? Lance.state.can_undo : Lance.state.can_redo);
  if (stepping || !possible) return;
  stepping = true;
  try {
    /* a bid still waiting to be saved is the last change, so it goes first */
    if (typeof Bids !== "undefined") await Bids.flush();
    const answer = await Lance.send(`/api/${way}`, {});
    if (!answer.error) Lance.toast(way === "undo" ? "Undone" : "Redone");
  } finally {
    stepping = false;
  }
}

/* an arrow is switched off when there is nothing to take back or to do again */
function renderArrows(state) {
  document.getElementById("undo").disabled = !state.can_undo;
  document.getElementById("redo").disabled = !state.can_redo;
}

/* a field keeps its own undo: Cmd+Z while typing in the search, a number or a menu is not meant for your plan */
const inField = (node) => node instanceof Element && node.matches("input:not([type=checkbox]), textarea, select");

/* the keys: Cmd+Z or Ctrl+Z one step back; with Shift, or Ctrl+Y, forward again */
function arrowKeys(event) {
  if (!(event.metaKey || event.ctrlKey) || event.altKey || inField(event.target)) return;
  const key = event.key.toLowerCase();
  const way = key === "z" ? (event.shiftKey ? "redo" : "undo") : key === "y" && event.ctrlKey && !event.shiftKey ? "redo" : null;
  if (!way) return;
  event.preventDefault();
  takeStep(way);
}

/* ---- wiring ---- */

function render(state) {
  /* no week, nothing to fill the alternate list in: spring keeps the search in the Bids tab */
  if (view.alternates && !hasWeek(state)) view.alternates = false;
  document.getElementById("alternate-banner").hidden = !view.alternates;
  renderArrows(state);
  renderTabs(state);
  renderHead(state);
  renderList(state);
  renderSections(state);
  renderWeek(state);
  renderClashes(state);
  renderPlanTable(state);
  const programme = document.getElementById("set-programme");
  const semester = document.getElementById("set-semester");
  programme.value = state.plan.programme;
  semester.value = state.plan.semester;
  fitToValue(programme);
  fitToValue(semester);
  /* LN R20: the areas of the programme on show; a programme without any hides the menu */
  const area = document.getElementById("set-area");
  area.replaceChildren(el("option", { value: "", text: "No area of expertise" }), ...state.areas.map((name) => el("option", { value: name, text: name })));
  area.value = state.plan.area || "";
  area.hidden = !state.areas.length;
  if (!area.hidden) fitToValue(area);
}

/* a menu is only as wide as what it shows, so that everything stays on one line (browsers make it as wide as its longest option).
   46 = the padding on the left (10) and right (32, room for the chevron) and the border (2), plus a little air */
function fitToValue(select) {
  const context = fitToValue.canvas.getContext("2d");
  context.font = getComputedStyle(select).font;
  select.style.width = `${Math.ceil(context.measureText(select.selectedOptions[0].text).width) + 46}px`;
}
fitToValue.canvas = document.createElement("canvas");

/* the Bids tab reads the same catalogue, for the sections to try if full and the alternate list */
async function loadCatalogue() {
  const response = await fetch("/api/catalogue");
  view.catalogue = await response.json();
  Lance.catalogue = view.catalogue;
}

async function changeSetting(body) {
  await Lance.send("/api/settings", body);
  await loadCatalogue();
  view.half = null;
  view.fits = false;
  document.getElementById("fits").setAttribute("aria-pressed", "false");
  Lance.update(Lance.state);
}

document.getElementById("search").addEventListener("input", (event) => {
  view.query = event.target.value.trim();
  Lance.remember("query", view.query);
  if (Lance.state) renderList(Lance.state);
});
document.getElementById("fits").addEventListener("click", (event) => {
  view.fits = !view.fits;
  event.currentTarget.setAttribute("aria-pressed", view.fits ? "true" : "false");
  if (Lance.state) renderList(Lance.state);
});
document.getElementById("reset").addEventListener("click", resetPlan);
document.getElementById("alternate-done").addEventListener("click", stopAlternates);
document.getElementById("undo").addEventListener("click", () => takeStep("undo"));
document.getElementById("redo").addEventListener("click", () => takeStep("redo"));
document.addEventListener("keydown", arrowKeys);
document.getElementById("set-programme").addEventListener("change", (event) => changeSetting({ programme: event.target.value }));
document.getElementById("set-semester").addEventListener("change", (event) => changeSetting({ semester: event.target.value }));
document.getElementById("set-area").addEventListener("change", (event) => changeSetting({ area: event.target.value }));
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (view.open) goBack();
  else if (view.expanded) { const id = view.expanded; view.expanded = null; renderKeeping(id); const main = document.querySelector(`[data-key="main-${id}"]`); if (main) main.focus({ preventScroll: true }); }
  /* with nothing left to close, Esc ends filling the alternate list, like Done */
  else if (view.alternates) stopAlternates();
});
window.addEventListener("hashchange", route);
/* on a phone the bar at the bottom only changes the surface; there is no need to load the page again */
[["courses", ""], ["week", "week"], ["bids", "bids"]].forEach(([key, target]) => {
  document.querySelector(`.tabbar [data-tab=${key}]`).addEventListener("click", (event) => { event.preventDefault(); location.hash = target; });
});
document.querySelectorAll("#plan-tabs [role=tab]").forEach((tab) => tab.addEventListener("click", () => setTab(tab.dataset.view)));
document.getElementById("plan-tabs").addEventListener("keydown", (event) => {
  if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
  const next = TABS[(TABS.indexOf(view.tab) + (event.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length];
  setTab(next);
  document.getElementById(`tab-${next}`).focus();
});

(async function start() {
  const planner = document.getElementById("planner");
  view.tab = planner.dataset.view;
  view.half = Lance.remember("half") || null;
  view.query = Lance.remember("query") || "";
  document.getElementById("search").value = view.query;
  await loadCatalogue();
  Lance.onChange(render);
  await Lance.load();
  /* a link to a course opens the same page with that course open */
  if (planner.dataset.open) history.replaceState(null, "", Lance.courseHref(planner.dataset.open));
  /* /bids is this screen with the Bids tab open; on a phone the address says so, so that the bar can lead back */
  else if (view.tab !== "week" && !location.hash) {
    try { history.replaceState(null, "", `#${view.tab}`); } catch (error) { /* a sandboxed preview keeps its address */ }
  }
  route();
})();
