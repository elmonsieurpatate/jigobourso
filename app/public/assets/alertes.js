/* Centre d'alertes : compteurs, liste des règles, configuration d'une position (stratégie d'origine, stratégie de surveillance, règles héritées et personnelles), historique, notifications. */
(async () => {
  const user = await J.init('alertes'); if (!user) return;
  const page = J.$('#page'), qs = new URLSearchParams(location.search);
  const AP = AlertPanel, KIND = AP.KIND, OP = AP.OP, GRAN = AP.GRAN, SEV = AP.SEV, STATE = AP.STATE, STATUS = AP.STATUS;
  const V = { tab: 'all', q: '', sel: +qs.get('listing') || null };
  let S = null, pid = +qs.get('portfolio') || null;
  const fmt = AP.fmt;
  const stateOf = AP.stateOf;
  const badge = AP.badge;
  const when = AP.when;
  const pos = id => S.positions.find(p => p.listing_id === id);
  const label = AP.label;

  async function load() {
    S = await J.api('alerts/state', { params: pid ? { portfolio: pid } : {} });
    if (S.portfolio) pid = S.portfolio.id;
    if (!V.sel || !pos(V.sel)) V.sel = S.positions.length ? S.positions[0].listing_id : null;
    draw();
  }
  function draw() {
    if (!S.portfolio) { page.innerHTML = '<div class="card empty"><p>Aucun portefeuille. Créez-en un pour surveiller vos titres.</p><a class="btn primary" href="portefeuilles.html">Aller aux portefeuilles</a></div>'; return; }
    const c = S.counts, rules = S.rules;
    page.innerHTML = `<div class="al"><header class="al-h"><div><h1>Centre d’alertes</h1><p class="muted">Surveillez vos positions, vos stratégies et vos objectifs. Jigobourso signale, il ne vend jamais à votre place.</p></div><div class="al-hr"><select id="al-pf" aria-label="Portefeuille">${S.portfolios.map(p => `<option value="${p.id}" ${p.id === pid ? 'selected' : ''}>${J.esc(p.name)}</option>`).join('')}</select><button class="btn" id="al-refresh">Évaluer maintenant</button></div></header>
      <section class="al-cnt"><div class="al-c g"><b>${c.active}</b><span>Alertes actives</span></div><div class="al-c r"><b>${c.triggered}</b><span>Déclenchées à traiter</span></div><div class="al-c o"><b>${c.todo}</b><span>Position(s) sans alerte</span></div><div class="al-c n"><b>${c.insufficient}</b><span>Données insuffisantes</span></div></section>
      <div class="al-grid"><section class="al-main"><div class="al-tabs" id="al-tabs">${[['all', 'Toutes', rules.length], ['active', 'Actives', c.active], ['trig', 'Déclenchées', c.triggered], ['todo', 'À configurer', c.todo], ['hist', 'Historique', S.events.length]].map(([k, l, n]) => `<button data-t="${k}" class="${V.tab === k ? 'on' : ''}">${l} <i>${n}</i></button>`).join('')}<input id="al-q" type="search" placeholder="Rechercher un titre" value="${J.esc(V.q)}"></div><div id="al-list"></div></section><aside class="al-side" id="al-side"></aside></div></div>`;
    J.$('#al-pf').onchange = e => { pid = +e.target.value; V.sel = null; load(); };
    J.$('#al-refresh').onclick = async e => { e.target.disabled = true; try { await J.post('alerts/refresh', {}); await load(); J.toast('Évaluation terminée'); } catch (x) { J.toast(x.message); } e.target.disabled = false; };
    J.$$('#al-tabs [data-t]').forEach(b => b.onclick = () => { V.tab = b.dataset.t; draw(); });
    J.$('#al-q').oninput = e => { V.q = e.target.value; list(); };
    list(); side();
  }
  function list() {
    const q = V.q.trim().toLowerCase(), host = J.$('#al-list');
    if (V.tab === 'hist') { host.innerHTML = events(S.events.filter(e => { const p = pos(e.listing_id); return !q || (p && (p.symbol + p.name).toLowerCase().includes(q)); })); return; }
    if (V.tab === 'todo') { host.innerHTML = S.positions.filter(p => !p.rules && (!q || (p.symbol + p.name).toLowerCase().includes(q))).map(p => `<div class="al-row todo" data-p="${p.listing_id}"><div class="al-t"><b>${J.esc(p.symbol)}</b><small>${J.esc(p.name || '')}</small></div><div class="al-w">Aucune alerte configurée</div><button class="btn small primary">Configurer</button></div>`).join('') || '<p class="muted pad">Toutes vos positions ont au moins une alerte.</p>'; bind(); return; }
    let rs = S.rules.filter(r => { const p = pos(r.listing_id); return p && (!q || (p.symbol + p.name).toLowerCase().includes(q)); });
    if (V.tab === 'active') rs = rs.filter(r => r.enabled); if (V.tab === 'trig') rs = rs.filter(r => r.enabled && r.state === 'triggered' && !r.acked_at);
    host.innerHTML = rs.length ? rs.map(r => { const p = pos(r.listing_id); return `<div class="al-row sev-${r.severity} ${V.sel === r.listing_id ? 'sel' : ''}" data-p="${r.listing_id}"><div class="al-t"><b>${J.esc(p.symbol)}</b><small>${J.esc(p.name || '')}</small></div><div class="al-w"><b>${J.esc(label(r))}</b><small>${OP[r.kind]} ${fmt(r.threshold)} ${KIND[r.kind] ? KIND[r.kind][1] : ''} · ${r.source === 'strategy' ? 'Stratégie' : r.source === 'legacy' ? 'Stop / objectif' : 'Personnelle'}</small></div><div class="al-s">${badge(r)}<small>${r.last_eval_at ? 'Éval. ' + when(r.last_eval_at) : 'Jamais évaluée'}${r.last_value !== null ? ' · valeur ' + fmt(r.last_value) : ''}</small>${r.last_reason && r.state !== 'normal' ? `<small class="muted">${J.esc(r.last_reason)}</small>` : ''}</div></div>`; }).join('') : '<p class="muted pad">Aucune alerte dans ce filtre.</p>';
    bind();
  }
  function bind() { J.$$('#al-list [data-p]').forEach(r => r.onclick = () => { V.sel = +r.dataset.p; list(); side(); J.$('#al-side').scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }); }
  function events(es) { return AP.eventsHtml(es, id => { const p = pos(id); return p ? p.symbol : '?'; }); }
  function side() {
    const host = J.$('#al-side'), p = pos(V.sel);
    if (!p) { host.innerHTML = '<div class="al-box"><p class="muted">Sélectionnez une position pour configurer ses alertes.</p></div>'; return; }
    host.innerHTML = `<div class="al-box"><div class="al-ph"><h2>${J.esc(p.symbol)}</h2><span>${J.esc(p.name || '')}</span>${p.listing_id ? `<a class="btn small" href="titre.html?id=${p.listing_id}&from=alertes" target="_blank" rel="noopener">Analyse du titre ↗</a>` : ''}</div><div id="al-panel"></div></div>
      <div class="al-box"><h3>Notifications</h3><label class="check"><input type="checkbox" id="np-in" checked disabled> Dans Jigobourso (cloche et centre d’alertes)</label><label class="check"><input type="checkbox" id="np-mail" ${S.prefs.alert_email ? 'checked' : ''}> Par e-mail à chaque nouvelle alerte déclenchée</label><p class="small muted">Notifications sur mobile : indisponibles pour l’instant (le site n’est pas une application installée).</p></div>`;
    AP.render(J.$('#al-panel'), { S, pid, listing: p.listing_id, reload: load });
    J.$('#np-mail').onchange = async e => { await J.post('alerts/prefs', { alert_email: e.target.checked }); S.prefs.alert_email = e.target.checked; };
  }
  load().catch(e => { page.innerHTML = `<div class="notice err">${J.esc(e.message)}</div>`; });
})();
