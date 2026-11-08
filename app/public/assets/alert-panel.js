/* Panneau de surveillance d'une position, partagé par le détail du Portefeuille et le Centre d'alertes.
   AlertPanel.render(host, {S: état alerts/state, pid, listing, reload}) : en-tête (stratégie d'origine / de surveillance / état),
   A règles de la stratégie, B protection de l'investissement, C compléments de marché, D historique. Une alerte informe, elle ne vend jamais. */
(function (root) {
  'use strict';
  const KIND = { price_below: ['Cours inférieur à', '€'], price_above: ['Cours supérieur à', '€'], target: ['Objectif de cours', '€'], gain_pct_above: ['Gain personnel', '%'], loss_pct: ['Perte personnelle', '%'], gain_eur_above: ['Gain personnel', '€'], loss_eur: ['Perte personnelle', '€'], drawdown_from_high: ['Recul depuis le plus haut cours', '%'], gain_giveback: ['Gain rendu depuis le meilleur résultat', 'pts'], daily_move: ['Variation sur une séance', '%'], slope_min: ['Pente minimale', '%/séance'], r2_min: ['Régularité minimale (R²)', ''], vol_max: ['Volatilité maximale', '%/séance'], drawdown_max: ['Recul maximal', '%'], momentum_min: ['Progression minimale', '%'], ma_below: ['Cours sous la moyenne mobile', 'séances'] };
  const OP = { price_below: '<', price_above: '>', target: '≥', gain_pct_above: '≥', loss_pct: '≥', gain_eur_above: '≥', loss_eur: '≥', drawdown_from_high: '≥', gain_giveback: '≥', daily_move: '≥', slope_min: '≥', r2_min: '≥', vol_max: '≤', drawdown_max: '≤', momentum_min: '≥', ma_below: '<' };
  const GRAN = { day: '1 jour', week: '1 semaine', month: '1 mois', quarter: '3 mois', half: '6 mois', year: '1 an' };
  const SEV = { info: 'Information', vigilance: 'Vigilance', goal: 'Objectif atteint', sell: 'Vente à envisager' };
  const STATUS = { official: 'Officielle', adapted: 'Adaptée', personal: 'Personnelle' };
  const TREND = ['slope_min', 'r2_min', 'vol_max', 'drawdown_max', 'momentum_min'];
  const STATE = { normal: ['ok', 'Normale'], triggered: ['ko', 'Déclenchée'], insufficient: ['na', 'Données insuffisantes'], error: ['na', 'Erreur d’évaluation'], none: ['na', 'Pas encore évaluée'], off: ['off', 'Désactivée'] };
  const EV = { triggered: 'Déclenchée', normal: 'Retour à la normale', insufficient: 'Données insuffisantes', acked: 'Acquittée', rearmed: 'Réarmée' };
  const CATS = { cours: ['Cours', ['price_below', 'price_above', 'target', 'daily_move', 'ma_below'], 'Le prix du titre franchit un niveau.'], invest: ['Mon investissement', ['loss_pct', 'loss_eur', 'gain_pct_above', 'gain_eur_above', 'drawdown_from_high', 'gain_giveback'], 'Votre gain ou votre perte sur cette ligne, et la protection de vos gains.'], trend: ['Tendance', TREND, 'La qualité de la hausse : pente, régularité, volatilité, recul, progression.'], score: ['Scores et stratégie', [], 'Appliquer le modèle d’une stratégie (règles reprises de ses vrais paramètres).'] };
  const PROTECT = ['price_below', 'loss_pct', 'loss_eur', 'drawdown_from_high', 'gain_giveback'];
  const esc = s => J.esc(String(s == null ? '' : s));
  const fmt = v => v === null || v === undefined ? '–' : J.num(v, Number.isInteger(+v) ? 0 : Math.abs(v) < 1 ? 4 : 2);
  const when = d => d ? J.dateTime(String(d).replace(' ', 'T')) : '–';
  const stateOf = r => !r.enabled ? 'off' : r.state === null ? 'none' : (r.state === 'triggered' && r.acked_at ? 'acked' : r.state);
  const badge = r => { const k = stateOf(r); if (k === 'acked') return '<span class="al-b ko">Déclenchée · acquittée</span>'; const [c, l] = STATE[k]; return `<span class="al-b ${c}">${l}</span>`; };
  const label = r => (KIND[r.kind] || [r.kind])[0] + (r.granularity ? ' · ' + GRAN[r.granularity] : '');
  const unit = k => (KIND[k] || [0, ''])[1];
  /** Phrase claire de la condition. */
  function explain(r) {
    const t = r.threshold === null || r.threshold === '' || r.threshold === undefined ? '…' : fmt(+r.threshold), g = r.granularity ? GRAN[r.granularity] : '';
    return ({
      price_below: `le cours passe sous ${t} €`, price_above: `le cours dépasse ${t} €`, target: `le cours atteint votre objectif de ${t} €`,
      gain_pct_above: `votre gain sur cette ligne atteint ${t} %`, loss_pct: `votre perte sur cette ligne atteint ${t} % du capital engagé`, gain_eur_above: `votre gain sur cette ligne atteint ${t} €`, loss_eur: `votre perte sur cette ligne atteint ${t} €`,
      drawdown_from_high: `le cours recule d’au moins ${t} % depuis son plus haut cours observé depuis votre premier achat`, gain_giveback: `vous avez rendu au moins ${t} points de rendement par rapport à votre meilleur rendement atteint sur cette ligne`,
      daily_move: `le cours varie d’au moins ${t} % en une séance`, ma_below: `le cours passe sous sa moyenne mobile de ${t} séances`,
      slope_min: `la pente moyenne du cours sur ${g || 'la durée choisie'} tombe sous ${t} % par séance (vitesse de progression)`, r2_min: `la régularité de la hausse (R²) sur ${g || 'la durée choisie'} tombe sous ${t}`,
      vol_max: `la volatilité sur ${g || 'la durée choisie'} dépasse ${t} % par séance`, drawdown_max: `le recul maximal sur ${g || 'la durée choisie'} dépasse ${t} %`, momentum_min: `la progression sur ${g || 'la durée choisie'} tombe sous ${t} %`
    })[r.kind] || '';
  }
  const HOW = {
    drawdown_from_high: 'Mécanisme 1 — protection du prix : compare le cours actuel à son plus haut depuis votre premier achat. Il ne dépend ni de vos quantités ni de vos achats ultérieurs.',
    gain_giveback: 'Mécanisme 2 — protection de votre gain : compare votre rendement actuel sur la ligne à son meilleur niveau atteint. Les achats et ventes sont pris en compte dans le calcul du rendement du capital engagé.',
    slope_min: 'Régression linéaire du logarithme du cours : la pente est la progression moyenne par séance. Même calcul que le moteur de la stratégie.', r2_min: 'Part de la hausse expliquée par une droite : proche de 1, la montée est régulière.', vol_max: 'Écart-type des variations quotidiennes sur la durée.', drawdown_max: 'Plus forte baisse depuis un sommet sur la durée.', momentum_min: 'Rendement du cours sur la durée de mesure.',
    price_below: 'Compare chaque cours enregistré au niveau choisi.', price_above: 'Compare chaque cours enregistré au niveau choisi.', target: 'Votre objectif de cours : alerte à l’atteinte.', daily_move: 'Variation du dernier cours par rapport à la clôture précédente.', ma_below: 'Moyenne simple des dernières clôtures.',
    gain_pct_above: 'Gain latent plus réalisé sur la ligne, rapporté au capital engagé.', loss_pct: 'Perte sur la ligne rapportée au capital engagé.', gain_eur_above: 'Gain en euros sur la ligne.', loss_eur: 'Perte en euros sur la ligne.'
  };
  const EVALFREQ = k => TREND.includes(k) ? 'une fois par jour de cotation (la tendance se mesure sur des clôtures)' : 'à chaque passage automatique (toutes les 5 minutes, limité à une évaluation par 10 minutes et par règle)';

  function eventsHtml(es, symbolOf) {
    return es.length ? es.map(e => `<div class="al-ev"><span>${when(e.at)}</span>${symbolOf ? `<b>${esc(symbolOf(e.listing_id))}</b>` : ''}<span class="al-b ${e.event === 'triggered' ? 'ko' : e.event === 'normal' ? 'ok' : 'na'}">${EV[e.event] || esc(e.event)}</span><small>${esc(KIND[e.kind] ? KIND[e.kind][0] : e.kind)}${e.value_obs !== null && e.value_obs !== undefined ? ' · valeur ' + fmt(+e.value_obs) : ''}${e.threshold !== null && e.threshold !== undefined ? ' · seuil ' + fmt(+e.threshold) : ''}${e.message ? ' · ' + esc(e.message) : ''}</small></div>`).join('') : '<p class="muted pad">Aucun événement pour le moment. Les événements apparaissent à partir de la première évaluation : rien n’est reconstitué rétroactivement.</p>';
  }
  function ruleLine(r) {
    const k = stateOf(r), inh = r.source === 'strategy', custom = inh && r.default_threshold !== null && Math.abs(r.threshold - r.default_threshold) > 1e-9;
    const tag = inh ? (custom ? '<span class="al-b pe">Personnalisée</span>' : '<span class="al-b he">Héritée</span>') : r.source === 'legacy' ? '<span class="al-b he">Stop / objectif</span>' : '<span class="al-b pe">Personnelle</span>';
    return `<div class="al-r ${r.enabled ? '' : 'dim'}"><label class="sw"><input type="checkbox" data-tg="${r.id}" ${r.enabled ? 'checked' : ''} aria-label="Activer ${esc(label(r))}"><i></i></label>
      <div class="al-rt"><b>${esc(label(r))}</b> ${tag}<small>Alerte si ${esc(explain(r))}.</small><small>${badge(r)} Mesuré : <b>${r.last_value !== null ? fmt(r.last_value) : '–'}</b> · Seuil : <b>${OP[r.kind]} ${fmt(r.threshold)} ${unit(r.kind)}</b>${custom ? ` <em>(stratégie : ${fmt(r.default_threshold)})</em>` : ''} · ${SEV[r.severity]} · Évaluée : ${when(r.last_eval_at)}</small>
      <details class="al-cmp"><summary>Comprendre</summary><p>${esc(HOW[r.kind] || '')}</p><p>Évaluation : ${EVALFREQ(r.kind)}.</p>${r.last_reason ? `<p>Dernier constat : ${esc(r.last_reason)}</p>` : ''}${r.triggered_at ? `<p>Déclenchée le ${when(r.triggered_at)}${r.acked_at ? ', acquittée le ' + when(r.acked_at) + ' (la condition peut persister)' : ''}.</p>` : ''}${custom ? '<p>Seuil modifié par vous ; la valeur de la stratégie est conservée pour le bouton ↺.</p>' : ''}</details></div>
      <div class="al-ra"><button type="button" class="btn small" data-ed="${r.id}" aria-label="Modifier">✎ Modifier</button>${custom ? `<button type="button" class="btn small" data-rs="${r.id}" title="Restaurer la valeur de la stratégie">↺ Restaurer</button>` : ''}${k === 'triggered' ? `<button type="button" class="btn small" data-ak="${r.id}">Acquitter</button>` : ''}${(r.state === 'triggered' && r.acked_at) || k === 'off' ? '' : `<button type="button" class="btn small" data-ra="${r.id}" title="Réarmer : réévaluer comme neuve">⟳ Réarmer</button>`}<button type="button" class="btn small danger" data-dl="${r.id}" aria-label="Supprimer">✕</button></div></div>`;
  }

  function render(host, o) {
    const S = o.S, pid = o.pid, p = S.positions.find(x => x.listing_id === o.listing);
    if (!p) { host.innerHTML = '<p class="muted">Sélectionnez une position pour configurer sa surveillance.</p>'; return; }
    const rs = S.rules.filter(r => r.listing_id === p.listing_id), A = rs.filter(r => r.source === 'strategy'), pers = rs.filter(r => r.source !== 'strategy'), B = pers.filter(r => PROTECT.includes(r.kind)), Cc = pers.filter(r => !PROTECT.includes(r.kind));
    const on = rs.filter(r => r.enabled), trig = on.filter(r => r.state === 'triggered' && !r.acked_at).length, bad = on.filter(r => ['insufficient', 'error'].includes(r.state)).length, lastEval = rs.map(r => r.last_eval_at).filter(Boolean).sort().pop();
    const global = !rs.length ? ['none', 'Sans surveillance'] : !on.length ? ['off', 'Désactivée'] : trig ? ['ko', trig + ' déclenchée' + (trig > 1 ? 's' : '')] : bad ? ['na', 'Données insuffisantes'] : on.every(r => r.state === null) ? ['na', 'Pas encore évaluée'] : ['ok', 'Normale'];
    const origins = p.origins.filter(o2 => o2.strategy), legacy = p.lot_strategies, unknown = p.origins.filter(o2 => !o2.strategy && !p.lot_strategies.some(l => l.tx === o2.tx));
    const oTxt = origins.length ? [...new Set(origins.map(o2 => o2.label + ' — ' + (STATUS[o2.status] || '')))].map(esc).join('<br>') : legacy.length ? [...new Set(legacy.map(l => l.label))].map(esc).join('<br>') + ' <small>(renseignée manuellement)</small>' : 'Stratégie d’origine non renseignée';
    const log = (p.watch_log || []).slice(0, 4);
    host.innerHTML = `<div class="ap">
      <div class="ap-head"><div><small>Stratégie d’origine <span class="muted">(historique, non modifiable)</span></small><b>${oTxt}</b>${unknown.length ? '<button type="button" class="btn small" id="ap-setorigin">Renseigner</button>' : ''}</div>
        <div><small>Stratégie de surveillance <span class="muted">(modifiable)</span></small><select id="ap-watch" aria-label="Stratégie de surveillance"><option value="">Choisir…</option>${S.strategies.map(s => `<option value="${esc(s.key)}" ${p.watch && p.watch.key === s.key ? 'selected' : ''}>${esc(s.label)} — ${STATUS[s.status] || ''}</option>`).join('')}</select><div class="row"><button type="button" class="btn small primary" id="ap-apply">${p.watch ? 'Changer / mettre à jour…' : 'Appliquer le modèle…'}</button></div></div>
        <div><small>État global</small><span class="al-b ${global[0]}">${global[1]}</span><small>Dernière évaluation : ${when(lastEval)}</small></div></div>
      <h4>A · Règles de la stratégie <small>(${A.length})</small></h4>${A.map(ruleLine).join('') || '<p class="muted small">Aucune règle héritée. Choisissez une stratégie de surveillance : ses règles sont créées à partir de ses vrais paramètres, sans valeur imposée.</p>'}
      <h4>B · Protection de l’investissement <small>(${B.length})</small> <button type="button" class="btn small primary" data-new="invest">＋ Ajouter</button></h4>${B.map(ruleLine).join('') || '<p class="muted small">Aucune protection. Aucun seuil n’est choisi à votre place : vous fixez vous-même ce qui vous protège.</p>'}
      <h4>C · Compléments de marché <small>(${Cc.length})</small> <button type="button" class="btn small" data-new="cours">＋ Ajouter</button></h4>${Cc.map(ruleLine).join('') || '<p class="muted small">Aucune règle complémentaire (objectifs, variation brutale, moyenne mobile…).</p>'}
      <h4>D · Historique</h4><div class="al-evs">${eventsHtml(S.events.filter(e => e.listing_id === p.listing_id).slice(0, 12))}${log.length ? log.map(l => `<div class="al-ev"><span>${when(l.at)}</span><span class="al-b pe">Stratégie de surveillance</span><small>${esc(l.summary)}</small></div>`).join('') : ''}</div></div>`;
    const post = async (url, b) => { try { await J.post(url, b); } catch (e) { J.toast(e.message); } };
    const done = async () => { await o.reload(); };
    host.querySelectorAll('[data-tg]').forEach(i => i.onchange = async () => { await post('alerts/rule-toggle', { id: +i.dataset.tg, enabled: i.checked }); done(); });
    host.querySelectorAll('[data-ed]').forEach(b => b.onclick = () => ruleDialog(o, p, S.rules.find(r => r.id == b.dataset.ed)));
    host.querySelectorAll('[data-rs]').forEach(b => b.onclick = async () => { await post('alerts/rule-restore', { id: +b.dataset.rs }); done(); });
    host.querySelectorAll('[data-ak]').forEach(b => b.onclick = async () => { await post('alerts/rule-ack', { id: +b.dataset.ak }); done(); });
    host.querySelectorAll('[data-ra]').forEach(b => b.onclick = async () => { await post('alerts/rule-rearm', { id: +b.dataset.ra }); await post('alerts/refresh', {}); done(); });
    host.querySelectorAll('[data-dl]').forEach(b => b.onclick = async () => { if (await J.confirm('Supprimer l’alerte', 'Cette règle et son historique seront supprimés.', 'Supprimer')) { await post('alerts/rule-delete', { id: +b.dataset.dl }); done(); } });
    host.querySelectorAll('[data-new]').forEach(b => b.onclick = () => ruleDialog(o, p, null, b.dataset.new));
    host.querySelector('#ap-apply').onclick = () => strategyChange(o, p, host.querySelector('#ap-watch').value);
    host.querySelector('#ap-setorigin')?.addEventListener('click', () => originDialog(o, p, unknown));
  }

  /** Changement de stratégie de surveillance : aperçu des différences avant toute écriture, règles personnelles conservées. */
  async function strategyChange(o, p, key) {
    if (!key) { J.toast('Choisissez une stratégie'); return; }
    const mode = p.watch ? 'sync' : 'add';
    let d; try { d = await J.post('alerts/apply-template', { portfolio_id: o.pid, listing_id: p.listing_id, strategy: key, mode, dry: true }); } catch (e) { J.toast(e.message); return; }
    const li = (r, extra) => `<li>${esc(label(r))} : ${OP[r.kind]} ${fmt(r.threshold)} ${unit(r.kind)}${extra || ''}</li>`;
    const none = !d.available && !d.add.length;
    J.dialog({ title: 'Surveillance : ' + d.strategy_label, body: `${p.watch && p.watch.key !== key ? `<p>Vous passez de <b>${esc(p.watch.label)}</b> à <b>${esc(d.strategy_label)}</b>. La stratégie d’origine des achats ne change pas.</p>` : ''}
      ${none ? '<p class="notice">Cette stratégie n’a pas de critère de tendance surveillable : aucune règle ne sera créée. Vos règles personnelles restent intactes.</p>' : ''}
      ${d.add.length ? `<h4>Règles ajoutées (${d.add.length})</h4><ul>${d.add.map(r => li(r)).join('')}</ul>` : ''}
      ${d.update.length ? `<h4>Seuils mis à jour (${d.update.length})</h4><ul>${d.update.map(u => `<li>${esc(KIND[u.kind][0])}${u.granularity ? ' · ' + GRAN[u.granularity] : ''} : ${fmt(u.from)} → ${fmt(u.to)} ${unit(u.kind)}</li>`).join('')}</ul>` : ''}
      ${d.keep.length ? `<h4>Seuils que vous avez modifiés : conservés (${d.keep.length})</h4><ul>${d.keep.map(u => `<li>${esc(KIND[u.kind][0])}${u.granularity ? ' · ' + GRAN[u.granularity] : ''} : votre ${fmt(u.threshold)} (stratégie : ${fmt(u.strategy_threshold)}) ${unit(u.kind)}</li>`).join('')}</ul>` : ''}
      <p class="small muted">${d.personal_kept} règle(s) personnelle(s) conservée(s). Aucune règle n’est supprimée. L’opération est inscrite à l’historique.</p>${!d.add.length && !d.update.length && !d.keep.length && !none ? '<p>Rien à modifier : les règles sont déjà à jour.</p>' : ''}`,
      actions: [{ label: 'Annuler', run: () => { } }, { label: 'Confirmer', cls: 'primary', run: async () => { try { const r = await J.post('alerts/apply-template', { portfolio_id: o.pid, listing_id: p.listing_id, strategy: key, mode }); await J.post('alerts/refresh', {}); J.toast(r.added + ' ajoutée(s), ' + r.updated + ' mise(s) à jour, ' + r.kept + ' conservée(s)'); } catch (e) { J.toast(e.message); } await o.reload(); } }] });
  }

  /** Création / modification : catégorie, type, seuil, phrase de synthèse. */
  function ruleDialog(o, p, r, cat) {
    const catOf = k => Object.keys(CATS).find(c => CATS[c][1].includes(k)) || 'cours';
    let c = r ? catOf(r.kind) : (cat || 'invest');
    J.dialog({ title: r ? 'Modifier l’alerte' : 'Nouvelle alerte · ' + p.symbol, body: `<div id="ar-cat" class="ar-cats" role="group" aria-label="Catégorie">${Object.entries(CATS).map(([k, v]) => `<button type="button" class="btn small ${k === c ? 'primary' : ''}" data-c="${k}" ${r ? 'disabled' : ''}>${v[0]}</button>`).join('')}</div><p class="small muted" id="ar-cd"></p>
      <div id="ar-form">${J.field('Type', '<select id="ar-k"></select>')}<div id="ar-g">${J.field('Durée de mesure', `<select id="ar-gr">${Object.entries(GRAN).map(([k, l]) => `<option value="${k}" ${r && r.granularity === k ? 'selected' : ''}>${l}</option>`).join('')}</select>`)}</div>${J.field('Seuil', `<input id="ar-t" inputmode="decimal" value="${r ? r.threshold : ''}" placeholder="À vous de choisir">`)}${J.field('Niveau', `<select id="ar-s">${Object.entries(SEV).map(([k, l]) => `<option value="${k}" ${(r ? r.severity : 'vigilance') === k ? 'selected' : ''}>${l}</option>`).join('')}</select>`)}</div>
      <div id="ar-score" hidden><p>Les alertes sur un score ou un verdict ne sont pas encore évaluables automatiquement : elles ne sont pas proposées pour ne pas afficher une surveillance qui ne fonctionnerait pas.</p><p>Vous pouvez en revanche appliquer le modèle d’une stratégie : ses critères de tendance deviennent des règles.</p></div>
      <p class="small muted" id="ar-u"></p><p id="ar-sum" class="ar-sum" aria-live="polite"></p><p id="ar-how" class="small muted"></p>`,
      onopen: d => {
        const q = i => d.querySelector(i), sync = () => {
          const kinds = CATS[c][1], isScore = c === 'score'; q('#ar-form').hidden = isScore; q('#ar-score').hidden = !isScore; q('#ar-cd').textContent = CATS[c][2];
          if (!isScore) { const cur = r ? r.kind : q('#ar-k').value; q('#ar-k').innerHTML = kinds.map(k => `<option value="${k}" ${k === cur ? 'selected' : ''}>${KIND[k][0]}${KIND[k][1] ? ' (' + KIND[k][1] + ')' : ''}</option>`).join(''); q('#ar-k').disabled = !!r; }
          const k = q('#ar-k').value; q('#ar-g').hidden = isScore || !TREND.includes(k); q('#ar-u').textContent = isScore ? '' : 'Unité du seuil : ' + (unit(k) || 'sans unité') + '.';
          const rr = { kind: k, threshold: q('#ar-t').value.trim().replace(',', '.'), granularity: q('#ar-gr').value };
          q('#ar-sum').textContent = isScore ? '' : 'Vous serez alerté si ' + explain(rr) + '.'; q('#ar-how').textContent = isScore ? '' : (HOW[k] || '') + (PROTECT.includes(k) ? ' Le seuil est le vôtre : aucune valeur n’est suggérée par défaut.' : '');
        };
        d.querySelectorAll('[data-c]').forEach(b => b.onclick = () => { c = b.dataset.c; d.querySelectorAll('[data-c]').forEach(x => x.classList.toggle('primary', x === b)); q('#ar-k').innerHTML = ''; sync(); });
        ['#ar-k', '#ar-gr', '#ar-t'].forEach(i => { q(i).onchange = sync; q(i).oninput = sync; }); sync();
      },
      actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async d => {
        if (c === 'score') return true;
        const v = i => d.querySelector(i).value.trim().replace(',', '.');
        try { await J.post('alerts/rule-save', { id: r ? r.id : undefined, portfolio_id: o.pid, listing_id: p.listing_id, kind: r ? r.kind : v('#ar-k'), granularity: v('#ar-gr'), threshold: v('#ar-t'), severity: v('#ar-s'), enabled: r ? !!r.enabled : true }); } catch (e) { J.formError(d, e.message); return true; }
        await J.post('alerts/refresh', {}); await o.reload();
      } }] });
  }
  function originDialog(o, p, lots) {
    J.dialog({ title: 'Stratégie d’origine · ' + p.symbol, body: `<p class="small muted">Indiquez la stratégie réellement utilisée pour ces achats. Elle n’est jamais devinée ; une fois enregistrée à l’achat, elle ne se modifie plus.</p>${J.field('Achat', `<select id="so-tx">${lots.map(l => `<option value="${l.tx}">Achat du ${J.date(l.date)}</option>`).join('')}</select>`)}${J.field('Stratégie', `<select id="so-st">${o.S.strategies.map(s => `<option value="${esc(s.key)}">${esc(s.label)} — ${STATUS[s.status] || ''}</option>`).join('')}</select>`)}`,
      actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async d => { try { await J.post('alerts/origin', { tx_id: +d.querySelector('#so-tx').value, strategy: d.querySelector('#so-st').value }); } catch (e) { J.formError(d, e.message); return true; } await o.reload(); } }] });
  }
  root.AlertPanel = { render, ruleDialog, originDialog, eventsHtml, ruleLine, explain, stateOf, badge, label, fmt, when, KIND, OP, GRAN, SEV, STATUS, STATE, TREND, CATS };
})(window);
