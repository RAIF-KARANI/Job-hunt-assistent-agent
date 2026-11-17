// 17j: tabs through each screen in both themes and lists any control that
// does not visibly change when it gets the keyboard focus. Run like
// scripts/check_contrast.js (dev server on port 5199, then playwright-cli run-code).
async (page) => {
  const out = [];
  const ROUTES = ["dashboard", "analyze", "tracker", "evals", "settings"];
  for (const theme of ["dark", "light"]) {
    for (const route of ROUTES) {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto("http://localhost:5199/#/" + route);
      await page.reload();
      await page.waitForTimeout(1000);
      await page.evaluate((t) => (document.documentElement.dataset.theme = t), theme);
      await page.locator("body").click({ position: { x: 5, y: 5 } });
      // what a control looks like: its own outline, shadow and border, and those of the part you see
      await page.evaluate(() => {
        window.__look = (el) =>
          [el, el.nextElementSibling, el.closest("label, summary")]
            .filter(Boolean)
            .map((v) => {
              const c = getComputedStyle(v);
              return [c.outlineStyle, c.outlineWidth, c.outlineColor, c.boxShadow, c.borderColor, c.backgroundColor, c.textDecorationLine].join("|");
            })
            .join("#");
        window.__seen = [];
      });
      const noMark = [];
      let count = 0;
      for (let i = 0; i < 80; i++) {
        await page.keyboard.press("Tab");
        const r = await page.evaluate(() => {
          const el = document.activeElement;
          const result = { done: !el || el === document.body, prev: null };
          // the one focused before: compare how it looked focused with how it looks now
          if (window.__prev) {
            const now = window.__look(window.__prev.el);
            if (now === window.__prev.focused) result.prev = window.__prev.name;
          }
          if (result.done) return result;
          const name = (el.getAttribute("aria-label") || el.textContent || el.getAttribute("placeholder") || el.tagName).replace(/\s+/g, " ").trim().slice(0, 30);
          const key = el.tagName + ":" + name;
          result.loop = window.__seen.includes(key);
          window.__seen.push(key);
          const rect = el.getBoundingClientRect();
          window.__prev = rect.width > 0 ? { el, name: el.tagName.toLowerCase() + " '" + name + "'", focused: window.__look(el) } : null;
          return result;
        });
        if (r.prev) noMark.push(r.prev);
        if (r.done || r.loop) break;
        count++;
      }
      out.push(theme + " " + route + ": " + count + " stops; no visible change on focus: " + JSON.stringify(noMark));
    }
  }
  return out.join("\n");
}
