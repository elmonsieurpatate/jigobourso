// Régression F08 : une classe !important bloquait la colonne unique sur mobile.
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');
const base = process.env.BASE || 'http://127.0.0.1:18089';
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.JIGO_CHROMIUM });
  try {
    const page = await browser.newPage();
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto(base + '/login.html'); await page.fill('#u', 'review_user'); await page.fill('#p', 'review-local-password');
    await page.click('#auth-form button.primary'); await page.waitForURL('**/index.html');
    await page.goto(base + '/titre.html?id=1'); await page.locator('#layout #main .card').first().waitFor();
    for (const theme of ['light', 'dark']) for (const width of [390, 1280, 768, 900, 901, 320]) {
      await page.setViewportSize({ width, height: 900 });
      await page.evaluate(t => J.applyTheme(t), theme);
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const r = await page.locator('#layout').evaluate(el => ({
        columns: getComputedStyle(el).gridTemplateColumns.split(' ').length,
        main: el.querySelector('#main').getBoundingClientRect().width,
        available: el.getBoundingClientRect().width,
        overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        offenders: [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1 && getComputedStyle(e).position !== 'fixed').slice(0, 12).map(e => [e.tagName, String(e.className), e.getBoundingClientRect().width]),
      }));
      assert.equal(r.columns, width <= 900 ? 1 : 2, `${width}/${theme}: colonnes`);
      if (width <= 900) assert(r.main >= r.available - 2, `${width}: contenu écrasé`);
      assert(r.overflow <= 1, `${width}/${theme}: débordement de page ${JSON.stringify(r)}`);
    }
    console.log('Fiche titre : 12 redimensionnements conformes (320 à 1280 px, clair/sombre).');
  } finally { await browser.close(); }
})().catch(e => { console.error(e.stack); process.exitCode = 1; });
