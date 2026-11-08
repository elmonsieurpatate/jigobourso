/* Centre d'alertes V4 : modèles par stratégie, règles personnelles, évaluation, acquittement, réarmement, isolation entre comptes, affichage desktop et mobile. */
const assert = require('node:assert/strict'); const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const BASE = process.env.BASE || 'http://127.0.0.1:18095', SHOTS = process.env.SHOTS || '';
(async () => {
  const b = await chromium.launch({ executablePath: process.env.JIGO_CHROMIUM, args: ['--no-sandbox'] });
  const login = async (u, p, width = 1440) => { const ctx = await b.newContext({ viewport: { width, height: 1000 }, isMobile: width < 600, hasTouch: width < 600 }); const r = await ctx.request.post(BASE + '/api.php?r=auth/login', { data: { username: u, password: p } }); assert.equal(r.ok(), true, 'login ' + u); return ctx; };
  const call = async (ctx, route, data) => { const r = data === undefined ? await ctx.request.get(BASE + '/api.php?r=' + route) : await ctx.request.post(BASE + '/api.php?r=' + route, { data }); return { status: r.status(), body: await r.json().catch(() => ({})) }; };
  try {
    const A = await login('audit_portfolio', 'audit-local-validation-2026');
    const pfs = (await call(A, 'portfolios')).body.portfolios; let pid = null, st = null;
    for (const p of pfs) { const s = (await call(A, 'alerts/state&portfolio=' + p.id)).body; if (s.positions.length > 2 && (!st || s.positions.length > st.positions.length)) { st = s; pid = p.id; } }
    assert.ok(st, 'portefeuille avec positions'); const lid = st.positions[0].listing_id;
    assert.ok(st.strategies.some(s => s.key === 'regular'), 'stratégies listées');
    // modèle de stratégie : règles issues de la configuration réelle
    const ap = (await call(A, 'alerts/apply-template', { portfolio_id: pid, listing_id: lid, strategy: 'regular', mode: 'add' })).body; assert.ok(ap.added >= 2, 'règles de la stratégie créées ' + JSON.stringify(ap));
    const ap2 = (await call(A, 'alerts/apply-template', { portfolio_id: pid, listing_id: lid, strategy: 'regular', mode: 'add' })).body; assert.equal(ap2.added, 0, 'pas de doublon');
    // règle personnelle : cours très supérieur => normale ; cours très bas => déclenchée
    const hi = (await call(A, 'alerts/rule-save', { portfolio_id: pid, listing_id: lid, kind: 'price_below', threshold: 1e8, severity: 'sell' })).body.id;
    const lo = (await call(A, 'alerts/rule-save', { portfolio_id: pid, listing_id: lid, kind: 'price_above', threshold: 0.0001, severity: 'goal' })).body.id;
    const bad = await call(A, 'alerts/rule-save', { portfolio_id: pid, listing_id: lid, kind: 'inconnu', threshold: 1 }); assert.equal(bad.status, 422);
    let s0 = (await call(A, 'alerts/state&portfolio=' + pid)).body; assert.ok(s0.rules.every(r => r.state === null), 'jamais « Normale » sans évaluation');
    await call(A, 'alerts/refresh', {});
    let s1 = (await call(A, 'alerts/state&portfolio=' + pid)).body; const get = id => s1.rules.find(r => r.id === id);
    assert.equal(get(hi).state, 'triggered'); assert.equal(get(lo).state, 'triggered');
    assert.ok(s1.rules.every(r => r.state !== null && r.last_eval_at), 'toutes évaluées'); assert.ok(s1.counts.triggered >= 2);
    const n1 = s1.events.length; await call(A, 'alerts/refresh', {}); let s2 = (await call(A, 'alerts/state&portfolio=' + pid)).body; assert.equal(s2.events.length, n1, 'pas de nouvel événement tant que la condition persiste');
    await call(A, 'alerts/rule-ack', { id: hi }); s2 = (await call(A, 'alerts/state&portfolio=' + pid)).body; assert.ok(s2.rules.find(r => r.id === hi).acked_at); assert.equal(s2.counts.triggered, s1.counts.triggered - 1);
    await call(A, 'alerts/rule-save', { id: hi, kind: 'price_below', threshold: 0.0001, severity: 'sell', enabled: true }); await call(A, 'alerts/refresh', {});
    s2 = (await call(A, 'alerts/state&portfolio=' + pid)).body; assert.equal(s2.rules.find(r => r.id === hi).state, 'normal'); await call(A, 'alerts/rule-rearm', { id: hi });
    // restauration d'un seuil hérité
    const inh = s2.rules.find(r => r.source === 'strategy'); const orig = inh.threshold; await call(A, 'alerts/rule-save', { id: inh.id, kind: inh.kind, granularity: inh.granularity, threshold: orig + 1, severity: 'vigilance', enabled: true });
    await call(A, 'alerts/rule-restore', { id: inh.id }); assert.equal((await call(A, 'alerts/state&portfolio=' + pid)).body.rules.find(r => r.id === inh.id).threshold, orig);
    // origine : valeur manuelle acceptée pour un achat sans origine, jamais inventée
    const pos = (await call(A, 'alerts/state&portfolio=' + pid)).body.positions[0]; assert.ok(pos.origins.every(o => o.strategy === null || o.by), 'origine absente tant que non renseignée');
    const tx = pos.origins[0].tx; assert.equal((await call(A, 'alerts/origin', { tx_id: tx, strategy: 'fast' })).status, 200); assert.equal((await call(A, 'alerts/origin', { tx_id: tx, strategy: 'nope' })).status, 422);
    // isolation : un autre compte ne voit ni ne touche rien
    const B = await login('plain_user', 'plain-local-password');
    assert.equal((await call(B, 'alerts/state&portfolio=' + pid)).status, 404);
    assert.equal((await call(B, 'alerts/rule-delete', { id: hi })).status, 404); assert.equal((await call(B, 'alerts/rule-ack', { id: lo })).status, 404);
    assert.equal((await call(B, 'alerts/rule-save', { portfolio_id: pid, listing_id: lid, kind: 'target', threshold: 5 })).status, 404);
    const sb = (await call(B, 'alerts/state')).body; assert.deepEqual(sb.rules || [], []);
    // interface
    for (const width of [390, 1440]) {
      const ctx = await login('audit_portfolio', 'audit-local-validation-2026', width), page = await ctx.newPage(), errors = []; page.on('pageerror', e => errors.push(e.message)); page.setDefaultTimeout(15000);
      await page.goto(`${BASE}/alertes.html?portfolio=${pid}&listing=${lid}`); await page.locator('.al-cnt').waitFor(); await page.locator('.al-row').first().waitFor();
      assert.ok(await page.locator('.al-c').count() === 4); assert.ok(await page.locator('#al-side .al-r').count() >= 3);
      assert.doesNotMatch(await page.locator('#al-side').innerText(), /Stratégie d’origine/); assert.match(await page.locator('#al-side').innerText(), /Stratégie de surveillance/);
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/al-${width}.png`, fullPage: true });
      await page.locator('#al-tabs [data-t="hist"]').click(); assert.ok(await page.locator('.al-ev').count() >= 1);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, 'défilement horizontal ' + width);
      assert.deepEqual(errors, []); await ctx.close(); console.log('ok ui', width);
    }
    // suppression
    await call(A, 'alerts/rule-delete', { id: lo }); assert.ok(!(await call(A, 'alerts/state&portfolio=' + pid)).body.rules.some(r => r.id === lo));
    console.log('ok alertes');
  } finally { await b.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
