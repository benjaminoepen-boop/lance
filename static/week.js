/* The week: Monday to Friday on Nova's real time slots. This file only draws blocks; planner.js decides what they are. */
const Week = (() => {
  const { el } = Lance;
  const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"];
  const SLOT = 90;               /* Nova teaches in blocks of 90 minutes, from 8:00 on */
  const FIRST = 8 * 60;
  const USUAL_END = 20 * 60;

  const minutes = (clock) => { const [h, m] = clock.split(":"); return Number(h) * 60 + Number(m); };
  const clock = (total) => `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;

  const overlap = (a, b) => minutes(a.start) < minutes(b.end) && minutes(b.start) < minutes(a.end);

  /* blocks that overlap stand side by side: each gets a column inside its group.
     Real blocks take the left columns, ghosts go beside them, so a ghost never hides what it clashes with. */
  function layOut(blocks) {
    const groups = [];
    blocks.slice().sort((a, b) => minutes(a.start) - minutes(b.start) || minutes(b.end) - minutes(a.end)).forEach((block) => {
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
      group.items.slice().sort((a, b) => Number(Boolean(a.ghost)) - Number(Boolean(b.ghost))).forEach((block) => {
        let column = columns.findIndex((taken) => taken.every((other) => !overlap(other, block)));
        if (column === -1) { columns.push([]); column = columns.length - 1; }
        columns[column].push(block);
        block.column = column;
      });
      group.items.forEach((block) => {
        block.columns = columns.length;
        block.beside = !block.ghost && group.items.some((other) => other !== block && !other.ghost && overlap(block, other));
      });
    });
    return blocks;
  }

  function blockNode(block, percent) {
    const width = 100 / block.columns;
    /* of a clashing course, only the block that really has another one next to it */
    return el("button", {
      type: "button",
      class: `block ${block.class}${block.clashing && block.beside ? " clash" : ""}`,
      title: block.title,
      "data-section": block.sectionId,
      style: `top:${percent(minutes(block.start))}%;height:calc(${percent(minutes(block.end)) - percent(minutes(block.start))}% - 2px);left:calc(${block.column * width}% + 1px);width:calc(${width}% - 2px)`,
      onclick: block.onclick,
      onmouseenter: block.onmouseenter,
      onmouseleave: block.onmouseleave,
    }, el("b", { text: block.name }), block.section ? el("span", {}, block.section, block.room ? el("span", { class: "room", style: "display:inline", text: ` · ${block.room}` }) : null) : null);
  }

  /* blocks and ghosts: [{ day, start, end, title, name, section, room, sectionId, class, clashing, onclick, onmouseenter, onmouseleave }] */
  function draw(days, grid, blocks, ghosts, half) {
    const end = Math.max(USUAL_END, ...blocks.concat(ghosts).map((block) => minutes(block.end)));
    const last = FIRST + Math.ceil((end - FIRST) / SLOT) * SLOT;
    const percent = (at) => ((at - FIRST) / (last - FIRST)) * 100;

    days.replaceChildren(el("div", { class: "week-half", text: half }), ...DAYS.map((day) => el("div", { class: "week-head", text: day })));
    const hours = el("div", { class: "hours" });
    for (let at = FIRST; at < last; at += SLOT) {
      hours.append(el("span", { class: "hour-label", style: `top:${percent(at)}%`, text: clock(at) }));
    }
    grid.replaceChildren(hours);
    DAYS.forEach((day) => {
      const column = el("div", { class: "day" });
      for (let at = FIRST; at <= last; at += SLOT) {
        column.append(el("div", { class: "slot-line", style: `top:${percent(at)}%` }));
      }
      const today = blocks.filter((block) => block.day === day).concat(ghosts.filter((block) => block.day === day).map((block) => ({ ...block, ghost: true })));
      layOut(today).forEach((block) => column.append(blockNode(block, percent)));
      grid.append(column);
    });
  }

  return { draw };
})();
