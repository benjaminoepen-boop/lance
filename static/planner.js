/* The planner page: the course list on the left, the week on the right.
   Every rule lives on the server. This file only draws what logic.py answered. */
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"];
const FIRST_HOUR = 8, LAST_HOUR = 22;
const { el } = Lance;

const view = {
  catalogue: [],
  kind: "all",
  term: "all",
  query: "",
  fits: false,
  week: "T1",
  ghost: null,   /* the section under the mouse, previewed in the week */
};

const minutes = (clock) => { const [h, m] = clock.split(":"); return Number(h) * 60 + Number(m); };
const hourHeight = () => parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--hour")) || 44;
const compactTime = (clock) => clock.replace(/^0/, "");

/* ---- the course list ---- */

function meetingText(section) {
  return section.meetings.map((m) => `${m.day} ${compactTime(m.start)}`).join(" · ");
}

function sectionChip(course, section, state) {
  const on = state.items.some((item) => item.section_id === section.id);
  const warnings = state.section_warnings[section.id];
  const title = warnings ? `Clashes with ${warnings.join(", ")}` : `${section.delivery}, ${section.meetings.map((m) => `${m.day} ${m.start}–${m.end} ${m.room}`).join("; ")}`;
  return el("button", {
    type: "button",
    class: `chip sec${on ? " on" : ""}${warnings ? " warn" : ""}`,
    title,
    "aria-pressed": on ? "true" : "false",
    onclick: () => toggleSection(section.id, course),
    onmouseenter: () => showGhost(section, course),
    onmouseleave: hideGhost,
    onfocus: () => showGhost(section, course),
    onblur: hideGhost,
  }, `${section.section} ${meetingText(section)}`);
}

function courseCard(course, state) {
  const planned = state.items.some((item) => item.offering_id === course.id);
  const meta = el("div", { class: "course-meta" });
  if (course.lecturers) meta.append(el("span", { text: course.lecturers }));
  if (course.exam) meta.append(el("span", { text: `Exam ${course.exam}` }));
  if (course.cutoff_low !== null) {
    const low = Math.round(course.cutoff_low), high = Math.round(course.cutoff_high);
    meta.append(el("span", { class: "num", title: "Rank value that just won a seat in the last known round", text: low === high ? `Cut-off ${low}` : `Cut-off ${low}–${high}` }));
  }
  const row = el("div", { class: "section-row" });
  if (course.sections.length) {
    course.sections.forEach((section) => row.append(sectionChip(course, section, state)));
  } else {
    const entry = state.items.find((item) => item.offering_id === course.id);
    row.append(el("button", {
      type: "button",
      class: `chip${entry ? " on" : ""}`,
      "aria-pressed": entry ? "true" : "false",
      onclick: () => entry ? Lance.send("/api/remove", { item_id: entry.id }) : Lance.send("/api/add", { offering_id: course.id }),
    }, entry ? "In your plan" : "Add"));
    row.append(el("span", { class: "small faint", style: "align-self:center", text: "Timetable not published" }));
  }
  const warning = state.exam_warnings[course.id];
  return el("article", { class: `course${planned ? " in-plan" : ""}` },
    el("div", { class: "course-top" },
      el("a", { class: "course-name", href: `/course/${course.id}`, text: course.name }),
      el("span", { class: "tag num", text: `${course.term} · ${course.ects} ECTS` })),
    meta,
    warning ? el("div", { class: "small", style: "color:var(--red)", text: `Exam clash with ${warning.join(", ")}` }) : null,
    row);
}

function matches(course, state) {
  if (view.kind !== "all" && course.kind !== view.kind) return false;
  if (view.term !== "all" && course.term !== view.term) return false;
  if (view.query) {
    const haystack = `${course.name} ${course.code} ${course.lecturers}`.toLowerCase();
    if (!view.query.toLowerCase().split(/\s+/).every((word) => haystack.includes(word))) return false;
  }
  if (view.fits && !state.items.some((item) => item.offering_id === course.id)) {
    if (!course.sections.length) return false;
    if (state.exam_warnings[course.id]) return false;
    if (course.sections.every((section) => state.section_warnings[section.id])) return false;
  }
  return true;
}

function renderCourses(state) {
  const list = document.getElementById("courses");
  const scroll = list.scrollTop;
  list.replaceChildren();
  const shown = view.catalogue.filter((course) => matches(course, state));
  if (!shown.length) {
    list.append(el("p", { class: "empty-note", text: view.fits ? "Nothing else fits your week." : "No course matches." }));
    return;
  }
  let group = null;
  const titles = { mandatory: "Mandatory: pick the ones Nova assigned you", elective: "Electives", outside: "Outside your programme" };
  shown.forEach((course) => {
    if (course.kind !== group) {
      group = course.kind;
      list.append(el("h2", { class: "group-title", text: titles[group] }));
    }
    list.append(courseCard(course, state));
  });
  list.scrollTop = scroll;
}

function renderTermFilter() {
  const terms = [...new Set(view.catalogue.map((course) => course.term))].sort();
  const box = document.getElementById("filter-term");
  box.replaceChildren(...["all", ...terms].map((term) => el("button", {
    type: "button",
    class: `chip${view.term === term ? " on" : ""}`,
    onclick: () => { view.term = term; renderTermFilter(); if (Lance.state) renderCourses(Lance.state); },
  }, term === "all" ? "All terms" : term)));
}

async function toggleSection(sectionId, course) {
  const entry = Lance.state.items.find((item) => item.section_id === sectionId);
  hideGhost();
  if (entry) {
    await Lance.send("/api/remove", { item_id: entry.id });
  } else {
    /* a T2 course is planned on the T2 week: show it where it lands */
    if (course.term === "T1" || course.term === "T2") view.week = course.term;
    await Lance.send("/api/add", { section_id: sectionId });
  }
}

/* ---- the week ---- */

function termsInView() {
  /* S1 runs through both halves of the semester, T1 and T2 only through their own. */
  return view.week === "T1" ? ["S1", "T1"] : view.week === "T2" ? ["S1", "T2"] : view.week === "T3" ? ["S2", "T3"] : ["S2", "T4"];
}

function clashingItemIds(state) {
  const ids = new Set();
  state.clashes.forEach((clash) => {
    if (clash.weeks && clash.weeks.includes(view.week)) clash.items.forEach((id) => ids.add(id));
  });
  return ids;
}

/* side by side when blocks overlap: each block gets a column inside its group */
function layOut(blocks) {
  blocks.sort((a, b) => minutes(a.start) - minutes(b.start) || minutes(b.end) - minutes(a.end));
  const groups = [];
  blocks.forEach((block) => {
    const group = groups.find((g) => minutes(block.start) < g.end);
    if (group) {
      group.items.push(block);
      group.end = Math.max(group.end, minutes(block.end));
    } else {
      groups.push({ items: [block], end: minutes(block.end) });
    }
  });
  groups.forEach((group) => {
    const columns = [];
    group.items.forEach((block) => {
      let column = columns.findIndex((end) => end <= minutes(block.start));
      if (column === -1) { columns.push(0); column = columns.length - 1; }
      columns[column] = minutes(block.end);
      block.column = column;
    });
    group.items.forEach((block) => { block.columns = columns.length; });
  });
  return blocks;
}

function colourIndex(state) {
  const order = [...new Set(state.items.map((item) => item.offering_id))];
  return (offeringId) => order.indexOf(offeringId) % 10;
}

function blockNode(block, state, colourOf, height) {
  const top = (minutes(block.start) - FIRST_HOUR * 60) / 60 * height;
  const tall = (minutes(block.end) - minutes(block.start)) / 60 * height - 2;
  const width = 100 / block.columns;
  const style = `top:${top}px;height:${tall}px;left:calc(${block.column * width}% + 1px);width:calc(${width}% - 2px)`;
  if (block.ghost) {
    return el("div", { class: `block ghost${block.bad ? " bad" : ""}`, style },
      el("b", { text: block.name }), el("span", { text: block.detail }));
  }
  const link = el("a", {
    class: `block c${colourOf(block.offering_id)}${block.clash ? " clash" : ""}${block.alt ? " alt" : ""}`,
    style, href: `/course/${block.offering_id}`, title: `${block.name} ${block.section}, ${block.start}–${block.end}, ${block.room}`,
  }, el("b", { text: block.name }), el("span", { text: `${block.section} · ${block.room}` }));
  link.append(el("button", {
    type: "button", class: "x", title: "Remove", "aria-label": `Remove ${block.name} ${block.section}`,
    html: '<svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M2 2l8 8M10 2l-8 8"/></svg>',
    onclick: (event) => { event.preventDefault(); event.stopPropagation(); Lance.send("/api/remove", { item_id: block.item_id }); },
  }));
  return link;
}

function renderWeek(state) {
  const box = document.getElementById("week");
  const height = hourHeight();
  const clashing = clashingItemIds(state);
  const colourOf = colourIndex(state);
  box.replaceChildren(el("div", {}));
  DAYS.forEach((day) => box.append(el("div", { class: "week-head", text: day })));
  const hours = el("div", { class: "hours", style: `height:${(LAST_HOUR - FIRST_HOUR) * height}px` });
  for (let hour = FIRST_HOUR; hour < LAST_HOUR; hour += 1) {
    if (hour === FIRST_HOUR) continue;
    hours.append(el("span", { class: "hour-label", style: `top:${(hour - FIRST_HOUR) * height}px`, text: `${hour}:00` }));
  }
  box.append(hours);
  const visible = termsInView();
  const firstSection = {};
  state.items.forEach((item) => {
    if (!item.section_id) return;
    const key = `${item.list}-${item.offering_id}`;
    if (!(key in firstSection)) firstSection[key] = item.id;
  });
  DAYS.forEach((day) => {
    const blocks = [];
    state.items.forEach((item) => {
      if (!visible.includes(item.term)) return;
      item.meetings.filter((m) => m.day === day).forEach((m) => {
        blocks.push({
          item_id: item.id, offering_id: item.offering_id, name: item.name, section: item.section, start: m.start, end: m.end, room: m.room,
          clash: clashing.has(item.id), alt: firstSection[`${item.list}-${item.offering_id}`] !== item.id,
        });
      });
    });
    if (view.ghost && visible.includes(view.ghost.term)) {
      view.ghost.meetings.filter((m) => m.day === day).forEach((m) => {
        blocks.push({ ghost: true, bad: view.ghost.bad, name: view.ghost.name, detail: `${view.ghost.section} · ${m.room}`, start: m.start, end: m.end });
      });
    }
    const column = el("div", { class: "day", style: `height:${(LAST_HOUR - FIRST_HOUR) * height}px` });
    layOut(blocks).forEach((block) => column.append(blockNode(block, state, colourOf, height)));
    box.append(column);
  });
}

function renderWeekTabs(state) {
  const fall = state.plan.semester === "Fall";
  const tabs = fall ? [["T1", "T1 · until 12 Oct"], ["T2", "T2 · from 22 Oct"]] : [["T3", "T3 · 1 Feb – 16 Mar"], ["T4", "T4 · 5 Apr – 14 May"]];
  if (!tabs.some(([key]) => key === view.week)) view.week = tabs[0][0];
  document.getElementById("week-tabs").replaceChildren(...tabs.map(([key, label]) => el("button", {
    type: "button", class: view.week === key ? "on" : "",
    onclick: () => { view.week = key; renderWeekTabs(state); renderWeek(Lance.state); },
  }, label)));
}

function showGhost(section, course) {
  const already = Lance.state.items.some((item) => item.section_id === section.id);
  if (already) return;
  view.ghost = {
    name: course.name, section: section.section, term: course.term, meetings: section.meetings,
    bad: Boolean(Lance.state.section_warnings[section.id]),
  };
  /* T1 and T2 live on different weeks: bring the right one forward while looking at a course */
  if ((course.term === "T1" || course.term === "T2") && course.term !== view.week) {
    view.week = course.term;
    renderWeekTabs(Lance.state);
  }
  renderWeek(Lance.state);
}

function hideGhost() {
  if (!view.ghost) return;
  view.ghost = null;
  renderWeek(Lance.state);
}

/* ---- clashes and exams ---- */

function renderClashes(state) {
  const box = document.getElementById("clashes");
  box.replaceChildren(...state.clashes.map((clash) => {
    const detail = clash.kind === "class"
      ? `${clash.when}, ${clash.times === clash.of ? "every class" : `${clash.times} of ${clash.of} classes`}`
      : clash.kind === "exam"
        ? `${clash.when}. The platform blocks overlapping exams.`
        : `${clash.when}. The platform does not check midterms.`;
    return el("div", { class: `note-card ${clash.severity === "midterm" ? "midterm" : "clash"}` },
      el("div", {},
        el("div", { class: "strong", text: `${clash.first} × ${clash.second}` }),
        el("div", { class: "when", text: detail })));
  }));
}

function renderExams(state) {
  const card = document.getElementById("exams-card");
  const box = document.getElementById("exams");
  card.hidden = !state.exams.length;
  const clashing = new Set();
  state.clashes.filter((clash) => clash.kind !== "class").forEach((clash) => clashing.add(clash.when));
  box.replaceChildren(...state.exams.map((exam) => {
    const bad = clashing.has(`${exam.label}, ${exam.start}`);
    const kind = exam.kind === "exam" ? "" : ` · ${exam.kind}`;
    return el("div", { class: `exam${bad ? " bad" : ""}` },
      el("b", { text: exam.name }),
      el("span", { class: "small muted num", text: `${exam.label}, ${exam.start}${kind}` }));
  }));
}

function renderStart(state) {
  const card = document.getElementById("week-card");
  let start = card.querySelector(".start-note");
  const empty = !state.items.length && state.plan.semester === "Fall";
  if (empty && !start) {
    start = el("div", { class: "start-note", style: "display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-bottom:12px" },
      el("span", { class: "muted", text: "Pick a section on the left, or start from a real plan." }),
      el("button", { type: "button", class: "btn small", onclick: async () => { await Lance.send("/api/example", {}); document.dispatchEvent(new Event("lance:catalogue")); } }, "Load an example"));
    card.insertBefore(start, card.querySelector(".week"));
  }
  if (!empty && start) start.remove();
}

function renderSpringNote(state) {
  const card = document.getElementById("week-card");
  const spring = state.plan.semester === "Spring";
  card.querySelector(".week").hidden = spring;
  let note = card.querySelector(".spring-note");
  if (spring && !note) {
    note = el("p", { class: "spring-note muted", style: "padding:18px 4px", text: "Nova has not published the spring timetable yet. Courses, bids and past prices already work; the week fills in once the schedule is out." });
    card.append(note);
  }
  if (!spring && note) note.remove();
}

/* ---- wiring ---- */

async function loadCatalogue() {
  const response = await fetch("/api/catalogue");
  view.catalogue = await response.json();
  view.term = "all";
  renderTermFilter();
}

function render(state) {
  renderWeekTabs(state);
  renderCourses(state);
  renderStart(state);
  renderSpringNote(state);
  renderWeek(state);
  renderClashes(state);
  renderExams(state);
}

/* Filters can be touched while the page is still loading: the list then simply draws them on arrival. */
const redrawCourses = () => { if (Lance.state) renderCourses(Lance.state); };
document.getElementById("search").addEventListener("input", (event) => {
  view.query = event.target.value.trim();
  redrawCourses();
});
document.getElementById("fits").addEventListener("change", (event) => {
  view.fits = event.target.checked;
  redrawCourses();
});
document.getElementById("filter-kind").addEventListener("click", (event) => {
  const button = event.target.closest("[data-kind]");
  if (!button) return;
  view.kind = button.dataset.kind;
  document.querySelectorAll("#filter-kind .chip").forEach((chip) => chip.classList.toggle("on", chip === button));
  redrawCourses();
});
document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => {
    document.getElementById("planner").dataset.view = button.dataset.view;
    document.querySelectorAll("[data-view]").forEach((other) => other.classList.toggle("on", other === button));
    if (Lance.state) render(Lance.state);
  });
});
document.addEventListener("lance:catalogue", async () => {
  await loadCatalogue();
  render(Lance.state);
});

(async function start() {
  await loadCatalogue();
  Lance.onChange(render);
  await Lance.load();
  /* the list sits next to the week and scrolls on its own; its height depends on the head card */
  const head = document.getElementById("head").offsetHeight;
  document.documentElement.style.setProperty("--head", `${head}px`);
})();
