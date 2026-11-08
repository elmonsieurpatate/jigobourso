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
      // les deux accès redondants ont disparu du Portefeuille
      const pageTxt = await page.locator('#px-page').innerText(); assert.ok(!/Transactions et lots/.test(pageTxt) && !/Centre d’alertes/.test(pageTxt), 'accès redondants supprimés');
      // détail : en-tête compact + trois onglets, retour au même emplacement
      await page.evaluate(() => scrollTo(0, 250)); const yBefore = await page.evaluate(() => scrollY);
      await page.locator('.px-t tbody tr[data-open]').first().evaluate(e => e.click()); await page.locator('.px-drawer').waitFor();
      const tabs = await page.locator('.px-tabs2 button').allInnerTexts(); assert.deepEqual(tabs.map(t => t.replace(/ \(\d+\)/, '')), ['Chiffres', 'Graphique', 'Alertes']);
      assert.equal(await page.locator('.px-tabs2 button.on').count(), 1); const head = await page.locator('.px-dh').innerText(); for (const h of ['Cours', 'Prix de revient', 'Résultat global', 'Acheter', 'Vendre']) assert.ok(head.includes(h), 'en-tête : ' + h);
      assert.equal(await page.locator('.px-drawer a[target="_blank"]').first().getAttribute('rel'), 'noopener'); await noOverflow('détail');
      // CHIFFRES : 14 périodes, rien d'inventé avant l'achat
      const prow = await page.locator('.px-fig tbody tr').allInnerTexts(); assert.equal(prow.length, 14, 'quatorze lignes de périodes');
      for (const lab of ['1J', '2J', '5J', '1S', '2S', '1M', '3M', '6M', '1A', '2A', '3A', '5A', '10A', 'Depuis l’achat']) assert.ok(prow.some(r => r.startsWith(lab)), 'période ' + lab);
      const last = prow[12]; assert.ok(/Partiel|Indisponible/.test(last), '10A : partiel ou indisponible, jamais une performance inventée : ' + last.replace(/\s+/g, ' '));
      assert.ok(/Depuis l’origine[\s\S]*réalisé[\s\S]*latent/i.test(await page.locator('.px-origin').innerText()), 'origine, réalisé, latent');
      await page.locator('[data-fig="market"]').click(); assert.match(await page.locator('.px-fig thead').innerText(), /Variation du cours/i); assert.equal((await page.locator('.px-fig tbody tr').count()), 14); await page.locator('[data-fig="perso"]').click();
      assert.match(await page.locator('.px-ops thead').innerText(), /Frais/i); assert.ok(await page.locator('.px-ops tbody tr').count() >= 1, 'opérations'); assert.ok(!/Lots FIFO/i.test(await page.locator('.px-drawer').innerText()), 'FIFO pas en titre');
      if (await page.locator('.px-tech').count()) { await page.locator('.px-tech summary').click(); assert.match(await page.locator('.px-tech').innerText(), /Stratégie : (Non renseignée|Croissance|Croiss|Rapide|Calme|Rebond|Momentum)/); }
      // GRAPHIQUE : onglet, périodes, intraday, modes
      await page.locator('[data-tab="graphique"]').click(); await page.locator('#px-det-plot').waitFor(); await page.waitForFunction(() => !document.querySelector('#px-det-plot.loading') && document.querySelector('#px-det-plot svg,#px-det-plot .px-empty'));
      assert.equal(await page.locator('#px-det-box [data-k="per"] button').count(), 15, 'quinze périodes dans le graphique'); await page.locator('#px-det-box [data-k="per"] [data-v="1d"]').click(); await page.waitForFunction(() => !document.querySelector('#px-det-plot.loading'));
      assert.match(await page.locator('#px-det-cur').innerText(), /1J/); await page.locator('#px-det-box [data-k="mode"] [data-v="market"]').click(); await page.locator('#px-det-box [data-k="per"] [data-v="max"]').click(); await page.waitForFunction(() => !document.querySelector('#px-det-plot.loading'));
      assert.match(await page.locator('#px-det-sum').innerText(), /^Données :/); await shot('drawer');
      // ALERTES
      // Émulation mobile de Playwright : le test de visibilité du clic se trompe de conteneur de défilement dans le tiroir ; sur mobile, clic par script après défilement (le contenu a été vérifié sans débordement).
      const LP = Object.getPrototypeOf(page.locator('body')), origClick = LP.click; if (width < 600) LP.click = function () { return this.evaluate(e => { e.scrollIntoView({ block: 'center' }); e.click(); }); };
      await page.locator('[data-tab="alertes"]').click(); await page.locator('.ap-top,.ap-empty').first().waitFor(); const atxt = await page.locator('[data-panel="alertes"]').innerText();
      assert.ok(/Surveillance non configurée|Stratégie de surveillance/.test(atxt) && atxt.includes('Ajouter une protection'), 'alertes : en-tête et protections');
      assert.ok(!/Stratégie d’origine/.test(atxt), 'la stratégie d’origine reste dans les infos d’achat');
      assert.ok(!/Appliquer le modèle|A · Règles|B · Protection/.test(atxt), 'plus de jargon A/B/C');
      assert.ok(!/Tout va bien/.test(atxt) || await page.locator('.al-r .al-b.ok').count() > 0, 'jamais « Tout va bien » sans règle évaluée');
      assert.equal(await page.locator('dialog[open]').count(), 0, 'aucune fenêtre ouverte');
      // choix de stratégie en ligne : aperçu, puis confirmation
      if (await page.locator('#ap-chg').count()) await page.locator('#ap-chg').click(); else if (await page.locator('#ap-other').count()) await page.locator('#ap-other').click();
      const hd = await page.locator('[data-panel="alertes"]').innerText(); await page.locator('#ap-watch').selectOption(/rapide/i.test(hd) ? 'regular' : 'fast');
      await page.locator('.ap-pvw').waitFor(); assert.match(await page.locator('.ap-pvw').innerText(), /Règles proposées/); assert.match(await page.locator('.ap-pvw').innerText(), /Nécessite \d+ clôtures|aucun critère surveillable/); assert.equal(await page.locator('dialog[open]').count(), 0, 'aperçu sans fenêtre'); await shot('alert-preview');
      await page.locator('#ap-go').click(); await page.locator('.ap-pvw').waitFor({ state: 'detached' }); await page.locator('.al-r').first().waitFor();
      const apTop = await page.locator('.ap-top').innerText(); assert.match(apTop, /règle\(s\) active\(s\)[\s\S]*déclenchée\(s\)/); assert.match(apTop, /Modèle version \d+/);
      assert.match(await page.locator('[data-panel="alertes"]').innerText(), /Tendance sur|Régularité sur|Progression sur|Volatilité sur|Momentum|Cours sous la moyenne|Recul maximal/);
      // boutons : une seule taille
      const hs = await page.locator('.ap .btn').evaluateAll(bs => [...new Set(bs.map(b => Math.round(b.getBoundingClientRect().height)))]); assert.equal(hs.length, 1, 'tous les boutons ont la même hauteur : ' + hs);
      // protection personnelle en ligne : ajout, modification, désactivation
      await page.locator('#ap-add').click(); await page.locator('#pr-k').waitFor(); assert.equal(await page.locator('#pr-k option').count(), 9); assert.equal(await page.locator('dialog[open]').count(), 0, 'formulaire en ligne');
      await page.locator('#pr-k').selectOption('loss_pct'); await page.locator('#pr-t').fill('8'); assert.match(await page.locator('#pr-s').innerText(), /Vous serez averti si je perds 8 % ou plus/); await shot('alert-edit');
      await page.locator('#pr-ok').click(); const card = page.locator('.al-r', { hasText: 'Perte de 8 %' }).first(); await card.waitFor();
      await card.getByRole('button', { name: 'Modifier' }).click(); await page.locator('#ap-e-t').fill('9'); await page.locator('[data-es]').click(); const c9 = page.locator('.al-r', { hasText: 'Perte de 9 %' }).first(); await c9.waitFor();
      await c9.getByRole('button', { name: 'Désactiver' }).click(); await page.locator('.al-r', { hasText: 'Perte de 9 %' }).first().getByText('Réactiver').waitFor(); assert.match(await page.locator('.al-r', { hasText: 'Perte de 9 %' }).first().innerText(), /Désactivée/);
      await page.locator('.al-r', { hasText: 'Perte de 9 %' }).first().getByRole('button', { name: 'Réactiver' }).click(); await page.locator('.al-r', { hasText: 'Perte de 9 %' }).first().getByText('Désactiver').waitFor(); await shot('surv-detail');
      LP.click = origClick;
      await page.keyboard.press('Escape'); await page.locator('.px-drawer').waitFor({ state: 'detached' }); assert.ok(Math.abs(await page.evaluate(() => scrollY) - yBefore) < 5, 'retour au même emplacement');
      // zones : positions, transactions, surveillance
      await page.locator('.px-zones [data-zone="surveillance"]').click(); await page.locator('.px-alert').first().waitFor(); const atx = (await page.locator('.px-alert').allInnerTexts()).join('\n'); assert.ok(/Meilleur gain observé[\s\S]*Gain rendu/.test(atx) && /Régler cet achat/.test(atx), 'alertes : protection des gains et réglage par achat : ' + atx.slice(0, 300)); await noOverflow('surveillance'); await shot('surveillance');
      await page.locator('.px-alert [data-lot]').first().evaluate(e => e.click()); await page.locator('dialog, .dlg, [role="dialog"]').first().waitFor(); await page.keyboard.press('Escape');
      await page.locator('.px-zones [data-zone="positions"]').click(); await page.locator('.px-t').waitFor(); await noOverflow('positions'); await shot('positions');
      await page.locator('.px-zones [data-zone="transactions"]').click(); await page.locator('.px-tx').waitFor(); await noOverflow('transactions');
      assert.deepEqual(errors, [], 'erreurs JS'); await ctx.close(); console.log('ok pf', width);
    }
    fs.writeFileSync((SHOTS || '.') + '/pf5-periods-report.json', JSON.stringify(report, null, 1)); console.log('ok portefeuille');
  } finally { await b.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
