/* Fiche d'un titre : cours, intraday 15 min (deux dernières séances), analyse de la stratégie, données et qualité, fonds (ETF). */
(async () => {
  const user = await J.init('explorer'); if (!user) return;
  const params = new URLSearchParams(location.search), id = +params.get('id'), page = J.$('#page');
  /* Le verdict suit exactement la configuration choisie : celle de l'Explorer (par défaut si on vient de là), d'un profil ou d'un portefeuille. */
  /* Négociabilité : même calcul que le filtre « Titres facilement négociables ». Discret quand tout va bien, explicite quand le titre est masqué ou non évalué. */
  const tradability = t => {
    if (!t) return '';
    const meta = `<span class="small muted">${J.esc(t.source)}${t.values.volume_at ? ' · données du ' + J.dateTime(t.values.volume_at) : ''}</span>`;
    const notes = t.notes.map(n => `<br><span class="small">${J.esc(n)}</span>`).join('');
    if (t.level === 'bad' || t.level === 'unknown') return `<div class="notice" style="margin-bottom:12px"><b>${J.esc(t.label)}</b><br>${J.esc(t.text)}${notes}<br>${meta}</div>`;
    return `<p class="small" style="margin:0 0 12px"><b>${J.esc(t.label)}.</b> ${J.esc(t.text)}${notes} ${meta}</p>`;
  };
  const saved = (() => { try { return JSON.parse(new URLSearchParams(location.hash.slice(1)).get('explore')) || JSON.parse(localStorage.getItem('jigo_explorer2')) || null; } catch (e) { return null; } })();
  const pfList = (await J.api('portfolios').catch(() => ({ portfolios: [] }))).portfolios.filter(p => p.has_strategy);
  const P = await J.api('strategy/presets').catch(() => ({ presets: {} }));
  const PN = { regular: 'Croissance régulière', fast: 'Croissance rapide', recovery: 'Rebond', low_volatility: 'Hausse calme', momentum: 'Momentum 6 mois (essai)', momentum12: 'Momentum 12 mois (essai)' };
  let src = params.get('src') || (params.get('portfolio') ? 'pf:' + params.get('portfolio') : '');
  if (src === 'explorer' && !(saved && saved.config)) src = '';
  const reqBody = { id };
  if (src === 'explorer') {
    const sv = saved.view || {}, keep = {};
    ['kind', 'market', 'country', 'category', 'budget', 'min_price', 'max_price', 'min_score', 'max_volatility', 'max_drawdown', 'min_volume', 'pea', 'owned_only', 'open_now', 'fresh_only'].forEach(k => { if (sv[k] !== '' && sv[k] !== false && sv[k] !== undefined) keep[k] = sv[k]; });
    reqBody.config = saved.config; reqBody.view = keep;
    reqBody.source = 'Réglages de l’Explorer' + (saved.label ? ' · ' + saved.label : saved.preset && PN[saved.preset] ? ' · ' + PN[saved.preset] : ' (personnalisés)');
  } else if (src.startsWith('preset:') && P.presets[src.slice(7)]) { reqBody.config = P.presets[src.slice(7)]; reqBody.source = 'Profil « ' + PN[src.slice(7)] + ' »'; }
  else if (src.startsWith('pf:')) reqBody.portfolio = +src.slice(3);
  let s;
  try { s = await J.post('sheet', reqBody); } catch (e) { page.innerHTML = `<div class="notice err">${J.esc(e.message)}</div>`; return; }
  document.title = s.name + ' — Jigobourso';
  const tvMarket = {XNAS:'NASDAQ',XNYS:'NYSE',ARCX:'AMEX',XETR:'XETR',XPAR:'EURONEXT',XLON:'LSE',XAMS:'EURONEXT',XMIL:'MIL'}[s.mic];
  const localSymbol=s.symbol.replace(/\.(DE|PA|AS|L|MI|SW|MU)$/,'');
  const us=['XNAS','XNYS','ARCX','BATS','XASE'].includes(s.mic);
  const ext=[['Yahoo Finance','https://finance.yahoo.com/quote/'+encodeURIComponent(s.symbol)+'/']];
  if(tvMarket)ext.push(['TradingView','https://www.tradingview.com/symbols/'+tvMarket+'-'+encodeURIComponent(localSymbol)+'/']);
  if(us)ext.push(['StockAnalysis','https://stockanalysis.com/'+(s.kind==='etf'?'etf':'stocks')+'/'+encodeURIComponent(s.symbol.toLowerCase())+'/']);
  const v = s.verdict || {}, F = s.freshness || {}, SRC = s.sources || {}, st = s.state || {};
  const closes = s.daily.map(d => d[1]), last = closes[closes.length - 1];
  const perf = n => s.measures[String(n)] ? s.measures[String(n)].perf : null;
  const lastDay = perf(1);
  const periodRows = Object.entries(s.measures).filter(([, m]) => m).map(([n, m]) => ({ n: +n, m }));
  const labelFor = n => (s.config_periods.find(p => p.sessions === n) || { label: n + ' séances' }).label;
  const grouped = {}; (v.reasons || []).forEach(r => { (grouped[r.period || 'data'] = grouped[r.period || 'data'] || []).push(r); });
  const sib = s.other_listings.map(o => `<div><a href="titre.html?id=${o.id}">${J.esc(o.symbol)}</a> <span class="muted">${J.esc(o.mic)} · ${J.esc(o.currency || '')}</span>${o.is_primary ? ' <span class="tag held">PRINCIPALE</span>' : ''}${o.status === 'excluded' ? ' <span class="tag">EXCLUE</span>' : ''}</div>`).join('');
  const held = s.holdings.length > 0;
  const PEA = { probable: ['PEA probable', 'pea'], a_verifier: ['PEA à vérifier', 'pea'], non: null }[s.pea.status];
  const ageDays = F.last_close_date ? Math.round((Date.now() - new Date(F.last_close_date)) / 864e5) : null;
  const fresh = F.stale ? ['stale', 'En retard sur la place'] : ageDays !== null && ageDays > 5 ? ['old', 'Ancienne'] : ['ok', 'À jour'];
  const hasTabs = ['cours', 'intraday', 'analyse', 'donnees'].concat(s.kind === 'etf' ? ['fonds'] : []);
  const tabLabel = { cours: 'Cours', intraday: 'Intraday 15 min', analyse: 'Analyse de la stratégie', donnees: 'Données et qualité', fonds: 'Contenu du fonds' };
  const notice = [
    s.catalogue_status === 'excluded' ? `<div class="notice warn"><b>Ce titre est exclu des recommandations.</b> ${J.esc(s.excluded_reason || '')} Il n’est ni classé ni proposé dans l’Explorer${held ? ' ; il reste suivi et actualisé parce que vous le détenez' : ''}.</div>` : '',
    s.product_warning ? `<div class="notice warn"><b>Produit à surveiller.</b> ${J.esc(s.product_warning)}</div>` : '',
    F.stale ? `<div class="notice warn">Les clôtures de ce titre sont anciennes par rapport à la dernière séance attendue (dernière : ${J.date(F.last_close_date)}, attendue : ${J.date(F.market_latest_close)}). Les mesures peuvent être décalées.</div>` : '',
  ].filter(Boolean).join('');
  page.innerHTML = `
  <p class="small" style="margin:0 0 8px"><a href="index.html">← Explorer</a></p>
  <div class="hero"><div><h1>${J.esc(s.name)}</h1>
    <div class="chips" style="margin-top:8px"><span class="badge">${J.esc(s.symbol)}</span><span class="badge">${J.esc(s.market)} · ${J.esc(s.mic)}</span><span class="badge">${s.kind === 'etf' ? 'ETF' : 'Action'}</span>${s.isin ? `<span class="badge">${J.esc(s.isin)}</span>` : ''}${s.country ? `<span class="badge">${J.esc(s.country)}</span>` : ''}${s.category ? `<span class="badge">${J.esc(s.category)}</span>` : ''}${PEA ? `<span class="badge">${PEA[0]}</span>` : ''}${held ? '<span class="badge">Détenu</span>' : ''}${s.is_primary ? '' : '<span class="badge">Cotation secondaire</span>'}</div>
    <div style="margin-top:10px">${v.status ? J.statusBadge(v.status, v.status_label) : ''}${v.rank ? ` <span class="muted">n° ${v.rank} sur ${v.of} ${s.kind === 'etf' ? 'ETF' : 'actions'} retenus${v.scope_filtered ? ' (sélection)' : ''} · selon ${J.esc((s.strategy || {}).source || 'réglage par défaut')} · score ${J.num(v.score, 0)}/100</span>` : ''}</div></div>
    <div style="text-align:right"><div class="px">${J.money(s.price, s.currency)}</div><div class="muted">${s.price ? J.priceLabel(s) + ' · ' + J.dateTime(s.price_time) : 'Pas de cours'}</div>${lastDay !== null ? `<div class="${J.cls(lastDay)}" style="font-weight:700">${J.pct(lastDay)} <span class="muted" style="font-weight:400">sur la dernière séance</span></div>` : ''}
    ${s.price_eur !== null && s.currency !== 'EUR' ? `<div class="muted small">≈ ${J.eur(s.price_eur)}</div>` : ''}<div style="margin-top:10px"><button class="btn small" id="add">+ Ajouter à un portefeuille</button></div></div></div>
  ${s.price_stale ? '<div class="notice warn">Cours ancien : aucune cotation récente confirmée. Le prix affiché reste daté, il ne représente pas un cours actuel.</div>' : ''}
  <div class="row small" style="gap:14px;margin:10px 0">${ext.map(([name,url])=>`<a href="${J.esc(url)}" target="_blank" rel="noopener noreferrer">${name} ↗</a>`).join('')}</div>
  ${notice ? `<div class="grid" style="gap:10px;margin-bottom:14px">${notice}</div>` : ''}
  <div class="tabs big" id="tabs">${hasTabs.map(t => `<button data-t="${t}">${tabLabel[t]}</button>`).join('')}</div>
  <div class="grid" style="grid-template-columns:minmax(0,2.3fr) minmax(270px,1fr);align-items:start" id="layout"><div id="main"></div>
   <div>
    <div class="card"><div class="row between"><h2 style="margin:0">Mes portefeuilles</h2></div>
      ${held ? `<table class="dense"><tbody>${s.holdings.map(h => `<tr><td><a href="portefeuilles.html?id=${h.portfolio_id}">${J.esc(h.portfolio)}</a></td><td class="num">${J.num(h.qty, 4)}</td><td class="num ${J.cls(h.unrealized)}">${h.unrealized !== null ? J.eur(h.unrealized) + '<div class="small">' + J.pct(h.unrealized_pct, 1) + '</div>' : '–'}</td></tr>`).join('')}</tbody></table>` : '<p class="muted small" style="margin:8px 0 0">Vous ne détenez pas ce titre.</p>'}</div>
    <div class="card"><h2>Repères</h2><div class="metric-grid" style="grid-template-columns:1fr 1fr"><div class="metric"><div class="l">Moy. 20 j</div><div class="v">${J.num(st.ma20, 2)}</div></div><div class="metric"><div class="l">Moy. 50 j</div><div class="v">${J.num(st.ma50, 2)}</div></div><div class="metric"><div class="l">Écart moy. 20 j</div><div class="v">${J.pct(st.gap_to_ma20, 1)}</div></div><div class="metric"><div class="l">Volume moy. 3 m</div><div class="v">${s.avg_volume_3m !== null ? J.num(s.avg_volume_3m, 0) : '–'}</div></div><div class="metric" title="Variation du cours entre il y a 126 et il y a 21 séances (le dernier mois est ignoré). Mesure du passé."><div class="l">Momentum 6 mois</div><div class="v ${J.cls(st.momentum_6m)}">${st.momentum_6m !== null && st.momentum_6m !== undefined ? J.pct(st.momentum_6m, 1) : 'non évaluable'}</div></div><div class="metric" title="Variation du cours entre il y a 252 et il y a 21 séances (le dernier mois est ignoré). Mesure du passé."><div class="l">Momentum 12 mois</div><div class="v ${J.cls(st.momentum_12m)}">${st.momentum_12m !== null && st.momentum_12m !== undefined ? J.pct(st.momentum_12m, 1) : 'non évaluable'}</div></div></div></div>
    ${sib ? `<div class="card"><h2>Autres cotations du produit</h2><div class="small" style="display:grid;gap:6px">${sib}</div></div>` : ''}
   </div></div>`;
  if (innerWidth < 960) J.$('#layout').style.gridTemplateColumns = '1fr';

  const panes = {
    cours() {
      const R = [['1 S', 5], ['1 M', 21], ['3 M', 63], ['6 M', 126], ['1 A', 252], ['Max', 0]];
      let sessions = 252, ma20 = true, ma50 = false, vol = true;
      J.$('#main').innerHTML = JEtf.assessment(s.assessment) + JEtf.reading(s.signals) + tradability(s.tradability) + `<div class="card"><div class="row between wrap-s"><h2 style="margin:0">Évolution du cours</h2><div class="row gap-s"><span class="seg" id="range">${R.map(([l, n]) => `<button data-n="${n}" class="${n === sessions ? 'on' : ''}">${l}</button>`).join('')}</span>
        <button class="chip on" data-o="ma20">Moy. 20 j</button><button class="chip" data-o="ma50">Moy. 50 j</button><button class="chip on" data-o="vol">Volumes</button></div></div>
        <div id="chart" style="margin-top:8px"></div><div class="row between small muted" id="chart-sum" style="margin-top:6px"></div></div>
        <div class="card"><h2>Performances</h2><div class="metric-grid">${[['1 jour', perf(1)], ['1 semaine', perf(5)], ['1 mois', perf(21)], ['3 mois', perf(63)], ['6 mois', perf(126)], ['1 an', perf(252)]].map(([l, p]) => `<div class="metric"><div class="l">${l}</div><div class="v ${J.cls(p)}">${J.pct(p, 1)}</div></div>`).join('')}</div>
        <p class="small muted" style="margin:10px 0 0">Performances calculées sur la même série que la stratégie (${J.esc(s.analysis_basis === 'adjusted' ? 'clôtures ajustées du fournisseur' : 'clôtures brutes, splits connus corrigés si leur ratio est disponible')}), dans sa devise (${J.esc(s.currency || '')}). Elles décrivent le passé et ne garantissent rien pour la suite.</p></div>`;
      const draw = () => { const r = J.priceChart(J.$('#chart'), s.daily.map((d, i) => [d[0], d[1], s.daily_volume[i]]), { sessions, ma20, ma50, volume: vol, unit: s.currency });
        J.$('#chart-sum').innerHTML = r ? `<span>${J.date(r.from)} → ${J.date(r.to)} · ${r.sessions} séances</span><span class="${J.cls(r.perf)}"><b>${J.pct(r.perf, 1)}</b> sur la période · plus haut ${J.num(r.high, 2)} · plus bas ${J.num(r.low, 2)}</span>` : ''; };
      J.$$('#range button').forEach(b => b.onclick = () => { sessions = +b.dataset.n; J.$$('#range button').forEach(x => x.classList.toggle('on', x === b)); draw(); });
      J.$$('[data-o]').forEach(b => b.onclick = () => { const k = b.dataset.o; if (k === 'ma20') ma20 = !ma20; if (k === 'ma50') ma50 = !ma50; if (k === 'vol') vol = !vol; b.classList.toggle('on'); draw(); });
      draw();
    },
    intraday() {
      J.$('#main').innerHTML = `<div class="card"><div class="row between"><h2 style="margin:0">Les deux dernières séances · 15 minutes</h2></div><div id="ipanel" style="margin-top:10px"></div></div>
        <p class="small muted">Chaque bougie ou point représente 15 minutes de cotation, à l’heure de la place (${J.esc(s.market)}). Les barres proviennent de Yahoo Finance et sont conservées par Jigobourso ; quand Yahoo n’en fournit pas pour un créneau, le créneau reste vide.</p>`;
      J.intradayPanel(J.$('#ipanel'), id);
    },
    analyse() {
      const sg = s.strategy || {}, crit = p => Object.entries(p.criteria).map(([k, x]) => `${(J.CRITERIA[k] || [k])[0]} ${k.startsWith('min') ? '≥' : '≤'} ${J.num(x, 2)}`).join(', ') || 'aucun seuil';
      const opts = [['', 'Réglage par défaut (Croissance régulière)'], ...(saved && saved.config ? [['explorer', 'Réglages actuels de l’Explorer']] : []), ...Object.keys(P.presets).map(k => ['preset:' + k, 'Profil « ' + PN[k] + ' »']), ...pfList.map(p => ['pf:' + p.id, 'Portefeuille « ' + p.name + ' »'])];
      J.$('#main').innerHTML = `<div class="notice" style="margin-bottom:12px"><div class="row between"><span><b>Verdict calculé selon :</b> ${J.esc(sg.source || 'réglage par défaut')}</span><select id="src-sel" aria-label="Configuration du verdict">${opts.map(([k, l]) => `<option value="${k}" ${k === src ? 'selected' : ''}>${J.esc(l)}</option>`).join('')}</select></div>
        <div class="small muted" style="margin-top:6px">${(sg.periods || []).map(p => `<b>${J.esc(p.label)}</b> (${p.sessions} séances) : ${J.esc(crit(p))}`).join(' · ')}${Object.keys(sg.technical || {}).length ? ' · filtres techniques actifs' : ''} · classement par ${({ trend: 'pente', performance: 'performance', regularity: 'régularité', stability: 'stabilité', momentum: 'momentum 6 mois (J−126 → J−21 séances)' })[sg.ranking] || sg.ranking}</div>
        ${sg.experimental ? '<div class="notice warn" style="margin-top:8px"><b>Stratégie à titre d’essai.</b> Elle classe les titres selon leur progression passée entre il y a ' + (sg.ranking === 'momentum12' ? '12' : '6') + ' mois et il y a 1 mois (le dernier mois est ignoré). Elle décrit le passé et ne prédit pas la suite. Dans l’historique étudié, ce type de classement a connu des mois à plus de −25 % et des baisses de plus de 50 % depuis un sommet ; ses meilleurs titres sont souvent très volatils et l’avantage observé diminue quand on exige des titres très négociables. Aucune performance n’est garantie.</div>' : ''}
        ${v.scope_filtered ? `<div class="small muted" style="margin-top:4px">Rang calculé dans la sélection de l’Explorer : ${J.num(v.examined, 0)} titres examinés sur ${J.num(v.universe, 0)}.</div>` : ''}</div>
        <div class="card"><div class="row between"><h2 style="margin:0">Verdict de la stratégie</h2>${v.status ? J.statusBadge(v.status, v.status_label) : ''}</div>
        ${v.rank ? `<p class="muted" style="margin:6px 0 10px">N° <b>${v.rank}</b> sur ${v.of} ${s.kind === 'etf' ? 'ETF' : 'actions'} retenus${v.scope_filtered ? ' dans votre sélection' : ''} · score ${J.num(v.score, 0)} / 100 (percentile moyen sur les périodes actives)</p>` : v.in_scope === false ? '<p class="muted" style="margin:6px 0 10px">Ce titre est hors de la sélection de l’Explorer (filtres actifs) : il n’est pas classé.</p>' : ''}
        ${v.note ? `<p>${J.esc(v.note)}</p>` : ''}<div class="reasons">${Object.values(grouped).flat().map(J.explain).join('') || (v.note ? '' : '<span class="muted">Aucun critère actif.</span>')}</div>
        <p class="small muted" style="margin:10px 0 0">Chaque ligne donne la valeur mesurée et le seuil exigé par la configuration ci-dessus.</p></div>
        <div class="card"><h2>Mesures par période</h2><div class="table-wrap"><table><thead><tr><th>Période</th><th class="num">Séances</th><th class="num">Pente (%/séance)</th><th class="num">R²</th><th class="num">ER</th><th class="num">Performance</th><th class="num">Volatilité</th><th class="num">Repli max.</th></tr></thead><tbody>
        ${periodRows.map(({ n, m }) => `<tr><td>${J.esc(labelFor(n))}</td><td class="num">${n}</td><td class="num ${J.cls(m.slope)}">${J.num(m.slope, 3)}</td><td class="num">${J.num(m.r2, 2)}</td><td class="num">${J.num(m.er, 2)}</td><td class="num ${J.cls(m.perf)}">${J.pct(m.perf)}</td><td class="num">${m.volatility === null || m.volatility === undefined ? '–' : J.num(m.volatility, 2) + ' %'}</td><td class="num">${m.drawdown === null || m.drawdown === undefined ? '–' : J.num(m.drawdown, 1) + ' %'}</td></tr>`).join('')}</tbody></table></div></div>
        <div class="card"><h2>Comment lire ces mesures</h2><div class="grid cols-2" style="gap:10px"><div class="metric"><div class="l">Pente</div><div class="s">Hausse moyenne par séance, calculée sur le logarithme du cours : un titre à 5 € se compare à un titre à 500 €.</div></div><div class="metric"><div class="l">R² (régularité)</div><div class="s">À quel point la hausse suit une droite : 1 = parfaitement régulière, 0 = aucun lien avec le temps.</div></div><div class="metric"><div class="l">ER (efficacité)</div><div class="s">Trajet net divisé par le trajet total parcouru, entre −1 et +1 : un cours qui zigzague a un ER faible.</div></div><div class="metric"><div class="l">Volatilité / repli</div><div class="s">Écart-type des variations quotidiennes ; plus forte baisse depuis un sommet pendant la période.</div></div></div></div>`;
      J.$('#src-sel').onchange = e => { const u = new URL(location.href); if (e.target.value) u.searchParams.set('src', e.target.value); else u.searchParams.delete('src'); u.searchParams.delete('portfolio'); u.hash = '#analyse'; location.href = u.toString(); };
    },
    donnees() {
      const row = (a, b, c = '') => `<tr><td class="muted" style="width:34%">${a}</td><td>${b}</td><td class="small muted">${c}</td></tr>`;
      J.$('#main').innerHTML = `<div class="card"><div class="row between"><h2 style="margin:0">Sources des données</h2><span class="badge ${fresh[0] === 'ok' ? 'ok' : 'wait'}">${fresh[1]}</span></div><div class="table-wrap"><table class="dense"><tbody>
        ${row('Catalogue (identité, type, pays)', `<b>${J.esc(SRC.catalogue)}</b>`, SRC.catalogue_loaded_at ? `chargé le ${J.dateTime(SRC.catalogue_loaded_at)} · version ${J.esc(SRC.catalogue_commit)}` : '')}
        ${row('Cours et historiques', `<b>${J.esc(SRC.prices)}</b>`, 'clôtures quotidiennes, barres de 15 minutes, cotation de référence')}
        ${row('Dernier cours', s.price !== null ? `${J.money(s.price, s.currency)} · ${J.priceLabel(s)}` : '–', s.price_time ? 'horodaté ' + J.dateTime(s.price_time) : '')}
        ${row('Dernière clôture quotidienne', F.last_close_date ? J.date(F.last_close_date) : '–', F.market_latest_close ? 'dernière séance de la place : ' + J.date(F.market_latest_close) : '')}
        ${row('Historique quotidien', `${s.daily.length} clôtures`, F.first_close_date ? 'depuis le ' + J.date(F.first_close_date) + ' · ' + (F.closes_count || 0) + ' utilisées pour les calculs' : '')}
        ${row('Dernière collecte de la place', SRC.last_daily_collect ? 'clôtures : ' + J.dateTime(SRC.last_daily_collect) : '–', SRC.last_intraday_collect ? 'barres 15 min : ' + J.dateTime(SRC.last_intraday_collect) : '')}
        ${(s.data_corrections || []).length ? row('Données corrigées', `${s.data_corrections.length} correction${s.data_corrections.length > 1 ? 's' : ''}`, s.data_corrections.map(c => c.kind === 'unit' ? `${J.date(c.date)} : changement d’unité du cours (×${c.factor >= 1 ? 100 : '0,01'}) ramené à l’unité actuelle` : `${J.date(c.date)} : cours isolé aberrant ignoré (${J.num(c.close, 4)})`).map(J.esc).join('<br>')) : ''}${row('Qualité de la série', { ok: 'Correcte', insufficient: 'Historique court', incomplete: 'Historique incomplet', calendar_unknown: 'Calendrier indisponible', stale: 'Clôture ancienne', break: 'Rupture de cours détectée' }[st.quality] || '–', st.quality === 'break' ? J.esc(s.break_dates || '') : st.quality === 'calendar_unknown' ? 'Calendrier de séances indisponible : les fenêtres dépendant des dates ne sont pas évaluées.' : st.quality === 'incomplete' ? (() => { const gap = Object.entries(s.window_coverage || {}).find(([, x]) => x.missing_sessions > 0); return gap ? `${gap[1].observations} clôtures disponibles sur ${gap[1].expected_closes} attendues (${gap[0]} séances)` : 'Voir les critères de stratégie pour le détail des fenêtres.'; })() : '')}
        ${row('Statut dans le catalogue', { selected: 'Sélectionné', excluded: 'Exclu', candidate: 'Candidat (pas encore analysé)' }[s.catalogue_status] || s.catalogue_status, s.excluded_reason ? J.esc(s.excluded_reason) : (s.is_primary ? 'cotation principale du produit' : 'cotation secondaire'))}
        ${row('Place et devise', `${J.esc(s.market)} (${J.esc(s.mic)}) · ${J.esc(s.currency || '')}`, '')}
        ${row('Capitalisation', s.market_cap ? J.num(s.market_cap / 1e6, 0) + ' M' : '–', s.market_cap_class ? J.esc(s.market_cap_class) + ' · donnée Yahoo Finance' : 'donnée Yahoo Finance')}
        ${s.kind === 'equity' ? row('Analystes', s.analyst ? J.esc(s.analyst.text) : '—', s.analyst ? 'consensus des analystes financiers relevé par Yahoo, pas une recommandation de Jigobourso ; aucun effet sur les scores, filtres ou classements' : 'information indisponible : cela n’est pas un défaut du titre') : ''}
        ${row('PEA', PEA ? PEA[0] : 'Non', J.esc(s.pea.note))}</tbody></table></div></div>
        <div class="card"><h2>À savoir sur ces données</h2><p class="small muted" style="margin:0">Les clôtures sont définitives une fois publiées par Yahoo Finance ; les barres de 15 minutes sont fournies pour les deux dernières séances et peuvent être différées de quelques minutes selon la place. Les actions européennes et américaines sont comptées dans la devise de leur place. Les ruptures de cours non expliquées (par exemple un regroupement d’actions) invalident les mesures de la période concernée plutôt que de les fausser.</p></div>`;
    },
    fonds() {
      J.$('#main').innerHTML = JEtf.fund(s.etf_analysis, s.etf_profile, s.etf_compare);
    },
  };
  function open(t) {
    if (!panes[t]) t = 'cours';
    J.$$('#tabs button').forEach(b => b.classList.toggle('on', b.dataset.t === t));
    history.replaceState(null, '', '#' + t); panes[t]();
  }
  J.$$('#tabs button').forEach(b => b.onclick = () => open(b.dataset.t));
  J.$('#add').onclick = async () => { const p = await J.api('portfolios'); if (!p.portfolios.length) { const n = await J.post('portfolio/create', { name: 'Portefeuille principal' }); p.portfolios.push({ id: n.id, name: 'Portefeuille principal' }); } J.txDialog({ portfolios: p.portfolios, portfolioId: (p.portfolios.find(x => x.is_default) || p.portfolios[0]).id, listing: { id: s.id, symbol: s.symbol, name: s.name, currency: s.currency, price: s.price }, onDone: () => location.reload() }); };
  open(location.hash.slice(1) || 'cours');
})();
