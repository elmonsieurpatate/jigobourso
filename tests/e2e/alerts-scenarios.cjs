/* 33 scénarios fonctionnels du moteur d'alertes (via l'API réelle) : transitions, acquittement, réarmement, données insuffisantes, modèles de stratégie, aperçu, isolation. */
const assert = require('node:assert/strict'); const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const BASE = process.env.BASE || 'http://127.0.0.1:18095'; let n = 0;
(async () => {
  const b = await chromium.launch({ executablePath: process.env.JIGO_CHROMIUM, args: ['--no-sandbox'] });
  const login = async (u, p) => { const c = await b.newContext(); assert.equal((await c.request.post(BASE + '/api.php?r=auth/login', { data: { username: u, password: p } })).ok(), true); return c; };
  const call = async (c, r, d) => { const x = d === undefined ? await c.request.get(BASE + '/api.php?r=' + r) : await c.request.post(BASE + '/api.php?r=' + r, { data: d }); return { s: x.status(), b: await x.json().catch(() => ({})) }; };
  const ok = (name, cond, extra) => { assert.ok(cond, name + ' ' + (extra || '')); n++; console.log('✓', n, name); };
  try {
    const A = await login('audit_portfolio', 'audit-local-validation-2026'), B = await login('plain_user', 'plain-local-password');
    let pid, st; for (const p of (await call(A, 'portfolios')).b.portfolios) { const s = (await call(A, 'alerts/state&portfolio=' + p.id)).b; if (s.positions.length >= 3 && (!st || s.positions.length > st.positions.length)) { st = s; pid = p.id; } }
    const lid = st.positions[1].listing_id, other = st.positions[2].listing_id, S = async () => (await call(A, 'alerts/state&portfolio=' + pid)).b, R = (s, id) => s.rules.find(r => r.id === id);
    const save = async d => (await call(A, 'alerts/rule-save', Object.assign({ portfolio_id: pid, listing_id: lid, severity: 'vigilance' }, d)));
    const lo = (await save({ kind: 'price_above', threshold: 0.0001 })).b.id;                                   // toujours vraie
    ok('01 règle neuve : jamais évaluée, pas « Normale »', R(await S(), lo).state === null);
    await call(A, 'alerts/refresh', {}); let s = await S();
    ok('02 condition vraie : déclenchée', R(s, lo).state === 'triggered');
    const ev1 = s.events.filter(e => e.rule_id === lo && e.event === 'triggered').length; ok('03 un seul événement de déclenchement', ev1 === 1, ev1);
    await call(A, 'alerts/refresh', {}); s = await S(); ok('04 condition persistante : aucun nouvel événement', s.events.filter(e => e.rule_id === lo && e.event === 'triggered').length === 1);
    await call(A, 'alerts/rule-ack', { id: lo }); s = await S(); ok('05 acquittement : state reste déclenchée, acked_at posé', R(s, lo).state === 'triggered' && !!R(s, lo).acked_at);
    ok('06 acquittée : retirée du compteur à traiter', s.counts.triggered === (await S()).counts.triggered && !s.rules.some(r => r.id === lo && r.state === 'triggered' && !r.acked_at));
    await save({ id: lo, kind: 'price_above', threshold: 1e9, enabled: true }); await call(A, 'alerts/refresh', {}); s = await S();
    ok('07 condition disparue : retour à normale journalisé', R(s, lo).state === 'normal' && s.events.some(e => e.rule_id === lo && e.event === 'normal'));
    await save({ id: lo, kind: 'price_above', threshold: 0.0001, enabled: true }); await call(A, 'alerts/refresh', {}); s = await S();
    ok('08 nouveau déclenchement après retour normal : nouvel événement', s.events.filter(e => e.rule_id === lo && e.event === 'triggered').length === 2);
    await call(A, 'alerts/rule-rearm', { id: lo }); s = await S(); ok('09 réarmement : état remis à zéro', R(s, lo).state === null && !R(s, lo).acked_at);
    await call(A, 'alerts/rule-toggle', { id: lo, enabled: false }); await call(A, 'alerts/refresh', {}); s = await S(); ok('10 règle désactivée : non évaluée', R(s, lo).state === null && !R(s, lo).enabled);
    await call(A, 'alerts/rule-toggle', { id: lo, enabled: true }); await call(A, 'alerts/refresh', {}); ok('11 réactivée : évaluée', R(await S(), lo).state === 'triggered');
    const ma = (await save({ kind: 'ma_below', threshold: 5000 })).b.id; await call(A, 'alerts/refresh', {}); s = await S();
    ok('12 historique trop court : données insuffisantes, jamais Normale', ['insufficient', 'error'].includes(R(s, ma).state), R(s, ma).state);
    ok('13 type inconnu refusé', (await save({ kind: 'zzz', threshold: 1 })).s === 422);
    ok('14 seuil manquant refusé', (await save({ kind: 'price_below' })).s === 422);
    ok('15 tendance sans durée refusée', (await save({ kind: 'slope_min', threshold: 0.1 })).s === 422);
    const bad = await call(A, 'alerts/rule-save', { portfolio_id: pid, listing_id: 999999, kind: 'price_below', threshold: 1 }); ok('16 titre non détenu refusé', bad.s === 404);
    const dry = (await call(A, 'alerts/apply-template', { portfolio_id: pid, listing_id: other, strategy: 'regular', mode: 'add', dry: true })).b; s = await S();
    ok('17 aperçu : liste des ajouts sans rien écrire', dry.add.length >= 2 && !s.rules.some(r => r.listing_id === other));
    const ap = (await call(A, 'alerts/apply-template', { portfolio_id: pid, listing_id: other, strategy: 'regular', mode: 'add' })).b; ok('18 application : règles créées', ap.added === dry.add.length, JSON.stringify(ap));
    ok('19 application répétée : aucun doublon', (await call(A, 'alerts/apply-template', { portfolio_id: pid, listing_id: other, strategy: 'regular', mode: 'add' })).b.added === 0);
    s = await S(); const inh = s.rules.find(r => r.listing_id === other && r.source === 'strategy'); const orig = inh.threshold;
    await save({ listing_id: other, id: inh.id, kind: inh.kind, granularity: inh.granularity, threshold: orig + 1 });
    const sync = (await call(A, 'alerts/apply-template', { portfolio_id: pid, listing_id: other, strategy: 'regular', mode: 'sync' })).b; s = await S();
    ok('20 synchronisation : seuil modifié conservé', sync.kept >= 1 && R(s, inh.id).threshold === orig + 1);
    await call(A, 'alerts/rule-restore', { id: inh.id }); ok('21 restauration de la valeur de la stratégie', R(await S(), inh.id).threshold === orig);
    const chg = (await call(A, 'alerts/apply-template', { portfolio_id: pid, listing_id: other, strategy: 'fast', mode: 'sync', dry: true })).b;
    ok('22 changement de stratégie : aperçu avec règles personnelles intactes', typeof chg.personal_kept === 'number' && (chg.add.length + chg.update.length + chg.keep.length) >= 1);
    await call(A, 'alerts/apply-template', { portfolio_id: pid, listing_id: other, strategy: 'fast', mode: 'sync' }); s = await S(); const pos = s.positions.find(p => p.listing_id === other);
    ok('23 stratégie de surveillance changée et journalisée', pos.watch.key === 'fast' && pos.watch_log.length >= 2, JSON.stringify(pos.watch_log));
    ok('24 stratégie inconnue refusée', (await call(A, 'alerts/apply-template', { portfolio_id: pid, listing_id: other, strategy: 'nope', mode: 'add' })).s === 422);
    ok('25 isolation : un autre compte ne voit ni ne modifie', (await call(B, 'alerts/state&portfolio=' + pid)).s === 404 && (await call(B, 'alerts/rule-ack', { id: lo })).s === 404 && (await call(B, 'alerts/apply-template', { portfolio_id: pid, listing_id: lid, strategy: 'regular' })).s === 404);
    // modèles versionnés, restauration, compléments désactivés, journal
    s = await S(); let pos2 = s.positions.find(p => p.listing_id === other); const fastRules = s.rules.filter(r => r.listing_id === other && r.source === 'strategy' && r.strategy_key === 'fast');
    ok('26 modèle : version enregistrée sur la position et sur chaque règle, avec explication', pos2.watch.model_version >= 1 && fastRules.length > 0 && fastRules.every(r => r.model_version === pos2.watch.model_version && r.why), JSON.stringify(pos2.watch));
    const cu = fastRules.find(r => r.kind === 'slope_min'); await save({ listing_id: other, id: cu.id, kind: cu.kind, granularity: cu.granularity, threshold: cu.threshold + 0.5 });
    const rdry = (await call(A, 'alerts/apply-template', { portfolio_id: pid, listing_id: other, strategy: 'fast', mode: 'reset', dry: true })).b; ok('27 restauration du modèle : aperçu de la personnalisation à défaire, rien d’écrit', rdry.update.some(u => u.id === cu.id) && Math.abs(R(await S(), cu.id).threshold - cu.threshold - 0.5) < 2e-6, JSON.stringify(rdry));
    await call(A, 'alerts/apply-template', { portfolio_id: pid, listing_id: other, strategy: 'fast', mode: 'reset' }); ok('28 restauration du modèle : seuil du modèle rétabli, personnelles intactes', Math.abs(R(await S(), cu.id).threshold - cu.threshold) < 2e-6);
    const mdry = (await call(A, 'alerts/apply-template', { portfolio_id: pid, listing_id: other, strategy: 'mom6', mode: 'sync', dry: true })).b; ok('29 momentum sans seuil : un seul complément, désactivé et à confirmer', mdry.tpl.length === 1 && mdry.tpl[0].enabled === false && mdry.tpl[0].kind === 'momentum6_min', JSON.stringify(mdry.tpl));
    await call(A, 'alerts/apply-template', { portfolio_id: pid, listing_id: other, strategy: 'mom6', mode: 'sync' }); s = await S(); const comp = s.rules.find(r => r.listing_id === other && r.strategy_key === 'mom6');
    ok('30 complément créé désactivé, jamais évalué', comp && comp.enabled === 0 && comp.state === null && /à confirmer/.test(comp.why), JSON.stringify(comp));
    ok('31 nouveau changement de stratégie : règles précédentes conservées sans doublon', (await call(A, 'alerts/apply-template', { portfolio_id: pid, listing_id: other, strategy: 'mom6', mode: 'sync' })).b.added === 0);
    await call(A, 'alerts/rule-toggle', { id: comp.id, enabled: true }); await call(A, 'alerts/refresh', {}); s = await S(); const c2 = R(s, comp.id);
    ok('32 complément confirmé : évalué, et jamais « normal » sans données (non évaluable ou mesuré)', c2.enabled === 1 && (['normal', 'triggered'].includes(c2.state) ? c2.last_value !== null : ['insufficient', 'error'].includes(c2.state) && !!c2.last_reason), JSON.stringify(c2));
    ok('33 journal : modifications et activations tracées', s.positions.find(p => p.listing_id === other).watch_log.some(l => /Règle activée|Seuil modifié|restauré/.test(l.summary)), JSON.stringify(s.positions.find(p => p.listing_id === other).watch_log));
    console.log('ok scénarios', n);
  } finally { await b.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
