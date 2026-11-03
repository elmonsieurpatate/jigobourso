/* Page Portefeuilles — l'essentiel d'abord : valeur et gain, courbe compacte, ce qui fait bouger, positions ; le reste replié. */
(async () => {
  const user = await J.init('portefeuilles'); if (!user) return;
  const page = J.$('#page');
  let list = (await J.api('portfolios')).portfolios;
  let current = +new URLSearchParams(location.search).get('id') || (list.find(p => p.is_default) || list[0] || {}).id;
  const NAMES = { regular: 'Croissance régulière', fast: 'Croissance rapide', recovery: 'Rebond', low_volatility: 'Hausse calme', momentum: 'Momentum 6 mois (essai)', momentum12: 'Momentum 12 mois (essai)', momentum_risk: 'Momentum ajusté du risque (essai)' };
  const PAL = ['#6366f1', '#14b8a6', '#f59e0b', '#ec4899', '#3b82f6', '#84cc16', '#a855f7', '#ef4444', '#06b6d4', '#eab308', '#64748b', '#22c55e'];
  const store = (k, v) => { try { if (v === undefined) return JSON.parse(localStorage.getItem('jigo_pf_' + k)); localStorage.setItem('jigo_pf_' + k, JSON.stringify(v)); } catch (e) { return null; } };
  const EVO = { mode: 'titles', per: store('evo_per') || '1m', unit: store('evo_unit') === 'pct' ? 'pct' : 'eur', hidden: new Set(store('evo_hidden') || []) };
  const PERIODS = [['1d', '1 J', 0], ['1w', '1 S', 8], ['1m', '1 M', 31], ['3m', '3 M', 92], ['6m', '6 M', 183], ['1y', '1 A', 366], ['all', 'Tout', 0]];
  const px = (v, c) => v === null || v === undefined ? '–' : J.money(v, c || 'EUR');
  const eur0 = v => J.eur(v, 0), sgn = v => v === null || v === undefined ? '–' : (v > 0 ? '+' : v < 0 ? '−' : '') + J.eur(Math.abs(v), 0);
  const pills = (id, items, cur) => `<div class="pills" id="${id}">${items.map(([k, l]) => `<button type="button" data-v="${k}" class="${k === cur ? 'on' : ''}">${l}</button>`).join('')}</div>`;
  const splitNotice = positions => positions.filter(p => p.splits_applied && p.splits_applied.length).map(p => `<div class="notice" style="margin-top:12px"><b>${J.esc(p.name_catalogue || p.name || p.symbol)}</b> : ${p.splits_applied.map(a => a.ratio >= 1 ? `split ${J.num(a.ratio, 2)} pour 1` : `regroupement ${J.num(1 / a.ratio, 2)} pour 1`).join(', ')} pris en compte automatiquement : la quantité affichée est celle d’aujourd’hui, le prix de revient total est inchangé.</div>`).join('');
  const ANALYSIS = { domain: 'personal', scale: 'index', markers: true, focus: null, auto: true, reference: 'purchase' };
  let VIEW = 'overview';
  let SORT = 'attention';
  let D = null, H = null;                       // données du portefeuille affiché, et son évolution (chargée à part)

  /* ── Blocs repliables : un clic sur l'en-tête ; choix mémorisé dans ce navigateur. Par défaut, seuls l'essentiel et les positions sont ouverts. ── */
  const FOLD_DEFAULT = { etf: true, alloc: true, lots: true, sales: true, tx: true, settings: true };
  const section = (id, title, extra, body, cls = '') => `<section class="card fold ${cls}" data-fold="${id}"><header class="fold-h"><h2>${title}</h2><div class="fold-x">${extra || ''}</div><span class="chev" aria-hidden="true"></span></header><div class="fold-b">${body}</div></section>`;
  function folds() {
    const saved = Object.assign({}, FOLD_DEFAULT, store('folds2') || {});
    J.$$('#page [data-fold]').forEach(c => {
      c.classList.toggle('folded', !!saved[c.dataset.fold]);
      const h = c.querySelector('.fold-h') || c.firstElementChild; if (!h) return;
      h.classList.add('fold-h'); h.tabIndex=0; h.setAttribute('role','button'); h.setAttribute('aria-expanded',String(!c.classList.contains('folded')));
      h.onkeydown=e=>{if(e.target===h && ['Enter',' '].includes(e.key)){e.preventDefault();h.click();}};
      h.addEventListener('click', e => { if (e.target.closest('button, a, input, select, .pills')) return; c.classList.toggle('folded'); h.setAttribute('aria-expanded',String(!c.classList.contains('folded'))); const f = Object.assign({}, FOLD_DEFAULT, store('folds2') || {}); f[c.dataset.fold] = c.classList.contains('folded'); store('folds2', f); if (c.dataset.fold === 'hero' && !c.classList.contains('folded')) drawEvo(); });
    });
  }

  /* ── En-tête : valeur, gain total, variation du jour ── */
  function hero(d) {
    const t = d.totals, gain = t.total_gain, base = t.invested_total || 0;
    const realizedTaxBase = Object.values(d.realized_by_year || {}).reduce((s, g) => s + Math.max(0, Number(g) || 0), 0);
    const net = gain === null ? null : gain - .3 * (realizedTaxBase + Math.max(0, Number(t.unrealized) || 0));
    const stat = (label, value, note = '', cls = '') => `<div class="pf-stat"><span>${label}</span><strong class="${cls}">${value}</strong><small>${note}</small></div>`;
    return `<section class="card pf-summary" aria-label="Résultat personnel du portefeuille">
      <div class="pf-balance"><span class="eyebrow">Valeur de vos titres</span><strong class="hero-v">${eur0(t.value)}</strong><span class="small muted" id="hero-day"></span></div>
      <div class="pf-profit"><span class="eyebrow">Votre gain total · ventes comprises</span><strong class="hero-g ${J.cls(gain)}">${sgn(gain)} <small>${base > 0 && gain !== null ? J.pct(100 * gain / base, 1) : ''}</small></strong><small>Gain ÷ achats cumulés, frais compris</small></div>
      <div class="pf-stats">${stat('Achats cumulés', eur0(base), 'Frais inclus · ventes non déduites')}${stat('Capital encore investi', eur0(t.cost), 'Coût des titres détenus')}${stat('Gain latent', sgn(t.unrealized), 'Sur les positions ouvertes', J.cls(t.unrealized))}${stat('Gain réalisé', sgn(t.realized), 'Sur les ventes, frais déduits', J.cls(t.realized))}${stat('Gain net estimé', sgn(net) + (net !== null && base > 0 ? ' · ' + J.pct(100 * net / base, 1) : ''), 'Hypothèse forfaitaire 30 %, non personnalisée', J.cls(net))}</div>
      <details class="pf-explain"><summary>Comprendre ces chiffres</summary><p>Le gain total additionne réalisé et latent. Le pourcentage utilise les achats cumulés, pas le capital restant. Le net suppose une taxation forfaitaire de 30 % des gains annuels positifs réalisés et du latent positif : hors PEA, pertes reportables et fiscalité personnelle. Liquidités et dividendes ne sont pas gérés.</p></details></section>`;
  }
  function analysis(d) {
    return `<section class="card analysis-chart" aria-label="Évolution et analyse"><div id="analysis-priority" aria-live="polite"></div><div class="analysis-heading"><h2 id="analysis-title">Résultat de mes positions</h2>${pills('analysis-domain', [['personal','Mon investissement'],['market','Cours du titre']],ANALYSIS.domain)}${pills('evo-per', PERIODS.map(p => [p[0], p[1]]), EVO.per)}</div>
      <div class="analysis-controls"><div id="market-controls">${pills('market-scale',[['index','Base 100'],['price','Cours réels']],ANALYSIS.scale)}</div><div id="personal-controls">${pills('evo-mode', [['titles', 'Comparer les titres'], ['gain', 'Gain'], ['value', 'Valeur']], EVO.mode)}${pills('evo-unit', [['eur', '€'], ['pct', '%']], EVO.unit)}<label>Référence <select id="personal-reference"><option value="purchase">Depuis vos achats</option><option value="period">Sur la période</option></select></label></div><label class="purchase-toggle"><input type="checkbox" id="purchase-markers" checked> Repères d’achat</label><button class="btn small" id="clear-focus" hidden>Tous les titres</button></div>
      <div class="analysis-definitions"><span><b>Cours</b> · prix du titre, hors frais</span><span><b>Ma position</b> · mon gain, frais et change inclus</span><span><b>Contribution</b> · effet en € sur le résultat de la période</span></div><div id="analysis-positions" aria-label="Toutes les positions détenues"></div><p class="small muted" id="period-reference"></p><p id="evo-note" class="small muted" role="status"></p><div id="evo-chart"><div class="lc-empty"><span class="spinner"></span></div></div><section id="analysis-detail" aria-live="polite" aria-label="Détail de la position sélectionnée"></section>
      <details class="pf-explain"><summary>Cours du titre ou résultat personnel ?</summary><p>Cours du titre : observations de marché dans la devise du titre, corrigées des splits selon la série disponible, sans frais ni change personnel, y compris avant les achats. Base 100 : comparaison à une même date ; si le cours de départ manque, la comparaison reste indisponible. Aucun portefeuille fictif n’est reconstitué avant vos achats.</p><p>Mon investissement : transactions, frais et conversions historiques en euros. Depuis vos achats : gain cumulé ÷ achats cumulés ; sur la période : gain de la période ÷ (valeur de départ + achats). Les gains réalisés restent inclus. Les pourcentages des titres ne s’additionnent pas.</p></details></section>
      <div class="analysis-bottom"><section class="card analysis-losses"><h2>Ce qui fait baisser mon portefeuille</h2><p class="small muted">Classement par perte réelle en euros sur la période, frais et change compris.</p><div id="analysis-losses"></div><details><summary>Toutes les contributions</summary><div id="movers" class="movers"></div></details></section><section class="card analysis-purchases"><h2>Mes achats</h2><p class="small muted">Premiers achats et compléments réels. Sélectionnez un titre pour mettre sa courbe en évidence.</p><details id="all-purchases"><summary>Historique des achats par titre</summary><div id="analysis-purchases"></div></details></section></div>`;
  }
  const STATUS = { normal: ['ok', 'Normal'], watch: ['wait', 'À surveiller'], act: ['ko', 'À examiner'], unknown: ['', 'Données insuffisantes'] };
  const positionLots = (d,p) => d.lots.filter(l => p.listing_id ? l.listing_id === p.listing_id : !l.listing_id && l.symbol === p.symbol);
  const insight = p => (D.insights || {})[p.key] || { status: 'unknown', label: 'Données insuffisantes', reasons: [], market: {} };
  function statusBadge(i) { const c = STATUS[i.status] || STATUS.unknown; return `<span class="badge ${c[0]}">${J.esc(i.label || c[1])}</span>`; }
  function attention(d) {
    const ordered = d.positions.map(p => ({ p, i: insight(p) })).filter(x => x.i.status !== 'normal').sort((a, b) => priority(b.i) - priority(a.i));
    return `<section class="card pf-attention"><div class="pf-section-title"><h2>À regarder aujourd’hui</h2><span class="cnt">${ordered.length}</span></div>${ordered.length ? ordered.slice(0, 4).map(({p, i}) => `<button type="button" class="attention-row" data-inspect="${J.esc(p.key)}"><span><b>${J.esc(p.name_catalogue || p.name || p.symbol)}</b> ${statusBadge(i)}<small>${J.esc(i.personal_text || '')} ${J.esc(i.reasons[0]?.message || i.next_step || '')}</small></span><span aria-hidden="true">→</span></button>`).join('') : '<p class="small muted">Aucun signal notable selon les règles disponibles. Les données ne garantissent pas les évolutions futures.</p>'}<button class="btn small" data-switch="positions">Voir toutes les positions</button></section>`;
  }
  function priority(i) { return ({ act: 3, watch: 2, unknown: 1, normal: 0 })[i.status] || 0; }
  function gainProtection(g, compact = false) {
    if (!g || !g.available) return `<p class="small muted">${J.esc(g?.reason || 'Sommet depuis l’achat indisponible.')}</p>`;
    const used = Math.max(0, g.peak_gain_pct), kept = Math.max(0, Math.min(100, used > 0 ? 100 * Math.max(0, g.gain_pct) / used : 0));
    return `<div class="protection"><div class="protection-values"><span>Meilleur gain observé <b>${J.pct(g.peak_gain_pct, 1)}</b></span><span>Actuel <b class="${J.cls(g.gain_pct)}">${J.pct(g.gain_pct, 1)}</b></span><span>Gain rendu <b>${J.num(g.given_back_pp, 1)} points</b></span></div><div class="protection-track" role="img" aria-label="${J.num(kept, 0)} % du gain positif observé conservé"><i style="width:${kept.toFixed(2)}%"></i></div>${compact ? `<p class="small muted">Position actuelle suivie depuis le ${J.date(g.start)} · sommet ${px(g.high,g.currency)} · recul −${J.num(g.drop_pct,2)} %.</p>` : `<p class="small muted">Recul du cours : −${J.num(g.drop_pct, 2)} % depuis le sommet observé ${px(g.high,g.currency)}. Gains personnels calculés en euros ; le recul du cours utilise la devise du titre. Référence : ${J.date(g.start)} ; dernière valeur du ${J.date(g.value_date)} ; sommet du gain le ${J.date(g.peak_date)}.</p>`}</div>`;
  }
  function positionCards(d) {
    const items = [...d.positions];
    const metric = p => { const i = insight(p); return SORT === 'loss' ? (p.unrealized === null ? -Infinity : -p.unrealized) : SORT === 'gain' ? (p.unrealized ?? -Infinity) : SORT === 'weight' ? (p.weight ?? -Infinity) : SORT === 'drop' ? (i.protection?.drop_pct ?? -Infinity) : priority(i); };
    items.sort((a,b) => metric(b) - metric(a) || a.symbol.localeCompare(b.symbol));
    return items.map(p => {
      const i = insight(p), strategies = [...new Set(positionLots(d,p).map(l => l.alert?.strategy_label).filter(Boolean))];
      return `<article class="pf-position" data-position="${J.esc(p.key)}"><div class="pf-position-title"><div><h3>${J.esc(p.name_catalogue || p.name || p.symbol)}</h3><span class="small muted">${J.esc(p.symbol)} · ${J.num(p.qty, 4)} titre(s) · ${J.esc(strategies.join(' / ') || 'stratégie non renseignée')}</span></div>${statusBadge(i)}</div>
        <div class="position-numbers"><div><span>Valeur actuelle</span><b>${J.eur(p.value)}</b><small>${J.pct(p.weight, 1, false)} du portefeuille</small></div><div><span>Depuis vos achats · latent</span><b class="${J.cls(p.unrealized)}">${sgn(p.unrealized)}</b><small>${J.pct(p.unrealized_pct, 1)} du coût restant</small></div><div><span class="per-h">Sur la période sélectionnée</span><div class="per" data-per="${p.listing_id || ''}">–</div></div><div><span>Prix de revient</span><b>${J.eur(p.avg_cost)}</b><small>par titre · coût total ${J.eur(p.cost)}</small></div></div>
        ${p.value === null ? '<p class="notice warn">Valorisation indisponible : aucun cours n’est inventé.</p>' : ''}${p.price_time ? `<p class="small muted">${p.price_source === 'daily' ? 'Dernière clôture' : 'Dernier cours connu'} : ${J.dateTime(p.price_time)}</p>` : ''}
        <div class="position-protection">${gainProtection(i.protection,true)}</div><div class="position-observation"><b>Mon investissement.</b> ${J.esc(i.personal_text || 'Résultat indisponible.')} <b>État du titre.</b> ${J.esc(i.next_step || 'Données insuffisantes.')}</div>
        <details class="position-details" ${store('inspect') === p.key ? 'open' : ''}><summary>Pourquoi ce statut ? Suivre les gains et les achats</summary>${diagnosticDetails(p, i, d)}
        <div class="row"><button class="btn small" data-chart="${p.listing_id || ''}" ${p.listing_id ? '' : 'disabled'}>Évolution du cours</button><button class="btn small" data-lv="${p.listing_id || ''}" ${p.linked ? '' : 'disabled'}>Filet et objectif</button></div></details></article>`;
    }).join('') || '<div class="card empty">Aucune position ouverte. Les résultats des ventes restent dans l’historique et le gain total.</div>';
  }
  function diagnosticDetails(p, i, d) {
    const m = i.market || {}, trend = { strong: 'hausse forte', steady: 'hausse soutenue', gentle: 'hausse douce', flat: 'pas de tendance nette', down: 'baisse' }[m.trend] || 'non mesurée';
    return `<div class="diagnostic-grid"><section><h4>Mon investissement · protection des gains</h4><p class="small muted">Quantités actuellement détenues, prix de revient moyen actuel. Comparaison depuis le dernier achat encore ouvert. Les détails de chaque achat suivent leur propre date et leur coût FIFO.</p>${gainProtection(i.protection)}</section><section><h4>État actuel du titre</h4>${!m.reliable ? '<p class="small muted">Données anciennes ou incomplètes : ces indicateurs ne permettent pas un diagnostic actuel fiable.</p>' : ''}<p class="small muted">Clôture de référence : ${m.as_of ? J.date(m.as_of) : 'indisponible'}.</p><dl class="market-facts"><dt>Tendance · 1 mois</dt><dd>${trend}</dd><dt>Momentum 6 mois</dt><dd>${J.pct(m.momentum_6m)}</dd><dt>Clôture / moyenne 50 j</dt><dd>${px(m.close, p.price_currency)} / ${px(m.ma50, p.price_currency)}</dd><dt>Moyenne 200 j</dt><dd>${px(m.ma200, p.price_currency)}</dd><dt>Volatilité · 3 mois</dt><dd>${m.volatility === null || m.volatility === undefined ? 'indisponible' : J.num(m.volatility, 2) + ' % par séance'}</dd></dl></section></div>
      <div class="diagnostic-reasons"><h4>Ce qui mérite votre attention</h4>${i.reasons?.length ? i.reasons.map(r => `<p><b>${J.esc(r.action || 'Observation')}.</b> ${J.esc(r.message)}</p>`).join('') : '<p>Aucun signal notable parmi les indicateurs disponibles.</p>'}<p class="small muted">Les observations ne sont ni une prévision ni un ordre de vente.</p></div>
      <details><summary>Détail par achat ouvert</summary>${positionLots(d,p).map(l => `<div class="lot-detail"><b>Achat du ${J.date(l.trade_at)}</b> · ${J.num(l.remaining, 4)} titre(s) · ${J.esc(l.alert?.strategy_label || '')}${gainProtection(l.alert?.protection)}<button class="btn small" data-lot="${l.tx_id}">Régler cet achat</button></div>`).join('')}</details>`;
  }
  function overviewContributions() { return `<section class="card"><div class="pf-section-title"><h2>Ce qui fait votre résultat</h2><button class="btn small" data-switch="analysis">Analyser l’évolution</button></div><p class="small muted" id="overview-period"></p><div id="overview-movers"><span class="spinner"></span></div></section>`; }
  function updateOverview() {
    if (!H) return;
    const i0 = periodStart(H), last = H.dates.length - 1;
    const total = last >= 0 ? perf(H.gain, H.value, H.purchases, i0, last) : {eur:null,pct:null};
    const rows = H.lines.map(l => ({l, ...perf(l.gain,l.values,l.purchases,i0,last)})).filter(x => x.eur !== null && Number.isFinite(x.eur));
    const missing = H.lines.length - rows.length;
    const absolute = rows.reduce((s,r) => s + Math.abs(r.eur), 0);
    rows.sort((a,b) => b.eur-a.eur);
    const side = (title, items) => `<div><h3>${title}</h3>${items.length ? items.slice(0,3).map(r => `<div class="contribution-row"><b>${J.esc(r.l.symbol)}</b><strong class="${J.cls(r.eur)}">${sgn(r.eur)}</strong><small>${absolute > 0 ? J.num(100*Math.abs(r.eur)/absolute,1) : '0'} % des mouvements en € · ${J.pct(r.pct,1)} de rendement propre</small></div>`).join('') : '<p class="small muted">Aucun titre dans cette catégorie.</p>'}</div>`;
    const host = J.$('#overview-movers');
    if (host) host.innerHTML = EVO.per === '1d' ? '<p>En 1 J, seule la valeur intraday des quantités actuelles est disponible. Choisissez une période plus longue pour les contributions.</p>' : `${missing ? `<p class="notice warn">Contributions partielles : ${missing} titre(s) non calculable(s). Les parts relatives portent uniquement sur les contributions connues.</p>` : ''}<div class="pf-contributions">${side('Contribuent aux gains', rows.filter(r=>r.eur>0))}${side('Contribuent aux pertes', [...rows].reverse().filter(r=>r.eur<0))}</div><p class="small">Résultat de la période : <b class="${J.cls(total.eur)}">${sgn(total.eur)}</b>. Part relative = contribution absolue ÷ somme des contributions absolues ; ce n’est pas un poids de portefeuille.</p>`;
    const text = EVO.per === 'all' ? 'Depuis le début' : 'Période : ' + (PERIODS.find(p=>p[0]===EVO.per)?.[1] || '1 M');
    if (J.$('#overview-period')) J.$('#overview-period').textContent = text + (H.dates.length && EVO.per !== '1d' ? ' · ' + J.date(H.dates[i0]) + ' → ' + J.date(H.dates[last]) : '') + ' · gains réalisés et latents, frais compris.';
  }
  function switchView(view) {
    VIEW = view;
    J.$$('#pf-nav [data-view]').forEach(b => { const active=b.dataset.view===view; b.classList.toggle('on',active); b.setAttribute('aria-selected',String(active)); b.tabIndex=active?0:-1; });
    J.$$('.pf-panel').forEach(p => p.hidden = p.dataset.panel !== view);
    if (view === 'analysis') drawEvo();
  }
  function periodStart(h) {
    if (EVO.per === 'all' || EVO.per === '1d' || !h.dates.length) return 0;
    const end=new Date(h.dates[h.dates.length-1]+'T12:00:00Z'), target=new Date(end);
    if(EVO.per==='1w') target.setUTCDate(target.getUTCDate()-7);
    else {const months={ '1m':1,'3m':3,'6m':6,'1y':12 }[EVO.per]||1, day=target.getUTCDate();target.setUTCDate(1);target.setUTCMonth(target.getUTCMonth()-months);const last=new Date(Date.UTC(target.getUTCFullYear(),target.getUTCMonth()+1,0)).getUTCDate();target.setUTCDate(Math.min(day,last));}
    const since=target.toISOString().slice(0,10);
    let index=0; h.dates.forEach((d,i)=>{if(d<=since)index=i;}); return index;
  }
  /* Gain / (valeur initiale + achats, frais compris). Les ventes restent dans le gain,
     jamais dans ce dénominateur. Sur Tout : gain total / achats cumulés, comme le résumé. */
  function perf(gain, values, purchases, i0, i) {
    if (i < 0 || gain[i] === undefined || gain[i] === null || (i0 > 0 && (gain[i0] === null || values[i0] === null))) return { eur: null, pct: null };
    const g = gain[i] - (i0 === 0 ? 0 : gain[i0]);
    const base = (i0 === 0 ? 0 : values[i0]) + purchases[i] - (i0 === 0 ? 0 : purchases[i0]);
    return { eur: g, pct: base > 0 ? 100 * g / base : null };
  }
  const PER_LABEL = { '1w': 'la semaine', '1m': 'le mois', '3m': '3 mois', '6m': '6 mois', '1y': 'un an', all: 'depuis le début' };
  const tradePrice = t => J.num(t.unit_price,4)+' '+(t.currency || 'devise inconnue');
  function purchaseMarkers(xs, time = false) {
    if (!ANALYSIS.markers || !xs.length) return [];
    return (H.trades || []).filter(t=>t.side==='buy' && !t.note && (!ANALYSIS.focus || t.key===ANALYSIS.focus) && t.date>=xs[0].slice(0,10) && t.date<=xs[xs.length-1].slice(0,10) && (!time || (t.trade_at.replace(' ','T')>=xs[0] && t.trade_at.replace(' ','T')<=xs[xs.length-1]))).map(t=>({x:time?t.trade_at.replace(' ','T'):t.date,kind:'buy',symbol:t.symbol,label:(t.first_buy?'Premier achat ':'Achat complémentaire ')+t.symbol,detail:`${J.num(t.quantity,4)} titre(s) · prix ${tradePrice(t)} · frais ${J.eur(t.fees_eur)} · change ${J.num(t.fx_to_eur,6)} €/unité · ${t.trade_at}`}));
  }
  function focusAnalysis(key, reveal = false) {
    ANALYSIS.focus=key; ANALYSIS.auto=false;
    CMP.delete('market:'+key);CMP.delete('t:'+key);EVO.hidden.delete('t:'+key);
    if(ANALYSIS.domain==='market'&&!(H.market?.lines||[]).some(l=>l.key===key))ANALYSIS.domain='personal';
    if(ANALYSIS.domain==='personal'&&EVO.mode==='value')EVO.mode='titles';
    drawEvo();
    if(reveal)J.$('#evo-chart').scrollIntoView({block:'start',behavior:'smooth'});
  }
  const positionKey = p => p.listing_id ? String(p.listing_id) : 'S'+p.symbol.toUpperCase();
  function lossHistory(dates, gains) {
    const known=gains.map((v,i)=>({v,i})).filter(x=>x.v!==null && Number.isFinite(x.v));
    const first=known.find(x=>x.v<0), last=known[known.length-1];
    if(!first)return {first:null,current:null};
    if(!last || last.i!==gains.length-1 || last.v>=0)return {first:dates[first.i],current:null};
    let start=last.i;
    while(start>0 && gains[start-1]!==null && gains[start-1]<0)start--;
    return {first:dates[first.i],current:dates[start],gap:start>0 && gains[start-1]===null};
  }
  function miniCurve(values) {
    const nums=values.filter(v=>v!==null && Number.isFinite(v));
    if(nums.length<2)return '<span class="small muted">Historique insuffisant</span>';
    const lo=Math.min(0,...nums),hi=Math.max(0,...nums),span=hi-lo||1,Y=v=>30-28*(v-lo)/span;
    let d='',pen=false;values.forEach((v,i)=>{if(v===null || !Number.isFinite(v)){pen=false;return;}d+=(pen?'L':'M')+(2+i*96/Math.max(1,values.length-1)).toFixed(1)+' '+Y(v).toFixed(1);pen=true});
    return `<svg viewBox="0 0 100 34" role="img" aria-label="Gain personnel, échelle propre à cette position"><line x1="2" x2="98" y1="${Y(0)}" y2="${Y(0)}" stroke="var(--line)"/><path d="${d}" fill="none" stroke="${nums[nums.length-1]<0?'var(--down)':'var(--up)'}" stroke-width="1.8"/></svg>`;
  }
  function analysisPositions(rows,i0,last) {
    const host=J.$('#analysis-positions');
    host.innerHTML=`<div class="analysis-positions-label"><b>${D.positions.length} position(s) détenue(s)</b><span>Mini-courbes : gain depuis les achats · échelles propres · clic pour suivre</span></div><div class="analysis-position-grid">${D.positions.map(p=>{
      const key=positionKey(p),l=H.lines.find(l=>l.key===key),r=rows.find(r=>r.l.key===key),v=l?perf(l.gain,l.values,l.purchases,0,last):{eur:null,pct:null};
      const values=l?l.gain.slice(i0).map((g,k)=>l.purchases[i0+k]>0?perf(l.gain,l.values,l.purchases,0,i0+k)[EVO.unit]:null):[];
      return `<button type="button" class="analysis-position" data-key="${J.esc(key)}" aria-pressed="${ANALYSIS.focus===key}"><span class="analysis-position-name"><b>${J.esc(p.symbol)}</b><strong class="${J.cls(v.eur)}">${EVO.unit==='pct'?J.pct(v.pct,1):J.eur(v.eur)}</strong></span>${miniCurve(values)}<span class="analysis-position-period">Période : ${J.eur(r?.eur)} · poids ${J.pct(p.weight,1,false)}</span>${v.eur===null?'<span class="small muted">Résultat indisponible</span>':''}</button>`;
    }).join('')}</div>`;
    host.querySelectorAll('[data-key]').forEach(b=>b.onclick=()=>focusAnalysis(b.dataset.key));
  }
  function analysisDetail(rows,last) {
    const host=J.$('#analysis-detail'),key=ANALYSIS.focus,l=H.lines.find(l=>l.key===key),r=rows.find(r=>r.l.key===key);
    if(!key||!l){host.innerHTML='<p class="small muted">Sélectionnez une position pour relier sa courbe, ses résultats et ses achats.</p>';return;}
    const p=D.positions.find(p=>positionKey(p)===key),g=p?insight(p).protection:null,personal=perf(l.gain,l.values,l.purchases,0,last),history=lossHistory(H.dates,l.gain),trades=(H.trades||[]).filter(t=>t.key===key&&t.side==='buy'&&!t.note);
    const fact=(label,value)=>`<div><span>${label}</span><b>${value}</b></div>`;
    host.innerHTML=`<div class="pf-section-title"><h3>${J.esc(l.symbol)} · ${J.esc(l.name)}</h3>${p?statusBadge(insight(p)):'<span class="badge">Position soldée</span>'}</div><div class="analysis-detail-facts">${fact('Premier achat',trades.length?J.date(trades[0].date):'Indisponible')}${fact('Depuis vos achats · ventes comprises',J.eur(personal.eur)+' · '+J.pct(personal.pct,1))}${fact('Contribution sur la période',J.eur(r?.eur)+' · '+J.pct(r?.pct,1)+' de rendement propre')}${fact('Poids actuel',p?J.pct(p.weight,1,false):'0 % · soldée')}${fact('Recul après achat',g?.available?'−'+J.num(g.drop_pct,2)+' %':'Non calculable')}</div>
      <p class="analysis-detail-reading">${personal.eur===null?'Résultat personnel indisponible.':personal.eur<0?'Cette position vous fait perdre depuis vos achats.':'Cette position reste '+(personal.eur>0?'bénéficiaire':'à l’équilibre')+' depuis vos achats.'} ${r?.eur===null?'Contribution de période indisponible.':r?.eur<0?'Elle pénalise le portefeuille sur la période.':'Elle ne pénalise pas le portefeuille sur la période.'} ${history.first?'Première perte observée : '+J.date(history.first)+'. ':''}${history.current?'Séquence de perte observée depuis le '+J.date(history.current)+(history.gap?' (historique précédent incomplet).':'.'):''} Ces dates décrivent les observations conservées, sans dater un franchissement entre deux cotations.</p>
      <details class="selected-purchases" open><summary>Achats de ${J.esc(l.symbol)} · ${trades.length}</summary>${trades.map(t=>`<div><b>${t.first_buy?'Premier achat':'Achat complémentaire'} · ${J.date(t.date)}</b><span>${J.num(t.quantity,4)} titre(s) à ${tradePrice(t)} · Frais ${J.eur(t.fees_eur)} · change ${J.num(t.fx_to_eur,6)} €/unité</span></div>`).join('')}</details>`;
  }
  function analysisPurchases() {
    const opened=new Set(J.$$('#analysis-purchases details[open]').map(e=>e.dataset.key));
    const groups=new Map();
    (H.trades||[]).filter(t=>t.side==='buy'&&!t.note).forEach(t=>{if(!groups.has(t.key))groups.set(t.key,[]);groups.get(t.key).push(t)});
    J.$('#analysis-purchases').innerHTML=[...groups].map(([key,trades])=>`<div class="purchase-group ${ANALYSIS.focus===key?'selected':''}"><button type="button" class="purchase-title" data-focus="${J.esc(key)}" aria-pressed="${ANALYSIS.focus===key}"><b>${J.esc(trades[0].symbol)}</b><span>${trades.length} achat(s)</span></button><div class="purchase-first"><time>${J.date(trades[0].date)}</time><span>Premier achat · ${J.num(trades[0].quantity,4)} titre(s) à ${tradePrice(trades[0])}</span></div>${trades.length>1?`<details data-key="${J.esc(key)}" ${opened.has(key)?'open':''}><summary>${trades.length-1} achat(s) complémentaire(s)</summary>${trades.slice(1).map(t=>`<p><time>${J.date(t.date)}</time> · ${J.num(t.quantity,4)} titre(s) à ${tradePrice(t)}<br><small>Frais ${J.eur(t.fees_eur)} · change ${J.num(t.fx_to_eur,6)} €/unité</small></p>`).join('')}</details>`:''}<small>Frais du premier achat ${J.eur(trades[0].fees_eur)} · change ${J.num(trades[0].fx_to_eur,6)} €/unité</small></div>`).join('')||'<p class="small muted">Aucun achat enregistré.</p>';
    J.$$('#analysis-purchases [data-focus]').forEach(b=>b.onclick=()=>focusAnalysis(b.dataset.focus));
    J.$('#clear-focus').hidden=!ANALYSIS.focus;
  }
  function analysisLosses(rows, total) {
    const host=J.$('#analysis-losses'), missing=rows.filter(r=>r.eur===null).length;
    const negatives=rows.filter(r=>r.eur!==null&&r.eur<0).sort((a,b)=>a.eur-b.eur);
    const leader=negatives[0];
    J.$('#analysis-priority').innerHTML=leader?`<button class="analysis-priority-button" data-focus="${J.esc(leader.l.key)}"><span>${missing?'Principal impact négatif connu · données partielles':'Principal impact négatif · période sélectionnée'}</span><b>${J.esc(leader.l.symbol)} · ${J.eur(leader.eur)}</b><small>${J.esc(leader.l.name)} · voir la courbe et les achats →</small></button>`:'<p class="small muted">Aucune contribution négative calculable sur la période.</p>';
    J.$('#analysis-priority [data-focus]')?.addEventListener('click',()=>focusAnalysis(leader.l.key));
    host.innerHTML=(missing?`<p class="notice warn">Contributions partielles : ${missing} titre(s) non calculable(s). Aucun gain total complet n’est déduit des seules lignes connues.</p>`:'')+(negatives.length?`<div class="loss-table"><div class="loss-head"><span>Titre</span><span>Impact période</span><span>Rendement période</span><span>Résultat personnel</span><span>Poids actuel</span><span>Recul après achat</span></div>${negatives.map(r=>{const p=D.positions.find(p=>(p.listing_id?String(p.listing_id):'S'+p.symbol.toUpperCase())===r.l.key),g=p?insight(p).protection:null;return `<article class="loss-row ${r===leader?'loss-leader':''} ${ANALYSIS.focus===r.l.key?'selected':''}" data-loss="${J.esc(r.l.key)}"><div><button class="purchase-title" data-focus="${J.esc(r.l.key)}"><b>${J.esc(r.l.symbol)}</b></button><small>${J.esc(r.l.name)}</small>${p?statusBadge(insight(p)):'<span class="badge">Soldée</span>'}</div><div data-label="Impact période" class="down"><b>${J.eur(r.eur)}</b></div><div data-label="Rendement période">${J.pct(r.pct,1)}</div><div data-label="Résultat personnel">${J.eur(r.l.gain[r.l.gain.length-1])}<small>depuis les achats · ventes comprises</small></div><div data-label="Poids actuel">${p?J.pct(p.weight,1,false):'0 % · soldée'}</div><div data-label="Recul après achat">${g?.available?'−'+J.num(g.drop_pct,2)+' %':'Indisponible'}</div><p class="loss-reason">${r.l.gain[r.l.gain.length-1]===null?'Résultat personnel indisponible.':r.l.gain[r.l.gain.length-1]<0?'Résultat personnel cumulé en perte, ventes comprises.':'Résultat personnel cumulé positif ou à l’équilibre, ventes comprises.'} Contribution négative de ${J.eur(Math.abs(r.eur))} sur la période. ${g?.available?'Recul du cours depuis le sommet observé après le dernier achat encore ouvert.':'Le recul après achat n’est pas calculable avec les données disponibles.'} Une baisse seule ne constitue pas un signal de vente.</p></article>`}).join('')}</div>`:'<p class="small muted">Aucune contribution négative calculable sur cette période.</p>')+`<p class="small">Résultat total de la période : <b class="${J.cls(total.eur)}">${sgn(total.eur)}</b>. Les contributions complètes en euros incluent gains et pertes, réalisés et latents.</p>`;
    host.querySelectorAll('[data-focus]').forEach(b=>b.onclick=()=>focusAnalysis(b.dataset.focus,true));
    host.querySelectorAll('[data-loss]').forEach(row=>row.onclick=e=>{if(!e.target.closest('button'))focusAnalysis(row.dataset.loss,true)});
  }
  function drawMarket() {
    const host=J.$('#evo-chart'), market=H.market||{dates:[],lines:[]}, h=EVO.per==='1d'?(market.intraday||{dates:[],lines:[]}):market;
    const i0=periodStart(h),xs=h.dates.slice(i0),index=ANALYSIS.scale==='index',focused=ANALYSIS.focus;
    const notes=[];
    const series=h.lines.map((l,k)=>{
      const values=l.prices.slice(i0),base=values[0],bad=(l.break_dates||[]).some(d=>d>xs[0]&&d<=xs[xs.length-1]);
      if(index && (!(base>0)||bad))notes.push(l.symbol+': base 100 indisponible (cours initial absent ou rupture non résolue).');
      if(values.some(v=>v===null))notes.push(l.symbol+': observations manquantes ; les trous ne sont pas remplacés.');
      if(l.last_date && H.dates.length && l.last_date<H.dates[H.dates.length-1])notes.push(l.symbol+': dernière clôture du '+J.date(l.last_date)+'.');
      return {id:'market:'+l.key,label:l.symbol+(index?'':' · '+(l.currency||'devise inconnue')),values:index?values.map(v=>v!==null&&base>0&&!bad?100*v/base:null):values,color:PAL[k%PAL.length],width:focused===l.key?3:1.8,opacity: focused && focused!==l.key ? .2 : 1,format:index?v=>J.num(v,2):v=>px(v,l.currency)};
    });
    const when=xs.length?J.date(xs[0].slice(0,10))+' → '+J.date(xs[xs.length-1].slice(0,10)):'';
    J.$('#period-reference').textContent=(EVO.per==='1d'?'Dernière séance intrajournalière enregistrée · ':'Cours observés · ')+when+' · '+(index?'base 100 à la même date, hors frais et change personnel.':'cours dans chaque devise d’origine, sans conversion en euros.');
    J.$('#evo-note').textContent=(H.notes||[]).concat(notes).join(' ')+' '+(EVO.per==='all'?'Tout = historique de marché disponible, qui peut commencer avant vos achats.':'')+' Les données conservées peuvent limiter la période demandée.';
    J.lineChart(host,xs,series,{height:innerWidth<700?200:230,label:'Cours des titres détenus',format:v=>J.num(v,2),time:EVO.per==='1d',markers:purchaseMarkers(xs,EVO.per==='1d'),verticalMarkers:true,selected:focused?'market:'+focused:null,hidden:CMP,onToggle:id=>{CMP.has(id)?CMP.delete(id):CMP.add(id);store('cmp_hidden',[...CMP]);drawEvo()}});
    if(EVO.per==='1d'&&ANALYSIS.markers)J.$('#evo-note').textContent+=' Seuls les achats dont l’heure enregistrée est dans la séance visible portent un repère ; tous restent consultables dans Mes achats.';
  }
  function drawEvo() {
    const host = J.$('#evo-chart'), mv = J.$('#movers'), h = H; if (!host || !h) return;
    updateOverview();
    J.$('#analysis-title').textContent=ANALYSIS.domain==='personal'?'Résultat de mes positions':'Cours des titres · hors investissement';
    const lastIndex=H.dates.length-1,startIndex=periodStart(H),contributions=H.lines.map(l=>({l,...(EVO.per==='1d'?{eur:null,pct:null}:perf(l.gain,l.values,l.purchases,startIndex,lastIndex))}));
    if(ANALYSIS.auto && EVO.per!=='1d'){const worst=contributions.filter(r=>r.eur!==null&&r.eur<0).sort((a,b)=>a.eur-b.eur)[0];ANALYSIS.focus=worst?.l.key||null;}
    analysisPositions(contributions,startIndex,lastIndex);analysisDetail(contributions,lastIndex);
    if(EVO.per==='1d'){J.$('#analysis-priority').innerHTML='<p class="small muted">Impact personnel en 1 J indisponible : choisir une période plus longue.</p>';}
    J.$('#market-controls').hidden=ANALYSIS.domain!=='market'; J.$('#personal-controls').hidden=ANALYSIS.domain!=='personal';
    J.$$('#analysis-domain button').forEach(b=>{b.classList.toggle('on',b.dataset.v===ANALYSIS.domain);b.setAttribute('aria-pressed',String(b.dataset.v===ANALYSIS.domain))});
    analysisPurchases();
    const reference = J.$('#period-reference');
    if (reference) reference.textContent = EVO.per === 'all' ? 'Tout : depuis la première transaction. Les gains réalisés restent inclus.' : 'Période affichée : ' + (PERIODS.find(p=>p[0]===EVO.per)?.[1] || '') + '. La colonne depuis vos achats conserve sa propre référence.';
    const last = h.dates.length - 1;
    const intraday = EVO.per === '1d', mode = intraday ? 'value' : EVO.mode, unit = mode === 'value' ? 'eur' : EVO.unit;
    J.$$('#evo-mode button').forEach(b => { b.disabled = intraday && b.dataset.v !== 'value'; b.classList.toggle('on', b.dataset.v === mode); b.title = b.disabled ? 'En 1 J, seule la valeur des quantités actuelles est disponible.' : ''; });
    const note = J.$('#evo-note');
    if (note) note.textContent = intraday ? '1 J : valeur en euros des quantités actuelles sur la dernière séance disponible. Comparaison et gain intraday indisponibles : les mouvements de la séance ne sont pas reconstitués.' : (h.notes || []).join(' ');
    const height = innerWidth < 700 ? 220 : 250, pct = unit === 'pct', fmtV = pct ? (v => J.pct(v, 1)) : eur0;
    J.$$('#evo-unit button').forEach(b => { b.disabled = mode === 'value' && b.dataset.v === 'pct'; b.classList.toggle('on', b.dataset.v === unit); b.title = b.disabled ? 'La valeur est exprimée en euros.' : ''; });
    if (!h.dates || !h.dates.length) { host.innerHTML = '<div class="lc-empty">Ajoutez une transaction pour voir l’évolution.</div>'; mv.innerHTML = ''; J.$('#analysis-losses').innerHTML='<p>Aucune transaction.</p>'; return; }
    const dd = h.dates.length > 1 && h.value[last] !== null && h.value[last - 1] !== null ? h.value[last] - h.value[last - 1] - (h.net_in[last] - h.net_in[last - 1]) : null;
    const hd = J.$('#hero-day'); if (hd && dd !== null) hd.innerHTML = `<span class="${J.cls(dd)}">${sgn(dd)}</span> depuis la clôture du ${J.date(h.dates[last - 1])}`;
    if (EVO.per === '1d') {
      const it = h.intraday || { t: [], value: [] };
      J.lineChart(host, it.t, [{ id: 'v', label: 'Valeur', values: it.value, color: '#6366f1', area: true }], { height, format: eur0, time: true, markers:purchaseMarkers(it.t,true), verticalMarkers:true });
      if (it.t.length < 2) host.querySelector('.lc-empty').textContent = 'Pas de cotations de 15 minutes enregistrées aujourd’hui pour vos titres.';
      const d0 = it.value[0], d1 = it.value[it.value.length - 1];
      mv.innerHTML = it.t.length > 1 ? `<h3>Aujourd’hui</h3><p class="mv-big ${J.cls(d1 - d0)}">${sgn(d0 === null || d1 === null ? null : d1 - d0)}</p><p class="small muted">Valeur des titres détenus aujourd’hui, de ${J.dateTime(it.t[0])} à ${J.dateTime(it.t[it.t.length - 1])}.</p>` : '';
      fillPeriodCells(null); J.$('#analysis-losses').innerHTML='<p class="small muted">Contributions personnelles indisponibles en 1 J : les transactions intrajournalières ne sont pas reconstituées. Choisissez une période plus longue.</p>'; if(ANALYSIS.domain==='market')drawMarket(); return;
    }
    const i0 = periodStart(h), xs = h.dates.slice(i0), idx = xs.map((_, k) => i0 + k);
    if(reference) reference.textContent = `Période visible : ${J.date(xs[0])} → ${J.date(xs[xs.length-1])}. `+(mode==='value'?'Valeur des titres et apports nets en euros.':ANALYSIS.reference==='purchase'?'Courbes personnelles : résultat cumulé depuis vos achats ; % = gain cumulé ÷ achats cumulés, frais compris.':'Courbes personnelles : gain sur la période ; % = gain de la période ÷ (valeur au départ + achats de la période).');
    const chartStart=ANALYSIS.reference==='purchase'?0:i0;
    const pfSeries = i => perf(h.gain, h.value, h.purchases, chartStart, i), lineSeries = (l, i) => perf(l.gain, l.values, l.purchases, chartStart, i);
    let series;
    if (mode === 'value') {
      series = [{ id: 'value', label: 'Valeur', values: idx.map(i => h.value[i]), color: '#6366f1', area: true }, { id: 'net', label: 'Apports nets', values: idx.map(i => h.net_in[i]), color: '#94a3b8', dash: '5 5', width: 1.6 }];
    } else {
      const tot = idx.map(i => pfSeries(i)[unit]), up = (tot[tot.length - 1] || 0) >= 0;
      const titles = h.lines.map((l, k) => ({ id: 't:' + l.key, label: l.symbol, values: idx.map(i => { const v = lineSeries(l, i); return l.purchases[i] > 0 ? v[unit] : null; }), color: PAL[k % PAL.length], width: 1.8 }));
      series = mode === 'gain' ? [{ id: 'gain', label: 'Portefeuille', values: tot, color: up ? '#16a34a' : '#dc2626', area: true }].concat(titles)
        : [{ id: 'gain', label: 'Portefeuille', values: tot, color: '#0f172a', width: 2.6, dash: '6 4' }].concat(titles);

    }
    if(ANALYSIS.focus && mode!=='value')series=series.map(s=>({...s,color:s.id==='t:'+ANALYSIS.focus && s.values[s.values.length-1]<0?'#dc2626':s.color,opacity:s.id==='t:'+ANALYSIS.focus?1:.15,width:s.id==='t:'+ANALYSIS.focus?3.5:s.width}));
    J.lineChart(host, xs, series, { height, format: mode === 'value' ? eur0 : fmtV, zeroLine: mode !== 'value', markers: purchaseMarkers(xs), verticalMarkers: true, hidden: new Set(), focusLegend: true, selected: ANALYSIS.focus?'t:'+ANALYSIS.focus:null, onToggle: id => {if(id.startsWith('t:'))focusAnalysis(id.slice(2));else{ANALYSIS.focus=null;ANALYSIS.auto=false;drawEvo();}} });
    // Barres divergentes : à gauche (rouge) ce qui fait baisser, à droite (vert) ce qui fait monter, sur la période choisie
    const periodLine=(l,i)=>perf(l.gain,l.values,l.purchases,i0,i);
    const allRows=h.lines.map(l=>({l,...periodLine(l,last)}));
    const periodTotal=perf(h.gain,h.value,h.purchases,i0,last);
    analysisLosses(allRows,periodTotal);
    const rows = allRows.filter(r => r.l.values.slice(i0).some(v => v > 0) || r.eur !== null && Math.abs(r.eur) >= .5);
    rows.sort((a, b) => (b[unit] ?? -1e9) - (a[unit] ?? -1e9));
    const tot = periodTotal, m = Math.max(1e-9, ...rows.map(r => Math.abs(r[unit] || 0)));
    const val = r => r[unit] === null || r[unit] === undefined ? '–' : pct ? J.pct(r[unit], 1) : sgn(r[unit]);
    mv.innerHTML = `<h3>Sur ${PER_LABEL[EVO.per] === 'depuis le début' ? 'toute la période' : PER_LABEL[EVO.per]}</h3>
      <p class="mv-big ${J.cls(tot.eur)}">${sgn(tot.eur)}${tot.pct !== null ? ` <small>${J.pct(tot.pct, 1)}</small>` : ''}</p>
      <div class="dv-head"><span class="down">fait baisser</span><span class="up">fait monter</span></div>
      <div class="dv">${rows.map(r => { const v = r[unit] || 0, w = (50 * Math.abs(v) / m).toFixed(1); return `<div class="dv-row" title="${J.esc(r.l.name)} : ${sgn(r.eur)}${r.pct !== null ? ' (' + J.pct(r.pct, 1) + ')' : ''} sur la période"><span class="dv-s">${J.esc(r.l.symbol)}</span><span class="dv-track"><i class="${v >= 0 ? 'up' : 'down'}" style="${v >= 0 ? 'left:50%' : 'right:50%'};width:${w}%"></i></span><span class="dv-v ${J.cls(v)}">${val(r)}</span></div>`; }).join('') || (tot.eur === null ? '<p class="small muted">Valorisation indisponible.</p>' : '<p class="small muted">Rien n’a bougé.</p>')}</div>
      <p class="small muted" style="margin-top:8px">${pct ? '% = gain sur la période ÷ argent engagé (valeur au début + achats pendant la période).' : 'Gain ou perte en euros sur la période, frais compris. Le pourcentage rapporte ce gain à la valeur au départ + achats de la période ; ce n’est pas un rendement annualisé ni pondéré dans le temps.'}</p>`;
    fillPeriodCells(new Map(h.lines.map(l => [l.key, periodLine(l, last)])));
    if(ANALYSIS.domain==='market')drawMarket();
  }
  const CMP = new Set(store('cmp_hidden') || []);
  /* Colonne « Sur la période » du tableau des positions, remplie quand l'évolution est chargée. */
  function fillPeriodCells(map) {
    const lab = (PERIODS.find(p => p[0] === EVO.per) || [, 'Tout'])[1];
    J.$$('.per-h').forEach(e => { e.textContent = EVO.per === '1d' ? 'Sur 1 J' : 'Sur ' + (EVO.per === 'all' ? 'tout' : lab); });
    J.$$('[data-per]').forEach(td => { const r = map && map.get(td.dataset.per); td.className = 'num per ' + (r ? J.cls(r.eur) : '');
      td.innerHTML = r ? `<b>${sgn(r.eur)}</b><div class="ps">${r.pct !== null ? J.pct(r.pct, 1) : ''}</div>` : (EVO.per === '1d' ? '<span class="muted">Non calculé en 1 J</span>' : '<span class="muted">–</span>'); });
  }
  /* ── Alertes, ventes, répartition, transactions : repliés par défaut ── */
  function lotsBody(d) {
    const groups = new Map();
    d.lots.forEach(l => { const label=l.alert?.strategy_label || 'Non renseignée', rule=l.alert?.rules||{}, key=label+JSON.stringify([rule.days,rule.drop,rule.off,rule.exit]); if(!groups.has(key))groups.set(key,{label,rule,lots:[]});groups.get(key).lots.push(l); });
    return `<p class="small muted">Les règles communes sont regroupées par stratégie et réglages effectifs. Les réglages individuels restent accessibles à la demande. Aucune vente n’est automatique.</p>${[...groups.values()].map(({label,rule,lots})=>`<details><summary>${J.esc(label)} · ${lots.length} achat(s)</summary><p class="small muted">${rule.off?'Alertes désactivées':`Rappel : ${rule.days || 'aucun'} jours · recul : ${rule.drop ? J.num(rule.drop,1)+' %' : 'sans seuil'}${rule.exit==='momentum_negative'?' · momentum 6 mois négatif':rule.exit==='below_ma50'?' · sous la moyenne 50 j':''}`}</p>${lots.map(l=>`<div class="lot-detail"><b>${J.esc(l.name||l.symbol)}</b> · ${J.date(l.trade_at)} · ${J.num(l.remaining,4)} titre(s) ${l.alert?.rules?.personal?'<span class="badge accent">personnalisé</span>':''}<button class="btn small" data-lot="${l.tx_id}">Régler cet achat</button></div>`).join('')}</details>`).join('')}`;
  }
  function salesBody(d) {
    return `<div class="table-wrap"><table><thead><tr><th>Date</th><th>Titre</th><th class="num">Produit net</th><th class="num hide-s">Prix de revient</th><th class="num">Gain</th></tr></thead><tbody>
      ${d.sales.map(x => `<tr><td>${J.date(x.trade_at)}</td><td>${x.listing_id ? `<a href="titre.html?id=${x.listing_id}" target="_blank" rel="noopener"><b>${J.esc(x.name || x.symbol)}</b></a>` : `<b>${J.esc(x.name || x.symbol)}</b>`}<div class="ps">${J.esc(x.symbol)} · ${J.num(x.quantity, 4)} vendu(s)</div></td><td class="num">${J.eur(x.proceeds)}</td><td class="num hide-s">${J.eur(x.cost)}</td><td class="num ${J.cls(x.gain)}"><b>${sgn(x.gain)}</b><div class="ps">${J.pct(x.gain_pct, 1)}</div></td></tr>`).join('')}</tbody></table></div>`;
  }
  function allocBody(a) {
    const rows = a.rows.filter(r => r.value_eur > 0 || (a.target && r.zone !== 'other')).map(r => `<tr><td>${J.esc(r.label)}</td><td class="num">${J.eur(r.value_eur, 0)}</td><td class="num">${r.current_pct === null ? '–' : J.pct(r.current_pct, 0, false)}</td>${a.target ? `<td class="num">${r.target_pct === null ? '–' : J.pct(r.target_pct, 0, false)}</td><td class="num ${r.off_target ? 'neg' : ''}">${r.gap_eur === null ? '–' : (r.gap_eur >= 0 ? 'acheter ' : 'vendre ') + J.eur(Math.abs(r.gap_eur), 0)}</td>` : ''}</tr>`).join('');
    return `<p class="small muted">${a.target ? `Cible : ${a.rows.filter(r => r.zone !== 'other').map(r => `${J.esc(r.label)} ${J.num(r.target_pct, 0)} %`).join(' · ')}. Rééquilibrer une fois par an, ou quand une zone s’écarte de ${J.num(a.tolerance, 0)} points.` : 'Stratégie prudente : des ETF larges et peu chers, 50 % États-Unis, 25 % Europe, 25 % émergents, rééquilibrés une fois par an.'}</p>
      ${a.rebalance_suggested ? '<div class="notice warn">Une zone s’écarte de la cible : un rééquilibrage peut être envisagé.</div>' : ''}
      ${rows ? `<div class="table-wrap"><table><thead><tr><th>Zone</th><th class="num">Valeur</th><th class="num">Part</th>${a.target ? '<th class="num">Cible</th><th class="num">Pour y revenir</th>' : ''}</tr></thead><tbody>${rows}</tbody></table></div>` : ''}
      <div class="row" style="margin-top:8px">${a.target ? '<button class="btn small" id="alloc-edit">Modifier la cible</button><button class="btn small" id="alloc-off">Retirer la cible</button>' : '<button class="btn small primary" id="alloc-prudent">Utiliser 50 / 25 / 25</button><button class="btn small" id="alloc-edit">Autre répartition…</button>'}
        ${['us', 'eu', 'emerging'].map(z => `<a class="btn small" href="index.html?kind=large_etf&geo_region=${z}&max_fee=0.3" target="_blank" rel="noopener">Gros ETF ${z === 'us' ? 'US' : z === 'eu' ? 'Europe' : 'émergents'}</a>`).join('')}</div>`;
  }
  function txBody(d) {
    return `<div class="row" style="justify-content:flex-end;margin-bottom:6px"><a class="btn small" href="api.php?r=export&id=${current}">Exporter en CSV</a></div><div class="table-wrap"><table><thead><tr><th>Date</th><th>Titre</th><th class="num">Quantité</th><th class="num">Prix</th><th class="num hide-s">Frais</th><th></th></tr></thead><tbody>
      ${d.transactions_list.map(x => `<tr><td>${J.date(x.trade_at)}</td><td><span class="badge ${x.side === 'buy' ? 'ok' : 'wait'}">${x.side === 'buy' ? 'Achat' : 'Vente'}</span> ${J.esc(x.name || x.symbol)} <span class="muted small">${J.esc(x.symbol)}</span></td><td class="num">${J.num(+x.quantity, 4)}</td><td class="num">${J.money(+x.unit_price, x.currency)}</td><td class="num hide-s">${x.fees ? J.eur(+x.fees) : '–'}</td>
        <td class="num"><button class="btn small" data-edit="${x.id}">Modifier</button> <button class="btn small danger" data-del="${x.id}" aria-label="Supprimer">✕</button></td></tr>`).join('') || '<tr><td colspan="6" class="empty">Aucune transaction.</td></tr>'}</tbody></table></div>`;
  }

  async function render() {
    list = (await J.api('portfolios')).portfolios;
    if (!list.length) { page.innerHTML = `<h1>Portefeuilles</h1><div class="card empty"><p>Vous n’avez pas encore de portefeuille.</p><button class="btn primary" id="first">Créer mon premier portefeuille</button></div>`; J.$('#first').onclick = createPf; return; }
    if (!list.find(p => p.id === current)) current = list[0].id;
    const d = D = await J.api('portfolio', { params: { id: current } });
    H = null; ANALYSIS.focus=null; ANALYSIS.auto=true;
    history.replaceState(null, '', '?id=' + current);
    const nAlerts = (d.lots || []).filter(l => l.alert && (l.alert.level === 'act' || l.alert.level === 'watch')).length;
    const etfHtml = JEtf.portfolio(d.etf_analysis);
    page.innerHTML = `${d.integrity && !d.integrity.ok ? `<div class="notice err">${d.integrity.issues.map(x => J.esc(x.message)).join('<br>')}</div>` : ''}
      <header class="pf-toolbar"><div><h1>Mes portefeuilles</h1><label class="sr-only" for="pf-select">Portefeuille affiché</label><select id="pf-select">${list.map(p=>`<option value="${p.id}" ${p.id===current?'selected':''}>${J.esc(p.name)}${p.is_default?' ★':''}</option>`).join('')}</select><button class="btn small" id="new-pf" aria-label="Créer un portefeuille">＋</button></div><button class="btn primary" id="add-tx">＋ Transaction</button></header>
      ${d.totals.unpriced ? '<div class="notice warn">Position(s) sans cours ou change exploitable : valorisation et gain total indisponibles. Aucun prix d’achat n’est utilisé comme cours actuel.</div>' : ''}${splitNotice(d.positions)}
      <nav class="pf-nav" id="pf-nav" role="tablist" aria-label="Espaces du portefeuille">${[['overview','Vue d’ensemble'],['positions','Mes positions'],['analysis','Évolution et analyse'],['manage','Historique et gestion']].map(([k,l])=>`<button type="button" role="tab" data-view="${k}" id="tab-${k}" aria-controls="panel-${k}">${l}</button>`).join('')}</nav>
      <section class="pf-panel" role="tabpanel" aria-labelledby="tab-overview" id="panel-overview" data-panel="overview">${hero(d)}${attention(d)}${overviewContributions()}</section>
      <section class="pf-panel" role="tabpanel" aria-labelledby="tab-positions" id="panel-positions" data-panel="positions"><div class="pf-section-title"><h2>Mes positions <span class="cnt">${d.positions.length}</span></h2><label>Trier <select id="position-sort">${[['attention','Priorité de surveillance'],['loss','Plus grosses pertes'],['gain','Plus gros gains'],['drop','Recul depuis le sommet'],['weight','Poids dans le portefeuille']].map(([v,l])=>`<option value="${v}" ${SORT===v?'selected':''}>${l}</option>`).join('')}</select></label></div><p class="small muted">Depuis vos achats = gain latent des titres restants (PMP). Sur la période = résultat du titre, ventes comprises. Choisissez la période dans Évolution et analyse.</p><div id="position-cards">${positionCards(d)}</div></section>
      <section class="pf-panel" role="tabpanel" aria-labelledby="tab-analysis" id="panel-analysis" data-panel="analysis">${analysis(d)}</section>
      <section class="pf-panel" role="tabpanel" aria-labelledby="tab-manage" id="panel-manage" data-panel="manage">
        ${section('tx','Transactions','',txBody(d))}${d.sales.length?section('sales','Ventes réalisées','',salesBody(d)):''}
        ${d.lots.length?section('lots','Réglages des achats et alertes','',lotsBody(d)):''}
        ${d.allocation?.rows?section('alloc','Répartition par zone','',allocBody(d.allocation)):''}
        ${d.positions.some(p=>p.kind==='etf')&&etfHtml?section('etf','Secteurs de vos ETF','',etfHtml.replace(/^<div class="card">\s*<h2>[^<]*<\/h2>/,'<div>')):''}
        ${section('settings','Réglages du portefeuille','',`<div class="row"><button class="btn small" id="rename">Renommer</button>${d.portfolio.is_default?'':'<button class="btn small" id="mk-default">Définir par défaut</button>'}<button class="btn small danger" id="del-pf">Supprimer</button></div><p class="small muted">Stratégie : ${J.esc(d.portfolio.strategy ? (NAMES[d.portfolio.strategy.name] || 'Personnalisée') : 'Croissance régulière par défaut')}. Réglage depuis l’Explorer.</p>`)}
      </section>`;
    folds();
    J.$('#pf-select').onchange = e => { current=+e.target.value; render(); };
    J.$$('#pf-nav [data-view]').forEach((b,index,buttons) => {
      b.onclick=()=>switchView(b.dataset.view);
      b.onkeydown=e=>{ const delta={ArrowRight:1,ArrowLeft:-1}[e.key]; if(delta){e.preventDefault();const next=buttons[(index+delta+buttons.length)%buttons.length];switchView(next.dataset.view);next.focus();} };
    });
    const bindPositions = () => {
      J.$$('[data-chart]').forEach(b=>b.onclick=()=>chartDialog(d,d.positions.find(p=>p.listing_id==b.dataset.chart)));
      J.$$('[data-lv]').forEach(b=>b.onclick=()=>levelsDialog(d.positions.find(p=>p.listing_id==b.dataset.lv)));
      J.$$('[data-lot]').forEach(b=>b.onclick=()=>lotDialog(d,d.lots.find(l=>l.tx_id==b.dataset.lot)));
    };
    J.$('#position-sort').onchange=e=>{SORT=e.target.value;J.$('#position-cards').innerHTML=positionCards(d);bindPositions();if(H)drawEvo();};
    J.$$('[data-switch]').forEach(b=>b.onclick=()=>switchView(b.dataset.switch));
    J.$$('[data-inspect]').forEach(b=>b.onclick=()=>{store('inspect',b.dataset.inspect);J.$('#position-cards').innerHTML=positionCards(d);bindPositions();switchView('positions');const target=J.$$('[data-position]').find(e=>e.dataset.position===b.dataset.inspect);target?.scrollIntoView({block:'nearest'});if(H)drawEvo();});
    switchView(VIEW);
    J.$('#new-pf').onclick = createPf;
    J.$$('#evo-mode button, #evo-per button, #evo-unit button').forEach(b => b.onclick = e => { e.stopPropagation(); if (b.disabled) return; const k = { 'evo-mode': 'mode', 'evo-per': 'per', 'evo-unit': 'unit' }[b.parentElement.id]; EVO[k] = b.dataset.v; store(k === 'mode' ? 'evo_mode2' : 'evo_' + k, EVO[k]); J.$$('#' + b.parentElement.id + ' button').forEach(x => x.classList.toggle('on', x === b)); drawEvo(); });
    J.$$('#analysis-domain button, #market-scale button').forEach(b=>b.onclick=()=>{ANALYSIS[b.parentElement.id==='analysis-domain'?'domain':'scale']=b.dataset.v;J.$$('#'+b.parentElement.id+' button').forEach(x=>x.classList.toggle('on',x===b));drawEvo()});
    J.$('#purchase-markers').checked=ANALYSIS.markers;J.$('#purchase-markers').onchange=e=>{ANALYSIS.markers=e.target.checked;drawEvo()};
    J.$('#personal-reference').value=ANALYSIS.reference;J.$('#personal-reference').onchange=e=>{ANALYSIS.reference=e.target.value;drawEvo()};
    J.$('#clear-focus').onclick=()=>{ANALYSIS.focus=null;ANALYSIS.auto=false;drawEvo()};
    const pid = current;
    J.api('portfolio/history', { params: { id: pid } }).then(h => { if (pid !== current) return; H = h; drawEvo(); }).catch(e => { const c = J.$('#evo-chart'); if (c) c.innerHTML = `<div class="notice err">${J.esc(e.message)}</div>`; });
    J.$$('[data-lot]').forEach(b => b.onclick = () => lotDialog(d, d.lots.find(x => x.tx_id == b.dataset.lot)));
    const ap = J.$('#alloc-prudent'); if (ap) ap.onclick = async () => { await J.post('portfolio/target', { id: current, target: { us: 50, eu: 25, emerging: 25 } }); render(); };
    const ae = J.$('#alloc-edit'); if (ae) ae.onclick = () => allocationDialog(d.allocation);
    const ao = J.$('#alloc-off'); if (ao) ao.onclick = async () => { await J.post('portfolio/target', { id: current, target: null }); render(); };
    J.$$('[data-lv]').forEach(b => b.onclick = e => { e.stopPropagation(); levelsDialog(d.positions.find(x => x.listing_id == b.dataset.lv)); });
    J.$$('[data-chart]').forEach(b => b.onclick = e => { e.stopPropagation(); e.preventDefault(); chartDialog(d, d.positions.find(x => x.listing_id == b.dataset.chart)); });

    J.$('#add-tx').onclick = () => J.txDialog({ portfolios: list, portfolioId: current, onDone: render });
    J.$$('[data-edit]').forEach(b => b.onclick = () => J.txDialog({ portfolios: list, portfolioId: current, tx: d.transactions_list.find(x => x.id == b.dataset.edit), onDone: render }));
    J.$$('[data-del]').forEach(b => b.onclick = async () => { if (await J.confirm('Supprimer la transaction', 'Cette transaction sera supprimée définitivement.', 'Supprimer')) { await J.post('tx/delete', { id: +b.dataset.del }); render(); } });
    J.$('#rename').onclick = () => J.dialog({ title: 'Renommer', body: J.field('Nom', `<input id="nm" value="${J.esc(d.portfolio.name)}">`), actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async dlg => { await J.post('portfolio/rename', { id: current, name: J.$('#nm', dlg).value }); render(); } }] });
    const mk = J.$('#mk-default'); if (mk) mk.onclick = async () => { await J.post('portfolio/default', { id: current }); render(); };
    J.$('#del-pf').onclick = () => J.dialog({ title: 'Supprimer le portefeuille', body: `<p>Supprimer « ${J.esc(d.portfolio.name)} » et ses ${d.transactions_list.length} transactions ? Cette action est définitive.</p>${d.transactions_list.length ? J.field('Pour confirmer, tapez le nom du portefeuille', '<input id="cf">') : ''}`, actions: [{ label: 'Annuler', run: () => { } }, { label: 'Supprimer', cls: 'danger', run: async dlg => { await J.post('portfolio/delete', { id: current, confirm: J.$('#cf', dlg)?.value || '' }); render(); } }] });
  }

  /* ── Courbe d'un titre : instantanée pour les périodes en jours (série déjà chargée), 15 min pour 1 J et 1 S ── */
  function chartDialog(d, p) {
    if (!p || !p.listing_id) return;
    const c = (d.curves || {})[p.listing_id] || {}, dly = (c.daily || []).map(x => [x[0], x[1], null]), since = (p.first_buy || '').slice(0, 10), from = Math.max(0, dly.findIndex(x => x[0] >= since) - 1), n = dly.length - from;
    const GR = [['1d', '1 J'], ['1w', '1 S'], ['buy', 'Depuis l’achat'], ['1m', '1 M'], ['3m', '3 M'], ['6m', '6 M'], ['1y', '1 A'], ['all', 'Tout']], SESS = { '1m': 21, '3m': 63, '6m': 126, '1y': 252, all: 0 };
    let gr = store('chart_gr') || 'buy'; if (!GR.find(g => g[0] === gr)) gr = 'buy';
    const cur = p.price_currency || p.currency;
    const dlg = J.dialog({ title: p.name_catalogue || p.name || p.symbol, body: `${pills('pc-gr', GR, gr)}<div id="pc" class="pc-box"></div><p class="small muted" id="pc-n"></p>
      <p class="small"><a href="titre.html?id=${p.listing_id}" target="_blank" rel="noopener">Ouvrir la fiche complète ↗</a> · <a href="#" id="pc-lv">Filet de sécurité et objectif</a></p>`, actions: [{ label: 'Fermer', run: () => { } }] });
    dlg.classList && dlg.classList.add('wide');
    const buys = d.transactions_list.filter(x => x.side === 'buy' && x.listing_id == p.listing_id).map(x => ({ date: x.trade_at.slice(0, 10), label: 'Achat ' + J.date(x.trade_at) }));
    const open = (d.lots || []).filter(l => l.listing_id == p.listing_id && l.alert && l.alert.measures), first = open[0], lv = [];
    if (p.levels && p.levels.stop) lv.push({ value: +p.levels.stop, label: 'Filet de sécurité' });
    if (first && first.alert.rules && first.alert.rules.drop && !first.alert.rules.off) lv.push({ value: first.alert.measures.high * (1 - first.alert.rules.drop / 100), label: `Alerte −${J.num(first.alert.rules.drop, 0)} %` });
    const host = () => J.$('#pc', dlg), note = t => { J.$('#pc-n', dlg).textContent = t; };
    const draw = () => {
      J.$$('#pc-gr button', dlg).forEach(x => x.classList.toggle('on', x.dataset.v === gr));
      if (gr === '1d') { note('Les deux dernières séances, barre par barre (15 minutes).'); J.intradayPanel(host(), p.listing_id); return; }
      if (gr === '1w') { host().innerHTML = '<div class="lc-empty"><span class="spinner"></span></div>'; J.api('bars15', { params: { id: p.listing_id } }).then(w => { if (gr !== '1w') return;
          const r = w.bars.length > 1 ? J.priceChart(host(), w.bars, { sessions: 0, intraday: true, ma20: false, ma50: false, volume: false, unit: cur, levels: lv }) : (host().innerHTML = '<div class="lc-empty">Pas de barres de 15 minutes enregistrées cette semaine pour ce titre.</div>', null);
          note(r ? `${J.pct(r.perf, 1)} sur la semaine.` : ''); }).catch(e => { host().innerHTML = `<div class="notice err">${J.esc(e.message)}</div>`; }); return; }
      if (dly.length < 2) { host().innerHTML = '<div class="lc-empty">Pas d’historique pour ce titre.</div>'; note(''); return; }
      const r = J.priceChart(host(), dly, { sessions: gr === 'buy' ? Math.max(5, n) : SESS[gr], ma20: false, ma50: false, volume: false, unit: cur, marks: buys, levels: lv });
      note(r ? (gr === 'buy' ? `${J.pct(r.perf, 1)} depuis votre premier achat (${J.date(since)}), cours du titre hors frais et change.` : `${J.pct(r.perf, 1)} du ${J.date(r.from)} au ${J.date(r.to)}.`) : '');
    };
    J.$$('#pc-gr button', dlg).forEach(x => x.onclick = () => { gr = x.dataset.v; store('chart_gr', gr); draw(); });
    J.$('#pc-lv', dlg).onclick = e => { e.preventDefault(); dlg.close(); levelsDialog(p); };
    draw();
  }
  function levelsDialog(p) {
    if (!p) return;
    const L = p.levels || {}, cur = p.price_currency || p.currency;
    J.dialog({ title: 'Filet et objectif · ' + (p.name_catalogue || p.name || p.symbol), body: `<p class="small muted">Prix dans la devise du titre (${J.esc(cur || '')}). Repères personnels : rien n’est vendu automatiquement. Cours : ${px(p.price, cur)} · prix de revient moyen : ${J.eur(p.avg_cost)}.</p>${J.field('Filet de sécurité (stop)', `<input id="lv-stop" inputmode="decimal" value="${L.stop ?? ''}">`)}${J.field('Objectif', `<input id="lv-target" inputmode="decimal" value="${L.target ?? ''}">`)}`,
      actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async dlg => { const n = i => J.$(i, dlg).value.trim().replace(',', '.'); try { await J.post('position/levels', { portfolio_id: current, listing_id: p.listing_id, stop: n('#lv-stop'), target: n('#lv-target') }); } catch (e) { J.formError(dlg, e.message); return true; } render(); } }] });
  }
  function lotDialog(d, l) {
    const s = l.settings || {}, a = l.alert || {}, strategies = d.lot_strategies || {};
    const opts = `<option value="">Celle du portefeuille</option>` + Object.entries(strategies).map(([k, v]) => `<option value="${k}" ${s.strategy === k ? 'selected' : ''}>${J.esc(v)}</option>`).join('');
    J.dialog({ title: 'Achat du ' + J.date(l.trade_at) + ' · ' + (l.name || l.symbol), body: `<p class="small muted">Laissez vide pour garder la valeur par défaut de la stratégie${a.rules ? ` (actuellement : ${a.rules.days ? a.rules.days + ' jours' : 'pas de durée'}, ${a.rules.drop ? '−' + a.rules.drop + ' %' : 'pas de seuil de recul'})` : ''}.</p>
      ${J.field('Stratégie de cet achat', `<select id="lt-st">${opts}</select>`)}${J.field('Rappel après (jours de détention)', `<input id="lt-days" inputmode="numeric" value="${s.alert_days ?? ''}" placeholder="défaut de la stratégie">`)}${J.field('Alerte si recul depuis le plus haut (%)', `<input id="lt-drop" inputmode="decimal" value="${s.alert_drop_pct ?? ''}" placeholder="défaut de la stratégie">`)}
      <label class="check"><input type="checkbox" id="lt-off" ${s.alerts_off ? 'checked' : ''}> Désactiver les alertes de cet achat</label>`,
      actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async dlg => { const v = i => J.$(i, dlg).value.trim().replace(',', '.'); try { await J.post('lot/settings', { tx_id: l.tx_id, strategy: v('#lt-st'), alert_days: v('#lt-days'), alert_drop_pct: v('#lt-drop'), alerts_off: J.$('#lt-off', dlg).checked }); } catch (e) { J.formError(dlg, e.message); return true; } render(); } }] });
  }
  function allocationDialog(a) {
    const t = (a && a.target) || { us: 50, eu: 25, emerging: 25 };
    J.dialog({ title: 'Répartition cible par zone', body: `<p class="small muted">Trois parts en %, total 100.</p>${J.field('États-Unis (%)', `<input id="al-us" inputmode="decimal" value="${t.us}">`)}${J.field('Europe (%)', `<input id="al-eu" inputmode="decimal" value="${t.eu}">`)}${J.field('Émergents (%)', `<input id="al-em" inputmode="decimal" value="${t.emerging}">`)}`,
      actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async dlg => { const n = i => J.$(i, dlg).value.trim().replace(',', '.'); try { await J.post('portfolio/target', { id: current, target: { us: n('#al-us'), eu: n('#al-eu'), emerging: n('#al-em') } }); } catch (e) { J.formError(dlg, e.message); return true; } render(); } }] });
  }
  function createPf() { J.dialog({ title: 'Nouveau portefeuille', body: J.field('Nom', '<input id="nm" maxlength="100" autofocus>'), actions: [{ label: 'Annuler', run: () => { } }, { label: 'Créer', cls: 'primary', run: async d => { const r = await J.post('portfolio/create', { name: J.$('#nm', d).value }); current = r.id; render(); } }] }); }
  let rs; addEventListener('resize', () => { clearTimeout(rs); rs = setTimeout(drawEvo, 150); });
  render();
})();
