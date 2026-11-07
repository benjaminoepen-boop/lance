/* Step 3: what to do on Nova's platform. Everything shown here comes from the plan the server holds. */
const { el } = Lance;

function coursesOf(state, list) {
  const items = state.items.filter((item) => item.list === list).sort((a, b) => a.position - b.position);
  return [...new Set(items.map((item) => item.offering_id))].map((id) => items.filter((item) => item.offering_id === id));
}

/* the order counts on the primary list only, so only that list has numbers */
function listBlock(title, rows, numbered) {
  if (!rows.length) return [];
  return [
    el("div", { class: "small strong muted", style: "margin-top:4px", text: title }),
    ...rows.map((sections, index) => el("div", { class: "platform-row" },
      el("span", { class: "n", text: numbered ? String(index + 1) : "·" }),
      el("div", {},
        el("div", { text: sections[0].name }),
        el("div", { class: "bids", text: `${sections[0].code} · ${sections[0].term} · ${sections.map((item) => `${item.section || "section to choose"} ${item.bid === null ? "no bid" : item.bid}`).join(", ")}` })))),
  ];
}

/* the round of this plan's semester, and if it is over, the next one */
function roundLine(state) {
  const round = state.round;
  const box = document.getElementById("round-line");
  if (!round) { box.replaceChildren(); return; }
  if (round.status === "closed") {
    const next = state.next_deadline;
    box.replaceChildren(`The ${state.plan.semester} round closed on ${round.last_day}, so this plan is practice.`,
      next ? ` Next: ${next.label.replace(" (bidding)", "")}, ${next.range}. ` : " ",
      state.plan.semester === "Fall" ? el("button", {
        type: "button", class: "link-btn",
        onclick: async () => {
          await Lance.send("/api/settings", { semester: "Spring" });
          Lance.toast("Now planning spring. Your fall plan stays saved.", { label: "Back to fall", run: () => Lance.send("/api/settings", { semester: "Fall" }) });
        },
      }, "Plan for spring") : null);
    return;
  }
  box.textContent = `${round.label.replace(" (bidding)", "")}: ${round.range}${round.status === "open" ? ", open now." : `, in ${round.days} days.`}`;
}

function beforeYouGo(state) {
  const pages = { bids: Lance.pages.bids, courses: Lance.pages.courses };
  const rows = [
    ...state.clashes.map((clash) => ({ level: clash.kind === "exam" ? "stop" : "note", where: "courses", text: `${clash.first} × ${clash.second}: ${clash.when}` })),
    ...state.warnings,
  ];
  document.getElementById("before").hidden = !rows.length;
  document.getElementById("before-list").replaceChildren(...rows.map((row) => el("div", { class: `figure small ${row.level === "stop" ? "bad" : "warn"}` },
    el("span", { text: row.text }), el("a", { href: pages[row.where], style: "white-space:nowrap", text: row.where === "bids" ? "To bids" : "To courses" }))));
}

function render(state) {
  roundLine(state);
  beforeYouGo(state);
  const lists = document.getElementById("platform-lists");
  const blocks = [...listBlock("Primary list", coursesOf(state, "primary"), true), ...listBlock("Alternate list", coursesOf(state, "alternate"), false)];
  if (blocks.length) {
    lists.replaceChildren(...blocks);
  } else {
    lists.replaceChildren(el("p", { class: "muted" }, "Nothing yet. ", el("a", { href: Lance.pages.courses, text: "Pick courses first." })));
  }
  const file = document.getElementById("calendar-file");
  if (file) file.hidden = !state.items.length;
}

const copyList = () => {
  if (!Lance.state.platform_list) { Lance.toast("Nothing to copy yet."); return; }
  Lance.copy(Lance.state.platform_list, "Copied. Keep it next to you on Nova's platform.");
};
document.getElementById("copy-list").addEventListener("click", copyList);
document.getElementById("copy-list-phone").addEventListener("click", copyList);
const linkButton = document.getElementById("copy-link");
if (linkButton.dataset.link) {
  linkButton.addEventListener("click", () => Lance.copy(linkButton.dataset.link, "Link copied. It opens this same plan on another device, so keep it to yourself."));
}
/* the checklist remembers its ticks on this device; if the browser refuses, it simply starts empty */
document.querySelectorAll("[data-check]").forEach((box) => {
  const key = `lance-check-${box.dataset.check}`;
  try { box.checked = localStorage.getItem(key) === "1"; } catch (error) { /* private window */ }
  box.addEventListener("change", () => {
    try { localStorage.setItem(key, box.checked ? "1" : "0"); } catch (error) { /* private window */ }
  });
});
Lance.onChange(render);
Lance.load();
