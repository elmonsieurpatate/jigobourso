// Mesures navigateur (Chromium) sur la base de perf jetable : temps de chargement, octets JSON de l'API, coût d'un tri et d'une recherche côté client.
// Prérequis : scripts/perf_probe.py exécuté, serveur php -S sur 127.0.0.1:18089 avec JIGO_DB_NAME=jigobourso_perf, utilisateur perf_user.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE);
const BASE = 'http://127.0.0.1:18089/';
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.JIGO_CHROMIUM, args: ['--no-sandbox'] });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage(); page.setDefaultTimeout(120000);
  const api = []; page.on('response', async (r) => { if (r.url().includes('api.php')) { try { api.push({ route: new URL(r.url()).searchParams.get('r'), kb: Math.round((await r.body()).length / 1024), wire_kb: r.headers()['content-length'] ? Math.round(r.headers()['content-length'] / 1024) : null, encoding: r.headers()['content-encoding'] || null, timing: r.headers()['server-timing'] || null }); } catch (e) { /* page changée */ } } });
  await page.goto(BASE + 'login.html'); await page.fill('#u', 'perf_user'); await page.fill('#p', 'perf-local-password'); await page.click('#auth-form button.primary'); await page.waitForURL('**/index.html');
  const out = [];
  const t0 = Date.now(); api.length = 0;
  await page.goto(BASE + 'index.html');
  await page.waitForFunction(() => /Cliquez sur/.test(document.querySelector('#ct-ranking-status')?.textContent || ''), null, { timeout: 120000 });
  const ready = Date.now() - t0; api.length = 0; const t1 = Date.now();
  await page.click('#ct-apply');
  await page.locator('#ct-table-body tr:not(.ct-loading)').first().waitFor({ timeout: 120000 });
  const rowsMs = Date.now() - t1;
  await page.waitForLoadState('networkidle').catch(() => {});
  const rows = await page.locator('#ct-table-body tr').count();
  const heap = await page.evaluate(() => (performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null));
  const r = { page: 'classement (index.html)', page_ready_ms: ready, apply_to_first_row_ms: rowsMs, rendered_rows: rows, js_heap_mb: heap, api: api.slice() };
  r.client_sort_ms = await page.evaluate(async () => { const th = document.querySelector('#ct-table-head th'); if (!th) return null; const t = performance.now(); th.click(); await new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res))); return Math.round(performance.now() - t); });
  r.client_search_ms_incl_wait = await page.evaluate(async () => { const el = document.querySelector('#ct-search'); if (!el) return null; const t = performance.now(); el.value = 'Titre synthétique 12'; el.dispatchEvent(new Event('input', { bubbles: true })); await new Promise((res) => setTimeout(res, 700)); return Math.round(performance.now() - t); });
  r.rows_after_search = await page.locator('#ct-table-body tr').count();
  out.push(r);
  for (const [name, url, sel] of [['fiche titre', 'titre.html?id=1', '.hero'], ['portefeuilles', 'portefeuilles.html', '#page']]) {
    api.length = 0; const t = Date.now(); await page.goto(BASE + url); await page.locator(sel).first().waitFor({ timeout: 60000 }); await page.waitForLoadState('networkidle').catch(() => {});
    out.push({ page: name, idle_ms: Date.now() - t, api: api.slice() });
  }
  await browser.close(); console.log(JSON.stringify(out, null, 1));
})().catch((e) => { console.error(e); process.exit(1); });
