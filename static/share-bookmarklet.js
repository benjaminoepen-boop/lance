(async function () {
  var wait = function (ms) { return new Promise(function (done) { setTimeout(done, ms); }); };
  var openWindow = function () { return document.querySelector(".modal.in, .modal.show"); };
  var until = async function (test, seconds) {
    for (var tries = 0; tries < seconds * 4; tries += 1) {
      if (test()) { return true; }
      await wait(250);
    }
    return false;
  };
  var infoLinks = function () {
    var area = document.querySelector("#bidding") || document;
    return area.querySelectorAll('a[title="View Rank Information"]');
  };
  if (!infoLinks().length) { alert("Open the tab Rank of the bidding platform first."); return; }
  var TERMS = { "1st Semester": "S1", "2nd Semester": "S2", "1st Half/1st Sem (Trim1)": "T1", "2nd Half/1st Sem (Trim2)": "T2", "1st Half/2nd Sem (Trim3)": "T3", "2nd Half/2nd Sem(Trim4)": "T4" };
  var year = "2026/2027";
  document.querySelectorAll("select").forEach(function (select) {
    var option = select.options[select.selectedIndex];
    if (option && /^\d{4}\/\d{4}$/.test(option.text.trim())) { year = option.text.trim(); }
  });
  /* the platform's old Prototype.js replaces Array methods, so collections are spread into real arrays first */
  var heads = function (table) { return [...table.rows[0].cells].map(function (cell) { return cell.innerText.trim(); }); };
  var note = document.createElement("div");
  note.style.cssText = "position:fixed;top:12px;right:12px;z-index:99999;background:#1d1d1f;color:#fff;padding:10px 14px;border-radius:8px;font:14px sans-serif;max-width:340px";
  document.body.appendChild(note);
  var pager = function (label) { return [...openWindow().querySelectorAll("a")].find(function (a) { return a.innerText.trim() === label; }); };
  var firstRow = function () {
    var inner = openWindow() && openWindow().querySelector("table");
    return inner && inner.rows[1] ? inner.rows[1].cells[0].innerText.trim() : "";
  };
  var flip = async function (link) {
    var before = firstRow();
    link.click();
    return until(function () { return firstRow() && firstRow() !== before; }, 30);
  };
  var lists = [];
  var skipped = 0;
  var total = infoLinks().length;
  for (var i = 0; i < total; i += 1) {
    note.textContent = "Lance: reading section " + (i + 1) + " of " + total + " ...";
    var link = infoLinks()[i];
    var row = link.closest("tr");
    var table = link.closest("table");
    var names = heads(table);
    var cell = function (name) { return row.cells[names.indexOf(name)].innerText.trim(); };
    var course = cell("Course Description");
    var section = cell("Section");
    var term = TERMS[cell("Term")];
    var seats = parseInt(cell("Vacancies"), 10) || 0;
    var tables = [...(document.querySelector("#bidding") || document).querySelectorAll("table")].filter(function (t) { return t.rows[0] && heads(t).indexOf("Vacancies") >= 0; });
    var listName = tables.indexOf(table) === 0 ? "primary" : "alternate";
    link.click();
    if (!(await until(function () { return firstRow(); }, 40))) { skipped += 1; continue; }
    /* the platform remembers the page it showed last: go back to page 1 */
    if (pager("1")) { await flip(pager("1")); }
    var rows = [];
    var page = 1;
    var complete = true;
    while (true) {
      var inner = openWindow().querySelector("table");
      var columns = heads(inner);
      var final = columns.indexOf("Final Bid");
      var bid = columns.indexOf("Bid");
      var won = columns.indexOf("Alocated");
      for (var r = 1; r < inner.rows.length; r += 1) {
        var cells = inner.rows[r].cells;
        rows.push({ final: parseFloat(cells[final].innerText), bid: parseFloat(cells[bid].innerText), allocated: !!cells[won].querySelector(".glyphicon-check") });
      }
      page += 1;
      var next = pager(String(page));
      if (!next) { break; }
      if (!(await flip(next))) { complete = false; break; }
    }
    var close = openWindow().querySelector(".close");
    if (close) { close.click(); }
    await until(function () { return !openWindow(); }, 10);
    await wait(400);
    if (complete && term) {
      lists.push({ code: course.split(" - ")[0].trim(), term: term, section: section, list: listName, seats: seats, year: year, rows: rows });
    } else {
      skipped += 1;
    }
  }
  note.textContent = "Lance: " + lists.length + " of " + total + " sections read" + (skipped ? " (the platform was too slow for " + skipped + ")" : "") + ". Press Copy, then paste in Lance.";
  var area = document.createElement("textarea");
  var oldToJSON = Array.prototype.toJSON;
  delete Array.prototype.toJSON;
  area.value = JSON.stringify({ lists: lists });
  if (oldToJSON) { Array.prototype.toJSON = oldToJSON; }
  area.style.cssText = "position:fixed;top:64px;right:12px;width:320px;height:90px;z-index:99999";
  document.body.appendChild(area);
  var button = document.createElement("button");
  button.textContent = "Copy";
  button.style.cssText = "position:fixed;top:162px;right:12px;z-index:99999;padding:8px 14px";
  button.addEventListener("click", function () { area.select(); document.execCommand("copy"); button.textContent = "Copied"; });
  document.body.appendChild(button);
})().catch(function () { alert("Lance could not finish. Reload the Rank tab and try again."); });
