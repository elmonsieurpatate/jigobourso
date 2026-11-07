/* Administration → Colonnes : colonnes visibles, ordre, largeurs, tri par défaut et filtres initiaux des tableaux Explorer / Scores,
   pour l'ordinateur et le mobile (quatre configurations indépendantes). Aucun calcul : seulement des préférences d'affichage. */
(() => {
  const E = s => J.esc(String(s ?? ''));
  const PAGES = [['explorer', 'Explorer / Stratégie'], ['scores', 'Scores / Classement']];
  const DEVICES = [['desktop', 'Ordinateur'], ['mobile', 'Mobile']];
  const VERDICTS = [['retained', 'Retenues'], ['excluded', 'Exclues'], ['all', 'Toutes']];
  let MINE = false;
  const R = () => MINE ? 'table-layouts' : 'admin/table-layouts';
  let root, data, page = 'explorer', device = 'desktop', draft = null, base = '', notice = null, busy = false;

  const key = () => page + '.' + device;
  const catalog = () => data.catalog[page].columns;
  const meta = id => catalog().find(c => c.id === id) || { id, label: id, group: '' };
  const clone = o => JSON.parse(JSON.stringify(o));
  const dirty = () => draft && JSON.stringify(draft) !== base;

  function open() {
    draft = clone(data.layouts[key()]);
    base = JSON.stringify(draft);
    notice = null;
  }
  async function reload() { data = await J.api(R()); open(); }

  async function guard(fn) {
    if (dirty() && !await J.confirm('Modifications non enregistrées', 'Les changements de cette configuration seront perdus.', 'Abandonner')) return;
    fn(); open(); paint();
  }

  // ───────── aperçu fidèle : mêmes colonnes, même ordre, mêmes largeurs, tri indiqué ─────────
  const SAMPLE = [
    { name: ['TTE', 'TotalEnergies SE'], price: '62,40 €', change: '+0,52 %', pct: '+3,18 %', r2: '0,86', vol: '1,42 %', turn: '48,2 M€', avg: '3 120 000', score: '78,6', rank: '1', kind: 'Action', mic: 'XPAR', sector: 'Énergie', status: ['Retenue', 'ok'] },
    { name: ['SPYL', 'SPDR S&P 500 ETF'], price: '14,81 €', change: '-0,12 %', pct: '+1,04 %', r2: '0,71', vol: '0,88 %', turn: '9,6 M€', avg: '640 000', score: '64,2', rank: '2', kind: 'ETF', mic: 'XETR', sector: 'Actions US', status: ['Exclue', 'no'] },
    { name: ['ABC', 'Alpha Bêta Corp'], price: '—', change: '—', pct: '—', r2: '—', vol: '—', turn: '—', avg: '—', score: '—', rank: '—', kind: 'Action', mic: 'XNAS', sector: '—', status: ['Indéterminée', 'na'] },
  ];
  function sample(id, r) {
    if (id === 'rank' || id === 'rank_simple' || id === 'rank_complex') return r.rank;
    if (id === 'name') return `<b>${E(r.name[0])}</b> <span class="muted">${E(r.name[1])}</span>`;
    if (id === 'status') return `<i class="ac-badge ${r.status[1]}">${r.status[0]}</i>`;
    if (id === 'kind') return r.kind;
    if (id === 'market') return r.mic;
    if (id === 'sector') return r.sector;
    if (id === 'price') return r.price;
    if (id === 'change') return r.change;
    if (id === 'simple' || id === 'complex') return r.score;
    if (id === 'trend') return r.price === '—' ? '—' : '<svg width="70" height="18" viewBox="0 0 70 18" aria-hidden="true"><polyline fill="none" stroke="currentColor" stroke-width="1.5" points="1,15 14,11 26,13 40,6 54,8 69,2"/></svg>';
    if (id === 'volatility') return r.vol;
    if (id === 'drawdown') return r.price === '—' ? '—' : '-8,4 %';
    if (id === 'turnover') return r.turn;
    if (id === 'avgVolume') return r.avg;
    if (id.startsWith('r2')) return r.r2;
    return r.pct;                                                     // performances et pentes
  }
  function preview() {
    const cols = draft.columns.filter(c => c.visible);
    const prim = draft.sort[0];
    const w = c => c.width ? ` style="width:${c.width}px;min-width:${c.width}px"` : '';
    return `<div class="ac-frame ${device}"><div class="ac-scroll"><table class="ac-table"><thead><tr>${cols.map(c => `<th${w(c)}${meta(c.id).hint ? ` title="${E(meta(c.id).hint)}"` : ''}>${E(meta(c.id).label)}${prim && prim.key === c.id ? (prim.dir === 'asc' ? ' ↑' : ' ↓') : ''}</th>`).join('')}</tr></thead>
      <tbody>${SAMPLE.map(r => `<tr>${cols.map(c => `<td${w(c)}>${sample(c.id, r)}</td>`).join('')}</tr>`).join('')}</tbody></table></div></div>
      <p class="small muted" style="margin:6px 0 0">Valeurs d’exemple : seuls l’ordre, la visibilité et les largeurs sont réels. ${device === 'mobile' ? 'Cadre de 375 px ; le tableau défile horizontalement.' : ''}</p>`;
  }

  // ───────── sections ─────────
  const seg = (items, cur, attr) => `<div class="seg" role="radiogroup">${items.map(([v, l]) => `<button type="button" role="radio" aria-checked="${v === cur}" class="${v === cur ? 'on' : ''}" ${attr}="${v}">${l}</button>`).join('')}</div>`;

  function columnsSection() {
    const rows = draft.columns.map((c, i) => `<li class="ac-row ${c.visible ? '' : 'off'}" data-id="${E(c.id)}">
        <span class="ac-handle" data-handle title="Glisser pour déplacer" aria-hidden="true">⠿</span>
        <span class="ac-pos">${i + 1}</span>
        <label class="ac-vis"><input type="checkbox" data-vis="${E(c.id)}" ${c.visible ? 'checked' : ''} ${c.id === 'name' ? 'disabled title="Colonne d’identification : toujours visible"' : ''}><span class="ac-name"${meta(c.id).hint ? ` title="${E(meta(c.id).hint)}"` : ''}>${E(meta(c.id).label)}</span> <span class="small muted">${E(meta(c.id).group || '')}</span></label>
        <span class="ac-width"><select data-wmode="${E(c.id)}" aria-label="Largeur de ${E(meta(c.id).label)}"><option value="auto" ${c.width ? '' : 'selected'}>Auto</option><option value="custom" ${c.width ? 'selected' : ''}>Fixe</option></select>${c.width ? `<input type="number" min="48" max="480" step="1" value="${c.width}" data-w="${E(c.id)}" aria-label="Largeur en pixels"> <span class="small muted">px</span>` : ''}</span>
        <span class="ac-move"><button type="button" class="btn small" data-up="${E(c.id)}" ${i === 0 ? 'disabled' : ''} aria-label="Monter ${E(meta(c.id).label)}">↑</button><button type="button" class="btn small" data-down="${E(c.id)}" ${i === draft.columns.length - 1 ? 'disabled' : ''} aria-label="Descendre ${E(meta(c.id).label)}">↓</button></span></li>`).join('');
    const visible = draft.columns.filter(c => c.visible).length;
    return `<div class="card"><div class="row between wrap-s"><h2 style="margin:0">Colonnes <span class="small muted">${visible} visible${visible > 1 ? 's' : ''} sur ${draft.columns.length}</span></h2>
        <span class="small muted">Une colonne masquée garde sa position. Elle reste utilisable pour le tri.</span></div>
      <ol class="ac-list" id="ac-list">${rows}</ol></div>`;
  }
  function sortSection() {
    const opts = catalog().filter(c => c.sortable);
    const row = i => {
      const s = draft.sort[i];
      return `<div class="ac-sortrow"><span class="small muted">${i === 0 ? 'Tri principal' : i === 1 ? 'Puis par' : 'Puis par'}</span>
        <select data-sortkey="${i}" aria-label="Colonne de tri ${i + 1}"><option value="">${i === 0 ? 'Selon la stratégie (score par défaut, décroissant)' : '— aucun —'}</option>${opts.map(c => `<option value="${E(c.id)}" ${s && s.key === c.id ? 'selected' : ''}>${E(c.label)}</option>`).join('')}</select>
        ${s ? seg([['asc', 'Croissant'], ['desc', 'Décroissant']], s.dir, 'data-sortdir="' + i + '" data-v') : ''}</div>`;
    };
    const n = draft.sort.length;
    return `<div class="card"><h2 style="margin:0 0 4px">Tri par défaut</h2>
      <p class="small muted" style="margin:0 0 8px">Appliqué à l’ouverture de la page, sur tous les résultats (pas seulement la page affichée). Un clic sur une colonne reste prioritaire pendant la consultation. Les valeurs absentes sont toujours en dernier ; les égalités sont départagées par le rang général puis l’identifiant. Le rang global ne change jamais avec le tri.</p>
      ${row(0)}${n >= 1 ? row(1) : ''}${n >= 2 ? row(2) : ''}</div>`;
  }
  function filtersSection() {
    const f = draft.filters;
    return `<div class="card"><h2 style="margin:0 0 8px">Filtres et affichage initiaux</h2>
      <div class="ac-filter"><span>Statut de stratégie</span>${seg(VERDICTS, f.verdict, 'data-verdict')}</div>
      ${page === 'explorer' ? `<div class="ac-filter"><span>Lignes par page</span><select data-pagesize aria-label="Lignes par page">${[25, 50, 100].map(n => `<option value="${n}" ${f.page_size === n ? 'selected' : ''}>${n}</option>`).join('')}</select></div>` : ''}
      <p class="small muted" style="margin:8px 0 0">Valeurs initiales : l’utilisateur peut ensuite les changer pendant sa consultation. Les catégories des filtres secondaires (pays, secteur, place, type d’actif…) se règlent dans <a href="admin-categories-test.html">Filtres et catégories</a>.</p></div>`;
  }

  function paint() {
    const d = dirty();
    root.innerHTML = `<div class="ac-head card"><div class="ac-pick"><div><div class="small muted">Page</div>${seg(PAGES, page, 'data-page')}</div><div><div class="small muted">Affichage</div>${seg(DEVICES, device, 'data-device')}</div></div>
        <div class="small muted">Quatre configurations indépendantes : modifier celle-ci ne touche pas les trois autres. ${data.saved[key()] ? 'Configuration enregistrée.' : 'Valeurs par défaut (rien d’enregistré).'}</div></div>
      ${notice ? `<div class="notice ${notice.err ? 'err' : 'ok'}" role="status">${E(notice.text)}</div>` : ''}
      <div class="ac-grid"><div>${columnsSection()}${sortSection()}${filtersSection()}</div>
        <div class="ac-side"><div class="card"><h2 style="margin:0 0 8px">Aperçu</h2>${preview()}</div></div></div>
      <div class="ac-actions" role="group" aria-label="Actions"><span class="small ${d ? 'warn' : 'muted'}">${d ? 'Modifications non enregistrées.' : 'Aucune modification.'}</span>
        <button class="btn" data-act="reset" ${busy ? 'disabled' : ''}>Réinitialiser aux valeurs par défaut</button><button class="btn" data-act="cancel" ${d && !busy ? '' : 'disabled'}>Annuler les modifications</button><button class="btn primary" data-act="save" ${d && !busy ? '' : 'disabled'}>Enregistrer</button></div>`;
  }

  // ───────── actions ─────────
  const move = (id, to) => { const i = draft.columns.findIndex(c => c.id === id); if (i < 0) return; const [c] = draft.columns.splice(i, 1); draft.columns.splice(Math.max(0, Math.min(draft.columns.length, to)), 0, c); };

  async function save() {
    busy = true; paint();
    try { data = await J.post(R() + '/save', { page, device, config: draft, revision: data.revision }); open(); notice = { text: 'Enregistré : ' + PAGES.find(p => p[0] === page)[1] + ' · ' + DEVICES.find(d => d[0] === device)[1] + '. Les trois autres configurations ne sont pas modifiées.' }; J.toast('Réglages enregistrés'); }
    catch (e) { notice = { err: true, text: e.message }; if (/autre session/.test(e.message)) { try { await reload(); } catch (_) { /* message déjà affiché */ } notice = { err: true, text: e.message }; } }
    busy = false; paint();
  }
  async function resetDefaults() {
    if (!await J.confirm('Réinitialiser', 'Revenir aux valeurs par défaut pour cette page et cet affichage ? Les trois autres configurations ne changent pas.', 'Réinitialiser')) return;
    busy = true; paint();
    try { data = await J.post(R() + '/save', { action: 'reset', page, device, revision: data.revision }); open(); notice = { text: 'Valeurs par défaut rétablies pour cette configuration.' }; }
    catch (e) { notice = { err: true, text: e.message }; }
    busy = false; paint();
  }

  function onClick(e) {
    const t = e.target.closest('button'); if (!t) return;
    if (t.dataset.page) { if (t.dataset.page !== page) guard(() => { page = t.dataset.page; }); return; }
    if (t.dataset.device) { if (t.dataset.device !== device) guard(() => { device = t.dataset.device; }); return; }
    if (t.dataset.up) { const i = draft.columns.findIndex(c => c.id === t.dataset.up); move(t.dataset.up, i - 1); paint(); const b = root.querySelector(`[data-up="${CSS.escape(t.dataset.up)}"]`); if (b && !b.disabled) b.focus(); return; }
    if (t.dataset.down) { const i = draft.columns.findIndex(c => c.id === t.dataset.down); move(t.dataset.down, i + 1); paint(); const b = root.querySelector(`[data-down="${CSS.escape(t.dataset.down)}"]`); if (b && !b.disabled) b.focus(); return; }
    if (t.dataset.verdict) { draft.filters.verdict = t.dataset.verdict; paint(); return; }
    if (t.dataset.sortdir !== undefined) { draft.sort[+t.dataset.sortdir].dir = t.dataset.v; paint(); return; }
    if (t.dataset.act === 'save') save();
    else if (t.dataset.act === 'cancel') { open(); paint(); }
    else if (t.dataset.act === 'reset') resetDefaults();
  }
  function onChange(e) {
    const t = e.target;
    if (t.dataset.vis) { draft.columns.find(c => c.id === t.dataset.vis).visible = t.checked; paint(); }
    else if (t.dataset.wmode) { const c = draft.columns.find(x => x.id === t.dataset.wmode); c.width = t.value === 'custom' ? 120 : null; paint(); }
    else if (t.dataset.w) { const c = draft.columns.find(x => x.id === t.dataset.w); const n = Math.round(+t.value); c.width = Number.isFinite(n) ? Math.max(48, Math.min(480, n)) : null; paint(); }
    else if (t.dataset.sortkey !== undefined) {
      const i = +t.dataset.sortkey, k = t.value;
      if (!k) draft.sort.splice(i); else { draft.sort = draft.sort.filter((s, j) => j === i || s.key !== k); const at = Math.min(i, draft.sort.length); if (draft.sort[at]) draft.sort[at].key = k; else draft.sort.push({ key: k, dir: 'desc' }); }
      paint();
    } else if (t.dataset.pagesize !== undefined) { draft.filters.page_size = +t.value; paint(); }
  }

  // Glisser-déposer au pointeur (souris, stylet et écran tactile) : on déplace le nœud pendant le geste, l'ordre est relu à la fin.
  function onPointerDown(e) {
    const h = e.target.closest('[data-handle]'); if (!h) return;
    const row = h.closest('.ac-row'), list = row.parentElement;
    e.preventDefault(); row.classList.add('drag');
    const startOrder = draft.columns.map(c => c.id).join();
    const moveFn = ev => {
      const rows = [...list.children].filter(r => r !== row);
      const after = rows.find(r => { const b = r.getBoundingClientRect(); return ev.clientY < b.top + b.height / 2; });
      if (after) { if (row.nextElementSibling !== after) list.insertBefore(row, after); } else list.appendChild(row);
      const b = list.getBoundingClientRect(); if (ev.clientY < 60) window.scrollBy(0, -12); else if (ev.clientY > innerHeight - 60) window.scrollBy(0, 12);
      void b;
    };
    const up = () => {
      window.removeEventListener('pointermove', moveFn); window.removeEventListener('pointerup', up); window.removeEventListener('pointercancel', up);
      const order = [...list.children].map(r => r.dataset.id);
      draft.columns = order.map(id => draft.columns.find(c => c.id === id));
      if (order.join() !== startOrder) notice = null;
      paint();
    };
    window.addEventListener('pointermove', moveFn); window.addEventListener('pointerup', up); window.addEventListener('pointercancel', up);
  }

  async function render(host, opts) {
    MINE = !!(opts && opts.mine);
    root = host;
    root.innerHTML = '<div class="empty"><span class="spinner"></span></div>';
    await reload();
    root.onclick = onClick; root.onchange = onChange; root.onpointerdown = onPointerDown;
    window.onbeforeunload = () => (dirty() ? 'Modifications non enregistrées' : undefined);
    paint();
  }
  window.AdminColumns = { render };
})();
