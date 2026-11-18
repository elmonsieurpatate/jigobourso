// Navigation de l'administration vers une vraie fiche ; périodes longues et manque d'historique explicite.
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');
const base = process.env.BASE || 'http://127.0.0.1:18089';
(async () => {
 const browser = await chromium.launch({ executablePath: process.env.JIGO_CHROMIUM });
 try {
  for (const width of [390, 1280]) {
   const page = await browser.newPage({ viewport: { width, height: 900 } });
   const errors = []; page.on('pageerror', e => errors.push(e.message));
   const row = { id: 2, lid: 2, sheet_id: 1, sheet_symbol: 'TEST.PA', sheet_redirected: true, symbol: 'SECOND.PA', mic: 'XPAR', name: 'Produit secondaire de test', isin: 'LU1812092168', kind: 'equity', status: 'candidate', fdb_state: 'kept', y_state: 'secondary', in_final: false, primary: { id: 1, symbol: 'TEST.PA', mic: 'XPAR', in_catalogue: true } };
   await page.route('**/api.php?r=admin%2Ftitles*', route => route.fulfill({ json: { rows: [row], places: ['XPAR'], total: 1, raw_total: 1, page: 1, pages: 1 } }));
   await page.route('**/api.php?r=admin%2Ffunnel%2Fitems*', route => route.fulfill({ json: { rows: [row], total: 1, page: 1, pages: 1 } }));
   await page.goto(base + '/login.html'); await page.fill('#u', 'review_user'); await page.fill('#p', 'review-local-password');
   await page.click('#auth-form button.primary'); await page.waitForURL('**/index.html');
   for (const stage of ['titres', 'catalogue', 'yahoo']) {
    await page.goto(base + '/admin.html#titres'); await page.waitForSelector('#tq');
    if (stage !== 'titres') await page.evaluate(stage => AdminCore.itemsPanel(stage, stage === 'catalogue' ? 'raw' : 'secondary', 'Test', document.querySelector('#page')), stage);
    const link = page.locator('#page tbody a').first();
    assert.equal(await link.getAttribute('href'), 'titre.html?id=1', `${stage} : lien vers la principale conservée`);
    const response = page.waitForResponse(r => new URL(r.url()).searchParams.get('r') === 'sheet');
    await link.click(); await page.waitForURL('**/titre.html?id=1');
    const sheet = await (await response).json();
    await page.locator('#range button[data-n="756"]').waitFor();
    for (const n of [756, 1260]) {
     const button = page.locator(`#range button[data-n="${n}"]`);
     const box = await button.boundingBox(); assert(box.x >= 0 && box.x + box.width <= width + 1, 'bouton long hors écran');
     await button.click(); await page.locator('#chart svg').waitFor();
     if (sheet.daily.length < n + 1) assert.match(await page.locator('#chart-history-notice').innerText(), /Historique incomplet/);
    }
    await page.locator('#range button[data-n="0"]').click();
    assert.match(await page.locator('#chart-sum').innerText(), new RegExp(`${sheet.daily.length - 1} variations de séance`));
    assert(await page.locator('#chart-history-notice').isHidden());
   }
   assert.deepEqual(errors, []); await page.close();
  }
  console.log('Fiches : liens FinanceDatabase/Yahoo/Actions-ETF vers la principale, boutons 3/5 ans et Max, historique court explicite, mobile/bureau OK.');
 } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
