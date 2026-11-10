/* What every page shares: talking to the server, small messages, building elements. */
const Lance = {
  state: null,

  /* the addresses the scripts link to, in one place */
  pages: { courses: "/", bids: "/bids", share: "/share", nova: "/nova", rules: "/rules" },
  courseHref(id) { return `/#${id}`; },

  async send(path, body) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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
  /* a redraw between pressing and releasing the mouse would swallow the click, so it waits for the release */
  pressed: false,
  redrawLater: false,
  update(state) {
    Lance.state = state;
    if (Lance.pressed) { Lance.redrawLater = true; return; }
    Lance.listeners.forEach((listener) => listener(state));
  },

  /* remembers small things for this visit, like the half of the semester on show; if the browser refuses, it simply forgets */
  remember(key, value) {
    try {
      if (value === undefined) return sessionStorage.getItem(`lance-${key}`);
      sessionStorage.setItem(`lance-${key}`, value);
    } catch (error) { /* private window */ }
    return value;
  },

  /* a short message; with an action it also offers one thing to do about it, like Undo */
  toast(message, action) {
    const toast = document.getElementById("toast");
    toast.replaceChildren(Lance.el("span", { text: message }));
    if (action) {
      toast.append(Lance.el("button", { type: "button", onclick: () => { toast.hidden = true; action.run(); } }, action.label));
    }
    toast.hidden = false;
    clearTimeout(Lance.toastTimer);
    Lance.toastTimer = setTimeout(() => { toast.hidden = true; }, action ? 6000 : 3500);
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

  /* the two signs a row can show */
  icons: {
    plus: '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" aria-hidden="true"><path d="M7 2v10M2 7h10"/></svg>',
    tick: '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2.5 7.5 5.5 10.5 11.5 3.5"/></svg>',
    down: '<svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2.5 4.5 6 8l3.5-3.5"/></svg>',
    next: '<svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5.5 2.5 10 7l-4.5 4.5"/></svg>',
    back: '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8.5 2.5 4 7l4.5 4.5"/></svg>',
    close: '<svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M2 2l8 8M10 2l-8 8"/></svg>',
    help: '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true"><circle cx="8" cy="8" r="6.5"/><path d="M6.2 6.3a1.9 1.9 0 1 1 2.6 1.8c-.5.2-.8.6-.8 1.1v.4"/><circle cx="8" cy="11.5" r=".5" fill="currentColor" stroke="none"/></svg>',
    dots: '<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><circle cx="3" cy="8" r="1.4"/><circle cx="8" cy="8" r="1.4"/><circle cx="13" cy="8" r="1.4"/></svg>',
  },
};

document.addEventListener("pointerdown", () => { Lance.pressed = true; }, true);
const released = () => {
  Lance.pressed = false;
  if (Lance.redrawLater) {
    Lance.redrawLater = false;
    setTimeout(() => Lance.update(Lance.state), 0);
  }
};
document.addEventListener("pointerup", released, true);
document.addEventListener("pointercancel", released, true);   /* a finger that starts scrolling */
