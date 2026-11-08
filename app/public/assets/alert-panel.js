/* Surveillance d'une position, partagée par le détail du Portefeuille (onglet Alertes) et le Centre d'alertes.
   AlertPanel.render(host, {S: état alerts/state, pid, listing, reload, cur?: {price, currency, gainPct, gainEur}})
   Une alerte informe, elle ne vend jamais. Les seuils viennent toujours des paramètres réels (stratégie ou saisie de l'utilisateur), jamais d'une valeur inventée. */
(function (root) {
  'use strict';
  const KIND = { price_below: ['Cours inférieur à', '€'], price_above: ['Cours supérieur à', '€'], target: ['Objectif de cours', '€'], gain_pct_above: ['Gain personnel', '%'], loss_pct: ['Perte personnelle', '%'], gain_eur_above: ['Gain personnel', '€'], loss_eur: ['Perte personnelle', '€'], drawdown_from_high: ['Recul depuis le plus haut cours', '%'], gain_giveback: ['Gain rendu depuis le meilleur résultat', 'pts'], daily_move: ['Variation sur une séance', '%'], slope_min: ['Pente minimale', '%/séance'], r2_min: ['Régularité minimale (R²)', ''], vol_max: ['Volatilité maximale', '%/séance'], drawdown_max: ['Recul maximal', '%'], momentum_min: ['Progression minimale', '%'], ma_below: ['Cours sous la moyenne mobile', 'séances'] };
  const OP = { price_below: '<', price_above: '>', target: '≥', gain_pct_above: '≥', loss_pct: '≥', gain_eur_above: '≥', loss_eur: '≥', drawdown_from_high: '≥', gain_giveback: '≥', daily_move: '≥', slope_min: '≥', r2_min: '≥', vol_max: '≤', drawdown_max: '≤', momentum_min: '≥', ma_below: '<' };
  const GRAN = { day: '1 jour', week: '1 semaine', month: '1 mois', quarter: '3 mois', half: '6 mois', year: '1 an' };
  const GW = { day: 'un jour', week: 'une semaine', month: 'un mois', quarter: 'trois mois', half: 'six mois', year: 'un an' };
  const SEV = { info: 'Information', vigilance: 'Vigilance', goal: 'Objectif atteint', sell: 'Vente à envisager' };
  const STATUS = { official: 'Officielle', adapted: 'Adaptée', personal: 'Personnelle' };
  const TREND = ['slope_min', 'r2_min', 'vol_max', 'drawdown_max', 'momentum_min'];
  const STATE = { normal: ['ok', 'Normale'], triggered: ['ko', 'Déclenchée'], insufficient: ['na', 'Données insuffisantes'], error: ['na', 'Erreur d’évaluation'], none: ['na', 'Vérification en attente'], off: ['off', 'Désactivée'] };
  const EV = { triggered: 'Déclenchée', normal: 'Retour à la normale', insufficient: 'Données insuffisantes', acked: 'Acquittée', rearmed: 'Réarmée' };
  /* protections proposées à l'utilisateur : type, libellé, unité du champ, niveau */
  const CHOICES = [['loss_pct', 'Être averti si je perds X %', '%', 'vigilance'], ['loss_eur', 'Être averti si je perds X €', '€', 'sell'], ['gain_pct_above', 'Être averti si je gagne X %', '%', 'goal'], ['price_below', 'Être averti si le cours passe sous X €', '€', 'sell'], ['price_above', 'Être averti si le cours dépasse X €', '€', 'goal'], ['gain_giveback', 'Être averti si je rends une partie de mes gains', 'points de rendement', 'vigilance'], ['drawdown_from_high', 'Être averti si le cours recule de X % depuis son plus haut', '%', 'vigilance']];
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
      slope_min: ['Tendance sur ' + g, inh ? 'M’avertir si la hausse moyenne devient inférieure au minimum prévu par ma stratégie.' : `M’avertir si la hausse moyenne passe sous ${t} % par séance.`],
      r2_min: ['Régularité sur ' + g, inh ? 'M’avertir si les cours deviennent moins réguliers que le minimum prévu.' : `M’avertir si la régularité (R²) passe sous ${t}.`],
      vol_max: ['Volatilité sur ' + g, inh ? 'M’avertir si le cours devient plus agité que le maximum prévu.' : `M’avertir si la volatilité dépasse ${t} % par séance.`],
      drawdown_max: ['Recul maximal sur ' + g, inh ? 'M’avertir si la plus forte baisse récente dépasse le maximum prévu.' : `M’avertir si la plus forte baisse dépasse ${t} %.`],
      momentum_min: ['Progression sur ' + g, inh ? 'M’avertir si la progression est inférieure au minimum prévu.' : `M’avertir si la progression passe sous ${t} %.`],
      loss_pct: ['Perte de ' + t + ' %', `M’avertir si je perds ${t} % ou plus sur ce titre.`], loss_eur: ['Perte de ' + t + ' €', `M’avertir si je perds ${t} € ou plus sur ce titre.`],
      gain_pct_above: ['Gain de ' + t + ' %', `M’avertir si je gagne ${t} % ou plus sur ce titre.`], gain_eur_above: ['Gain de ' + t + ' €', `M’avertir si je gagne ${t} € ou plus sur ce titre.`],
      price_below: ['Cours sous ' + t + ' €', `M’avertir si le cours passe sous ${t} €.`], price_above: ['Cours au-dessus de ' + t + ' €', `M’avertir si le cours dépasse ${t} €.`], target: ['Objectif de cours : ' + t + ' €', `M’avertir quand le cours atteint ${t} €.`],
      gain_giveback: ['Gains rendus : ' + t + ' points', `M’avertir si mon rendement recule de ${t} points par rapport à son meilleur niveau.`], drawdown_from_high: ['Recul de ' + t + ' % depuis le plus haut', `M’avertir si le cours recule de ${t} % depuis son plus haut depuis mon premier achat.`],
      daily_move: ['Variation d’une séance : ' + t + ' %', `M’avertir si le cours varie de ${t} % ou plus en une séance.`], ma_below: ['Moyenne mobile ' + t + ' séances', `M’avertir si le cours passe sous sa moyenne des ${t} dernières séances.`]
    };
    return T[r.kind] || [label(r), ''];
  }
  const HOW = { slope_min: 'Même calcul que le moteur de la stratégie : progression moyenne du cours par séance sur la durée.', r2_min: 'Proche de 1, la hausse est régulière.', vol_max: 'Écart-type des variations quotidiennes.', drawdown_max: 'Plus forte baisse depuis un sommet sur la durée.', momentum_min: 'Rendement du cours sur la durée.', gain_giveback: 'Rendement actuel sur la ligne comparé à son meilleur niveau atteint.', drawdown_from_high: 'Cours actuel comparé à son plus haut depuis votre premier achat.' };
  const FREQ = k => TREND.includes(k) ? 'une fois par jour de cotation' : 'toutes les 5 minutes (au plus une fois par 10 minutes et par règle)';

  function eventsHtml(es, symbolOf) {
    return es.length ? es.map(e => `<div class="al-ev"><span>${when(e.at)}</span>${symbolOf ? `<b>${esc(symbolOf(e.listing_id))}</b>` : ''}<span class="al-b ${e.event === 'triggered' ? 'ko' : e.event === 'normal' ? 'ok' : 'na'}">${EV[e.event] || esc(e.event)}</span><small>${esc(KIND[e.kind] ? KIND[e.kind][0] : e.kind)}${e.value_obs !== null && e.value_obs !== undefined ? ' · valeur ' + fmt(+e.value_obs) : ''}${e.threshold !== null && e.threshold !== undefined ? ' · seuil ' + fmt(+e.threshold) : ''}${e.message ? ' · ' + esc(e.message) : ''}</small></div>`).join('') : '<p class="muted pad">Aucun événement enregistré.</p>';
  }
  function ruleCard(r) {
    const k = stateOf(r), inh = r.source === 'strategy', custom = inh && r.default_threshold !== null && Math.abs(r.threshold - r.default_threshold) > 2e-6, [title, ask] = words(r);
    const tag = inh ? (custom ? '<span class="al-b pe">Personnalisée</span>' : '<span class="al-b he">Héritée de la stratégie</span>') : '<span class="al-b pe">Personnelle</span>';
    return `<div class="al-r ${r.enabled ? '' : 'dim'}"><div class="ap-rh"><b>${esc(title)}</b> ${tag} ${badge(r)}</div><p class="ap-ask">${esc(ask)}</p>
      <dl class="ap-m"><div><dt>Valeur mesurée</dt><dd>${r.last_value !== null ? fmt(r.last_value) + ' ' + unit(r.kind) : 'pas encore mesurée'}</dd></div><div><dt>Seuil</dt><dd>${OP[r.kind]} ${fmt(r.threshold)} ${unit(r.kind)}${custom ? ` <small>(stratégie : ${fmt(r.default_threshold)})</small>` : ''}</dd></div><div><dt>Dernière vérification</dt><dd>${when(r.last_eval_at)}</dd></div></dl>
      ${r.last_reason && ['insufficient', 'error'].includes(r.state) ? `<p class="small muted">${esc(r.last_reason)}</p>` : ''}
      <div class="al-ra"><button type="button" class="btn small" data-ed="${r.id}">Modifier</button>${r.enabled ? `<button type="button" class="btn small" data-tg="${r.id}" data-on="0">Désactiver</button>` : `<button type="button" class="btn small" data-tg="${r.id}" data-on="1">Réactiver</button>`}${custom ? `<button type="button" class="btn small" data-rs="${r.id}">Revenir à la stratégie</button>` : ''}${k === 'triggered' ? `<button type="button" class="btn small" data-ak="${r.id}">Acquitter</button>` : ''}${r.state === 'triggered' && r.acked_at && r.enabled ? `<button type="button" class="btn small" data-ra="${r.id}">Réarmer</button>` : ''}<button type="button" class="btn small danger" data-dl="${r.id}">Supprimer</button></div>
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

  function render(host, o) {
    const S = o.S, pid = o.pid, p = S.positions.find(x => x.listing_id === o.listing);
    if (!p) { host.innerHTML = '<p class="muted">Sélectionnez une position pour voir sa surveillance.</p>'; return; }
    const rs = S.rules.filter(r => r.listing_id === p.listing_id), inh = rs.filter(r => r.source === 'strategy'), mine = rs.filter(r => r.source !== 'strategy');
    const gs = globalState(rs), last = rs.map(r => r.last_eval_at).filter(Boolean).sort().pop(), oi = originInfo(p), evs = S.events.filter(e => e.listing_id === p.listing_id), log = (p.watch_log || []).slice(0, 4), cur = p.watch ? p.watch.key : '';
    const originHtml = !oi.uniq.length ? 'Non renseignée' : oi.uniq.length === 1 ? esc(oi.uniq[0]) : 'Plusieurs stratégies d’achat';
    host.innerHTML = `<div class="ap">
      <div class="ap-top"><div><small>Stratégie d’origine</small><b>${originHtml}</b>${oi.uniq.length > 1 ? `<details><summary>Voir le détail</summary>${oi.rows.map(r => `<div class="small">${r[0] ? 'Achat du ' + J.date(r[0]) + ' : ' : ''}${esc(r[1])}</div>`).join('')}</details>` : ''}${oi.unknown.length ? '<button type="button" class="btn small" id="ap-setorigin">Renseigner</button>' : ''}</div>
        <div><small>Stratégie de surveillance</small><select id="ap-watch" aria-label="Stratégie de surveillance"><option value="">Aucune</option>${S.strategies.map(s => `<option value="${esc(s.key)}" ${cur === s.key ? 'selected' : ''}>${esc(s.label)}</option>`).join('')}</select><button type="button" class="btn small primary" id="ap-apply" hidden>Appliquer…</button></div>
        <div><small>État de la surveillance</small><span class="al-b ${gs[0]}">${esc(gs[1])}</span><small>Dernière vérification : ${rs.length ? when(last) : '–'}</small></div></div>
      <h4>Ce que Jigobourso surveille pour moi</h4>${inh.map(ruleCard).join('') || `<p class="muted small">${p.watch ? 'Cette stratégie n’a pas de critère de tendance surveillable.' : 'Aucune stratégie de surveillance choisie : choisissez-en une ci-dessus, ses règles viendront de ses vrais paramètres.'}</p>`}
      <h4>Mes protections <button type="button" class="btn small primary" id="ap-add">Ajouter une protection</button></h4>${mine.map(ruleCard).join('') || '<p class="muted small">Aucune protection personnelle. Vous fixez vous-même ce qui vous protège : aucun seuil n’est choisi à votre place.</p>'}
      ${evs.length || log.length ? `<details class="ap-hist"><summary>Historique (${evs.length + log.length})</summary>${eventsHtml(evs.slice(0, 12))}${log.map(l => `<div class="al-ev"><span>${when(l.at)}</span><span class="al-b pe">Stratégie de surveillance</span><small>${esc(l.summary)}</small></div>`).join('')}</details>` : '<p class="small muted">Aucun événement enregistré pour l’instant.</p>'}</div>`;
    const post = async (url, b) => { try { await J.post(url, b); } catch (e) { J.toast(e.message); } }, done = () => o.reload();
    const sel = host.querySelector('#ap-watch'), btn = host.querySelector('#ap-apply'); sel.onchange = () => { btn.hidden = sel.value === cur || !sel.value; };
    btn.onclick = () => strategyChange(o, p, sel.value);
    host.querySelectorAll('[data-tg]').forEach(b => b.onclick = async () => { await post('alerts/rule-toggle', { id: +b.dataset.tg, enabled: b.dataset.on === '1' }); if (b.dataset.on === '1') await post('alerts/refresh', {}); done(); });
    host.querySelectorAll('[data-ed]').forEach(b => b.onclick = () => ruleDialog(o, p, S.rules.find(r => r.id == b.dataset.ed)));
    host.querySelectorAll('[data-rs]').forEach(b => b.onclick = async () => { await post('alerts/rule-restore', { id: +b.dataset.rs }); await post('alerts/refresh', {}); done(); });
    host.querySelectorAll('[data-ak]').forEach(b => b.onclick = async () => { await post('alerts/rule-ack', { id: +b.dataset.ak }); done(); });
    host.querySelectorAll('[data-ra]').forEach(b => b.onclick = async () => { await post('alerts/rule-rearm', { id: +b.dataset.ra }); await post('alerts/refresh', {}); done(); });
    host.querySelectorAll('[data-dl]').forEach(b => b.onclick = async () => { if (await J.confirm('Supprimer l’alerte', 'Cette règle et son historique seront supprimés.', 'Supprimer')) { await post('alerts/rule-delete', { id: +b.dataset.dl }); done(); } });
    host.querySelector('#ap-add').onclick = () => ruleDialog(o, p, null);
    host.querySelector('#ap-setorigin')?.addEventListener('click', () => originDialog(o, p, oi.unknown));
  }

  /** Changement de stratégie de surveillance : aperçu des différences, règles personnelles conservées, rien d'écrit avant confirmation. */
  async function strategyChange(o, p, key) {
    if (!key) return;
    const mode = p.watch ? 'sync' : 'add';
    let d; try { d = await J.post('alerts/apply-template', { portfolio_id: o.pid, listing_id: p.listing_id, strategy: key, mode, dry: true }); } catch (e) { J.toast(e.message); return; }
    const li = r => `<li>${esc(words(Object.assign({ source: 'strategy' }, r))[0])} : ${OP[r.kind]} ${fmt(r.threshold)} ${unit(r.kind)}</li>`, none = !d.available && !d.add.length;
    J.dialog({ title: 'Surveillance : ' + d.strategy_label, body: `${p.watch && p.watch.key !== key ? `<p>Vous passez de <b>${esc(p.watch.label)}</b> à <b>${esc(d.strategy_label)}</b>. La stratégie d’origine des achats ne change pas.</p>` : ''}
      ${none ? '<p>Cette stratégie n’a pas de critère de tendance surveillable : aucune règle ne sera créée. Vos protections personnelles restent intactes.</p>' : ''}
      ${d.add.length ? `<p><b>Règles ajoutées (${d.add.length})</b></p><ul>${d.add.map(li).join('')}</ul>` : ''}
      ${d.update.length ? `<p><b>Seuils mis à jour (${d.update.length})</b></p><ul>${d.update.map(u => `<li>${esc(KIND[u.kind][0])}${u.granularity ? ' · ' + GRAN[u.granularity] : ''} : ${fmt(u.from)} → ${fmt(u.to)} ${unit(u.kind)}</li>`).join('')}</ul>` : ''}
      ${d.keep.length ? `<p><b>Vos seuils modifiés sont conservés (${d.keep.length})</b></p><ul>${d.keep.map(u => `<li>${esc(KIND[u.kind][0])}${u.granularity ? ' · ' + GRAN[u.granularity] : ''} : votre ${fmt(u.threshold)} (stratégie : ${fmt(u.strategy_threshold)})</li>`).join('')}</ul>` : ''}
      ${!d.add.length && !d.update.length && !d.keep.length && !none ? '<p>Rien à modifier : les règles sont déjà à jour.</p>' : ''}<p class="small muted">${d.personal_kept} protection(s) personnelle(s) conservée(s). Rien n’est supprimé. Le changement est inscrit à l’historique.</p>`,
      actions: [{ label: 'Annuler', run: () => { o.reload(); } }, { label: 'Confirmer', cls: 'primary', run: async () => { try { await J.post('alerts/apply-template', { portfolio_id: o.pid, listing_id: p.listing_id, strategy: key, mode }); await J.post('alerts/refresh', {}); } catch (e) { J.toast(e.message); } await o.reload(); } }] });
  }

  /** Ajouter une protection (choix en français, champ, unité, valeur actuelle, phrase de confirmation) ou modifier une règle. */
  function ruleDialog(o, p, r) {
    const c = o.cur || {}, px = c.price != null ? 'Cours actuel : ' + J.num(c.price, 2) + ' ' + (c.currency || '') : '', gp = c.gainPct != null ? 'Rendement actuel : ' + J.num(c.gainPct, 2) + ' %' : '', ge = c.gainEur != null ? 'Résultat actuel : ' + J.num(c.gainEur, 2) + ' €' : '';
    const curTxt = k => ({ price_below: px, price_above: px, target: px, loss_pct: gp, gain_pct_above: gp, gain_giveback: gp, loss_eur: ge, gain_eur_above: ge })[k] || '';
    const ch = r ? [CHOICES.find(x => x[0] === r.kind) || [r.kind, '', unit(r.kind), r.severity]] : CHOICES;
    J.dialog({ title: r ? 'Modifier : ' + words(r)[0] : 'Ajouter une protection · ' + p.symbol, body: `${r ? '' : `<div class="ap-choices" role="radiogroup" aria-label="Type de protection">${ch.map((x, i) => `<label class="ap-ch"><input type="radio" name="apc" value="${x[0]}" ${i === 0 ? 'checked' : ''}> ${esc(x[1])}</label>`).join('')}</div>`}
      ${r && TREND.includes(r.kind) ? `<p class="small muted">Durée de mesure : ${GRAN[r.granularity]} (non modifiable). Modifier ce seuil n’altère jamais la stratégie officielle.</p>` : ''}
      ${J.field('Seuil', `<input id="ar-t" inputmode="decimal" value="${r ? r.threshold : ''}" placeholder="À vous de choisir">`)}<p class="small muted" id="ar-u"></p><p id="ar-sum" class="ar-sum" aria-live="polite"></p>`,
      onopen: d => {
        const q = i => d.querySelector(i), kind = () => r ? r.kind : q('input[name=apc]:checked').value, sync = () => {
          const k = kind(), cc = CHOICES.find(x => x[0] === k), t = q('#ar-t').value.trim().replace(',', '.');
          q('#ar-u').textContent = 'Unité : ' + ((cc && cc[2]) || unit(k) || 'sans unité') + (curTxt(k) ? ' · ' + curTxt(k) : '') + '.';
          q('#ar-sum').textContent = t ? words({ kind: k, threshold: t, granularity: r && r.granularity, source: r ? r.source : 'personal' })[1].replace('M’avertir', 'Vous serez averti') : '';
        };
        d.querySelectorAll('input[name=apc]').forEach(i => i.onchange = sync); q('#ar-t').oninput = sync; sync();
      },
      actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async d => {
        const t = d.querySelector('#ar-t').value.trim().replace(',', '.'), k = r ? r.kind : d.querySelector('input[name=apc]:checked').value, cc = CHOICES.find(x => x[0] === k);
        try { await J.post('alerts/rule-save', { id: r ? r.id : undefined, portfolio_id: o.pid, listing_id: p.listing_id, kind: k, granularity: r ? r.granularity : undefined, threshold: t, severity: r ? r.severity : (cc ? cc[3] : 'vigilance'), enabled: r ? !!r.enabled : true }); } catch (e) { J.formError(d, e.message); return true; }
        await J.post('alerts/refresh', {}); await o.reload();
      } }] });
  }
  function originDialog(o, p, lots) {
    J.dialog({ title: 'Stratégie d’origine · ' + p.symbol, body: `<p class="small muted">Indiquez la stratégie réellement utilisée pour cet achat. Elle n’est jamais devinée ; une fois enregistrée à l’achat, elle ne se modifie plus.</p>${J.field('Achat', `<select id="so-tx">${lots.map(l => `<option value="${l.tx}">Achat du ${J.date(l.date)}</option>`).join('')}</select>`)}${J.field('Stratégie', `<select id="so-st">${o.S.strategies.map(s => `<option value="${esc(s.key)}">${esc(s.label)} — ${STATUS[s.status] || ''}</option>`).join('')}</select>`)}`,
      actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async d => { try { await J.post('alerts/origin', { tx_id: +d.querySelector('#so-tx').value, strategy: d.querySelector('#so-st').value }); } catch (e) { J.formError(d, e.message); return true; } await o.reload(); } }] });
  }
  root.AlertPanel = { render, ruleDialog, originDialog, eventsHtml, stateOf, badge, label, fmt, when, words, globalState, KIND, OP, GRAN, SEV, STATUS, STATE };
})(window);
