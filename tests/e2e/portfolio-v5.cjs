/* Portefeuille V4 (spécification exécutable) : zones, graphique partagé J.financialChart, 15 périodes × 2 modes, thème clair/sombre, tableau, panneau de détail,
   surveillance intégrée, création d'alerte, changement de stratégie avec aperçu, mobile 320→1440 sans débordement. Écrit un rapport de couverture par période. */
const assert = require('node:assert/strict'); const fs = require('node:fs'); const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const BASE = process.env.BASE || 'http://127.0.0.1:18095', SHOTS = process.env.SHOTS || '';
const PERIODS = ['1d', '2d', '5d', '1w', '2w', '1m', '3m', '6m', '1y', '2y', '3y', '5y', '10y', 'max', 'all'];
(async () => {
  const b = await chromium.launch({ executablePath: process.env.JIGO_CHROMIUM, args: ['--no-sandbox'] }); const report = [];
  try {
    for (const width of [320, 375, 390, 430, 768, 1024, 1440]) {
      const ctx = await b.newContext({ viewport: { width, height: width > 700 ? 1000 : 900 }, isMobile: width < 600, hasTouch: width < 600 });
      const page = await ctx.newPage(), errors = []; page.on('pageerror', e => errors.push(e.message)); page.on('console', m => { if (m.type() === 'error' && !/favicon|Failed to load resource/.test(m.text())) errors.push(m.text()); }); page.setDefaultTimeout(20000);
      assert.equal((await ctx.request.post(BASE + '/api.php?r=auth/login', { data: { username: 'audit_portfolio', password: 'audit-local-validation-2026' } })).ok(), true);
      const list = (await (await ctx.request.get(BASE + '/api.php?r=portfolios')).json()).portfolios;
      let id = null, rows = 0;
      for (const p of list) { await page.goto(BASE + '/portefeuilles.html?id=' + p.id); await page.locator('.px-zones').waitFor(); const n = await page.locator('.px-t tbody tr').count(); if (n > rows) { rows = n; id = p.id; } }
      assert.ok(id, 'portefeuille avec positions'); await page.goto(BASE + '/portefeuilles.html?id=' + id); await page.locator('.px-zones').waitFor();
      const shot = async n => { if (SHOTS && [390, 1440].includes(width)) await page.screenshot({ path: `${SHOTS}/pf5-${n}-${width}.png`, fullPage: n !== 'drawer' && n !== 'surv-detail' && n !== 'alert-edit' }); };
      const noOverflow = async tag => assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, `débordement horizontal ${tag} ${width}`);
      const settle = async () => { await page.waitForFunction(() => !document.querySelector('#px-main-plot.loading') && document.querySelector('#px-main-plot svg,#px-main-plot .px-empty')); };
      // quatre zones, ordre de la vue d'ensemble
      assert.deepEqual(await page.locator('.px-zones button').allInnerTexts(), ['Vue d’ensemble', 'Positions', 'Transactions', 'Surveillance']);
      const order = await page.evaluate(() => ['.px-head', '.px-syn', '.px-sum', '#px-main-box', '.px-t'].map(s => document.querySelector(s).getBoundingClientRect().top));
      assert.deepEqual(order, [...order].sort((x, y) => x - y), 'ordre : en-tête, synthèse, alertes, graphique, positions');
      await settle(); await noOverflow('overview'); await shot('overview');
      // thème : les cartes suivent les variables du thème (pas de fond forcé)
      const bg = () => page.evaluate(() => getComputedStyle(document.querySelector('.px-card')).backgroundColor);
      const light = await bg(); await page.evaluate(() => { document.documentElement.dataset.theme = 'dark'; }); const dark = await bg(); await page.evaluate(() => { document.documentElement.dataset.theme = 'light'; });
      assert.notEqual(light, dark, 'le thème change les couleurs'); assert.notEqual(light, 'rgb(15, 33, 66)');
      // périodes × modes (rapport de couverture)
      for (const mode of ['perso', 'market']) {
        await page.locator(`#px-main-box [data-k="mode"] [data-v="${mode}"]`).click();
        for (const per of PERIODS) {
          await page.locator(`#px-main-box [data-k="per"] [data-v="${per}"]`).click(); await settle();
          const cur = await page.locator('#px-main-cur').innerText(), sum = await page.locator('#px-main-sum').innerText(), hasSvg = await page.locator('#px-main-plot svg.fc-svg').count();
          assert.match(sum, /^Données :/); assert.ok(hasSvg || await page.locator('#px-main-plot .px-empty').count(), `${mode} ${per} : graphique ou message`);
          if (width === 1440) report.push({ mode, per, cur: cur.replace(/\s+/g, ' '), data: sum });
        }
      }
      await noOverflow('périodes');
      // cours indépendants de la date d'achat : « Max » remonte avant la première opération
      const early = await page.evaluate(async () => { const C = PFHome.ctx(), st = { mode: 'market', per: 'max', unit: 'pct' }, keys = C.D.positions.filter(p => p.qty > 0).map(p => p.listing_id ? String(p.listing_id) : 'S' + p.symbol.toUpperCase()); const o = await PFHome.build(st, { keys, pf: false }); return { first: o.times[0], op: C.H.dates[0], n: o.series.length }; });
      assert.ok(early.n >= 1 && String(early.first).slice(0, 10) <= early.op, `max market commence avant ou à la première opération ${JSON.stringify(early)}`);
      // lignes et marqueurs, bascule € / %
      await page.locator('#px-main-box [data-k="mode"] [data-v="perso"]').click(); await page.locator('#px-main-box [data-k="per"] [data-v="all"]').click(); await settle();
      await page.locator('#px-main-box [data-k="unit"] [data-v="eur"]').click(); await settle(); await page.locator('#px-main-box [data-k="unit"] [data-v="pct"]').click(); await settle();
      // pastille : masquer une courbe garde les autres
      const chips = page.locator('#px-main-leg .px-chip'); const nChips = await chips.count(); assert.ok(nChips >= 2); const before = await page.locator('#px-main-plot path[data-curve]').count();
      await chips.nth(1).click(); await settle(); assert.equal(await page.locator('#px-main-plot path[data-curve]').count(), before - 1); await page.locator('#px-main-leg .px-chip').nth(1).click(); await settle();
      // pas de saut de défilement au changement de période
      const y0 = await page.evaluate(() => scrollY); await page.locator('#px-main-box [data-k="per"] [data-v="3m"]').click(); await settle(); assert.equal(await page.evaluate(() => scrollY), y0, 'défilement stable');
      if (width > 700) { // zoom par glissement : ni sélection de texte ni défilement
        const box = await page.locator('#px-main-plot .fc-plot').boundingBox(); const sy = await page.evaluate(() => scrollY);
        await page.mouse.move(box.x + box.width * 0.4, box.y + box.height / 2); await page.mouse.down(); await page.mouse.move(box.x + box.width * 0.7, box.y + box.height / 2, { steps: 6 }); await page.mouse.up();
        assert.equal(await page.evaluate(() => getSelection().toString()), '', 'aucune sélection de texte'); assert.equal(await page.evaluate(() => scrollY), sy);
        await page.locator('#px-main-plot .fc-plot').dblclick({ position: { x: box.width / 2, y: box.height / 2 } });
        await page.mouse.move(box.x + box.width * 0.5, box.y + box.height / 2); await page.waitForTimeout(100); assert.ok(await page.locator('#px-main-plot .fc-tip').isVisible(), 'infobulle');
      }
      // tableau compact : en-têtes, tri stable, ligne cliquable
      if (width >= 1024) { for (const h of ['Titre', 'Valeur', 'Gain/perte', 'Rendement', 'Surveillance', 'Actions']) assert.ok((await page.locator('.px-t thead').first().innerText()).toLowerCase().includes(h.toLowerCase()), h); }
      await noOverflow('tableau'); await page.locator('.px-t [data-sort="value"]').first().evaluate(e => e.click());
      // détail en panneau avec surveillance intégrée
      await page.locator('.px-t tbody tr[data-open]').first().evaluate(e => e.click()); await page.locator('.px-drawer').waitFor();
      const dtxt = await page.locator('.px-drawer').innerText();
      for (const s of ['Synthèse financière', 'Évolution', 'Stratégies', 'Surveillance', 'Transactions et lots', 'Stratégie d’origine', 'A · Règles de la stratégie', 'B · Protection', 'C · Compléments', 'D · Historique']) assert.ok(dtxt.includes(s), 'détail : ' + s);
      const secOrder = await page.evaluate(() => [...document.querySelectorAll('.px-db > section h3')].map(h => h.textContent)); assert.deepEqual(secOrder.slice(0, 5), ['Synthèse financière', 'Évolution', 'Stratégies', 'Surveillance', 'Transactions et lots']);
      assert.equal(await page.locator('.px-drawer a[target="_blank"]').first().getAttribute('rel'), 'noopener'); await noOverflow('détail');
      await page.waitForFunction(() => !document.querySelector('#px-det-plot.loading')); await page.locator('#px-det-box [data-k="per"] [data-v="1y"]').click(); await page.locator('#px-det-box [data-k="mode"] [data-v="market"]').click(); await page.waitForFunction(() => !document.querySelector('#px-det-plot.loading'));
      assert.match(await page.locator('#px-det-cur').innerText(), /1A/); await shot('drawer');
      // création d'une alerte de protection par l'assistant
      await page.locator('[data-new="invest"]').click(); await page.locator('#ar-t').fill('12'); await page.locator('#ar-k').selectOption('drawdown_from_high');
      assert.match(await page.locator('#ar-sum').innerText(), /Vous serez alerté si le cours recule d’au moins 12 %/); await shot('alert-edit');
      await page.getByRole('button', { name: 'Enregistrer' }).click(); await page.locator('.al-r', { hasText: 'Recul depuis le plus haut cours' }).first().waitFor();
      assert.match(await page.locator('.px-drawer').innerText(), /Alerte si le cours recule d’au moins 12 %/);
      // changement de stratégie de surveillance : aperçu puis confirmation
      await page.locator('#ap-watch').selectOption('regular'); await page.locator('#ap-apply').click(); await page.locator('dialog[open]').first().waitFor(); const prev = await page.locator('dialog[open]').first().innerText(); assert.match(prev, /Règles ajoutées|Rien à modifier|Seuils/);
      await page.getByRole('button', { name: 'Confirmer' }).click(); await page.locator('.al-r').first().waitFor(); await shot('surv-detail');
      await page.locator('dialog[open]').waitFor({ state: 'detached' }); await page.keyboard.press('Escape'); await page.locator('.px-drawer').waitFor({ state: 'detached' });
      // zones : positions, transactions, surveillance
      await page.locator('.px-zones [data-zone="surveillance"]').click(); await page.locator('.px-sv').waitFor(); assert.match(await page.locator('.px-sv thead').innerText(), /Stratégie de surveillance[\s\S]*Dernière évaluation/i); await noOverflow('surveillance'); await shot('surveillance');
      await page.locator('.px-sv [data-conf]').first().evaluate(e => e.click()); await page.locator('.px-drawer').waitFor(); await page.keyboard.press('Escape');
      await page.locator('.px-zones [data-zone="positions"]').click(); await page.locator('.px-t').waitFor(); await noOverflow('positions'); await shot('positions');
      await page.locator('.px-zones [data-zone="transactions"]').click(); await page.locator('.px-tx').waitFor(); await noOverflow('transactions');
      assert.deepEqual(errors, [], 'erreurs JS'); await ctx.close(); console.log('ok pf', width);
    }
    fs.writeFileSync((SHOTS || '.') + '/pf5-periods-report.json', JSON.stringify(report, null, 1)); console.log('ok portefeuille');
  } finally { await b.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
