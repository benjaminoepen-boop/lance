/* Applies the saved colour choice (system, light, dark) before the page paints, so a dark page never flashes white.
   A file of its own and not a script inside the page, because the page allows scripts from its own address only.
   The switch itself is in common.js. */
try {
  const theme = localStorage.getItem("lance-theme");
  if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
} catch (error) { /* private window: the system decides */ }
