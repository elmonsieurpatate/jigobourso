/* Centre d'alertes : compteurs, liste des règles, configuration d'une position (stratégie d'origine, stratégie de surveillance, règles héritées et personnelles), historique, notifications. */
(async () => {
  const user = await J.init('alertes'); if (!user) return;
  const page = J.$('#page'), qs = new URLSearchParams(location.search);
  const KIND = { price_below: ['Cours inférieur à', '€'], price_above: ['Cours supérieur à', '€'], target: ['Objectif de cours', '€'], gain_pct_above: ['Gain personnel', '%'], loss_pct: ['Perte personnelle', '%'], gain_eur_above: ['Gain personnel', '€'], loss_eur: ['Perte personnelle', '€'], drawdown_from_high: ['Recul depuis le sommet', '%'], gain_giveback: ['Gain rendu depuis le meilleur', 'pts'], daily_move: ['Variation sur une séance', '%'], slope_min: ['Pente minimale', '%/séance'], r2_min: ['R² minimal', ''], vol_max: ['Volatilité maximale', '%/séance'], drawdown_max: ['Recul maximal', '%'], momentum_min: ['Progression minimale', '%'], ma_below: ['Cours sous la moyenne mobile', 'séances'] };
  const OP = { price_below: '<', price_above: '>', target: '≥', gain_pct_above: '≥', loss_pct: '≥', gain_eur_above: '≥', loss_eur: '≥', drawdown_from_high: '≥', gain_giveback: '≥', daily_move: '≥', slope_min: '≥', r2_min: '≥', vol_max: '≤', drawdown_max: '≤', momentum_min: '≥', ma_below: '<' };
  const GRAN = { day: '1 jour', week: '1 semaine', month: '1 mois', quarter: '3 mois', half: '6 mois', year: '1 an' };
  const SEV = { info: 'Information', vigilance: 'Vigilance', goal: 'Objectif atteint', sell: 'Vente à envisager' };
  const STATUS = { official: 'Officielle', adapted: 'Adaptée', personal: 'Personnelle' };
  const TREND = ['slope_min', 'r2_min', 'vol_max', 'drawdown_max', 'momentum_min'];
  const STATE = { normal: ['ok', 'Normale'], triggered: ['ko', 'Déclenchée'], insufficient: ['na', 'Données insuffisantes'], error: ['na', 'Erreur d’évaluation'], none: ['na', 'Pas encore évaluée'], off: ['off', 'Désactivée'] };
  const V = { tab: 'all', q: '', sel: +qs.get('listing') || null };
  let S = null, pid = +qs.get('portfolio') || null;
  const fmt = v => v === null || v === undefined ? '–' : J.num(v, Math.abs(v) < 1 ? 4 : 2);
  const stateOf = r => !r.enabled ? 'off' : r.state === null ? 'none' : (r.state === 'triggered' && r.acked_at ? 'acked' : r.state);
  const badge = r => { const k = stateOf(r); if (k === 'acked') return '<span class="al-b ko">Déclenchée · acquittée</span>'; const [c, l] = STATE[k]; return `<span class="al-b ${c}">${l}</span>`; };
  const when = d => d ? J.dateTime(String(d).replace(' ', 'T')) : '–';
  const pos = id => S.positions.find(p => p.listing_id === id);
  const label = r => (KIND[r.kind] || [r.kind])[0] + (r.granularity ? ' · ' + GRAN[r.granularity] : '');

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
  function events(es) { return es.length ? es.map(e => { const p = pos(e.listing_id); return `<div class="al-ev"><span>${when(e.at)}</span><b>${J.esc(p ? p.symbol : '?')}</b><span class="al-b ${e.event === 'triggered' ? 'ko' : e.event === 'normal' ? 'ok' : 'na'}">${({ triggered: 'Déclenchée', normal: 'Retour à la normale', insufficient: 'Données insuffisantes', acked: 'Acquittée', rearmed: 'Réarmée' })[e.event]}</span><small>${J.esc(KIND[e.kind] ? KIND[e.kind][0] : e.kind)}${e.value_obs !== null ? ' · valeur ' + fmt(+e.value_obs) : ''}${e.threshold !== null ? ' · seuil ' + fmt(+e.threshold) : ''}${e.message ? ' · ' + J.esc(e.message) : ''}</small></div>`; }).join('') : '<p class="muted pad">Aucun événement pour le moment.</p>'; }

  function ruleLine(r) {
    const k = stateOf(r), inh = r.source === 'strategy', custom = inh && r.default_threshold !== null && Math.abs(r.threshold - r.default_threshold) > 1e-9;
    return `<div class="al-r ${r.enabled ? '' : 'dim'}"><label class="sw"><input type="checkbox" data-tg="${r.id}" ${r.enabled ? 'checked' : ''}><i></i></label><div class="al-rt"><b>${J.esc(label(r))}</b><small>${OP[r.kind]} ${fmt(r.threshold)} ${KIND[r.kind] ? KIND[r.kind][1] : ''} · ${SEV[r.severity]}</small><small>${badge(r)} ${r.last_value !== null ? 'valeur ' + fmt(r.last_value) : ''}</small></div><span class="al-b ${r.source === 'strategy' ? (custom ? 'pe' : 'he') : r.source === 'legacy' ? 'he' : 'pe'}">${r.source === 'strategy' ? (custom ? 'Personnalisée' : 'Héritée') : r.source === 'legacy' ? 'Stop / objectif' : 'Personnelle'}</span><div class="al-ra"><button class="btn small" data-ed="${r.id}" aria-label="Modifier">✎</button>${custom ? `<button class="btn small" data-rs="${r.id}" title="Restaurer la valeur de la stratégie">↺</button>` : ''}${k === 'triggered' ? `<button class="btn small" data-ak="${r.id}">Acquitter</button>` : ''}${r.state === 'triggered' && r.acked_at || k === 'off' ? '' : `<button class="btn small" data-ra="${r.id}" title="Réarmer : réévaluer comme neuve">⟳</button>`}<button class="btn small danger" data-dl="${r.id}" aria-label="Supprimer">✕</button></div></div>`;
  }
  function side() {
    const host = J.$('#al-side'), p = pos(V.sel);
    if (!p) { host.innerHTML = '<div class="al-box"><p class="muted">Sélectionnez une position pour configurer ses alertes.</p></div>'; return; }
    const rs = S.rules.filter(r => r.listing_id === p.listing_id), strat = rs.filter(r => r.source === 'strategy'), perso = rs.filter(r => r.source !== 'strategy');
    const origins = p.origins.filter(o => o.strategy), legacy = p.lot_strategies, unknown = p.origins.filter(o => !o.strategy && !p.lot_strategies.some(l => l.tx === o.tx));
    const oTxt = origins.length ? origins.map(o => `${J.esc(o.label)} — ${STATUS[o.status] || ''} <small>(achat du ${J.date(o.date)})</small>`).join('<br>') : legacy.length ? legacy.map(l => `${J.esc(l.label)} <small>(renseignée manuellement)</small>`).join('<br>') : 'Stratégie non renseignée';
    host.innerHTML = `<div class="al-box"><div class="al-ph"><h2>${J.esc(p.symbol)}</h2><span>${J.esc(p.name || '')}</span>${p.listing_id ? `<a class="btn small" href="titre.html?id=${p.listing_id}&from=alertes" target="_blank" rel="noopener">Analyse du titre ↗</a>` : ''}</div>
      <div class="al-st"><div><small>Stratégie d’origine</small><b>${oTxt}</b>${unknown.length ? `<button class="btn small" id="al-setorigin">Renseigner</button>` : ''}</div>
      <div><small>Stratégie de surveillance</small><select id="al-watch"><option value="">Choisir…</option>${S.strategies.map(s => `<option value="${J.esc(s.key)}" ${p.watch && p.watch.key === s.key ? 'selected' : ''}>${J.esc(s.label)} — ${STATUS[s.status]}</option>`).join('')}</select><div class="row"><button class="btn small primary" id="al-apply">Appliquer le modèle</button>${p.watch ? '<button class="btn small" id="al-sync">Mettre à jour</button>' : ''}</div></div></div>
      <h3>Paramètres prédéfinis <small>(hérités de la stratégie)</small></h3>${strat.map(ruleLine).join('') || '<p class="muted small">Aucune règle héritée. Choisissez une stratégie de surveillance puis « Appliquer le modèle ».</p>'}
      <h3>Alertes personnelles <button class="btn small primary" id="al-add">＋ Ajouter</button></h3>${perso.map(ruleLine).join('') || '<p class="muted small">Aucune alerte personnelle.</p>'}
      <h3>Historique</h3><div class="al-evs">${events(S.events.filter(e => e.listing_id === p.listing_id).slice(0, 8))}</div></div>
      <div class="al-box"><h3>Notifications</h3><label class="check"><input type="checkbox" id="np-in" checked disabled> Dans Jigobourso (cloche et centre d’alertes)</label><label class="check"><input type="checkbox" id="np-mail" ${S.prefs.alert_email ? 'checked' : ''}> Par e-mail (envoi à chaque nouveau déclenchement)</label><p class="muted small">Pas de notification sur téléphone pour l’instant : aucun service de notifications mobiles n’est en place.</p></div>`;
    J.$$('[data-tg]', host).forEach(i => i.onchange = async () => { await J.post('alerts/rule-toggle', { id: +i.dataset.tg, enabled: i.checked }); load(); });
    J.$$('[data-ed]', host).forEach(b => b.onclick = () => ruleDialog(p, S.rules.find(r => r.id == b.dataset.ed)));
    J.$$('[data-rs]', host).forEach(b => b.onclick = async () => { await J.post('alerts/rule-restore', { id: +b.dataset.rs }); load(); });
    J.$$('[data-ak]', host).forEach(b => b.onclick = async () => { await J.post('alerts/rule-ack', { id: +b.dataset.ak }); load(); });
    J.$$('[data-ra]', host).forEach(b => b.onclick = async () => { await J.post('alerts/rule-rearm', { id: +b.dataset.ra }); await J.post('alerts/refresh', {}); load(); });
    J.$$('[data-dl]', host).forEach(b => b.onclick = async () => { if (await J.confirm('Supprimer l’alerte', 'Cette règle et son historique seront supprimés.', 'Supprimer')) { await J.post('alerts/rule-delete', { id: +b.dataset.dl }); load(); } });
    J.$('#al-add').onclick = () => ruleDialog(p, null);
    const apply = async mode => { const key = J.$('#al-watch').value; if (!key) { J.toast('Choisissez une stratégie'); return; } try { const r = await J.post('alerts/apply-template', { portfolio_id: pid, listing_id: p.listing_id, strategy: key, mode }); await J.post('alerts/refresh', {}); J.toast(r.available ? `${r.added} règle(s) ajoutée(s), ${r.updated} mise(s) à jour, ${r.kept} personnalisée(s) conservée(s)` : 'Cette stratégie n’a pas de critère à surveiller : ajoutez vos propres alertes.'); load(); } catch (e) { J.toast(e.message); } };
    J.$('#al-apply').onclick = () => apply('add'); J.$('#al-sync')?.addEventListener('click', () => apply('sync'));
    J.$('#al-setorigin')?.addEventListener('click', () => originDialog(p, unknown));
    J.$('#np-mail').onchange = async e => { await J.post('alerts/prefs', { alert_email: e.target.checked }); S.prefs.alert_email = e.target.checked; };
  }
  function ruleDialog(p, r) {
    const kinds = Object.keys(KIND);
    J.dialog({ title: r ? 'Modifier l’alerte' : 'Nouvelle alerte · ' + p.symbol, body: `${J.field('Type', `<select id="ar-k" ${r ? 'disabled' : ''}>${kinds.map(k => `<option value="${k}" ${r && r.kind === k ? 'selected' : ''}>${KIND[k][0]}${KIND[k][1] ? ' (' + KIND[k][1] + ')' : ''}</option>`).join('')}</select>`)}<div id="ar-g">${J.field('Durée de mesure', `<select id="ar-gr">${Object.entries(GRAN).map(([k, l]) => `<option value="${k}" ${r && r.granularity === k ? 'selected' : ''}>${l}</option>`).join('')}</select>`)}</div>${J.field('Seuil', `<input id="ar-t" inputmode="decimal" value="${r ? r.threshold : ''}">`)}${J.field('Niveau', `<select id="ar-s">${Object.entries(SEV).map(([k, l]) => `<option value="${k}" ${(r ? r.severity : 'vigilance') === k ? 'selected' : ''}>${l}</option>`).join('')}</select>`)}<p class="small muted" id="ar-h"></p>`,
      onopen: d => { const sync = () => { const k = J.$('#ar-k', d).value; J.$('#ar-g', d).hidden = !TREND.includes(k); J.$('#ar-h', d).textContent = 'Condition : ' + (KIND[k][0]) + ' ' + OP[k] + ' seuil. Une alerte informe, elle ne vend jamais.'; }; J.$('#ar-k', d).onchange = sync; sync(); },
      actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async d => { const v = i => J.$(i, d).value.trim().replace(',', '.'); try { await J.post('alerts/rule-save', { id: r ? r.id : undefined, portfolio_id: pid, listing_id: p.listing_id, kind: r ? r.kind : v('#ar-k'), granularity: v('#ar-gr'), threshold: v('#ar-t'), severity: v('#ar-s'), enabled: r ? !!r.enabled : true }); } catch (e) { J.formError(d, e.message); return true; } await J.post('alerts/refresh', {}); load(); } }] });
  }
  function originDialog(p, lots) {
    J.dialog({ title: 'Stratégie d’origine · ' + p.symbol, body: `<p class="small muted">Indiquez la stratégie réellement utilisée pour ces achats. Elle ne sera jamais devinée, et une fois enregistrée à l’achat elle ne se modifie plus.</p>${J.field('Achat', `<select id="so-tx">${lots.map(o => `<option value="${o.tx}">Achat du ${J.date(o.date)}</option>`).join('')}</select>`)}${J.field('Stratégie', `<select id="so-st">${S.strategies.map(s => `<option value="${J.esc(s.key)}">${J.esc(s.label)} — ${STATUS[s.status]}</option>`).join('')}</select>`)}`,
      actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async d => { try { await J.post('alerts/origin', { tx_id: +J.$('#so-tx', d).value, strategy: J.$('#so-st', d).value }); } catch (e) { J.formError(d, e.message); return true; } load(); } }] });
  }
  load().catch(e => { page.innerHTML = `<div class="notice err">${J.esc(e.message)}</div>`; });
})();
