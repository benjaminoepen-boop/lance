/* What every page shares: talking to the server, the head card, small messages. */
const Lance = {
  state: null,

  async send(path, body) {
    const response = await fetch(path, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body || {}),
    });
    const answer = await response.json();
    if (answer.error) Lance.toast(answer.error);
    if (answer.state) Lance.update(answer.state);
    return answer;
  },

  async load() {
    const response = await fetch("/api/state");
    const answer = await response.json();
    Lance.update(answer.state);
  },

  listeners: [],
  onChange(listener) { Lance.listeners.push(listener); },
  update(state) {
    Lance.state = state;
    Lance.renderHead(state);
    Lance.listeners.forEach((listener) => listener(state));
  },

  renderHead(state) {
    /* the settings follow the saved plan, except the field someone is typing in */
    const sync = (id, apply) => { const field = document.getElementById(id); if (field && field !== document.activeElement) apply(field); };
    sync("set-programme", (field) => { field.value = state.plan.programme; });
    sync("set-points", (field) => { field.value = state.plan.points; });
    sync("set-bonus", (field) => { field.checked = Boolean(state.plan.has_bonus); });
    document.querySelectorAll("[data-semester]").forEach((button) => button.classList.toggle("on", button.dataset.semester === state.plan.semester));
    const set = (id, value, label, tone) => {
      const kpi = document.getElementById(id);
      if (!kpi) return;
      kpi.querySelector("b").textContent = value;
      if (label) kpi.querySelector("span").textContent = label;
      kpi.classList.toggle("bad", tone === "bad");
      kpi.classList.toggle("good", tone === "good");
    };
    const ects = state.ects;
    set("kpi-ects", `${ects.total} / ${ects.recommended}`, ects.over ? `ECTS, max ${ects.maximum}` : "ECTS", ects.over ? "bad" : null);
    set("kpi-points", `${state.reserved} / ${state.plan.points}`, "points bid", state.reserved > state.plan.points ? "bad" : null);
    const hard = state.clashes.length;
    set("kpi-clashes", String(hard), hard === 1 ? "clash" : "clashes", hard ? "bad" : (state.items.length ? "good" : null));
    if (state.next_deadline) {
      const days = state.next_deadline.days;
      set("kpi-next", days === 0 ? "now" : `${days} days`, state.next_deadline.label.replace(" (bidding)", ""));
    }
  },

  toast(message) {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.hidden = false;
    clearTimeout(Lance.toastTimer);
    Lance.toastTimer = setTimeout(() => { toast.hidden = true; }, 3500);
  },

  async copy(text, done) {
    try {
      await navigator.clipboard.writeText(text);
      Lance.toast(done);
    } catch (error) {
      Lance.toast("Copying is blocked here. Select the text and copy it yourself.");
    }
  },

  /* tiny helper: text must never be written as HTML, course names come from a PDF */
  el(tag, attrs, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs || {})) {
      if (value === undefined || value === null || value === false) continue;
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key === "html") node.innerHTML = value;
      else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
      else if (key === "style") node.style.cssText = value;
      else node.setAttribute(key, value === true ? "" : value);
    }
    for (const child of children) {
      if (child !== null && child !== undefined && child !== false) node.append(child);
    }
    return node;
  },
};

/* ---- the settings in the head card ---- */
function wireSettings() {
  const programme = document.getElementById("set-programme");
  if (!programme) return;
  const points = document.getElementById("set-points");
  const bonus = document.getElementById("set-bonus");
  programme.addEventListener("change", async () => {
    await Lance.send("/api/settings", {programme: programme.value});
    document.dispatchEvent(new Event("lance:catalogue"));
  });
  points.addEventListener("change", () => Lance.send("/api/settings", {points: points.value}));
  bonus.addEventListener("change", () => Lance.send("/api/settings", {has_bonus: bonus.checked}));
  document.querySelectorAll("[data-semester]").forEach((button) => {
    button.addEventListener("click", async () => {
      document.querySelectorAll("[data-semester]").forEach((other) => other.classList.toggle("on", other === button));
      await Lance.send("/api/settings", {semester: button.dataset.semester});
      document.dispatchEvent(new Event("lance:catalogue"));
    });
  });
}
wireSettings();
