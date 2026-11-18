/* The Bids tab of your plan: how much for each course. Your points on top, then one card per course:
   the bid in its field and last round's answer at the same place in every card, the details folded away inside the card.
   The server does all the arithmetic in logic.py; this file draws what it answers.
   It shares the screen with planner.js, so it keeps its names to itself. */
const Bids = (() => {
  const { el } = Lance;
  const QUICK = [["exact", "Just enough", "Exactly what the last seat cost last round"], ["plus10", "+10 %", "Last round's price plus 10 %"], ["plus25", "+25 %", "Last round's price plus 25 %"]];
  const view = { open: null, picking: false, query: "" };
  const compact = (time) => time.replace(/^0/, "");
  const whole = (value) => String(Math.round(value * 10) / 10);
  const meetingsText = (meetings) => meetings.map((m) => `${m.day} ${compact(m.start)}`).join(" · ");
  const catalogue = () => Lance.catalogue || [];   /* loaded by planner.js */
  const courseOf = (id) => catalogue().find((course) => course.id === id);
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
  /* the arrows in the top bar save a waiting bid at once, so that it counts as the last change (LN R19) */
  async function flush() {
    if (!pending) return;
    clearTimeout(pending.timer);
    const { body } = pending;
    pending = null;
    await Lance.send("/api/bid", body);
  }

  /* a number in its field with the unit inside: the same field for your points, a course's bid and, smaller, each section's bid.
     The unit lets clicks through, so a click on "pts" still lands in the field. */
  function numberField(attrs, small) {
    const input = el("input", { type: "number", min: 0, step: 1, inputmode: "numeric", placeholder: "–", ...attrs });
    selectOnFocus(input);
    return el("span", { class: `num-field${small ? " small" : ""}` }, input, el("span", { class: "unit", text: "pts" }));
  }

  /* a click or a tap into a number selects it, so that typing replaces it: a 0 never turns into 1100.
     The release of the click would put the cursor back, so it is held once; a redraw that puts the cursor
     back into the field it was in (see render) is no click and leaves the cursor where it was. */
  let restoring = false;
  function selectOnFocus(input) {
    let fresh = false;
    const select = () => { try { input.select(); } catch (error) { /* a browser that cannot select here simply does not */ } };
    input.addEventListener("focus", () => {
      if (restoring) return;
      fresh = true;
      select();
      setTimeout(() => { if (fresh && document.activeElement === input) select(); }, 0);
    });
    input.addEventListener("mouseup", (event) => { if (fresh) event.preventDefault(); fresh = false; });
    input.addEventListener("keydown", () => { fresh = false; });
    input.addEventListener("blur", () => { fresh = false; });
  }

  /* ---- your points on top: the one field here, what your bids hold, and what last round would have charged ---- */

  function renderPoints(state) {
    const box = document.getElementById("summary");
    let field = document.getElementById("set-points");
    if (!field) {
      /* built once and kept, so that typing is never interrupted by a redraw */
      let timer = null;
      const points = numberField({
        class: "field num", id: "set-points", max: 2000,
        "aria-label": "Your points, the Balance on Nova's platform", title: "The Balance on Nova's platform",
        oninput: (event) => { clearTimeout(timer); timer = setTimeout(() => Lance.send("/api/settings", { points: event.target.value || 0 }), 350); },
        onchange: (event) => { clearTimeout(timer); Lance.send("/api/settings", { points: event.target.value || 0 }); },
      });
      box.append(
        el("div", { class: "budget" },
          el("label", { class: "points-field" }, el("span", { text: "Your points" }), points),
          el("div", { class: "budget-use", id: "budget-use" })),
        el("p", { class: "forecast", id: "forecast" }),
        el("div", { id: "sum-note" }));
      field = document.getElementById("set-points");
    }
    if (field !== document.activeElement) field.value = state.plan.points || "";
    const use = budget(state);
    document.getElementById("budget-use").hidden = !use.length;
    document.getElementById("budget-use").replaceChildren(...use);
    const forecast = forecastLine(state);
    document.getElementById("forecast").hidden = !forecast;
    document.getElementById("forecast").replaceChildren(...(forecast || []));
    document.getElementById("sum-note").replaceChildren(...pointsNote(state));
  }

  /* "165 of 165 in bids · 0 left" and a slim bar of what the bids take; red once they take more than you have.
     Without your points there is nothing to compare: no line and no bar, only the note that asks for them */
  function budget(state) {
    const points = state.plan.points;
    if (!points) return [];
    const left = points - state.reserved;
    const over = left < 0;
    const share = Math.min(100, (state.reserved / points) * 100);
    return [
      el("p", { class: "budget-text" }, el("b", { class: "num", text: String(state.reserved) }), " of ", el("b", { class: "num", text: String(points) }), " in bids · ",
        el("b", { class: `num${over ? " bad" : ""}`, id: "points-left", text: String(left) }), " left"),
      el("div", { class: `meter${over ? " over" : ""}`, "aria-hidden": "true" }, el("i", { style: `width:${share}%` })),
    ];
  }

  /* what last round would have charged: one quiet line, the question it raises answered one click away, on the rules page at the price.
     The line breaks only between its parts, never inside one */
  function forecastLine(state) {
    const points = state.plan.points;
    const f = state.forecast;
    const seats = f.rows.filter((row) => row.status === "seat").length;
    const unknown = f.rows.filter((row) => row.status === "no data").length;
    if (!points || points < state.reserved || !seats) return null;
    const why = el("a", { class: "icon-btn why", href: `${Lance.pages.rules}#price`, title: "Why less than you bid?", "aria-label": "Why less than you bid?", html: Lance.icons.help });
    const pay = el("b", { class: "num", text: whole(f.expected) });
    const part = (...children) => el("span", { class: "part" }, ...children);
    /* without a price for every course the points coming back cannot be said */
    if (unknown) return [part("If last round repeats, for the courses with a price:"), " ", part("you pay about ", pay, " ", why)];
    return [part("If last round repeats:"), " ", part("you pay about ", pay, " ", why), el("span", { class: "sep", text: " · " }),
      part(el("b", { class: "num", text: whole(f.left) }), " back afterwards")];
  }

  /* missing points or a budget spent twice: one line with its icon. LN R17: points nobody typed are an estimate, and a line says so */
  function pointsNote(state) {
    const points = state.plan.points;
    const estimate = state.plan.points_estimated
      ? [el("p", { class: "meta", id: "points-estimate", text: `Estimated from your ${state.mandatory_ects} mandatory ECTS. Type the Balance from Nova's platform to replace it.` })] : [];
    if (!state.items.some((item) => item.list === "primary")) return estimate;
    if (!points) return [Lance.status("warn", "Enter your points: they are the Balance on Nova's platform.")];
    if (state.reserved > points) return [Lance.status("bad", `Your bids hold ${state.reserved} points, you have ${points}.`), ...estimate];
    return estimate;
  }

  /* the small print, once, under the lists */
  function foot(state) {
    const known = state.known_prices;
    const mandatory = new Set(state.items.filter((item) => item.list === "mandatory").map((item) => item.offering_id)).size;
    return el("div", { class: "bids-foot" },
      mandatory ? el("p", { text: `${mandatory} mandatory ${mandatory === 1 ? "course needs" : "courses need"} no bid.` }) : null,
      state.items.some((item) => item.analysis && item.analysis.known) ? el("label", { class: "check", title: "Part of the students with 45 or more ECTS passed rank with their bid × 1.1. It shows on your rank list. Not sure: leave it off." },
        el("input", { type: "checkbox", checked: state.plan.has_bonus ? true : null, onchange: (event) => Lance.send("/api/settings", { has_bonus: event.target.checked }) }),
        el("span", { text: "My bids count × 1.1 (45+ ECTS passed)" })) : null,
      el("p", {}, "Only a plan: nothing goes to Nova from here.", known ? ` Past prices for ${known.sections} of ${known.total} sections. ` : " ",
        el("a", { href: Lance.pages.share, text: "Share yours" })));
  }

  /* ---- the answer for one course: a verdict first, then the number; ok, warn, bad, or unknown when nobody can say ---- */

  function statusOf(rows, state) {
    const first = rows[0];
    const a = first.analysis;
    const bid = highest(rows);
    if (bid === null) return { tone: "warn", text: "No bid", title: "Nova reads an empty field as not interested. 0 is a bid." };
    if (!a.known) {
      const known = state.known_prices;
      return { tone: "unknown", text: "No past price", title: known ? `Known sections went for ${known.low} to ${known.high}.` : null };
    }
    if (!a.exact || !first.section) {
      const high = a.cutoff_high !== undefined && a.cutoff_high !== null && a.cutoff_high !== a.cutoff ? `–${Math.ceil(a.cutoff_high)}` : "";
      return { tone: "unknown", text: `Other term · from ${Math.ceil(a.cutoff)}${high}`, title: `${a.round}, another term: only a rough hint.` };
    }
    if (first.list === "alternate") {
      if (a.cutoff === null || a.cutoff === undefined) {
        if (!a.seats) return { tone: "warn", text: `No seat left · ${a.bids} bids`, title: "Last round no seat was left for the alternate list." };
        return { tone: "unknown", text: `${a.seats} seats for ${a.bids} bids`, title: "Last round on the alternate list" };
      }
      return { tone: "unknown", text: `Pays its bid · from ${Math.ceil(a.cutoff)}`, title: "If used, an alternate pays its bid, at most what is left." };
    }
    const outcome = state.forecast.rows.find((row) => row.offering_id === first.offering_id);
    if (outcome && outcome.status === "seat") {
      const where = outcome.section !== first.section ? ` in ${outcome.section}` : "";
      return { tone: "ok", text: `Enough${where} · pays ~${whole(outcome.price)}`, title: `(your bid + ${Math.min(a.lowest_in_course, bid)}, the lowest winning bid in the course) / 2` };
    }
    const lows = rows.map((item) => item.analysis.cutoff).filter((value) => value !== null && value !== undefined);
    return { tone: "bad", text: `Too low · from ${Math.ceil(Math.min(...lows))}`, title: "Last round's price for a seat" };
  }

  /* a course that clashes in the week, or whose exam Nova would block, says so in its card */
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

  const noteStatus = (note, cls) => Lance.status(note.level === "exam" ? "bad" : "warn", note.text, { cls });

  /* ---- the picture of last round: one grey bar per 20 points, darker where the bid won a seat ---- */

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
    /* the colours come from app.css, by the name of what a bar shows */
    const rect = (x0, y, w, h, kind) => {
      const node = document.createElementNS(ns, "rect");
      node.setAttribute("x", x0); node.setAttribute("y", y); node.setAttribute("width", Math.max(w, 0.5)); node.setAttribute("height", Math.max(h, 0));
      node.setAttribute("class", kind);
      svg.append(node);
    };
    bars.forEach((bar) => {
      const left = x(bar.from) + 0.5, w = x(bar.to) - x(bar.from) - 1;
      const all = (bar.bids / tallest) * (floor - 2);
      const won = (bar.allocated / tallest) * (floor - 2);
      rect(left, floor - all, w, all, "all");
      if (won) rect(left, floor - won, w, won, "won");
    });
    if (analysis.cutoff !== null && analysis.cutoff !== undefined) rect(x(analysis.cutoff) - 0.5, 0, 1, floor, "cut");
    if (rank !== undefined && bid !== null) rect(x(rank) - 1, 0, 2, height, `mine ${analysis.would_win ? "win" : "lose"}`);
    rect(0, floor, width, 1, "base");
    return svg;
  }

  /* ---- open: amounts to take, every section with its own numbers, other sections to try ---- */

  function sectionLine(item, rows, state) {
    const a = item.analysis;
    const backup = rows.indexOf(item) > 0;
    const numbers = a.known ? [a.cutoff !== null && a.cutoff !== undefined ? `a seat took ${Math.ceil(a.cutoff)}` : "no seat went out", a.seats !== null ? `${a.seats} seats` : null, a.bids !== null ? `${a.bids} bids` : null].filter(Boolean).join(" · ") : "no past price";
    const warning = item.conflicts.length ? item.conflicts.map((note) => note.text).join(" ") : null;
    /* every line has the same six places, so that the columns stay under each other; an empty one keeps its place */
    return el("div", { class: "sec-line" },
      el("b", { text: item.section || "Any" }),
      el("span", { class: "muted num", text: meetingsText(item.meetings) || "no timetable yet" }),
      rows.length > 1 ? numberField({
        class: "field num", max: state.plan.points, value: item.bid === null ? "" : item.bid, "data-item": item.id, "aria-label": `Bid on ${item.name} ${item.section || ""} only`,
        oninput: (event) => saveLater({ item_id: item.id, bid: event.target.value }),
      }, true) : el("span"),
      el("span", { class: "sec-numbers num" }, warning ? Lance.status("warn", `clashes · ${numbers}`, { title: warning }) : numbers),
      histogram(a, item.bid) || el("span"),
      backup ? el("button", { type: "button", class: "icon-btn", title: `Do not try ${item.section}`, "aria-label": `Do not try ${item.section}`, html: Lance.icons.close, onclick: () => Lance.send("/api/remove", { item_id: item.id }) }) : el("span"));
  }

  function details(rows, state, listName) {
    const first = rows[0];
    const a = first.analysis;
    const course = courseOf(first.offering_id);
    const free = course && first.section ? course.sections.filter((section) => !rows.some((row) => row.section_id === section.id)) : [];
    const quick = listName === "primary" && a.exact && first.section ? QUICK.filter(([key]) => a.suggestions[key] !== null && a.suggestions[key] !== undefined) : [];
    const notes = notesOf(rows, state);
    return el("div", { class: "bid-details" },
      /* the amount in its own span: on a phone it stands under its name, so that three buttons fit one row */
      quick.length ? el("div", { class: "quick" }, el("span", { class: "meta", text: "Take" }), ...quick.map(([key, label, hint]) => el("button", {
        type: "button", class: "btn small", title: hint, onclick: () => Lance.send("/api/bid", { offering_id: first.offering_id, bid: Math.min(a.suggestions[key], state.plan.points) }),
      }, el("span", { text: label }), " ", el("span", { class: "num", text: String(a.suggestions[key]) })))) : null,
      ...notes.map((note) => noteStatus(note)),
      el("div", { class: "sec-lines" },
        rows.length > 1 || free.length ? el("p", { class: "meta", text: listName === "primary" ? "Nova tries the sections in this order:" : "Sections:" }) : null,
        ...rows.map((item) => sectionLine(item, rows, state))),
      free.length && listName === "primary" ? el("div", { class: "try-more" }, el("span", { class: "meta", text: "If full, also try" }), ...free.map((section) => {
        const warning = state.section_warnings[section.id];
        return el("button", {
          type: "button", class: "btn small backup-add", title: warning ? `Clashes with ${warning.join(", ")}` : null,
          onclick: () => Lance.send("/api/add", { section_id: section.id }),
        }, warning ? Lance.icon("warn") : null, `${section.section} ${meetingsText(section.meetings)}`);
      })) : null,
      listName === "primary" && a.exact && a.lowest_in_course !== null && a.lowest_in_course !== undefined
        ? el("p", { class: "meta", text: `You pay the middle of your bid and ${a.lowest_in_course}, the lowest winning bid in the whole course. No seat, no charge.` }) : null);
  }

  /* what else can be done with a course: a row of tertiary buttons at the foot of the open card */
  function actions(first, listName, index, total) {
    const button = (label, action, disabled) => el("button", { type: "button", class: "btn tertiary", disabled: disabled ? true : null, onclick: action }, label);
    const other = listName === "primary" ? "alternate" : "primary";
    return el("div", { class: "bid-actions" },
      /* the order counts on the primary list only, so only there it can be changed */
      listName === "primary" ? button("Move up", () => Lance.send("/api/move", { item_id: first.id, direction: "up" }), index === 0) : null,
      listName === "primary" ? button("Move down", () => Lance.send("/api/move", { item_id: first.id, direction: "down" }), index === total - 1) : null,
      button(`To ${other} list`, () => Lance.send("/api/move", { item_id: first.id, list: other })),
      el("a", { class: "go", href: `#${first.offering_id}` }, "Course details"),
      button("Remove", async () => {
        const answer = await Lance.send("/api/remove", { offering_id: first.offering_id });
        if (!answer.error) Lance.toast(`Removed ${first.name}`, { label: "Undo", run: () => Lance.send("/api/restore", { rows: answer.removed }) });
      }));
  }

  /* ---- one course, one card ---- */

  function toggle(offeringId) {
    view.open = view.open === offeringId ? null : offeringId;
    render(Lance.state);
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
      el("div", {
        class: `bid-head${listName === "primary" ? "" : " no-rank"}`,
        /* the whole head opens the card, except the field: a click there is for typing */
        onclick: (event) => { if (!event.target.closest(".num-field")) toggle(first.offering_id); },
      },
        listName === "primary" ? el("span", { class: "rank", text: String(index + 1), title: "Place on your primary list" }) : null,
        /* the dot in the colour of the course, as before its name in the list and on its block in the week */
        el("button", { type: "button", class: "bid-name", "aria-expanded": open ? "true" : "false", "data-key": `bid-${first.offering_id}` },
          Lance.dot(state, first.offering_id),
          el("span", { class: "course-text" },
            el("span", { class: "course-name", text: first.name, title: first.name }),
            el("span", { class: "course-sub", text: sub }),
            notes.length ? noteStatus(notes.find((note) => note.level === "exam") || notes[0], "course-note") : null)),
        el("div", { class: "bid-answer" },
          numberField({
            class: "field num bid-input", max: state.plan.points, value: bid === null ? "" : bid, "data-course": first.offering_id, "aria-label": `Bid on ${first.name}`,
            oninput: (event) => saveLater({ offering_id: first.offering_id, bid: event.target.value }),
          }),
          Lance.status(status.tone, differs ? `${status.text} · bids differ` : status.text, { title: status.title, cls: "bid-status" })),
        Lance.icon("chev")),
      open ? details(rows, state, listName) : null,
      open ? actions(first, listName, index, total) : null);
  }

  /* ---- the alternate list ends in an empty card: it adds a course there, through a search ---- */

  function alternatePicker(state) {
    if (!view.picking) {
      return el("button", { type: "button", class: "add-card", onclick: () => { view.picking = true; render(Lance.state); } },
        el("span", { html: Lance.icons.plus }), "Add alternate course");
    }
    const results = el("div", {});
    const draw = () => {
      const words = view.query.toLowerCase().split(/\s+/).filter(Boolean);
      const planned = new Set(state.items.map((item) => item.offering_id));
      const hits = catalogue().filter((course) => course.kind !== "mandatory" && !planned.has(course.id))
        .filter((course) => words.every((word) => `${course.name} ${course.code} ${course.lecturers}`.toLowerCase().includes(word))).slice(0, 6);
      /* the same row as in the list on the left: name and facts, the plus at the right edge */
      results.replaceChildren(...hits.map((course) => {
        const clash = course.sections.length > 0 && course.sections.every((section) => state.section_warnings[section.id]);
        return el("div", { class: "hit" },
          el("span", { class: "course-text" },
            el("span", { class: "course-name", text: course.name }),
            el("span", { class: "course-sub", text: `${course.term} · ${course.ects} ECTS` }),
            clash ? Lance.status("warn", "Clashes with your week", { cls: "course-note" }) : null),
          el("span", { class: "control" }, el("button", {
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
    const close = el("button", {
      type: "button", class: "icon-btn", title: "Close", "aria-label": "Close the search", html: Lance.icons.close,
      onclick: () => { view.picking = false; view.query = ""; render(Lance.state); },
    });
    const box = el("div", { class: "picker" }, el("div", { class: "picker-top" }, field, close), results);
    setTimeout(() => { field.focus(); box.scrollIntoView({ block: "nearest" }); }, 0);
    return box;
  }

  /* a list: its heading with the count, one grey line about how it works, then its cards */
  function listBlock(title, hint, listName, state) {
    const items = state.items.filter((item) => item.list === listName).sort((a, b) => a.position - b.position);
    const order = [...new Set(items.map((item) => item.offering_id))];
    const block = el("section", { class: "bid-list", "aria-label": title },
      el("div", { class: "list-title" }, el("h3", {}, title, el("span", { class: "count", text: ` ${order.length}` })), el("p", { class: "meta", text: hint })));
    order.forEach((offeringId, index) => block.append(bidRow(items.filter((item) => item.offering_id === offeringId), state, listName, index, order.length)));
    return block;
  }

  /* ---- what the tab says about itself: the worst thing to fix, in two words ---- */

  function problem(state) {
    const items = state.items.filter((item) => item.list === "primary");
    if (!items.length) return null;
    const points = state.plan.points;
    if (!points) return { cls: "warn", text: "No points" };
    if (state.reserved > points) return { cls: "bad", text: `Over by ${state.reserved - points}` };
    const courses = [...new Set(items.map((item) => item.offering_id))].map((id) => items.filter((item) => item.offering_id === id).sort((a, b) => a.position - b.position));
    const low = courses.filter((rows) => statusOf(rows, state).tone === "bad").length;
    if (low) return { cls: "bad", text: `${low} too low` };
    const none = courses.filter((rows) => highest(rows) === null).length;
    if (none) return { cls: "warn", text: `${none} without bid` };
    return null;
  }

  /* after a redraw the cursor stays where it was: in the same field, or on the same card */
  function focusKeyOf(node) {
    if (!node || !node.dataset) return null;
    if (node.dataset.course) return `input[data-course="${node.dataset.course}"]`;
    if (node.dataset.item) return `input[data-item="${node.dataset.item}"]`;
    if (node.dataset.picker) return "input[data-picker]";
    if (node.dataset.key) return `[data-key="${node.dataset.key}"]`;
    return null;
  }

  function render(state) {
    const focused = document.activeElement;
    const focusKey = focusKeyOf(focused);
    const box = document.getElementById("bid-lists");
    renderPoints(state);
    const hasElectives = state.items.some((item) => item.list !== "mandatory");
    if (!hasElectives) {
      /* the courses are on the left; on a phone the button leads there */
      box.replaceChildren(el("div", { class: "empty-note" },
        el("p", { text: state.items.length ? "Mandatory courses need no bid. Add an elective to bid on." : "Nothing to bid on yet." }),
        el("button", { type: "button", class: "btn only-phone", onclick: () => { location.hash = ""; } }, "Pick courses")));
      return;
    }
    const alternate = listBlock("Alternate list", "Tried if a primary course gets no seat. Needs a bid, holds no points.", "alternate", state);
    alternate.append(alternatePicker(state));
    box.replaceChildren(listBlock("Primary list", "Higher up goes first", "primary", state), alternate, foot(state));
    const again = focusKey ? box.querySelector(focusKey) : null;
    if (!again) return;
    restoring = true;
    again.focus({ preventScroll: true });
    restoring = false;
    if (again.type === "number") {
      /* the cursor goes back behind the last digit; a number field only allows that as a text field */
      const end = focused.value.length;
      again.type = "text"; again.setSelectionRange(end, end); again.type = "number";
    }
  }

  /* Esc folds the open card, as it folds an open row on the left */
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !view.open) return;
    const id = view.open;
    view.open = null;
    render(Lance.state);
    const name = document.querySelector(`[data-key="bid-${id}"]`);
    if (name) name.focus({ preventScroll: true });
  });

  /* planner.js loads the catalogue and the plan; this tab draws itself whenever the plan changes */
  Lance.onChange(render);
  if (Lance.state) render(Lance.state);

  return { problem, flush };
})();
