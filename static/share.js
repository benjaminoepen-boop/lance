/* Sends a pasted export to the server and shows how far the pooled data has come. */
document.getElementById("send").addEventListener("click", async () => {
  const result = document.getElementById("share-result");
  const box = document.getElementById("export");
  const response = await fetch("/api/share", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ export: box.value }),
  });
  const answer = await response.json();
  if (answer.error) {
    result.textContent = answer.error;
    result.style.color = "var(--red)";
    return;
  }
  box.value = "";
  result.style.color = "var(--green)";
  result.textContent = answer.stored === 1 ? "1 rank list added. Thank you!" : `${answer.stored} rank lists added. Thank you!`;
  document.getElementById("coverage-text").textContent = `${answer.coverage.covered} of ${answer.coverage.total}`;
  document.getElementById("coverage-bar").style.width = `${answer.coverage.percent}%`;
});
