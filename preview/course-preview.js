/* The course sheet of the preview: one shell page, the sheet comes from courses.json by the name after the # */
(async function () {
  const slot = document.getElementById("sheet-slot");
  const id = decodeURIComponent(location.hash.slice(1)) || "2477-S1";
  const sheets = await (await fetch("courses.json")).json();
  slot.innerHTML = sheets[id] || '<section class="card"><p class="muted">This course is not in the preview.</p></section>';
  document.title = "Lance · " + (slot.querySelector("h1") ? slot.querySelector("h1").textContent : "Course");
  /* the sheet was rendered once on the server: bring its buttons in line with this browser's plan */
  const answer = await (await fetch("/api/state")).json();
  Lance.update(answer.state);
  const refresh = () => {
    document.querySelectorAll("[data-section],[data-offering]").forEach((button) => {
      const item = Lance.state.items.find((entry) => button.dataset.section ? entry.section_id === button.dataset.section : entry.offering_id === button.dataset.offering);
      button.dataset.item = item ? item.id : "";
      button.textContent = item ? "In your plan" : (button.dataset.section ? "Add" : "Add to my plan");
      button.classList.toggle("primary", Boolean(item));
      const offering = button.dataset.section ? button.dataset.section.split("-").slice(0, 2).join("-") : button.dataset.offering;
      const term = offering.split("-")[1];
      const semester = ["S1", "T1", "T2"].includes(term) ? "Fall" : "Spring";
      button.disabled = semester !== Lance.state.plan.semester;
    });
  };
  refresh();
  Lance.onChange(refresh);
  document.querySelectorAll("[data-section],[data-offering]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.item) Lance.send("/api/remove", { item_id: Number(button.dataset.item) });
      else if (button.dataset.section) Lance.send("/api/add", { section_id: button.dataset.section });
      else Lance.send("/api/add", { offering_id: button.dataset.offering });
    });
  });
  const form = slot.querySelector(".rate-form");
  if (form) {
    form.addEventListener("submit", (event) => { event.preventDefault(); Lance.toast("The preview does not store ratings. The full app does."); });
  }
})();
