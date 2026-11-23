/* Preview only. The real app computes everything on the server in logic.py. This file repeats those rules
   in the browser, so that the same pages work from a static link without a server. tests in
   preview/check_parity.py compare it with logic.py. The plan lives in this browser only. */
(function () {
  const realFetch = window.fetch.bind(window);
  const KEY = "lance-preview-plan-3";
  let DATA = null;
  let sheets = null;
  let offerings, sections, meetings, sessions, exams, kindsByProgramme, areasByProgramme;

  const ready = realFetch("data.json").then((r) => r.json()).then((d) => {
    DATA = d;
    offerings = Object.fromEntries(d.offerings.map((o) => [o.id, o]));
    sections = Object.fromEntries(d.sections.map((s) => [s.id, s]));
    meetings = d.meetings;
    sessions = d.sessions;
    exams = d.exams;
    kindsByProgramme = d.kinds;
    areasByProgramme = d.areas || {};
  });

  // ---------- storing the plan ----------
  function blank() { return { plan: { id: "preview", programme: "", semester: "Fall", points: 0, has_bonus: 0, area: "" }, items: [], next: 1 }; }
  function load() {
    if (window.__lanceStore) return window.__lanceStore;
    let store = null;
    try { store = JSON.parse(localStorage.getItem(KEY)); } catch (e) { store = null; }
    window.__lanceStore = store || blank();
    return window.__lanceStore;
  }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(window.__lanceStore)); } catch (e) { /* private window */ } }

  // ---------- times ----------
  const toMinutes = (clock) => { const [h, m] = clock.split(":"); return Number(h) * 60 + Number(m); };
  const overlaps = (a0, a1, b0, b1) => toMinutes(a0) < toMinutes(b1) && toMinutes(b0) < toMinutes(a1);
  const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  function dayLabel(iso) {
    const [y, m, d] = iso.split("-").map(Number);
    const day = new Date(Date.UTC(y, m - 1, d));
    return WEEKDAYS[(day.getUTCDay() + 6) % 7] + " " + d + " " + MONTHS[m - 1];
  }
  const weekOf = (iso) => (iso <= "2026-10-21" ? "T1" : iso <= "2026-12-31" ? "T2" : iso <= "2027-03-31" ? "T3" : "T4");
  const labelOf = (offeringId, sectionId) => offerings[offeringId].name + (sectionId ? " " + sections[sectionId].section : "");
  const regularExams = (o) => (exams[o.code + "-" + o.term] || []).filter((e) => ["exam", "midterm", "presentation"].includes(e.kind) && e.date);

  // ---------- clashes ----------
  function clashingDates(a, b) {
    const byDate = {};
    (sessions[b] || []).forEach((s) => { (byDate[s.date] = byDate[s.date] || []).push(s); });
    const found = [];
    (sessions[a] || []).forEach((s) => {
      (byDate[s.date] || []).forEach((o) => {
        if (overlaps(s.start, s.end, o.start, o.end)) {
          found.push([s.date, s.start > o.start ? s.start : o.start, s.end < o.end ? s.end : o.end]);
        }
      });
    });
    return found;
  }
  function weekItems(items) {
    const first = new Map();
    items.slice().sort((a, b) => a.position - b.position).forEach((item) => {
      if ((item.list === "mandatory" || item.list === "primary") && !first.has(item.offering_id)) first.set(item.offering_id, item);
    });
    return [...first.values()];
  }
  function alternatesInWeek(items) {
    const first = new Map();
    items.slice().sort((a, b) => a.position - b.position).forEach((item) => {
      if (item.list === "alternate" && !first.has(item.offering_id)) first.set(item.offering_id, item);
    });
    return [...first.values()];
  }
  function conflictsWithWeek(item, items, week) {
    const inWeek = new Set(week.map((e) => e.id));
    let others = items.filter((e) => e.offering_id !== item.offering_id && (e.list === "mandatory" || e.list === "primary"));
    if (item.list !== "alternate") others = others.filter((e) => inWeek.has(e.id));
    const found = [];
    if (item.section_id) {
      others.filter((e) => e.section_id).forEach((entry) => {
        if (clashingDates(item.section_id, entry.section_id).length) {
          found.push({ level: "class", text: "Clashes with " + labelOf(entry.offering_id, entry.section_id) + (inWeek.has(entry.id) ? "" : " (if you land there)") });
        }
      });
    }
    const firm = week.filter((e) => e.offering_id !== item.offering_id);
    if (item.list === "alternate") {
      examClashes(firm.concat([item])).forEach((clash) => {
        if (!clash.offerings.includes(item.offering_id)) return;
        const name = offerings[clash.offerings.find((id) => id !== item.offering_id)].name;
        if (clash.kind === "exam") found.push({ level: "exam", text: "Exam at the same time as " + name + ". Nova will not enroll you in both." });
        else found.push({ level: "midterm", text: "Midterm clash with " + name + ". Nova does not check this." });
      });
    } else if (item.section_id) {
      midtermClassClashes(firm.concat([item])).forEach((clash) => {
        if (clash.second === labelOf(item.offering_id, item.section_id)) found.push({ level: "midterm", text: "Meets during the midterm of " + clash.first.replace(" (midterm)", "") + "." });
      });
    }
    return found;
  }
  function classClashes(items) {
    const clashes = [];
    const entries = items.filter((i) => i.section_id);
    entries.forEach((first, i) => {
      entries.slice(i + 1).forEach((second) => {
        if (first.offering_id === second.offering_id) return;
        const dates = clashingDates(first.section_id, second.section_id);
        if (dates.length) {
          clashes.push({
            kind: "class", severity: "class", items: [first.id, second.id], offerings: [first.offering_id, second.offering_id],
            first: labelOf(first.offering_id, first.section_id), second: labelOf(second.offering_id, second.section_id),
            times: dates.length, of: (sessions[first.section_id] || []).length,
            when: dayLabel(dates[0][0]) + ", " + dates[0][1] + "–" + dates[0][2],
            dates: dates.map((d) => dayLabel(d[0])), weeks: [...new Set(dates.map((d) => weekOf(d[0])))].sort(),
          });
        }
      });
    });
    return clashes;
  }
  function plannedOfferings(items) { return [...new Set(items.map((i) => i.offering_id))].sort().map((id) => offerings[id]); }
  function examClashes(items) {
    const list = plannedOfferings(items);
    const clashes = [];
    list.forEach((first, i) => {
      list.slice(i + 1).forEach((second) => {
        regularExams(first).forEach((a) => {
          regularExams(second).forEach((b) => {
            if (a.date !== b.date || !overlaps(a.start, a.end, b.start, b.end)) return;
            const both = a.kind === "exam" && b.kind === "exam";
            clashes.push({ kind: both ? "exam" : "midterm", severity: both ? "exam" : "midterm", offerings: [first.id, second.id], first: `${first.name} (${a.kind})`, second: `${second.name} (${b.kind})`, when: dayLabel(a.date) + ", " + a.start });
          });
        });
      });
    });
    return clashes.concat(midtermClassClashes(items));
  }
  function midtermClassClashes(items) {
    const list = plannedOfferings(items);
    const clashes = [];
    const entries = items.filter((i) => i.section_id);
    list.forEach((offering) => {
      regularExams(offering).filter((e) => e.kind === "midterm").forEach((exam) => {
        entries.forEach((entry) => {
          if (entry.offering_id === offering.id) return;
          (sessions[entry.section_id] || []).forEach((s) => {
            if (s.date === exam.date && overlaps(s.start, s.end, exam.start, exam.end)) {
              clashes.push({ kind: "midterm", severity: "midterm", offerings: [offering.id, entry.offering_id], first: `${offering.name} (midterm)`, second: labelOf(entry.offering_id, entry.section_id), when: dayLabel(exam.date) + ", " + exam.start });
            }
          });
        });
      });
    });
    return clashes;
  }
  function sectionWarnings(items, semester) {
    const week = weekItems(items);
    const entries = week.filter((i) => i.section_id);
    const perSection = {}, perOffering = {};
    const planned = new Set(items.map((i) => i.offering_id));
    const inWeek = new Set(week.map((i) => i.offering_id));
    DATA.sections.forEach((section) => {
      if (offerings[section.offering_id].semester !== semester) return;
      const names = [];
      entries.forEach((entry) => {
        if (entry.offering_id === section.offering_id) return;
        const dates = clashingDates(section.id, entry.section_id);
        if (!dates.length) return;
        const halves = [...new Set(dates.map((d) => weekOf(d[0])))].sort();
        const term = offerings[section.offering_id].term;
        names.push(labelOf(entry.offering_id, entry.section_id) + (halves.length === 1 && (term === "S1" || term === "S2") ? " (" + halves[0] + ")" : ""));
      });
      if (names.length) perSection[section.id] = names;
    });
    DATA.offerings.forEach((offering) => {
      if (offering.semester !== semester || planned.has(offering.id)) return;
      const notes = new Set();
      inWeek.forEach((otherId) => {
        const other = offerings[otherId];
        regularExams(offering).forEach((a) => {
          regularExams(other).forEach((b) => {
            if (a.kind === "exam" && b.kind === "exam" && a.date === b.date && overlaps(a.start, a.end, b.start, b.end)) notes.add(other.name);
          });
        });
      });
      if (notes.size) perOffering[offering.id] = [...notes].sort();
    });
    return [perSection, perOffering];
  }

  // ---------- prices ----------
  function pastPrices(code, term, listName) {
    const rows = DATA.cutoffs.filter((r) => r.code === code && r.list === (listName || "primary"));
    const same = rows.filter((r) => r.term === term);
    return same.length ? [same, true] : [rows, false];
  }
  function lowestBid(code, term) {
    const bids = pastPrices(code, term)[0].map((r) => r.min_bid).filter((b) => b !== null);
    return bids.length ? Math.min(...bids) : null;
  }
  function cutoffFor(code, term, section) {
    const row = pastPrices(code, term)[0].find((r) => r.section === section && r.min_rank_value !== null);
    return row ? row.min_rank_value : null;
  }
  const MARGIN = { exact: 1.00, plus10: 1.10, plus25: 1.25 };
  const rankValue = (bid, bonus) => (bonus ? Math.round(bid * 1.1 * 100) / 100 : bid);
  function suggest(cutoff, bonus, priority) {
    if (cutoff === null || cutoff === undefined) return null;
    const needed = cutoff / (bonus ? 1.1 : 1);
    /* round away float noise first, as Python's ceil sees the same doubles */
    return Math.ceil(needed * MARGIN[priority]);
  }
  function bidAnalysis(item, plan) {
    const offering = offerings[item.offering_id];
    const section = item.section_id ? sections[item.section_id].section : null;
    const listName = item.list === "alternate" ? "alternate" : "primary";
    let [rows, exact] = pastPrices(offering.code, offering.term, listName);
    if (listName === "alternate" && !rows.length) [rows, exact] = pastPrices(offering.code, offering.term, "primary");
    const row = rows.find((r) => r.section === section) || null;
    const lowest = lowestBid(offering.code, offering.term);
    const bonus = Boolean(plan.has_bonus);
    const result = {
      known: row !== null || (!section && rows.length > 0), exact, round: rows.length ? rows[0].round : null,
      cutoff: row ? row.min_rank_value : null, top: row ? row.max_rank_value : null, seats: row ? row.seats : null,
      bids: row ? row.bids : null, zero_bids: row ? row.zero_bids : null, lowest_in_course: lowest, suggestions: {},
    };
    if (row) {
      result.histogram = DATA.histograms.filter((h) => h.code === offering.code && h.term === row.term && h.section === section && h.list === row.list && h.round === row.round)
        .map((h) => ({ from: h.bucket_from, to: h.bucket_to, bids: h.bids, allocated: h.allocated }));
    }
    if (!section && rows.length) {
      const lows = rows.map((r) => r.min_rank_value).filter((v) => v !== null);
      const highs = rows.map((r) => r.max_rank_value).filter((v) => v !== null);
      result.cutoff = lows.length ? Math.min(...lows) : null;
      result.cutoff_high = lows.length ? Math.max(...lows) : null;
      result.top = highs.length ? Math.max(...highs) : null;
    }
    Object.keys(MARGIN).forEach((p) => { result.suggestions[p] = suggest(result.cutoff, bonus, p); });
    if (item.bid !== null) {
      result.rank_value = rankValue(item.bid, bonus);
      if (result.cutoff !== null) result.would_win = result.rank_value >= result.cutoff;
      if (listName === "alternate") result.price = Math.min(item.bid, plan.points);
      else if (lowest !== null) result.price = (item.bid + Math.min(lowest, item.bid)) / 2;
    }
    return result;
  }
  function reserved(items) {
    const highest = {};
    items.forEach((i) => { if (i.list === "primary" && i.bid !== null) highest[i.offering_id] = Math.max(highest[i.offering_id] || 0, i.bid); });
    return Object.values(highest).reduce((a, b) => a + b, 0);
  }
  function forecast(plan, items) {
    const bonus = Boolean(plan.has_bonus);
    const courses = {};
    items.forEach((i) => { if (i.list === "primary") (courses[i.offering_id] = courses[i.offering_id] || []).push(i); });
    const rows = [];
    let expected = 0;
    Object.entries(courses).forEach(([offeringId, entries]) => {
      const offering = offerings[offeringId];
      entries = entries.slice().sort((a, b) => a.position - b.position);
      const lowest = lowestBid(offering.code, offering.term);
      const outcome = { offering_id: offeringId, name: offering.name, status: "no data", section: null, price: null };
      if (!entries.some((e) => e.bid !== null)) outcome.status = "no bid";
      for (const entry of entries) {
        if (entry.bid === null || !entry.section_id) continue;
        const section = sections[entry.section_id].section;
        const cutoff = cutoffFor(offering.code, offering.term, section);
        if (cutoff === null) continue;
        outcome.status = "no seat";
        if (rankValue(entry.bid, bonus) >= cutoff && lowest !== null) {
          outcome.status = "seat";
          outcome.section = section;
          outcome.price = (entry.bid + Math.min(lowest, entry.bid)) / 2;
          expected += outcome.price;
          break;
        }
      }
      rows.push(outcome);
    });
    return { rows, expected, left: plan.points - expected };
  }
  function ects(items) {
    const seen = {};
    items.forEach((i) => { if (i.list === "mandatory" || i.list === "primary") seen[offerings[i.offering_id].code] = offerings[i.offering_id].ects; });
    const total = Object.values(seen).reduce((a, b) => a + b, 0);
    return { total, recommended: 28, maximum: 31.5, over: total > 31.5 };
  }
  function warnings(plan, items) {
    const found = [];
    const res = reserved(items);
    const electives = items.filter((i) => i.list === "primary");
    if (electives.length && plan.points === 0) found.push({ level: "stop", where: "bids", text: "Enter your points: they are the Balance on Nova's platform." });
    else if (res > plan.points) found.push({ level: "stop", where: "bids", text: `Your primary bids hold ${res} points, you have ${plan.points}.` });
    const noBid = [...new Set(electives.filter((i) => i.bid === null).map((i) => offerings[i.offering_id].name))].sort();
    if (noBid.length) found.push({ level: "note", where: "bids", text: "No bid yet: " + noBid.join(", ") + ". Nova reads an empty field as not interested." });
    if (electives.length && !items.some((i) => i.list === "alternate")) found.push({ level: "note", where: "bids", text: "Your alternate list is empty. Nova strongly recommends filling it." });
    const sum = ects(items);
    if (sum.over) found.push({ level: "stop", where: "courses", text: `${sum.total} ECTS is above the maximum of 31.5.` });
    return found;
  }
  function roundOf(semester, today) {
    today = today || new Date().toISOString().slice(0, 10);
    const row = DATA.calendar.find((r) => r.key === semester.toLowerCase() + "-bidding");
    if (!row) return null;
    const status = today > row.last_day ? "closed" : today >= row.first_day ? "open" : "upcoming";
    return { label: row.label, range: dayLabel(row.first_day) + " – " + dayLabel(row.last_day), first_day: dayLabel(row.first_day).split(" ").slice(1).join(" "), last_day: dayLabel(row.last_day), status, days: Math.max(Math.round((Date.parse(row.first_day) - Date.parse(today)) / 86400000), 0) };
  }
  function knownPrices() {
    const prices = DATA.cutoffs.filter((r) => r.list === "primary" && r.min_rank_value !== null).map((r) => r.min_rank_value);
    if (!prices.length) return null;
    return { sections: prices.length, total: DATA.coverage_total, low: Math.floor(Math.min(...prices)), high: Math.ceil(Math.max(...prices)) };
  }
  function nextDeadline(today) {
    today = today || new Date().toISOString().slice(0, 10);
    const upcoming = DATA.calendar.filter((r) => (r.key.includes("bidding") || r.key.includes("add-drop")) && r.last_day >= today);
    if (!upcoming.length) return null;
    const row = upcoming[0];
    const days = Math.round((Date.parse(row.first_day) - Date.parse(today)) / 86400000);
    return { label: row.label, first_day: row.first_day, last_day: row.last_day, days: Math.max(days, 0), range: dayLabel(row.first_day) + " – " + dayLabel(row.last_day) };
  }
  function platformList(items) {
    const lines = [];
    [["primary", "PRIMARY LIST"], ["alternate", "ALTERNATE LIST"]].forEach(([listName, title]) => {
      const entries = items.filter((i) => i.list === listName).sort((a, b) => a.position - b.position);
      if (!entries.length) return;
      lines.push(title);
      const order = [];
      entries.forEach((i) => { if (!order.includes(i.offering_id)) order.push(i.offering_id); });
      order.forEach((offeringId, index) => {
        const o = offerings[offeringId];
        const parts = entries.filter((e) => e.offering_id === offeringId).map((e) => (e.section_id ? sections[e.section_id].section : "section to choose") + " " + (e.bid === null ? "no bid" : e.bid));
        lines.push(`${index + 1}. ${o.code} ${o.name} (${o.term}): ` + parts.join(", "));
      });
      lines.push("");
    });
    return lines.join("\n").trim();
  }
  function planItems(store) {
    /* the same order as the database query: list, position, id */
    return store.items.filter((i) => offerings[i.offering_id].semester === store.plan.semester)
      .sort((a, b) => a.list.localeCompare(b.list) || a.position - b.position || a.id - b.id);
  }
  // ---------- LN R20: areas of expertise (logic.areas_of, area_roles, area_progress) ----------
  const sortedNames = (names) => [...new Set(names)].sort();
  function areasOf(programme) { return programme ? sortedNames((areasByProgramme[programme] || []).map((row) => row.area)) : []; }
  function areaRows(plan) { return plan.area ? (areasByProgramme[plan.programme] || []).filter((row) => row.area === plan.area) : []; }
  function areaRoles(plan) {
    return Object.fromEntries(areaRows(plan).filter((row) => row.role !== "elsewhere").map((row) => [`${row.code}-${row.term}`, row.role]));
  }
  function areaProgress(store) {
    const rows = areaRows(store.plan);
    if (!rows.length) return null;
    const roles = areaRoles(store.plan);
    const taken = {};
    store.items.forEach((item) => {
      if (item.list === "primary" && roles[item.offering_id]) taken[offerings[item.offering_id].code] = offerings[item.offering_id].ects;
    });
    const coreMissing = sortedNames(rows.filter((row) => row.role === "core" && !(row.code in taken)).map((row) => row.name));
    const options = rows.filter((row) => row.role === "core_optional");
    const coreOptions = options.some((row) => row.code in taken) ? [] : sortedNames(options.map((row) => row.name));
    const ects = Object.values(taken).reduce((sum, value) => sum + value, 0);
    return {
      name: store.plan.area, ects, needed: 21, core_rule: rows.some((row) => row.role === "core") ? "core" : options.length ? "core_optional" : "none",
      core_missing: coreMissing, core_options: coreOptions,
      done: ects >= 21 && !coreMissing.length && !coreOptions.length,
      elsewhere: rows.filter((row) => row.role === "elsewhere").map((row) => ({ name: row.name, ects: row.ects })),
    };
  }

  function stateOf(store, today) {
    const items = planItems(store);
    const plan = store.plan;
    const week = weekItems(items);
    const weekIds = new Set(week.map((i) => i.id));
    const alternateIds = new Set(alternatesInWeek(items).map((i) => i.id));
    const enriched = items.map((item) => {
      const o = offerings[item.offering_id];
      return Object.assign({}, item, {
        in_week: weekIds.has(item.id),
        in_alternate_week: alternateIds.has(item.id),
        conflicts: weekIds.has(item.id) ? [] : conflictsWithWeek(item, items, week),
        plan_id: plan.id, name: o.name, code: o.code, term: o.term, ects: o.ects,
        section: item.section_id ? sections[item.section_id].section : null,
        meetings: item.section_id ? (meetings[item.section_id] || []) : [],
        analysis: item.list !== "mandatory" ? bidAnalysis(item, plan) : null,
      });
    });
    const [perSection, perOffering] = sectionWarnings(items, plan.semester);
    const examList = [];
    [...new Set(items.map((i) => i.offering_id))].sort().forEach((id) => {
      const o = offerings[id];
      regularExams(o).forEach((e) => examList.push({ offering_id: id, name: o.name, kind: e.kind, date: e.date, start: e.start, end: e.end, label: dayLabel(e.date), note: e.note }));
    });
    examList.sort((a, b) => (a.date + a.start).localeCompare(b.date + b.start));
    return {
      plan, items: enriched, ects: ects(items), reserved: reserved(items), forecast: forecast(plan, items),
      clashes: classClashes(week).concat(examClashes(week)).map((c, i) => [c, i]).sort((a, b) => ["exam", "class", "midterm"].indexOf(a[0].kind) - ["exam", "class", "midterm"].indexOf(b[0].kind) || a[1] - b[1]).map((pair) => pair[0]), section_warnings: perSection, exam_warnings: perOffering, exams: examList,
      warnings: warnings(plan, items), next_deadline: nextDeadline(today), round: roundOf(plan.semester, today), known_prices: knownPrices(), platform_list: platformList(items),
      areas: areasOf(plan.programme), area: areaProgress(store),
    };
  }
  function catalogue(store) {
    const plan = store.plan;
    const kinds = kindsByProgramme[plan.programme] || {};
    const roles = areaRoles(plan);
    const rows = [];
    DATA.offerings.forEach((o) => {
      if (o.semester !== plan.semester) return;
      const own = DATA.sections.filter((s) => s.offering_id === o.id).sort((a, b) => a.section.localeCompare(b.section))
        .map((s) => {
          const price = DATA.cutoffs.find((r) => r.code === o.code && r.list === "primary" && r.term === o.term && r.section === s.section);
          return { id: s.id, section: s.section, delivery: s.delivery, meetings: meetings[s.id] || [], cutoff: price ? price.min_rank_value : null, seats: price ? price.seats : null, bids: price ? price.bids : null };
        });
      const exam = regularExams(o).find((e) => e.kind === "exam");
      const prices = DATA.cutoffs.filter((r) => r.code === o.code && r.list === "primary" && r.min_rank_value !== null).map((r) => r.min_rank_value);
      rows.push({
        id: o.id, code: o.code, name: o.name, term: o.term, ects: o.ects, lecturers: o.lecturers, kind: kinds[o.id] || "outside",
        area_role: roles[o.id] || null,
        has_schedule: o.has_schedule, sections: own, exam: exam ? dayLabel(exam.date) : null,
        cutoff_low: prices.length ? Math.min(...prices) : null, cutoff_high: prices.length ? Math.max(...prices) : null,
      });
    });
    const order = { mandatory: 0, elective: 1, outside: 2 };
    const key = (s) => s.split("").map((c) => c.codePointAt(0).toString(16).padStart(5, "0")).join("");
    rows.sort((a, b) => order[a.kind] - order[b.kind] || (key(a.name) < key(b.name) ? -1 : key(a.name) > key(b.name) ? 1 : 0));
    return rows;
  }

  // ---------- changes ----------
  function nextPosition(items, listName) {
    const positions = items.filter((i) => i.list === listName).map((i) => i.position);
    return positions.length ? Math.max(...positions) + 1 : 1;
  }
  function firstFittingSection(items, offeringId) {
    const own = DATA.sections.filter((s) => s.offering_id === offeringId).sort((a, b) => (a.section < b.section ? -1 : 1));
    if (!own.length) return null;
    const week = weekItems(items).filter((e) => e.section_id && e.offering_id !== offeringId);
    const fit = own.find((s) => !week.some((e) => clashingDates(s.id, e.section_id).length));
    return (fit || own[0]).id;
  }
  function add(store, sectionId, offeringId, listName) {
    if (![undefined, null, "mandatory", "primary", "alternate"].includes(listName)) return "Unknown list.";
    if (sectionId) {
      if (!sections[sectionId]) return "Unknown section.";
      offeringId = sections[sectionId].offering_id;
    }
    const o = offerings[offeringId];
    if (!o) return "Unknown course.";
    if (o.semester !== store.plan.semester) return "This course is not offered in the semester of your plan.";
    const same = store.items.filter((i) => i.offering_id === offeringId).sort((a, b) => a.position - b.position);
    if (!sectionId) {
      if (same.length) return "Already in your plan.";
      sectionId = firstFittingSection(store.items, offeringId);
      if (sectionId && (kindsByProgramme[store.plan.programme] || {})[offeringId] === "mandatory") return "Pick the section Nova assigned you.";
    }
    if (same.some((i) => i.section_id === sectionId)) return "Already in your plan.";
    const kinds = kindsByProgramme[store.plan.programme] || {};
    const list = listName || (same.length ? same[0].list : (kinds[offeringId] === "mandatory" ? "mandatory" : "primary"));
    store.items.push({ id: store.next++, offering_id: offeringId, section_id: sectionId, list, position: nextPosition(store.items, list), bid: same.length ? same[0].bid : null });
    return null;
  }
  function switchSection(store, sectionId) {
    if (!sections[sectionId]) return "Unknown section.";
    const same = store.items.filter((i) => i.offering_id === sections[sectionId].offering_id).sort((a, b) => a.position - b.position);
    if (!same.length) return add(store, sectionId, null);
    const first = same[0];
    const backup = same.find((i) => i.section_id === sectionId);
    if (!backup) first.section_id = sectionId;
    else if (backup !== first) {
      [first.position, backup.position] = [backup.position, first.position];
      [first.bid, backup.bid] = [backup.bid, first.bid];
    }
    return null;
  }
  function removeCourse(store, offeringId) {
    const rows = store.items.filter((i) => i.offering_id === offeringId);
    if (!rows.length) return [[], "This course is not in your plan."];
    store.items = store.items.filter((i) => i.offering_id !== offeringId);
    window.__lanceStore = store;
    return [rows.map((r) => ({ offering_id: r.offering_id, section_id: r.section_id, list: r.list, position: r.position, bid: r.bid })), null];
  }
  function restoreItems(store, rows) {
    if (!Array.isArray(rows) || !rows.length) return "Nothing to put back.";
    if (rows.some((row) => store.items.some((i) => i.offering_id === row.offering_id))) return "Already in your plan.";
    rows.forEach((row) => store.items.push({ id: store.next++, offering_id: row.offering_id, section_id: row.section_id, list: row.list, position: row.position, bid: row.bid }));
    return null;
  }
  function startOver(store) {
    store.items = store.items.filter((i) => offerings[i.offering_id].semester !== store.plan.semester);
    window.__lanceStore = store;
    return null;
  }
  function remove(store, itemId) {
    const at = store.items.findIndex((i) => i.id === itemId);
    if (at < 0) return "This entry is not in your plan.";
    store.items.splice(at, 1);
    return null;
  }
  function checkedBid(store, bid) {
    if (bid === "" || bid === null || bid === undefined) return [null, null];
    const value = Number(bid);
    if (!Number.isInteger(value)) return [null, "A bid is a whole number."];
    if (value < 0) return [null, "A bid cannot be negative."];
    if (value > 0 && store.plan.points === 0) return [null, "Enter your points first."];
    if (value > store.plan.points) return [null, `A bid cannot exceed your ${store.plan.points} points.`];
    return [value, null];
  }
  function setBid(store, itemId, bid) {
    const item = store.items.find((i) => i.id === itemId);
    if (!item) return "This entry is not in your plan.";
    if (item.list === "mandatory") return "Mandatory courses need no bid.";
    const [value, error] = checkedBid(store, bid);
    if (error) return error;
    item.bid = value;
    return null;
  }
  function setCourseBid(store, offeringId, bid) {
    const rows = store.items.filter((i) => i.offering_id === offeringId);
    if (!rows.length) return "This course is not in your plan.";
    if (rows[0].list === "mandatory") return "Mandatory courses need no bid.";
    const [value, error] = checkedBid(store, bid);
    if (error) return error;
    rows.forEach((row) => { row.bid = value; });
    return null;
  }
  function move(store, itemId, listName, direction) {
    const item = store.items.find((i) => i.id === itemId);
    if (!item) return "This entry is not in your plan.";
    if (listName && listName !== item.list) {
      let position = nextPosition(store.items, listName);
      store.items.filter((e) => e.offering_id === item.offering_id).forEach((e) => { e.list = listName; e.position = position; position += 1; });
      return null;
    }
    if (direction === "up" || direction === "down") {
      const order = store.items.filter((e) => e.list === item.list).sort((a, b) => a.position - b.position);
      const courses = [];
      order.forEach((e) => { if (!courses.includes(e.offering_id)) courses.push(e.offering_id); });
      const index = courses.indexOf(item.offering_id);
      const swap = direction === "up" ? index - 1 : index + 1;
      if (swap >= 0 && swap < courses.length) { [courses[index], courses[swap]] = [courses[swap], courses[index]]; }
      let position = 1;
      courses.forEach((id) => order.filter((e) => e.offering_id === id).forEach((e) => { e.position = position; position += 1; }));
    }
    return null;
  }
  function settings(store, data) {
    const value = Number(data.points === undefined ? store.plan.points : data.points);
    if (!Number.isInteger(value)) return "Points are a whole number.";
    if (value < 0 || value > 2000) return "Points must be between 0 and 2000.";
    if (data.programme && !kindsByProgramme[data.programme]) return "Unknown programme.";
    /* LN R20: no area given keeps the chosen one, but another programme has other areas */
    let area = data.area === undefined || data.area === null ? null : data.area;
    if (area === null && (data.programme || store.plan.programme) !== store.plan.programme) area = "";
    if (area && !areasOf(data.programme || store.plan.programme).includes(area)) return "Unknown area of expertise.";
    if (area !== null) store.plan.area = area;
    const programmeBefore = store.plan.programme;
    store.plan.programme = data.programme || store.plan.programme;
    if (store.plan.programme !== programmeBefore) {
      const kinds = kindsByProgramme[store.plan.programme] || {};
      store.items.slice().sort((a, b) => a.list.localeCompare(b.list) || a.position - b.position || a.id - b.id).forEach((item) => {
        const mandatory = kinds[item.offering_id] === "mandatory";
        if (item.list === "mandatory" && !mandatory) move(store, item.id, "primary");
        else if (item.list === "primary" && mandatory) move(store, item.id, "mandatory");
      });
    }
    store.plan.semester = data.semester || store.plan.semester;
    store.plan.points = value;
    store.plan.has_bonus = (data.has_bonus === undefined ? store.plan.has_bonus : data.has_bonus) ? 1 : 0;
    return null;
  }
  function example(store) {
    if (planItems(store).length) return "Your plan already has courses.";
    store.plan.programme = "Management"; store.plan.semester = "Fall"; store.plan.points = 165; store.plan.has_bonus = 0; store.plan.area = "";
    const positions = {};
    DATA.example.forEach(([sectionId, listName, bid]) => {
      positions[listName] = (positions[listName] || 0) + 1;
      store.items.push({ id: store.next++, offering_id: sections[sectionId].offering_id, section_id: sectionId, list: listName, position: positions[listName], bid });
    });
    return null;
  }

  // ---------- the same addresses as the real server ----------
  const json = (body, status) => new Response(JSON.stringify(body), { status: status || 200, headers: { "Content-Type": "application/json" } });
  window.fetch = async function (input, options) {
    const url = typeof input === "string" ? input : input.url;
    if (!url.startsWith("/api/")) return realFetch(input, options);
    await ready;
    if (url.startsWith("/api/sheet/")) {
      /* the course sheets were rendered once on the server and wait in one file */
      sheets = sheets || await (await realFetch("courses.json")).json();
      const html = sheets[decodeURIComponent(url.slice("/api/sheet/".length))];
      return html ? new Response(html, { status: 200 }) : new Response("", { status: 404 });
    }
    const store = load();
    const body = options && options.body ? JSON.parse(options.body) : {};
    let error = null;
    if (url === "/api/state") return json({ error: null, state: stateOf(store) });
    if (url === "/api/catalogue") return json(catalogue(store));
    if (url === "/api/add") error = add(store, body.section_id, body.offering_id, body.list);
    else if (url === "/api/remove") {
      if (body.offering_id) {
        const [removed, problem] = removeCourse(store, body.offering_id);
        save();
        return json({ error: problem, removed, state: stateOf(store) });
      }
      error = remove(store, body.item_id);
    }
    else if (url === "/api/restore") error = restoreItems(store, body.rows);
    else if (url === "/api/switch") error = switchSection(store, body.section_id);
    else if (url === "/api/start-over") error = startOver(store);
    else if (url === "/api/bid") error = body.offering_id ? setCourseBid(store, body.offering_id, body.bid) : setBid(store, body.item_id, body.bid);
    else if (url === "/api/move") error = move(store, body.item_id, body.list, body.direction);
    else if (url === "/api/settings") error = settings(store, body);
    else if (url === "/api/example") error = example(store);
    else if (url === "/api/share") return json({ error: "The preview cannot store shared lists. The full app can.", stored: 0 }, 400);
    else return new Response("", { status: 404 });
    save();
    return json({ error, state: stateOf(store) });
  };

  /* a rating form cannot be stored without a server */
  if (typeof document !== "undefined") {
    document.addEventListener("submit", (event) => {
      if (!event.target.matches(".rate-form")) return;
      event.preventDefault();
      Lance.toast("The preview does not store ratings. The full app does.");
    });
  }

  /* for preview/check_parity.py */
  window.__lanceLocal = { ready, stateOf, catalogue, add, setBid, move, settings, example, blank, switchSection, removeCourse, restoreItems, setCourseBid };
})();
