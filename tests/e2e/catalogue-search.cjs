// Le vrai contrôleur Actions/ETF, avec réponses déterministes et retardées : frappe lente et réponses périmées.
const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.JIGO_CHROMIUM });
  try {
    for (const width of [390, 1280]) {
      const page = await browser.newPage({ viewport: { width, height: 850 } });
      await page.setContent('<main id="page"></main>');
      await page.addScriptTag({ path: path.resolve('app/public/assets/core.js') });
      await page.evaluate(() => {
        window.requests = [];
        window.AdminCore = { tabs: {}, page: document.querySelector('#page'), tab: () => 'titres', nf: String, runBar: () => '' };
        J.api = async (_, { params }) => {
          window.requests.push(params.q || '');
          await new Promise(r => setTimeout(r, 160));
          if (params.q === 'ERROR') throw new Error('Serveur temporairement indisponible');
          const symbols = ['SELD.DE', 'SEL.PA', 'SEL.MI', 'LYSEL.SW', 'SELD.BE', 'SELD.DU', 'SELD.F', 'SELD.MU'];
          const rows = params.q === 'LU1812092168' ? symbols.map((symbol, i) => ({
            symbol, mic: i === 0 ? 'XETR' : 'XPAR', isin: 'LU1812092168', name: 'Produit de test', kind: 'etf',
            lid: i + 1, in_final: i === 0, fdb_state: 'kept', y_state: i === 0 ? 'kept' : 'secondary',
            d_state: 'incomplete', intraday_state: i === 0 ? (window.intradayState || 'partial') : 'na', primary: { id: 1, symbol: 'SELD.DE', mic: 'XETR', in_catalogue: true },
          })) : [];
          return { places: ['XPAR'], raw_total: 8, rows, total: rows.length, page: 1, pages: 1 };
        };
      });
      await page.addScriptTag({ path: path.resolve('app/public/assets/admin-titres.js') });
      await page.evaluate(() => AdminCore.tabs.titres());
      await page.locator('#tq').focus();
      await page.keyboard.type('LU1812092168', { delay: 620 });
      await page.waitForTimeout(650);
      assert.equal(await page.locator('#tq').inputValue(), 'LU1812092168', 'la recherche coupe la saisie après la première réponse');
      assert(await page.locator('#tq').evaluate(e => e === document.activeElement), 'le champ doit garder le focus');
      assert.match(await page.locator('#titles-results').innerText(), /1 produit · 8 cotations du même ISIN/);
      assert(await page.locator('#titles-results a[href="titre.html?id=1"]').first().isVisible(), 'la principale doit être accessible avant les autres cotations');
      assert.equal(await page.locator('#titles-results details').getAttribute('open'), null);
      assert.equal(await page.locator('#titles-results tbody tr').count(), 8);
      await page.locator('#titles-results summary').click();
      assert(await page.locator('#titles-results table').isVisible());
      assert.match(await page.locator('#titles-results tbody tr').first().locator('td').nth(9).innerText(), /Partiel/);
      assert.match(await page.locator('#titles-results tbody tr').first().locator('td').nth(8).innerText(), /Séances manquantes/);
      await page.evaluate(() => window.intradayState = 'complete');
      await page.locator('#tq').press('Enter');
      await page.waitForTimeout(220);
      await page.locator('#titles-results summary').click();
      assert.equal(await page.locator('#titles-results tbody tr').first().locator('td').nth(9).innerText(), 'Complet', 'les barres intrajournalières ne doivent pas être étiquetées 5 ans complets');

      await page.locator('#tq').fill('ERROR');
      assert.equal(await page.locator('#titles-results table').count(), 0, 'les anciens résultats ne doivent pas rester pendant la nouvelle recherche');
      await page.waitForTimeout(650);
      assert.match(await page.locator('#titles-results [role=alert]').innerText(), /Recherche non actualisée/);
      assert.equal(await page.locator('#titles-results table').count(), 0, 'un échec ne doit pas montrer les anciens résultats comme valides');
      assert(await page.locator('#tq').evaluate(e => e === document.activeElement));

      await page.locator('#tq').fill('SM');
      await page.waitForTimeout(450); // une requête est en vol
      await page.keyboard.type('CRT');
      await page.waitForTimeout(650);
      assert.equal(await page.locator('#tq').inputValue(), 'SMCRT', 'une réponse périmée ne doit pas remplacer la saisie');
      assert.equal(await page.evaluate(() => requests.at(-1)), 'SMCRT');
      await page.locator('#tq').fill('');
      await page.waitForTimeout(650);
      assert.equal(await page.evaluate(() => requests.at(-1)), '', 'effacer relance la recherche');
      await page.selectOption('#tfin', '1');
      await page.waitForTimeout(220);
      assert.equal(await page.locator('#tfin').inputValue(), '1');
      await page.addScriptTag({ path: path.resolve('app/public/assets/admin-common.js') });
      await page.evaluate(() => AdminCore.itemsPanel('catalogue', 'final', 'Catalogue', document.querySelector('#page')));
      await page.locator('#ip-q').focus();
      await page.keyboard.type('LU1812092168', { delay: 620 });
      await page.waitForTimeout(650);
      assert.equal(await page.locator('#ip-q').inputValue(), 'LU1812092168', 'le panneau du catalogue doit aussi garder la saisie');
      assert(await page.locator('#ip-q').evaluate(e => e === document.activeElement));
      await page.locator('#ip-q').fill('TEST');
      await page.waitForTimeout(400);
      await page.locator('#ip-close').click();
      await page.waitForTimeout(200);
      assert.equal(await page.locator('#ip-q').count(), 0, 'une réponse tardive ne rouvre pas le panneau fermé');
      await page.close();
    }
    if (process.env.BASE) {
      const page = await browser.newPage({ viewport: { width: 390, height: 850 } });
      const errors = []; page.on('pageerror', e => errors.push(e.message));
      let rankings = 0;
      const primary = { id: 54321, symbol: 'TEST.PA', mic: 'XPAR', in_catalogue: true };
      await page.route('**/api.php?r=listings%2Fsearch*', route => route.fulfill({ json: { results: [
        { id: 54322, symbol: 'TEST.DE', mic: 'XETR', name: 'Produit de test', isin: 'LU1812092168', status: 'excluded', in_catalogue: false, primary, matched_symbols: 'TEST.DE' },
      ] } }));
      await page.route('**/api.php?r=ranking%2Ftable', route => {
        rankings++;
        return route.fulfill({ json: { rows: [], universe: 1, label: 'Test' } });
      });
      await page.goto(process.env.BASE + '/login.html');
      await page.fill('#u', 'review_user'); await page.fill('#p', 'review-local-password');
      await page.click('#auth-form button.primary'); await page.waitForURL('**/index.html');
      await page.waitForFunction(() => typeof document.querySelector('#ct-search')?.oninput === 'function');
      await page.locator('#ct-search').fill('TEST.DE');
      await page.locator('#ct-catalogue-matches a').waitFor();
      assert.match(await page.locator('#ct-catalogue-matches').innerText(), /Produit dans le catalogue final.*TEST.PA.*XPAR/);
      assert.match(await page.locator('#ct-catalogue-matches').innerText(), /cotation principale retenue/);
      assert.equal(await page.locator('#ct-catalogue-matches a').getAttribute('href'), 'titre.html?id=54321');
      assert.equal(rankings, 0, 'la recherche du catalogue ne doit pas lancer les scores');
      assert(await page.locator('#ct-search').evaluate(e => e === document.activeElement));
      await page.locator('#ct-search').fill('');
      assert(await page.locator('#ct-catalogue-matches').isHidden());
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log('Recherche Actions/ETF : saisie continue, focus, réponse périmée, effacement et filtres OK (mobile et bureau).');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
