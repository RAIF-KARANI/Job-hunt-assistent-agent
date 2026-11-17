// 17i: measures the contrast of every piece of visible text in the UI, in both
// themes, against the brightest and darkest spots of the glass backdrop.
// Run against the dev server (cd frontend; npx vite --port 5199) with
//   playwright-cli open http://localhost:5199/ ; playwright-cli --raw run-code --filename=scripts/check_contrast.js
// It prints a JSON list: one entry per screen, then any text below 4.5:1 (3:1 for large text).
async (page) => {
  // For every piece of visible text: blend the backgrounds behind it, from the
  // backdrop up, and work out the WCAG contrast. The backdrop is taken at its
  // brightest and darkest spots (the four coloured corners and the plain
  // middle), so a pass here holds wherever the text sits.
  const THEMES = ["light", "dark"];
  const PAGES = [
    ["dashboard", null],
    ["analyze", null],
    ["tracker", null],
    ["tracker", "list"],
    ["tracker", "sheet"],
    ["evals", "open"],
    ["settings", "open"],
    ["components", null],
    ["dashboard", "palette"],
  ];
  const results = [];

  async function measure(label) {
    return page.evaluate((label) => {
      const parse = (c) => {
        const m = c.match(/rgba?\(([^)]+)\)/);
        if (!m) return null;
        const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number);
        return [p[0], p[1], p[2], p[3] === undefined ? 1 : p[3]];
      };
      const over = (top, under) => [0, 1, 2].map((i) => top[i] * top[3] + under[i] * (1 - top[3])).concat(1);
      const lum = (c) => {
        const f = (v) => {
          v /= 255;
          return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
        };
        return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
      };
      const ratio = (a, b) => {
        const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
        return (x + 0.05) / (y + 0.05);
      };
      const dark = document.documentElement.dataset.theme !== "light";
      const base = dark ? [10, 13, 22, 1] : [234, 240, 251, 1];
      const corners = dark
        ? [[96, 165, 250, 0.8], [251, 146, 60, 0.72], [244, 114, 182, 0.62], [167, 139, 250, 0.72], [0, 0, 0, 0]]
        : [[96, 165, 250, 0.62], [251, 146, 60, 0.5], [244, 114, 182, 0.45], [167, 139, 250, 0.52], [0, 0, 0, 0]];
      const backdrops = corners.map((c) => over(c, base));

      const out = [];
      let skipped = 0;
      const seen = new Set();
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) {
        const node = walker.currentNode;
        const text = node.textContent.replace(/\s+/g, " ").trim();
        if (text.length < 2) continue;
        const el = node.parentElement;
        if (!el || seen.has(el)) continue;
        seen.add(el);
        const r = el.getBoundingClientRect();
        if (r.width < 2 || r.height < 2) continue;
        if (el.closest("[aria-hidden='true'], .sr-only, svg, canvas, option, dialog:not([open]), details:not([open]) > :not(summary)")) continue;
        const cs = getComputedStyle(el);
        if (cs.visibility === "hidden") continue;
        if (el.closest("[disabled], :disabled")) continue; // disabled controls are exempt in WCAG

        // the chain of backgrounds and opacities, outermost first
        const chain = [];
        let opacity = 1;
        let gradient = false;
        for (let a = el; a && a !== document.documentElement; a = a.parentElement) {
          const s = getComputedStyle(a);
          opacity *= Number(s.opacity);
          if (s.backgroundImage && s.backgroundImage !== "none" && !a.matches("body")) gradient = true;
          const bg = parse(s.backgroundColor);
          if (bg && bg[3] > 0 && !a.matches("body")) chain.unshift(bg);
        }
        if (opacity < 0.05) continue;
        if (gradient) {
          skipped++;
          continue; // gradients (cards, the main button, the galaxy) are checked by eye
        }
        let fg = parse(cs.color);
        if (!fg) continue;
        fg = [fg[0], fg[1], fg[2], fg[3] * opacity];
        let worst = 99;
        for (const b of backdrops) {
          let bg = b;
          for (const layer of chain) bg = over(layer, bg);
          const shown = over(fg, bg);
          worst = Math.min(worst, ratio(shown, bg));
        }
        const size = parseFloat(cs.fontSize);
        const bold = Number(cs.fontWeight) >= 600;
        const large = size >= 24 || (bold && size >= 18.66);
        const need = large ? 3 : 4.5;
        if (worst < need) {
          out.push({ page: label, text: text.slice(0, 48), ratio: Math.round(worst * 100) / 100, need, color: cs.color, cls: (el.className && el.className.baseVal === undefined ? el.className : el.tagName).toString().slice(0, 40) });
        }
      }
      return { out, skipped };
    }, label);
  }

  for (const theme of THEMES) {
    for (const [route, extra] of PAGES) {
      await page.goto("http://localhost:5199/#/" + route);
      await page.reload();
      await page.waitForTimeout(1100);
      await page.evaluate((t) => (document.documentElement.dataset.theme = t), theme);
      await page.waitForTimeout(250);
      if (extra === "list") await page.locator('label:has-text("List")').click();
      if (extra === "sheet") {
        await page.locator(".job-card").first().click();
        await page.waitForTimeout(700);
        await page.locator("dialog.sheet details:not([open]) > summary").evaluateAll((els) => els.forEach((s) => s.click()));
      }
      if (extra === "open") await page.locator("details:not([open]) > summary").evaluateAll((els) => els.forEach((s) => s.click()));
      if (extra === "palette") {
        await page.keyboard.press("Control+k");
        await page.waitForTimeout(400);
      }
      await page.waitForTimeout(300);
      const { out, skipped } = await measure(theme + " " + route + (extra ? "+" + extra : ""));
      results.push({ where: theme + " " + route + (extra ? "+" + extra : ""), fails: out.length, skipped });
      for (const f of out) results.push(f);
      if (extra === "list") await page.locator('label:has-text("Board")').click();
    }
  }
  return JSON.stringify(results);
}
