/* How much does each screen ask of a student? Counts the controls and the words a student can see in the window.
   Closed sections do not count, and neither does what lies below the window.

   Start a server first, then:  NODE_PATH=<folder with playwright>/node_modules node scripts/measure.cjs [base address] */
const { chromium, devices } = require("playwright");
const BASE = process.argv[2] || "http://127.0.0.1:8771";

async function count(page) {
  return page.evaluate(() => {
    const shown = (node) => {
      const box = node.getBoundingClientRect();
      const style = getComputedStyle(node);
      return box.width > 1 && box.height > 1 && style.visibility !== "hidden" && style.display !== "none"
        && box.top < innerHeight && box.bottom > 0 && box.left < innerWidth && node.checkVisibility({ contentVisibilityAuto: true, visibilityProperty: true });
    };
    const controls = [...document.querySelectorAll("a,button,input,select,textarea,summary,[role=button],[role=tab]")].filter(shown).length;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let words = 0;
    while (walker.nextNode()) {
      const text = walker.currentNode;
      const parent = text.parentElement;
      if (!parent || ["SCRIPT", "STYLE", "NOSCRIPT", "OPTION"].includes(parent.tagName) || !parent.checkVisibility({ contentVisibilityAuto: true, visibilityProperty: true })) continue;
      const amount = text.textContent.trim().split(/\s+/).filter(Boolean).length;
      if (!amount) continue;
      const range = document.createRange();
      range.selectNodeContents(text);
      const box = range.getBoundingClientRect();
      if (box.width > 0 && box.top < innerHeight && box.bottom > 0) words += amount;
    }
    return { controls, words, scrolls: document.documentElement.scrollHeight > innerHeight + 1 };
  });
}

(async () => {
  const browser = await chromium.launch();
  const laptop = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await laptop.newPage();
  const rows = [];
  const measure = async (name) => { const found = await count(page); rows.push([name, found.controls, found.words, found.scrolls ? "scrolls" : "fits"]); };
  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
  await measure("First screen, empty");
  await page.getByRole("button", { name: /example/i }).first().click();
  await page.waitForTimeout(500);
  await measure("First screen, example plan");
  await page.goto(`${BASE}/course/2477-S1`, { waitUntil: "networkidle" });
  await page.waitForTimeout(400);
  await measure("A course");
  await page.goto(`${BASE}/bids`, { waitUntil: "networkidle" });
  await measure("Bids, example plan");
  const last = await page.goto(`${BASE}/nova`, { waitUntil: "networkidle" });
  if (last.ok()) await measure("Last step");
  await page.goto(`${BASE}/rules`, { waitUntil: "networkidle" });
  await measure("Rules");
  await page.goto(`${BASE}/share`, { waitUntil: "networkidle" });
  await measure("Share");
  await laptop.close();
  const phone = await browser.newContext({ ...devices["iPhone 13"] });
  const small = await phone.newPage();
  await small.goto(`${BASE}/`, { waitUntil: "networkidle" });
  const found = await count(small);
  rows.push(["Phone, first screen", found.controls, found.words, ""]);
  await browser.close();
  rows.forEach((row) => console.log(row.join(" | ")));
})();
