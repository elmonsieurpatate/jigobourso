/* Page Explorer : stratégie réglable, filtres avancés, tableau triable, comparaison actions / ETF, statistiques d'exclusion, export CSV. */
(async () => {
  const user = await J.init('explorer'); if (!user) return;
  const [P, ov] = await Promise.all([J.api('strategy/presets'), J.api('data/overview').catch(() => null)]);
  const NAMES = { regular: ['Croissance régulière', 'Une hausse soutenue et bien alignée, sur un mois et trois mois.'], fast: ['Croissance rapide', 'Une hausse marquée sur la semaine et le mois, même irrégulière.'],
    recovery: ['Rebond', 'Repart à la hausse après six mois sans progrès notable.'], low_volatility: ['Hausse calme', 'Une hausse douce avec peu de variations et de replis.'] };
  const CRIT = { min_slope: 'pente insuffisante', min_r2: 'régularité insuffisante', min_er: 'efficacité insuffisante', min_return: 'performance trop faible', max_return: 'performance trop forte',
    max_volatility: 'volatilité trop forte', max_drawdown: 'repli trop fort', data: 'historique insuffisant ou rupture de cours', freshness: 'cours non à jour',
    above_ma50: 'cours sous la moyenne 50 j', ma50_rising: 'moyenne 50 j orientée à la baisse', max_daily_change: 'variation du jour trop forte', max_gap_ma20: 'écart à la moyenne 20 j trop grand' };
  const LEVELS = { regularity: [['ok', 'Régulière'], ['warn', 'Moyennement régulière'], ['bad', 'Irrégulière'], ['unknown', 'Inconnue']],
    risk: [['ok', 'Volatilité faible'], ['warn', 'Volatilité modérée'], ['bad', 'Volatilité forte'], ['unknown', 'Inconnue']],
    liquidity: [['ok', 'Facilement négociable'], ['warn', 'À surveiller'], ['bad', 'Limitée'], ['unknown', 'Non déterminée']] };
  const FILTERS = ['country', 'category', 'regularity', 'risk', 'liquidity', 'budget', 'min_price', 'min_score', 'max_volatility', 'max_drawdown', 'min_volume'];
  const CHECKS = ['pea', 'mine', 'open_now', 'fresh_only'];
  const MARKETS = { XETR: 'Xetra', XPAR: 'Paris', XAMS: 'Amsterdam', XLON: 'Londres', XMIL: 'Milan', XMAD: 'Madrid', XSTO: 'Stockholm', XOSL: 'Oslo', XSWX: 'Zurich', XNAS: 'Nasdaq', XNYS: 'NYSE', XASE: 'NYSE American', ARCX: 'NYSE Arca', BATS: 'Cboe' };
  const url = new URLSearchParams(location.search);
  const saved = (() => { try { return JSON.parse(sessionStorage.getItem('jigo_explorer2')) || JSON.parse(localStorage.getItem('jigo_explorer2')) || {}; } catch (e) { return {}; } })();
  const S = { preset: saved.preset || 'regular', label: saved.label || null, config: saved.config || P.presets[saved.preset || 'regular'], status: saved.status || 'retained', page: saved.page || 1, sort: saved.sort || 'rank', dir: saved.dir || 'asc', size: saved.size || 20, level: saved.level || 'guided', compare: !!saved.compare };
  const el = id => J.$('#' + id);
  const text = ['q', 'kind', 'market', ...FILTERS];
  text.forEach(k => { const v = k === 'q' ? (url.has('q') && saved.pageKey !== location.pathname + location.search ? url.get('q') : (saved.view || {}).q) : (saved.view || {})[k]; if (v !== undefined && v !== null && el(k)) el(k).value = v; });
  CHECKS.forEach(k => { if (el(k) && (saved.view || {})[k]) el(k).checked = true; });
  if ((saved.view || {}).tradable === false) el('tradable').checked = false;         // activé par défaut ; seul un choix explicite de le désactiver est conservé
  const MS = { country: JMulti(el('country')), category: JMulti(el('category')), regularity: JMulti(el('regularity')), risk: JMulti(el('risk')), liquidity: JMulti(el('liquidity')) };
  Object.keys(LEVELS).forEach(k => MS[k].set(LEVELS[k].map(([v, l]) => [v, l, ''])));
  ['country', 'category', ...Object.keys(LEVELS)].forEach(k => { const v = (saved.view || {})[k]; if (v) el(k).value = v; });
  let timer, seq = 0, lastRes = null;

  /* bandeau de sources */
  function drawSources() {
    if (!ov) { el('sources').innerHTML = '<span>Catalogue : <b>FinanceDatabase</b></span><span>Cours : <b>Yahoo Finance</b></span>'; return; }
    const latest = ov.places.map(p => p.last_close).filter(Boolean).sort().pop(), stale = ov.places.reduce((a, p) => a + p.stale, 0), ok = ov.places.reduce((a, p) => a + p.ok, 0), tot = ov.places.reduce((a, p) => a + p.followed, 0);
    el('sources').innerHTML = `<span>Catalogue : <b>FinanceDatabase</b> · chargé le ${J.date(ov.catalogue.loaded_at)}</span><span>Cours : <b>Yahoo Finance</b> · dernière clôture ${J.date(latest)}</span>
      <span><i class="dot ${stale ? 'stale' : ''}"></i>${J.num(ok, 0)} séries sur ${J.num(tot, 0)} à jour${stale ? ' · ' + stale + ' en retard' : ''}</span><span>Univers : <b>${J.num(ov.catalogue.recommendable, 0)}</b> titres analysés</span><a href="donnees.html" style="margin-left:auto">Détail des données →</a>`;
  }

  function freeConfig() { const c = JSON.parse(JSON.stringify(P.presets.regular)); c.name = 'free'; c.periods.forEach(p => { p.enabled = p.id === 'month'; ['min_slope', 'min_r2', 'min_er', 'min_return', 'max_return', 'max_volatility', 'max_drawdown'].forEach(f => p[f] = null); }); c.ranking.mode = 'trend'; return c; }
  function drawStrategies() {
    el('strats').innerHTML = Object.keys(P.presets).map(k => `<button class="strat ${S.preset === k ? 'on' : ''}" data-k="${k}"><b>${NAMES[k][0]}</b><span>${NAMES[k][1]}</span></button>`).join('') +
      `<button class="strat ${S.preset === 'free' ? 'on' : ''}" data-k="free"><b>Recherche libre</b><span>Aucun critère de départ : seuls vos filtres et vos réglages décident.</span></button>` +
      (S.preset === 'custom' ? `<button class="strat on"><b>Vos réglages${S.label ? ' · ' + J.esc(S.label) : ''}</b><span>Les critères ci-dessous sont appliqués tels quels, sans passer par un profil.</span></button>` : '');
    J.$$('#strats .strat[data-k]').forEach(b => b.onclick = () => { S.label = null; S.preset = b.dataset.k; S.config = S.preset === 'free' ? freeConfig() : JSON.parse(JSON.stringify(P.presets[S.preset])); S.page = 1; persist(); drawStrategies(); drawEditor(); load(); });
    const act = S.config.periods.filter(p => p.enabled).map(p => J.PERIODS[p.id].toLowerCase() + ' (' + p.sessions + ' séances)');
    el('strategy-summary').textContent = 'Périodes : ' + act.join(', ') + ' · classement par ' + ({ trend: 'pente', performance: 'performance', regularity: 'régularité', stability: 'stabilité' }[S.config.ranking.mode]);
  }
  function view() {
    const v = { q: el('q').value.trim(), kind: el('kind').value, market: el('market').value };
    FILTERS.forEach(k => { v[k] = el(k).value.trim(); });
    CHECKS.forEach(k => { v[k === 'mine' ? 'owned_only' : k] = el(k).checked; });
    v.tradable = el('tradable').checked;
    return v;
  }
  addEventListener('pagehide', () => { persist(); try { sessionStorage.setItem('jigo_explorer_scroll', String(scrollY)); } catch (e) {} });
  function persist() { try { localStorage.setItem('jigo_explorer2', JSON.stringify({ pageKey: location.pathname + location.search, preset: S.preset, config: S.config, status: S.status, page: S.page, level: S.level, compare: S.compare, sort: S.sort, dir: S.dir, size: S.size, view: { ...view(), mine: el('mine').checked }, label: S.label || null })); sessionStorage.setItem('jigo_explorer2', localStorage.getItem('jigo_explorer2')); } catch (e) { } }

  /* éditeur : réglages guidés + détaillé */
  const levelOpts = (obj, labels, cur) => Object.entries(labels).map(([k, l]) => `<option value="${k}" ${k === cur ? 'selected' : ''}>${l}</option>`).join('');
  function guessLevel(map, value, none = '') { if (value === null || value === undefined) return none; const best = Object.entries(map).filter(([, v]) => v !== null).sort((a, b) => Math.abs(a[1] - value) - Math.abs(b[1] - value))[0]; return best && Math.abs(best[1] - value) < 0.02 * Math.max(1, Math.abs(value)) ? best[0] : 'custom'; }
  function drawEditor() {
    const c = S.config, box = el('editor'), act = c.periods.filter(p => p.enabled), p0 = act[0] || c.periods[0];
    const sl = guessLevel(P.slope_levels, p0.min_slope, 'none'), rl = guessLevel(Object.fromEntries(Object.entries(P.r2_levels)), p0.min_r2, 'none'), dd = p0.max_drawdown === null ? '' : String(p0.max_drawdown);
    const num = (p, f, step) => `<input type="number" step="${step}" value="${p[f] ?? ''}" data-p="${p.id}" data-f="${f}" style="width:100px" placeholder="–">`;
    box.innerHTML = `<div class="row between"><h2 style="margin:0">Régler la stratégie</h2><span class="seg" id="lvl"><button data-l="guided" class="${S.level === 'guided' ? 'on' : ''}">Réglages guidés</button><button data-l="detail" class="${S.level === 'detail' ? 'on' : ''}">Réglage détaillé</button></span></div>
    <p class="muted small" style="margin:6px 0 12px">Un titre est retenu s’il respecte tous les critères de toutes les périodes cochées. Case vide = pas de critère. Pente = hausse moyenne par séance ; R² = régularité de la hausse (1 = droite parfaite).</p>
    <div class="row" style="gap:18px;margin-bottom:10px">${c.periods.map(p => `<label class="row gap-s small"><input type="checkbox" ${p.enabled ? 'checked' : ''} data-p="${p.id}" data-f="enabled"> ${J.PERIODS[p.id]} <input type="number" min="2" max="252" value="${p.sessions}" data-p="${p.id}" data-f="sessions" style="width:60px" ${p.id === 'day' ? 'disabled' : ''}> <span class="muted">séances</span></label>`).join('')}</div>
    <div id="guided" ${S.level === 'guided' ? '' : 'hidden'}><div class="filters" style="border:0;background:none;padding:0">
      <label>Pente exigée<select id="g-slope"><option value="none">Aucune</option>${Object.entries({ gentle: 'Douce (doublement en ~8 ans)', moderate: 'Modérée (~4 ans)', strong: 'Forte (~2 ans)', very_strong: 'Très forte (~1 an)' }).map(([k, l]) => `<option value="${k}" ${k === sl ? 'selected' : ''}>${l}</option>`).join('')}${sl === 'custom' ? '<option value="custom" selected>Personnalisée</option>' : ''}</select></label>
      <label>Régularité exigée<select id="g-r2"><option value="none">Aucune</option>${Object.entries({ flexible: 'Souple (R² ≥ 0,56)', balanced: 'Équilibrée (R² ≥ 0,75)', strict: 'Stricte (R² ≥ 0,89)' }).map(([k, l]) => `<option value="${k}" ${k === rl ? 'selected' : ''}>${l}</option>`).join('')}${rl === 'custom' ? '<option value="custom" selected>Personnalisée</option>' : ''}</select></label>
      <label>Tolérance aux corrections<select id="g-dd">${[['', 'Aucune limite'], ['5', 'Repli max. 5 %'], ['10', 'Repli max. 10 %'], ['20', 'Repli max. 20 %']].map(([v, l]) => `<option value="${v}" ${v === dd ? 'selected' : ''}>${l}</option>`).join('')}</select></label>
      <label>Classer par<select id="r-mode">${[['trend', 'Pente'], ['performance', 'Performance'], ['regularity', 'Régularité'], ['stability', 'Stabilité (faible volatilité)']].map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select></label></div>
      <p class="muted small" style="margin:8px 0 0">Ces réglages s’appliquent à chaque période cochée. Pour un réglage différent par période, passez au réglage détaillé.</p></div>
    <div id="detail" ${S.level === 'detail' ? '' : 'hidden'}><div class="table-wrap"><table><thead><tr><th>Période</th><th class="num">Pente min. (%/séance)</th><th class="num">R² min.</th><th class="num">ER min.</th><th class="num">Perf. min. (%)</th><th class="num">Perf. max. (%)</th><th class="num">Volat. max.</th><th class="num">Repli max. (%)</th><th class="num">Poids</th></tr></thead><tbody>
    ${c.periods.map(p => `<tr><td>${J.PERIODS[p.id]}</td><td class="num">${num(p, 'min_slope', .01)}</td><td class="num">${num(p, 'min_r2', .01)}</td><td class="num">${num(p, 'min_er', .01)}</td><td class="num">${num(p, 'min_return', 1)}</td><td class="num">${num(p, 'max_return', 1)}</td><td class="num">${num(p, 'max_volatility', .1)}</td><td class="num">${num(p, 'max_drawdown', 1)}</td><td class="num"><input type="number" min="0" step=".5" data-w="${p.id}" value="${(c.ranking.weights || {})[p.id] ?? 1}" style="width:64px"></td></tr>`).join('')}</tbody></table></div>
    <div class="row" style="margin-top:12px"><label class="row gap-s small"><input type="checkbox" id="t-ma50" ${c.technical.above_ma50 ? 'checked' : ''}> Cours au-dessus de la moyenne 50 j</label>
      <label class="row gap-s small"><input type="checkbox" id="t-ma50r" ${c.technical.ma50_rising ? 'checked' : ''}> Moyenne 50 j en hausse</label>
      <label class="row gap-s small">Variation du jour max. (%) <input type="number" id="t-day" value="${c.technical.max_daily_change ?? ''}" style="width:70px"></label>
      <label class="row gap-s small">Écart moy. 20 j max. (%) <input type="number" id="t-gap" value="${c.technical.max_gap_ma20 ?? ''}" style="width:70px"></label>
      <label class="row gap-s small">Classer par <select id="r-mode2">${[['trend', 'Pente'], ['performance', 'Performance'], ['regularity', 'Régularité'], ['stability', 'Stabilité']].map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select></label></div></div>
    <div id="editor-msg" class="notice err" hidden style="margin-top:10px"></div>
    <div class="row" style="margin-top:12px"><button class="btn primary" id="apply">Appliquer</button><select id="save-to" aria-label="Portefeuille"><option value="">Enregistrer pour un portefeuille…</option></select><button class="btn" id="save-btn">Enregistrer</button></div>`;
    J.$('#r-mode', box).value = c.ranking.mode; J.$('#r-mode2', box).value = c.ranking.mode;
    ['#g-slope', '#g-r2', '#g-dd'].forEach(id => { const e = J.$(id, box); e.dataset.init = e.value; });
    J.$$('#lvl button', box).forEach(b => b.onclick = () => { S.level = b.dataset.l; drawEditor(); });
    J.$('#apply', box).onclick = readEditor;
    J.api('portfolios').then(r => { const sel = J.$('#save-to', box); r.portfolios.forEach(p => sel.insertAdjacentHTML('beforeend', `<option value="${p.id}">${J.esc(p.name)}</option>`)); });
    J.$('#save-btn', box).onclick = async () => { const id = J.$('#save-to', box).value; if (!id) return; if (await readEditor()) { await J.post('portfolio/strategy', { id: +id, config: S.config }); J.toast('Stratégie enregistrée pour ce portefeuille'); } };
  }
  async function readEditor() {
    const box = el('editor'), c = JSON.parse(JSON.stringify(S.config)), v = x => x === '' || x === null ? null : Number(x);
    J.$$('[data-p]', box).forEach(i => { const p = c.periods.find(x => x.id === i.dataset.p); if (i.dataset.f === 'enabled') p.enabled = i.checked; else if (i.dataset.f === 'sessions') p.sessions = p.id === 'day' ? 1 : parseInt(i.value, 10); else if (S.level === 'detail') p[i.dataset.f] = v(i.value); });
    if (S.level === 'guided') {
      const g = id => { const e = J.$(id, box); return e.value !== e.dataset.init ? e.value : null; }, sl = g('#g-slope'), rl = g('#g-r2'), dd = g('#g-dd');   // seuls les réglages que vous avez touchés écrasent les périodes
      c.periods.filter(p => p.enabled).forEach(p => { if (sl !== null && sl !== 'custom') p.min_slope = sl === 'none' ? null : P.slope_levels[sl]; if (rl !== null && rl !== 'custom') p.min_r2 = rl === 'none' || p.sessions < 3 ? null : P.r2_levels[rl]; if (dd !== null) p.max_drawdown = dd === '' || p.sessions < 3 ? null : Number(dd); });
      c.ranking = { mode: J.$('#r-mode', box).value, weights: c.ranking.weights || {} };
    } else {
      c.technical = { above_ma50: J.$('#t-ma50', box).checked, ma50_rising: J.$('#t-ma50r', box).checked, max_daily_change: v(J.$('#t-day', box).value), max_gap_ma20: v(J.$('#t-gap', box).value) };
      const w = {}; J.$$('[data-w]', box).forEach(i => { if (i.value !== '' && Number(i.value) !== 1) w[i.dataset.w] = Number(i.value); });
      c.ranking = { mode: J.$('#r-mode2', box).value, weights: w };
    }
    const m = J.$('#editor-msg', box);
    try { S.config = (await J.post('strategy/validate', c)).config; m.hidden = true; } catch (e) { m.textContent = e.message; m.hidden = false; return false; }
    S.config.name = 'custom'; S.preset = 'custom'; S.page = 1; persist(); drawStrategies(); load(); return true;
  }
  /* recherches enregistrées : critères + filtres + tri */
  let searches = [];
  async function drawSaved() {
    searches = (await J.api('searches')).searches;
    el('saved').innerHTML = `<select id="saved-sel" aria-label="Mes recherches"><option value="">Mes recherches (${searches.length})</option>${searches.map(x => `<option value="${x.id}">${J.esc(x.name)}</option>`).join('')}</select><button class="btn small" id="saved-save">Enregistrer cette recherche</button><button class="btn small danger" id="saved-del" hidden>Supprimer</button>`;
    el('saved-sel').onchange = () => { const x = searches.find(y => y.id == el('saved-sel').value); el('saved-del').hidden = !x; if (!x) return; applySearch(x); };
    el('saved-del').onclick = async () => { const x = searches.find(y => y.id == el('saved-sel').value); if (x && await J.confirm('Supprimer la recherche', '« ' + x.name + ' » sera supprimée.', 'Supprimer')) { await J.post('search/delete', { id: +x.id }); drawSaved(); } };
    el('saved-save').onclick = () => J.dialog({ title: 'Enregistrer cette recherche', body: J.field('Nom', `<input id="sv-name" maxlength="80" value="${J.esc(S.label || '')}" autofocus>`) + '<p class="small muted">Enregistre vos critères, périodes, filtres et tri. Un nom existant est remplacé.</p>',
      actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async d => { const name = J.$('#sv-name', d).value.trim(); if (!name) return true; try { await J.post('search/save', { name, config: S.config, view: { ...view(), sort: S.sort, dir: S.dir } }); } catch (e) { J.formError(d, e.message); return true; } S.label = name; persist(); await drawSaved(); drawStrategies(); J.toast('Recherche enregistrée'); } }] });
  }
  function applySearch(x) {
    S.config = x.config; S.preset = 'custom'; S.label = x.name; S.page = 1; const v = x.view || {};
    [...FILTERS, 'kind', 'market'].forEach(k => { el(k).value = v[k] ?? ''; }); el('pea').checked = !!v.pea; el('mine').checked = !!v.owned_only; el('open_now').checked = !!v.open_now; el('fresh_only').checked = !!v.fresh_only; el('tradable').checked = v.tradable !== false;
    S.sort = v.sort || 'rank'; S.dir = v.dir || 'asc'; el('filters').hidden = !(FILTERS.some(k => el(k).value) || CHECKS.some(k => el(k).checked));
    persist(); drawStrategies(); if (!el('editor').hidden) drawEditor(); load();
  }
  el('edit-btn').onclick = () => { const e = el('editor'); e.hidden = !e.hidden; if (!e.hidden) drawEditor(); };
  el('filters-btn').onclick = () => { el('filters').hidden = !el('filters').hidden; };

  function drawTabs(res) {
    const sc = res.scope_counts, tabs = [['retained', 'Retenus', sc.retained], ['rejected', 'Écartés', sc.rejected], ['unknown', 'Non évaluables', sc.unknown], ['all', 'Tous', sc.retained + sc.rejected + sc.unknown]];
    el('status-tabs').innerHTML = tabs.map(([k, l, n]) => `<button class="${S.status === k ? 'on' : ''}" data-s="${k}">${l} <span class="count">${J.num(n, 0)}</span></button>`).join('');
    J.$$('#status-tabs button').forEach(b => b.onclick = () => { S.status = b.dataset.s; S.page = 1; load(); });
    const n = FILTERS.filter(k => el(k).value.trim()).length + CHECKS.filter(k => el(k).checked).length;
    el('filters-count').hidden = !n; el('filters-count').textContent = n;
  }
  const COLS = [['rank', '#', 'rk'], ['name', 'Titre'], ['price', 'Prix (€)', 'num'], [null, 'Tendance', 'hide-s'], ['slope', 'Pente', 'num'], ['r2', 'R²', 'num'], ['perf', 'Perf.', 'num'], ['volatility', 'Volat.', 'num'], ['drawdown', 'Repli', 'num'], ['volume', 'Volume moy.', 'num'], ['score', 'Score', 'num'], [null, 'Analystes', 'hide-s'], ['fresh', 'Données', 'num'], [null, 'Verdict', '']];
  function header(ref) {
    const tip = { slope: '%/séance', r2: 'régularité', perf: 'performance', volatility: '%/séance', drawdown: 'repli maximal' };
    return '<thead><tr>' + COLS.map(([k, l, c]) => k ? `<th class="sortable ${c || ''} ${S.sort === k ? 'sorted' : ''}" data-k="${k}" title="${tip[k] ? tip[k] + ' sur ' + ref + ' séances' : 'Trier'}">${l}${S.sort === k ? (S.dir === 'asc' ? ' ▲' : ' ▼') : ''}</th>` : `<th class="${c || ''}">${l}</th>`).join('') + '</tr></thead>';
  }
  function sheetHref(id) { return 'titre.html?src=explorer&id=' + encodeURIComponent(id) + '#explore=' + encodeURIComponent(JSON.stringify({config:S.config,view:view(),preset:S.preset,label:S.label})); }
  /* Filtre actif : « # » = position dans la liste affichée, et le rang d'origine du catalogue complet reste visible dessous (jamais recalculé). */
  function rankCell(r) {
    const filtered = lastRes && lastRes.tradable && lastRes.tradable.on && S.sort === 'rank' && r.position;
    return filtered ? `${r.position}<span class="sub" style="display:block" title="Rang dans le catalogue complet, sans filtre">rang ${r.rank || '·'}</span>` : (r.rank || '·');
  }
  /* ETF « presque identiques » (Groupe A, B…) : le mieux classé reste visible, les autres se déplient sous lui avec « + ». Rangs, scores et ordre ne changent pas. */
  const openGroups = new Set();
  const famWhy = i => i && !i.leader ? `<span class="fam-why"><b>Rapproche :</b> ${(i.why || []).map(J.esc).join(' · ')}.${(i.diff || []).length ? ` <b>Diffère :</b> ${i.diff.map(J.esc).join(' · ')}.` : ' <b>Aucune différence relevée</b> dans le nom, la devise et les frais connus.'}</span>` : '';
  function groupedRows(rows) {
    const members = {};
    rows.forEach(r => { if (r.etf_group) (members[r.etf_group] = members[r.etf_group] || []).push(r); });
    const open = g => openGroups.has(g);
    return rows.map(r => {
      const g = r.etf_group, list = g ? members[g] : null;
      if (!list || list.length < 2) return row(r);
      if (list[0] !== r) return null;
      const btn = `<button type="button" class="fam-toggle" data-g="${J.esc(g)}" aria-expanded="${open(g)}" title="Afficher ou masquer les ETF presque identiques"><span class="fam-sign">${open(g) ? '−' : '+'}</span> ${list.length - 1} similaire${list.length > 2 ? 's' : ''} · ${r.etf_group_info && r.etf_group_info.index ? J.esc(r.etf_group_info.index) + ' · ' : ''}Groupe ${J.esc(g)}</button>`;
      const lead = row(r).replace(/(<td class="name">[\s\S]*?)<\/td>/, (m, a) => a + btn + '</td>');
      return lead + list.slice(1).map(c => row(c).replace('<tr ', `<tr data-child-of="${J.esc(g)}" ${open(g) ? '' : 'hidden '}`).replace(/(<td class="name">[\s\S]*?)<\/td>/, (m, a) => a + famWhy(c.etf_group_info) + '</td>')).join('');
    }).filter(x => x !== null).join('');
  }
  const ANALYST_TIP = 'Consensus des analystes financiers relevé par Yahoo (1 = achat fort, 5 = vente forte). Ce n’est pas une recommandation de Jigobourso et n’entre dans aucun score, filtre ou classement.';
  const analystCell = a => a ? `<span class="help" title="${J.esc(ANALYST_TIP)}">${J.esc(a.text)}</span>` : '<span class="muted" title="Information indisponible pour ce titre">—</span>';
  function row(r) {
    const m = r.ref || {};
    const badge = r.status === 'excluded' ? `<span class="badge ko help" title="${J.esc(r.excluded_reason || '')}">Exclu</span>` : J.statusBadge(r.status, r.status_label);
    const fresh = r.last_close ? J.date(r.last_close) : '–';
    return `<tr data-id="${r.id}"${r.etf_group ? ` class="in-family" data-group="${J.esc(r.etf_group)}"` : ''}><td class="rk">${rankCell(r)}</td>
      <td class="name"><span class="nm">${`<a data-sheet href="${J.esc(sheetHref(r.id))}" target="_blank" rel="noopener" aria-label="Ouvrir ${J.esc(r.symbol)} dans un nouvel onglet">${J.esc(r.name)}</a>`}</span><span class="sub">${J.esc(r.symbol)} · ${J.esc(r.market)} <span class="tag ${r.kind === 'etf' ? 'etf' : ''}">${r.kind === 'etf' ? 'ETF' : 'ACTION'}</span>${r.pea ? ' <span class="tag pea">PEA</span>' : ''}${r.held ? ' <span class="tag held">DÉTENU</span>' : ''}${r.open ? ' <span class="tag open">OUVERT</span>' : ''}${r.etf_group ? ` <span class="tag grp" title="Cet ETF évolue presque comme les autres ETF du groupe ${J.esc(r.etf_group)} (voir le bandeau au-dessus du tableau). Information seulement : son rang n’est pas modifié.">Groupe ${J.esc(r.etf_group)}</span>` : ''}</span>${(r.signals || []).length ? `<span class="sigs">${JEtf.rowSignals(r.signals)}</span>` : ''}${r.status === 'excluded' ? `<span class="sub warn">${J.esc(r.excluded_reason || '')}</span>` : ''}</td>
      <td class="num">${r.price_eur !== null && r.price_eur !== undefined ? J.eur(r.price_eur) : J.money(r.price, r.currency)}<span class="sub" style="display:block">${r.currency !== 'EUR' && r.price !== null ? J.money(r.price, r.currency) : (r.price ? J.priceLabel(r) : '')}</span>${r.price_stale ? '<span class="sub warn">Cours ancien</span>' : ''}</td>
      <td class="hide-s">${J.spark(r.curve)}</td>
      <td class="num ${J.cls(m.slope)}">${m.slope !== null && m.slope !== undefined ? J.num(m.slope, 3) : '–'}</td><td class="num">${J.num(m.r2, 2)}</td><td class="num ${J.cls(m.perf)}">${J.pct(m.perf, 1)}</td>
      <td class="num">${m.volatility !== null && m.volatility !== undefined ? J.num(m.volatility, 2) : '–'}</td><td class="num">${m.drawdown !== null && m.drawdown !== undefined ? J.num(m.drawdown, 1) + ' %' : '–'}</td>
      <td class="num">${r.volume ? J.num(r.volume, 0) : '–'}</td><td class="num">${r.score !== null && r.score !== undefined ? `<b>${J.num(r.score, 0)}</b><div class="score-bar"><i style="width:${r.score}%"></i></div>` : '–'}</td>
      <td class="hide-s small">${analystCell(r.analyst)}</td>
      <td class="num small ${r.quality && r.quality !== 'ok' ? 'warn' : ''}" title="${{ ok: 'À jour', stale: 'Clôture en retard', insufficient: 'Historique court', incomplete: 'Historique incomplet : des séances de marché sont absentes', calendar_unknown: 'Calendrier de séances indisponible pour cette place', break: 'Rupture de cours' }[r.quality] || ''}">${fresh}${r.quality && r.quality !== 'ok' ? ' ⚠' : ''}</td><td>${badge}</td></tr>`;
  }
  function drawWhy(res) {
    const total = (res.scope_counts.rejected || 0) + (res.scope_counts.unknown || 0), groups = {};
    Object.entries(res.reasons).forEach(([k, n]) => { const [per, crit] = k.split('|'); (groups[per || 'general'] = groups[per || 'general'] || []).push([crit, n]); });
    const label = p => p === 'technical' ? 'Filtres techniques' : p === 'general' ? 'Général' : J.PERIODS[p] || p;
    el('why-body').innerHTML = total ? `<p class="small muted" style="margin:0 0 10px">Parmi les ${J.num(total, 0)} titres non retenus (avec les filtres actuels), nombre de titres qui échouent à chaque critère. Un titre peut échouer à plusieurs critères : les totaux se cumulent.</p>` +
      Object.entries(groups).map(([per, list]) => `<h3 style="margin:10px 0 6px;font-size:.95rem">${J.esc(label(per))}</h3>` + list.sort((a, b) => b[1] - a[1]).map(([crit, n]) => `<div class="row between small" style="gap:10px"><span style="min-width:230px">${J.esc(CRIT[crit] || crit)}</span><div class="bar" style="flex:1"><i style="width:${Math.min(100, 100 * n / total)}%"></i></div><span class="muted" style="min-width:90px;text-align:right">${J.num(n, 0)} · ${J.num(100 * n / total, 0)} %</span></div>`).join('')).join('') : '<p class="muted">Aucun titre écarté avec ces filtres.</p>';
  }
  async function load() {
    const my = ++seq; el('results').innerHTML = '<div class="empty"><span class="spinner"></span></div>';
    persist();
    if (S.compare) return loadCompare(my);
    const v = { ...view(), status: S.status, sort: S.sort, dir: S.dir, page: S.page, page_size: S.size };
    let res;
    try { res = await J.post('explore', { config: S.config, view: v }); } catch (e) { if (my === seq) el('results').innerHTML = `<div class="empty"><div class="notice err">${J.esc(e.message)}</div></div>`; return; }
    if (my !== seq) return;
    lastRes = res; const lm = (res.level_filters || {}).masked || 0; el('level-note').textContent = lm ? `${J.num(lm, 0)} titre${lm > 1 ? 's' : ''} masqué${lm > 1 ? 's' : ''} par vos filtres de régularité, volatilité ou négociabilité (rang et score inchangés).` : '';
    el('tradable-note').textContent = res.tradable.on ? (res.tradable.masked ? `${J.num(res.tradable.masked, 0)} titre${res.tradable.masked > 1 ? 's' : ''} masqué${res.tradable.masked > 1 ? 's' : ''} : valeur échangée estimée trop faible. Décochez pour tout voir.` : 'Aucun titre masqué dans cette vue.') : 'Tous les titres du catalogue sont affichés.';
    drawTabs(res); drawWhy(res); fillFacets(res);
    el('results').innerHTML = res.rows.length ? JEtf.concentration(res.etf_concentration) + `<p class="small muted" style="margin:0 0 8px">${JEtf.LEGEND}</p><div class="table-wrap"><table class="rtable">${header(res.ref_sessions)}<tbody>${groupedRows(res.rows)}</tbody></table></div>` : `<div class="empty">${v.q ? 'Aucun titre ne correspond à cette recherche.' : 'Aucun titre dans cette vue avec ces critères et ces filtres.'}</div>`;
    if (!window.jigoScrollRestored) { window.jigoScrollRestored = true; try { requestAnimationFrame(() => scrollTo(0, +(sessionStorage.getItem('jigo_explorer_scroll') || 0))); } catch (e) {} }
    J.$$('#results tbody tr').forEach(tr => { const a = tr.querySelector('a[data-sheet]'); a.addEventListener('click', () => { persist(); sessionStorage.setItem('jigo_explorer_scroll', String(scrollY)); }); tr.onclick = e => { if (e.target.closest('a,button,input')) return; persist(); window.open(a.href, '_blank', 'noopener'); }; });
    J.$$('#results .fam-toggle').forEach(b => b.onclick = () => { const g = b.dataset.g, on = !openGroups.has(g); on ? openGroups.add(g) : openGroups.delete(g); b.setAttribute('aria-expanded', on); b.querySelector('.fam-sign').textContent = on ? '−' : '+'; J.$$('#results tr[data-child-of]').forEach(tr => { if (tr.dataset.childOf === g) tr.hidden = !on; }); });
    J.$$('#results th.sortable').forEach(th => th.onclick = () => { const k = th.dataset.k; if (S.sort === k) S.dir = S.dir === 'asc' ? 'desc' : 'asc'; else { S.sort = k; S.dir = ['name', 'price', 'volatility', 'drawdown', 'rank'].includes(k) ? 'asc' : 'desc'; } S.page = 1; load(); });
    el('pager').innerHTML = `<span class="muted small">${J.num(res.examined, 0)} titres examinés sur ${J.num(res.universe, 0)} · ${J.num(res.total, 0)} résultat${res.total > 1 ? 's' : ''}${res.populations.etf && res.populations.equity ? ' · actions et ETF sont classés séparément' : ''} · mesures sur ${res.ref_sessions} séances</span>
      <span class="row gap-s"><select id="size" aria-label="Lignes par page">${[20, 50, 100].map(n => `<option value="${n}" ${n === S.size ? 'selected' : ''}>${n} par page</option>`).join('')}</select><button class="btn small" id="prev" ${res.page <= 1 ? 'disabled' : ''}>←</button><span class="small">Page ${res.page} / ${res.pages}</span><button class="btn small" id="next" ${res.page >= res.pages ? 'disabled' : ''}>→</button></span>`;
    el('prev').onclick = () => { S.page--; load(); window.scrollTo({ top: 0 }); }; el('next').onclick = () => { S.page++; load(); window.scrollTo({ top: 0 }); };
    el('size').onchange = e => { S.size = +e.target.value; S.page = 1; load(); };
  }
  async function loadCompare(my) {
    const base = { ...view(), kind: '', status: 'retained', sort: 'rank', page: 1, page_size: 12 };
    let eq, etf;
    try { [eq, etf] = await Promise.all([J.post('explore', { config: S.config, view: { ...base, kind: 'equity' } }), J.post('explore', { config: S.config, view: { ...base, kind: 'etf' } })]); } catch (e) { el('results').innerHTML = `<div class="empty"><div class="notice err">${J.esc(e.message)}</div></div>`; return; }
    if (my !== seq) return;
    drawTabs(eq);
    const col = (title, res) => `<div><h2 style="margin:0 0 4px">${title}</h2><div class="muted small" style="margin-bottom:8px">${J.num(res.counts[title === 'Actions' ? 'equity' : 'etf'].retained || 0, 0)} retenus sur ${J.num(res.populations[title === 'Actions' ? 'equity' : 'etf'], 0)} · 12 premiers</div>
      ${res.rows.map(r => `<a class="result" target="_blank" rel="noopener" href="${J.esc(sheetHref(r.id))}" style="grid-template-columns:34px 1fr auto"><div class="rank">${r.rank}</div><div style="min-width:0"><div class="name">${J.esc(r.name)}</div><div class="meta">${J.esc(r.symbol)} · ${J.esc(r.market)} · pente ${J.num(r.ref.slope, 3)} · R² ${J.num(r.ref.r2, 2)}</div></div><div class="num"><b>${J.num(r.score, 0)}</b><div class="meta">${J.pct(r.ref.perf, 1)}</div></div></a>`).join('') || '<div class="muted">Aucun titre retenu.</div>'}</div>`;
    el('results').innerHTML = `<div class="grid cols-2" style="padding:16px 18px;gap:24px">${col('Actions', eq)}<div>${JEtf.concentration(etf.etf_concentration)}${col('ETF', etf)}</div></div>`;
    el('pager').innerHTML = '<span class="muted small">Chaque groupe est classé à part : un ETF n’est jamais comparé à une action pour le rang ; ici les deux classements sont côte à côte.</span>';
  }
  function fillFacets(res) {
    Object.keys(LEVELS).forEach(k => MS[k].set(LEVELS[k].map(([v, l]) => [v, l, (((res.level_filters || {}).counts || {})[k] || {})[v] || 0])));
    if (!MS.country.loaded) { MS.country.loaded = 1; MS.country.set(Object.entries(res.facets.countries).map(([c, n]) => [c, c, n])); }
    if (!MS.category.loaded) { MS.category.loaded = 1; MS.category.set(Object.entries(res.facets.categories || {}).sort((a, b) => a[0].localeCompare(b[0], 'fr')).map(([c, n]) => [c, c, n])); }
    if (el('market').options.length === 1) Object.entries(res.facets.markets).sort((a, b) => b[1] - a[1]).forEach(([m, n]) => el('market').insertAdjacentHTML('beforeend', `<option value="${J.esc(m)}">${J.esc(MARKETS[m] || m)} (${n})</option>`));
    ['market'].forEach(k => { const v = (saved.view || {})[k]; if (v && !el(k).dataset.restored) { el(k).value = v; el(k).dataset.restored = 1; } });
    el('filters-note').textContent = 'Les filtres numériques utilisent les mesures sur ' + res.ref_sessions + ' séances (la plus longue période active).';
  }
  el('compare-btn').onclick = () => { S.compare = !S.compare; el('compare-btn').classList.toggle('primary', S.compare); el('compare-btn').textContent = S.compare ? 'Retour au tableau' : 'Comparer actions / ETF'; S.page = 1; load(); };
  el('export-btn').onclick = async () => {
    const res = await J.post('explore', { config: S.config, view: { ...view(), status: S.status, sort: S.sort, dir: S.dir, export: true } });
    const head = ['Rang', 'Nom', 'Symbole', 'ISIN', 'Place', 'Type', 'Pays', 'Prix (devise)', 'Devise', 'Prix (EUR)', 'Pente', 'R2', 'Perf %', 'Volatilité', 'Repli %', 'Volume moyen', 'Score', 'Statut', 'Dernière clôture'];
    const q = v => { v = v === null || v === undefined ? '' : String(v).replace('.', ','); return /[;"\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
    const lines = res.rows.map(r => [r.rank, r.name, r.symbol, r.isin, r.market, r.kind, r.country, r.price, r.currency, r.price_eur, r.ref.slope, r.ref.r2, r.ref.perf, r.ref.volatility, r.ref.drawdown, r.volume, r.score, r.status_label, r.last_close].map(q).join(';'));
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob(['﻿' + [head.join(';'), ...lines].join('\r\n')], { type: 'text/csv;charset=utf-8' })); a.download = 'jigobourso-explorer-' + new Date().toISOString().slice(0, 10) + '.csv'; a.click();
    J.toast(res.rows.length + ' lignes exportées' + (res.total > res.rows.length ? ' (limite de 3 000)' : ''));
  };
  el('reset-filters').onclick = () => { FILTERS.forEach(k => el(k).value = ''); CHECKS.forEach(k => el(k).checked = false); el('kind').value = ''; el('market').value = ''; el('tradable').checked = true; S.page = 1; load(); };
  el('tradable').onchange = () => { S.page = 1; load(); };
  [...text, ...CHECKS].forEach(k => el(k).addEventListener(el(k).type === 'search' || el(k).type === 'number' || el(k).placeholder ? 'input' : 'change', () => { clearTimeout(timer); timer = setTimeout(() => { S.page = 1; if (el('q').value.trim()) S.status = 'all'; load(); }, 350); }));
  /* liens du menu latéral : ?kind=, ?compare=1, ?preset= */
  if (url.get('kind')) el('kind').value = url.get('kind');
  if (url.get('preset') === 'free') { S.preset = 'free'; S.label = null; S.config = freeConfig(); } else if (P.presets[url.get('preset')]) { S.preset = url.get('preset'); S.label = null; S.config = JSON.parse(JSON.stringify(P.presets[S.preset])); }
  drawSources(); drawStrategies(); drawSaved(); if (el('q').value) S.status = 'all';
  if (url.get('compare')) { S.compare = true; el('compare-btn').classList.add('primary'); el('compare-btn').textContent = 'Retour au tableau'; }
  if (FILTERS.some(k => el(k).value) || CHECKS.some(k => el(k).checked)) el('filters').hidden = false;
  load();
})();
