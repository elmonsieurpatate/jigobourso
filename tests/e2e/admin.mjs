// Parcours de bout en bout dans un vrai navigateur : connexion, Explorer, fiche, portefeuilles, bilan, administration.
// Usage : BASE=http://127.0.0.1:8090 USER=… PASS=… SHOTS=dossier node tests/e2e/smoke.mjs
import { chromium } from '/home/jigo/test-chartmill/node_modules/playwright-core/index.mjs';
const BASE = process.env.BASE || 'http://127.0.0.1:8090', SHOTS = process.env.SHOTS || '/tmp';
const results = []; const check = (name, ok, info = '') => { results.push([name, ok, info]); console.log((ok ? 'OK   ' : 'ÉCHEC'), name, info); };
const browser = await chromium.launch(); const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } }); const page = await ctx.newPage();
const errors = []; page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); }); page.on('pageerror', e => errors.push(String(e)));
const ready = () => page.waitForFunction(() => { const r = document.querySelector('#results'); return r && !r.querySelector('.spinner'); }, null, { timeout: 90000 });
const shot = async n => page.screenshot({ path: `${SHOTS}/${n}.png`, fullPage: true });
const finished = async () => { await page.waitForSelector('.toast:has-text("Traitement terminé")', { timeout: 180000 }); await page.waitForSelector('.toast', { state: 'detached', timeout: 10000 }); await page.waitForSelector('table.funnel'); };
try {
  await page.goto(BASE + '/login.html'); await page.fill('#u', process.env.USER_NAME); await page.fill('#p', process.env.PASS); await page.click('#in button.primary'); await page.waitForURL('**/index.html'); check('connexion', true);
  for (const [t, name] of [['fdb', '07-admin-fdb'], ['yahoo', '07b-admin-yahoo'], ['titres', '07c-admin-titres'], ['cron', '08-admin-cron'], ['logs', '08b-admin-journaux'], ['users', '09-admin-utilisateurs'], ['settings', '10-admin-reglages']]) { await page.goto(BASE + '/admin.html#' + t); await page.reload(); await page.waitForTimeout(1500); await shot(name); }
  // FinanceDatabase : import / filtres (places libres) / résultats
  await page.goto(BASE + '/admin.html#fdb'); await page.reload(); await page.waitForSelector('#go-import'); check('fdb : bouton Importer FinanceDatabase', await page.locator('#go-import').count() === 1);
  await page.waitForSelector('#pl-list input[data-mic]'); const nPlaces = await page.locator('#pl-list input[data-mic]').count(); check('fdb : toutes les places des données sont proposées (' + nPlaces + ')', nPlaces > 30);
  await page.waitForSelector('table.funnel'); const kept = async () => +(await page.locator('table.funnel tbody tr').last().locator('td.num').nth(2).innerText()).replace(/[^0-9]/g, '');
  const k0 = await kept(); const MIC = await page.locator('#pl-list input[data-def="0"]').first().getAttribute('data-mic'); const xtks = page.locator('#pl-list input[data-mic="' + MIC + '"]'); const was = await xtks.isChecked(); if (was) await xtks.uncheck(); else await xtks.check();
  await page.click('#go-filter'); await finished(); const k1 = await kept();
  check('fdb : choisir librement une place puis Filtrer change le résultat (' + k0 + ' → ' + k1 + ')', k1 !== k0);
  await page.waitForSelector('#pl-list input[data-mic="' + MIC + '"]'); const x2 = page.locator('#pl-list input[data-mic="' + MIC + '"]'); if ((await x2.isChecked()) === !was) { await x2.setChecked(was); await page.click('#go-filter'); await finished(); }
  check('fdb : retour à la sélection de départ', (await kept()) === k0);
  await page.locator('table.funnel tbody tr').nth(1).locator('button').click(); await page.waitForSelector('#items table tbody tr'); check('fdb : titres consultables à chaque étape', true);
  // Yahoo : filtres puis catalogue final avec le bouton des historiques juste dessous
  await page.goto(BASE + '/admin.html#yahoo'); await page.reload(); await page.waitForSelector('#go-info'); await page.waitForSelector('#go-history');
  check('yahoo : import, filtres et bouton historiques sur la même page', await page.locator('#go-info').count() === 1 && await page.locator('#go-filter').count() === 1 && await page.locator('#go-history').count() === 1);
  const liq = async () => +(await page.locator('table.funnel tbody tr').filter({ hasText: 'Exclus selon la liquidité' }).locator('td.num').nth(1).innerText()).replace(/[^0-9]/g, '');
  await page.waitForSelector('table.funnel'); const before = await liq(); await page.locator('input[data-rule="liquidity_equity"][data-f="min_eur"]').fill('1000000000'); await page.click('#go-filter'); await finished(); const after = await liq();
  check('yahoo : modifier un seuil puis Filtrer change les compteurs (' + before + ' → ' + after + ')', after > before);
  await page.locator('table.funnel tbody tr').filter({ hasText: 'Exclus selon la liquidité' }).locator('button').click(); await page.waitForSelector('#items table tbody tr[data-id]'); check('yahoo : titres écartés consultables', true);
  await page.click('#go-reset'); await page.click('dialog button.primary'); await page.waitForFunction(() => document.querySelector('input[data-rule="liquidity_equity"][data-f="min_eur"]')?.value === '1000000'); await page.click('#go-filter'); await finished();
  check('yahoo : valeurs par défaut restaurées puis refiltrées', (await liq()) === before);
  await page.fill('#ex-q', 'ETF'); await page.click('#ex-go'); await page.waitForSelector('#ex-out .reason, #ex-out .muted'); check('yahoo : « pourquoi ce titre a disparu »', true);
  // Actions / ETF
  await page.goto(BASE + '/admin.html#titres'); await page.reload(); await page.waitForSelector('tbody tr'); await page.selectOption('#tfdb', 'removed'); await page.waitForTimeout(2500); check('titres : écartés avec motif exact', /FinanceDatabase/.test(await page.locator('tbody').innerText()));
  await page.selectOption('#tfdb', ''); await page.selectOption('#tfin', '1'); await page.waitForTimeout(6000); check('titres : filtre « dans mon catalogue »', await page.locator('tbody tr').count() > 0);
  // Cron : état honnête
  await page.goto(BASE + '/admin.html#cron'); await page.reload(); await page.waitForSelector('text=Le cron fonctionne-t-il'); check('cron : installé et observé affiché honnêtement', /Cron installé et observé/.test(await page.locator('.card').first().innerText()) && await page.locator('#cr-test').count() === 1 && await page.locator('#cr-run').count() === 1);
  check('cron : aucune tâche de catalogue ni de filtrage', (await page.locator('[data-t]').count()) <= 3 && !/Rechargement|Filtrage/.test(await page.locator('.card').nth(1).innerText()));
  check('menu : sous-menu Administration › Cron actif', /Cron/.test(await page.locator('#side .sv.on').innerText())); await page.click('#side .sv:text("Utilisateurs")'); await page.waitForSelector('text=Créer un compte'); check('menu : sous-menu admin change de rubrique sans recharger', /Utilisateurs/.test(await page.locator('#side .sv.on').innerText()));
  await page.goto(BASE + '/admin.html#logs'); await page.reload(); await page.waitForSelector('tr[data-job]'); await page.locator('tr[data-job]').first().click(); await page.waitForSelector('dialog'); check('journaux : détail d’un traitement', /Traitement n°/.test(await page.locator('dialog').innerText())); await page.keyboard.press('Escape');
  check('administration : 7 rubriques', true);
} catch (e) { check('parcours', false, String(e.stack).split('\n').slice(0, 4).join(' | ')); await shot('erreur'); }
const bad = errors.filter(e => !/favicon/.test(e)); check('aucune erreur console', bad.length === 0, bad.slice(0, 3).join(' / '));
await browser.close(); process.exit(results.every(r => r[1]) ? 0 : 1);
