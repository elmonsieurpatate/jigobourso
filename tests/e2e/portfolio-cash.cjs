/* Portefeuilles à liquidités (phase 1) : création (nom, icône, description, type, capital), achat et vente par l'interface (1 000 € → 800 € → 1 050 €, gain réalisé 50 €),
   renommage, dépôt / retrait (et refus du retrait excessif), archivage avec réaffectation du défaut, conversion d'un portefeuille legacy avec aperçu, réinitialisation, suppression,
   section « Argent » de la page d'un portefeuille, absence d'erreur JavaScript, aucun débordement horizontal à 390 px. Base jetable uniquement. */
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const BASE = process.env.BASE || 'http://127.0.0.1:18089';
const USER = 'cash_user', PASS = 'cash-local-password-2026';

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.JIGO_CHROMIUM, args: ['--no-sandbox'] });
  const errors = [];
  try {
    const ctx = await browser.newContext({ extraHTTPHeaders: { Origin: BASE }, viewport: { width: 1280, height: 1000 } });
    const page = await ctx.newPage();
    page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
    page.on('console', (m) => { if (m.type() === 'error' && !/favicon|Failed to load resource/.test(m.text())) errors.push('console: ' + m.text()); });
    assert.equal((await ctx.request.post(BASE + '/api.php?r=auth/login', { data: { username: USER, password: PASS } })).ok(), true, 'connexion');
    const api = async (route, body) => {
      const r = body === undefined ? await ctx.request.get(BASE + '/api.php?r=' + route) : await ctx.request.post(BASE + '/api.php?r=' + route, { data: body });
      return { status: r.status(), data: await r.json() };
    };
    const list = async () => (await api('portfolios')).data.portfolios;
    const byName = async (name) => (await list()).find((p) => p.name === name);
    const balance = async (id) => (await api('portfolio/cash&id=' + id)).data.cash.balance;
    const dialog = page.locator('dialog[open]');
    const click = async (name) => dialog.getByRole('button', { name, exact: true }).click();
    const closed = () => page.locator('dialog[open]').waitFor({ state: 'detached' });
    const row = (name) => page.locator('.card', { hasText: name }).filter({ has: page.locator('[data-a="edit"], [data-a="unarchive"]') }).last();
    const act = (name, a) => row(name).locator(`[data-a="${a}"]`).click();

    // ── création par l'interface ──
    await page.goto(BASE + '/mes-portefeuilles.html');
    await page.locator('#side').waitFor();   // le menu latéral est monté (J.init)
    await page.locator('#pfm-new').click();
    await page.locator('#pf-name').fill('ETF Long Terme');
    await page.locator('#pf-kind').selectOption('virtual');
    await page.locator('#pf-capital').fill('1000');
    await page.locator('#pf-icon').selectOption('🚀');
    await page.locator('#pf-desc').fill('Simulation long terme');
    await click('Créer');
    await page.waitForURL(/portefeuilles\.html\?id=\d+/);
    const created = await byName('ETF Long Terme');
    assert.ok(created, 'portefeuille créé');
    assert.equal(created.icon, '🚀'); assert.equal(created.description, 'Simulation long terme'); assert.equal(created.kind, 'virtual'); assert.equal(created.cash_model, 'cash');
    assert.equal(await balance(created.id), 1000, 'capital initial = liquidités');
    await page.locator('#pf-toolbar').waitFor();

    // ── section « Argent » de la page du portefeuille ──
    await page.locator('#goto-cash').click();   // accès direct depuis le bandeau de liquidités
    await page.locator('#cash-host table').waitFor();
    const cashText = await page.locator('#cash-host').innerText();
    assert.match(cashText.replace(/[\s  ]/g, ''), /1000,00€deliquidités/, 'solde affiché : ' + cashText.slice(0, 80));
    assert.match(cashText, /Capital initial/);
    assert.equal(await page.locator('.notice.info', { hasText: 'Liquidités' }).count(), 0, 'plus de bandeau d’information : le bilan unique le remplace');

    // ── achat 200 € puis vente 250 € par l'interface ──
    const trade = async (side, price) => {
      await page.locator('#add-tx').click();
      await page.locator('#tx-q').fill('ALPHA');
      await page.locator('#tx-hits a').first().click();
      if (side === 'sell') await page.locator('#tx-side [data-v="sell"]').click();
      await page.locator('#tx-qty').fill('1');
      await page.locator('#tx-price').fill(String(price));
      await click('Enregistrer');
      await closed();
    };
    await trade('buy', 200);
    assert.equal(await balance(created.id), 800, 'après l’achat');
    await trade('sell', 250);
    assert.equal(await balance(created.id), 1050, 'après la vente');
    const detail = (await api('portfolio&id=' + created.id)).data;
    assert.equal(Math.round(detail.totals.realized * 100) / 100, 50, 'gain réalisé conservé');
    assert.equal(detail.positions.length, 0, 'plus de position ouverte'); assert.equal(detail.closed.length, 1, 'position clôturée conservée');
    assert.equal(detail.totals.total_gain, 50);

    await page.goto(BASE + '/mes-portefeuilles.html');
    await page.locator('[data-sub="portefeuilles"] a.sv', { hasText: '🚀' }).waitFor();   // icône du portefeuille dans le menu (chargé après la page)

    // ── bilan avec liquidités (moteur v2) : valeur totale, gains, performance exacte, contribution du titre vendu ──
    await page.goto(BASE + '/portefeuilles.html?id=' + created.id);
    await page.locator('.pf-kpis').waitFor();
    await page.locator('#pfc-plot .fc-plot').waitFor();
    const kpis = (await page.locator('#px-page').innerText()).replace(/[\s  ]/g, '');
    assert.match(kpis, /Valeurtotale:1050,00€/i, 'valeur totale liquidités comprises : ' + kpis.slice(0, 200));
    assert.match(kpis, /Liquidités1050,00€/i); assert.match(kpis, /Gaintotal\+50,00€/i); assert.match(kpis, /Gainsréalisés\+50,00€/i); assert.match(kpis, /Gainslatents/i);
    assert.match(kpis, /\+5,00%/); assert.match(kpis, /exact/i);
    assert.equal(await page.locator('#pf-perf2').count(), 0, 'plus de second bilan');
    assert.equal(await page.locator('.px-syn').count(), 0, 'plus d’ancien bilan sur un portefeuille à liquidités');
    // réglages remis à zéro au chargement : onglet Valeur, tous les titres cochés, période « Depuis le début »
    assert.equal(await page.locator('.px-top [data-k="mode"] .on').innerText(), 'Valeur');
    assert.equal(await page.locator('.px-ph + .px-per .on, #px-page .px-per [data-aper].on').first().innerText(), 'Depuis le début');
    // graphique unique : vue complète = titre vendu présent ; positions actuelles = absent
    assert.match(await page.locator('#pfc-leg').innerText(), /ALPHA/, 'titre vendu présent dans le portefeuille complet');
    await page.locator('.px-ph [data-k="view"] [data-v="open"]').click();
    await page.locator('#pfc-def').waitFor();
    assert.doesNotMatch(await page.locator('#pfc-leg').innerText(), /ALPHA/, 'titre vendu absent des positions actuelles');
    await page.locator('.px-ph [data-k="view"] [data-v="full"]').click();
    for (const m of ['value', 'gain', 'perf', 'market']) { await page.locator(`.px-top [data-k="mode"] [data-v="${m}"]`).click(); await page.locator('#pfc-plot .fc-plot, #pfc-plot .px-empty').first().waitFor(); }
    await page.locator('.px-top [data-k="mode"] [data-v="value"]').click();
    // un titre décoché l'est dans tous les onglets
    const chip = page.locator('#pfc-leg [data-sid]', { hasText: 'ALPHA' }); await chip.click();
    for (const m of ['gain', 'perf']) { await page.locator(`.px-top [data-k="mode"] [data-v="${m}"]`).click(); assert.equal(await page.locator('#pfc-leg [data-sid]', { hasText: 'ALPHA' }).getAttribute('aria-pressed'), 'false', 'titre décoché partout : ' + m); }
    await page.locator('.px-top [data-k="mode"] [data-v="value"]').click();
    // « Mes actions » : la position clôturée est dans le filtre « Vendues » avec son gain réalisé ; « Contribution au résultat » suit le même filtre
    await page.locator('[data-afilter="sold"]').first().click();
    const sold = (await page.locator('.px-t').innerText()).replace(/[\s  ]/g, '');
    assert.match(sold, /ALPHA/); assert.match(sold, /\+50,00€/, 'gain réalisé de la position clôturée');
    assert.match((await page.locator('.bars').innerText()).replace(/[\s  ]/g, ''), /ALPHA\(vendu\)\+50,00€/, 'contribution du titre vendu');
    await page.locator('[data-aper="1m"]').first().click(); await page.locator('.px-t').waitFor();
    await page.locator('[data-gosuivi]').click();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, 'débordement horizontal du bilan');
    if (process.env.SHOTS) await page.locator('#px-page').screenshot({ path: process.env.SHOTS + '/bilan-liquidites.png' });
    const legacyPf = (await api('portfolio/create', { name: 'Témoin ancien modèle' })).data.id;
    await page.goto(BASE + '/portefeuilles.html?id=' + legacyPf);
    await page.locator('.px-zones').waitFor();
    assert.equal(await page.locator('.pf-kpis, #pfc-card').count(), 0, 'aucun bilan à liquidités sur un portefeuille ancien modèle');
    await api('portfolio/delete', { id: legacyPf });

    // ── renommage, icône, description ──
    await page.goto(BASE + '/mes-portefeuilles.html');
    await act('ETF Long Terme', 'edit');
    await page.locator('#pf-name').fill('ETF Monde');
    await page.locator('#pf-icon').selectOption('🌍');
    await page.locator('#pf-desc').fill('Description modifiée');
    await click('Enregistrer');
    await closed();
    await row('ETF Monde').waitFor();
    const renamed = await byName('ETF Monde');
    assert.equal(renamed.id, created.id); assert.equal(renamed.icon, '🌍'); assert.equal(renamed.description, 'Description modifiée');
    assert.equal(await balance(created.id), 1050, 'le renommage ne perd aucune donnée');

    // ── dépôt, retrait, refus du retrait excessif ──
    await act('ETF Monde', 'deposit');
    await page.locator('#mv-amount').fill('500');
    await click('Enregistrer'); await closed();
    assert.equal(await balance(created.id), 1550);
    await act('ETF Monde', 'withdrawal');
    await page.locator('#mv-amount').fill('100');
    await click('Enregistrer'); await closed();
    assert.equal(await balance(created.id), 1450);
    await act('ETF Monde', 'withdrawal');
    await page.locator('#mv-amount').fill('99999');
    await click('Enregistrer');
    await dialog.locator('.notice.err').waitFor();
    assert.match(await dialog.locator('.notice.err').innerText(), /Liquidités insuffisantes/);
    await click('Annuler'); await closed();
    assert.equal(await balance(created.id), 1450, 'retrait excessif refusé, rien d’écrit');

    // ── archivage : défaut réaffecté, lecture seule, désarchivage ──
    assert.equal((await api('portfolio/create', { name: 'Autre', kind: 'real' })).status, 200);
    await page.goto(BASE + '/mes-portefeuilles.html');
    await act('ETF Monde', 'archive');
    await page.locator('h2', { hasText: 'Archivés' }).waitFor();
    const afterArchive = await list();
    assert.equal(afterArchive.find((p) => p.name === 'ETF Monde').archived, true);
    assert.equal(afterArchive.find((p) => p.name === 'Autre').is_default, true, 'défaut réaffecté à un portefeuille actif');
    assert.equal((await api('cash/add', { portfolio_id: created.id, kind: 'deposit', amount: 1, occurred_at: '2026-05-04' })).status, 409, 'archivé = lecture seule');
    await act('ETF Monde', 'unarchive');
    await page.locator('h2', { hasText: 'Archivés' }).waitFor({ state: 'detached' });

    // ── conversion d'un portefeuille legacy avec aperçu ──
    const legacy = (await api('portfolio/create', { name: 'Ancien modèle' })).data.id;
    assert.equal((await api('tx/add', { portfolio_id: legacy, listing_id: 1, side: 'buy', quantity: 2, unit_price: 100, trade_at: new Date().toISOString().slice(0, 10) })).status, 200);
    await page.goto(BASE + '/mes-portefeuilles.html');
    await row('Ancien modèle').getByText('Ancien modèle').first().waitFor();
    await act('Ancien modèle', 'convert');
    await page.locator('#cv-kind').selectOption('real');
    await click('Aperçu');
    await page.locator('#cv-preview .notice').waitFor();
    assert.match(await page.locator('#cv-preview').innerText(), /Solde après conversion/);
    assert.equal((await list()).find((p) => p.id === legacy).cash_model, 'legacy', 'l’aperçu n’écrit rien');
    await click('Convertir'); await closed();
    assert.equal((await list()).find((p) => p.id === legacy).cash_model, 'cash');

    // ── réinitialisation : identité conservée, opérations supprimées, nouveau capital ──
    await act('ETF Monde', 'reset');
    await dialog.locator('#rs-confirm').waitFor();
    assert.match(await dialog.innerText(), /transactions/);
    await page.locator('#rs-capital').fill('300');
    await page.locator('#rs-confirm').fill('ETF Monde');
    await click('Réinitialiser'); await closed();
    const reset = await byName('ETF Monde');
    assert.equal(reset.icon, '🌍'); assert.equal(reset.description, 'Description modifiée'); assert.equal(reset.kind, 'virtual');
    assert.equal(await balance(created.id), 300, 'nouveau capital initial');
    const afterReset = (await api('portfolio&id=' + created.id)).data;
    assert.equal(afterReset.transactions_list.length, 0); assert.equal(afterReset.totals.realized, 0);

    // ── suppression : confirmation par le nom, plus aucune trace ──
    await act('ETF Monde', 'delete');
    await dialog.locator('#dl-confirm').waitFor();
    await click('Supprimer définitivement');
    await dialog.locator('.notice.err').waitFor();   // sans le nom : refusé
    await page.locator('#dl-confirm').fill('ETF Monde');
    await click('Supprimer définitivement'); await closed();
    assert.equal(await byName('ETF Monde'), undefined);
    assert.equal((await api('portfolio&id=' + created.id)).status, 404);
    for (const name of ['Autre', 'Ancien modèle']) {
      await act(name, 'delete');
      await dialog.getByRole('button', { name: 'Supprimer définitivement', exact: true }).waitFor();   // l'aperçu des données est chargé
      if (await page.locator('#dl-confirm').count()) await page.locator('#dl-confirm').fill(name);
      await click('Supprimer définitivement'); await closed();
    }
    assert.equal((await list()).length, 0, 'plus aucun portefeuille');

    // ── mobile : pas de débordement horizontal ──
    await page.setViewportSize({ width: 390, height: 900 });
    await page.goto(BASE + '/mes-portefeuilles.html');
    await page.locator('#page h2').first().waitFor();
    await page.locator('#side').waitFor({ state: 'attached' });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, 'débordement horizontal à 390 px');

    assert.deepEqual(errors, [], 'erreurs JavaScript : ' + errors.join(' | '));
    console.log('portfolio-cash : OK');
  } finally {
    await browser.close();
  }
})().catch((e) => { console.error(e); process.exit(1); });
