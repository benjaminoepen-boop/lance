/* Step 2: how much for each course. The server does all the arithmetic in logic.py; this file draws what it answers. */
const { el } = Lance;
const QUICK = [["exact", "Just enough", "Exactly what the last seat cost last round"], ["plus10", "+10 %", "Last round's price plus 10 %"], ["plus25", "+25 %", "Last round's price plus 25 %"]];
const view = { catalogue: [], open: new Set(), adding: null, picking: false, query: "", menu: null };
const compact = (time) => time.replace(/^0/, "");
const whole = (value) => String(Math.round(value * 10) / 10);
const meetingsText = (meetings) => meetings.map((m) => `${m.day} ${compact(m.start)}`).join(" · ");
const courseOf = (id) => view.catalogue.find((course) => course.id === id);

/* ---- the numbers on top ---- */

function renderBudget(state) {
  const box = document.getElementById("budget");
  let field = document.getElementById("set-points");
  if (!field) {
    let timer = null;
    field = el("input", {
      class: "field", id: "set-points", type: "number", min: 0, max: 2000, step: 1, inputmode: "numeric", placeholder: "?", "aria-label": "Your points, the Balance on Nova's platform",
      oninput: (event) => {
        clearTimeout(timer);
        timer = setTimeout(() => Lance.send("/api/settings", { points: event.target.value || 0 }), 350);
      },
      onchange: (event) => {
        clearTimeout(timer);
        Lance.send("/api/settings", { points: event.target.value || 0 });
      },
    });
    box.append(
      el("label", { class: "budget-figure", title: "Your Balance on Nova's platform" }, field, el("span", { text: "Your points" })),
      el("div", { class: "budget-figure" }, el("b", { id: "points-left" }), el("span", { text: "Left" })),
      el("div", { class: "budget-note", id: "budget-note" }));
  }
  const points = state.plan.points;
  if (field !== document.activeElement) field.value = points || "";
  const left = points - state.reserved;
  const leftNode = document.getElementById("points-left");
  leftNode.textContent = points ? String(left) : "–";
  leftNode.classList.toggle("bad", Boolean(points) && left < 0);
  const note = document.getElementById("budget-note");
  note.replaceChildren();
  const f = state.forecast;
  const known = f.rows.filter((row) => row.status === "seat" || row.status === "no seat");
  const unknown = f.rows.filter((row) => row.status === "no data").length;
  if (!points) {
    note.append("Enter your points: the Balance on Nova's platform.");
  } else if (left < 0) {
    note.append(el("span", { class: "bad", text: `Your bids hold ${state.reserved} points, you have ${points}.` }));
  } else if (f.rows.some((row) => row.status === "seat")) {
    if (unknown) {
      note.append(`If last round repeats: about ${whole(f.expected)} for the ${known.length === 1 ? "course" : `${known.length} courses`} we know. ${unknown} without a past price.`);
    } else {
      note.append(`If last round repeats: you pay ${whole(f.expected)}, and ${whole(f.left)} come back for the alternate list and add/drop. `);
      note.append(el("a", { href: Lance.pages.rules, text: "Why less?" }));
    }
  }
  if (state.items.some((item) => item.analysis && item.analysis.known)) {
    const open = document.getElementById("rank-bonus");
    note.append(el("details", { class: "more", id: "rank-bonus", open: open && open.open ? true : null },
      el("summary", { text: state.plan.has_bonus ? "Rank bonus: on" : "Rank bonus?" }),
      el("label", { class: "check small", style: "text-align:left;display:flex;align-items:flex-start" },
        el("input", { type: "checkbox", checked: state.plan.has_bonus ? true : null, onchange: (event) => Lance.send("/api/settings", { has_bonus: event.target.checked }) }),
        el("span", { text: "My rank list shows my bid × 1.1. Part of the students with 45 or more ECTS passed rank like this. Not sure: leave it off." }))));
  }
}

/* ---- the answer for one course ---- */

function answerOf(rows, state) {
  const first = rows[0];
  const a = first.analysis;
  const bid = rows.some((item) => item.bid !== null) ? Math.max(...rows.map((item) => item.bid || 0)) : null;
  const span = (cls, text, title) => el("span", { class: cls, title, text });
  const known = state.known_prices;
  const anchor = known ? `No past price yet. Known sections went for ${known.low} to ${known.high}.` : "No past price yet.";
  if (bid === null) {
    const price = a.known && a.cutoff !== null && a.cutoff !== undefined && a.exact ? ` Last round: seat from ${Math.ceil(a.cutoff)}.` : a.known ? "" : ` ${anchor}`;
    return [span("warn", "No bid: Nova reads this as not interested."), price];
  }
  if (!a.known) return [span("faint", anchor)];
  if (!a.exact || !first.section) {
    /* the price comes from another term or does not know the section: only a rough hint, so no verdict */
    const high = a.cutoff_high !== undefined && a.cutoff_high !== null && a.cutoff_high !== a.cutoff ? ` to ${Math.ceil(a.cutoff_high)}` : "";
    return [span("muted", `${a.round}: seats from ${Math.ceil(a.cutoff)}${high}. No price for this term yet.`)];
  }
  if (first.list === "alternate") {
    if (a.cutoff === null || a.cutoff === undefined) return [span("muted", `Last round: ${a.seats} seats for ${a.bids} bids on the alternate list.`)];
    return [span("muted", `Last round: seats from ${Math.ceil(a.cutoff)}.`)];
  }
  const outcome = state.forecast.rows.find((row) => row.offering_id === first.offering_id);
  if (outcome && outcome.status === "seat") {
    const formula = `(your bid + ${Math.min(a.lowest_in_course, bid)}, the lowest winning bid in the course) / 2`;
    if (outcome.section !== first.section) return [span("", `Not enough for ${first.section}, enough for ${outcome.section} last round · you'd pay about ${whole(outcome.price)}`, formula)];
    return [span("", `Enough last round · you'd pay about ${whole(outcome.price)}`, formula)];
  }
  const lows = rows.map((item) => item.analysis.cutoff).filter((value) => value !== null && value !== undefined);
  return [span("bad", `Too low last round · seat from ${Math.ceil(Math.min(...lows))}`)];
}

/* a course that clashes in the week says so here too: bidding on it would be wasted */
function weekNotes(first, state) {
  return state.clashes.filter((clash) => clash.offerings.includes(first.offering_id) && (first.in_week || clash.kind !== "class")).map((clash) => {
    const other = clash.offerings.find((id) => id !== first.offering_id);
    const name = (state.items.find((item) => item.offering_id === other) || {}).name || "";
    if (clash.kind === "exam") return { level: "exam", text: `Exam at the same time as ${name}. Nova will not enroll you in both.` };
    if (clash.kind === "midterm") return { level: "midterm", text: `Midterm clash with ${name}. Nova does not check this.` };
    return { level: "class", text: `Clashes with ${name}. You can't attend both.` };
  });
}

let pending = null;
function saveLater(body) {
  clearTimeout(pending && pending.timer);
  pending = { body, timer: setTimeout(() => { pending = null; Lance.send("/api/bid", body); }, 350) };
}
const courseBid = (offeringId, value) => saveLater({ offering_id: offeringId, bid: value });
const sectionBid = (itemId, value) => saveLater({ item_id: itemId, bid: value });
/* a bid typed just before leaving the page still arrives */
window.addEventListener("pagehide", () => {
  if (pending) fetch("/api/bid", { method: "POST", keepalive: true, headers: { "Content-Type": "application/json" }, body: JSON.stringify(pending.body) });
});

/* ---- the picture of last round: one bar per 20 points, blue where the bid won a seat ---- */

function histogram(analysis, bid) {
  const bars = analysis.histogram || [];
  if (!bars.length) return null;
  const rank = analysis.rank_value;
  const top = Math.max(...bars.map((bar) => bar.to), rank || 0, 60);
  const tallest = Math.max(...bars.map((bar) => bar.bids));
  const width = 240, height = 44, floor = 42;
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
    rect(left, floor - all, w, all, "#d2d2d7");
    if (won) rect(left, floor - won, w, won, "#6d8bff");
  });
  if (analysis.cutoff !== null && analysis.cutoff !== undefined) rect(x(analysis.cutoff) - 0.5, 0, 1, floor, "#1d1d1f");
  if (rank !== undefined && bid !== null) rect(x(rank) - 1, 0, 2, height, analysis.would_win ? "#17762f" : "#c4000f");
  rect(0, floor, width, 1, "#d2d2d7");
  return svg;
}

/* ---- details: each section with its own numbers, and its own bid if someone wants that ---- */

function detailRow(item, rows, plan) {
  const a = item.analysis;
  const numbers = a.known ? [a.cutoff !== null && a.cutoff !== undefined ? `Seat from ${Math.ceil(a.cutoff)}` : null, a.seats !== null ? `${a.seats} seats` : null, a.bids !== null ? `${a.bids} bids` : null, a.top !== null ? `highest ${a.top}` : null, a.round].filter(Boolean).join(" · ") : "No past price yet";
  return el("div", { class: "detail-row" },
    el("div", { class: "detail-head" },
      el("b", { class: "strong", text: item.section || "Any" }),
      el("span", { class: "muted num", text: meetingsText(item.meetings) }),
      rows.length > 1 ? el("input", {
        class: "field num", type: "number", min: 0, max: plan.points, step: 1, inputmode: "numeric", placeholder: "no bid",
        value: item.bid === null ? "" : item.bid, "data-item": item.id, "aria-label": `Bid on ${item.name} ${item.section || ""} only`,
        oninput: (event) => sectionBid(item.id, event.target.value),
      }) : null,
      el("span", { class: "faint num", text: numbers })),
    histogram(a, item.bid),
    a.lowest_in_course !== null && a.lowest_in_course !== undefined && a.exact && item.list === "primary" ? el("div", { class: "faint", style: "margin-top:4px", text: `You pay the middle of your bid and ${a.lowest_in_course}, the lowest winning bid in the whole course.` }) : null);
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
      button("Remove", async () => {
        const answer = await Lance.send("/api/remove", { offering_id: first.offering_id });
        if (!answer.error) Lance.toast(`Removed ${first.name}`, { label: "Undo", run: () => Lance.send("/api/restore", { rows: answer.removed }) });
      })));
}

/* "If TXB is full": other sections of the same course. Nova tries them in this order. */
function otherSections(rows, state) {
  const first = rows[0];
  const course = courseOf(first.offering_id);
  if (!course || !first.section) return [];
  const backups = rows.slice(1);
  const free = course.sections.filter((section) => !rows.some((row) => row.section_id === section.id));
  if (!backups.length && !free.length) return [];
  const nodes = [el("span", { text: `If ${first.section} is full:` })];
  backups.forEach((item) => {
    const tooLow = item.bid !== null && item.analysis.would_win === false;
    const warning = item.conflicts.length ? item.conflicts.map((note) => note.text).join(" ") : tooLow ? `Your bid was below the ${Math.ceil(item.analysis.cutoff)} this section took last round.` : null;
    nodes.push(el("span", { class: `tryalso${warning ? " warn" : ""}`, title: warning },
      `${item.section}${item.conflicts.length ? " · clashes" : tooLow ? " · too low" : ""}`,
      el("button", { type: "button", class: "x", title: `Do not try ${item.section}`, "aria-label": `Do not try ${item.section}`, html: Lance.icons.close, onclick: () => Lance.send("/api/remove", { item_id: item.id }) })));
  });
  if (view.adding === first.offering_id) {
    free.forEach((section) => {
      const warning = state.section_warnings[section.id];
      nodes.push(el("button", {
        type: "button", class: `backup-add${warning ? " warn" : ""}`, title: warning ? `Clashes with ${warning.join(", ")}` : null,
        onclick: () => { view.adding = null; Lance.send("/api/add", { section_id: section.id }); },
      }, `${section.section} ${meetingsText(section.meetings)}`));
    });
  } else if (free.length) {
    nodes.push(el("button", { type: "button", class: "link-btn small", onclick: () => { view.adding = first.offering_id; render(Lance.state); } }, "+ try another"));
  }
  return nodes;
}

function courseCard(rows, state, listName, index, total) {
  const first = rows[0];
  const a = first.analysis;
  const bid = rows.some((item) => item.bid !== null) ? Math.max(...rows.map((item) => item.bid || 0)) : null;
  const differs = new Set(rows.map((item) => item.bid)).size > 1;
  const showQuick = listName === "primary" && a.exact && first.section;
  const quick = showQuick ? QUICK.filter(([key]) => a.suggestions[key] !== null && a.suggestions[key] !== undefined).map(([key, label, hint]) => el("button", {
    type: "button", title: hint, onclick: () => Lance.send("/api/bid", { offering_id: first.offering_id, bid: Math.min(a.suggestions[key], state.plan.points) }),
  }, `${label} ${a.suggestions[key]}`)) : [];
  const others = listName === "primary" ? otherSections(rows, state) : [];
  const canOpen = rows.length > 1 || (a.known && a.histogram && a.histogram.length);
  const isOpen = view.open.has(first.offering_id);
  return el("article", { class: `card bid-course${bid === null ? "" : " has-bid"}` },
    el("div", { class: "bid-course-top" },
      el("a", { class: "name", href: Lance.courseHref(first.offering_id), text: first.name }),
      el("span", { class: "small faint num", text: `${first.term} · ${first.ects} ECTS${first.section ? ` · ${first.section} ${meetingsText(first.meetings)}` : ""}` }),
      menu(first, listName, index, total)),
    el("div", { class: "bid-main" },
      el("input", {
        class: "field num", type: "number", min: 0, max: state.plan.points, step: 1, inputmode: "numeric", placeholder: "no bid",
        value: bid === null ? "" : bid, "data-course": first.offering_id, "aria-label": `Bid on ${first.name}`,
        oninput: (event) => courseBid(first.offering_id, event.target.value),
      }),
      el("div", { class: "answer" }, ...answerOf(rows, state), differs ? el("span", { class: "faint", text: " · highest of different bids" }) : null),
      quick.length ? el("span", { class: "quick" }, ...quick) : null,
      canOpen ? el("button", {
        type: "button", class: "link-btn small", "aria-expanded": isOpen ? "true" : "false",
        onclick: () => { if (isOpen) view.open.delete(first.offering_id); else view.open.add(first.offering_id); render(Lance.state); },
      }, isOpen ? "Hide details" : "Details") : null),
    ...first.conflicts.concat(weekNotes(first, state)).map((note) => el("div", { class: `note-line ${note.level === "exam" ? "bad" : "warn"}`, text: note.text })),
    others.length ? el("div", { class: "bid-line" }, ...others) : null,
    isOpen ? el("div", { class: "bid-details" }, ...rows.map((item) => detailRow(item, rows, state.plan))) : null);
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
        el("div", { class: "course-main" }, el("span", { class: "course-name", text: course.name }),
          el("span", { class: "course-sub" }, `${course.term} · ${course.ects} ECTS`, clash ? el("span", { class: "warn", text: " · clashes" }) : null)),
        el("button", {
          type: "button", class: "pick", "aria-pressed": "false", "aria-label": `Add ${course.name} to the alternate list`, title: "Add", html: Lance.icons.plus,
          onclick: () => { view.picking = false; view.query = ""; Lance.send("/api/add", { offering_id: course.id, list: "alternate" }); },
        }));
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

function listBlock(title, subtitle, listName, state) {
  const items = state.items.filter((item) => item.list === listName).sort((a, b) => a.position - b.position);
  const order = [...new Set(items.map((item) => item.offering_id))];
  const block = el("section", { class: "stack", style: "gap:10px" },
    el("div", { class: "list-title" }, el("h2", { text: title }), subtitle ? el("span", { text: subtitle }) : null));
  order.forEach((offeringId, index) => {
    block.append(courseCard(items.filter((item) => item.offering_id === offeringId), state, listName, index, order.length));
  });
  return block;
}

function render(state) {
  const focused = document.activeElement;
  const focusKey = focused && focused.dataset ? (focused.dataset.course ? `[data-course="${focused.dataset.course}"]` : focused.dataset.item ? `[data-item="${focused.dataset.item}"]` : focused.dataset.picker ? "[data-picker]" : null) : null;
  const box = document.getElementById("bid-lists");
  renderBudget(state);
  const hasElectives = state.items.some((item) => item.list !== "mandatory");
  const nextButton = document.getElementById("next");
  nextButton.classList.toggle("primary", hasElectives);
  if (!hasElectives) {
    box.replaceChildren(el("section", { class: "card muted", style: "text-align:center;padding:36px 16px" },
      el("p", { text: state.items.length ? "Mandatory courses need no bid. Add an elective to bid on." : "Nothing to bid on yet." }),
      el("a", { class: "btn small", style: "margin-top:10px", href: Lance.pages.courses, text: "Pick courses" })));
    return;
  }
  const known = state.known_prices;
  const mandatory = new Set(state.items.filter((item) => item.list === "mandatory").map((item) => item.offering_id)).size;
  const alternate = listBlock("Alternate list", "Other courses, tried if a primary course gets no seat. Holds no points now; if used, it pays its bid, at most what is left.", "alternate", state);
  alternate.append(alternatePicker(state));
  box.replaceChildren(...[
    el("p", { class: "small faint" }, "Only a plan: nothing goes to Nova from here.", known ? ` Past prices so far for ${known.sections} of ${known.total} sections. ` : " ", el("a", { href: Lance.pages.share, text: "Share yours" })),
    listBlock("Primary list", "Higher up goes first. The highest bid per course is held.", "primary", state),
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

/* a menu closes when the click lands anywhere else */
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
