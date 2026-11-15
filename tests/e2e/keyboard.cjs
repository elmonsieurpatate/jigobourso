// Parcours clavier du dialogue partagé et des onglets personnels, sur les vraies pages.
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');
const base = process.env.BASE || 'http://127.0.0.1:18089';
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.JIGO_CHROMIUM });
  try {
    for (const width of [390, 1280]) for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: theme, reducedMotion: 'reduce', isMobile: width === 390, hasTouch: width === 390 });
      const page = await context.newPage();
      await page.goto(base + '/login.html');
      await page.fill('#u', process.env.USER_NAME || 'review_user');
      await page.fill('#p', process.env.PASS || 'review-local-password');
      await page.click('#auth-form button.primary'); await page.waitForURL('**/index.html');
      await page.evaluate(t => J.applyTheme(t), theme);
      const opener = page.locator('#user-btn'); await opener.focus(); await page.keyboard.press('Enter');
      await page.locator('dialog[open]').waitFor();
      for (const key of ['Tab', 'Shift+Tab']) for (let n = 0; n < 24; n++) {
        await page.keyboard.press(key);
        // Chromium peut placer le focus sur son interface (activeElement=body)
        // en bouclant. Aucun contrôle de la page derrière la modale ne doit le recevoir.
        assert(await page.evaluate(() => document.activeElement === document.body || document.activeElement.closest('dialog[open]') !== null), `${width}/${theme}: contrôle de fond accessible`);
      }
      assert(await page.evaluate(() => { document.querySelector('#theme-btn').focus(); return document.activeElement.id !== 'theme-btn'; }), 'le fond doit rester inerte');
      await page.keyboard.press('Escape'); await page.locator('dialog').waitFor({ state: 'detached' });
      assert(await opener.evaluate(e => e === document.activeElement), 'le focus doit revenir au déclencheur');
      await page.goto(base + '/mes-filtres.html'); await page.locator('[role=tab]').first().waitFor();
      await page.waitForFunction(() => typeof document.querySelector('#ac-tab-categories').onclick === 'function');
      const tabs = page.locator('[role=tab]');
      assert(await tabs.count() > 1, 'au moins deux onglets');
      await tabs.first().focus(); await page.keyboard.press('ArrowRight');
      assert(await tabs.nth(1).evaluate(e => e === document.activeElement && e.getAttribute('aria-selected') === 'true'));
      await page.keyboard.press('Home'); assert(await tabs.first().evaluate(e => e === document.activeElement));
      await page.keyboard.press('End'); assert(await tabs.last().evaluate(e => e === document.activeElement));
      if (width === 390) {
        let searches = 0;
        page.on('request', r => { if (new URL(r.url()).searchParams.get('r') === 'ranking/table') searches++; });
        await page.goto(base + '/index.html');
        await page.waitForFunction(() => /Cliquez sur/.test(document.querySelector('#ct-ranking-status')?.textContent || ''));
        await page.locator('.sui-pick-btn').tap();
        const picker = page.locator('.sui-list'); await picker.waitFor();
        const box = await picker.boundingBox(); assert(box.x >= 0 && box.x + box.width <= 391, 'sélecteur hors écran');
        await page.locator('.sui-opt').nth(1).tap();
        assert.equal(searches, 0, 'une sélection ne doit pas lancer la recherche');
        await page.route('**/api.php?r=ranking/table', async route => { await new Promise(r => setTimeout(r, 250)); await route.continue(); });
        await page.locator('#ct-apply').tap();
        await page.waitForFunction(() => document.querySelector('.ct-ranking').getAttribute('aria-busy') === 'true');
        await page.locator('a.ct-company').first().waitFor();
        assert.equal(searches, 1, 'une seule recherche par clic');
        const table = page.locator('.ct-table-wrap'); await table.scrollIntoViewIfNeeded();
        const rect = await table.boundingBox(), y = Math.min(rect.y + 60, 820);
        const touch = await context.newCDPSession(page);
        await touch.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: 320, y }] });
        for (let x = 290; x >= 80; x -= 30) await touch.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x, y }] });
        await touch.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
        await page.waitForFunction(() => document.querySelector('.ct-table-wrap').scrollLeft > 0);
        await touch.detach();
      }
      await context.close();
    }
    console.log('Clavier : dialogue partagé (focus, tabulation, Échap, retour) et onglets (4 contextes), sélecteur/recherche/défilement tactiles (2 thèmes) OK.');
  } finally { await browser.close(); }
})().catch(e => { console.error(e.stack); process.exitCode = 1; });
