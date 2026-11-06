/* The checklist remembers its ticks on this device. If the browser refuses, it simply starts empty. */
document.querySelectorAll("[data-check]").forEach((box) => {
  const key = "lance-check-" + box.dataset.check;
  try { box.checked = localStorage.getItem(key) === "1"; } catch (error) { /* private window */ }
  box.addEventListener("change", () => {
    try { localStorage.setItem(key, box.checked ? "1" : "0"); } catch (error) { /* private window */ }
  });
});
