/* Page Suivi : résultats observés des classements passés, par stratégie, groupe et horizon. */
(async () => {
  if (!await J.init('suivi')) return;
  const s = await J.api('suivi'), page = J.$('#page');
  if (!s.days) { page.innerHTML = '<div class="empty">Aucun classement enregistré pour l’instant : le premier le sera cette nuit.</div>'; return; }
  const HZ = { 1: '1 séance (le lendemain)', 3: '3 séances', 5: '5 séances (1 semaine)', 21: '21 séances (environ 1 mois)', 63: '63 séances (environ 3 mois)' };
  const GROUPS = { equity: 'Actions', etf: 'ETF' };
  const NAMES = { '*': 'Toutes les stratégies', regular: 'Croissance régulière', fast: 'Croissance rapide', recovery: 'Rebond', low_volatility: 'Hausse calme', momentum: 'Momentum 6 mois (expérimental)' };
  Object.entries(s.presets).forEach(([k, p]) => { p.label = NAMES[k] || p.label; });
  let preset = '*', group = 'equity';
  const ready = Math.max(...Object.values(s.resolved_days));
  const warn = ready < 20
    ? `<div class="notice warn"><b>Trop tôt pour conclure.</b> ${ready} classement(s) ont un résultat mesuré à ce jour. En dessous d’une vingtaine de jours, une moyenne dépend surtout du hasard du marché.</div>` : '';
  const rebuilt = s.rebuilt_days
    ? `<div class="notice">${s.rebuilt_days} jour(s) sur ${s.days} ont été <b>reconstitués</b> après coup à partir des cours passés et des titres actuellement analysés (les titres disparus n’y figurent pas, ce qui flatte légèrement les résultats). Ils sont repérés par « reconstitué » dans la liste.</div>` : '';
  const stat = st => st ? `<td class="num">${st.n}</td><td class="num ${J.cls(st.mean)}">${J.pct(st.mean)}</td><td class="num">${J.pct(st.median)}</td><td class="num">${J.num(st.win_pct, 0)} %</td><td class="num ${J.cls(st.edge)}">${st.edge === null ? '–' : (st.edge > 0 ? '+' : '') + J.num(st.edge, 2) + ' pt'}</td><td class="num">${st.beat_pct === null ? '–' : J.num(st.beat_pct, 0) + ' %'}</td>`
    : '<td colspan="6" class="muted small">pas encore de résultat</td>';
  function draw() {
    const p = s.presets[preset], g = p.groups[group];
    J.$('#table').innerHTML = `<div class="table-wrap"><table><thead><tr><th>Horizon</th><th class="num">Cas</th><th class="num">Moyenne</th><th class="num">Médiane</th><th class="num">En hausse</th><th class="num">Écart vs univers</th><th class="num">Battent l’univers</th></tr></thead><tbody>
      ${s.horizons.map(h => `<tr><td>${HZ[h]}</td>${stat(g[h])}</tr>`).join('')}</tbody></table></div>
      <p class="small muted">« Écart vs univers » : rendement moyen des titres classés moins rendement moyen de tous les ${GROUPS[group].toLowerCase()} analysés le même jour, sur le même horizon, en points de pourcentage. Les classements de jours voisins se chevauchent : « Cas » ne compte donc pas autant d’observations indépendantes. Les jours « reconstitués » utilisent l’univers actuel (biais de survie).</p>`;
    J.$$('#presets button').forEach(b => b.classList.toggle('on', b.dataset.p === preset));
    J.$$('#groups button').forEach(b => b.classList.toggle('on', b.dataset.g === group));
    drawRecent();
  }
  function drawRecent() {
    const names = preset === '*' ? Object.keys(s.recent) : [preset];
    const byDay = {};
    names.forEach(n => (s.recent[n] || []).forEach(d => { (byDay[d.date] = byDay[d.date] || []).push(...d.entries.filter(e => e.group === group).map(e => ({ ...e, preset: n, origin: d.origin }))); }));
    const dates = Object.keys(byDay).sort().reverse();
    J.$('#recent').innerHTML = dates.map(d => {
      const rows = byDay[d], origin = rows.some(r => r.origin === 'rebuilt') ? ' · reconstitué' : '';
      const cell = (e, h) => e.returns[h] === undefined ? '<td class="num muted">–</td>' : `<td class="num ${J.cls(e.returns[h])}">${J.pct(e.returns[h], 1)}</td>`;
      return `<details><summary>${J.date(d)}${origin} · ${rows.length} titre(s)</summary><div class="table-wrap"><table><thead><tr><th>Titre</th><th>Stratégie</th><th class="num">Rang</th><th class="num">+1 séance</th><th class="num">+3</th><th class="num">+5</th></tr></thead><tbody>
        ${rows.map(e => `<tr><td><a href="titre.html?id=${e.id}"><b>${J.esc(e.symbol)}</b></a> <span class="small muted">${J.esc(e.name)}</span></td><td class="small">${J.esc(s.presets[e.preset].label)}</td><td class="num">${e.rank}</td>${[1, 3, 5].map(h => cell(e, h)).join('')}</tr>`).join('')}</tbody></table></div></details>`;
    }).join('') || '<div class="empty">Rien à afficher pour ce choix.</div>';
  }
  page.innerHTML = `${warn}${rebuilt}
    <div class="card"><div class="row" style="gap:12px;flex-wrap:wrap;margin-bottom:12px">
      <div id="presets" class="seg">${Object.entries(s.presets).map(([k, p]) => `<button data-p="${k}">${J.esc(p.label)}</button>`).join('')}</div>
      <div id="groups" class="seg">${Object.entries(GROUPS).map(([k, l]) => `<button data-g="${k}">${l}</button>`).join('')}</div></div>
      <div id="table"></div></div>
    <div class="card"><h2>Derniers classements</h2><div id="recent"></div></div>
    <p class="small muted">${s.days} jour(s) enregistré(s) du ${J.date(s.first)} au ${J.date(s.last)}. Les ${'20'} premiers titres de chaque groupe sont conservés pour chaque stratégie. Un titre est évalué à partir de sa clôture du jour du classement ; un saut de cours non expliqué (split) invalide la mesure. Analyse descriptive du passé, sans conseil ni promesse de performance.</p>`;
  J.$('#presets').onclick = e => { const b = e.target.closest('button'); if (b) { preset = b.dataset.p; draw(); } };
  J.$('#groups').onclick = e => { const b = e.target.closest('button'); if (b) { group = b.dataset.g; draw(); } };
  draw();
})();
