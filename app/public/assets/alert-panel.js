/* Surveillance d'une position, partagée par le détail du Portefeuille (onglet Alertes) et le Centre d'alertes.
   AlertPanel.render(host, {S: état alerts/state, pid, listing, reload, cur?: {price, currency, gainPct, gainEur}})
   Une alerte informe, elle ne vend jamais. Les seuils viennent toujours des paramètres réels (stratégie ou saisie de l'utilisateur), jamais d'une valeur inventée. */
(function (root) {
  'use strict';
  const KIND = { price_below: ['Cours inférieur à', '€'], price_above: ['Cours supérieur à', '€'], target: ['Objectif de cours', '€'], gain_pct_above: ['Gain personnel', '%'], loss_pct: ['Perte personnelle', '%'], gain_eur_above: ['Gain personnel', '€'], loss_eur: ['Perte personnelle', '€'], drawdown_from_high: ['Recul depuis le plus haut cours', '%'], gain_giveback: ['Gain rendu depuis le meilleur résultat', 'pts'], daily_move: ['Variation sur une séance', '%'], slope_min: ['Pente minimale', '%/séance'], r2_min: ['Régularité minimale (R²)', ''], vol_max: ['Volatilité maximale', '%/séance'], drawdown_max: ['Recul maximal', '%'], momentum_min: ['Progression minimale', '%'], ma_below: ['Cours sous la moyenne mobile', 'séances'], momentum6_min: ['Momentum 6 mois (6−1)', '%'], momentum12_min: ['Momentum 12 mois (12−1)', '%'], er_min: ['Régularité (efficacité)', ''], ma_falling: ['Moyenne mobile en baisse', 'séances'], gap_ma20_max: ['Écart à la moyenne 20 séances', '%'] };
  const OP = { price_below: '<', price_above: '>', target: '≥', gain_pct_above: '≥', loss_pct: '≥', gain_eur_above: '≥', loss_eur: '≥', drawdown_from_high: '≥', gain_giveback: '≥', daily_move: '≥', slope_min: '≥', r2_min: '≥', vol_max: '≤', drawdown_max: '≤', momentum_min: '≥', ma_below: '<', momentum6_min: '≥', momentum12_min: '≥', er_min: '≥', ma_falling: '≥', gap_ma20_max: '≤' };
  const GRAN = { day: '1 jour', week: '1 semaine', month: '1 mois', quarter: '3 mois', half: '6 mois', year: '1 an' };
  const GW = { day: 'un jour', week: 'une semaine', month: 'un mois', quarter: 'trois mois', half: 'six mois', year: 'un an' };
  const SEV = { info: 'Information', vigilance: 'Vigilance', goal: 'Objectif atteint', sell: 'Vente à envisager' };
  const STATUS = { official: 'Officielle', adapted: 'Adaptée', personal: 'Personnelle' };
  const TREND = ['slope_min', 'r2_min', 'vol_max', 'drawdown_max', 'momentum_min', 'momentum6_min', 'momentum12_min', 'er_min'];
  const STATE = { normal: ['ok', 'Normale'], triggered: ['ko', 'Déclenchée'], insufficient: ['na', 'Non évaluable'], error: ['na', 'Non évaluable'], none: ['na', 'En attente d’évaluation'], off: ['off', 'Désactivée'] };
  const EV = { triggered: 'Déclenchée', normal: 'Retour à la normale', insufficient: 'Données insuffisantes', acked: 'Acquittée', rearmed: 'Réarmée' };
  /* protections proposées à l'utilisateur : type, libellé, unité du champ, niveau */
  const CHOICES = [['loss_pct', 'Être averti si je perds X %', '%', 'vigilance'], ['loss_eur', 'Être averti si je perds X €', '€', 'sell'], ['gain_pct_above', 'Être averti si je gagne X %', '%', 'goal'], ['price_below', 'Être averti si le cours passe sous X €', '€', 'sell'], ['price_above', 'Être averti si le cours dépasse X €', '€', 'goal'], ['gain_eur_above', 'Être averti si je gagne X €', '€', 'goal'], ['daily_move', 'Être averti d’une variation brutale en une séance (X %)', '%', 'vigilance'], ['gain_giveback', 'Être averti si je rends une partie de mes gains', 'points de rendement', 'vigilance'], ['drawdown_from_high', 'Être averti si le cours recule de X % depuis son plus haut', '%', 'vigilance']];
  const esc = s => J.esc(String(s == null ? '' : s));
  const fmt = v => v === null || v === undefined ? '–' : J.num(v, Number.isInteger(+v) ? 0 : Math.abs(v) < 1 ? 4 : 2);
  const when = d => d ? J.dateTime(String(d).replace(' ', 'T')) : '–';
  const stateOf = r => !r.enabled ? 'off' : r.state === null ? 'none' : (r.state === 'triggered' && r.acked_at ? 'acked' : r.state);
  const badge = r => { const k = stateOf(r); if (k === 'acked') return '<span class="al-b ko">Déclenchée · acquittée</span>'; const [c, l] = STATE[k]; return `<span class="al-b ${c}">${l}</span>`; };
  const unit = k => (KIND[k] || [0, ''])[1];
  const label = r => (KIND[r.kind] || [r.kind])[0] + (r.granularity ? ' · ' + GRAN[r.granularity] : '');

  /** Titre et phrase « M'avertir si… » en langage courant. */
  function words(r) {
    const t = r.threshold === null || r.threshold === '' || r.threshold === undefined ? '…' : fmt(+r.threshold), g = GW[r.granularity] || 'la durée choisie', inh = r.source === 'strategy';
    const T = {
      slope_min: ['Tendance sur ' + g, inh ? `M’avertir si la hausse moyenne passe sous ${t} % par séance (seuil de ma stratégie).` : `M’avertir si la hausse moyenne passe sous ${t} % par séance.`],
      r2_min: ['Régularité sur ' + g, inh ? `M’avertir si la régularité (R²) passe sous ${t} (seuil de ma stratégie).` : `M’avertir si la régularité (R²) passe sous ${t}.`],
      vol_max: ['Volatilité sur ' + g, inh ? `M’avertir si la volatilité dépasse ${t} % par séance (seuil de ma stratégie).` : `M’avertir si la volatilité dépasse ${t} % par séance.`],
      drawdown_max: ['Recul maximal sur ' + g, inh ? `M’avertir si la plus forte baisse dépasse ${t} % (seuil de ma stratégie).` : `M’avertir si la plus forte baisse dépasse ${t} %.`],
      momentum_min: ['Progression sur ' + g, inh ? `M’avertir si la progression passe sous ${t} % (seuil de ma stratégie).` : `M’avertir si la progression passe sous ${t} %.`],
      loss_pct: ['Perte de ' + t + ' %', `M’avertir si je perds ${t} % ou plus sur ce titre.`], loss_eur: ['Perte de ' + t + ' €', `M’avertir si je perds ${t} € ou plus sur ce titre.`],
      gain_pct_above: ['Gain de ' + t + ' %', `M’avertir si je gagne ${t} % ou plus sur ce titre.`], gain_eur_above: ['Gain de ' + t + ' €', `M’avertir si je gagne ${t} € ou plus sur ce titre.`],
      price_below: ['Cours sous ' + t + ' €', `M’avertir si le cours passe sous ${t} €.`], price_above: ['Cours au-dessus de ' + t + ' €', `M’avertir si le cours dépasse ${t} €.`], target: ['Objectif de cours : ' + t + ' €', `M’avertir quand le cours atteint ${t} €.`],
      gain_giveback: ['Gains rendus : ' + t + ' points', `M’avertir si mon rendement recule de ${t} points par rapport à son meilleur niveau.`], drawdown_from_high: ['Recul de ' + t + ' % depuis le plus haut', `M’avertir si le cours recule de ${t} % depuis son plus haut depuis mon premier achat.`],
      daily_move: ['Variation d’une séance : ' + t + ' %', `M’avertir si le cours varie de ${t} % ou plus en une séance.`], ma_below: ['Cours sous la moyenne ' + t + ' séances', `M’avertir si le cours passe sous sa moyenne des ${t} dernières séances.`],
      ma_falling: ['Moyenne ' + t + ' séances en baisse', `M’avertir si la moyenne des ${t} dernières séances se met à baisser.`],
      momentum6_min: ['Momentum 6 mois (6−1)', `M’avertir si le momentum 6−1 (variation entre il y a 6 mois et il y a 1 mois) passe sous ${t} %.`],
      momentum12_min: ['Momentum 12 mois (12−1)', `M’avertir si le momentum 12−1 (variation entre il y a 12 mois et il y a 1 mois) passe sous ${t} %.`],
      er_min: ['Régularité sur ' + g, `M’avertir si la régularité de la hausse passe sous ${t}.`], gap_ma20_max: ['Écart à la moyenne 20 séances', `M’avertir si le cours s’écarte de plus de ${t} % de sa moyenne 20 séances.`]
    };
    return T[r.kind] || [label(r), ''];
  }
  const HOW = { slope_min: 'Même calcul que le moteur de la stratégie : progression moyenne du cours par séance sur la durée.', r2_min: 'Proche de 1, la hausse est régulière.', vol_max: 'Écart-type des variations quotidiennes.', drawdown_max: 'Plus forte baisse depuis un sommet sur la durée.', momentum_min: 'Rendement du cours sur la durée.', gain_giveback: 'Rendement actuel sur la ligne comparé à son meilleur niveau atteint.', momentum6_min: 'Variation du cours entre J−126 et J−21 séances (le dernier mois est exclu).', momentum12_min: 'Variation du cours entre J−252 et J−21 séances (le dernier mois est exclu).', ma_below: 'Cours comparé à la moyenne des dernières clôtures.', ma_falling: 'Moyenne d’aujourd’hui comparée à celle d’il y a 5 séances.', gap_ma20_max: 'Écart entre le cours et sa moyenne sur 20 séances.', er_min: 'Rapport entre la progression nette et le chemin parcouru.', drawdown_from_high: 'Cours actuel comparé à son plus haut depuis votre premier achat.' };
  const FREQ = k => TREND.includes(k) || ['ma_below', 'ma_falling', 'gap_ma20_max'].includes(k) ? 'une fois par jour de cotation' : 'toutes les 5 minutes (au plus une fois par 10 minutes et par règle)';

  function eventsHtml(es, symbolOf) {
    return es.length ? es.map(e => `<div class="al-ev"><span>${when(e.at)}</span>${symbolOf ? `<b>${esc(symbolOf(e.listing_id))}</b>` : ''}<span class="al-b ${e.event === 'triggered' ? 'ko' : e.event === 'normal' ? 'ok' : 'na'}">${EV[e.event] || esc(e.event)}</span><small>${esc(KIND[e.kind] ? KIND[e.kind][0] : e.kind)}${e.value_obs !== null && e.value_obs !== undefined ? ' · valeur ' + fmt(+e.value_obs) : ''}${e.threshold !== null && e.threshold !== undefined ? ' · seuil ' + fmt(+e.threshold) : ''}${e.message ? ' · ' + esc(e.message) : ''}</small></div>`).join('') : '<p class="muted pad">Aucun événement enregistré.</p>';
  }
  const isCompl = r => r.source === 'strategy' && !r.enabled && /à confirmer/i.test(r.why || '');
  /** Règle normale : une ligne compacte. Règle déclenchée ou non évaluable : carte détaillée. Modification en place, dans la ligne. */
  function ruleRow(r, ui) {
    const k = stateOf(r), inh = r.source === 'strategy', custom = inh && r.default_threshold !== null && Math.abs(r.threshold - r.default_threshold) > 2e-6, [title, ask] = words(r), open = k === 'triggered' || k === 'acked' || k === 'insufficient' || k === 'error' || k === 'none';
    const tag = isCompl(r) ? '<span class="al-b pe">Complément proposé · à confirmer</span>' : inh ? (custom ? '<span class="al-b pe">Personnalisée</span>' : '<span class="al-b he">Modèle</span>') : '<span class="al-b pe">Personnelle</span>';
    const thr = r.threshold === null ? 'seuil non renseigné' : `${OP[r.kind]} ${fmt(r.threshold)} ${unit(r.kind)}`.trim();
    if (ui.edit === r.id) return `<div class="al-r ap-edit" data-rid="${r.id}"><div class="ap-rh"><b>${esc(title)}</b> ${tag}</div>${TREND.includes(r.kind) ? `<p class="small muted">Durée de mesure : ${GRAN[r.granularity]}. Modifier ce seuil n’altère jamais la stratégie.</p>` : ''}
      <div class="ap-form"><label>Seuil <input id="ap-e-t" inputmode="decimal" value="${r.threshold === null ? '' : r.threshold}" placeholder="À vous de choisir"> <span class="small muted">${esc(unit(r.kind))}</span></label></div><p class="small muted" id="ap-e-s" aria-live="polite"></p>
      <div class="al-ra"><button type="button" class="btn small primary" data-es="${r.id}">Enregistrer</button><button type="button" class="btn small" data-ec>Annuler</button>${custom ? `<button type="button" class="btn small" data-rs="${r.id}">Restaurer le modèle (${fmt(r.default_threshold)})</button>` : ''}</div></div>`;
    const acts = `<button type="button" class="btn small" data-ed="${r.id}">Modifier</button>${r.enabled ? `<button type="button" class="btn small" data-tg="${r.id}" data-on="0">Désactiver</button>` : `<button type="button" class="btn small" data-tg="${r.id}" data-on="1">${isCompl(r) ? 'Activer' : 'Réactiver'}</button>`}${k === 'triggered' ? `<button type="button" class="btn small" data-ak="${r.id}">Acquitter</button>` : ''}${r.state === 'triggered' && r.acked_at && r.enabled ? `<button type="button" class="btn small" data-ra="${r.id}">Réarmer</button>` : ''}${inh ? '' : `<button type="button" class="btn small" data-dl="${r.id}">Supprimer</button>`}`;
    if (!open) return `<div class="al-r ap-line ${r.enabled ? '' : 'dim'}"><div class="ap-l1"><b>${esc(title)}</b> <span class="small muted">${esc(thr)}${r.last_value !== null ? ' · mesuré ' + fmt(r.last_value) + ' ' + unit(r.kind) : ''}</span> ${tag} ${badge(r)}</div><div class="al-ra">${acts}</div></div>`;
    return `<div class="al-r ${r.enabled ? '' : 'dim'}"><div class="ap-rh"><b>${esc(title)}</b> ${tag} ${badge(r)}</div><p class="ap-ask">${esc(ask)}</p>
      <dl class="ap-m"><div><dt>Valeur mesurée</dt><dd>${r.last_value !== null ? fmt(r.last_value) + ' ' + unit(r.kind) : 'non mesurée'}</dd></div><div><dt>Seuil</dt><dd>${esc(thr)}${custom ? ` <small>(modèle : ${fmt(r.default_threshold)})</small>` : ''}</dd></div><div><dt>Dernière vérification</dt><dd>${when(r.last_eval_at)}</dd></div></dl>
      ${r.last_reason && ['insufficient', 'error'].includes(r.state) ? `<p class="small muted">Non évaluable : ${esc(r.last_reason)}</p>` : ''}${r.why ? `<p class="small muted">${esc(r.why)}</p>` : ''}
      <div class="al-ra">${acts}</div>
      <details class="al-cmp"><summary>Détails</summary><p>${esc(HOW[r.kind] || '')} Vérifiée ${FREQ(r.kind)}.</p>${r.triggered_at ? `<p>Déclenchée le ${when(r.triggered_at)}${r.acked_at ? ', acquittée le ' + when(r.acked_at) + ' (acquitter n’éteint pas la condition)' : ''}.</p>` : ''}</details></div>`;
  }
  /** État global : jamais « Tout va bien » sans règle réellement évaluée. */
  function globalState(rs) {
    const on = rs.filter(r => r.enabled); if (!rs.length) return ['none', 'Surveillance non configurée']; if (!on.length) return ['off', 'Surveillance désactivée'];
    const trig = on.filter(r => r.state === 'triggered' && !r.acked_at); if (trig.length) return trig.some(r => ['sell', 'goal'].includes(r.severity)) ? ['ko', 'Alerte déclenchée'] : ['na', 'Vigilance'];
    if (on.some(r => ['insufficient', 'error'].includes(r.state))) return ['na', 'Données insuffisantes']; if (!on.some(r => r.state === 'normal')) return ['na', 'Vérification en attente'];
    return ['ok', 'Tout va bien : ' + on.filter(r => r.state === 'normal').length + ' règle(s) évaluée(s)'];
  }
  function originInfo(p) {
    const dates = {}; p.origins.forEach(o => { dates[o.tx] = o.date; });
    const rows = [];
    p.origins.filter(o => o.strategy).forEach(o => rows.push([o.date, o.label + (STATUS[o.status] ? ' — ' + STATUS[o.status] : '')]));
    p.lot_strategies.forEach(l => { if (!p.origins.some(o => o.tx === l.tx && o.strategy)) rows.push([dates[l.tx] || null, l.label]); });
    const uniq = [...new Set(rows.map(r => r[1]))], unknown = p.origins.filter(o => !o.strategy && !p.lot_strategies.some(l => l.tx === o.tx));
    return { rows, uniq, unknown };
  }

  const PRESET_ID = { regular: 'regular', fast: 'fast', low_volatility: 'calm', recovery: 'rebound', momentum: 'mom6', momentum12: 'mom12', momentum_risk: 'momrisk' };
  /** Stratégies d'achat connues de la position, de la plus récente à la plus ancienne (clés Classement). Jamais devinées. */
  function knownStrategies(S, p) {
    const ok = k => { if (!k) return null; if (S.strategies.some(s => s.key === k)) return k; const m = PRESET_ID[k]; return m && S.strategies.some(s => s.key === m) ? m : null; };
    const dates = {}; p.origins.forEach(o => { dates[o.tx] = o.date; });
    const rows = []; p.origins.forEach(o => { const k = ok(o.strategy); if (k) rows.push([o.date, k]); });
    p.lot_strategies.forEach(l => { const k = ok(l.strategy); if (k && !p.origins.some(o => o.tx === l.tx && o.strategy)) rows.push([dates[l.tx] || '', k]); });
    rows.sort((x, y) => String(y[0]).localeCompare(String(x[0])));
    return [...new Set(rows.map(r => r[1]))];
  }
  const label0 = (S, k) => (S.strategies.find(s => s.key === k) || {}).label || k;
  const sentence = (kind, t, r) => words({ kind, threshold: t, granularity: r && r.granularity, source: r ? r.source : 'personal' })[1];
  function need(r) { const n = { day: 2, week: 6, month: 22, quarter: 64, half: 127, year: 253 }; if (r.kind === 'momentum6_min') return 127; if (r.kind === 'momentum12_min') return 253; if (r.kind === 'ma_below') return +r.threshold; if (r.kind === 'ma_falling') return +r.threshold + 5; if (r.kind === 'gap_ma20_max') return 20; return TREND.includes(r.kind) ? n[r.granularity] : null; }
  function previewHtml(d, key, cur, S) {
    const tpl = d.tpl || [], row = r => { const rr = Object.assign({ source: 'strategy' }, r), n = need(rr), ti = words(rr)[0]; return `<li class="ap-pv"><b>${esc(ti)}</b> <span class="small muted">${OP[r.kind]} ${fmt(r.threshold)} ${unit(r.kind)}</span>${r.enabled === false ? ' <span class="al-b pe">Complément proposé · à confirmer (désactivé)</span>' : ''}<br><small class="muted">${esc(r.why || '')}${n ? ` Nécessite ${n} clôtures.` : ''}</small></li>`; };
    return `<section class="ap-pvw" aria-label="Règles proposées"><h4>Règles proposées · ${esc(d.strategy_label)}</h4>
      ${cur && cur !== key ? `<p class="small">Vous passez de <b>${esc(label0(S, cur))}</b> à <b>${esc(d.strategy_label)}</b>. La stratégie d’origine des achats ne change pas.</p>` : ''}
      ${tpl.length ? `<ul class="ap-pvl">${tpl.map(row).join('')}</ul>` : '<p class="small">Cette stratégie n’a aucun critère surveillable : aucune règle ne sera créée. Vos protections personnelles restent intactes.</p>'}
      ${d.update.length ? `<p class="small"><b>Seuils mis à jour (${d.update.length})</b> : ${d.update.map(u => `${esc(KIND[u.kind][0])}${u.granularity ? ' · ' + GRAN[u.granularity] : ''} ${fmt(u.from)} → ${fmt(u.to)}`).join(' ; ')}</p>` : ''}
      ${d.keep.length ? `<p class="small"><b>Vos seuils modifiés sont conservés (${d.keep.length})</b> : ${d.keep.map(u => `${esc(KIND[u.kind][0])}${u.granularity ? ' · ' + GRAN[u.granularity] : ''} votre ${fmt(u.threshold)} (modèle ${fmt(u.strategy_threshold)})`).join(' ; ')}</p>` : ''}
      <p class="small muted">${d.personal_kept} protection(s) personnelle(s) conservée(s). Rien n’est supprimé. Aucune vente automatique.</p></section>`;
  }

  function render(host, o) {
    const S = o.S, p = S.positions.find(x => x.listing_id === o.listing);
    if (!p) { host.innerHTML = '<p class="muted">Sélectionnez une position pour voir sa surveillance.</p>'; return; }
    if (!host._ui || host._ui.lid !== p.listing_id) host._ui = { lid: p.listing_id, pick: false, key: null, plan: null, protect: false, edit: null };
    const ui = host._ui, redraw = () => render(host, o);
    const rs = S.rules.filter(r => r.listing_id === p.listing_id), inh = rs.filter(r => r.source === 'strategy'), mine = rs.filter(r => r.source !== 'strategy');
    const gs = globalState(rs), on = rs.filter(r => r.enabled), trig = on.filter(r => r.state === 'triggered' && !r.acked_at), last = rs.map(r => r.last_eval_at).filter(Boolean).sort().pop();
    const evs = S.events.filter(e => e.listing_id === p.listing_id), log = (p.watch_log || []).slice(0, 6), cur = p.watch ? p.watch.key : '';
    const known = knownStrategies(S, p), proposal = known[0] || '', configured = !!cur;
    const sel = (id, v) => `<select id="${id}" aria-label="Stratégie de surveillance"><option value="">Choisir…</option>${S.strategies.map(s => `<option value="${esc(s.key)}" ${v === s.key ? 'selected' : ''}>${esc(s.label)}${STATUS[s.status] ? ' — ' + STATUS[s.status] : ''}</option>`).join('')}</select>`;
    const upd = configured && p.watch.model_latest && p.watch.model_version && p.watch.model_latest > p.watch.model_version;
    let top;
    if (!configured && !rs.length) {
      top = `<div class="ap-empty"><b>Surveillance non configurée</b>
        ${proposal ? `<p>${known.length > 1 ? 'Plusieurs stratégies d’achat connues. Proposition : la plus récente, ' : 'Stratégie d’achat connue : '}<b>${esc(label0(S, proposal))}</b>. ${known.length > 1 ? 'Les seuils ne sont jamais fusionnés.' : ''}</p>` : '<p>Choisir une stratégie pour surveiller ce titre. Les règles viendront de ses vrais critères.</p>'}
        <div class="ap-pick">${proposal && !ui.pick ? `<button type="button" class="btn small primary" id="ap-prop">Voir les règles de ${esc(label0(S, proposal))}</button><button type="button" class="btn small" id="ap-other">Choisir une autre stratégie</button>` : sel('ap-watch', ui.key || '')}</div></div>`;
    } else {
      top = `<div class="ap-top"><div><small>Stratégie de surveillance</small><b>${configured ? esc(p.watch.label) : 'Aucune (protections seulement)'}</b>${configured ? `<small>Modèle version ${p.watch.model_version || '–'}${upd ? ` · version ${p.watch.model_latest} disponible` : ''}</small>` : ''}</div>
        <div><small>État</small><span class="al-b ${gs[0]}">${esc(gs[1])}</span><small>${on.length} règle(s) active(s) · ${trig.length} déclenchée(s)</small></div>
        <div><small>Dernière vérification</small><b>${rs.length ? when(last) : '–'}</b><button type="button" class="btn small" id="ap-chg">${ui.pick ? 'Annuler' : 'Changer de stratégie'}</button></div></div>
        ${ui.pick ? `<div class="ap-pick">${sel('ap-watch', ui.key || '')}</div>` : ''}${upd ? '<div class="ap-note">Une nouvelle version du modèle existe. <button type="button" class="btn small" id="ap-sync">Voir les changements</button></div>' : ''}`;
    }
    const pv = ui.plan ? `${previewHtml(ui.plan, ui.key, cur, S)}<div class="al-ra"><button type="button" class="btn small primary" id="ap-go">${configured && cur !== ui.key ? 'Appliquer le changement' : configured ? 'Appliquer la mise à jour' : 'Activer la surveillance'}</button><button type="button" class="btn small" id="ap-no">Annuler</button></div>` : '';
    const choices = CHOICES, ch0 = choices[0];
    const form = ui.protect ? `<div class="ap-form ap-new"><label>Type <select id="pr-k">${choices.map(x => `<option value="${x[0]}">${esc(x[1])}</option>`).join('')}</select></label><label>Seuil <input id="pr-t" inputmode="decimal" placeholder="À vous de choisir"></label><p class="small muted" id="pr-u"></p><p class="small" id="pr-s" aria-live="polite"></p><p class="small" id="pr-e" role="alert"></p>
      <div class="al-ra"><button type="button" class="btn small primary" id="pr-ok">Enregistrer</button><button type="button" class="btn small" id="pr-no">Annuler</button></div></div>` : '';
    host.innerHTML = `<div class="ap">${top}${pv}
      ${inh.length || configured ? `<h4>Ce que Jigobourso surveille pour moi${inh.length && configured ? ` <button type="button" class="btn small" id="ap-reset">Restaurer le modèle par défaut</button>` : ''}</h4>${inh.map(r => ruleRow(r, ui)).join('') || '<p class="muted small">Cette stratégie n’a pas de critère surveillable.</p>'}` : ''}
      <h4>Mes protections <button type="button" class="btn small" id="ap-add">Ajouter une protection</button></h4>${form}${mine.map(r => ruleRow(r, ui)).join('') || (ui.protect ? '' : '<p class="muted small">Aucune protection personnelle. Vous fixez vous-même ce qui vous protège : aucun seuil n’est choisi à votre place.</p>')}
      ${evs.length || log.length ? `<details class="ap-hist"><summary>Historique (${evs.length + log.length})</summary>${eventsHtml(evs.slice(0, 12))}${log.map(l => `<div class="al-ev"><span>${when(l.at)}</span><span class="al-b pe">Surveillance</span><small>${esc(l.summary)}</small></div>`).join('')}</details>` : ''}</div>`;
    const q = i => host.querySelector(i), post = async (url, b) => { try { await J.post(url, b); return true; } catch (e) { J.toast(e.message); return false; } }, done = () => { host._ui.edit = null; return o.reload(); };
    const preview = async key => {
      if (!key) { ui.plan = null; ui.key = null; redraw(); return; }
      let d; try { d = await J.post('alerts/apply-template', { portfolio_id: o.pid, listing_id: p.listing_id, strategy: key, mode: configured ? 'sync' : 'add', dry: true }); } catch (e) { J.toast(e.message); return; }
      ui.key = key; ui.plan = d; redraw();
    };
    q('#ap-watch')?.addEventListener('change', e => preview(e.target.value));
    q('#ap-prop')?.addEventListener('click', () => preview(proposal));
    q('#ap-other')?.addEventListener('click', () => { ui.pick = true; redraw(); });
    q('#ap-chg')?.addEventListener('click', () => { ui.pick = !ui.pick; ui.plan = null; ui.key = null; redraw(); });
    q('#ap-no')?.addEventListener('click', () => { ui.plan = null; ui.key = null; ui.pick = false; redraw(); });
    q('#ap-sync')?.addEventListener('click', () => preview(cur));
    q('#ap-reset')?.addEventListener('click', async () => { ui.reset = true; let d; try { d = await J.post('alerts/apply-template', { portfolio_id: o.pid, listing_id: p.listing_id, strategy: cur, mode: 'reset', dry: true }); } catch (e) { J.toast(e.message); return; } ui.key = cur; ui.plan = Object.assign(d, { reset: true }); redraw(); });
    q('#ap-go')?.addEventListener('click', async () => { const mode = ui.plan.reset ? 'reset' : configured ? 'sync' : 'add'; if (await post('alerts/apply-template', { portfolio_id: o.pid, listing_id: p.listing_id, strategy: ui.key, mode })) { await post('alerts/refresh', {}); ui.plan = null; ui.key = null; ui.pick = false; await done(); } });
    host.querySelectorAll('[data-tg]').forEach(b => b.onclick = async () => { await post('alerts/rule-toggle', { id: +b.dataset.tg, enabled: b.dataset.on === '1' }); if (b.dataset.on === '1') await post('alerts/refresh', {}); done(); });
    host.querySelectorAll('[data-ed]').forEach(b => b.onclick = () => { ui.edit = +b.dataset.ed; redraw(); host.querySelector('#ap-e-t')?.focus(); });
    host.querySelectorAll('[data-ec]').forEach(b => b.onclick = () => { ui.edit = null; redraw(); });
    host.querySelectorAll('[data-es]').forEach(b => b.onclick = async () => {
      const r = S.rules.find(x => x.id == b.dataset.es), t = q('#ap-e-t').value.trim().replace(',', '.');
      if (!t || isNaN(+t)) { q('#ap-e-s').textContent = 'Indiquez un seuil numérique.'; return; }
      if (await post('alerts/rule-save', { id: r.id, portfolio_id: o.pid, listing_id: p.listing_id, kind: r.kind, granularity: r.granularity || undefined, threshold: t, severity: r.severity, enabled: !!r.enabled })) { await post('alerts/refresh', {}); done(); }
    });
    host.querySelectorAll('[data-rs]').forEach(b => b.onclick = async () => { await post('alerts/rule-restore', { id: +b.dataset.rs }); await post('alerts/refresh', {}); done(); });
    host.querySelectorAll('[data-ak]').forEach(b => b.onclick = async () => { await post('alerts/rule-ack', { id: +b.dataset.ak }); done(); });
    host.querySelectorAll('[data-ra]').forEach(b => b.onclick = async () => { await post('alerts/rule-rearm', { id: +b.dataset.ra }); await post('alerts/refresh', {}); done(); });
    host.querySelectorAll('[data-dl]').forEach(b => b.onclick = async () => { if (await J.confirm('Supprimer l’alerte', 'Cette règle et son historique seront supprimés.', 'Supprimer')) { await post('alerts/rule-delete', { id: +b.dataset.dl }); done(); } });
    q('#ap-add').onclick = () => { ui.protect = !ui.protect; redraw(); q('#pr-t')?.focus(); };
    if (ui.protect) {
      const c = o.cur || {}, px = c.price != null ? 'Cours actuel : ' + J.num(c.price, 2) + ' ' + (c.currency || '') : '', gp = c.gainPct != null ? 'Rendement actuel : ' + J.num(c.gainPct, 2) + ' %' : '', ge = c.gainEur != null ? 'Résultat actuel : ' + J.num(c.gainEur, 2) + ' €' : '';
      const curTxt = k => ({ price_below: px, price_above: px, target: px, loss_pct: gp, gain_pct_above: gp, gain_giveback: gp, loss_eur: ge, gain_eur_above: ge })[k] || '';
      const sync = () => { const k = q('#pr-k').value, cc = CHOICES.find(x => x[0] === k), t = q('#pr-t').value.trim().replace(',', '.'); q('#pr-u').textContent = 'Unité : ' + cc[2] + (curTxt(k) ? ' · ' + curTxt(k) : '') + '.'; q('#pr-s').textContent = t ? sentence(k, t).replace('M’avertir', 'Vous serez averti') : ''; };
      q('#pr-k').onchange = sync; q('#pr-t').oninput = sync; sync();
      q('#pr-no').onclick = () => { ui.protect = false; redraw(); };
      q('#pr-ok').onclick = async () => {
        const k = q('#pr-k').value, cc = CHOICES.find(x => x[0] === k), t = q('#pr-t').value.trim().replace(',', '.');
        if (!t || isNaN(+t)) { q('#pr-e').textContent = 'Indiquez un seuil : il n’est jamais choisi à votre place.'; return; }
        try { await J.post('alerts/rule-save', { portfolio_id: o.pid, listing_id: p.listing_id, kind: k, threshold: t, severity: cc[3], enabled: true }); } catch (e) { q('#pr-e').textContent = e.message; return; }
        ui.protect = false; await post('alerts/refresh', {}); await o.reload();
      };
    }
  }
  function originDialog(o, p, lots) {
    J.dialog({ title: 'Stratégie d’origine · ' + p.symbol, body: `<p class="small muted">Indiquez la stratégie réellement utilisée pour cet achat. Elle n’est jamais devinée ; une fois enregistrée à l’achat, elle ne se modifie plus.</p>${J.field('Achat', `<select id="so-tx">${lots.map(l => `<option value="${l.tx}">Achat du ${J.date(l.date)}</option>`).join('')}</select>`)}${J.field('Stratégie', `<select id="so-st">${o.S.strategies.map(s => `<option value="${esc(s.key)}">${esc(s.label)} — ${STATUS[s.status] || ''}</option>`).join('')}</select>`)}`,
      actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async d => { try { await J.post('alerts/origin', { tx_id: +d.querySelector('#so-tx').value, strategy: d.querySelector('#so-st').value }); } catch (e) { J.formError(d, e.message); return true; } await o.reload(); } }] });
  }
  root.AlertPanel = { render, originDialog, eventsHtml, stateOf, badge, label, fmt, when, words, globalState, KIND, OP, GRAN, SEV, STATUS, STATE };
})(window);
