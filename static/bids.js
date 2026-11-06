/* The bids page. The server does all the arithmetic in logic.py; this file draws what it answers. */
const { el } = Lance;
const PRIORITIES = [["must", "Must have", "last cut-off + 25 %"], ["want", "Want", "last cut-off + 10 %"], ["nice", "Nice", "exactly last cut-off"]];

/* A small picture of last round: one bar per 20 points, dark where the bid won a seat. */
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

function outcomeText(item, plan) {
  const a = item.analysis;
  if (!a.known) return el("span", { class: "small faint" }, "No past price yet");
  const lines = [];
  if (a.cutoff !== null && a.cutoff !== undefined) {
    lines.push(el("div", { class: "small muted num", text: `Cut-off ${a.cutoff}${a.exact ? "" : ` (${a.round}, other term)`}${item.list === "alternate" ? ", alternate list" : ""}` }));
  }
  if (item.bid !== null && a.would_win !== undefined) {
    lines.push(el("div", { class: "small", style: `color:var(${a.would_win ? "--green" : "--red"});font-weight:600` },
      a.would_win ? "Seat last round" : "No seat last round"));
  }
  if (item.bid !== null && a.price !== undefined && a.would_win && item.list === "primary") {
    lines.push(el("div", { class: "small num", title: `(your bid + lowest winning bid in the course) / 2 = (${item.bid} + ${Math.min(a.lowest_in_course, item.bid)}) / 2` }, `Pays about `, el("b", { text: String(Math.round(a.price * 10) / 10) })));
  }
  if (item.bid !== null && item.list === "alternate" && a.would_win !== false) {
    lines.push(el("div", { class: "small muted num", text: "Pays its bid, at most what is left" }));
  }
  return el("div", { class: "outcome" }, ...lines);
}

let timers = {};
function saveBid(itemId, value) {
  clearTimeout(timers[itemId]);
  timers[itemId] = setTimeout(() => Lance.send("/api/bid", { item_id: itemId, bid: value }), 350);
}

function bidRow(item, plan) {
  const a = item.analysis;
  const input = el("input", {
    class: "field num", type: "number", min: 0, max: plan.points, step: 1, inputmode: "numeric", placeholder: "no bid",
    value: item.bid === null ? "" : item.bid, "data-item": item.id, "aria-label": `Bid on ${item.name} ${item.section || ""}`,
    oninput: (event) => saveBid(item.id, event.target.value),
  });
  const suggestions = el("div", { class: "suggest" });
  PRIORITIES.forEach(([key, label, hint]) => {
    const value = a.suggestions[key];
    if (value === null || value === undefined) return;
    suggestions.append(el("button", {
      type: "button", title: `${label}: ${hint}`,
      onclick: () => Lance.send("/api/bid", { item_id: item.id, bid: Math.min(value, plan.points) }),
    }, `${label} ${value}`));
  });
  const spark = histogram(a, item.bid);
  return el("div", { class: "bid-row" },
    el("div", { class: "strong", text: item.section || "Any" }),
    input,
    el("div", { class: "spark-cell" }, spark, spark ? null : (a.known ? null : el("a", { class: "small", href: "/share", text: "Share your rank list" })), suggestions),
    outcomeText(item, plan));
}

function courseCard(rows, plan, listName, index, total) {
  const first = rows[0];
  const moveButton = (direction, label, path) => el("button", {
    type: "button", class: "icon-btn", title: label, "aria-label": `${label}: ${first.name}`, disabled: (direction === "up" && index === 0) || (direction === "down" && index === total - 1) ? true : null,
    html: `<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${path}"/></svg>`,
    onclick: () => Lance.send("/api/move", { item_id: first.id, direction }),
  });
  const other = listName === "primary" ? "alternate" : "primary";
  return el("article", { class: "card bid-course" },
    el("div", { class: "bid-course-top" },
      el("span", { class: "tag num", text: String(index + 1) }),
      el("a", { class: "course-name grow", href: `/course/${first.offering_id}`, text: first.name }),
      el("span", { class: "tag num", text: `${first.term} · ${first.ects}` }),
      moveButton("up", "Higher priority", "M8 13V3M3.5 7.5 8 3l4.5 4.5"),
      moveButton("down", "Lower priority", "M8 3v10M3.5 8.5 8 13l4.5-4.5"),
      el("button", { type: "button", class: "btn small", onclick: () => Lance.send("/api/move", { item_id: first.id, list: other }) }, `To ${other}`)),
    ...rows.map((item) => bidRow(item, plan)));
}

function listBlock(title, listName, state) {
  const items = state.items.filter((item) => item.list === listName);
  const order = [];
  items.slice().sort((a, b) => a.position - b.position).forEach((item) => {
    if (!order.includes(item.offering_id)) order.push(item.offering_id);
  });
  const block = el("section", { class: "stack", style: "gap:10px" }, el("h2", { text: title }));
  if (!order.length) {
    block.append(el("div", { class: "card muted" }, listName === "primary"
      ? el("span", {}, "Nothing to bid on yet. ", el("a", { href: "/", text: "Pick courses in the planner." }))
      : el("span", { text: "Courses you would take if the primary list falls short. Nova strongly recommends filling this list." })));
  }
  order.forEach((offeringId, index) => {
    const rows = items.filter((item) => item.offering_id === offeringId).sort((a, b) => a.position - b.position);
    block.append(courseCard(rows, state.plan, listName, index, order.length));
  });
  return block;
}

function pointsCard(state) {
  const f = state.forecast;
  const figure = (label, value, cls) => el("div", { class: `figure ${cls || ""}` }, el("span", { class: "muted", text: label }), el("b", { text: value }));
  const box = document.getElementById("points-card");
  const seats = f.rows.filter((row) => row.status === "seat").length;
  box.replaceChildren(
    el("h2", { text: "If last round repeats" }),
    figure("Your points", String(state.plan.points)),
    figure("Taken while bidding", String(state.reserved)),
    figure(`Charged for ${seats} ${seats === 1 ? "seat" : "seats"}`, `${Math.round(f.expected * 10) / 10}`),
    figure("Left afterwards", `${Math.round(f.left * 10) / 10}`, "total"),
    f.left > 0 && f.rows.length ? el("p", { class: "small faint", style: "margin-top:6px", text: "Points do not carry over to the next semester. A higher bid on a course you must have costs only half of what you add." }) : null,
    ...f.rows.filter((row) => row.status !== "seat").map((row) => el("p", { class: "small", style: "margin-top:6px" }, el("b", { text: row.name }),
      el("span", { class: "muted", text: row.status === "no seat" ? ": no seat at this bid last round" : row.status === "no bid" ? ": no bid yet" : ": no past price yet" }))));
}

function warnings(state) {
  document.getElementById("bid-warnings").replaceChildren(...state.warnings.map((warning) => el("div", { class: `note-card ${warning.level}` }, el("span", { text: warning.text }))));
}

function render(state) {
  const focused = document.activeElement;
  const focusItem = focused && focused.dataset ? focused.dataset.item : null;
  const start = focusItem ? focused.value.length : 0;
  const box = document.getElementById("bid-lists");
  box.replaceChildren(listBlock("Primary list", "primary", state), listBlock("Alternate list", "alternate", state));
  pointsCard(state);
  warnings(state);
  if (focusItem) {
    const again = box.querySelector(`input[data-item="${focusItem}"]`);
    if (again) { again.focus(); again.type = "text"; again.setSelectionRange(start, start); again.type = "number"; }
  }
  document.getElementById("platform-list").value = state.platform_list;
}

document.getElementById("copy-list").addEventListener("click", () => {
  Lance.copy(document.getElementById("platform-list").value, "Copied. Type it into the platform: only there it counts.");
});
document.getElementById("copy-link").addEventListener("click", (event) => {
  Lance.copy(event.target.dataset.link, "Link copied. Open it on your phone to continue there.");
});
Lance.onChange(render);
Lance.load();
