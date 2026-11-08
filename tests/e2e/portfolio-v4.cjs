/* Portefeuille V4 : synthèse, période commune, € | %, graphique (infobulle, zoom), tableau, détail, lien Analyse du titre, mobile. */
const assert = require('node:assert/strict'); const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const BASE = process.env.BASE || 'http://127.0.0.1:18095';
(async () => {
  const b = await chromium.launch({ executablePath: process.env.JIGO_CHROMIUM, args: ['--no-sandbox'] });
  try {
    for (const width of [1280, 768, 390]) {
      const ctx = await b.newContext({ viewport: { width, height: 1000 }, isMobile: width < 600 });
      const page = await ctx.newPage(), errors = []; page.on('pageerror', e => errors.push(e.message)); page.setDefaultTimeout(15000);
      const r = await ctx.request.post(BASE + '/api.php?r=auth/login', { data: { username: 'audit_portfolio', password: 'audit-local-validation-2026' } }); assert.equal(r.ok(), true);
      const list = (await (await ctx.request.get(BASE + '/api.php?r=portfolios')).json()).portfolios;
      let id = null, rows = 0;
      for (const p of list) { await page.goto(BASE + '/portefeuilles.html?id=' + p.id); await page.locator('.pf-cards').waitFor(); const n = await page.locator('.pf-table tbody tr[data-key]').count(); if (n > rows) { rows = n; id = p.id; } }
      assert.ok(id, 'portefeuille avec positions'); await page.goto(BASE + '/portefeuilles.html?id=' + id); await page.locator('.pf-cards').waitFor();
      assert.equal(await page.locator('.pf-card').count(), 6);
      assert.match(await page.locator('.pf-period .on').innerText(), /Depuis le début/);
      assert.ok(await page.locator('#pfh-chart svg path').count() >= 1, 'courbe tracée');
      const first = await page.locator('.pf-card').nth(5).innerText();
      await page.locator('.pf-period [data-p="1m"]').click(); await page.locator('.pf-cards').waitFor();
      assert.match(await page.locator('.pf-card').nth(5).innerText(), /1 mois/i); assert.match(await page.locator('#pfh-notes').innerText(), /1 mois/i);
      await page.locator('.pf-period [data-p="all"]').click();
      await page.locator('#pfh-unit [data-u="pct"]').click(); assert.match(await page.locator('.pf-table thead').innerText(), /Contribution \(pts\)|Rendement/i);
      await page.locator('#pfh-unit [data-u="eur"]').click();
      if (width > 600) {
        const box = await page.locator('#pfh-chart .pfc-hit').boundingBox();
        await page.mouse.move(box.x + box.width * 0.5, box.y + box.height / 2); assert.ok(await page.locator('.pfc-tip').isVisible(), 'infobulle');
        await page.mouse.move(box.x + box.width * 0.3, box.y + 20); await page.mouse.down(); await page.mouse.move(box.x + box.width * 0.7, box.y + 20, { steps: 6 }); await page.mouse.up();
        await page.locator('#pfh-unz').waitFor(); assert.match(await page.locator('#pfh-notes').innerText(), /Zoom/);
        await page.locator('#pfh-reset').click(); assert.equal(await page.locator('#pfh-unz').count(), 0);
      }
      await page.locator('#pfh-only').click(); assert.ok(await page.locator('#pfh-chart svg').count() === 1);
      await page.locator('#pfh-all').click();
      await page.locator('.pf-table tbody tr[data-key]').first().click(); await page.locator('#pfh-detail').waitFor();
      assert.ok(await page.locator('#pfh-dchart svg').count() === 1 || await page.locator('#pfh-dchart .pfc-empty').count() === 1);
      const href = await page.locator('#pfh-detail a:has-text("Analyse du titre")').getAttribute('href'); assert.match(href, /^titre\.html\?id=\d+/);
      await page.locator('#pfh-close').click(); assert.equal(await page.locator('#pfh-detail').count(), 0);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, 'pas de défilement horizontal à ' + width);
      assert.deepEqual(errors, []); await ctx.close(); console.log('ok', width);
    }
  } finally { await b.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
