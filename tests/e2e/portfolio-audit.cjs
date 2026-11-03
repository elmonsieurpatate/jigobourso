/* Run after portfolio_audit_seed.py with JIGO_TEST_DATABASE=1, BASE=local PHP server,
   JIGO_CHROMIUM=/path/to/chromium and optional PLAYWRIGHT_MODULE/AUDIT_OUT. No production access. */
const assert = require('node:assert/strict'), fs = require('node:fs');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const BASE = process.env.BASE || 'http://127.0.0.1:18090', OUT = process.env.AUDIT_OUT || '/tmp/jigobourso-portfolio-regression';
assert.equal(process.env.JIGO_TEST_DATABASE, '1');
assert.equal(new URL(BASE).hostname, '127.0.0.1');
fs.mkdirSync(OUT, { recursive: true });
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.JIGO_CHROMIUM || '/usr/bin/chromium', args: ['--no-sandbox'] });
  const report = [];
  try {
    for (const width of [1280, 390, 375]) {
      const context = await browser.newContext({ viewport: { width, height: 900 }, isMobile: width < 600, hasTouch: width < 600 });
      await context.route('**/*', route => {
        const u = new URL(route.request().url());
        if (u.hostname !== '127.0.0.1') return route.abort();
        if (u.searchParams.get('r') === 'intraday') { u.searchParams.set('fetch', '0'); return route.continue({ url: u.toString() }); }
        return route.continue();
      });
      const auth = await context.request.post(BASE + '/api.php?r=auth/login', { data: { username: 'audit_portfolio', password: 'audit-local-validation-2026' } });
      assert.equal(auth.status(), 200);
      const get = async (route, id) => { const res = await context.request.get(`${BASE}/api.php?r=${route}&id=${id}`); assert.equal(res.status(), 200); return res.json(); };
      const page = await context.newPage(), errors = [], checks = [], geometry = [];
      page.on('pageerror', e => errors.push(e.message));
      const open = async id => {
        const ready = page.waitForResponse(res => { const u = new URL(res.url()); return u.searchParams.get('r') === 'portfolio/history'; });
        await page.goto(`${BASE}/portefeuilles.html?id=${id}`);
        assert.equal((await ready).status(), 200);
        await page.waitForFunction(() => document.querySelector('#evo-note') && !document.querySelector('#evo-chart .spinner'));
        await page.evaluate(() => {
          window.lastPortfolioChart = null;
          const original = J.lineChart;
          J.lineChart = (host, xs, series, options) => { if (host.id === 'evo-chart') window.lastPortfolioChart = { xs, series, time: !!options.time }; return original(host, xs, series, options); };
        });
      };
      await open(1);
      for (const period of ['1w', '1m', '3m', '6m', '1y', 'all']) {
        await page.locator(`#evo-per [data-v="${period}"]`).click();
        for (const mode of ['titles', 'gain', 'value']) {
          await page.locator(`#evo-mode [data-v="${mode}"]`).click();
          for (const unit of ['eur', 'pct']) {
            const button = page.locator(`#evo-unit [data-v="${unit}"]`);
            if (mode === 'value' && unit === 'pct') { assert.equal(await button.isDisabled(), true); continue; }
            await button.click();
            const result = await page.evaluate(() => {
              const host = document.querySelector('#evo-chart'), svg = host.querySelector('svg'), movers = document.querySelector('#movers');
              return { chart: window.lastPortfolioChart, host: host.getBoundingClientRect().toJSON(), svg: svg?.getBoundingClientRect().toJSON(), movers: movers.getBoundingClientRect().toJSON(), overflow: document.documentElement.scrollWidth > innerWidth };
            });
            assert.ok(result.host.width >= 250, `A1: ${width}px graph width ${result.host.width}`);
            assert.ok(result.svg?.width >= 250, `A1: missing or unreadable SVG at ${width}`);
            assert.equal(result.overflow, false);
            if (width < 600) assert.ok(result.movers.top >= result.host.bottom - 1, 'A1: contributions overlap graph/legend');
            if (mode === 'titles' && unit === 'eur') {
              const values = result.chart.series.map(s => s.values.at(-1));
              assert.ok(Math.abs(values[0] - values.slice(1).reduce((s, x) => s + x, 0)) < .031);
            }
            if (period === 'all' && mode !== 'value' && unit === 'pct') assert.ok(Math.abs(result.chart.series[0].values.at(-1) - 233.4 / 3942 * 100) < .001, 'A2: gross purchases denominator');
            checks.push({ period, mode, unit }); geometry.push({ width: result.host.width, svg: result.svg.width });
          }
        }
      }
      // A6: 1J explicitly offers only the existing supported Value/EUR view.
      await page.locator('#evo-per [data-v="1d"]').click();
      for (const mode of ['titles', 'gain']) assert.equal(await page.locator(`#evo-mode [data-v="${mode}"]`).isDisabled(), true);
      assert.equal(await page.locator('#evo-unit [data-v="pct"]').isDisabled(), true);
      assert.equal(await page.locator('#evo-mode [data-v="value"]').getAttribute('class'), 'on');
      assert.match(await page.locator('#evo-note').innerText(), /quantités actuelles/);
      assert.equal((await page.evaluate(() => window.lastPortfolioChart)).time, true);
      assert.ok((await page.locator('#evo-chart').boundingBox()).width >= 250);
      assert.ok((await page.locator('#evo-chart svg').boundingBox()).width >= 250);
      checks.push({ period: '1d', mode: 'value', unit: 'eur', unsupportedChoicesDisabled: true });
      // Leaving 1J restores availability; legends must respond to genuine clicks.
      await page.locator('#evo-per [data-v="1m"]').click(); await page.locator('#evo-mode [data-v="titles"]').click();
      const chip = page.locator('#evo-chart .lc-chip').first(), before = await chip.getAttribute('aria-pressed');
      await chip.click(); assert.notEqual(await page.locator('#evo-chart .lc-chip').first().getAttribute('aria-pressed'), before);
      await page.locator('#evo-chart .lc-chip').first().click();
      for (const fold of ['lots', 'sales', 'alloc', 'tx', 'settings', 'positions', 'hero']) {
        const section = page.locator(`[data-fold="${fold}"]`), before = await section.getAttribute('class');
        await section.locator('.fold-h').click(); assert.notEqual(await section.getAttribute('class'), before);
        await section.locator('.fold-h').click();
      }
      await page.screenshot({ path: `${OUT}/portfolio-${width}.png`, fullPage: true });
      await open(3); await page.locator('#evo-per [data-v="all"]').click(); await page.locator('#evo-mode [data-v="titles"]').click(); await page.locator('#evo-unit [data-v="pct"]').click();
      assert.equal((await page.evaluate(() => window.lastPortfolioChart)).series[0].values.at(-1), 20, 'A2: fully sold gain must remain');
      assert.match(await page.locator('#movers').innerText(), /20,0/);
      const split = await get('portfolio', 2);
      assert.equal(split.positions[0].qty, 20); assert.equal(split.lots.reduce((s, l) => s + l.remaining, 0), 20, 'A4: open lots after split');
      assert.equal(split.totals.cost, 1000); assert.equal(split.totals.total_gain, 200);
      await open(4);
      const missing = await get('portfolio', 4), history = await get('portfolio/history', 4);
      assert.equal(missing.totals.value, null); assert.equal(history.value.at(-1), null); assert.equal(missing.totals.cost, 20);
      assert.equal(missing.positions[0].price, null); assert.equal(history.gain.at(-1), null);
      assert.match(await page.locator('#page').innerText(), /valorisation et gain total indisponibles/);
      assert.equal(await page.locator('.hero-v').innerText(), '–');
      await page.screenshot({ path: `${OUT}/missing-${width}.png`, fullPage: true });
      const lot = (await get('portfolio', 1)).lots.find(l => l.alert.strategy === 'momentum');
      assert.equal(lot.alert.alerts.find(a => a.kind === 'momentum').value, -.1, 'A3: stored percent is not a ratio');
      assert.deepEqual(errors, []);
      report.push({ width, checks, geometry, errors, legendClick: true, panels: true, soldPercentage: 20, splitQty: 20, missingValue: null });
      fs.writeFileSync(`${OUT}/results.json`, JSON.stringify(report, null, 2));
      await context.close();
    }
    console.log(JSON.stringify(report.map(r => ({ width: r.width, combinations: r.checks.length, minGraphWidth: Math.min(...r.geometry.map(x => x.width)), errors: r.errors }))));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
