/* Suivi des positions (spécification exécutable) : section repliable sous le tableau, une ligne par position, jauge, états, configuration par règle,
   cohérence ligne/détail, sections repliables, thèmes, mobile 320→1440 sans débord. Base : tests/seeds/plan_suivi_seed.py. Serveur : php8.3 -S 127.0.0.1:18096 -t app/public. */
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
      assert.match(await page.locator('.px-sum').innerText(), /Synthèse du suivi/); assert.match(await page.locator('#px-sec-suivi h2').innerText(), /Suivi des positions/); assert.doesNotMatch(await page.locator('body').innerText(), /Surveillance/);
      // 2. la liste des positions : toutes les positions ouvertes (plus de limite à 8), colonnes inchangées sauf « Suivi »
      const heads = (await page.locator('.px-t thead th').allInnerTexts()).map(t => t.replace(/[▲▼]/g, '').trim().toLowerCase());
      assert.deepEqual(heads, ['titre', 'valeur', 'gain/perte', 'rendement', 'contribution', 'poids', 'stratégie', 'suivi', 'actions']);
      assert.equal(await page.locator('.px-t tbody tr').count(), 25, '25 positions ouvertes');
      assert.equal(await page.locator('.px-more').count(), 0);
      const closedBox = page.locator('#px-closed'); assert.equal(await closedBox.count(), 1, 'positions soldées : case dans la Vue d’ensemble');
      await closedBox.check(); assert.equal(await page.locator('.px-t tbody tr').count(), 26); await page.locator('#px-closed').uncheck();
      assert.ok(await page.locator('#px-main-box').count(), 'graphique conservé');
      await shot('overview');

      // 3. « Suivi des positions » : sous le tableau, une ligne par position ouverte, toutes visibles sans ouvrir de détail
      const sec = page.locator('#px-sec-suivi'); await sec.locator('.psr').first().waitFor();
      assert.equal(await sec.locator('.psr').count(), 25, 'une ligne par position ouverte');
      assert.equal(await page.evaluate(() => { const p = document.querySelector('#px-sec-positions'), s = document.querySelector('#px-sec-suivi'); return !!(p.compareDocumentPosition(s) & Node.DOCUMENT_POSITION_FOLLOWING); }), true, 'Suivi des positions sous le tableau Positions');
      { const tops = await sec.locator('.psr').evaluateAll(els => els.map(e => Math.round(e.getBoundingClientRect().top))); assert.equal(new Set(tops).size, tops.length, 'jamais deux positions sur la même ligne'); }
      const row = sym => sec.locator(`.psr:has(.psr-name strong:text-is("${sym}"))`);
      const adv = async sym => text(await row(sym).evaluate(e => (e.querySelector('.psr-adv').textContent + ' ' + e.querySelector('.psr-more').textContent)));
      const states = ['SUIVI PARTIEL', 'CONSERVER', 'SURVEILLER', 'RÉÉVALUER', 'SORTIE À ENVISAGER'];
      for (const t of await sec.locator('.psr .psr-adv').allInnerTexts()) assert.ok(states.some(x => t.includes(x)), 'chaque ligne porte un état : ' + text(t).slice(0, 60));
      await noOverflow('suivi'); await shot('suivi');
      // 4. cas chiffrés : chaque conseil nomme la règle déclenchée
      assert.match(await adv('GIBO'), /SURVEILLER[\s\S]*La hausse se poursuit, mais le risque de repli est très élevé/i); assert.match(await adv('GIBO'), /Protection automatique : [\d\s.,  ]+ €\. Tu peux la modifier/i); assert.doesNotMatch(await adv('GIBO'), /SORTIE|RÉÉVALUER/i, 'forte volatilité seule : jamais un ordre de sortie');
      assert.match(await adv('RISEUP'), /CONSERVER/i); assert.match(await adv('MULTILOT'), /CONSERVER/i);
      assert.match(await adv('LOSSPERS'), /SORTIE À ENVISAGER[\s\S]*protection personnelle/i);
      assert.match(await adv('TARGETHIT'), /SORTIE À ENVISAGER[\s\S]*objectif de gain/i);
      assert.match(await adv('RECULPERS'), /RÉÉVALUER[\s\S]*seuil de [\s\S]*5,0 %/i); assert.match(await adv('MULTIRULE'), /RÉÉVALUER/i);
      assert.match(await adv('FAST'), /SORTIE À ENVISAGER[\s\S]*protection automatique/i, 'protection automatique franchie');
      assert.match(await adv('NOSTOP'), /SURVEILLER|CONSERVER/i); assert.doesNotMatch(await adv('NOSTOP'), /SORTIE/i, 'règle de protection désactivée : pas de sortie');
      assert.match(await adv('SHORT'), /historique insuffisant|Historique insuffisant/i); assert.equal(await row('SHORT').locator('.ps-mk').count() <= 3, true); assert.doesNotMatch(await row('SHORT').innerText(), /Protection auto\s*\d/i, 'aucune protection inventée');
      // priorité : sortie > réévaluer > surveiller > conserver ; autres règles consultables
      { const r = row('MULTIRULE'), btn = r.locator('[data-ps-exp]'); assert.equal(await r.locator('.psr-more').isVisible(), false, 'détail replié par défaut'); await btn.click(); assert.equal(await r.locator('.psr-more').isVisible(), true); assert.equal(await btn.getAttribute('aria-expanded'), 'true'); await btn.click(); assert.equal(await r.locator('.psr-more').isVisible(), false); }
      // jauge : repères aux vrais prix, PRU non centré, perte (protection < cours < PRU), protection perso au-dessus du cours
      const xs = async sym => row(sym).locator('.ps-track .ps-mk').evaluateAll(els => Object.fromEntries(els.map(e => [e.className.match(/ps-m-(\w+)/)[1], e.getBoundingClientRect().left + e.getBoundingClientRect().width / 2])));
      { const x = await xs('LOSS'); assert.ok(x.suggested < x.current && x.current < x.pru, 'perte ' + JSON.stringify(x)); }
      { const x = await xs('LOSSPERS'); assert.ok(x.personal > x.current, 'protection perso au-dessus du cours ' + JSON.stringify(x)); }
      { const x = await xs('GIBO'); assert.ok(x.pru < x.suggested && x.suggested < x.current, 'GIBO ' + JSON.stringify(x)); }
      { const x = await xs('MULTIRULE'); assert.ok(x.pru < x.personal && x.personal < x.current && x.current < x.suggested, 'protection perso au-dessus du PRU ' + JSON.stringify(x)); }
      assert.equal(await row('CROWD').locator('.ps-mk').count() >= 3, true);
      for (const sym of ['CROWD', 'GIBO', 'MULTIRULE', 'LOSSPERS']) { const lb = row(sym).locator('.ps-lb'); if (await row(sym).locator('.ps-labels').first().isVisible()) { const r = await lb.evaluateAll(els => els.map(e => { const b = e.getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; }));
        for (let i = 0; i < r.length; i++) for (let j = i + 1; j < r.length; j++) assert.ok(r[i][2] <= r[j][0] + 1 || r[j][2] <= r[i][0] + 1 || r[i][3] <= r[j][1] + 1 || r[j][3] <= r[i][1] + 1, `étiquettes ${sym} ${i}/${j} superposées`); } }
      // 5. sept stratégies : chaque ligne affiche sa stratégie de surveillance
      for (const [sym, chip] of Object.entries({ FAST: /Croissance rapide/, REGULAR: /Croissance régulière/, CALM: /Hausse calme/, REBOUND: /Rebond/, MOM6: /Momentum 6 mois/, MOM12: /Momentum 12 mois/, MOMRISK: /ajusté au risque/, NOSTRAT: /non définie/ })) assert.match(await row(sym).locator('.ps-chip').innerText(), chip, sym);
      // 6. cohérence ligne / détail : même état, même message, même protection
      const detail = async sym => { await page.locator(`#px-sec-suivi .psr:has(.psr-name strong:text-is("${sym}")) .psr-name`).click(); await page.locator('.px-drawer').waitFor(); await page.locator('.px-tabs2 [data-tab="suivi"]').click(); await page.locator('.ps-card').waitFor(); };
      const close = async () => { await page.locator('.px-dact [data-close]').click(); await page.locator('.px-drawer').waitFor({ state: 'detached' }); };
      for (const sym of ['GIBO', 'LOSSPERS', 'MULTIRULE', 'RISEUP', 'SHORT']) { const a = (await adv(sym)).replace(/Explication et détails[\s\S]*/, '').replace(/Configurer/, '').trim(); await detail(sym); const d = text(await page.locator('.ps-card .ps-advice, .ps-card .psr-adv, .ps-card [class*=adv]').first().innerText());
        const head = a.split(/\s{1}/).slice(0, 8).join(' '); assert.ok(d.toLowerCase().includes(head.slice(0, 40).toLowerCase()), `ligne et détail alignés ${sym} : « ${head} » / « ${d.slice(0, 100)} »`); await noOverflow('détail ' + sym); await close(); }
      // 7. repli indépendant des deux sections : le repli masque seulement l'affichage, le contenu reste intact
      const foldBtn = n => page.locator(`[data-fold="${n}"]`);
      assert.equal(await foldBtn('suivi').getAttribute('aria-expanded'), 'true'); assert.equal(await foldBtn('positions').getAttribute('aria-expanded'), 'true');
      await foldBtn('suivi').click(); assert.equal(await foldBtn('suivi').getAttribute('aria-expanded'), 'false'); assert.equal(await page.locator('#px-fb-suivi').isVisible(), false); assert.equal(await page.locator('#px-fb-positions').isVisible(), true, 'Positions indépendante');
      await foldBtn('positions').click(); assert.equal(await page.locator('#px-fb-positions').isVisible(), false); assert.equal(await foldBtn('suivi').getAttribute('aria-expanded'), 'false');
      assert.ok(await page.locator('#px-main-box').count(), 'graphique intact après repli'); await page.reload(); await page.locator('.px-zones').waitFor();
      assert.equal(await foldBtn('positions').getAttribute('aria-expanded'), 'false', 'état mémorisé (Positions)'); assert.equal(await foldBtn('suivi').getAttribute('aria-expanded'), 'false', 'état mémorisé (Suivi)');
      await foldBtn('positions').click(); await foldBtn('suivi').click(); await page.locator('#px-sec-suivi .psr').first().waitFor();
      assert.equal(await page.locator('.px-t tbody tr').count(), 25, 'tableau Positions inchangé après repli/dépli'); assert.equal(await sec.locator('.psr').count(), 25);
      // 8. dialogue Configurer : valeurs automatiques à côté des personnalisées, règle par règle
      const cfg = async sym => { await row(sym).locator('[data-ps-cfg]').click(); await page.locator('dialog [data-rule="stop"]').waitFor(); };
      const save = async () => { await page.locator('dialog .btn.primary').click(); await page.waitForFunction(() => !document.querySelector('dialog[open]')); await page.waitForTimeout(400); await sec.locator('.psr').first().waitFor(); };
      await cfg('LOSSPERS'); { const dlg = page.locator('dialog'); assert.deepEqual(await dlg.locator('.ps-rule legend').allInnerTexts().then(a => a.length >= 5), true, 'une règle par bloc'); assert.match(await dlg.locator('[data-rule="stop"]').innerText(), /Personnalisé[\s\S]*Valeur automatique/); assert.match(await dlg.innerText(), /objectif de gain facultatif|Objectif/i); await dlg.locator('button:has-text("Annuler")').click(); await page.waitForFunction(() => !document.querySelector('dialog[open]')); }
      const stopOf = async sym => { const pf = await (await ctx.request.get(BASE + '/api.php?r=portfolio&id=1')).json(); return pf.positions.find(p => p.symbol === sym).levels; };
      const lv0 = await stopOf('LOSSPERS');
      if (width === 1440) {
        // protection personnelle modifiée : devient la référence effective, l'automatique reste calculée
        await cfg('GIBO'); await page.locator('dialog [data-rule="stop"] input[value="custom"]').check(); await page.locator('dialog [data-rule="stop"] [data-val]').fill('130'); await save();
        assert.match(await adv('GIBO'), /Protection personnelle : 130,00 €/i); assert.match(await adv('GIBO'), /automatique : [\d\s.,  ]+ €/i);
        { const x = await xs('GIBO'); assert.ok(x.personal !== undefined && x.personal > x.pru, 'repère personnel sur la jauge'); }
        await cfg('GIBO'); await page.locator('dialog [data-rule="recul"] [data-en]').uncheck(); await save(); // une autre règle reste indépendante
        assert.match(await adv('GIBO'), /Protection personnelle : 130,00 €/i, 'désactiver une règle ne touche pas les autres');
        await cfg('GIBO'); await page.locator('dialog [data-rule="recul"] [data-en]').check(); await save();
        // retour à l'automatique par règle : n'efface pas les autres réglages
        await cfg('GIBO'); await page.locator('dialog [data-rule="stop"] [data-reset]').click(); await save();
        assert.doesNotMatch(await adv('GIBO'), /Protection personnelle/i); assert.match(await adv('GIBO'), /Protection automatique/i); assert.equal(((await stopOf('GIBO')) || {}).stop_px ?? null, null, 'retour à l’automatique : valeur personnelle retirée');
        // protection personnelle franchie : 200 > cours 160,67 -> sortie à envisager nommant la protection
        await cfg('GIBO'); await page.locator('dialog [data-rule="stop"] input[value="custom"]').check(); await page.locator('dialog [data-rule="stop"] [data-val]').fill('200'); await save();
        assert.match(await adv('GIBO'), /SORTIE À ENVISAGER[\s\S]*Ta protection personnelle de 200,00 € est franchie/i);
        await cfg('GIBO'); await page.locator('dialog [data-rule="stop"] [data-reset]').click(); await save(); assert.match(await adv('GIBO'), /SURVEILLER/i);
        // la protection personnelle d'un autre titre est intacte
        assert.deepEqual(await stopOf('LOSSPERS'), lv0, 'autres protections personnelles intactes');
      }
      // 9. changement de stratégie de surveillance : n'écrase aucune protection personnelle
      await cfg('PERSOSTOP'); await page.locator('dialog #ps-st').selectOption('rebound'); await save(); assert.match(await row('PERSOSTOP').locator('.ps-chip').innerText(), /Rebond/); assert.match(await row('PERSOSTOP').locator('.psr-gauge').innerText(), /110,00/, 'Rebond garde la protection personnelle');
      await cfg('PERSOSTOP'); await page.locator('dialog #ps-st').selectOption('regular'); await save();
      // 10. détail : onglets, PRU multi-lots, lots réglables, colonne Suivi du tableau
      await detail('MULTILOT'); assert.match(text(await page.locator('.ps-card').innerText()), /PRU 120,00 €/); assert.equal(await page.locator('.ps-card .ps-gauge').count(), 1); { const origin = await page.locator('.ps-card .ps-origin').innerText(); for (const o of ['Croissance rapide', 'Croissance régulière', 'Rebond']) assert.match(origin, new RegExp(o)); }
      await page.locator('.px-tabs2 [data-tab="chiffres"]').click(); await page.locator('.px-tech summary').click(); assert.equal(await page.locator('.px-tech [data-lot]').count(), 3, 'trois lots restants');
      await page.locator('.px-tech [data-lot]').first().click(); await page.locator('dialog #lt-st').waitFor(); assert.doesNotMatch(await page.locator('dialog').innerText(), /Désactiver les alertes/); for (const id of ['#lt-days', '#lt-drop']) assert.equal(await page.locator('dialog ' + id).count(), 1);
      await page.locator('dialog button:has-text("Annuler")').click(); await page.waitForFunction(() => !document.querySelector('dialog[open]')); await close();
      await page.locator('.px-t tbody tr:has(.c-title b:text-is("DEEP140")) .px-w').click(); await page.locator('.ps-card').waitFor(); await close();
      // 11. thème sombre / clair : contraste des textes du suivi
      for (const theme of ['dark', 'light']) { await page.evaluate(t => { document.documentElement.dataset.theme = t; }, theme);
        const bad = await sec.evaluate(c => { const lum = rgb => { const v = rgb.match(/[\d.]+/g).slice(0, 3).map(Number).map(x => { x /= 255; return x <= .03928 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4; }); return .2126 * v[0] + .7152 * v[1] + .0722 * v[2]; };
          const bgOf = el => { for (let e = el; e; e = e.parentElement) { const b = getComputedStyle(e).backgroundColor; const a = b.match(/[\d.]+/g); if (a && (a.length < 4 || +a[3] > .5)) return b; } return 'rgb(255,255,255)'; };
          return [...c.querySelectorAll('.psr-msg, .psr-more p, .ps-state, .psr-gain strong, .ps-lb b, .ps-lb strong, .psr-hl, .ps-chip')].filter(e => e.offsetParent && e.textContent.trim()).map(e => { const f = lum(getComputedStyle(e).color), g = lum(bgOf(e)), [hi, lo] = f > g ? [f, g] : [g, f]; return { t: e.textContent.trim().slice(0, 30), r: (hi + .05) / (lo + .05) }; }).filter(x => x.r < 4.5); });
        assert.deepEqual(bad, [], 'contraste insuffisant (' + theme + ')'); await shot('suivi-' + theme); }
      // 12. zone Transactions inchangée
      await page.locator('.px-zones [data-zone="transactions"]').click(); assert.ok(await page.locator('.px-tx').count()); await page.locator('[data-hist]').first().click(); await page.waitForSelector('#back-home'); assert.match(await page.locator('#panel-manage').innerText(), /Lots et réglages/); assert.doesNotMatch(await page.locator('#panel-manage').innerText(), /Lots et réglages des alertes/); await page.locator('#back-home').click(); await page.locator('.px-zones').waitFor(); await page.locator('.px-zones [data-zone="transactions"]').click(); await page.locator('.px-zones [data-zone="overview"]').click();
      await noOverflow('final');
      assert.deepEqual(errors, [], 'aucune erreur JavaScript : ' + errors.join(' | '));
      report.push(width); await ctx.close();
    }
    console.log('Plan de suivi : OK sur', report.join(', '), 'px');
  } finally { await b.close(); }
})().catch(e => { console.error(e); process.exit(1); });
