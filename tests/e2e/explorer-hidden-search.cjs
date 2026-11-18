// Afficher un résultat masqué est une action de vue, jamais une remise à zéro de stratégie.
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.JIGO_CHROMIUM });
  try {
    for (const width of [390, 1280]) {
      const page = await browser.newPage({ viewport: { width, height: 900 } });
      const errors = []; page.on('pageerror', e => errors.push(e.message));
      let requests = 0, withoutScores = false;
      await page.route('**/api.php?r=ranking%2Ftable', route => {
        requests++;
        return route.fulfill({ json: { universe: 1, rows: withoutScores ? [] : [{ id: 999, symbol: 'DEMO.PA', name: 'Titre recherché', isin: 'LU1812092168', mic: 'XPAR', kind: 'etf', currency: 'EUR', status: 'excluded', simple: 80, complex: 90, rank_simple: 42, rank_complex: 42, pos_simple: 1, pos_complex: 1, group: {}, price: null, price_eur: null, change: null, slope: null, r2: null, volatility: null, drawdown: null, turnover_eur: null, avg_volume: null }] } });
      });
      await page.route('**/api.php?r=listings%2Fsearch*', route => route.fulfill({ json: { results: new URL(route.request().url()).searchParams.get('q') === 'introuvable' ? [] : [{ id: 999, symbol: 'DEMO.PA', name: 'Titre recherché', in_catalogue: true, primary: { id: 999, symbol: 'DEMO.PA', mic: 'XPAR', in_catalogue: true } }] } }));
      await page.goto((process.env.BASE || 'http://127.0.0.1:18089') + '/login.html');
      await page.fill('#u', 'review_user'); await page.fill('#p', 'review-local-password');
      await page.click('#auth-form button.primary'); await page.waitForURL('**/index.html');
      await page.waitForFunction(() => typeof document.querySelector('#ct-search')?.oninput === 'function');
      await page.locator('#ct-filter-panel').evaluate(e => e.open = true);
      await page.locator('#ct-none-filters').click();
      const filters = await page.locator('#ct-filters').innerHTML();
      const strategy = await page.locator('#ct-strategy').inputValue();
      for (const before of [false, true]) {
        await page.locator('#ct-show-hidden').uncheck();
        await page.locator('#ct-search').fill(before ? 'LU1812092168' : '');
        await page.locator('#ct-apply').click();
        await page.waitForFunction(() => document.querySelector('.ct-ranking').getAttribute('aria-busy') !== 'true');
        if (!before) await page.locator('#ct-search').fill('LU1812092168');
        await page.locator('#ct-catalogue-matches a').waitFor();
        const n = requests;
        assert.equal(await page.locator('#ct-table-body tr[data-row]').count(), 0);
        await page.locator('#ct-show-hidden').check();
        await page.locator('#ct-table-body tr[data-row="999"]').waitFor();
        assert.equal(await page.locator('#ct-search').inputValue(), 'LU1812092168');
        assert.equal(await page.locator('#ct-filters').innerHTML(), filters);
        assert.equal(await page.locator('#ct-strategy').inputValue(), strategy);
        assert.equal(requests, n, 'afficher les masqués ne relance pas les scores');
        await page.locator('#ct-show-hidden').uncheck();
        assert.equal(await page.locator('#ct-table-body tr[data-row]').count(), 0);
        await page.locator('#ct-show-demo-all').click();
        await page.locator('#ct-table-body tr[data-row="999"]').waitFor();
        assert.equal(await page.locator('#ct-search').inputValue(), 'LU1812092168');
        assert.equal(requests, n, 'le bouton du tableau vide ne relance pas les scores');
      }
      withoutScores = true;
      await page.locator('#ct-apply').click();
      await page.waitForFunction(() => document.querySelector('.ct-ranking').getAttribute('aria-busy') !== 'true');
      await page.locator('#ct-table-body tr[data-row="999"]').waitFor();
      assert.match(await page.locator('#ct-table-body').innerText(), /sans note dans le classement chargé/);
      assert.match(await page.locator('#ct-result-count').innerText(), /1 sans note/);
      assert.equal(await page.locator('#ct-table-body .ct-rank-cell').innerText(), '—');
      assert(!await page.locator('#ct-table-body').innerText().then(s => s.includes('NaN')));
      await page.locator('#ct-search').fill('introuvable');
      await page.waitForTimeout(500);
      assert.equal(await page.locator('#ct-table-body tr[data-row]').count(), 0, 'afficher les masqués ne doit pas ignorer la recherche');
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log('Explorer : recherche avant/après Appliquer, masqués visibles immédiatement, recherche/stratégie/filtres préservés, aucun recalcul (mobile et bureau).');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
