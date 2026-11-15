// Mesure du parcours réel, sans semis, écriture de transaction ou changement de réglage enregistré.
// BASE=https://... PERF_USER=... PERF_PASSWORD=... node scripts/measure_search.cjs
// Chromium avec réseau/CPU simulés ≠ mesure sur un iPhone physique. Sortie JSON sans identifiant ni cours.
const assert = require("node:assert/strict");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright-core");
const BASE = (process.env.BASE || "http://127.0.0.1:18089").replace(/\/$/, "");
const target = new URL(BASE);
assert.ok(target.protocol === "https:" || target.hostname === "127.0.0.1", "HTTPS requis hors machine locale");
assert.ok(process.env.PERF_USER && process.env.PERF_PASSWORD, "PERF_USER et PERF_PASSWORD requis");
const repeats = Number(process.env.PERF_RUNS || 5);
assert.ok(Number.isInteger(repeats) && repeats >= 2 && repeats <= 10, "PERF_RUNS entre 2 et 10");
const quantile = (values, q) => [...values].sort((a, b) => a - b)[Math.ceil(values.length * q) - 1];
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.JIGO_CHROMIUM });
  const report = {
    measured_at: new Date().toISOString(),
    origin: target.origin,
    kind: "Chromium, réseau et CPU simulés ; pas un appareil physique",
    verdict: "all",
    profiles: [],
  };
  try {
    for (const profile of [
      { name: "bureau", width: 1280, latency: 0, bytes: -1, cpu: 1 },
      { name: "mobile 4G simulé", width: 390, latency: 150, bytes: 200000, cpu: 4 },
    ]) {
      const context = await browser.newContext({
        viewport: { width: profile.width, height: 900 },
        reducedMotion: "reduce",
      });
      const page = await context.newPage();
      page.setDefaultTimeout(120000);
      await page.goto(BASE + "/login.html");
      await page.fill("#u", process.env.PERF_USER);
      await page.fill("#p", process.env.PERF_PASSWORD);
      await page.click("#auth-form button.primary");
      await page.waitForURL("**/index.html");
      const cdp = await context.newCDPSession(page);
      await cdp.send("Network.enable");
      await cdp.send("Network.emulateNetworkConditions", {
        offline: false,
        latency: profile.latency,
        downloadThroughput: profile.bytes,
        uploadThroughput: profile.bytes,
      });
      await cdp.send("Emulation.setCPUThrottlingRate", { rate: profile.cpu });
      const runs = [];
      for (let i = 0; i < repeats; i++) {
        await page.goto(BASE + "/index.html");
        await page.waitForFunction(
          () =>
            typeof document.querySelector("#ct-apply")?.onclick === "function" &&
            !document.querySelector("#ct-apply").disabled,
        );
        await page.locator("#ct-verdict [data-verdict=all]").click();
        const response = page.waitForResponse((r) => new URL(r.url()).searchParams.get("r") === "ranking/table");
        const started = Date.now();
        await page.locator("#ct-apply").click();
        const api = await response;
        await api.finished();
        const headers = await api.allHeaders();
        if (!api.ok())
          throw new Error(
            "Classement indisponible : HTTP " + api.status() + " ; " + (headers["server-timing"] || "durées absentes"),
          );
        await page.waitForFunction(
          () => !document.querySelector("#ct-apply")?.disabled && !document.querySelector("#ct-table-body .ct-loading"),
        );
        const renderedMs = Date.now() - started;
        const body = await api.body();
        const state = await page.evaluate((url) => {
          const resource = performance.getEntriesByName(url).at(-1);
          return {
            rows: document.querySelectorAll("#ct-table-body tr[data-row]").length,
            heap_bytes: performance.memory?.usedJSHeapSize ?? null,
            overflow: document.documentElement.scrollWidth > innerWidth,
            transfer_bytes: resource?.transferSize ?? null,
            wire_body_bytes: resource?.encodedBodySize ?? null,
          };
        }, api.url());
        runs.push({
          apply_to_render_ms: renderedMs,
          decoded_json_bytes: body.length,
          wire_bytes: Number(headers["content-length"]) || null,
          encoding: headers["content-encoding"] || null,
          server_timing: headers["server-timing"] || null,
          ...state,
        });
      }
      report.profiles.push({
        profile,
        runs,
        p50_ms: quantile(
          runs.map((r) => r.apply_to_render_ms),
          0.5,
        ),
        p95_ms: quantile(
          runs.map((r) => r.apply_to_render_ms),
          0.95,
        ),
      });
      await context.close();
    }
    console.log(JSON.stringify(report, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
