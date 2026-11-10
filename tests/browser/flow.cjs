/* The whole way through Lance in real browsers: what a student clicks, and what must then be on the screen.
   The rules are tested in pytest; this checks that the pages use them.

   Start a server first:  LANCE_DB=/tmp/flow.db uv run flask --app app run --port 8771
   Then:                  NODE_PATH=<folder with playwright>/node_modules node tests/browser/flow.cjs [base address] [c|w|a|all]
   c = Chromium on a laptop, s = a small laptop, w = Safari on an iPhone, a = Chrome on an Android phone.
   The static preview: serve the folder preview/ (python3 -m http.server) and give the address of its out folder.
   Every run starts with an empty browser, so it does not matter what the database already holds. */
const { chromium, webkit, devices } = require("playwright");
const BASE = process.argv[2] || "http://127.0.0.1:8771";
const WHICH = process.argv[3] || "all";
const PREVIEW = /preview|\/out\/?$/.test(BASE);
const results = [];
const check = (name, ok, detail) => results.push({ name, ok: Boolean(ok), detail: ok ? "" : String(detail === undefined ? "" : detail) });

async function run(browserType, label, options) {
  const browser = await browserType.launch();
  const context = await browser.newContext(options);
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(`${error.message} @ ${page.url()}`));
  page.on("console", (message) => { if (message.type() === "error" && !message.text().includes("status of 400")) errors.push(message.text()); });
  page.on("dialog", (dialog) => dialog.accept());
  const phone = Boolean(options.isMobile);
  const n = (text) => `${label}: ${text}`;
  const url = (address) => (PREVIEW ? BASE + { "/": "/index.html", "/bids": "/bids.html", "/nova": "/nova.html", "/rules": "/rules.html", "/share": "/share.html" }[address] : BASE + address);
  const noSideways = async (where) => check(n(`${where} does not scroll sideways`), await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1));
  /* the courses are on the left, your plan on the right with the tabs Week, Bids and Summary.
     A phone shows one half at a time: the bar at the bottom changes it, and the summary sits under the week. */
  const toWeek = async () => {
    if (phone) { await page.locator(".tabbar [data-tab=week]").click(); await page.waitForTimeout(120); }
    else if ((await page.locator("#tab-week").getAttribute("aria-selected")) !== "true") { await page.locator("#tab-week").click(); await page.waitForTimeout(120); }
  };
  const toSummary = async () => {
    if (phone) await toWeek();
    else { await page.locator("#tab-summary").click(); await page.waitForTimeout(120); }
  };
  const toCourses = async () => { if (phone) { await page.locator(".tabbar [data-tab=courses]").click(); await page.waitForTimeout(120); } };
  const row = (name) => page.locator("#courses .course", { hasText: name }).first();
  const bidCard = (name) => page.locator("#bid-lists .bid-row", { hasText: name });
  const toast = () => page.locator("#toast");
  const sectionRow = (name) => page.locator("#sheet-sections .tile").filter({ has: page.locator("b", { hasText: new RegExp(`^${name}$`) }) });

  run.page = page;
  /* ---- the first look ---- */
  await page.goto(url("/"));
  await page.waitForSelector("#courses .course");
  await noSideways("the first screen");
  if (!phone) {
    check(n("the page fits the window"), await page.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight + 1));
    check(n("the empty week says what to do"), await page.getByText("Choose your programme, then press + on a course.").isVisible());
    check(n("no filter for a week that is still empty"), !(await page.locator("#fits").isVisible()));
  }
  await page.selectOption("#set-programme", "Management");
  await page.waitForFunction(() => document.querySelector("#courses") && document.querySelector("#courses").textContent.includes("Mandatory"));
  const subs = await page.locator("#courses .course-sub").allTextContents();
  check(n("T1 shows only T1 and S1 courses"), subs.length > 5 && subs.every((text) => /^(S1|T1)/.test(text)), subs.slice(0, 4));
  /* every row: name, chevron, then its control (Pick or +) at the right edge, all controls ending on one line */
  const edges = await page.locator("#courses .course").evaluateAll((rows) => rows.slice(0, 10).map((course) => {
    const box = course.getBoundingClientRect();
    const control = course.querySelector(".course-head > .control > button").getBoundingClientRect();
    const chevron = course.querySelector(".course-main > .i").getBoundingClientRect();
    const name = course.querySelector(".course-name").getBoundingClientRect();
    return { gap: Math.round(box.right - control.right), right: Math.round(control.right), order: name.right <= chevron.left + 1 && chevron.right <= control.left };
  }));
  check(n("the control sits at the right edge of the row"), edges.length === 10 && edges.every((edge) => edge.gap >= 0 && edge.gap <= 12 && edge.order) && new Set(edges.map((edge) => edge.right)).size === 1, JSON.stringify(edges.slice(0, 3)));

  /* ---- search looks through all terms ---- */
  await page.fill("#search", "impact investments");
  await page.waitForTimeout(120);
  check(n("a search finds a T2 course while T1 is showing"), await row("Impact Investments").isVisible());
  await page.fill("#search", "programming");
  await page.waitForTimeout(120);

  /* ---- plus adds at once ---- */
  await row("Introduction to Programming").locator(".pick").click();
  await page.waitForFunction(() => document.querySelector("#toast") && !document.querySelector("#toast").hidden);
  check(n("the toast names the section"), (await toast().textContent()).includes("Introduction to Programming TXA"), await toast().textContent());
  check(n("the plus became a tick"), (await row("Introduction to Programming").locator(".pick").getAttribute("aria-pressed")) === "true");
  check(n("the row folds open with its sections to pick from"), (await row("Introduction to Programming").locator(".tile").count()) === 3);
  check(n("the section it took is marked"), (await row("Introduction to Programming").locator(".tile.on").textContent()).includes("TXA"));
  await toWeek();
  check(n("the course is in the week"), await page.locator("#week .block", { hasText: "Introduction to Programming" }).first().isVisible());
  await toCourses();
  await page.fill("#search", "");
  await page.waitForTimeout(120);
  check(n("your plan counts it"), (await page.locator("#ects").textContent()).startsWith("7 ECTS"), await page.locator("#figures").textContent());
  /* a phone has no plan beside the list: the same figures stand above it, so a + shows what it changed */
  if (phone) check(n("the list shows the figures of your plan"), (await page.locator("#list-figures").isVisible()) && (await page.locator("#list-figures").textContent()).startsWith("7 ECTS"), await page.locator("#list-figures").textContent());

  /* ---- a mandatory course: Nova assigned the section, the student picks it right in the list.
     Its control says Pick instead of a plus, and asks for the section instead of adding one ---- */
  const strategy = page.locator("#courses .course", { hasText: "Advanced Strategy" }).first();
  check(n("a mandatory course asks for its section and does not add one"), (await strategy.getByRole("button", { name: /Pick your section/ }).count()) === 1 && (await strategy.getByRole("button", { name: /^Add / }).count()) === 0 && (await strategy.locator(".pick[aria-pressed]").count()) === 0);
  const pickText = (await strategy.getByRole("button", { name: /Pick your section/ }).textContent()).trim();
  check(n("a mandatory course without a section shows Pick"), pickText === "Pick" && (await strategy.locator(".pick").count()) === 0, pickText);
  await strategy.getByRole("button", { name: /Pick your section/ }).click();
  await page.waitForTimeout(phone ? 700 : 150);
  check(n("Pick folds the row open with all ten sections"), (await strategy.locator(".tile").count()) === 10);
  if (phone) {
    /* the page does not jump: the row comes up just far enough that its sections stand above the bar at the bottom */
    const opened = await strategy.boundingBox();
    const bar = await page.locator(".tabbar").boundingBox();
    check(n("the opened row stands above the bar at the bottom"), opened.y > 0 && opened.y + opened.height <= bar.y + 1, `row ${Math.round(opened.y)} to ${Math.round(opened.y + opened.height)}, bar at ${Math.round(bar.y)}`);
  }
  check(n("it says why Lance does not choose"), (await strategy.textContent()).includes("Pick the section Nova assigned you."));
  check(n("a clashing section says so before the choice"), (await strategy.locator(".tile", { hasText: "TXB" }).textContent()).includes("clashes"));
  if (!phone) {
    check(n("the sections wait in the week while the row is open"), (await page.locator("#week .block.ghost").count()) === 10, await page.locator("#week .block.ghost").count());
    check(n("a clashing one is marked there too"), (await page.locator("#week .block.ghost.bad").count()) === 1);
  }
  await strategy.locator(".tile", { hasText: "TXC" }).click();
  await page.waitForTimeout(250);
  check(n("the chosen tile is marked"), (await strategy.locator(".tile.on").textContent()).includes("TXC"));
  await toWeek();
  check(n("the chosen section is in the week"), await page.locator("#week .block", { hasText: "Advanced Strategy" }).first().isVisible());
  await toCourses();

  /* ---- the whole course still opens, with the same tiles ---- */
  await page.fill("#search", "advanced strategy");
  await page.waitForTimeout(120);
  const opened = page.locator("#courses .course", { hasText: "Advanced Strategy" }).first();
  if (!(await opened.locator(".tile").count())) await opened.locator(".course-main").click();
  await opened.getByRole("link", { name: "Course details" }).click();
  await page.waitForSelector("#sheet-sections .tile");
  check(n("all ten sections are in the course"), (await page.locator("#sheet-sections .tile").count()) === 10);
  check(n("a clashing section is marked in its tile"), (await sectionRow("TXB").getAttribute("title")).includes("Clashes with Introduction to Programming TXA"), await sectionRow("TXB").getAttribute("title"));
  if (!phone) {
    check(n("the other sections wait in the week"), (await page.locator("#week .block.ghost").count()) === 9, await page.locator("#week .block.ghost").count());
    await page.locator("#week .block.ghost", { hasText: "TXA" }).click();
  } else {
    await sectionRow("TXA").click();
  }
  await page.waitForTimeout(200);
  check(n("switching marks the new section"), (await page.locator("#sheet-sections .tile.on").textContent()).includes("TXA"));
  check(n("the others can be picked"), (await page.locator("#sheet-sections .tile:not(.on)").count()) === 9);
  await page.locator("#course-view .back").click();
  await page.waitForTimeout(150);
  check(n("back returns to the list with the search"), await page.locator("#list-view").isVisible() && (await page.inputValue("#search")) === "advanced strategy");

  /* ---- a clash says what clashes and offers a way out ---- */
  await page.fill("#search", "econometrics");
  await page.waitForTimeout(120);
  await row("Econometrics").locator(".pick").click();
  await page.waitForTimeout(200);
  await toWeek();
  const line = page.locator("#clashes .clash-line").first();
  check(n("a clash is named under the week"), await line.isVisible());
  check(n("it offers a way out"), (await line.getByRole("button", { name: /Remove/ }).count()) === 1, await line.textContent());
  check(n("clashing blocks are marked"), (await page.locator("#week .block.clash").count()) >= 2);
  await line.getByRole("button", { name: /Remove/ }).click();
  await page.waitForTimeout(200);
  check(n("the way out works"), (await page.locator("#clashes .clash-line").count()) === 0);
  check(n("and offers undo"), (await toast().textContent()).includes("Undo"));
  await toast().locator("button").click();
  await page.waitForTimeout(200);
  await toCourses();
  check(n("undo brings it back"), (await row("Econometrics").locator(".pick").getAttribute("aria-pressed")) === "true");
  await page.waitForTimeout(400);
  await row("Econometrics").locator(".pick").click();
  await page.waitForTimeout(450);

  /* ---- a course in the plan still says that it clashes, a double click adds once ---- */
  await page.fill("#search", "asian brands");
  await page.waitForTimeout(120);
  await row("Asian Brands").locator(".pick").dblclick();
  await page.waitForTimeout(500);
  check(n("a double click adds once"), (await row("Asian Brands").locator(".pick").getAttribute("aria-pressed")) === "true");
  await row("Asian Brands").locator(".pick").click();
  await page.waitForTimeout(300);
  check(n("the closed round is said on this page too"), (await page.locator("#round-note").textContent()).includes("practice") || phone, await page.locator("#round-note").textContent());

  /* ---- from one course to another, Back still means the list ---- */
  await page.fill("#search", "programming");
  await page.waitForTimeout(120);
  if (!(await row("Introduction to Programming").locator(".tile").count())) await row("Introduction to Programming").locator(".course-main").click();
  await row("Introduction to Programming").getByRole("link", { name: "Course details" }).click();
  await page.waitForSelector("#sheet-sections .tile");
  await page.locator("#course-view a", { hasText: "Applied Corporate Finance" }).click();
  await page.waitForFunction(() => document.querySelector("#sheet-name") && document.querySelector("#sheet-name").textContent.includes("Applied Corporate Finance"));
  await page.locator("#course-view .back").click();
  await page.waitForTimeout(150);
  check(n("back from a second course goes to the list"), await page.locator("#list-view").isVisible());

  /* ---- a T2 course brings its week forward ---- */
  await page.fill("#search", "impact investments");
  await page.waitForTimeout(120);
  await row("Impact Investments").locator(".pick").click();
  await page.waitForTimeout(200);
  check(n("T2 came forward"), (await page.locator("#half-tabs .on").textContent()).startsWith("T2"), await page.locator("#half-tabs .on").textContent());
  await page.fill("#search", "");
  await page.waitForTimeout(120);
  const inT2 = await page.locator("#courses .course-sub").allTextContents();
  check(n("the list follows the half"), inT2.every((text) => /^(S1|T2)/.test(text)), inT2.slice(0, 4));
  await page.locator("#half-tabs button", { hasText: "T1" }).click();
  await page.waitForTimeout(120);

  /* ---- fits my week ---- */
  const before = await page.locator("#courses .course").count();
  await page.click("#fits");
  await page.waitForTimeout(150);
  const after = await page.locator("#courses .course").count();
  check(n("fits my week shortens the list"), after < before, `${before} -> ${after}`);
  await page.click("#fits");

  /* ---- one bid per course, in a row with its answer ---- */
  await page.goto(url("/bids"));
  await page.waitForSelector("#bid-lists input");
  await noSideways("the bids");
  /* without points there is nothing to compare: no budget line and no bar, only the note that asks for them */
  check(n("a new plan asks for the points"), (await page.inputValue("#set-points")) === "" && (await page.locator("#points-left, #budget-use .meter").count()) === 0
    && (await page.locator("#sum-note").textContent()).includes("Enter your points"), await page.locator("#summary").textContent());
  const bid = page.locator('input[aria-label="Bid on Introduction to Programming"]');
  await bid.fill("10");
  await page.waitForTimeout(600);
  check(n("a bid before the points says what to do"), (await toast().textContent()).includes("Enter your points"), await toast().textContent());
  await page.locator("#set-points").fill("165");
  await page.locator("#set-points").blur();
  await page.waitForTimeout(250);
  const programming = bidCard("Introduction to Programming");
  const status = programming.locator(".bid-status");
  check(n("an empty bid says so in its row"), (await status.textContent()) === "No bid" && (await status.getAttribute("title")).includes("not interested"), await status.textContent());
  await programming.locator(".bid-name").click();
  await page.waitForTimeout(150);
  check(n("folded open, a course offers three amounts"), await programming.locator(".quick button", { hasText: "+10 %" }).isVisible());
  await programming.locator(".quick button", { hasText: "+10 %" }).click();
  await page.waitForTimeout(300);
  check(n("the amount is taken"), (await bid.inputValue()) === "132", await bid.inputValue());
  check(n("the row answers in words"), (await status.textContent()).startsWith("Enough"), await status.textContent());
  await bid.fill("500");
  await page.waitForTimeout(600);
  check(n("a bid above the points is refused and explained"), (await toast().textContent()).includes("cannot exceed"), await toast().textContent());
  await bid.fill("120");
  await page.waitForTimeout(600);
  check(n("the points left follow"), (await page.locator("#points-left").textContent()) === String(165 - 120), await page.locator("#points-left").textContent());
  check(n("the budget says what is in bids"), (await page.locator("#budget-use").textContent()) === "120 of 165 in bids · 45 left", await page.locator("#budget-use").textContent());
  /* a click or a tap into a number selects it, so typing replaces it instead of adding digits to it.
     The bid field still has the cursor from typing: first into the points, then back into the bid */
  if (phone) await page.locator("#set-points").tap(); else await page.locator("#set-points").click();
  await page.keyboard.type("165");
  const typedPoints = await page.inputValue("#set-points");
  if (phone) await bid.tap(); else await bid.click();
  await page.keyboard.type("120");
  check(n("a focused bid field has its value selected, so typing replaces it"), typedPoints === "165" && (await bid.inputValue()) === "120", `${typedPoints} / ${await bid.inputValue()}`);
  await bid.blur();
  await page.waitForTimeout(600);
  await programming.locator(".backup-add", { hasText: "TXC" }).click();
  await page.waitForTimeout(300);
  check(n("another section holds no extra points"), (await page.locator("#points-left").textContent()) === String(165 - 120), await page.locator("#points-left").textContent());
  check(n("details show both sections with their numbers"), (await programming.locator(".sec-line").count()) === 2 && (await programming.locator(".sec-line").first().textContent()).includes("seats"));
  check(n("the row says which one is tried next"), (await programming.locator(".course-sub").first().textContent()).includes("if full TXC"));
  check(n("another section starts with the same bid"), (await page.locator('input[aria-label="Bid on Introduction to Programming TXC only"]').inputValue()) === "120");
  await programming.getByRole("button", { name: "Do not try TXC" }).click();
  await page.waitForTimeout(250);
  check(n("a section can be taken out alone"), (await programming.locator(".sec-line").count()) === 1);
  /* what else a course can do sits at the foot of its open card */
  const card = bidCard("Impact Investments");
  await card.locator(".bid-name").click();
  await page.waitForTimeout(150);
  check(n("the primary list can be reordered"), (await card.getByRole("button", { name: "Move up" }).count()) === 1);
  await card.getByRole("button", { name: "To alternate list" }).click();
  await page.waitForTimeout(250);
  const lists = await page.locator("#bid-lists > section").nth(1).textContent();
  check(n("a course moves to the alternate list"), lists.includes("Impact Investments"), lists);
  const moved = bidCard("Impact Investments");
  if (!(await moved.locator(".bid-actions").count())) await moved.locator(".bid-name").click();   /* the card stays open after the move */
  check(n("the order of the alternate list does not count, so no arrows"), (await moved.getByRole("button", { name: "To primary list" }).isVisible()) && (await moved.getByRole("button", { name: "Move up" }).count()) === 0);
  await page.keyboard.press("Escape");
  check(n("Esc folds the card"), !(await moved.getByRole("button", { name: "Remove" }).isVisible()));
  await page.locator("#bid-lists").getByRole("button", { name: "Add alternate course" }).click();
  await page.getByLabel("Search a course for the alternate list").fill("family business");
  await page.waitForTimeout(120);
  await page.getByRole("button", { name: "Add Family Business to the alternate list" }).click();
  await page.waitForTimeout(250);
  check(n("the alternate list has its own way in"), (await page.locator("#bid-lists > section").nth(1).textContent()).includes("Family Business"));
  check(n("the alternate list says it needs a bid"), (await page.locator("#bid-lists > section").nth(1).textContent()).includes("Needs a bid, holds no points."));
  if (!phone) {
    /* a course opened in the list leaves the right half where it is: Bids stays open */
    await page.fill("#search", "programming");
    await page.waitForTimeout(120);
    await row("Introduction to Programming").locator(".course-main").click();
    await page.waitForTimeout(200);
    check(n("opening a course in the list keeps Bids open"), (await row("Introduction to Programming").locator(".tile").count()) === 3
      && (await page.locator("#tab-bids").getAttribute("aria-selected")) === "true" && (await page.locator("#pane-bids").isVisible()));
    await page.keyboard.press("Escape");
    await page.fill("#search", "");
    await page.waitForTimeout(120);
  }

  /* ---- switching keeps the bid ---- */
  await page.goto(url("/"));
  await page.waitForSelector("#courses .course");
  await page.fill("#search", "programming");
  await page.waitForTimeout(120);
  if (!(await row("Introduction to Programming").locator(".tile").count())) await row("Introduction to Programming").locator(".course-main").click();
  await row("Introduction to Programming").locator(".tile", { hasText: "TXC" }).click();
  await page.waitForTimeout(250);
  check(n("a tile switches the section right in the list"), (await row("Introduction to Programming").locator(".tile.on").textContent()).includes("TXC"));
  await page.keyboard.press("Escape");
  await page.waitForTimeout(150);
  check(n("Esc folds the row"), (await page.locator("#courses .course.open").count()) === 0);
  await page.goto(url("/bids"));
  await page.waitForSelector("#bid-lists input");
  check(n("the new section took over the bid"), (await bidCard("Introduction to Programming").textContent()).includes("TXC") && (await page.locator('input[aria-label="Bid on Introduction to Programming"]').inputValue()) === "120");

  /* ---- finish on Nova ---- */
  await page.goto(url("/nova"));
  await page.waitForSelector("#platform-lists .platform-row");
  await noSideways("the last step");
  check(n("the last step says nothing was sent"), (await page.locator("main").textContent()).includes("Nothing has been sent."));
  check(n("a closed round is called practice"), (await page.locator("#round-line").textContent()).includes("practice"), await page.locator("#round-line").textContent());
  check(n("the lists are there"), (await page.locator("#platform-lists").textContent()).includes("TXC 120"), await page.locator("#platform-lists").textContent());
  check(n("with nothing missing there is no warning"), !(await page.locator("#before").isVisible()), await page.locator("#before-list").textContent());
  await page.locator("#checklist summary").click();
  await page.locator('[data-check=fees]').check();
  await page.reload();
  await page.waitForSelector("#platform-lists .platform-row");
  await page.locator("#checklist summary").click();
  check(n("the checklist remembers"), await page.locator('[data-check=fees]').isChecked());

  /* ---- a new programme changes what is mandatory ---- */
  await page.goto(url("/"));
  await page.waitForSelector("#courses .course");
  await page.selectOption("#set-programme", "Finance");
  await page.waitForTimeout(300);
  await page.goto(url("/bids"));
  await page.waitForSelector("#bid-lists input");
  check(n("a course follows its new status"), await page.locator('input[aria-label="Bid on Advanced Strategy"]').isVisible());
  await page.goto(url("/"));
  await page.waitForSelector("#courses .course");
  await page.selectOption("#set-programme", "Management");
  await page.waitForTimeout(300);

  /* ---- the summary of your plan, start over, the example ---- */
  await page.goto(url("/"));
  await page.waitForSelector("#courses .course");
  await toSummary();
  const planned = page.locator("#plan-table tbody tr:not(.plan-group)").first();
  const examOf = ((await planned.locator(".plan-sub").textContent()).match(/Exam (.+)$/) || [])[1];   /* a laptop shows it in the column Exam, a phone under the name */
  check(n("the summary lists the plan with its exams"), Boolean(examOf) && (await planned.innerText()).includes(examOf), await planned.innerText());
  await page.locator("#plan-table").getByRole("button", { name: "Start over" }).click();
  await page.waitForTimeout(250);
  await toCourses();
  await page.fill("#search", "family business");
  await page.waitForTimeout(120);
  await row("Family Business").locator(".pick").click();
  await page.waitForTimeout(250);
  await page.goto(url("/nova"));
  await page.waitForSelector("#platform-lists .platform-row");
  const missing = await page.locator("#before-list").textContent();
  check(n("before you go names a missing bid and an empty alternate list"), missing.includes("No bid yet") && missing.includes("alternate list is empty"), missing);
  check(n("the alternate list is not numbered, its order does not count"), (await page.locator("#platform-lists .n").first().textContent()) === "1");
  await page.goto(url("/"));
  await page.waitForSelector("#courses .course");
  await toSummary();
  await page.locator("#plan-table").getByRole("button", { name: "Start over" }).click();
  await page.waitForTimeout(250);
  if (!phone) await page.mouse.move(800, 500);   /* the pointer off the list: a course under it would be previewed in the week */
  await page.waitForTimeout(250);
  await toWeek();
  await page.getByRole("button", { name: "Try an example" }).first().click();
  await page.waitForTimeout(350);
  await toSummary();
  check(n("the example fills the plan"), (await page.locator("#plan-table tfoot").textContent()).includes("6 courses + 2 alternate"), await page.locator("#plan-table tfoot").textContent());
  /* the ECTS say in words what they are measured against, in the head and in the summary */
  check(n("the ECTS figure shows 28 recommended for the example plan"), /ECTS · 28 recommended$/.test(await page.locator("#ects").textContent())
    && (await page.locator("#plan-table tfoot").textContent()).includes("ECTS · 28 recommended"), `${await page.locator("#ects").textContent()} / ${await page.locator("#plan-table tfoot").textContent()}`);
  await toWeek();
  check(n("the real plan has no clash"), (await page.locator("#clashes .clash-line").count()) === 0);
  /* a course keeps one colour: its block in the week, the dot before its name in the list and in its bid card */
  const colourIn = (node, property) => node.evaluate((element, name) => getComputedStyle(element)[name], property);
  const inWeek = await colourIn(page.locator("#week .block", { hasText: "Introduction to Programming" }).first(), "borderLeftColor");
  await toCourses();
  await page.fill("#search", "programming");
  await page.waitForTimeout(150);
  const inList = await colourIn(row("Introduction to Programming").locator(".course-main > .dot"), "backgroundColor");
  await page.fill("#search", "");
  await page.waitForTimeout(120);
  await page.goto(url("/bids"));
  await page.waitForSelector("#bid-lists input");
  const inBids = await colourIn(bidCard("Introduction to Programming").locator(".bid-name > .dot"), "backgroundColor");
  check(n("a course has the same colour in the list, the week and its bid card"), inList === inWeek && inList === inBids && !["rgba(0, 0, 0, 0)", "rgb(14, 69, 253)"].includes(inList), `${inList} / ${inWeek} / ${inBids}`);
  check(n("the real plan comes out at 132 and 33"), (await page.locator("#summary").textContent()).includes("you pay about 132") && (await page.locator("#summary").textContent()).includes("33 back afterwards"), await page.locator("#summary").textContent());
  check(n("the example has all its points in bids"), (await page.locator("#budget-use").textContent()) === "165 of 165 in bids · 0 left", await page.locator("#budget-use").textContent());
  /* the (?) answers the question it raises: the price rule on the rules page, not its top */
  await page.locator("#forecast a.why").click();
  await page.waitForSelector("#price");
  check(n("the (?) leads to the price rule"), /#price$/.test(page.url()) && (await page.locator("#price").evaluate((node) => node.matches(":target") && node.getBoundingClientRect().top >= 0)), page.url());

  /* ---- a phone shows one surface at a time, all five days ---- */
  if (phone) {
    await page.goto(url("/"));
    await page.waitForSelector("#courses .course");
    check(n("the list and not the week"), await page.locator("#courses").isVisible() && !(await page.locator("#week").isVisible()));
    await toWeek();
    check(n("the week and not the list"), await page.locator("#week").isVisible() && !(await page.locator("#courses").isVisible()));
    const heads = await page.locator(".week-head").evaluateAll((nodes) => nodes.map((node) => node.getBoundingClientRect().right));
    check(n("all five days fit"), heads.length === 5 && Math.max(...heads) <= (await page.evaluate(() => window.innerWidth)), heads);
    await noSideways("the week");
    await page.locator("#week .block").first().click();
    await page.waitForSelector("#sheet-sections .tile");
    check(n("a block opens its course as a full page"), await page.locator("#course-view").isVisible() && !(await page.locator("#week").isVisible()));
    await page.locator("#course-view .back").click();
    await page.waitForTimeout(150);
    check(n("back returns to the week"), await page.locator("#week").isVisible());
  }

  /* ---- the quiet pages ---- */
  await page.goto(url("/rules"));
  await noSideways("the rules");
  await page.getByText("Is an empty bid the same as 0?").click();
  check(n("a rule opens to its answer"), await page.getByText("Empty means you do not want the section.").isVisible());
  await page.getByText("More questions").click();
  check(n("the other questions are one click away"), await page.getByText("When is what?").isVisible());
  await page.goto(url("/share"));
  await noSideways("share");
  await page.fill("#export", "hello");
  await page.click("#send");
  await page.waitForTimeout(250);
  check(n("share refuses nonsense"), (await page.textContent("#share-result")).length > 5);

  if (!PREVIEW) {
    await page.fill("#export", JSON.stringify({ lists: [{ code: "2206", term: "S1", section: "TXA", list: "primary", seats: 2, year: "2026/2027", rows: [{ final: 100, bid: 100, allocated: true }, { final: 90, bid: 90, allocated: true }, { final: 80, bid: 80, allocated: false }] }] }));
    await page.click("#send");
    await page.waitForTimeout(250);
    check(n("share accepts a real export"), (await page.textContent("#share-result")).includes("Thank you"));
    await page.goto(BASE + "/course/2206-S1");
    await page.waitForSelector("#sheet-sections .tile");
    check(n("a link opens the course, with the shared price"), (await page.textContent("#course-view")).includes("from 90"), (await page.textContent("#course-view")).slice(0, 300));
    await page.locator("#course-view summary", { hasText: "Rate this course" }).click();
    for (const name of ["Overall", "Fair grading", "Organisation"]) await page.locator(`.rate-form [aria-label="${name}"] label`, { hasText: "4" }).click();
    await page.locator('.rate-form input[name=workload_hours]').fill("6");
    await page.locator('.rate-form [aria-label="Would take it again"] label', { hasText: "Yes" }).click();
    await page.locator('.rate-form button[type=submit]').click();
    await page.waitForTimeout(400);
    check(n("a rating is thanked for"), (await toast().textContent()).includes("Thanks"), await toast().textContent());
    check(n("and the course stays open at a simple address"), page.url().endsWith("/#2206-S1") && (await page.locator("#course-view").isVisible()), page.url());
    const file = await page.request.get(`${BASE}/plan.ics`);
    check(n("the calendar file downloads"), (await file.text()).includes("BEGIN:VCALENDAR"));
  }
  check(n("no script errors"), errors.length === 0, errors.slice(0, 3).join(" | "));
  await browser.close();
}

(async () => {
  if (WHICH === "all" || WHICH === "c") await run(chromium, "Chromium laptop", { viewport: { width: 1440, height: 900 } });
  if (WHICH === "all" || WHICH === "s") await run(chromium, "Chromium small laptop", { viewport: { width: 1280, height: 720 } });
  if (WHICH === "all" || WHICH === "w") await run(webkit, "Safari iPhone", { ...devices["iPhone 13"] });
  if (WHICH === "all" || WHICH === "a") await run(chromium, "Chrome Android", { ...devices["Pixel 5"] });
})().catch(async (error) => {
  results.push({ name: "STOPPED", ok: false, detail: `${error.message.split("\n").slice(0, 3).join(" ")} @ ${run.page.url()}` });
  if (process.env.FLOW_SHOT) await run.page.screenshot({ path: process.env.FLOW_SHOT }).catch(() => {});
}).finally(() => {
  const bad = results.filter((result) => !result.ok);
  bad.forEach((result) => console.log(`FAIL ${result.name}: ${result.detail}`.slice(0, 420)));
  console.log(`${results.length - bad.length} of ${results.length} checks passed`);
  process.exit(bad.length ? 1 : 0);
});
