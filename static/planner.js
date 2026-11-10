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
  preview: null,       /* the course under the mouse in the list */
  hot: null,           /* the section under the mouse */
  fresh: null,         /* the section that was just added: it pops in */
  backTo: "",          /* where the Back button of an open course leads: the list, or a tab of your plan on a phone */
  allClashes: false,
  pausedUntil: 0,      /* a double click must not hit the row that has just moved under the mouse */
};
const HALVES = {
  Fall: [["T1", "T1: until 12 Oct"], ["T2", "T2: from 22 Oct"]],
  Spring: [["T3", "T3: from 1 Feb"], ["T4", "T4: from 5 Apr"]],
};
const TERMS_OF = { T1: ["S1", "T1"], T2: ["S1", "T2"], T3: ["S2", "T3"], T4: ["S2", "T4"] };
const EXAM_WORD = { exam: "Exam", midterm: "Midterm", presentation: "Presentation" };
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

async function addCourse(course) {
  bringForward(course);
  const answer = await Lance.send("/api/add", { offering_id: course.id });
  if (answer.error) return;
  const entry = entriesOf(Lance.state, course.id)[0];
  view.fresh = entry.section_id;
  if (course.sections.length > 1) { view.expanded = course.id; showWeek(); }
  render(Lance.state);
  Lance.toast(`Added ${course.name}${course.sections.length > 1 ? ` ${entry.section}` : ""}`);
}

async function removeCourse(offeringId, name) {
  const answer = await Lance.send("/api/remove", { offering_id: offeringId });
  if (answer.error) return;
  Lance.toast(`Removed ${name}`, { label: "Undo", run: () => Lance.send("/api/restore", { rows: answer.removed }) });
}

async function chooseSection(course, section) {
  view.hot = null;
  bringForward(course);
  view.fresh = section.id;
  await Lance.send(entriesOf(Lance.state, course.id).length ? "/api/switch" : "/api/add", { section_id: section.id });
}

/* the section under the mouse lights up in the list and in the week at once, without drawing anything again */
function markHot(sectionId) {
  view.hot = sectionId;
  document.querySelectorAll("[data-section]").forEach((node) => node.classList.toggle("hot", node.dataset.section === sectionId));
}

function toggleExpanded(course) {
  /* a click beats the mouse: the week shows the row just opened, not the one hovered a moment ago */
  clearTimeout(previewTimer);
  view.preview = null;
  view.expanded = view.expanded === course.id ? null : course.id;
  if (view.expanded) { bringForward(course); showWeek(); }
  render(Lance.state);
}

/* a row folded open shows its sections in the week, so the right half turns to the week */
function showWeek() {
  if (view.tab !== "week" && !onPhone()) setTab("week");
}

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
    type: "button", class: "back", html: `${Lance.icons.back} Courses`, onclick: goBack,
  }));
  const response = await fetch(`/api/sheet/${encodeURIComponent(wanted)}`);
  if (view.open !== wanted) return;
  box.append(el("div", { style: "display:contents", html: response.ok ? await response.text() : '<p class="muted">This course does not exist.</p>' }));
  box.scrollTop = 0;
  renderSections(Lance.state);
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
  clearTimeout(previewTimer);
  previewTimer = setTimeout(() => {
    if (view.preview === id) return;
    view.preview = id;
    renderWeek(Lance.state);
  }, id ? 180 : 0);
}

/* the one control of a row. Plus always adds. A tick means it is in; under the mouse it shows that a click takes it out. */
function pickButton(course, planned) {
  if (planned) {
    return el("button", {
      type: "button", class: "pick", "aria-pressed": "true", "aria-label": `Remove ${course.name}`, title: "Remove", "data-key": `pick-${course.id}`,
      html: `<span class="is-in">${Lance.icons.tick}</span><span class="to-out">${Lance.icons.close}</span>`,
      onclick: () => { if (!tooSoon()) removeCourse(course.id, course.name); },
    });
  }
  if (course.kind === "mandatory" && course.sections.length > 1) {
    /* Nova assigned the section, so Lance does not guess one: the row folds open instead */
    return el("button", {
      type: "button", class: "btn small", "aria-label": `Pick your section of ${course.name}`, "data-key": `pick-${course.id}`,
      onclick: () => toggleExpanded(course),
    }, "Pick");
  }
  return el("button", {
    type: "button", class: "pick", "aria-pressed": "false", "aria-label": `Add ${course.name}`, title: "Add", html: Lance.icons.plus, "data-key": `pick-${course.id}`,
    onclick: () => { if (!tooSoon()) addCourse(course); },
  });
}

/* what a row has to say about a clash, also once the course is in the plan */
function clashNote(course, state) {
  const entry = entriesOf(state, course.id)[0];
  const sections = entry ? course.sections.filter((section) => section.id === entry.section_id) : course.sections;
  if (!sections.length || !sections.every((section) => state.section_warnings[section.id])) return null;
  return `clashes with ${state.section_warnings[sections[0].id][0]}`;
}

/* the sections of a course as small tiles: one click picks one, the week shows where they lie */
function sectionTiles(course, state) {
  const entries = entriesOf(state, course.id);
  return el("div", { class: "tiles", role: "group", "aria-label": `Sections of ${course.name}` }, ...course.sections.map((section) => {
    const at = entries.findIndex((entry) => entry.section_id === section.id);
    const clash = state.section_warnings[section.id];
    const known = section.cutoff !== null && section.cutoff !== undefined;
    const note = clash ? el("span", { class: "tile-note warn", text: "clashes" })
      : at > 0 ? el("span", { class: "tile-note", text: "backup" })
        : known ? el("span", { class: "tile-note", text: `from ${Math.ceil(section.cutoff)}` }) : null;
    const where = section.meetings.map((m) => `${m.day} ${compact(m.start)}–${compact(m.end)}, ${m.room}`).join("; ");
    return el("button", {
      type: "button",
      class: `tile${at === 0 ? " on" : ""}${clash ? " warn" : ""}${view.hot === section.id ? " hot" : ""}`,
      "aria-pressed": at === 0 ? "true" : "false",
      "data-section": section.id, "data-key": `tile-${section.id}`,
      title: [where, section.delivery === "blended" ? "blended" : null, clash ? `Clashes with ${clash.join(", ")}` : null,
        known ? `Last round: seat from ${Math.ceil(section.cutoff)}, ${section.seats} seats, ${section.bids} bids` : null].filter(Boolean).join(". "),
      onclick: () => { if (at !== 0) chooseSection(course, section); },
      onmouseenter: canHover ? () => markHot(section.id) : null,
      onmouseleave: canHover ? () => markHot(null) : null,
      onfocus: () => markHot(section.id),
      onblur: () => markHot(null),
    },
      el("span", { class: "tile-top" }, el("b", { text: section.section }), at === 0 ? el("span", { class: "tile-tick", html: Lance.icons.tick }) : null),
      ...section.meetings.map((m) => el("span", { class: "tile-time", text: `${m.day} ${compact(m.start)}` })),
      note);
  }));
}

/* a row of the list: name and facts, one control, and folded open the sections to pick from */
function courseRow(course, state, mine) {
  const entries = entriesOf(state, course.id);
  const first = entries[0];
  const planned = entries.length > 0;
  const clash = clashNote(course, state);
  const open = view.expanded === course.id && course.sections.length > 0;
  const price = course.cutoff_low === null ? "" : course.cutoff_low === course.cutoff_high ? ` · seat from ${Math.ceil(course.cutoff_low)}` : ` · seats from ${Math.ceil(course.cutoff_low)} to ${Math.ceil(course.cutoff_high)}`;
  const twin = state.items.find((item) => item.code === course.code && item.offering_id !== course.id);
  const lines = [];
  if (mine) {
    lines.push(el("span", { class: "course-sub" }, `${course.term} · `, first.section ? `${first.section} · ${meetingsText(first.meetings)}` : "Timetable not published",
      first.list === "alternate" ? " · alternate, not counted" : ""));
    const exams = state.exams.filter((exam) => exam.offering_id === course.id);
    const clashWhen = new Set(state.clashes.filter((item) => item.kind !== "class").map((item) => item.when));
    exams.forEach((exam) => lines.push(el("span", {
      class: `course-sub${clashWhen.has(`${exam.label}, ${exam.start}`) ? " bad" : ""}`,
      text: `${EXAM_WORD[exam.kind] || exam.kind} ${exam.label}, ${exam.start}`,
    })));
    const note = first.conflicts[0] || (clash ? { level: "class", text: clash[0].toUpperCase() + clash.slice(1) } : null);
    if (note) lines.push(el("span", { class: `course-sub ${note.level === "exam" ? "bad" : "warn"}`, text: note.text }));
  } else {
    const chosen = first && first.section ? ` · ${first.section} ${meetingsText(first.meetings)}` : "";
    lines.push(el("span", { class: "course-sub" },
      `${course.term} · ${course.ects} ECTS`, chosen,
      !first && course.sections.length === 1 ? el("span", { class: "time", text: ` · ${meetingsText(course.sections[0].meetings)}` }) : null,
      first ? "" : price,
      state.exam_warnings[course.id] ? el("span", { class: "bad", title: `Exam at the same time as ${state.exam_warnings[course.id].join(", ")}`, text: " · exam clash" }) : null,
      clash ? el("span", { class: "warn", text: ` · ${clash}` }) : null,
      twin ? el("span", { class: "warn", text: ` · in your plan in ${twin.term}` }) : null));
  }
  const exam = state.exams.find((item) => item.offering_id === course.id && item.kind === "exam");
  return el("article", {
    class: `course${open ? " open" : ""}${planned ? " in" : ""}`,
    onmouseenter: canHover ? () => previewCourse(course.id) : null,
    onmouseleave: canHover ? () => previewCourse(null) : null,
  },
    el("div", { class: "course-head" },
      el("button", {
        type: "button", class: "course-main", title: course.name, "aria-expanded": course.sections.length ? (open ? "true" : "false") : null, "data-key": `main-${course.id}`,
        onclick: () => (course.sections.length ? toggleExpanded(course) : go(course.id)),
      },
        el("span", { class: "course-name" }, el("span", { text: course.name }), course.sections.length ? el("span", { class: "chev", html: Lance.icons.down }) : null),
        ...lines),
      pickButton(course, planned)),
    open ? el("div", { class: "course-more" },
      course.kind === "mandatory" && !planned ? el("p", { class: "hint", text: "Pick the section Nova assigned you." }) : null,
      sectionTiles(course, state),
      el("div", { class: "course-foot" },
        el("span", { class: "faint", text: [exam ? `Exam ${exam.label}` : course.exam ? `Exam ${course.exam}` : null, course.lecturers].filter(Boolean).join(" · ") }),
        el("button", { type: "button", class: "text-btn", onclick: () => go(course.id) }, "Course details", el("span", { html: Lance.icons.next })))) : null);
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
      view.fits ? null : el("button", { type: "button", class: "link-btn", onclick: () => changeSetting({ semester: other }) }, `Look in ${other}`)));
    return;
  }
  const noProgramme = !state.plan.programme;
  const titles = { mandatory: "Mandatory", elective: "Electives", outside: noProgramme ? "All courses" : "Other programmes" };
  Object.keys(titles).forEach((kind) => {
    const courses = shown.filter((course) => course.kind === kind);
    if (!courses.length) return;
    const folded = !view.query && !noProgramme && view.closed[kind];
    list.append(el("button", {
      type: "button", class: "group", "aria-expanded": folded ? "false" : "true", html: Lance.icons.down,
      onclick: () => { view.closed[kind] = !view.closed[kind]; renderList(Lance.state); },
    }, el("span", { class: "group-name", text: titles[kind] }), el("span", { class: "count", text: String(courses.length) })));
    if (!folded) courses.forEach((course) => list.append(courseRow(course, state, false)));
  });
  list.scrollTop = scroll;
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
    box.replaceChildren(title, el("p", { class: "muted small" }, `This course runs in ${other}. `,
      el("button", { type: "button", class: "link-btn", onclick: async () => { await changeSetting({ semester: other }); renderSections(Lance.state); } }, `Plan for ${other.toLowerCase()}`)));
    return;
  }
  const entries = entriesOf(state, course.id);
  const remove = entries.length ? el("button", { type: "button", class: "text-btn small", style: "align-self:flex-start", onclick: () => removeCourse(course.id, course.name) }, "Remove from my plan") : null;
  if (!course.sections.length) {
    box.replaceChildren(title, el("p", { class: "small muted", text: "Nova has not published the timetable yet." }),
      remove || el("button", { type: "button", class: "btn small", style: "align-self:flex-start", onclick: () => Lance.send("/api/add", { offering_id: course.id }) }, "Add to my plan"));
    return;
  }
  box.replaceChildren(...[
    title,
    course.kind === "mandatory" && !entries.length ? el("p", { class: "hint", text: "Pick the section Nova assigned you." }) : null,
    state.exam_warnings[course.id] ? el("p", { class: "small bad", text: `Exam at the same time as ${state.exam_warnings[course.id].join(", ")}` }) : null,
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

function ghostBlocks(state) {
  const course = courseById(view.open || view.preview || view.expanded);
  if (!course || !TERMS_OF[view.half] || !TERMS_OF[view.half].includes(course.term)) return [];
  const chosen = entriesOf(state, course.id)[0];
  const blocks = [];
  course.sections.forEach((section) => {
    if (chosen && chosen.section_id === section.id) return;
    const clash = state.section_warnings[section.id];
    section.meetings.forEach((m) => {
      blocks.push({
        day: m.day, start: m.start, end: m.end,
        name: section.section, section: clash ? "clashes" : m.room, sectionId: section.id,
        class: `ghost${clash ? " bad" : ""}${view.hot === section.id ? " hot" : ""}`,
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
    if (!item.in_week || !TERMS_OF[view.half].includes(item.term)) return;
    item.meetings.forEach((m) => {
      blocks.push({
        day: m.day, start: m.start, end: m.end,
        name: item.name, section: item.section, room: m.room, sectionId: item.section_id,
        clashing: clashing.has(item.id),
        class: [(view.open || view.expanded) === item.offering_id && "open", view.fresh === item.section_id && "fresh", view.hot === item.section_id && "hot"].filter(Boolean).join(" "),
        title: `${item.name} ${item.section}, ${m.day} ${compact(m.start)}–${compact(m.end)}, ${m.room}`,
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
    el("button", { type: "button", class: "btn small", onclick: tryExample }, "Try an example"));
}

async function tryExample() {
  await Lance.send("/api/example", {});
  await loadCatalogue();
  Lance.update(Lance.state);
  Lance.toast("An example: a real Management plan from Fall 2026.", { label: "Start over", run: () => Lance.send("/api/start-over", {}) });
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
      state.plan.semester === "Fall" ? el("button", { type: "button", class: "link-btn", onclick: () => changeSetting({ semester: "Spring" }) }, "Plan for spring") : null);
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
    clash.weeks && !clash.weeks.includes(view.half) ? el("button", { type: "button", class: "btn small", onclick: () => { view.half = clash.weeks[0]; render(Lance.state); } }, `Show ${clash.weeks[0]}`) : null,
    other ? el("button", { type: "button", class: "btn small", title: `Switch ${target.name} to ${other.section}`, onclick: () => chooseSection(course, other) }, `Switch to ${other.section}`) : null,
    el("button", { type: "button", class: "btn small", title: `Remove ${target.name}`, onclick: () => removeCourse(target.offering_id, target.name) }, `Remove ${target.name}`),
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

function renderClashes(state) {
  const shown = state.clashes.slice(0, view.allClashes ? undefined : 2);
  const box = document.getElementById("clashes");
  box.replaceChildren(...shown.map((clash) => {
    const [before, pair, after] = clashText(clash);
    return el("div", { class: `clash-line ${clash.severity}` },
      el("div", { class: "grow" }, before, el("b", { text: pair }), after),
      ...clashActions(clash, state).filter(Boolean));
  }));
  if (state.clashes.length > 2 && !view.allClashes) {
    box.append(el("button", { type: "button", class: "link-btn small", style: "align-self:flex-start", onclick: () => { view.allClashes = true; renderClashes(Lance.state); } }, `${state.clashes.length - 2} more`));
  }
}

/* ---- the head of your plan: where you stand, whatever tab is open ---- */

function renderHead(state) {
  const points = state.plan.points;
  const left = points - state.reserved;
  const electives = state.items.some((item) => item.list === "primary");
  const above = state.ects.total > state.ects.recommended;
  const clashes = state.clashes.length;
  const exam = state.clashes.some((clash) => clash.kind === "exam");
  const figure = (value, label, cls, title, id) => el("span", { class: cls || null, title, id }, el("b", { class: "num", text: value }), ` ${label}`);
  document.getElementById("figures").replaceChildren(
    figure(String(state.ects.total), "ECTS", state.ects.over ? "bad" : above ? "warn" : state.items.length ? "" : "faint",
      `Nova recommends ${state.ects.recommended} ECTS, the maximum is ${state.ects.maximum}`, "ects"),
    points ? figure(String(left), "points left", left < 0 ? "bad" : "", `${state.reserved} of your ${points} points are held while bidding`)
      : el("span", { class: electives ? "warn" : "faint", text: "No points yet" }),
    clashes ? figure(String(clashes), clashes === 1 ? "clash" : "clashes", exam ? "bad" : "warn") : el("span", { class: "faint", text: "No clash" }));
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

function planRow(entries, state, classClash, examClash) {
  const first = entries[0];
  const alternate = first.list === "alternate";
  const backups = entries.slice(1).map((item) => item.section).filter(Boolean);
  const exam = state.exams.find((item) => item.offering_id === first.offering_id && item.kind === "exam");
  const clash = classClash.get(first.id);
  const examLevel = examClash.get(first.offering_id);
  const bid = entries.some((item) => item.bid !== null) ? Math.max(...entries.map((item) => item.bid || 0)) : null;
  const time = first.section ? meetingsText(first.meetings) : "Not published";
  return el("tr", { class: alternate ? "alt" : null },
    el("td", { class: "name" },
      el("button", { type: "button", class: "name-btn", title: first.name, onclick: () => go(first.offering_id) }, first.name),
      el("span", { class: "plan-sub", text: [first.term, first.section ? `${first.section} ${time}` : null, exam ? `Exam ${exam.label}` : null].filter(Boolean).join(" · ") })),
    el("td", { class: "opt" }, first.section || "–", backups.length ? el("span", { class: "faint", title: `If full: ${backups.join(", ")}`, text: ` +${backups.length}` }) : null),
    el("td", { class: `opt${clash ? " warn" : ""}`, title: clash ? `Clashes: ${clash}` : null }, el("span", { class: "faint", text: `${first.term} · ` }), time),
    el("td", { class: `r num${alternate ? " faint" : ""}`, title: alternate ? "The alternate list does not count" : null, text: alternate ? `(${first.ects})` : String(first.ects) }),
    el("td", { class: `opt${examLevel === "exam" ? " bad" : examLevel ? " warn" : ""}`, text: exam ? exam.label : "–" }),
    el("td", { class: `r num${first.list === "primary" && bid === null ? " warn" : alternate ? " faint" : ""}`, text: first.list === "mandatory" ? "–" : bid === null ? "No bid" : String(bid) }));
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
    body.append(el("tr", { class: "group" }, el("th", { colspan: 6, scope: "colgroup", text: title })));
    ids.forEach((id) => body.append(planRow(entriesOf(state, id), state, classClash, examClash)));
  });
  const counted = offerings.filter((id) => entriesOf(state, id)[0].list !== "alternate").length;
  const alternates = offerings.length - counted;
  const weekClashes = state.clashes.filter((clash) => clash.kind === "class").length;
  const examClashes = state.clashes.filter((clash) => clash.kind !== "class");
  const above = state.ects.total > state.ects.recommended;
  const many = (count, word) => `${count} ${word}${count === 1 ? "" : word.endsWith("sh") ? "es" : "s"}`;
  const head = (label, cls) => el("th", { scope: "col", class: cls || null, text: label });
  box.replaceChildren(
    el("table", { class: "plan-table" },
      el("thead", {}, el("tr", {}, head("Course"), head("Section", "opt"), head("Time", "opt"), head("ECTS", "r"), head("Exam", "opt"), head("Bid", "r"))),
      body,
      el("tfoot", {}, el("tr", {},
        el("th", { scope: "row" }, many(counted, "course"), alternates ? el("span", { class: "faint", text: ` + ${alternates} alternate` }) : null),
        el("td", { class: "opt" }),
        el("td", { class: `opt ${weekClashes ? "warn" : "faint"}`, text: weekClashes ? many(weekClashes, "clash") : "No clash" }),
        el("td", { class: `r num${state.ects.over ? " bad" : above ? " warn" : ""}`, title: `Nova recommends ${state.ects.recommended} ECTS, the maximum is ${state.ects.maximum}`, text: String(state.ects.total) }),
        el("td", { class: `opt ${examClashes.length ? (examClashes.some((clash) => clash.kind === "exam") ? "bad" : "warn") : "faint"}`, text: examClashes.length ? many(examClashes.length, "clash") : "No clash" }),
        el("td", { class: "r num", title: "Held while bidding" }, String(state.reserved), el("span", { class: "faint", text: " held" }))))),
    el("button", {
      type: "button", class: "text-btn plan-reset",
      onclick: () => { if (window.confirm(`Remove every ${state.plan.semester} course from your plan?`)) Lance.send("/api/start-over", {}); },
    }, "Start over"));
}

/* ---- wiring ---- */

function render(state) {
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
}

/* a menu is only as wide as what it shows, so that everything stays on one line (browsers make it as wide as its longest option) */
function fitToValue(select) {
  const context = fitToValue.canvas.getContext("2d");
  context.font = getComputedStyle(select).font;
  select.style.width = `${Math.ceil(context.measureText(select.selectedOptions[0].text).width) + 36}px`;
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
document.getElementById("set-programme").addEventListener("change", (event) => changeSetting({ programme: event.target.value }));
document.getElementById("set-semester").addEventListener("change", (event) => changeSetting({ semester: event.target.value }));
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (view.open) goBack();
  else if (view.expanded) { const id = view.expanded; view.expanded = null; render(Lance.state); const main = document.querySelector(`[data-key="main-${id}"]`); if (main) main.focus(); }
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
  if (planner.dataset.saved === "yes") Lance.toast("Thanks, your answers are in.");
  if (planner.dataset.saved === "error") Lance.toast("Please answer every question.");
  route();
})();
