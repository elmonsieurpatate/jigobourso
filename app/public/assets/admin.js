/* Administration : construire le catalogue à la main, dans l'ordre (FinanceDatabase → Yahoo → historiques), consulter les titres, suivre le cron. */
(async () => {
  if (!await J.init('admin', { admin: true })) return;
  const page = J.$('#page'); const TABS = ['fdb', 'yahoo', 'titres', 'cron', 'logs', 'users', 'settings'];
  const LEGACY = { data: 'fdb', catalogue: 'fdb', overview: 'fdb', jobs: 'logs', run: 'logs', schedule: 'cron' };
  const hashTab = () => { const h = location.hash.slice(1); return TABS.includes(h) ? h : (LEGACY[h] || 'fdb'); };
  let tab = hashTab();
  const TITLES = { fdb: 'FinanceDatabase', yahoo: 'Yahoo Finance', titres: 'Actions / ETF', cron: 'Cron', logs: 'Journaux', users: 'Utilisateurs', settings: 'Réglages' };
  const STATE = { completed: ['ok', 'Terminé'], completed_with_errors: ['wait', 'Terminé avec erreurs'], failed: ['ko', 'Échec'], running: ['info', 'En cours'], queued: ['info', 'En attente'], paused: ['wait', 'En pause'], interrupted: ['ko', 'Interrompu'] };
  const TSTATE = { ok: ['ok', 'Fonctionne'], late: ['wait', 'En retard'], error: ['ko', 'En erreur'], inactive: ['', 'Désactivée'], never: ['wait', 'Jamais exécutée'], running: ['info', 'En cours'] };
  const JOBNAME = { fdb_import: 'Import FinanceDatabase', fdb_filter: 'Filtrage FinanceDatabase', yahoo_info: 'Import des informations Yahoo', yahoo_filter: 'Filtrage Yahoo', history: 'Import / mise à jour des historiques',
    metrics: 'Indicateurs et classements', etf: 'Similarité des ETF', maintenance: 'Entretien après collecte', catchup: 'Rattrapage des données manquantes', intraday: 'Barres de 15 min', daily: 'Clôtures quotidiennes', catalogue: 'Import FinanceDatabase (ancien)', nightly: 'Analyse de nuit (ancienne)' };
  const jobName = t => JOBNAME[t] || (t.includes(':') ? (JOBNAME[t.split(':')[0]] || t.split(':')[0]) + ' · ' + t.split(':')[1] : t);
  const nf = v => v == null ? '–' : J.num(+v, 0);
  const dur = s => s == null ? '–' : s < 90 ? Math.round(s) + ' s' : s < 5400 ? Math.round(s / 60) + ' min' : (s / 3600).toFixed(1).replace('.', ',') + ' h';
  const MANUAL = ['fdb_import', 'fdb_filter', 'yahoo_info', 'yahoo_filter', 'history', 'gaps', 'maintenance', 'metrics', 'etf'];

  async function render() {
    page.innerHTML = '<div class="empty"><span class="spinner"></span></div>';
    J.$('.page-head h1').textContent = 'Administration · ' + TITLES[tab];
    try { await ({ fdb, yahoo, titres, cron, logs, users, settings })[tab](); } catch (e) { page.innerHTML = `<div class="notice err">${J.esc(e.message)}</div>`; }
  }
  window.addEventListener('hashchange', () => { const t = hashTab(); if (t !== tab) { tab = t; render(); } });

  // ───────── lancement et suivi d'un traitement ─────────
  let polling = false;
  async function run(job, label, confirmText) {
    if (confirmText && !await J.confirm(label, confirmText, 'Lancer')) return false;
    try { const stamp = new Date(Date.now() - 4000).toISOString().slice(0, 19).replace('T', ' '); const r = await J.post('admin/run', { job }); J.toast(r.label + ' lancé'); poll(stamp, job); return true; } catch (e) { J.toast(e.message); return false; }
  }
  async function poll(launchedAt, launchedJob) {
    if (polling) return; polling = true;
    let bar = J.$('#runbar'); if (!bar) { page.insertAdjacentHTML('afterbegin', '<div id="runbar" class="notice" style="display:none"></div>'); bar = J.$('#runbar'); }
    let seen = false;
    const done = () => { polling = false; J.toast('Traitement terminé'); render(); };
    for (let i = 0; i < 2000; i++) {
      let r; try { r = await J.api('admin/jobs', { params: { status: 'running' } }); } catch (e) { break; }
      const list = r.jobs.filter(j => MANUAL.includes(j.job_type));
      if (list.length) { seen = true; bar = J.$('#runbar') || bar; bar.style.display = ''; bar.innerHTML = '<span class="spinner"></span> <b>' + list.map(j => J.esc(jobName(j.job_type))).join(', ') + '</b> en cours · ' + J.esc(list[0].summary || 'démarrage…') + ' <a href="#logs">Journaux</a>'; }
      else {
        if (bar) bar.style.display = 'none';
        if (seen) return done();
        if (launchedAt) { const r2 = await J.api('admin/jobs', { params: { since: launchedAt } }).catch(() => ({ jobs: [] })); if (r2.jobs.some(j => j.job_type === launchedJob && !['running', 'queued'].includes(j.status))) return done(); }
        else if (i > 2) break;
      }
      await new Promise(res => setTimeout(res, 2000));
    }
    polling = false;
  }
  const runBar = () => '<div id="runbar" class="notice" style="display:none"></div>';
  const when = v => v ? J.dateTime(v) : 'jamais';
  const jobLine = j => j ? `<span class="badge ${STATE[j.status][0]}">${STATE[j.status][1]}</span> ${J.dateTime(j.started_at)} · durée ${dur(j.duration_s)}${j.items_error ? ` · <span class="warn">${j.items_error} erreurs</span>` : ''}<div class="small muted">${J.esc(j.summary || '')} <a href="#" data-job="${j.id}">Détail</a></div>` : '<span class="muted">Jamais lancé</span>';
  const bindJobLinks = () => J.$$('a[data-job]').forEach(a => a.onclick = e => { e.preventDefault(); jobDialog(a.dataset.job); });

  // ───────── formulaire de filtres (règles éditables) ─────────
  function filterForm(lv, { places, categories } = {}) {
    const row = r => {
      const c = r.current; let ctl = '';
      if (r.id === 'types') ctl = ['equity', 'etf'].map(k => `<label class="row gap-s small"><input type="checkbox" data-rule="types" data-f="${k}" ${c[k] ? 'checked' : ''}> ${k === 'etf' ? 'ETF' : 'Actions'}</label>`).join(' ');
      else if (r.key) ctl = `<span class="row gap-s"><input type="number" data-rule="${r.id}" data-f="${r.key}" step="${r.step}" min="0" max="${r.max}" value="${c[r.key]}" style="width:130px"> <span class="small muted">${J.esc(r.unit)}</span></span>`;
      return `<div class="frow"><label class="row gap-s" style="align-items:flex-start"><input type="checkbox" data-rule="${r.id}" data-f="enabled" ${c.enabled ? 'checked' : ''}><span><b>${J.esc(r.label)}</b>${r.is_default ? '' : ' <span class="badge wait">modifié</span>'}<span class="small muted" style="display:block">${J.esc(r.role)}</span></span></label>
        ${ctl ? `<div style="margin:4px 0 0 26px">${ctl}</div>` : ''}${r.id === 'markets' ? placePicker(r, places) : r.id === 'categories' ? catPicker(r, categories) : ''}
        <details style="margin-left:26px"><summary class="small muted" style="cursor:pointer">Pourquoi ce filtre ?</summary><p class="small">${J.esc(r.help)}</p></details></div>`;
    };
    const groups = {}; lv.rules.forEach(r => (groups[r.group] = groups[r.group] || []).push(r));
    const names = { ...lv.groups, liquidity: 'Prix, ancienneté du cours et liquidité' };
    return Object.entries(groups).map(([g, rs]) => `<div style="margin-bottom:14px"><h3 style="margin:0 0 6px">${J.esc(names[g] || g)}</h3>${rs.map(row).join('')}</div>`).join('');
  }
  function placePicker(r, places) {
    const sel = new Set(r.current.values);
    return `<div style="margin:6px 0 0 26px"><div class="row gap-s" style="flex-wrap:wrap"><input id="pl-q" type="search" placeholder="Chercher une place (nom ou code)" style="width:240px"><span class="small muted" id="pl-n"></span>
      <button class="btn small" type="button" id="pl-all">Cocher les places affichées</button><button class="btn small" type="button" id="pl-none">Décocher les places affichées</button><button class="btn small" type="button" id="pl-def">Places par défaut</button></div>
      <div id="pl-list" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:2px 12px;max-height:240px;overflow:auto;margin-top:6px;border:1px solid var(--line,#ddd);border-radius:8px;padding:8px">
      ${places.map(p => `<label class="small" data-search="${J.esc((p.mic + ' ' + p.name).toLowerCase())}"><input type="checkbox" data-mic="${J.esc(p.mic)}" data-def="${p.default ? 1 : 0}" ${sel.has(p.mic) ? 'checked' : ''}> <b>${J.esc(p.mic)}</b> ${J.esc(p.name)} <span class="muted">${nf(p.equity)} act. · ${nf(p.etf)} ETF${p.hours_known ? '' : ' · pas de barres 15 min'}</span></label>`).join('') || '<span class="muted small">Importez FinanceDatabase pour voir toutes les places disponibles.</span>'}</div>
      <p class="small muted" style="margin:4px 0 0">Toutes les places présentes dans FinanceDatabase sont proposées. Les places sans horaires connus n’ont que les clôtures quotidiennes.</p></div>`;
  }
  function catPicker(r, cats) {
    const sel = new Set(r.current.values);
    return `<details style="margin:6px 0 0 26px"><summary class="small" style="cursor:pointer">Choisir les catégories à exclure (${r.current.values.length} cochées)</summary><div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:2px 12px;max-height:200px;overflow:auto;margin-top:6px">
      ${(cats || []).map(c => `<label class="small"><input type="checkbox" data-cat="${J.esc(c.category)}" ${sel.has(c.category) ? 'checked' : ''}> ${J.esc(c.category)} <span class="muted">${nf(c.n)}</span></label>`).join('') || '<span class="muted small">Aucune catégorie : importez FinanceDatabase.</span>'}</div></details>`;
  }
  function bindForm() {
    const q = J.$('#pl-q'); if (!q) return;
    const labels = () => J.$$('#pl-list label[data-search]');
    const count = () => { J.$('#pl-n').textContent = J.$$('#pl-list input:checked').length + ' places cochées sur ' + labels().length; };
    q.oninput = () => { const t = q.value.trim().toLowerCase(); labels().forEach(l => l.style.display = !t || l.dataset.search.includes(t) ? '' : 'none'); };
    const vis = () => labels().filter(l => l.style.display !== 'none');
    J.$('#pl-all').onclick = () => { vis().forEach(l => l.querySelector('input').checked = true); count(); };
    J.$('#pl-none').onclick = () => { vis().forEach(l => l.querySelector('input').checked = false); count(); };
    J.$('#pl-def').onclick = () => { labels().forEach(l => { const i = l.querySelector('input'); i.checked = i.dataset.def === '1'; }); count(); };
    J.$('#pl-list').onchange = count; count();
  }
  function collectForm() {
    const cfg = {};
    J.$$('[data-rule]').forEach(el => { const id = el.dataset.rule; cfg[id] = cfg[id] || {}; if (el.type === 'checkbox') cfg[id][el.dataset.f] = el.checked; else cfg[id][el.dataset.f] = el.value === '' ? null : +el.value; });
    if (J.$('#pl-list')) { cfg.markets = cfg.markets || {}; cfg.markets.values = J.$$('#pl-list input[data-mic]:checked').map(i => i.dataset.mic); }
    if (J.$$('[data-cat]').length) { cfg.categories = cfg.categories || {}; cfg.categories.values = J.$$('[data-cat]:checked').map(i => i.dataset.cat); }
    return cfg;
  }
  async function saveThen(level, next) {
    try { await J.post('admin/rules/save', { level, config: collectForm() }); } catch (e) { J.toast(e.message); return; }
    if (next) await run(next); else { J.toast('Filtres enregistrés'); render(); }
  }

  // ───────── entonnoir ─────────
  function funnelTable(steps, { onItems, all = false } = {}) {
    const max = Math.max(1, ...steps.map(s => s.before));
    steps = steps.filter((s, i) => all || i === 0 || i === steps.length - 1 || s.removed > 0 || ['primary', 'no_data'].includes(s.key));
    return `<div class="table-wrap"><table class="funnel"><thead><tr><th>Étape</th><th>Règle et seuil</th><th class="num">Avant</th><th class="num">Écartés</th><th class="num">Conservés</th><th style="width:130px"></th>${onItems ? '<th></th>' : ''}</tr></thead><tbody>
      ${steps.map(s => `<tr><td><b>${J.esc(s.label)}</b>${s.info && s.info.by_kind && Object.keys(s.info.by_kind).length ? `<div class="small muted">${Object.entries(s.info.by_kind).map(([k, v]) => `${nf(v)} ${k === 'etf' ? 'ETF' : 'actions'}`).join(' · ')}</div>` : ''}${s.info && s.info.quality ? `<div class="small muted">${Object.entries(s.info.quality).map(([k, v]) => `${nf(v)} ${J.esc(k)}`).join(' · ')}</div>` : ''}</td>
        <td class="small">${J.esc(s.rule)}${s.info && s.info.enabled === false ? ' <span class="badge">désactivée</span>' : ''}</td><td class="num">${nf(s.before)}</td><td class="num ${s.removed ? 'warn' : ''}">${s.removed ? '− ' + nf(s.removed) : '0'}</td><td class="num"><b>${nf(s.kept)}</b></td>
        <td><div style="height:8px;background:var(--line,#ddd);border-radius:4px;overflow:hidden"><div style="width:${100 * s.kept / max}%;height:100%;background:var(--accent,#2a6)"></div></div></td>
        ${onItems ? `<td class="num"><button class="btn small" data-step="${s.key}">Voir les titres</button></td>` : ''}</tr>`).join('')}</tbody></table></div>`;
  }
  async function itemsPanel(stage, step, label, host) {
    const st = { q: '', kind: '', mic: '', page: 1 };
    host.innerHTML = '';
    async function load() {
      const r = await J.api('admin/funnel/items', { params: { stage, step, ...Object.fromEntries(Object.entries(st).filter(([, v]) => v !== '')) } });
      const cat = stage === 'catalogue';
      host.innerHTML = `<div class="card" style="margin-top:14px;padding:0"><div class="row between" style="padding:14px 18px"><h3 style="margin:0">Titres · ${J.esc(label)}</h3><button class="btn small" id="ip-close">Fermer</button></div>
        <div class="row" style="padding:0 18px 12px;gap:10px"><input id="ip-q" type="search" placeholder="Nom, symbole ou ISIN" value="${J.esc(st.q)}" style="flex:1;min-width:160px"><select id="ip-k"><option value="">Actions et ETF</option><option value="equity" ${st.kind === 'equity' ? 'selected' : ''}>Actions</option><option value="etf" ${st.kind === 'etf' ? 'selected' : ''}>ETF</option></select><input id="ip-m" placeholder="Place (ex. XETR)" value="${J.esc(st.mic)}" style="width:130px"></div>
        <div class="table-wrap"><table><thead><tr><th>Titre</th><th>Place</th><th>Type</th><th>${cat ? 'Motif' : 'Statut / motif'}</th>${cat ? '' : '<th class="num">Cours (€)</th><th class="num">Liquidité (€/jour)</th>'}</tr></thead><tbody>
        ${r.rows.map(x => `<tr ${x.id ? `data-id="${x.id}" style="cursor:pointer"` : ''}><td><b>${J.esc(x.name)}</b>${x.held ? ' <span class="badge accent">détenu</span>' : ''}<div class="small muted">${J.esc(x.symbol)} · ${J.esc(x.isin || '')} · ${J.esc(x.country || '')}</div></td><td>${J.esc(x.mic)}</td><td>${x.kind === 'etf' ? 'ETF' : 'Action'}</td>
          <td class="small">${J.esc(cat ? (x.removed_reason || 'conservée') : (x.excluded_reason || x.status + (x.is_primary ? ' · principale' : '')))}</td>${cat ? '' : `<td class="num">${x.price_eur != null ? J.num(x.price_eur, 2) : '–'}</td><td class="num">${x.liquidity_eur != null ? J.num(x.liquidity_eur, 0) : '–'}</td>`}</tr>`).join('') || `<tr><td colspan="6" class="empty">Aucun titre.</td></tr>`}</tbody></table></div>
        <div class="row between" style="padding:12px 18px"><span class="muted small">${nf(r.total)} titres</span><span class="row gap-s"><button class="btn small" id="ip-p" ${r.page <= 1 ? 'disabled' : ''}>←</button><span class="small">Page ${r.page} / ${r.pages}</span><button class="btn small" id="ip-n" ${r.page >= r.pages ? 'disabled' : ''}>→</button></span></div></div>`;
      const go = () => { st.q = J.$('#ip-q').value.trim(); st.kind = J.$('#ip-k').value; st.mic = J.$('#ip-m').value.trim().toUpperCase(); st.page = 1; load(); };
      let t; J.$('#ip-q').oninput = () => { clearTimeout(t); t = setTimeout(go, 350); }; J.$('#ip-k').onchange = go; J.$('#ip-m').onchange = go;
      J.$('#ip-p').onclick = () => { st.page--; load(); }; J.$('#ip-n').onclick = () => { st.page++; load(); }; J.$('#ip-close').onclick = () => host.innerHTML = '';
      J.$$('tr[data-id]', host).forEach(tr => tr.onclick = () => location.href = 'titre.html?id=' + tr.dataset.id);
      host.scrollIntoView({ block: 'nearest' });
    }
    await load();
  }
  function explainBox(host) {
    host.innerHTML = `<div class="card"><h2>Pourquoi ce titre a-t-il disparu ?</h2><div class="row" style="gap:10px"><input id="ex-q" placeholder="Nom, symbole ou ISIN (ex. DVDG.DE)" style="flex:1"><button class="btn primary" id="ex-go">Expliquer</button></div><div id="ex-out" style="margin-top:12px"></div></div>`;
    const go = async () => {
      const out = J.$('#ex-out', host); out.innerHTML = '<span class="spinner"></span>';
      try {
        const r = await J.api('admin/funnel/explain', { params: { q: J.$('#ex-q', host).value } });
        const mark = { passed: ['ok', '✓'], removed: ['fail', '✗'], not_reached: ['missing', '–'] };
        const line = t => `<div class="reason ${mark[t.result][0]}" style="margin-bottom:4px"><span class="mark">${mark[t.result][1]}</span><span class="small"><b>${J.esc(t.label)}</b> · ${J.esc(t.detail || '')}${t.rule && t.result === 'removed' ? `<br><span class="muted">${J.esc(t.rule)}</span>` : ''}</span></div>`;
        const warn = r.pending.catalogue || r.pending.yahoo ? `<div class="notice">Des règles ont été modifiées sans être appliquées : ce diagnostic montre le dernier résultat calculé, pas la configuration actuelle.</div>` : '';
        out.innerHTML = warn + (r.results.map(x => `<div style="margin-bottom:14px"><b>${J.esc(x.raw.name)}</b> <span class="muted small">${J.esc(x.raw.symbol)} · ${J.esc(x.raw.mic)} · ${J.esc(x.raw.isin || '')}</span>
          <h4 style="margin:8px 0 4px">Catalogue FinanceDatabase</h4>${x.catalogue.map(line).join('')}${x.yahoo.length ? '<h4 style="margin:8px 0 4px">Yahoo Finance</h4>' + x.yahoo.map(line).join('') : ''}
          ${x.listing && x.listing.held ? '<p class="small">Titre détenu : toujours suivi et valorisé, même s’il est exclu.</p>' : ''}</div>`).join('') || '<p class="muted">Aucun titre trouvé dans les données FinanceDatabase stockées. Si le catalogue n’a jamais été importé dans cette version, lancez un import complet.</p>');
      } catch (e) { out.innerHTML = `<div class="notice err">${J.esc(e.message)}</div>`; }
    };
    J.$('#ex-go', host).onclick = go; J.$('#ex-q', host).onkeydown = e => { if (e.key === 'Enter') go(); };
  }


  const funnelBlock = (steps, stage, run_) => `<div class="row between" style="margin-bottom:6px"><span class="small muted">${run_ ? `Dernier filtrage : ${J.dateTime(run_.created_at)}` : 'Pas encore de filtrage : état actuel de la base'}</span><label class="small row gap-s"><input type="checkbox" id="fn-all"> Afficher aussi les étapes sans effet</label></div><div id="fun">${funnelTable(steps, { onItems: true })}</div><div id="items"></div>`;
  function bindFunnel(stage, steps, run_) {
    const draw = () => { J.$('#fun').innerHTML = funnelTable(steps, { onItems: true, all: J.$('#fn-all').checked }); bind(); };
    const bind = () => J.$$('#fun button[data-step]').forEach(b => b.onclick = () => itemsPanel(stage, b.dataset.step, steps.find(s => s.key === b.dataset.step).label, J.$('#items')));
    J.$('#fn-all').onchange = draw; bind();
  }

  // ───────── FinanceDatabase ─────────
  async function fdb() {
    const s = await J.api('admin/fdb'), imp = s.import, lv = s.filters, f = s.funnel;
    const none = !imp.raw_rows;
    page.innerHTML = `${runBar()}
      <div class="card"><h2>A · Importer FinanceDatabase</h2><div class="grid cols-2"><div>
        <p style="margin:0">${imp.load ? `Dernier import : <b>${J.dateTime(imp.load.loaded_at)}</b><br><span class="small muted">Source ${J.esc(imp.source)} · version ${J.esc(imp.load.commit)} · ${nf(imp.load.rows_read)} lignes lues</span>` : '<b>Jamais importé.</b>'}</p>
        <p class="small muted" style="margin:6px 0 0">Données brutes conservées en base : <b>${nf(imp.raw_rows)}</b> lignes${none && imp.load ? ' <span class="warn">(import fait avec l’ancienne version : relancez l’import pour pouvoir filtrer)</span>' : ''}. L’import ne filtre rien et ne supprime rien : vous pourrez changer les filtres sans retélécharger.</p></div>
        <div><div class="small">${jobLine(imp.last)}</div><button class="btn primary" id="go-import" style="margin-top:10px">Importer FinanceDatabase</button></div></div></div>
      <div class="card" style="margin-top:16px"><h2>B · Filtres FinanceDatabase</h2>
        <p class="small muted">Valeurs actuelles = valeurs par défaut au départ. Tout est modifiable ; rien n’est appliqué avant de cliquer sur « Filtrer ». ${lv.pending ? '<b class="warn">Filtres modifiés depuis le dernier filtrage.</b>' : ''}</p>
        ${filterForm(lv, { places: s.places, categories: s.categories })}
        <details style="margin-bottom:12px"><summary class="small muted" style="cursor:pointer">Règles techniques toujours appliquées</summary>${lv.technical.map(t => `<p class="small" style="margin:4px 0"><b>${J.esc(t.label)}</b> : ${J.esc(t.role)}</p>`).join('')}</details>
        <div class="row gap-s"><button class="btn primary" id="go-filter" ${none ? 'disabled title="Importez d’abord FinanceDatabase"' : ''}>Filtrer</button><button class="btn" id="go-reset" ${lv.is_default ? 'disabled' : ''}>Valeurs par défaut</button></div></div>
      <div class="card" style="margin-top:16px"><h2>C · Résultats du filtrage</h2>${none ? '<p class="muted">Aucun résultat : importez puis filtrez.</p>' : funnelBlock(f.steps, 'catalogue', f.run)}
        ${none ? '' : '<p style="margin:12px 0 0">Résultat transmis à Yahoo : <b>' + nf(f.steps[f.steps.length - 1].kept) + ' titres</b>. <a href="#yahoo">Étape suivante : Yahoo Finance →</a></p>'}</div>
      <div id="explain" style="margin-top:16px"></div>`;
    bindForm(); bindJobLinks(); poll();
    J.$('#go-import').onclick = () => run('fdb_import', 'Importer FinanceDatabase', 'Télécharge FinanceDatabase (quelques minutes) et remplace les données brutes stockées. Aucun filtre n’est appliqué, vos portefeuilles ne sont pas touchés.');
    J.$('#go-filter').onclick = () => saveThen('catalogue', 'fdb_filter');
    J.$('#go-reset').onclick = async () => { if (await J.confirm('Valeurs par défaut', 'Tous les filtres FinanceDatabase reviennent à leur configuration d’origine (non appliquée tant que vous ne cliquez pas sur « Filtrer »).', 'Restaurer')) { await J.post('admin/rules/reset', { level: 'catalogue' }); render(); } };
    if (!none) { bindFunnel('catalogue', f.steps, f.run); explainBox(J.$('#explain')); }
  }

  // ───────── Yahoo Finance ─────────
  async function yahoo() {
    const s = await J.api('admin/yahoo'), info = s.info, lv = s.filters, f = s.funnel, fin = s.final, st = info.stats, cov = fin.coverage, h = fin.stats;
    const hist = fin.last_history, many = x => x == null ? '–' : nf(x);
    page.innerHTML = `${runBar()}${s.pending.map(p => `<div class="notice" style="margin-bottom:10px">${J.esc(p)}</div>`).join('')}
      <div class="card"><h2>A · Importer les informations Yahoo</h2><p class="small muted" style="margin:0 0 8px">Pour les titres issus du filtrage FinanceDatabase : cours, devise, volume moyen, capitalisation. Pas encore d’historique.</p>
        <div class="grid cols-2"><div>${info.last ? `<p style="margin:0">Dernier import : <b>${J.dateTime(info.last.finished_at || info.last.started_at)}</b></p>` : '<p style="margin:0"><b>Jamais importé.</b></p>'}
          ${st ? `<div class="grid cols-4" style="margin-top:8px"><div class="kpi"><span class="l">Demandés</span><span class="v">${nf(st.requested)}</span></div><div class="kpi"><span class="l">Récupérés</span><span class="v">${nf(st.recovered)}</span></div><div class="kpi"><span class="l">Manquants</span><span class="v">${nf(st.missing)}</span></div><div class="kpi"><span class="l">En erreur</span><span class="v ${st.errors ? 'warn' : ''}">${nf(st.errors)}</span></div></div>` : ''}
          <p class="small muted" style="margin:8px 0 0">${nf(info.asked_now)} titres seraient interrogés maintenant.</p></div>
          <div><div class="small">${jobLine(info.last)}</div><button class="btn primary" id="go-info" style="margin-top:10px">Importer les informations Yahoo</button></div></div></div>
      <div class="card" style="margin-top:16px"><h2>B · Filtres Yahoo</h2><p class="small muted">Réapplicables aux informations déjà stockées, sans appeler Yahoo. ${lv.pending ? '<b class="warn">Filtres modifiés depuis le dernier filtrage.</b>' : ''}</p>
        ${filterForm(lv)}<div class="row gap-s"><button class="btn primary" id="go-filter" ${info.quotes ? '' : 'disabled title="Importez d’abord les informations Yahoo"'}>Filtrer</button><button class="btn" id="go-reset" ${lv.is_default ? 'disabled' : ''}>Valeurs par défaut</button></div>
        <h3 style="margin:18px 0 6px">Résultats du filtrage</h3>${funnelBlock(f.steps, 'yahoo', f.run)}</div>
      <div id="explain" style="margin-top:16px"></div>
      <div class="card" style="margin-top:16px;border:2px solid var(--accent,#2a6)"><h2>C · Mon catalogue final et ses historiques</h2>
        <div class="grid cols-4"><div class="kpi"><span class="l">Titres du catalogue</span><span class="v">${nf(fin.total)}</span><span class="small muted">${nf(fin.equity)} actions · ${nf(fin.etf)} ETF</span></div>
          <div class="kpi"><span class="l">Historique complet</span><span class="v">${nf(cov.complete)}</span><span class="small muted">${fin.full} séances ou plus</span></div>
          <div class="kpi"><span class="l">Historique incomplet</span><span class="v ${cov.partial ? 'warn' : ''}">${nf(cov.partial)}</span><span class="small muted">moins de ${fin.full} séances</span></div>
          <div class="kpi"><span class="l">Sans historique</span><span class="v ${cov.absent ? 'warn' : ''}">${nf(cov.absent)}</span></div></div>
        <p class="small muted" style="margin:8px 0">Cotations principales retenues : ${nf(fin.total)}${fin.held_extra ? ` · ${fin.held_extra} titre(s) détenu(s) hors catalogue, toujours valorisés` : ''}. Dernière séance en base : ${cov.last_day ? J.date(cov.last_day) : '–'}. Dernière mise à jour des historiques : <b>${hist ? J.dateTime(hist.finished_at || hist.started_at) : 'jamais'}</b>.</p>
        <button class="btn primary" id="go-history" style="font-size:16px;padding:12px 20px" ${fin.total ? '' : 'disabled title="Le catalogue final est vide : filtrez d’abord Yahoo"'}>Importer / mettre à jour les historiques</button>
        <button class="btn" id="go-gaps" style="margin-left:8px" ${fin.total ? '' : 'disabled'} title="Un appel Yahoo par titre dont l’année est incomplète">Combler les clôtures manquantes</button>
        <p class="small muted" style="margin:8px 0 0">Récupère les clôtures quotidiennes manquantes (jusqu’à ${fin.full} séances, sans retélécharger l’existant), complète les barres de 15 minutes des deux dernières séances, puis recalcule les indicateurs. Le cron entretient ensuite ces historiques automatiquement.</p>
        ${h ? `<h3 style="margin:16px 0 6px">Résultat de la dernière mise à jour</h3><div class="table-wrap"><table><thead><tr><th></th><th class="num">Titres</th><th class="num">Déjà à jour</th><th class="num">Interrogés</th><th class="num">Données ajoutées</th><th class="num">Déjà présentes</th><th class="num">Sans réponse</th></tr></thead><tbody>
          <tr><td>Clôtures quotidiennes</td><td class="num">${many(h.daily.titles)}</td><td class="num">${many(h.daily.up_to_date)}</td><td class="num">${many(h.daily.asked)}</td><td class="num">${many(h.daily.added)}</td><td class="num">${many(h.daily.present)}</td><td class="num ${h.daily.errors ? 'warn' : ''}">${many(h.daily.errors)}</td></tr>
          <tr><td>Barres de 15 minutes</td><td class="num">${many(h.intraday.titles)}</td><td class="num">${many(h.intraday.up_to_date)}</td><td class="num">${many(h.intraday.asked)}</td><td class="num">${many(h.intraday.added)}</td><td class="num">${many(h.intraday.present)}</td><td class="num ${h.intraday.errors ? 'warn' : ''}">${many(h.intraday.errors)}</td></tr></tbody></table></div>
          ${h.intraday.unknown_hours ? `<p class="small muted">${nf(h.intraday.unknown_hours)} titres de places sans horaires connus : clôtures quotidiennes seulement.</p>` : ''}<div class="small">${jobLine(hist)}</div>` : ''}</div>`;
    bindForm(); bindJobLinks(); poll();
    J.$('#go-info').onclick = () => run('yahoo_info', 'Importer les informations Yahoo', 'Interroge Yahoo Finance pour ' + nf(info.asked_now) + ' titres (plusieurs minutes). Aucun historique n’est téléchargé.');
    J.$('#go-filter').onclick = () => saveThen('prefilter', 'yahoo_filter');
    J.$('#go-reset').onclick = async () => { if (await J.confirm('Valeurs par défaut', 'Les filtres Yahoo reviennent à leur configuration d’origine (non appliquée tant que vous ne cliquez pas sur « Filtrer »).', 'Restaurer')) { await J.post('admin/rules/reset', { level: 'prefilter' }); render(); } };
    J.$('#go-history').onclick = () => run('history', 'Importer / mettre à jour les historiques', 'Travaille sur les ' + nf(fin.total) + ' titres du catalogue final. Ça peut durer longtemps la première fois ; la progression s’affiche en haut de page.');
    J.$('#go-gaps').onclick = () => run('gaps', 'Combler les clôtures manquantes', 'Interroge Yahoo (un appel par titre) pour chaque titre dont la dernière année a des séances manquantes, ajoute uniquement les jours absents, puis recalcule les indicateurs. Plusieurs minutes ; reprenable si Yahoo limite les appels.');
    bindFunnel('yahoo', f.steps, f.run); explainBox(J.$('#explain'));
  }

  // ───────── Actions / ETF ─────────
  const tf = { q: '', kind: '', mic: '', fdb: '', yahoo: '', final: '', daily: '', sort: 'name', dir: 'asc', page: 1 };
  async function titres() {
    const r = await J.api('admin/titles', { params: Object.fromEntries(Object.entries(tf).filter(([, v]) => v !== '')) });
    const opt = (cur, list) => list.map(([v, l]) => `<option value="${v}" ${String(cur) === String(v) ? 'selected' : ''}>${l}</option>`).join('');
    const B = { kept: ['ok', 'Conservé'], removed: ['ko', 'Écarté'], pending: ['wait', 'En attente'], secondary: ['', 'Secondaire'], na: ['', '–'], complete: ['ok', 'Complet'], partial: ['wait', 'Incomplet'], absent: ['ko', 'Absent'] };
    const badge = k => `<span class="badge ${B[k][0]}">${B[k][1]}</span>`;
    const th = (key, label) => `<th ${key ? `data-sort="${key}" style="cursor:pointer"` : ''}>${label}${tf.sort === key ? (tf.dir === 'asc' ? ' ▲' : ' ▼') : ''}</th>`;
    page.innerHTML = `${runBar()}<div class="card" style="padding:0"><div class="row" style="padding:14px 18px;gap:10px;flex-wrap:wrap"><input id="tq" type="search" placeholder="Nom, symbole ou ISIN" value="${J.esc(tf.q)}" style="flex:1;min-width:180px">
        <select id="tk">${opt(tf.kind, [['', 'Actions et ETF'], ['equity', 'Actions'], ['etf', 'ETF']])}</select>
        <select id="tm"><option value="">Toutes les places</option>${r.places.map(m => `<option ${tf.mic === m ? 'selected' : ''}>${J.esc(m)}</option>`).join('')}</select>
        <select id="tfdb">${opt(tf.fdb, [['', 'Filtre FinanceDatabase : tous'], ['kept', 'Conservés'], ['removed', 'Écartés']])}</select>
        <select id="ty">${opt(tf.yahoo, [['', 'Filtre Yahoo : tous'], ['kept', 'Retenus'], ['removed', 'Écartés'], ['pending', 'En attente'], ['secondary', 'Cotations secondaires']])}</select>
        <select id="tfin">${opt(tf.final, [['', 'Catalogue : tous'], ['1', 'Dans mon catalogue'], ['0', 'Hors catalogue']])}</select>
        <select id="td">${opt(tf.daily, [['', 'Historique quotidien : tous'], ['complete', 'Complet'], ['partial', 'Incomplet'], ['absent', 'Absent']])}</select></div>
      ${r.raw_total ? '' : '<div class="notice" style="margin:0 18px 12px">Aucun titre connu : importez et filtrez FinanceDatabase (page FinanceDatabase).</div>'}
      <div class="table-wrap"><table><thead><tr>${th('name', 'Titre')}${th('mic', 'Place · type')}<th>FinanceDatabase</th><th>Yahoo</th><th>Mon catalogue</th><th>Motif</th>${th('price_time', 'Dernier cours')}${th('closes', 'Quotidien')}<th>15 min</th><th>Mise à jour / problème</th></tr></thead><tbody>
      ${r.rows.map(x => `<tr ${x.in_final && x.lid ? `data-id="${x.lid}" style="cursor:pointer"` : ''}><td><b>${J.esc(x.name)}</b><div class="small muted">${J.esc(x.symbol)} · ${J.esc(x.isin || '')} · ${J.esc(x.country || '')}${x.category ? ' · ' + J.esc(x.category) : ''}</div></td>
        <td>${J.esc(x.mic)}<div class="small muted">${x.kind === 'etf' ? 'ETF' : 'Action'}</div></td><td>${badge(x.fdb_state)}</td><td>${badge(x.y_state)}</td>
        <td>${x.in_final ? '<span class="badge ok">Oui</span>' : '<span class="badge ko">Non</span>'}${x.held ? ' <span class="badge accent">détenu</span>' : ''}</td>
        <td class="small">${x.reason ? `<b>${J.esc(x.reason.stage)}</b>${x.reason.rule ? ' · ' + J.esc(x.reason.rule) : ''}<div class="muted">${J.esc(x.reason.detail || '')}</div>` : '–'}</td>
        <td class="num small">${x.price != null ? J.num(x.price, 2) + ' ' + J.esc(x.pcur || '') + `<div class="muted">${x.price_time ? J.dateTime(x.price_time) : ''}</div>` : '–'}</td>
        <td>${x.in_final ? badge(x.d_state) + `<div class="small muted">${x.closes_count != null ? x.closes_count + ' séances' : ''}</div>` : '–'}</td><td>${x.in_final ? (x.intraday_state === 'na' ? '<span class="small muted">non géré</span>' : badge(x.intraday_state)) : '–'}</td>
        <td class="small">${x.issue ? `<span class="warn">${J.esc(x.issue)}</span>` : (x.quote_at ? 'Infos Yahoo ' + J.ago(x.quote_at) : '–')}</td></tr>`).join('') || '<tr><td colspan="10" class="empty">Aucun titre.</td></tr>'}</tbody></table></div>
      <div class="row between" style="padding:12px 18px"><span class="muted small">${nf(r.total)} titres sur ${nf(r.raw_total)} connus</span><span class="row gap-s"><button class="btn small" id="tp" ${r.page <= 1 ? 'disabled' : ''}>←</button><span class="small">Page ${r.page} / ${r.pages}</span><button class="btn small" id="tn" ${r.page >= r.pages ? 'disabled' : ''}>→</button></span></div></div>`;
    const go = () => { tf.q = J.$('#tq').value.trim(); tf.kind = J.$('#tk').value; tf.mic = J.$('#tm').value; tf.fdb = J.$('#tfdb').value; tf.yahoo = J.$('#ty').value; tf.final = J.$('#tfin').value; tf.daily = J.$('#td').value; tf.page = 1; titres(); };
    let t; J.$('#tq').oninput = () => { clearTimeout(t); t = setTimeout(go, 400); }; ['tk', 'tm', 'tfdb', 'ty', 'tfin', 'td'].forEach(i => J.$('#' + i).onchange = go);
    J.$('#tp').onclick = () => { tf.page--; titres(); }; J.$('#tn').onclick = () => { tf.page++; titres(); };
    J.$$('th[data-sort]').forEach(h => h.onclick = () => { if (tf.sort === h.dataset.sort) tf.dir = tf.dir === 'asc' ? 'desc' : 'asc'; else { tf.sort = h.dataset.sort; tf.dir = 'asc'; } titres(); });
    J.$$('tr[data-id]').forEach(tr => tr.onclick = () => location.href = 'titre.html?id=' + tr.dataset.id);
  }

  // ───────── rattrapage automatique (cron) ─────────
  function catchupCard(k, c) {
    const open = k.open || [], lost = k.unrecoverable || [], d = k.daily || {};
    const pending = open.length + (d.waiting || 0);
    const upToDate = !pending && !lost.length && !d.given_up;
    const head = lost.length || d.given_up ? ['ko', 'Des données ne sont pas récupérables'] : pending ? ['wait', 'Rattrapage en cours'] : ['ok', 'Tout est à jour'];
    return `<div class="card" style="margin-top:16px"><div class="row between"><h2 style="margin:0">Rattrapage automatique</h2><span class="badge ${head[0]}">${head[1]}</span></div>
      <p class="small muted">À chaque passage du cron : les barres de 15 minutes manquantes des ${k.sessions_kept} dernières séances et les clôtures quotidiennes en retard sont redemandées, avec un délai croissant entre les tentatives (aucune intervention nécessaire, même après une panne de Yahoo ou du cron). Un créneau sans transaction n’est pas un manque : seuls les vrais trous sont rattrapés.</p>
      ${k.cooldown_until ? `<div class="notice">Yahoo a refusé les requêtes (429) : rattrapage en pause jusqu’à ${J.dateTime(k.cooldown_until)} UTC.</div>` : ''}
      <p class="small" style="margin:6px 0">Dernière vérification des trous : <b>${k.last_check ? J.dateTime(k.last_check) + ' UTC' : 'jamais'}</b>${upToDate && k.last_check ? ' · aucun retard connu' : ''}</p>
      ${open.length ? `<h3 style="margin:10px 0 4px">Barres de 15 minutes à compléter</h3><div class="table-wrap"><table><thead><tr><th>Place</th><th>Séance</th><th>Titres</th><th>Tentatives</th><th>Depuis</th><th>Prochaine tentative</th><th>Constat</th></tr></thead><tbody>${open.map(o => `<tr><td>${J.esc(o.mic)}</td><td>${J.esc(o.session)}</td><td class="num">${o.titles == null ? 'tous' : nf(o.titles)}</td><td class="num">${o.tries}</td><td>${J.dateTime(o.since)}</td><td>${J.dateTime(o.next_try)}</td><td class="small">${J.esc(o.note)}</td></tr>`).join('')}</tbody></table></div>` : ''}
      ${d.waiting || d.given_up ? `<h3 style="margin:10px 0 4px">Clôtures quotidiennes</h3><p class="small" style="margin:0">${nf(d.waiting)} titre(s) en attente de leur dernière clôture (nouvelle tentative automatique) · ${nf(d.given_up)} abandonné(s) après 24 h (le fournisseur ne publie pas cette clôture)${d.sample && d.sample.length ? ' · par ex. ' + J.esc(d.sample.join(', ')) : ''}</p>` : ''}
      ${lost.length ? `<h3 style="margin:10px 0 4px">Non récupérables</h3>${lost.map(u => `<div class="reason fail" style="margin-bottom:6px"><span class="mark">✗</span><span class="small"><b>${J.esc(u.mic)} · séance du ${J.esc(u.session)}</b> · abandonnée le ${J.dateTime(u.at)} après ${u.tries} tentative(s)<br>${J.esc(u.why)}</span></div>`).join('')}` : ''}</div>`;
  }

  // ───────── Cron ─────────
  async function cron() {
    const s = await J.api('admin/cron'), c = s.cron, site = s.site;
    const yes = c.observed && c.state === 'ok';
    const st = t => t.stats;
    page.innerHTML = `${runBar()}
      <div class="card"><h2>Le cron fonctionne-t-il ?</h2>
        <div class="grid cols-4"><div class="kpi"><span class="l">Cron installé et observé</span><span class="v"><span class="badge ${yes ? 'ok' : 'ko'}">${yes ? 'Oui' : 'Non'}</span></span><span class="small muted">${J.esc(c.label)}</span></div>
          <div class="kpi"><span class="l">Dernier passage réel</span><span class="v" style="font-size:18px">${c.last_at ? J.dateTime(c.last_at) : 'jamais'}</span><span class="small muted">${c.last_at ? J.esc(c.last_done || 'rien à faire') + ' · durée ' + dur(c.last_duration_s) : ''}</span></div>
          <div class="kpi"><span class="l">Prochain passage attendu</span><span class="v" style="font-size:18px">${c.next_at ? J.dateTime(c.next_at) : '–'}</span><span class="small muted">réglé : toutes les <input id="cr-int" type="number" min="1" max="60" value="${c.expected_minutes}" style="width:56px"> min<br>${c.measured_minutes ? 'observé : toutes les ' + c.measured_minutes + ' min (médiane des ' + c.passes_seen + ' derniers passages)' : 'fréquence réelle : mesure en cours (' + c.passes_seen + ' passage' + (c.passes_seen > 1 ? 's' : '') + ' vu' + (c.passes_seen > 1 ? 's' : '') + ')'}</span></div>
          <div class="kpi"><span class="l">Clé cron sur le site</span><span class="v" style="font-size:18px">${site.cron_key_present ? 'Présente' : 'Absente'}</span><span class="small muted">adresse : ${J.esc(site.cron_path)}</span></div></div>
        ${s.diagnosis.length ? `<div class="notice" style="margin-top:12px"><b>Diagnostic</b><ul style="margin:6px 0 0 18px">${s.diagnosis.map(d => `<li class="small">${J.esc(d)}</li>`).join('')}</ul></div>` : '<p class="small muted" style="margin:10px 0 0">Aucun problème détectable.</p>'}
        ${!site.cron_key_present ? '<div class="notice err" style="margin-top:10px">Le site n’a pas de clé cron : l’adresse du cron répondra « clé absente ».</div>' : ''}
        <div class="row gap-s" style="margin-top:12px;flex-wrap:wrap"><button class="btn" id="cr-test">Tester le déclenchement</button><button class="btn" id="cr-run">Lancer une collecte maintenant</button><button class="btn" id="cr-maint">Lancer l’entretien maintenant</button><button class="btn" id="cr-etf">Relancer les ETF seuls</button><span class="small muted">Le test lance un passage comme le ferait le cron, sans le compter comme passage du cron. La collecte lance « Importer / mettre à jour les historiques ».</span></div>
        ${c.last_test ? `<p class="small muted" style="margin:8px 0 0">Dernier test manuel : ${J.dateTime(c.last_test.at)} · ${J.esc(c.last_test.done || '')}</p>` : ''}</div>
      <div class="card" style="margin-top:16px"><div class="row between"><h2 style="margin:0">Ce que fait le cron</h2><button class="btn primary" id="cr-save">Enregistrer</button></div>
        <p class="small muted">Uniquement l’entretien des historiques et cotations du catalogue final (et des titres détenus). Il n’importe jamais FinanceDatabase, ne filtre jamais, ne change jamais le catalogue. Après la collecte quotidienne, les indicateurs de l’Explorer sont recalculés sans nouvelle sélection.</p>
        <div class="grid cols-2">${s.tasks.map(t => { const k = st(t); return `<div class="card" style="margin:0"><div class="row between"><b>${J.esc(t.label)}</b><label class="small row gap-s"><input type="checkbox" data-t="${t.id}" data-f="enabled" ${t.enabled ? 'checked' : ''}> active</label></div>
          <p class="small muted" style="margin:4px 0">${J.esc(t.help)}</p>${Object.entries(t.params).map(([key, p]) => `<div class="small">${J.esc(p.label)} <input type="number" data-t="${t.id}" data-f="${key}" min="${p.min}" max="${p.max}" value="${p.value}" style="width:64px"></div>`).join('')}
          <p style="margin:8px 0 4px"><span class="badge ${TSTATE[t.state][0]}">${TSTATE[t.state][1]}</span> <span class="small muted">${J.esc(t.state_detail)}</span></p>
          <div class="small">Dernière collecte : ${t.last ? J.dateTime(t.last.started_at) + ' · ' + dur(t.last.duration_s) + ' (moyenne ' + dur(t.avg_duration_s) + ')' : 'jamais'}<br>Prochaine : ${t.next ? J.dateTime(t.next) + ' UTC' : '–'}</div>
          ${k ? `<div class="table-wrap"><table><tbody><tr><td>Titres traités</td><td class="num">${nf(k.titles)}</td></tr><tr><td>Déjà à jour / complets</td><td class="num">${nf(k.up_to_date)}</td></tr><tr><td>Données ajoutées</td><td class="num">${nf(k.added)}</td></tr><tr><td>Déjà présentes</td><td class="num">${nf(k.present)}</td></tr><tr><td>Sans réponse ou en erreur</td><td class="num ${k.errors ? 'warn' : ''}">${nf(k.errors)}</td></tr></tbody></table></div><div class="small muted">Dernier passage : ${J.dateTime(k.at)}</div>` : '<p class="small muted">Aucun chiffre : pas encore de collecte.</p>'}
          ${t.last ? `<div class="small"><a href="#" data-job="${t.last.id}">Détail de la dernière exécution</a></div>` : ''}</div>`; }).join('')}</div>
        ${s.maintenance ? `<p class="small muted" style="margin:10px 0 0">Dernier entretien après collecte : ${J.dateTime(s.maintenance.started_at)} · ${dur(s.maintenance.duration_s)} · ${J.esc(s.maintenance.summary || '')} <a href="#" data-job="${s.maintenance.id}">Détail</a></p>` : ''}</div>
      ${catchupCard(s.catchup, c)}
      <div class="card" style="margin-top:16px"><h2>Erreurs du cron <span class="small muted">· 7 derniers jours</span></h2>
        ${s.errors.length ? s.errors.map(l => `<div class="reason ${l.level === 'error' ? 'fail' : 'missing'}" style="margin-bottom:6px"><span class="mark">${l.level === 'error' ? '✗' : '!'}</span><span class="small"><b>${J.esc(l.source === 'passage du cron' ? 'Passage du cron · ' + l.job_type : jobName(l.job_type))}</b> · ${J.dateTime(l.at)}<br>${J.esc(l.message)} ${l.job_id ? `<a href="#" data-job="${l.job_id}">Détail</a>` : ''}</span></div>`).join('') : '<span class="muted">Aucune erreur enregistrée sur 7 jours (traitements, passages, appels).</span>'}
        ${site.log_errors && site.log_errors.length ? `<h3 style="margin:14px 0 6px">Journal brut du cron (logs/cron.log) — lignes d’erreur</h3><pre class="small" style="white-space:pre-wrap;margin:0;max-height:200px;overflow:auto">${J.esc(site.log_errors.join('\n'))}</pre>` : '<p class="small muted" style="margin:10px 0 0">Journal brut du cron : aucune ligne d’erreur.</p>'}
        ${site.rejected && site.rejected.length ? `<h3 style="margin:14px 0 6px">Appels du cron refusés (mauvaise clé, clé absente…)</h3><pre class="small" style="white-space:pre-wrap;margin:0;max-height:160px;overflow:auto">${J.esc(site.rejected.join('\n'))}</pre>` : '<p class="small muted" style="margin:6px 0 0">Aucun appel refusé.</p>'}</div>`;
    bindJobLinks(); poll();
    J.$('#cr-save').onclick = async () => {
      const cfg = { cron_interval_minutes: +J.$('#cr-int').value };
      J.$$('[data-t]').forEach(el => { const t = el.dataset.t; cfg[t] = cfg[t] || {}; cfg[t][el.dataset.f] = el.type === 'checkbox' ? el.checked : +el.value; });
      try { await J.post('admin/cron/save', cfg); J.toast('Planification enregistrée'); render(); } catch (e) { J.toast(e.message); }
    };
    J.$('#cr-test').onclick = async () => { try { const r = await J.post('admin/cron/test'); J.toast(r.note); setTimeout(render, 6000); } catch (e) { J.toast(e.message); } };
    J.$('#cr-maint').onclick = () => run('maintenance', 'Lancer l’entretien maintenant', 'Sauvegarde des données utilisateur, cours, indicateurs, ETF, suivi, rétention. Démarre tout de suite ; refusé si un calcul est déjà en cours.');
    J.$('#cr-etf').onclick = () => run('etf', 'Relancer la similarité des ETF', 'Recalcule seulement la similarité des ETF. Ne touche ni aux classements ni aux sauvegardes.');
    J.$('#cr-run').onclick = () => run('history', 'Lancer une collecte maintenant', 'Lance « Importer / mettre à jour les historiques » sur le catalogue final.');
  }

  // ───────── journaux ─────────
  const lf = { type: '', status: '', trigger: '', since: '', page: 1 };
  async function logs() {
    const r = await J.api('admin/jobs', { params: Object.fromEntries(Object.entries(lf).filter(([, v]) => v !== '')) });
    const opt = (cur, list) => list.map(([v, l]) => `<option value="${v}" ${cur === v ? 'selected' : ''}>${l}</option>`).join('');
    page.innerHTML = `<div class="card" style="padding:0"><div class="row" style="padding:14px 18px;gap:10px;flex-wrap:wrap"><select id="lf-t"><option value="">Tous les types</option>${opt(lf.type, [['fdb_import', 'Import FinanceDatabase'], ['fdb_filter', 'Filtrage FinanceDatabase'], ['yahoo_info', 'Import des informations Yahoo'], ['yahoo_filter', 'Filtrage Yahoo'], ['history', 'Mise à jour des historiques'], ['maintenance', 'Entretien après collecte'], ['intraday', 'Barres 15 min'], ['daily', 'Clôtures quotidiennes']])}</select>
      <select id="lf-s"><option value="">Tous statuts</option>${opt(lf.status, Object.entries(STATE).map(([k, v]) => [k, v[1]]))}</select><select id="lf-g"><option value="">Manuel et auto</option>${opt(lf.trigger, [['admin', 'Manuel'], ['cron', 'Automatique']])}</select><input id="lf-d" type="date" value="${J.esc(lf.since)}"></div>
      <div class="table-wrap"><table><thead><tr><th>#</th><th>Traitement</th><th>Départ</th><th>Durée</th><th>Origine</th><th>Statut</th><th class="num">OK</th><th class="num">Erreurs</th><th>Résumé</th></tr></thead><tbody>
      ${r.jobs.map(j => `<tr data-job="${j.id}" style="cursor:pointer"><td>${j.id}</td><td>${J.esc(jobName(j.job_type))}</td><td>${J.dateTime(j.started_at)}</td><td>${dur(j.duration_s)}</td><td>${j.trigger_by === 'admin' ? 'Manuel' : 'Auto'}</td><td><span class="badge ${STATE[j.status][0]}">${STATE[j.status][1]}</span></td><td class="num">${j.items_ok ?? '–'}</td><td class="num">${j.items_error}</td><td class="small muted">${J.esc(j.summary || '')}</td></tr>`).join('') || '<tr><td colspan="9" class="empty">Aucun traitement.</td></tr>'}</tbody></table></div>
      <div class="row between" style="padding:12px 18px"><span class="muted small">${nf(r.total)} traitements</span><span class="row gap-s"><button class="btn small" id="lp" ${r.page <= 1 ? 'disabled' : ''}>←</button><span class="small">Page ${r.page} / ${r.pages}</span><button class="btn small" id="ln" ${r.page >= r.pages ? 'disabled' : ''}>→</button></span></div></div>`;
    const go = () => { lf.type = J.$('#lf-t').value; lf.status = J.$('#lf-s').value; lf.trigger = J.$('#lf-g').value; lf.since = J.$('#lf-d').value; lf.page = 1; logs(); };
    ['lf-t', 'lf-s', 'lf-g', 'lf-d'].forEach(i => J.$('#' + i).onchange = go);
    J.$('#lp').onclick = () => { lf.page--; logs(); }; J.$('#ln').onclick = () => { lf.page++; logs(); };
    J.$$('tr[data-job]').forEach(tr => tr.onclick = () => jobDialog(tr.dataset.job));
  }
  async function jobDialog(id) {
    const d = await J.api('admin/job', { params: { id } }), j = d.job;
    const funnels = Object.entries(d.funnels).filter(([, v]) => v.length).map(([k, v]) => `<h4>Entonnoir ${k === 'catalogue' ? 'FinanceDatabase' : 'Yahoo Finance'} (figé à la fin du traitement)</h4>${funnelTable(v)}`).join('');
    J.dialog({ title: 'Traitement n° ' + j.id + ' · ' + jobName(j.job_type), wide: true, body: `<p class="small">Départ ${J.dateTime(j.started_at)} · fin ${j.finished_at ? J.dateTime(j.finished_at) : '–'} · ${j.items_ok ?? '–'} réussis · ${j.items_error} erreurs · <span class="badge ${STATE[j.status][0]}">${STATE[j.status][1]}</span><br>${J.esc(j.summary || '')}</p>
      ${d.steps.length ? `<h4>Étapes</h4><div class="table-wrap"><table><thead><tr><th>#</th><th>Étape</th><th class="num">Durée</th><th>Détail</th></tr></thead><tbody>${d.steps.map(s => `<tr><td>${s.seq}</td><td>${J.esc(s.name)}</td><td class="num">${dur(s.duration_ms / 1000)}</td><td class="small">${J.esc(s.detail || '')}</td></tr>`).join('')}</tbody></table></div>` : '<p class="muted small">Ce traitement n’a pas enregistré d’étapes détaillées.</p>'}
      ${funnels}<p class="small muted">Pour consulter les titres exclus à chaque étape : <a href="#fdb">FinanceDatabase</a> · <a href="#yahoo">Yahoo Finance</a> (état de la dernière exécution).</p>
      <h4>Messages</h4>${d.logs.map(l => `<div class="reason ${l.level === 'error' ? 'fail' : 'missing'}" style="margin-bottom:6px"><span class="mark">${l.level === 'error' ? '✗' : '!'}</span><span class="small">${J.dateTime(l.logged_at)} · ${J.esc(l.message)}</span></div>`).join('') || '<p class="muted">Aucun message : traitement sans incident.</p>'}`, actions: [{ label: 'Fermer', run: () => { } }] });
  }

  async function users() {
    const r = await J.api('admin/users');
    page.innerHTML = `<div class="card"><div class="row between"><h2 style="margin:0">Utilisateurs</h2><button class="btn primary" id="add-u">Créer un compte</button></div><div class="table-wrap"><table><thead><tr><th>Identifiant</th><th>E-mail</th><th class="num">Portefeuilles</th><th>Dernière connexion</th><th>Rôle</th><th></th></tr></thead><tbody>
      ${r.users.map(u => `<tr><td><b>${J.esc(u.username)}</b></td><td>${J.esc(u.email || '–')}</td><td class="num">${u.portfolios}</td><td>${J.dateTime(u.last_login)}</td><td>${u.is_admin == 1 ? '<span class="badge accent">Admin</span>' : 'Utilisateur'} ${u.active == 1 ? '' : '<span class="badge ko">Désactivé</span>'}</td>
        <td class="num"><button class="btn small" data-pw="${u.id}">Mot de passe</button> <button class="btn small" data-act="${u.id}" data-v="${u.active == 1 ? 0 : 1}">${u.active == 1 ? 'Désactiver' : 'Réactiver'}</button></td></tr>`).join('')}</tbody></table></div></div>`;
    J.$('#add-u').onclick = () => J.dialog({ title: 'Créer un compte', body: J.field('Identifiant', '<input id="nu">') + J.field('E-mail (facultatif)', '<input id="ne" type="email">') + J.field('Mot de passe (10 caractères minimum)', '<input id="np" type="password" autocomplete="new-password">') + '<label class="row gap-s"><input type="checkbox" id="na"> Administrateur</label>', actions: [{ label: 'Annuler', run: () => { } }, { label: 'Créer', cls: 'primary', run: async d => { await J.post('admin/user/create', { username: J.$('#nu', d).value, email: J.$('#ne', d).value, password: J.$('#np', d).value, is_admin: J.$('#na', d).checked }); render(); } }] });
    J.$$('[data-act]').forEach(b => b.onclick = async () => { await J.post('admin/user/update', { id: +b.dataset.act, active: b.dataset.v === '1' }); render(); });
    J.$$('[data-pw]').forEach(b => b.onclick = () => J.dialog({ title: 'Nouveau mot de passe', body: J.field('Mot de passe (10 caractères minimum)', '<input id="pw" type="password" autocomplete="new-password">') + '<p class="small muted">Ses sessions ouvertes seront fermées.</p>', actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async d => { await J.post('admin/user/update', { id: +b.dataset.pw, password: J.$('#pw', d).value }); J.toast('Mot de passe modifié'); } }] }));
  }
  async function settings() {
    const s = (await J.api('admin/system')).settings;
    page.innerHTML = `<div class="notice">Les seuils du catalogue et du préfiltre Yahoo se règlent désormais dans <a href="#fdb">FinanceDatabase</a> et <a href="#yahoo">Yahoo Finance</a>.</div>
      <div class="grid cols-2" style="margin-top:14px"><div class="card"><h2>Historique 15 minutes</h2>${J.field('Séances conservées (5 à 60)', `<input id="ret" type="number" min="5" max="60" value="${s.intraday_retention_sessions ?? 20}">`)}<button class="btn primary" id="sv-ret" style="margin-top:12px">Enregistrer</button></div>
      <div class="card"><h2>Inscriptions</h2><p class="muted small">Un mot d’invitation permet aux personnes qui le connaissent de créer un compte. Vide = inscriptions fermées. ${s.invite_code ? 'Un mot est actuellement défini.' : 'Aucun mot défini.'}</p>${J.field('Nouveau mot d’invitation', '<input id="inv" autocomplete="off">')}<button class="btn primary" id="sv-inv" style="margin-top:12px">Enregistrer</button></div></div>
      <div class="card" style="margin-top:16px"><h2>Base de données</h2><div id="tb"><span class="spinner"></span></div></div>`;
    const save = async (name, value) => { await J.post('admin/settings', { name, value }); J.toast('Réglage enregistré'); };
    J.$('#sv-ret').onclick = () => save('intraday_retention_sessions', J.$('#ret').value).catch(e => J.toast(e.message));
    J.$('#sv-inv').onclick = () => save('invite_code', J.$('#inv').value).then(render).catch(e => J.toast(e.message));
    const sys = await J.api('admin/system');
    J.$('#tb').innerHTML = `<p class="small muted">${J.num(sys.total_mb, 0)} Mo utilisés (plafond hébergeur : 3 072 Mo)</p><div class="table-wrap" style="max-height:260px;overflow:auto"><table><tbody>${sys.tables.map(t => `<tr><td>${J.esc(t.name)}</td><td class="num">${J.num(+t.rows, 0)} lignes</td><td class="num">${J.num(+t.mb, 1)} Mo</td></tr>`).join('')}</tbody></table></div>`;
  }
  render();
})();
