/* Plan de suivi (spécification exécutable) : zones sans « Positions » ni « Surveillance », table et graphique de la Vue d'ensemble conservés, onglet « Plan de suivi » du détail,
   jauge (repères, échelle), conseils par scénario chiffré, protection personnelle jamais écrasée, une stratégie de surveillance par position, mobile 320→1440 sans débordement.
   Base : tests/e2e/plan_suivi_seed.py. Serveur : php8.3 -S 127.0.0.1:18096 -t app/public. */
const assert = require('node:assert/strict'); const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const BASE = process.env.BASE || 'http://127.0.0.1:18096', SHOTS = process.env.SHOTS || '';
const text = s => s.replace(/\s+/g, ' ').trim();
(async () => {
  const b = await chromium.launch({ executablePath: process.env.JIGO_CHROMIUM, args: ['--no-sandbox'] }); const report = [];
  try {
    for (const width of [320, 390, 768, 1440]) {
      const ctx = await b.newContext({ viewport: { width, height: width > 700 ? 1000 : 900 }, isMobile: width < 600, hasTouch: width < 600 });
      const page = await ctx.newPage(), errors = [];
      page.on('pageerror', e => errors.push(e.message)); page.on('console', m => { if (m.type() === 'error' && !/favicon|Failed to load resource/.test(m.text())) errors.push(m.text()); });
      assert.equal((await ctx.request.post(BASE + '/api.php?r=auth/login', { data: { username: 'plan_suivi', password: 'plan-suivi-local-2026' } })).ok(), true);
      await page.goto(BASE + '/portefeuilles.html?id=1'); await page.locator('.px-zones').waitFor(); await page.waitForSelector('.px-t tbody tr');
      const noOverflow = async tag => assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, `débordement horizontal ${tag} ${width}`);
      const shot = async n => { if (SHOTS && [390, 1440].includes(width)) await page.screenshot({ path: `${SHOTS}/ps-${n}-${width}.png`, fullPage: false }); };
      // 0. PRU : une seule source. Le plan reprend le prix de revient moyen du portefeuille (ledger), sans second calcul.
      //    MULTILOT : achats 10@100, 5@130, 5@150, vente de 8 au PRU moyen -> 12 titres à 120 € (une moyenne FIFO des lots restants donnerait 133,33 : contradictoire, volontairement non utilisée).
      { const pf = await (await ctx.request.get(BASE + '/api.php?r=portfolio&id=1')).json(), st = await (await ctx.request.get(BASE + '/api.php?r=tracking/state&portfolio=1')).json(); let n = 0;
        for (const pos of pf.positions.filter(x => x.listing_id && x.qty > 0)) { const pl = st.positions[String(pos.listing_id)]; if (!pl || !pl.prices) continue; n++;
          assert.ok(Math.abs(pl.prices.pru - pos.avg_cost) < 1e-9, `PRU du plan ≠ PRU du portefeuille pour ${pos.symbol} : ${pl.prices.pru} vs ${pos.avg_cost}`); }
        assert.ok(n >= 15, 'PRU comparé sur toutes les positions'); const ml = pf.positions.find(x => x.symbol === 'MULTILOT');
        assert.ok(Math.abs(ml.avg_cost - 120) < 1e-9 && Math.abs(ml.qty - 12) < 1e-9, 'MULTILOT : 12 titres à 120 €');
        assert.ok(Math.abs(st.positions[String(ml.listing_id)].prices.pru - 120) < 1e-9, 'jauge MULTILOT : 120 €'); }
      // 1. navigation : deux zones, plus d'onglet Positions ni Surveillance, plus d'entrée « Alertes »
      assert.deepEqual(await page.locator('.px-zones button').allInnerTexts(), ['Vue d’ensemble', 'Transactions']);
      await page.waitForFunction(() => !/Chargement/.test(document.querySelector('.px-sum').innerText)); await noOverflow('overview');
      assert.equal(await page.locator('a[href="alertes.html"]').count(), 0, 'plus de lien vers le Centre d’alertes');
      assert.match(await page.locator('.px-sum').innerText(), /Suivi des positions/); assert.doesNotMatch(await page.locator('body').innerText(), /Surveillance/);
      // 2. la liste des positions : toutes les positions ouvertes (plus de limite à 8), colonnes inchangées sauf « Suivi »
      const heads = (await page.locator('.px-t thead th').allInnerTexts()).map(t => t.replace(/[▲▼]/g, '').trim().toLowerCase());
      assert.deepEqual(heads, ['titre', 'valeur', 'gain/perte', 'rendement', 'contribution', 'poids', 'stratégie', 'suivi', 'actions']);
      assert.equal(await page.locator('.px-t tbody tr').count(), 20, '20 positions ouvertes');
      assert.equal(await page.locator('.px-more').count(), 0);
      const closedBox = page.locator('#px-closed'); assert.equal(await closedBox.count(), 1, 'positions soldées : case dans la Vue d’ensemble');
      await closedBox.check(); assert.equal(await page.locator('.px-t tbody tr').count(), 21); await page.locator('#px-closed').uncheck();
      assert.ok(await page.locator('#px-main-box').count(), 'graphique conservé');
      await shot('overview');
      // 3. détail d'une position : onglets Chiffres, Graphique, Plan de suivi
      const open = async sym => { await page.locator(`.px-t tbody tr:has(.c-title b:text-is("${sym}"))`).click(); await page.locator('.px-drawer').waitFor(); };
      const plan = async () => { await page.locator('.px-tabs2 [data-tab="suivi"]').click(); await page.locator('.ps-card').waitFor(); return page.locator('.ps-card'); };
      const close = async () => { await page.locator('.px-dact [data-close]').click(); await page.locator('.px-drawer').waitFor({ state: 'detached' }); };
      await open('RISEUP'); assert.deepEqual((await page.locator('.px-tabs2 button').allInnerTexts()).map(text), ['Chiffres', 'Graphique', 'Plan de suivi']);
      let card = await plan();
      // forte hausse 100 -> 160 : aucun conseil de vente, jauge complète
      assert.match(await card.locator('.ps-advice').innerText(), /progresse sans signal de vigilance/); assert.doesNotMatch(await card.innerText(), /vendre maintenant|il faut vendre|objectif de vente (de|à|:)/i);
      assert.equal(await card.locator('.ps-track .ps-mk').count(), 4, 'PRU, cours, plus-haut, protection suggérée (pas de protection perso)');
      assert.equal(await card.locator('.ps-track .ps-m-personal').count(), 0, 'pas de protection perso inventée');
      for (const k of ['.ps-m-suggested', '.ps-m-pru', '.ps-m-current', '.ps-m-high']) assert.ok(await card.locator('.ps-track ' + k).count(), k);
      assert.equal(await card.locator('.ps-tile').count(), 4); assert.match(await card.locator('.ps-tiles').innerText(), /Tendance[\s\S]*Haussière[\s\S]*Risque[\s\S]*Modéré[\s\S]*Recul depuis le sommet[\s\S]*Momentum 6−1/);
      // ordre horizontal (valeurs 100 < 129,57 < 160 <= plus-haut) : PRU < suggérée < cours <= plus-haut
      const xs = await card.locator('.ps-track .ps-mk').evaluateAll(els => Object.fromEntries(els.map(e => [e.className.match(/ps-m-(\w+)/)[1], e.getBoundingClientRect().left + e.getBoundingClientRect().width / 2])));
      assert.ok(xs.pru < xs.suggested && xs.suggested < xs.current && xs.current <= xs.high + 1, JSON.stringify(xs));
      await noOverflow('drawer plan'); await shot('plan-rise');
      assert.match(await card.locator('.ps-foot').innerText(), /jamais un ordre de vente/); assert.match(await card.locator('.ps-foot').innerText(), /Aucun objectif de gain/);
      await close();
      // correction 160 -> 150 / recul important
      await open('CORRECT'); card = await plan(); assert.match(await card.locator('.ps-advice').innerText(), /sans signal de vigilance/); await close();
      await open('DEEP140'); card = await plan(); assert.match(await card.locator('.ps-advice').innerText(), /momentum de moyen terme est devenu négatif/); assert.match(await card.locator('.ps-advice').innerText(), /peut remonter/); await shot('plan-deep140'); await close();
      await open('DEEP120'); card = await plan(); assert.match(await card.locator('.ps-advice').innerText(), /repère de risque|momentum/); assert.match(await card.locator('.ps-advice').innerText(), /pas un signal de vente/); await close();
      // protection personnelle : distincte de la suggestion, jamais écrasée
      await open('PERSOSTOP'); card = await plan(); assert.equal(await card.locator('.ps-track .ps-m-personal').count(), 1); assert.match(await card.locator('.ps-labels, .ps-legend').first().innerText(), /110,00/);
      assert.match(await card.locator('.ps-foot').innerText(), /Objectif personnel enregistré : 200/); await shot('plan-personal');
      const before = await (await ctx.request.get(BASE + '/api.php?r=portfolio&id=1')).json(); const lv0 = before.positions.find(p => p.symbol === 'PERSOSTOP').levels;
      await card.locator('[data-ps-settings]').click(); await page.locator('dialog #ps-st').selectOption('regular'); await page.locator('dialog .btn.primary').click(); await page.waitForFunction(() => !document.querySelector('dialog[open]'));
      const after = await (await ctx.request.get(BASE + '/api.php?r=portfolio&id=1')).json(); assert.deepEqual(after.positions.find(p => p.symbol === 'PERSOSTOP').levels, lv0, 'protection et objectif intacts après changement de stratégie');
      await page.waitForFunction(() => /Croissance régulière/.test(document.querySelector('.ps-chip')?.innerText || '')); await close();
      // multi-lots : une seule jauge, une stratégie de surveillance, trois origines conservées
      await open('MULTILOT'); assert.match(text(await page.locator('.px-drawer').first().innerText()), /Prix de revient 120,00 €/); card = await plan(); assert.match(text(await card.innerText()), /PRU 120,00 €/); assert.equal(await card.locator('.ps-gauge').count(), 1); assert.match(await card.locator('.ps-chip').innerText(), /Croissance régulière/);
      const origin = await card.locator('.ps-origin').innerText(); for (const o of ['Croissance rapide', 'Croissance régulière', 'Rebond']) assert.match(origin, new RegExp(o));
      await close();
      // sept stratégies
      const expect = { FAST: [/Croissance rapide/, /momentum de moyen terme est devenu négatif/], REGULAR: [/Croissance régulière/, /momentum de moyen terme est devenu négatif/], CALM: [/Hausse calme/, /Vigilance renforcée/], REBOUND: [/Rebond/, /repère de risque/],
        MOM6: [/Momentum 6 mois/, /Vigilance renforcée/], MOM12: [/Momentum 12 mois/, /provisoire/], MOMRISK: [/ajusté au risque/, /provisoire/], NOSTRAT: [/non définie/, /repère de risque/] };
      for (const [sym, [chip, msg]] of Object.entries(expect)) { await open(sym); card = await plan(); assert.match(await card.locator('.ps-chip').innerText(), chip, sym); assert.match(await card.locator('.ps-advice').innerText(), msg, sym); if (sym === 'REBOUND') assert.doesNotMatch(await card.locator('.ps-advice').innerText(), /momentum de moyen terme est devenu/); await close(); }
      // cas particuliers : historique court, ETF, devise
      await open('SHORT'); card = await plan(); assert.match(await card.locator('.ps-advice').innerText(), /historique insuffisant/); assert.equal(await card.locator('.ps-track .ps-m-suggested').count(), 0, 'aucune protection inventée'); assert.match(await card.innerText(), /indisponible/); await close();
      await open('ETFSAFE'); card = await plan(); assert.match(await card.locator('.ps-tiles').innerText(), /Faible/); await close();
      await open('USDPOS'); card = await plan(); assert.match(await card.locator('.ps-advice').innerText(), /progresse/); await close();
      // position en perte, sans protection perso
      await open('LOSS'); card = await plan(); assert.match(await card.locator('.ps-gain').innerText(), /^−/); assert.equal(await card.locator('.ps-track .ps-m-personal').count(), 0); assert.equal(await card.locator('.ps-track .ps-m-suggested').count(), 1);
      assert.match(await card.locator('.ps-advice').innerText(), /Surveille le repère de protection suggéré/); assert.doesNotMatch(await card.locator('.ps-advice').innerText(), /ton niveau de protection\./);
      { const x = await card.locator('.ps-track .ps-mk').evaluateAll(els => Object.fromEntries(els.map(e => [e.className.match(/ps-m-(\w+)/)[1], e.getBoundingClientRect().left]))); assert.ok(x.suggested < x.current && x.current < x.pru, 'perte : protection < cours < PRU ' + JSON.stringify(x)); }
      await close();
      // perte, protection perso AU-DESSUS du cours : atteinte, jamais écrasée
      await open('LOSSPERS'); card = await plan(); assert.match(await card.locator('.ps-advice').innerText(), /protection personnel est atteint/); assert.equal(await card.locator('.ps-track .ps-m-personal').count(), 1);
      { const x = await card.locator('.ps-track .ps-mk').evaluateAll(els => Object.fromEntries(els.map(e => [e.className.match(/ps-m-(\w+)/)[1], e.getBoundingClientRect().left]))); assert.ok(x.personal > x.current, 'protection perso au-dessus du cours ' + JSON.stringify(x)); }
      await close();
      // repères superposés (PRU ≈ cours ≈ plus-haut) : étiquettes lisibles, jamais l'une sur l'autre
      await open('CROWD'); card = await plan(); assert.equal(await card.locator('.ps-track .ps-mk').count(), 4);
      if (await card.locator('.ps-labels').isVisible()) { const r = await card.locator('.ps-lb').evaluateAll(els => els.map(e => { const b = e.getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; }));
        for (let i = 0; i < r.length; i++) for (let j = i + 1; j < r.length; j++) assert.ok(r[i][2] <= r[j][0] + 1 || r[j][2] <= r[i][0] + 1 || r[i][3] <= r[j][1] + 1 || r[j][3] <= r[i][1] + 1, `étiquettes ${i}/${j} superposées`); }
      else assert.equal(await card.locator('.ps-legend li').count(), 4, 'légende mobile : 4 lignes');
      await noOverflow('crowd'); await close();
      // thème sombre : contraste des textes du plan (≥ 4,5:1) et fond sombre
      for (const theme of ['dark', 'light']) { await page.evaluate(t => { document.documentElement.dataset.theme = t; }, theme);
      for (const sym of ['LOSSPERS', 'RISEUP', 'LOSS']) { await open(sym); card = await plan();
        const ratios = await card.evaluate(c => { const lum = rgb => { const v = rgb.match(/[\d.]+/g).slice(0, 3).map(Number).map(x => { x /= 255; return x <= .03928 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4; }); return .2126 * v[0] + .7152 * v[1] + .0722 * v[2]; };
          const bgOf = el => { for (let e = el; e; e = e.parentElement) { const b = getComputedStyle(e).backgroundColor; const a = b.match(/[\d.]+/g); if (a && (a.length < 4 || +a[3] > .5)) return b; } return 'rgb(255,255,255)'; };
          return [...c.querySelectorAll('.ps-advice b, .ps-advice p, .ps-tile b, .ps-tile small, .ps-lb b, .ps-lb strong, .ps-legend li, .ps-gain strong, .ps-foot p')].filter(e => e.offsetParent && e.textContent.trim()).map(e => { const f = lum(getComputedStyle(e).color), g = lum(bgOf(e)), [hi, lo] = f > g ? [f, g] : [g, f]; return { t: e.textContent.trim().slice(0, 30), r: (hi + .05) / (lo + .05) }; }); });
        const bad = ratios.filter(x => x.r < 4.5); assert.deepEqual(bad, [], 'contraste insuffisant (' + theme + ') ' + sym); assert.ok(await card.evaluate((c, th) => { const m = getComputedStyle(c).backgroundColor.match(/\d+/g).map(Number), sum = m[0] + m[1] + m[2]; return th === 'dark' ? sum < 300 : sum > 600; }, theme), 'fond de carte ' + theme); await close(); } }
      // lots : toujours consultables et réglables depuis le détail (sans onglet Positions)
      await open('MULTILOT'); await page.locator('.px-tabs2 [data-tab="chiffres"]').click(); await page.locator('.px-tech summary').click();
      assert.equal(await page.locator('.px-tech [data-lot]').count(), 3, 'trois lots restants'); assert.match(await page.locator('.px-tech').innerText(), /Stratégie d’origine : Croissance rapide/);
      await page.locator('.px-tech [data-lot]').first().click(); await page.locator('dialog #lt-st').waitFor(); assert.match(await page.locator('dialog').innerText(), /Stratégie de cet achat/); assert.equal(await page.locator('dialog #lt-off').count(), 0, 'case « Désactiver les alertes de cet achat » retirée'); assert.doesNotMatch(await page.locator('dialog').innerText(), /Désactiver les alertes/); for (const id of ['#lt-days', '#lt-drop']) assert.equal(await page.locator('dialog ' + id).count(), 1, 'autres réglages du lot conservés ' + id);
      await page.locator('dialog button:has-text("Annuler")').click(); await page.waitForFunction(() => !document.querySelector('dialog[open]')); await close();
      // la colonne « Suivi » du tableau ouvre directement le plan
      await page.locator('.px-t tbody tr:has(.c-title b:text-is("DEEP140")) .px-w').click(); await page.locator('.ps-card').waitFor(); await close();
      // zone Transactions inchangée
      await page.locator('.px-zones [data-zone="transactions"]').click(); assert.ok(await page.locator('.px-tx').count()); await page.locator('[data-hist]').first().click(); await page.waitForSelector('#back-home'); assert.match(await page.locator('#panel-manage').innerText(), /Lots et réglages/); assert.doesNotMatch(await page.locator('#panel-manage').innerText(), /Lots et réglages des alertes|Surveillance/); await page.locator('#back-home').click(); await page.locator('.px-zones').waitFor(); await page.locator('.px-zones [data-zone="transactions"]').click(); await page.locator('.px-zones [data-zone="overview"]').click();
      await noOverflow('final');
      assert.deepEqual(errors, [], 'aucune erreur JavaScript : ' + errors.join(' | '));
      report.push(width); await ctx.close();
    }
    console.log('Plan de suivi : OK sur', report.join(', '), 'px');
  } finally { await b.close(); }
})().catch(e => { console.error(e); process.exit(1); });
