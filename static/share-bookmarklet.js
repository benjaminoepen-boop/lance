(async function () {
  var wait = function (ms) { return new Promise(function (done) { setTimeout(done, ms); }); };
  var openWindow = function () { return document.querySelector(".modal.in, .modal.show"); };
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
  var heads = function (table) { return Array.prototype.map.call(table.rows[0].cells, function (cell) { return cell.innerText.trim(); }); };
  var note = document.createElement("div");
  note.style.cssText = "position:fixed;top:12px;right:12px;z-index:99999;background:#1d1d1f;color:#fff;padding:10px 14px;border-radius:8px;font:14px sans-serif";
  document.body.appendChild(note);
  var lists = [];
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
    var tables = Array.prototype.filter.call((document.querySelector("#bidding") || document).querySelectorAll("table"), function (t) { return t.rows[0] && heads(t).indexOf("Vacancies") >= 0; });
    var listName = tables.indexOf(table) === 0 ? "primary" : "alternate";
    link.click();
    for (var tries = 0; tries < 40 && !(openWindow() && openWindow().querySelector("table")); tries += 1) { await wait(250); }
    var first = Array.prototype.find.call(openWindow().querySelectorAll("a"), function (a) { return a.innerText.trim() === "1"; });
    if (first) { first.click(); await wait(2000); }
    var rows = [];
    var page = 1;
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
      var next = Array.prototype.find.call(openWindow().querySelectorAll("a"), function (a) { return a.innerText.trim() === String(page); });
      if (!next) { break; }
      next.click();
      await wait(2000);
    }
    var close = openWindow().querySelector(".close");
    if (close) { close.click(); }
    await wait(900);
    lists.push({ code: course.split(" - ")[0].trim(), term: term, section: section, list: listName, seats: seats, year: year, rows: rows });
  }
  var text = JSON.stringify({ lists: lists });
  note.textContent = "Lance: " + total + " sections read. Press Copy, then paste in Lance.";
  var area = document.createElement("textarea");
  area.value = text;
  area.style.cssText = "position:fixed;top:60px;right:12px;width:320px;height:90px;z-index:99999";
  document.body.appendChild(area);
  var button = document.createElement("button");
  button.textContent = "Copy";
  button.style.cssText = "position:fixed;top:158px;right:12px;z-index:99999;padding:8px 14px";
  button.addEventListener("click", function () { area.select(); document.execCommand("copy"); button.textContent = "Copied"; });
  document.body.appendChild(button);
})();
