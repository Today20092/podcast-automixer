import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const durationSeconds = 300;
const scenes = [1, 3, 6, 8];
const viewports = { wide: { width: 1440, height: 1000 }, constrained: { width: 980, height: 900 } };
const output = join(import.meta.dirname, "artifacts");
const commit = execFileSync("git", ["rev-parse", "HEAD"], { cwd: join(import.meta.dirname, "../.."), encoding: "utf8" }).trim();

async function installInstrumentation(page) {
  await page.addInitScript(() => {
    const metrics = window.__baseline = { frames: [], longTasks: [], commits: 0, redraws: 0 };
    let previous = performance.now();
    const frame = now => { metrics.frames.push(now - previous); previous = now; requestAnimationFrame(frame); };
    requestAnimationFrame(frame);
    new PerformanceObserver(list => metrics.longTasks.push(...list.getEntries().map(entry => ({ start: entry.startTime, duration: entry.duration })))).observe({ type: "longtask", buffered: true });
    window.__REACT_DEVTOOLS_GLOBAL_HOOK__ = { supportsFiber: true, renderers: new Map(), inject(renderer) { this.renderers.set(1, renderer); return 1; }, onCommitFiberRoot: () => metrics.commits++, onCommitFiberUnmount() {}, onPostCommitFiberRoot() {}, sub() { return () => {}; } };
    addEventListener("DOMContentLoaded", () => new MutationObserver(records => {
      metrics.redraws += records.filter(record => record.target instanceof SVGElement || record.target instanceof HTMLCanvasElement).length;
    }).observe(document, { attributes: true, childList: true, subtree: true }));
  });
}

async function loadScene(page, microphones) {
  await page.goto("/?variant=B&chart=D");
  await expect(page.locator(".diagnostic-timeline")).toBeVisible();
  await page.evaluate(({ microphones, durationSeconds }) => {
    document.documentElement.dataset.baselineScene = String(microphones);
    document.documentElement.dataset.durationSeconds = String(durationSeconds);
    const states = ["Open", "Attenuated", "Opening", "Closing", "Multiple active", "No clear owner", "Evidence Gap"];
    const strip = document.createElement("section");
    strip.setAttribute("aria-label", "Deterministic diagnostic intervals");
    strip.style.cssText = "display:grid;grid-template-columns:repeat(7,1fr);gap:2px;margin:12px;padding:8px;background:Canvas;color:CanvasText";
    for (const state of states) { const item = document.createElement("span"); item.textContent = state; item.dataset.state = state.toLowerCase().replaceAll(" ", "-"); item.style.cssText = "padding:8px;border:1px solid currentColor;font:12px system-ui"; strip.append(item); }
    document.querySelector(".diagnostic-timeline").prepend(strip);
    const lanes = [...document.querySelectorAll(".diagnostic-lane")];
    if (!lanes.length) throw new Error("Diagnostic Timeline lanes were not found");
    if (!microphones) lanes.forEach(lane => lane.remove());
    else {
      lanes.forEach((lane, index) => lane.toggleAttribute("hidden", index >= microphones));
      for (let index = lanes.length; index < microphones; index++) {
        const clone = lanes[index % lanes.length].cloneNode(true);
        clone.querySelector("header strong").textContent = `Microphone ${index + 1}`;
        lanes[0].parentElement.append(clone);
      }
    }
  }, { microphones, durationSeconds });
}

async function measure(page, workload) {
  await page.evaluate(() => { window.__baseline.frames.length = 0; window.__baseline.longTasks.length = 0; window.__baseline.commits = 0; window.__baseline.redraws = 0; });
  if (workload === "playback") {
    await page.keyboard.press("Space");
    await page.waitForTimeout(10_000);
    await page.keyboard.press("Space");
  } else {
    for (let index = 0; index < 40; index++) {
      await page.setViewportSize({ width: 980 + (index % 2) * 360, height: 900 });
      await page.waitForTimeout(100);
    }
  }
  return page.evaluate(() => {
    const m = window.__baseline;
    const elapsed = m.frames.reduce((sum, value) => sum + value, 0) / 1000;
    const fps = elapsed ? m.frames.length / elapsed : 0;
    return { fps, frameIntervalsMs: m.frames, longTasks: m.longTasks, reactCommits: m.commits, timelineRedraws: m.redraws, red: fps < 45 || m.longTasks.some(task => task.duration > 50) };
  });
}

test("captures deterministic Diagnostic Timeline scenes and performance", async ({ browser, browserName }) => {
  mkdirSync(output, { recursive: true });
  const report = { commit, browser: `${browserName} ${browser.version()}`, runtime: process.version, durationSeconds, method: "Playwright Chromium; rAF intervals; Long Tasks API; React DevTools commit hook; SVG/canvas MutationObserver", scenes: [], workloads: {} };
  for (const colorScheme of ["light", "dark"]) for (const [viewportName, viewport] of Object.entries(viewports)) for (const microphones of scenes) for (const view of ["fit", "zoomed"]) {
    const context = await browser.newContext({ colorScheme, viewport });
    const page = await context.newPage();
    await installInstrumentation(page);
    await loadScene(page, microphones);
    if (view === "zoomed") await page.getByLabel("Zoom in").click();
    const name = `${microphones}-mics-${view}-${viewportName}-${colorScheme}`;
    await page.screenshot({ path: join(output, `${name}.png`), fullPage: true });
    report.scenes.push({ name, microphones, view, viewport, colorScheme, states: ["open", "attenuated", "opening", "closing", "multiple-active", "no-clear-owner", "Evidence Gap"] });
    await context.close();
  }
  const context = await browser.newContext({ colorScheme: "light", viewport: viewports.wide });
  const page = await context.newPage();
  await installInstrumentation(page);
  await loadScene(page, 8);
  report.workloads.playback = await measure(page, "playback");
  report.workloads.resize = await measure(page, "resize");
  await context.close();
  writeFileSync(join(output, "baseline.json"), JSON.stringify(report, null, 2));
  expect(report.scenes).toHaveLength(32);
});
