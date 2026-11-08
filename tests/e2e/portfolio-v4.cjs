/* Portefeuille V4 : synthèse, deux modes de graphique (le mode cours ignore la date d'achat), période, € | %, zoom, cartes, détail, nouvel onglet, responsive. */
const assert = require('node:assert/strict'); const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const BASE = process.env.BASE || 'http://127.0.0.1:18095', SHOTS = process.env.SHOTS || '';
(async () => {
  const b = await chromium.launch({ executablePath: process.env.JIGO_CHROMIUM, args: ['--no-sandbox'] });
  try {
    for (const width of [320, 375, 390, 430, 768, 1024, 1440]) {
      const ctx = await b.newContext({ viewport: { width, height: width > 700 ? 1000 : 900 }, isMobile: width < 600, hasTouch: width < 600 });
      const page = await ctx.newPage(), errors = []; page.on('pageerror', e => errors.push(e.message)); page.setDefaultTimeout(15000);
      assert.equal((await ctx.request.post(BASE + '/api.php?r=auth/login', { data: { username: 'audit_portfolio', password: 'audit-local-validation-2026' } })).ok(), true);
      const list = (await (await ctx.request.get(BASE + '/api.php?r=portfolios')).json()).portfolios;
      let id = null, rows = 0;
      for (const p of list) { await page.goto(BASE + '/portefeuilles.html?id=' + p.id); await page.locator('.px-hero').waitFor(); const n = await page.locator('.px-card').count(); if (n > rows) { rows = n; id = p.id; } }
      assert.ok(id); await page.goto(BASE + '/portefeuilles.html?id=' + id); await page.locator('.px-hero').waitFor();
      const shot = async n => { if (SHOTS && [390, 1440].includes(width)) await page.screenshot({ path: `${SHOTS}/pf-${n}-${width}.png`, fullPage: true }); };
      assert.equal(await page.locator('.px-mini > div').count(), 4); assert.match(await page.locator('.px-alerts').innerText(), /Mes alertes/);
      assert.match(await page.locator('#px-per .on').innerText(), /Depuis le début/);
      assert.ok(await page.locator('#px-chart svg path').count() >= 1); await shot('perso');
      await page.locator('#px-per [data-p="1m"]').click(); assert.match(await page.locator('#px-note').innerText(), /Période/);
      await page.locator('#px-unit [data-u="eur"]').click(); await page.locator('#px-unit [data-u="pct"]').click();
      // mode cours : historique antérieur à l'achat
      await page.locator('#px-mode [data-m="market"]').click(); await page.locator('#px-per [data-p="1y"]').click();
      const dates = await page.evaluate(() => PFHome.state.mode); assert.equal(dates, 'market');
      assert.match(await page.locator('#px-note').innerText(), /Cours normalisés/); await shot('cours');
      const mstart = await page.evaluate(() => PFChart.fr), nPts = await page.locator('#px-chart svg path[stroke]').count(); assert.ok(nPts >= 1);
      await page.locator('#px-mode [data-m="perso"]').click(); await page.locator('#px-per [data-p="all"]').click();
      if (width > 700) {
        const box = await page.locator('#px-chart .pfc-hit').boundingBox();
        await page.mouse.move(box.x + box.width * 0.5, box.y + box.height / 2); assert.ok(await page.locator('.pfc-tip').isVisible(), 'infobulle');
        await page.mouse.move(box.x + box.width * 0.3, box.y + 20); await page.mouse.down(); await page.mouse.move(box.x + box.width * 0.7, box.y + 20, { steps: 6 }); await page.mouse.up();
        await page.locator('#px-reset').waitFor(); await page.locator('#px-reset').click();
      }
      const first = page.locator('.px-card').first();
      const href = await first.locator('a.px-an').getAttribute('href'); assert.match(href, /^titre\.html\?id=\d+/); assert.equal(await first.locator('a.px-an').getAttribute('target'), '_blank');
      await first.dispatchEvent('click'); await page.locator('#px-detail').waitFor(); assert.ok(await page.locator('#px-detail a[target="_blank"]').count() >= 1); await shot('detail');
      await page.locator('#px-close').dispatchEvent('click');
      await page.locator('#px-hist').dispatchEvent('click'); await page.locator('#tx-rows').waitFor(); await page.locator('#back-home').dispatchEvent('click'); await page.locator('.px-hero').waitFor();
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, 'défilement horizontal à ' + width);
      assert.deepEqual(errors, []); await ctx.close(); console.log('ok', width);
    }
  } finally { await b.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
