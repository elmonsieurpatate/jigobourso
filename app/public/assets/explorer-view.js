/* Classement : constructeurs de HTML purs (aucun accès à la page ni à l'état) — réglages Simple, éditeur de règles Expert, filtres secondaires, cellules du tableau.
   Chargé après explorer-model.js et avant explorer.js, qui les place dans le DOM. */
window.ExplorerView = (() => {
  'use strict';
  const { periods, metrics } = window.ExplorerModel, esc = J.esc, fmt = n => J.num(n, 2, 3);

  // Illustration du critère de la période choisie (pente + R², ou variation du dernier jour).
  function chartSvg(p, selected) {
    if (selected === 'day') return `<svg viewBox="0 0 240 110" role="img" aria-label="Illustration : variation de la dernière séance clôturée d’au moins ${fmt(p.return)} pour cent"><path d="M10 95H230M10 95V10" fill="none" stroke="var(--line)"/><polyline points="60,70 180,${70 - Math.max(-30, Math.min(30, p.return * 4))}" fill="none" stroke="var(--accent)" stroke-width="2"/><circle cx="60" cy="70" r="3.5" fill="var(--accent)"/><circle cx="180" cy="${70 - Math.max(-30, Math.min(30, p.return * 4))}" r="3.5" fill="var(--accent)"/></svg>`;
    const slope = p.slope / 2, spread = (1 - p.r2) * 28, jitter = [0, 1, -.7, .8, -1, .4, -.6, .3, 0];
    const pts = jitter.map((j, i) => [15 + i * 25, 86 - i * (2 + slope * 7) + j * spread]);
    return `<svg viewBox="0 0 240 110" role="img" aria-label="Illustration : pente ${fmt(p.slope)} pour cent par séance, R² ${fmt(p.r2)}"><path d="M10 95H230M10 95V10" fill="none" stroke="var(--line)"/><path d="M15 86L215 ${86 - 8 * (2 + slope * 7)}" stroke="var(--accent)" stroke-width="2" stroke-dasharray="4 4"/><polyline points="${pts.map(p => p.join(',')).join(' ')}" fill="none" stroke="var(--accent)" stroke-width="2"/>${pts.map(([x, y]) => `<circle cx="${x}" cy="${y}" r="3.5" fill="var(--accent)"/>`).join('')}</svg>`;
  }
  // Résumé lisible de l'arbre de règles.
  function previewHtml(n) {
    if (n.kind === 'rule') return `<span>${n.metric === 'return' && n.period === 'day' ? 'Variation 1J' : metrics[n.metric][0]} ${esc(n.op)} ${fmt(n.value)} ${metrics[n.metric][1]} <em>(${periods.find(([k]) => k === n.period)[1]})</em></span>`;
    return `<div class="ct-preview-group"><b>${n.join === 'and' ? 'TOUTES (ET)' : 'AU MOINS UNE (OU)'}</b>${n.children.map(x => `<div>${previewHtml(x)}</div>`).join('') || '<span>Aucun critère</span>'}</div>`;
  }
  // Mode Simple : une carte par période, puis les curseurs de la période choisie.
  const periodsHtml = (c, selected) => periods.map(([k, label, n]) => `<div class="ct-period ${c.periods[k].enabled ? 'active' : ''} ${selected === k ? 'selected' : ''}"><button type="button" data-period="${k}" aria-pressed="${selected === k}">${label}<small>≈ ${n} séance${n > 1 ? 's' : ''}</small></button><label><input type="checkbox" data-enabled="${k}" ${c.periods[k].enabled ? 'checked' : ''}>Activée</label></div>`).join('');
  const SLIDERS_DAY = [['return', 'Variation 1J minimale', -20, 20, .1, '%', 'Variation du cours entre les deux dernières séances clôturées. Une seule séance : ni pente ni R². À 0 : le dernier jour doit être positif. Masque seulement des lignes : notes et rangs ne changent pas.']];
  const SLIDERS = [['slope', 'Pente minimale', 0, 2, .001, '% / séance', 'Progression moyenne modélisée par séance. À 0 : aucun seuil. Masque seulement des lignes : notes et rangs ne changent pas.'], ['r2', 'R² minimal', 0, 1, .001, '', 'Régularité : de 0 (dispersé) à 1 (aligné).']];
  const slidersHtml = (p, selected) => (selected === 'day' ? SLIDERS_DAY : SLIDERS).map(([id, label, min, max, step, unit, help]) => `<div class="ct-control"><label for="ct-range-${id}">${label} · ${periods.find(([k]) => k === selected)[1]}</label><div class="ct-slider-row"><button type="button" class="btn icon sm" data-step="${id}" data-delta="-${step}" aria-label="Diminuer ${label}">−</button><input id="ct-range-${id}" type="range" data-simple="${id}" min="${min}" max="${max}" step="${step}" value="${p[id]}" aria-label="${label}"><button type="button" class="btn icon sm" data-step="${id}" data-delta="${step}" aria-label="Augmenter ${label}">+</button><div class="ct-number"><input id="ct-value-${id}" type="number" data-simple="${id}" min="${min}" max="${max}" step="${step}" value="${p[id]}" aria-label="Valeur ${label}"><span>${unit}</span></div></div><p class="ct-control-help">${help}</p></div>`).join('');
  // Mode Expert : l'arbre de règles (ET / OU) sous forme de formulaire.
  function rulesHtml(n, path = [], depth = 0) {
    const p = path.join('.');
    if (n.kind === 'rule') return `<div class="ct-builder-row" data-path="${p}">
        <select data-rule-field="metric" aria-label="Indicateur ${p}">${Object.entries(metrics).map(([k, [l]]) => `<option value="${k}" ${n.metric === k ? 'selected' : ''}>${l}</option>`).join('')}</select>
        <select data-rule-field="op" aria-label="Opérateur ${p}">${[['>=', '≥'], ['<=', '≤'], ['>', '>'], ['<', '<'], ['=', '=']].map(([v, l]) => `<option value="${esc(v)}" ${n.op === v ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>
        <input type="number" step="any" value="${Number(n.value.toFixed(3))}" data-rule-field="value" aria-label="Valeur ${p}">
        <select data-rule-field="period" aria-label="Période ${p}">${periods.filter(([k]) => k !== 'day' || n.metric === 'return').map(([k, l, count]) => `<option value="${k}" ${n.period === k ? 'selected' : ''}>sur ${l.toLowerCase()} (≈ ${count} s.)</option>`).join('')}</select>
        <button type="button" class="ct-rule-remove" data-remove-node="${p}" aria-label="Supprimer le critère ${p}">×</button>
      </div>`;
    return `<div class="ct-builder-group ${depth ? 'nested' : ''}" data-group-path="${p}"><div class="ct-group-operator"><select data-group-join="${p}" aria-label="Combinaison ${depth ? 'du groupe ' + p : 'principale'}"><option value="and" ${n.join === 'and' ? 'selected' : ''}>ET</option><option value="or" ${n.join === 'or' ? 'selected' : ''}>OU</option></select></div><div class="ct-group-content">${n.children.map((x, i) => rulesHtml(x, [...path, i], depth + 1)).join('') || '<p class="ct-no-rules">Aucun critère dans ce groupe.</p>'}<div class="ct-group-actions"><button type="button" data-add-node="${p}">＋ Ajouter un critère</button>${depth < 4 ? `<button type="button" data-add-group="${p}">＋ Groupe ET / OU</button>` : ''}${depth ? `<button type="button" data-remove-node="${p}" class="ct-delete-group">Supprimer le groupe</button>` : ''}</div></div></div>`;
  }
  // Filtres secondaires : un menu à cases par indicateur ; les principaux d'abord, les autres repliés.
  const drawIndicator = (k, c, selected, active, query) => `<div class="ct-multi" data-indicator="${k}"><button type="button" class="ct-multi-trigger" data-open-filter="${k}" title="${esc(c.label)} · ${esc(c.unit)}" aria-expanded="${active === k}" aria-controls="ct-list-${k}"><span>${esc(c.label)}</span><b data-count="${k}">${selected[k].length} / ${c.options.length}</b><span aria-hidden="true">⌄</span></button><div class="ct-multi-popup" id="ct-list-${k}" ${active === k ? '' : 'hidden'}><label class="ct-category-search"><span aria-hidden="true">⌕</span><input type="search" data-category-search="${k}" placeholder="Rechercher une catégorie…" aria-label="Rechercher une catégorie : ${esc(c.label)}" value="${active === k ? esc(query) : ''}"></label><div class="ct-category-options" role="group" aria-label="Catégories : ${esc(c.label)}">${c.options.map(o => `<label class="ct-category-option" data-search-text="${esc(J.fold(o.label))}"><input type="checkbox" data-filter="${k}" data-category="${o.id}" ${selected[k].includes(o.id) ? 'checked' : ''}><i data-style="background:${o.color}" aria-hidden="true"></i><span>${esc(o.label)}</span><small>${esc(o.range)}</small></label>`).join('')}</div><p class="ct-no-category" hidden>Aucune catégorie correspondante.</p><footer><span data-selected-count="${k}">${selected[k].length} / ${c.options.length} sélectionnées</span><button type="button" data-all-indicator="${k}">Tout sélectionner</button><button type="button" data-close-filter="${k}" aria-label="Fermer ${esc(c.label)}">Fermer</button></footer></div></div>`;
  const LEGACY_PRIMARY = ['volatility', 'turnover_eur', 'avg_volume', 'drawdown', 'up_fraction', 'gain_share'];
  const isPrimaryFilter = (schema, k, c) => schema === 2 ? c.group === 'main' : LEGACY_PRIMARY.includes(k);
  function filtersHtml(categories, schema, selected, active, query) {
    const entries = Object.entries(categories), primary = entries.filter(([k, c]) => isPrimaryFilter(schema, k, c)), other = entries.filter(([k, c]) => !isPrimaryFilter(schema, k, c));
    const draw = ([k, c]) => drawIndicator(k, c, selected, active, query);
    return entries.length ? `<div class="ct-filter-main">${primary.map(draw).join('')}</div>${other.length ? `<details class="ct-more-filters"><summary>Autres indicateurs (${other.length}) <span id="ct-more-count"></span></summary><div class="ct-filter-main">${other.map(draw).join('')}</div></details>` : ''}` : '<p>Aucun filtre actif. Réactivez-les depuis « Mes filtres ».</p>';
  }
  // Tableau : statut de stratégie et courbe de tendance d'une ligne.
  const STATUS = { retained:['Retenue', 'ok'], excluded:['Exclue', 'no'], undetermined:['Indéterminée', 'na'] };
  const statusBadge = row => { const [t, c] = STATUS[row.status] || STATUS.undetermined; return `<i class="ct-status ${c}" title="Statut de la stratégie : ${t.toLowerCase()}. Détail dans la fiche du titre.">${t}</i>`; };
  function spark(row) {
    if (row.curveLoading) return '<span class="ct-missing">Chargement…</span>';
    if (!row.points.length) return '<span class="ct-missing">Indisponible</span>';
    const lo = Math.min(...row.points), hi = Math.max(...row.points), span = hi - lo || 1;
    const pts = row.points.map((v, i) => [4 + i * 96 / Math.max(1, row.points.length - 1), 25 - (v - lo) * 21 / span]);
    const up = row.points[row.points.length - 1] >= row.points[0];
    return `<svg class="ct-mini-curve ${up ? 'positive' : 'negative'}" viewBox="0 0 104 30" role="img" aria-label="Clôtures des 21 dernières séances : ${up ? 'hausse' : 'baisse'}"><polyline points="${pts.map(p => p.map(n => n.toFixed(1)).join(',')).join(' ')}"/><circle cx="${pts.at(-1)[0]}" cy="${pts.at(-1)[1]}" r="2"/></svg>`;
  }
  return { chartSvg, previewHtml, periodsHtml, slidersHtml, rulesHtml, filtersHtml, isPrimaryFilter, statusBadge, spark };
})();
