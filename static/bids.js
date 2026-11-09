/* Step 2: how much for each course. One row per course, its answer next to the number, the rest folded away.
   The server does all the arithmetic in logic.py; this file draws what it answers. */
const { el } = Lance;
const QUICK = [["exact", "Just enough", "Exactly what the last seat cost last round"], ["plus10", "+10 %", "Last round's price plus 10 %"], ["plus25", "+25 %", "Last round's price plus 25 %"]];
const view = { catalogue: [], open: null, adding: null, picking: false, query: "", menu: null };
const compact = (time) => time.replace(/^0/, "");
const whole = (value) => String(Math.round(value * 10) / 10);
const meetingsText = (meetings) => meetings.map((m) => `${m.day} ${compact(m.start)}`).join(" · ");
const courseOf = (id) => view.catalogue.find((course) => course.id === id);
const highest = (rows) => (rows.some((item) => item.bid !== null) ? Math.max(...rows.map((item) => item.bid || 0)) : null);

/* ---- saving: a bid typed just before leaving the page still arrives ---- */

let pending = null;
function saveLater(body) {
  clearTimeout(pending && pending.timer);
  pending = { body, timer: setTimeout(() => { pending = null; Lance.send("/api/bid", body); }, 350) };
}
window.addEventListener("pagehide", () => {
  if (pending) fetch("/api/bid", { method: "POST", keepalive: true, headers: { "Content-Type": "application/json" }, body: JSON.stringify(pending.body) });
});

/* ---- the summary: points in, points held, and what last round would have charged ---- */

function figure(label, value, cls, id) {
  return el("div", { class: `sum-row${cls ? ` ${cls}` : ""}` }, el("span", { text: label }), el("b", { class: "num", id, text: value }));
}

function renderSummary(state) {
  const box = document.getElementById("summary");
  let field = document.getElementById("set-points");
  if (!field) {
    let timer = null;
    field = el("input", {
      class: "field num", id: "set-points", type: "number", min: 0, max: 2000, step: 1, inputmode: "numeric", placeholder: "?",
      "aria-label": "Your points, the Balance on Nova's platform",
      oninput: (event) => { clearTimeout(timer); timer = setTimeout(() => Lance.send("/api/settings", { points: event.target.value || 0 }), 350); },
      onchange: (event) => { clearTimeout(timer); Lance.send("/api/settings", { points: event.target.value || 0 }); },
    });
    box.append(
      el("label", { class: "sum-points" }, el("span", {}, "Your points", el("small", { text: "Balance on Nova's platform" })), field),
      el("div", { id: "sum-body" }));
  }
  const points = state.plan.points;
  if (field !== document.activeElement) field.value = points || "";
  const left = points - state.reserved;
  const f = state.forecast;
  const seats = f.rows.filter((row) => row.status === "seat").length;
  const unknown = f.rows.filter((row) => row.status === "no data").length;
  const body = [
    figure("Held while bidding", String(state.reserved)),
    figure("Left now", points ? String(left) : "–", points && left < 0 ? "bad" : "", "points-left"),
  ];
  if (!points) {
    body.push(el("p", { class: "sum-note warn", text: "Enter your points first." }));
  } else if (left < 0) {
    body.push(el("p", { class: "sum-note bad", text: `Your bids hold ${state.reserved} points, you have ${points}.` }));
  } else if (seats) {
    body.push(el("h3", { class: "sum-head", text: unknown ? "If last round repeats, for the courses with a price" : "If last round repeats" }),
      figure("You pay about", whole(f.expected)),
      unknown ? null : figure("Back afterwards", whole(f.left)),
      el("a", { class: "quiet-link small", href: Lance.pages.rules, text: "Why less than you bid?" }));
  }
  if (state.items.some((item) => item.analysis && item.analysis.known)) {
    body.push(el("label", { class: "check small sum-bonus", title: "Part of the students with 45 or more ECTS passed rank with their bid × 1.1. It shows on your rank list. Not sure: leave it off." },
      el("input", { type: "checkbox", checked: state.plan.has_bonus ? true : null, onchange: (event) => Lance.send("/api/settings", { has_bonus: event.target.checked }) }),
      el("span", { text: "My rank list shows bid × 1.1" })));
  }
  const known = state.known_prices;
  body.push(el("p", { class: "sum-foot" }, "Only a plan: nothing goes to Nova from here.",
    known ? ` Past prices for ${known.sections} of ${known.total} sections. ` : " ", el("a", { class: "quiet-link", href: Lance.pages.share, text: "Share yours" })));
  document.getElementById("sum-body").replaceChildren(...body.filter(Boolean));
}

/* ---- the answer for one course, short enough for a column ---- */

function statusOf(rows, state) {
  const first = rows[0];
  const a = first.analysis;
  const bid = highest(rows);
  if (bid === null) return { cls: "warn", text: "No bid", title: "Nova reads an empty field as not interested. 0 is a bid." };
  if (!a.known) {
    const known = state.known_prices;
    return { cls: "faint", text: "No past price", title: known ? `Known sections went for ${known.low} to ${known.high}.` : null };
  }
  if (!a.exact || !first.section) {
    const high = a.cutoff_high !== undefined && a.cutoff_high !== null && a.cutoff_high !== a.cutoff ? `–${Math.ceil(a.cutoff_high)}` : "";
    return { cls: "muted", text: `${a.round}: ${Math.ceil(a.cutoff)}${high}`, title: "From another term: only a rough hint." };
  }
  if (first.list === "alternate") {
    if (a.cutoff === null || a.cutoff === undefined) return { cls: a.seats ? "muted" : "warn", text: `${a.seats} seats for ${a.bids} bids`, title: a.seats ? "Last round on the alternate list" : "Last round no seat was left for the alternate list." };
    return { cls: "muted", text: `From ${Math.ceil(a.cutoff)} · pays its bid`, title: "If used, an alternate pays its bid, at most what is left." };
  }
  const outcome = state.forecast.rows.find((row) => row.offering_id === first.offering_id);
  if (outcome && outcome.status === "seat") {
    const where = outcome.section !== first.section ? ` in ${outcome.section}` : "";
    return { cls: "", text: `Enough${where} · pays ~${whole(outcome.price)}`, title: `(your bid + ${Math.min(a.lowest_in_course, bid)}, the lowest winning bid in the course) / 2` };
  }
  const lows = rows.map((item) => item.analysis.cutoff).filter((value) => value !== null && value !== undefined);
  return { cls: "bad", text: `Too low · from ${Math.ceil(Math.min(...lows))}`, title: "Last round's price for a seat" };
}

/* a course that clashes in the week, or whose exam Nova would block, says so in its row */
function notesOf(rows, state) {
  const first = rows[0];
  const week = state.clashes.filter((clash) => clash.offerings.includes(first.offering_id) && (first.in_week || clash.kind !== "class")).map((clash) => {
    const other = clash.offerings.find((id) => id !== first.offering_id);
    const name = (state.items.find((item) => item.offering_id === other) || {}).name || "";
    if (clash.kind === "exam") return { level: "exam", text: `Exam at the same time as ${name}. Nova will not enroll you in both.` };
    if (clash.kind === "midterm") return { level: "midterm", text: `Midterm clash with ${name}. Nova does not check this.` };
    return { level: "class", text: `Clashes with ${name}. You can't attend both.` };
  });
  return first.conflicts.concat(week);
}

/* ---- the picture of last round: one bar per 20 points, blue where the bid won a seat ---- */

function histogram(analysis, bid) {
  const bars = analysis.histogram || [];
  if (!bars.length) return null;
  const rank = analysis.rank_value;
  const top = Math.max(...bars.map((bar) => bar.to), rank || 0, 60);
  const tallest = Math.max(...bars.map((bar) => bar.bids));
  const width = 240, height = 36, floor = 34;
  const x = (value) => (value / top) * width;
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("class", "spark");
  svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `Last round: ${analysis.bids} bids, ${analysis.seats} seats, cut-off ${analysis.cutoff}`);
  const rect = (x0, y, w, h, fill) => {
    const node = document.createElementNS(ns, "rect");
    node.setAttribute("x", x0); node.setAttribute("y", y); node.setAttribute("width", Math.max(w, 0.5)); node.setAttribute("height", Math.max(h, 0));
    node.setAttribute("fill", fill);
    svg.append(node);
  };
  bars.forEach((bar) => {
    const left = x(bar.from) + 0.5, w = x(bar.to) - x(bar.from) - 1;
    const all = (bar.bids / tallest) * (floor - 2);
    const won = (bar.allocated / tallest) * (floor - 2);
    rect(left, floor - all, w, all, "#d6d6dc");
    if (won) rect(left, floor - won, w, won, "#7c97ff");
  });
  if (analysis.cutoff !== null && analysis.cutoff !== undefined) rect(x(analysis.cutoff) - 0.5, 0, 1, floor, "#1d1d1f");
  if (rank !== undefined && bid !== null) rect(x(rank) - 1, 0, 2, height, analysis.would_win ? "#17762f" : "#c4000f");
  rect(0, floor, width, 1, "#d6d6dc");
  return svg;
}

/* ---- folded open: amounts to take, every section with its own numbers, other sections to try ---- */

function sectionLine(item, rows, state) {
  const a = item.analysis;
  const backup = rows.indexOf(item) > 0;
  const numbers = a.known ? [a.cutoff !== null && a.cutoff !== undefined ? `seat from ${Math.ceil(a.cutoff)}` : "no seat went out", a.seats !== null ? `${a.seats} seats` : null, a.bids !== null ? `${a.bids} bids` : null].filter(Boolean).join(" · ") : "no past price";
  const warning = item.conflicts.length ? item.conflicts.map((note) => note.text).join(" ") : null;
  return el("div", { class: "sec-line" },
    el("b", { text: item.section || "Any" }),
    el("span", { class: "muted num", text: meetingsText(item.meetings) || "no timetable yet" }),
    rows.length > 1 ? el("input", {
      class: "field num", type: "number", min: 0, max: state.plan.points, step: 1, inputmode: "numeric", placeholder: "no bid",
      value: item.bid === null ? "" : item.bid, "data-item": item.id, "aria-label": `Bid on ${item.name} ${item.section || ""} only`,
      oninput: (event) => saveLater({ item_id: item.id, bid: event.target.value }),
    }) : null,
    el("span", { class: `sec-numbers num${warning ? " warn" : ""}`, title: warning, text: warning ? `clashes · ${numbers}` : numbers }),
    histogram(a, item.bid),
    backup ? el("button", { type: "button", class: "x", title: `Do not try ${item.section}`, "aria-label": `Do not try ${item.section}`, html: Lance.icons.close, onclick: () => Lance.send("/api/remove", { item_id: item.id }) }) : el("span"));
}

function details(rows, state, listName) {
  const first = rows[0];
  const a = first.analysis;
  const course = courseOf(first.offering_id);
  const free = course && first.section ? course.sections.filter((section) => !rows.some((row) => row.section_id === section.id)) : [];
  const quick = listName === "primary" && a.exact && first.section ? QUICK.filter(([key]) => a.suggestions[key] !== null && a.suggestions[key] !== undefined) : [];
  const notes = notesOf(rows, state);
  return el("div", { class: "bid-details" },
    quick.length ? el("div", { class: "quick" }, el("span", { class: "faint", text: "Take" }), ...quick.map(([key, label, hint]) => el("button", {
      type: "button", title: hint, onclick: () => Lance.send("/api/bid", { offering_id: first.offering_id, bid: Math.min(a.suggestions[key], state.plan.points) }),
    }, `${label} ${a.suggestions[key]}`))) : null,
    ...notes.map((note) => el("p", { class: `note-line ${note.level === "exam" ? "bad" : "warn"}`, text: note.text })),
    el("div", { class: "sec-lines" },
      rows.length > 1 || free.length ? el("p", { class: "faint small", text: listName === "primary" ? "Nova tries the sections in this order:" : "Sections:" }) : null,
      ...rows.map((item) => sectionLine(item, rows, state))),
    free.length && listName === "primary" ? el("div", { class: "try-more" }, el("span", { class: "faint", text: "If full, also try" }), ...free.map((section) => {
      const warning = state.section_warnings[section.id];
      return el("button", {
        type: "button", class: `backup-add${warning ? " warn" : ""}`, title: warning ? `Clashes with ${warning.join(", ")}` : null,
        onclick: () => Lance.send("/api/add", { section_id: section.id }),
      }, `${section.section} ${meetingsText(section.meetings)}`);
    })) : null,
    listName === "primary" && a.exact && a.lowest_in_course !== null && a.lowest_in_course !== undefined
      ? el("p", { class: "faint small", text: `You pay the middle of your bid and ${a.lowest_in_course}, the lowest winning bid in the whole course. No seat, no charge.` }) : null);
}

/* ---- one course ---- */

function menu(first, listName, index, total) {
  const button = (label, action, disabled) => el("button", { type: "button", disabled: disabled ? true : null, onclick: action }, label);
  const other = listName === "primary" ? "alternate" : "primary";
  return el("details", {
    class: "menu", open: view.menu === first.offering_id ? true : null,
    ontoggle: (event) => {
      if (event.target.open) view.menu = first.offering_id;
      else if (view.menu === first.offering_id) view.menu = null;
    },
  },
    el("summary", { "aria-label": `More for ${first.name}`, title: "More", html: Lance.icons.dots }),
    el("div", { class: "menu-items" },
      listName === "primary" ? button("Move up", () => Lance.send("/api/move", { item_id: first.id, direction: "up" }), index === 0) : null,
      listName === "primary" ? button("Move down", () => Lance.send("/api/move", { item_id: first.id, direction: "down" }), index === total - 1) : null,
      button(`To ${other} list`, () => Lance.send("/api/move", { item_id: first.id, list: other })),
      button("Course details", () => { location.href = Lance.courseHref(first.offering_id); }),
      button("Remove", async () => {
        const answer = await Lance.send("/api/remove", { offering_id: first.offering_id });
        if (!answer.error) Lance.toast(`Removed ${first.name}`, { label: "Undo", run: () => Lance.send("/api/restore", { rows: answer.removed }) });
      })));
}

function bidRow(rows, state, listName, index, total) {
  const first = rows[0];
  const bid = highest(rows);
  const status = statusOf(rows, state);
  const notes = notesOf(rows, state);
  const open = view.open === first.offering_id;
  const differs = new Set(rows.map((item) => item.bid)).size > 1;
  const backups = rows.slice(1).map((item) => item.section);
  const sub = [`${first.term} · ${first.ects} ECTS`, first.section ? `${first.section} ${meetingsText(first.meetings)}` : "no timetable yet", backups.length ? `if full ${backups.join(", ")}` : null].filter(Boolean).join(" · ");
  return el("article", { class: `bid-row${open ? " open" : ""}` },
    el("div", { class: "bid-head" },
      el("button", {
        type: "button", class: "bid-name", "aria-expanded": open ? "true" : "false", title: "Details",
        onclick: () => { view.open = open ? null : first.offering_id; render(Lance.state); },
      },
        el("span", { class: "course-name" }, el("span", { text: first.name }), el("span", { class: "chev", html: Lance.icons.down })),
        el("span", { class: "course-sub", text: sub }),
        notes.length ? el("span", { class: `course-sub ${notes.some((note) => note.level === "exam") ? "bad" : "warn"}`, text: notes[0].text }) : null),
      el("input", {
        class: "field num bid-input", type: "number", min: 0, max: state.plan.points, step: 1, inputmode: "numeric", placeholder: "no bid",
        value: bid === null ? "" : bid, "data-course": first.offering_id, "aria-label": `Bid on ${first.name}`,
        oninput: (event) => saveLater({ offering_id: first.offering_id, bid: event.target.value }),
      }),
      el("span", { class: `bid-status ${status.cls}`, title: status.title || null, text: differs ? `${status.text} · bids differ` : status.text }),
      menu(first, listName, index, total)),
    open ? details(rows, state, listName) : null);
}

/* ---- the alternate list has its own way in ---- */

function alternatePicker(state) {
  const box = el("div", { class: "picker" });
  if (!view.picking) {
    box.append(el("button", { type: "button", class: "btn small", style: "align-self:flex-start", onclick: () => { view.picking = true; render(Lance.state); } }, "+ Alternate course"));
    return box;
  }
  const results = el("div", { class: "picker" });
  const draw = () => {
    const words = view.query.toLowerCase().split(/\s+/).filter(Boolean);
    const planned = new Set(state.items.map((item) => item.offering_id));
    const hits = view.catalogue.filter((course) => course.kind !== "mandatory" && !planned.has(course.id))
      .filter((course) => words.every((word) => `${course.name} ${course.code} ${course.lecturers}`.toLowerCase().includes(word))).slice(0, 6);
    results.replaceChildren(...hits.map((course) => {
      const clash = course.sections.length > 0 && course.sections.every((section) => state.section_warnings[section.id]);
      return el("article", { class: "course" },
        el("div", { class: "course-head" },
          el("div", { class: "course-main" }, el("span", { class: "course-name", text: course.name }),
            el("span", { class: "course-sub" }, `${course.term} · ${course.ects} ECTS`, clash ? el("span", { class: "warn", text: " · clashes" }) : null)),
          el("button", {
            type: "button", class: "pick", "aria-pressed": "false", "aria-label": `Add ${course.name} to the alternate list`, title: "Add", html: Lance.icons.plus,
            onclick: () => { view.picking = false; view.query = ""; Lance.send("/api/add", { offering_id: course.id, list: "alternate" }); },
          })));
    }));
  };
  draw();
  const field = el("input", {
    class: "field", type: "search", placeholder: "Search all courses", "aria-label": "Search a course for the alternate list", value: view.query, "data-picker": "1",
    oninput: (event) => { view.query = event.target.value; draw(); },
  });
  box.append(field, results);
  setTimeout(() => { field.focus(); box.scrollIntoView({ block: "nearest" }); }, 0);
  return box;
}

function listBlock(title, hint, listName, state) {
  const items = state.items.filter((item) => item.list === listName).sort((a, b) => a.position - b.position);
  const order = [...new Set(items.map((item) => item.offering_id))];
  const block = el("section", { class: "bid-list" },
    el("div", { class: "list-title" }, el("h2", { text: title }), el("span", { text: hint })),
    order.length ? el("div", { class: "cols", "aria-hidden": "true" }, el("span"), el("span", { text: "Your bid" }), el("span", { text: "Last round" }), el("span")) : null);
  order.forEach((offeringId, index) => block.append(bidRow(items.filter((item) => item.offering_id === offeringId), state, listName, index, order.length)));
  return block;
}

function render(state) {
  const focused = document.activeElement;
  const focusKey = focused && focused.dataset ? (focused.dataset.course ? `[data-course="${focused.dataset.course}"]` : focused.dataset.item ? `[data-item="${focused.dataset.item}"]` : focused.dataset.picker ? "[data-picker]" : null) : null;
  const box = document.getElementById("bid-lists");
  renderSummary(state);
  const hasElectives = state.items.some((item) => item.list !== "mandatory");
  document.getElementById("next").classList.toggle("primary", hasElectives);
  if (!hasElectives) {
    box.replaceChildren(el("section", { class: "card muted", style: "text-align:center;padding:36px 16px" },
      el("p", { text: state.items.length ? "Mandatory courses need no bid. Add an elective to bid on." : "Nothing to bid on yet." }),
      el("a", { class: "btn small", style: "margin-top:10px", href: Lance.pages.courses, text: "Pick courses" })));
    return;
  }
  const mandatory = new Set(state.items.filter((item) => item.list === "mandatory").map((item) => item.offering_id)).size;
  const alternate = listBlock("Alternate list", "Tried if a primary course gets no seat. Holds no points.", "alternate", state);
  alternate.append(alternatePicker(state));
  box.replaceChildren(...[
    listBlock("Primary list", "Higher up goes first", "primary", state),
    alternate,
    mandatory ? el("p", { class: "small faint", text: `${mandatory} mandatory ${mandatory === 1 ? "course needs" : "courses need"} no bid.` }) : null,
  ].filter(Boolean));
  if (focusKey) {
    const again = box.querySelector(`input${focusKey}`);
    if (again) {
      const end = focused.value.length;
      again.focus();
      if (again.type === "number") { again.type = "text"; again.setSelectionRange(end, end); again.type = "number"; }
    }
  }
}

/* a menu closes when the click lands anywhere else, or with Esc */
document.addEventListener("click", (event) => {
  document.querySelectorAll("details.menu[open]").forEach((menuNode) => { if (!menuNode.contains(event.target)) menuNode.open = false; });
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") document.querySelectorAll("details.menu[open]").forEach((menuNode) => { menuNode.open = false; });
});

(async function start() {
  const response = await fetch("/api/catalogue");
  view.catalogue = await response.json();
  Lance.onChange(render);
  await Lance.load();
})();
