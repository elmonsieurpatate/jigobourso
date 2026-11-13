/* Classement : logique pure (sans DOM, sans réseau) — profils de stratégie, arbre de règles, filtres secondaires, lignes du tableau.
   Chargé avant explorer.js ; testé sous Node par tests/e2e/explorer-model.cjs. L'état de la page reste dans explorer.js. */
window.ExplorerModel = (() => {
  'use strict';
  const periods = [['day','Jour',1],['week','Semaine',5],['month','Mois',21],['quarter','Trimestre',63],['half','6 mois',126],['year','1 an',252],['two_year','2 ans',504]];
  const metrics = { slope:['Pente (% / séance)','% / séance'], r2:['R² (régression)',''], volatility:['Volatilité quotidienne','%'], drawdown:['Recul maximal','%'], return:['Rendement observé','%'], volume:['Volume moyen','titres / séance'] };
  const builtinNames = { fast:'Croissance rapide', regular:'Croissance régulière', calm:'Hausse calme', rebound:'Rebond', mom6:'Momentum 6 mois (expérimental)', mom12:'Momentum 12 mois (expérimental)', momrisk:'Momentum ajusté du risque (expérimental)' };
  const FALLBACK = { fast:['week','month'], regular:['month','quarter'], calm:['month','quarter'], rebound:['week','month','half'], mom6:['quarter','half'], mom12:['half','year'], momrisk:['half','year'] };
  const SESS = { week:'5', month:'21', quarter:'63', half:'126', year:'252' };
  const cloneJSON = x => JSON.parse(JSON.stringify(x));

  // ───── Profils : critères de RECHERCHE de chaque stratégie intégrée, lus dans le moteur (ranking/criteria) ─────
  const profilesFrom = crit => Object.fromEntries(Object.keys(FALLBACK).map(id => {
    const src = (crit[id] && crit[id].periods) || Object.fromEntries(FALLBACK[id].map(k => [k, {}])), per = {}, extra = [];
    for (const [k, t] of Object.entries(src)) {
      if (t.slope !== undefined || t.r2 !== undefined || !Object.keys(t).length) per[k] = [t.slope || 0, t.r2 || 0];
      if (t.max_volatility !== undefined && !extra.some(x => x[0] === 'volatility')) extra.push(['volatility', '<=', t.max_volatility, 'month']);
      if (t.max_drawdown !== undefined && !extra.some(x => x[0] === 'drawdown')) extra.push(['drawdown', '<=', t.max_drawdown, 'month']);
      if (t.max_return !== undefined) extra.push(['return', '<=', t.max_return, k]);
      if (t.min_return !== undefined) extra.push(['return', '>=', t.min_return, k]);
    }
    for (const k of Object.keys(src)) if (!per[k]) per[k] = [0, 0];                     // période active sans pente ni R² (ex. contexte du Rebond)
    return [id, { per, extra }];
  }));
  // Jour (1 séance) : facultatif et désactivé par défaut ; seule la variation 1J sert de critère. Les configurations enregistrées avant son ajout n'ont pas cette entrée.
  const DAY_OFF = { enabled:false, slope:0, r2:0, return:0 };
  const withDay = c => { if (c && c.periods) { if (!c.periods.day) c.periods.day = { ...DAY_OFF }; if (c.periods.day.return == null) c.periods.day.return = 0; } return c; };
  const fresh = (profiles, id) => { const pr = profiles[id], first = Object.values(pr.per)[0];
    return { periods:Object.fromEntries(periods.map(([k]) => { const v = pr.per[k]; if (k === 'day') return [k, { ...DAY_OFF }]; return [k, { enabled:!!v, slope:v ? v[0] : first[0], r2:v ? v[1] : first[1] }]; })),
      extra:(pr.extra || []).map(([metric, op, value, period]) => ({ metric, op, value, period:period || 'month' })), join:'and' }; };
  // Une sauvegarde locale n'est reprise que si elle est complète et dans les bornes (sinon : valeurs d'origine).
  const isValidSaved = (saved, profiles) => !!(saved && ['simple','expert'].includes(saved.mode) && profiles[saved.strategy] && periods.some(([k]) => k === saved.selected) && Object.keys(profiles).every(id => {
    const p = saved.profiles?.[id]; return p && ['and','or'].includes(p.join) && Array.isArray(p.extra) && p.extra.every(x => metrics[x.metric] && ['>=','<='].includes(x.op) && Number.isFinite(x.value) && x.value >= 0)
      && periods.every(([k]) => k === 'day' || typeof p.periods?.[k]?.enabled === 'boolean' && Number.isFinite(p.periods[k].slope) && p.periods[k].slope >= .01 && p.periods[k].slope <= 2 && Number.isFinite(p.periods[k].r2) && p.periods[k].r2 >= 0 && p.periods[k].r2 <= 1);
  }) && saved.filters && typeof saved.filters === 'object');
  // Un choix enregistré garde ses identifiants ; seules les catégories apparues depuis suivent les défauts de l'administration.
  const filtersFor = (o, categories, adminSelections) => Object.fromEntries(Object.entries(categories).map(([k, c]) => {
    const own = o[k], all = c.options.map(x => x.id); if (!own) return [k, adminSelections[k]];
    const selected = new Set(own.selected.filter(id => all.includes(id)));
    if (own.selected.length && !selected.size) return [k, [...adminSelections[k]]];
    for (const id of adminSelections[k]) if (!own.known.includes(id)) selected.add(id);
    return [k, [...selected]];
  }));
  const number = (value, min, max, fallback) => { if (String(value).trim() === '') return fallback; const n = Number(String(value).replace(',', '.')); return Number.isFinite(n) ? Math.max(min, Math.min(max, n)) : fallback; };

  // ───── Arbre de règles (mode Expert) et sa projection sur les curseurs du mode Simple ─────
  const isPrimary = r => r.metric === 'slope' || r.metric === 'r2' || (r.metric === 'return' && r.period === 'day');
  const rule = (metric, period, value, op = '>=') => ({ kind:'rule', metric, period, value, op });
  const group = (children = [], join = 'and') => ({ kind:'group', join, children });
  function validTree(n, depth = 0) {
    if (!n || depth > 6) return false;
    if (n.kind === 'group') return ['and','or'].includes(n.join) && Array.isArray(n.children) && n.children.length <= 50 && n.children.every(x => validTree(x, depth + 1));
    return n.kind === 'rule' && metrics[n.metric] && ['>=','<=','>','<','='].includes(n.op) && periods.some(([k]) => k === n.period) && Number.isFinite(n.value);
  }
  function ensureTree(c) {
    if (!c.tree || !validTree(c.tree) || c.tree.kind !== 'group') {
      c.tree = group(periods.filter(([k]) => c.periods[k].enabled).flatMap(([k]) => k === 'day' ? [rule('return', 'day', c.periods.day.return)] : ['slope','r2'].map(m => rule(m, k, c.periods[k][m]))));
      if (c.extra.length) c.tree.children.push(group(c.extra.map(x => rule(x.metric, x.period || 'month', x.value, x.op)), c.join));
    }
    return c.tree;
  }
  function leaves(n, path = [], joins = []) {
    if (n.kind === 'rule') return [{ node:n, path, joins }];
    return n.children.flatMap((x, i) => leaves(x, [...path, i], [...joins, n.join]));
  }
  const at = (tree, path) => path === '' ? tree : path.split('.').reduce((n, i) => n.children[Number(i)], tree);
  function project(c) {
    const rules = leaves(ensureTree(c)).map(x => x.node);
    periods.forEach(([k]) => {
      const p = c.periods[k], own = rules.filter(r => isPrimary(r) && r.period === k);
      p.enabled = own.length > 0;
      ['slope','r2','return'].forEach(m => { const r = own.find(r => r.metric === m && r.op === '>='); if (r) p[m] = r.value; });
    });
  }
  function simpleCompatible(c) {
    const all = leaves(ensureTree(c)).filter(x => isPrimary(x.node));
    return all.every(({ node:r, joins }) => r.op === '>=' && joins.every(j => j === 'and') && (r.metric === 'return' ? r.value >= -20 && r.value <= 20 : r.value >= 0 && r.value <= (r.metric === 'slope' ? 2 : 1))) && periods.every(([k]) => {
      const own = all.filter(x => x.node.period === k); return !own.length || (k === 'day' ? own.length === 1 : own.length === 2 && new Set(own.map(x => x.node.metric)).size === 2);
    });
  }
  function setSimpleValue(c, selected, metric, value) {
    c.periods[selected][metric] = value;
    leaves(ensureTree(c)).filter(x => x.node.metric === metric && x.node.period === selected && x.node.op === '>=').forEach(x => x.node.value = value);
  }
  function activatePeriod(c, k, enabled) {
    function remove(n) { if (n.kind === 'group') { n.children = n.children.filter(x => !(x.kind === 'rule' && isPrimary(x) && x.period === k)); n.children.forEach(remove); } }
    const t = ensureTree(c); remove(t);
    if (enabled) (k === 'day' ? ['return'] : ['slope','r2']).forEach(m => t.children.push(rule(m, k, c.periods[k][m])));
    project(c);
  }
  // Un filtre est complet quand il a au moins une règle, aucun groupe vide et des valeurs dans leurs bornes.
  function isTreeValid(tree) {
    const hasEmpty = n => n.kind === 'group' && (!n.children.length || n.children.some(hasEmpty)), l = leaves(tree);
    return l.length > 0 && !hasEmpty(tree) && l.every(({ node:r }) => Number.isFinite(r.value) && (r.metric !== 'r2' || (r.value >= 0 && r.value <= 1)) && (!['volatility','drawdown','volume'].includes(r.metric) || r.value >= 0));
  }

  // ───── Catégories de l'administration (couleur d'un chiffre, appartenance d'une ligne à un filtre) ─────
  function categories(defs) {
    const measureOf = Object.create(null);
    for (const f of defs) for (const m of f.measures || []) measureOf[m.id] = m;
    const inside = (c, v) => (c.min === null || v > c.min || (v === c.min && c.minIncluded)) && (c.max === null || v < c.max || (v === c.max && c.maxIncluded));
    function categoryOf(measureId, value) {
      const m = measureOf[measureId]; if (!m) return null;
      const unknown = m.categories.find(c => c.unknown) || null;
      if (value === null || value === undefined || Number.isNaN(value)) return unknown;
      if (m.kind === 'enum') return m.categories.find(c => !c.unknown && (c.values || []).includes(String(value))) || unknown;
      return m.categories.find(c => !c.unknown && inside(c, value)) || unknown;
    }
    // Une ligne appartient à une catégorie par mesure (filtres à seuils) ou par groupe (pays, secteur, place, type) ; mémorisé sur la ligne.
    function rowOptions(row, k) {
      row._o = row._o || {};
      if (row._o[k]) return row._o[k];
      const f = defs.find(x => x.id === k); let out = [];
      if (f && f.editable) out = (f.measures || []).map(m => { const c = categoryOf(m.id, row.secondary[m.id]); return c ? m.id + '::' + c.id : null; }).filter(Boolean);
      else if (f) out = [row.group && row.group[k] || 'unknown'];
      return row._o[k] = out;
    }
    return { categoryOf, rowOptions };
  }

  // ───── Lignes du tableau : réponse du serveur → ligne d'affichage ─────
  const hue = s => { let h = 0; for (const ch of s) h = (h * 31 + ch.charCodeAt(0)) % 360; return `hsl(${h} 45% 42%)`; };
  const ctxKey = s => { let h = 0; for (const c of s) h = (h * 31 + c.charCodeAt(0)) | 0; return (h >>> 0).toString(36); };
  // Valeurs des mesures de filtres : reconstituées depuis les champs de la ligne (une valeur absente reste null, jamais 0).
  function secondaryOf(r) {
    const x = r.extra || {}, perf = r.perf || {};
    return { volatility:r.volatility, turnover_eur:r.turnover_eur, avg_volume:r.avg_volume, up_fraction:x.up_fraction ?? null, gain_share:x.gain_share ?? null, drawdown:r.drawdown,
      'perf-week':perf.week ?? null, 'perf-month':perf.month ?? null, 'perf-quarter':perf.quarter ?? null, quality:x.quality ?? null, freshness:null, coverage:x.coverage ?? null,
      score_simple_v4:r.simple, score_complex_v4:r.complex };
  }
  function toRow(r) {
    return { id:r.id, rank:r.rank_complex, rankSimple:r.rank_simple, rankComplex:r.rank_complex, posSimple:r.pos_simple, posComplex:r.pos_complex, tieSimple:r.tie_simple || 1, tieComplex:r.tie_complex || 1, symbol:r.symbol, name:r.name, mic:r.mic, currency:r.currency, kind:r.kind, country:r.country, category:r.category, group:r.group,
      price:r.price_eur, priceNative:r.price, change:r.change, slope:r.slope, r2:r.r2, volatility:r.volatility, drawdown:r.drawdown, turnover:r.turnover_eur, liquiditySource:r.liquidity_source, avgVolume:r.avg_volume,
      perf:r.perf || {}, perfMonth:r.perf && r.perf.month !== undefined ? r.perf.month : null, simple:r.simple, complex:r.complex, simpleStatus:r.simple_status, complexStatus:r.complex_status, score:r.complex,
      isin:r.isin, points:r.curve || [], color:hue(r.symbol), secondary:secondaryOf(r), periods:r.periods || {}, held:!!r.held, lastClose:r.last_close, quality:r.quality, status:r.status || 'undetermined' };
  }
  // Colonnes triables : identifiant → valeur de tri. `rankKey()` donne la clé du rang affiché (score simple ou complexe).
  const STATUS_ORDER = { retained:0, undetermined:1, excluded:2 };
  function registry(rankKey) {
    const REG = { rank:{ val:r => r[rankKey()], dir:'asc' }, name:{ val:r => r.name, dir:'asc' }, status:{ val:r => STATUS_ORDER[r.status] ?? 1, dir:'asc' }, market:{ val:r => r.mic, dir:'asc' }, sector:{ val:r => r.category, dir:'asc' }, kind:{ val:r => r.kind, dir:'asc' },
      price:{ val:r => r.price }, change:{ val:r => r.change }, last_close:{ val:r => r.lastClose }, slope:{ val:r => r.slope }, r2:{ val:r => r.r2 }, volatility:{ val:r => r.volatility }, turnover:{ val:r => r.turnover }, avgVolume:{ val:r => r.avgVolume }, drawdown:{ val:r => r.drawdown }, perfMonth:{ val:r => r.perfMonth },
      simple:{ val:r => r.posSimple == null ? null : -r.posSimple }, complex:{ val:r => r.posComplex == null ? null : -r.posComplex }, rank_simple:{ val:r => r.rankSimple, dir:'asc' }, rank_complex:{ val:r => r.rankComplex, dir:'asc' }, trend:{ val:() => null, nosort:true } };
    for (const k of ['week','quarter','half']) REG['perf_' + k] = { val:r => (r.perf || {})[k] };
    for (const k of ['week','quarter','half','year']) { REG['slope_' + k] = { val:r => (r.periods[SESS[k]] || {}).slope }; REG['r2_' + k] = { val:r => (r.periods[SESS[k]] || {}).r2 }; }
    return REG;
  }

  return { periods, metrics, builtinNames, SESS, cloneJSON, profilesFrom, DAY_OFF, withDay, fresh, isValidSaved, filtersFor, number,
    isPrimary, rule, group, validTree, ensureTree, leaves, at, project, simpleCompatible, setSimpleValue, activatePeriod, isTreeValid,
    categories, hue, ctxKey, secondaryOf, toRow, registry };
})();
