/* Page Données : d'où viennent les informations, quand elles ont été collectées, ce qui est couvert, ce qui est de qualité moindre. */
(async () => {
  const user = await J.init('donnees'); if (!user) return;
  const o = await J.api('data/overview'), c = o.catalogue, p = o.prices, page = J.$('#page');
  const kinds = { equity: 'Actions', etf: 'ETF' }, st = { selected: 'Sélectionnées', candidate: 'Candidates', excluded: 'Exclues' };
  const tot = o.places.reduce((a, x) => ({ followed: a.followed + x.followed, ok: a.ok + x.ok, incomplete: a.incomplete + x.incomplete, calendar_unknown: a.calendar_unknown + x.calendar_unknown, stale: a.stale + x.stale, insufficient: a.insufficient + x.insufficient, broken: a.broken + x.broken, full: a.full + x.full_year }), { followed: 0, ok: 0, incomplete: 0, calendar_unknown: 0, stale: 0, insufficient: 0, broken: 0, full: 0 });
  const pct = (a, b) => b ? J.num(100 * a / b, 1) + ' %' : '–';
  page.innerHTML = `<div class="page-head"><div><h1>Données</h1><p>D’où viennent les informations affichées, quand elles ont été collectées pour la dernière fois et ce qu’elles couvrent. Rien n’est estimé : une donnée manquante est signalée comme telle.</p></div></div>
  <div class="grid cols-2" style="gap:14px">
   <div class="card"><div class="row between"><h2 style="margin:0">Catalogue · ${J.esc(c.source)}</h2><span class="badge ok">Source d’identité</span></div>
     <p class="small muted" style="margin:6px 0 10px">Qui est quoi : nom, type (action ou ETF), pays, secteur, ISIN, places de cotation. FinanceDatabase fournit la liste des titres ; elle ne fournit aucun cours.</p>
     <table class="dense"><tbody><tr><td class="muted">Dernier chargement</td><td>${J.dateTime(c.loaded_at)}</td></tr><tr><td class="muted">Version de la source</td><td>${J.esc(c.commit || '–')}</td></tr>
       <tr><td class="muted">Lignes lues / conservées</td><td>${J.num(c.rows_read, 0)} / ${J.num(c.rows_kept, 0)}</td></tr><tr><td class="muted">Cotations analysées (principales, sélectionnées)</td><td><b>${J.num(c.recommendable, 0)}</b></td></tr></tbody></table>
     <table class="dense" style="margin-top:10px"><thead><tr><th></th>${Object.values(st).map(l => `<th class="num">${l}</th>`).join('')}</tr></thead><tbody>${Object.entries(kinds).map(([k, l]) => `<tr><td>${l}</td>${Object.keys(st).map(s => `<td class="num">${J.num((c.listings[k] || {})[s] || 0, 0)}</td>`).join('')}</tr>`).join('')}</tbody></table>
     <p class="small muted" style="margin:10px 0 0">« Exclues » : titres écartés d’office (liquidité ou prix insuffisants, place non couverte, cotation secondaire…), jamais recommandés ; « candidates » : en attente d’une première analyse.</p></div>
   <div class="card"><div class="row between"><h2 style="margin:0">Cours · ${J.esc(p.source)}</h2><span class="badge ok">Source des prix</span></div>
     <p class="small muted" style="margin:6px 0 10px">Clôtures quotidiennes, barres de 15 minutes des deux dernières séances, cotations de référence et taux de change. Les mesures de la stratégie sont calculées par Jigobourso sur ces clôtures.</p>
     <table class="dense"><tbody><tr><td class="muted">Clôtures quotidiennes</td><td>${J.num(p.daily_rows, 0)} · du ${J.date(p.daily_from)} au ${J.date(p.daily_to)}</td></tr>
       <tr><td class="muted">Barres de 15 minutes</td><td>${J.num(p.intraday_rows, 0)} · dernière : ${J.dateTime(p.intraday_last)} UTC</td></tr>
       <tr><td class="muted">Taux de change</td><td>${p.fx_currencies} devises · au ${J.date(p.fx_date)}</td></tr>
       <tr><td class="muted">Dernier calcul des mesures</td><td>${J.dateTime(p.last_computed)}</td></tr>
       <tr><td class="muted">Dernier entretien des historiques</td><td>${J.dateTime(p.last_nightly)}</td></tr></tbody></table></div></div>
  <div class="kpi-strip" style="margin:14px 0"><div class="card"><div class="muted small">Séries suivies</div><b style="font-size:1.4rem">${J.num(tot.followed, 0)}</b></div>
    <div class="card"><div class="muted small">Historique exploitable</div><b style="font-size:1.4rem">${pct(tot.ok, tot.followed)}</b></div>
    <div class="card gold"><div class="muted small">Historiques incomplets</div><b style="font-size:1.4rem">${J.num(tot.incomplete, 0)}</b><div class="small muted">calendrier inconnu : ${J.num(tot.calendar_unknown, 0)}</div></div>
    <div class="card gold"><div class="muted small">Un an d’historique complet</div><b style="font-size:1.4rem">${pct(tot.full, tot.followed)}</b></div>
    <div class="card red"><div class="muted small">En retard / ruptures / court</div><b style="font-size:1.4rem">${tot.stale} / ${tot.broken} / ${tot.insufficient}</b></div></div>
  <div class="card" id="places" style="padding:0;scroll-margin-top:76px"><div style="padding:14px 18px"><h2 style="margin:0">Couverture et fraîcheur par place</h2><p class="small muted" style="margin:4px 0 0">Les heures de collecte sont en UTC ; « état » est calculé selon les horaires de la place.</p></div>
   <div class="table-wrap"><table><thead><tr><th>Place</th><th>État</th><th class="num">Séries</th><th>Dernière clôture</th><th>Dernier cours</th><th>Collecte quotidienne</th><th>Collecte 15 min</th><th class="num">Historique exploitable</th><th class="num">Historique incomplet</th><th class="num">Calendrier inconnu</th><th class="num">1 an complet</th><th class="num">Court</th><th class="num">Rupture</th><th class="num">Retard</th></tr></thead><tbody>
   ${o.places.map(x => `<tr><td><b>${J.esc(x.market)}</b> <span class="muted small">${J.esc(x.mic)}</span></td><td>${x.open ? '<span class="tag open">OUVERTE</span>' : '<span class="tag">FERMÉE</span>'}</td><td class="num">${J.num(x.followed, 0)}</td><td>${J.date(x.last_close)}</td><td>${J.dateTime(x.last_price)}</td><td>${J.dateTime(x.last_daily_collect)}</td><td>${x.last_intraday_collect ? J.dateTime(x.last_intraday_collect) : '–'}</td>
     <td class="num">${pct(x.ok, x.followed)}</td><td class="num ${x.incomplete ? 'warn' : ''}">${x.incomplete}</td><td class="num ${x.calendar_unknown ? 'warn' : ''}">${x.calendar_unknown}</td><td class="num">${pct(x.full_year, x.followed)}</td><td class="num">${x.insufficient}</td><td class="num ${x.broken ? 'warn' : ''}">${x.broken}</td><td class="num ${x.stale ? 'warn' : ''}">${x.stale}</td></tr>`).join('')}</tbody></table></div></div>
  <div class="card" style="margin-top:14px"><h2>Ce que signifient ces indicateurs</h2><div class="grid cols-2" style="gap:10px">
   <div class="metric"><div class="l">Retard</div><div class="s">La dernière clôture du titre est antérieure à celle de sa place : les mesures peuvent être décalées.</div></div>
   <div class="metric"><div class="l">Rupture de cours</div><div class="s">Saut de cours non expliqué (regroupement d’actions, erreur de la source) : les périodes qui le contiennent ne sont pas mesurées.</div></div>
   <div class="metric"><div class="l">Historique court</div><div class="s">Moins de séances que la période exigée : le titre est « non évaluable » plutôt que jugé sur trop peu de données.</div></div>
   <div class="metric"><div class="l">Historique incomplet</div><div class="s">Une ou plusieurs clôtures de séance manquent. La pente et le R² utilisent les dates réelles; les indicateurs de chemin restent indisponibles si une clôture manque.</div></div>
   <div class="metric"><div class="l">Différé</div><div class="s">Yahoo Finance peut publier les cours avec quelques minutes de retard selon la place ; la fiche intraday signale tout retard.</div></div></div></div>`;
  if (location.hash === '#places') J.$('#places').scrollIntoView();
})();
