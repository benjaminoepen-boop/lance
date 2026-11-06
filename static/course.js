/* The course sheet: adding and removing a section here, then showing the fresh page. */
document.querySelectorAll("[data-section],[data-offering]").forEach((button) => {
  button.addEventListener("click", async () => {
    if (button.dataset.item) {
      await Lance.send("/api/remove", { item_id: Number(button.dataset.item) });
    } else if (button.dataset.section) {
      await Lance.send("/api/add", { section_id: button.dataset.section });
    } else {
      await Lance.send("/api/add", { offering_id: button.dataset.offering });
    }
    window.location.reload();
  });
});
