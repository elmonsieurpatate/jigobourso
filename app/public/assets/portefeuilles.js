/* Page Portefeuilles — l'essentiel d'abord : valeur et gain, courbe compacte, ce qui fait bouger, positions ; le reste replié. */
(async () => {
  const user = await J.init('portefeuilles'); if (!user) return;
  const page = J.$('#page');
  let list = (await J.api('portfolios')).portfolios;
  let current = +new URLSearchParams(location.search).get('id') || (list.find(p => p.is_default) || list[0] || {}).id;
  const NAMES = { regular: 'Croissance régulière', fast: 'Croissance rapide', recovery: 'Rebond', low_volatility: 'Hausse calme', momentum: 'Momentum 6 mois (essai)', momentum12: 'Momentum 12 mois (essai)', momentum_risk: 'Momentum ajusté du risque (essai)' };
  const PAL = ['#6366f1', '#14b8a6', '#f59e0b', '#ec4899', '#3b82f6', '#84cc16', '#a855f7', '#ef4444', '#06b6d4', '#eab308', '#64748b', '#22c55e'];
  const store = (k, v) => { try { if (v === undefined) return JSON.parse(localStorage.getItem('jigo_pf_' + k)); localStorage.setItem('jigo_pf_' + k, JSON.stringify(v)); } catch (e) { return null; } };
  const EVO = { mode: ['portfolio','positions'].includes(store('cockpit_mode')) ? store('cockpit_mode') : 'positions', per: 'all', unit: store('evo_unit') === 'eur' ? 'eur' : 'pct', hidden: new Set(store('evo_hidden') || []) };
  const PERIODS = [['1d', '1 J', 0], ['1w', '1 S', 8], ['1m', '1 M', 31], ['3m', '3 M', 92], ['6m', '6 M', 183], ['1y', '1 A', 366], ['all', 'Tout', 0]];
  const px = (v, c) => v === null || v === undefined ? '–' : J.money(v, c || 'EUR');
  const eur0 = v => J.eur(v, 0), sgn = v => v === null || v === undefined ? '–' : (v > 0 ? '+' : v < 0 ? '−' : '') + J.eur(Math.abs(v), 2);
  const pills = (id, items, cur) => `<div class="pills" id="${id}">${items.map(([k, l]) => `<button type="button" data-v="${k}" class="${k === cur ? 'on' : ''}">${l}</button>`).join('')}</div>`;
  const splitNotice = positions => positions.filter(p => p.splits_applied && p.splits_applied.length).map(p => `<div class="notice" style="margin-top:12px"><b>${J.esc(p.name_catalogue || p.name || p.symbol)}</b> : ${p.splits_applied.map(a => a.ratio >= 1 ? `split ${J.num(a.ratio, 2)} pour 1` : `regroupement ${J.num(1 / a.ratio, 2)} pour 1`).join(', ')} pris en compte automatiquement : la quantité affichée est celle d’aujourd’hui, le prix de revient total est inchangé.</div>`).join('');
  const ANALYSIS = { markers: true, focus: null, auto: true, separate: false, detail: false };
  let VIEW = 'home';
  let SORT = store('cockpit_sort') || 'loss';
  let D = null, H = null;                       // données du portefeuille affiché, et son évolution (chargée à part)

  /* ── Blocs repliables : un clic sur l'en-tête ; choix mémorisé dans ce navigateur. Par défaut, seuls l'essentiel et les positions sont ouverts. ── */
  const FOLD_DEFAULT = { etf: true, alloc: true, lots: true, sales: true, tx: true, settings: true, valuation: true };
  const section = (id, title, extra, body, cls = '') => `<section class="card fold ${cls}" data-fold="${id}"><header class="fold-h"><h2>${title}</h2><div class="fold-x">${extra || ''}</div><span class="chev" aria-hidden="true"></span></header><div class="fold-b">${body}</div></section>`;
  function folds() {
    const saved = Object.assign({}, FOLD_DEFAULT, store('folds2') || {});
    J.$$('#page [data-fold]').forEach(c => {
      c.classList.toggle('folded', !!saved[c.dataset.fold]);
      const h = c.querySelector('.fold-h') || c.firstElementChild; if (!h) return;
      h.classList.add('fold-h'); h.tabIndex=0; h.setAttribute('role','button'); h.setAttribute('aria-expanded',String(!c.classList.contains('folded')));
      h.onkeydown=e=>{if(e.target===h && ['Enter',' '].includes(e.key)){e.preventDefault();h.click();}};
      h.addEventListener('click', e => { if (e.target.closest('button, a, input, select, .pills')) return; c.classList.toggle('folded'); h.setAttribute('aria-expanded',String(!c.classList.contains('folded'))); const f = Object.assign({}, FOLD_DEFAULT, store('folds2') || {}); f[c.dataset.fold] = c.classList.contains('folded'); store('folds2', f); if (c.dataset.fold === 'valuation' && !c.classList.contains('folded')) drawEvo(); });
    });
  }

  const STATUS = { normal: ['ok', 'Normal'], watch: ['wait', 'À surveiller'], act: ['ko', 'À examiner'], unknown: ['', 'Données insuffisantes'] };
  const positionLots = (d,p) => d.lots.filter(l => p.listing_id ? l.listing_id === p.listing_id : !l.listing_id && l.symbol === p.symbol);
  const insight = p => (D.insights || {})[p.key] || { status: 'unknown', label: 'Données insuffisantes', reasons: [], market: {} };
  function statusBadge(i) { const c = STATUS[i.status] || STATUS.unknown; return `<span class="badge ${c[0]}">${J.esc(i.label || c[1])}</span>`; }
  function priority(i) { return ({ act: 3, watch: 2, unknown: 1, normal: 0 })[i.status] || 0; }
  function gainProtection(g, compact = false) {
    if (!g || !g.available) return `<p class="small muted">${J.esc(g?.reason || 'Sommet depuis l’achat indisponible.')}</p>`;
    const used = Math.max(0, g.peak_gain_pct), kept = Math.max(0, Math.min(100, used > 0 ? 100 * Math.max(0, g.gain_pct) / used : 0));
    return `<div class="protection"><div class="protection-values"><span>Meilleur gain observé <b>${J.pct(g.peak_gain_pct, 1)}</b></span><span>Actuel <b class="${J.cls(g.gain_pct)}">${J.pct(g.gain_pct, 1)}</b></span><span>Gain rendu <b>${J.num(g.given_back_pp, 1)} points</b></span></div><div class="protection-track" role="img" aria-label="${J.num(kept, 0)} % du gain positif observé conservé"><i style="width:${kept.toFixed(2)}%"></i></div>${compact ? `<p class="small muted">Position actuelle suivie depuis le ${J.date(g.start)} · sommet ${px(g.high,g.currency)} · recul −${J.num(g.drop_pct,2)} %.</p>` : `<p class="small muted">Recul du cours : −${J.num(g.drop_pct, 2)} % depuis le sommet observé ${px(g.high,g.currency)}. Gains personnels calculés en euros ; le recul du cours utilise la devise du titre. Référence : ${J.date(g.start)} ; dernière valeur du ${J.date(g.value_date)} ; sommet du gain le ${J.date(g.peak_date)}.</p>`}</div>`;
  }
  function diagnosticDetails(p, i, d) {
    const m = i.market || {}, trend = { strong: 'hausse forte', steady: 'hausse soutenue', gentle: 'hausse douce', flat: 'pas de tendance nette', down: 'baisse' }[m.trend] || 'non mesurée';
    return `<div class="diagnostic-grid"><section><h4>Mon investissement · protection des gains</h4><p class="small muted">Quantités actuellement détenues, prix de revient moyen actuel. Comparaison depuis le dernier achat encore ouvert. Les détails de chaque achat suivent leur propre date et leur coût FIFO.</p>${gainProtection(i.protection)}</section><section><h4>État actuel du titre</h4>${!m.reliable ? '<p class="small muted">Données anciennes ou incomplètes : ces indicateurs ne permettent pas un diagnostic actuel fiable.</p>' : ''}<p class="small muted">Clôture de référence : ${m.as_of ? J.date(m.as_of) : 'indisponible'}.</p><dl class="market-facts"><dt>Tendance · 1 mois</dt><dd>${trend}</dd><dt>Momentum 6 mois</dt><dd>${J.pct(m.momentum_6m)}</dd><dt>Clôture / moyenne 50 j</dt><dd>${px(m.close, p.price_currency)} / ${px(m.ma50, p.price_currency)}</dd><dt>Moyenne 200 j</dt><dd>${px(m.ma200, p.price_currency)}</dd><dt>Volatilité · 3 mois</dt><dd>${m.volatility === null || m.volatility === undefined ? 'indisponible' : J.num(m.volatility, 2) + ' % par séance'}</dd></dl></section></div>
      <div class="diagnostic-reasons"><h4>Ce qui mérite votre attention</h4>${i.reasons?.length ? i.reasons.map(r => `<p><b>${J.esc(r.action || 'Observation')}.</b> ${J.esc(r.message)}</p>`).join('') : '<p>Aucun signal notable parmi les indicateurs disponibles.</p>'}<p class="small muted">Les observations ne sont ni une prévision ni un ordre de vente.</p></div>
      <details><summary>Détail par achat ouvert</summary>${positionLots(d,p).map(l => `<div class="lot-detail"><b>Achat du ${J.date(l.trade_at)}</b> · ${J.num(l.remaining, 4)} titre(s) · ${J.esc(l.alert?.strategy_label || '')}${gainProtection(l.alert?.protection)}<button class="btn small" data-lot="${l.tx_id}">Régler cet achat</button></div>`).join('')}</details>`;
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
  const tradePrice = t => J.num(t.unit_price,4)+' '+(t.currency || 'devise inconnue');
  function purchaseMarkers(xs, time = false, focus = ANALYSIS.focus) {
    if (!ANALYSIS.markers || !xs.length) return [];
    return (H.trades || []).filter(t=>t.side==='buy' && !t.note && (!focus || t.key===focus) && t.date>=xs[0].slice(0,10) && t.date<=xs[xs.length-1].slice(0,10) && (!time || (t.trade_at.replace(' ','T')>=xs[0] && t.trade_at.replace(' ','T')<=xs[xs.length-1]))).map(t=>({x:time?t.trade_at.replace(' ','T'):t.date,kind:'buy',key:t.key,symbol:t.symbol,label:(t.first_buy?'Premier achat ':'Achat complémentaire ')+t.symbol,detail:`${J.num(t.quantity,4)} titre(s) · prix ${tradePrice(t)} · frais ${J.eur(t.fees_eur)} · change ${J.num(t.fx_to_eur,6)} €/unité · ${t.trade_at}`}));
  }
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
    return `<svg viewBox="0 0 100 34" role="img" aria-label="Résultat personnel sur la période, échelle propre à cette position"><line x1="2" x2="98" y1="${Y(0)}" y2="${Y(0)}" stroke="var(--line)"/><path d="${d}" fill="none" stroke="${nums[nums.length-1]<0?'var(--down)':'var(--up)'}" stroke-width="1.8"/></svg>`;
  }
  function hero(d) {
    const t=d.totals,base=t.invested_total||0,g=t.total_gain;
    const tax=Object.values(d.realized_by_year||{}).reduce((s,v)=>s+Math.max(0,Number(v)||0),0);
    const net=g===null?null:g-.3*(tax+Math.max(0,Number(t.unrealized)||0));
    const rate=v=>v!==null&&base>0?J.pct(100*v/base,1):'–';
    return `<section class="card cockpit-summary" aria-label="Résumé financier"><div><span>Valeur actuelle des titres</span><strong class="hero-v">${J.eur(t.value)}</strong></div><div><span>Depuis le début · ventes comprises</span><strong class="hero-g ${J.cls(g)}">${sgn(g)} <small>${rate(g)}</small></strong></div><div><span id="summary-period-label">Sur la période</span><strong id="period-g">Chargement…</strong></div><div class="summary-secondary"><span>Capital encore investi <b>${J.eur(t.cost)}</b></span><span>Réalisé <b>${sgn(t.realized)}</b></span><span>Latent <b>${sgn(t.unrealized)}</b></span><span>Net d’impôt estimé <b>${sgn(net)} · ${rate(net)}</b></span></div><details class="pf-explain"><summary>Définitions et fiscalité indicative</summary><p>Gain cumulé = réalisé + latent. Pourcentage cumulé = gain ÷ achats cumulés (${J.eur(base)}, frais compris). Sur une période : gain ÷ (valeur au départ + achats), ventes non déduites du dénominateur. Le net conserve l’hypothèse forfaitaire de 30 % des gains annuels réalisés positifs et du latent positif, sans fiscalité personnelle, PEA ou reports de pertes. Liquidités et dividendes ne sont pas gérés. Le coût restant est au PMP ; les lots suivent le FIFO.</p></details></section>`;
  }
  function analysis(){return `<section class="card cockpit-analysis" aria-label="Évolution et contributions"><div class="pf-section-title"><h2>Évolution et contributions</h2><label>Lecture <select id="chart-measure"><option value="personal">Performance personnelle</option><option value="market">Évolution des cours</option><option value="contribution">Contribution au portefeuille</option></select></label></div><div class="cockpit-chart-tools">${pills('evo-unit',[['eur','€'],['pct','%']],EVO.unit)}<details class="chart-options"><summary>Options et données</summary><label><input type="checkbox" id="purchase-markers" checked> Repères d’achat</label><button type="button" class="btn small" id="show-all-series">Tout afficher</button><button type="button" class="btn small" id="refresh-history">Compléter l’historique du titre sélectionné</button></details><button class="btn small" id="isolate-series">Isoler la sélection</button><button class="btn small" id="clear-focus">Retirer la mise en évidence</button></div><p id="chart-meaning" class="small muted"></p><div id="series-list" aria-label="Séries affichées et mises en évidence"></div><p id="chart-window" class="small muted"></p><p id="evo-note" class="small muted" role="status"></p><div class="cockpit-chart-grid"><div id="chart-pane"><div id="evo-chart"></div></div><aside id="contributions" aria-label="Classement des contributions"></aside></div><div id="selection-summary" aria-live="polite"></div></section>`;}
  const positionKey=p=>p.listing_id?String(p.listing_id):'S'+p.symbol.toUpperCase();
  function snapshot(window=null){
    const last=H.dates.length-1;let start=periodStart(H),end=last;
    const bound=(dates,time,fallback)=>{let found=fallback;dates.forEach((d,i)=>{if(Date.parse(d.length===10?d+'T00:00:00Z':d+'Z')<=time*1000)found=i});return found};
    if(EVO.per==='1d'&&H.session){
      const it=H.session,n=it.dates.length;let a=0,b=n-1;if(window){a=bound(it.dates,window.from,0);b=bound(it.dates,window.to,n-1)}
      const delta=values=>b<0||values[b]==null||values[a]==null?null:values[b]-values[a],base=it.base===null?null:it.value[a];
      const totalEur=delta(it.gain);const rows=H.lines.map((l,k)=>{const sl=it.lines.find(x=>x.key===l.key),eur=sl?delta(sl.gain):null,own=sl?.values[a];return {l,eur,pct:eur!==null&&own>0?100*eur/own:null,contribution_pct:eur!==null&&base>0?100*eur/base:null,color:PAL[k%PAL.length]}});
      return {start:a,last:b,base,total:{eur:totalEur,pct:totalEur!==null&&base>0?100*totalEur/base:null},rows};
    }
    if(window){start=bound(H.dates,window.from,0);end=bound(H.dates,window.to,-1)}
    if(end<0)return {start:0,last:-1,base:0,total:{eur:0,pct:null},rows:H.lines.map((l,k)=>({l,eur:0,pct:null,contribution_pct:null,color:PAL[k%PAL.length]}))};
    const calc=l=>EVO.per==='1d'?{eur:null,pct:null}:perf(l.gain,l.values||l.value,l.purchases,start,end);
    const base=end<0||start>0&&H.value[start]===null?null:(start?H.value[start]:0)+H.purchases[end]-(start?H.purchases[start]:0);
    return {start,last:end,base,total:calc(H),rows:H.lines.map((l,k)=>{const r=calc(l);return {l,...r,contribution_pct:r.eur!==null&&base>0?100*r.eur/base:null,color:PAL[k%PAL.length]}})};
  }
  function focusAnalysis(key, detail=false, reveal=false) {
    ANALYSIS.focus=key;ANALYSIS.auto=false;ANALYSIS.detail=detail||ANALYSIS.detail;
    CHART.selected=new Set([key]);CHART.hidden.delete(key);DASH.titles=true;
    switchView('home');drawEvo();
    if(reveal)J.$('#evo-chart').scrollIntoView({block:'start',behavior:'smooth'});
  }
  function switchView(view) {
    VIEW=view;
    J.$$('#pf-nav [data-view]').forEach(b=>{const active=b.dataset.view===view;b.classList.toggle('on',active);b.setAttribute('aria-selected',String(active));b.tabIndex=active?0:-1});
    J.$$('.pf-panel').forEach(e=>e.hidden=e.dataset.panel!==view);
    if(H)drawEvo();
  }
  function heldPerformance(l,start,i,unit) {
    const held=l.quantities ? l.quantities[i]>1e-12 || i>0 && l.quantities[i-1]>1e-12 : l.purchases[i]>0;
    return held?perf(l.gain,l.values,l.purchases,start,i)[unit]:null;
  }
  function positionTable(d,s) {
    const items=d.positions.map(p=>{const key=positionKey(p),r=s?.rows.find(r=>r.l.key===key),i=insight(p);return {p,key,r,i}});
    const value=x=>SORT==='gain'?x.r?.eur:SORT==='impact'?Math.abs(x.r?.eur??NaN):SORT==='pct'?x.r?.pct:SORT==='weight'?x.p.weight:SORT==='drop'?x.i.protection?.drop_pct:SORT==='attention'?priority(x.i):x.r?.eur;
    items.sort((a,b)=>{const av=value(a),bv=value(b),ak=av!==null&&av!==undefined&&Number.isFinite(av),bk=bv!==null&&bv!==undefined&&Number.isFinite(bv);return ak!==bk?ak?-1:1:ak?(SORT==='loss'?av-bv:bv-av)||a.p.symbol.localeCompare(b.p.symbol):a.p.symbol.localeCompare(b.p.symbol)});
    return `<table class="positions-table"><thead><tr><th>Titre · premier achat</th><th>Valeur · poids</th><th>Sur la période</th><th>Depuis les achats</th><th>Recul observé</th><th>Surveillance</th></tr></thead><tbody>${items.map(({p,key,r,i})=>{
      const l=H?.lines.find(l=>l.key===key),c=l?perf(l.gain,l.values,l.purchases,0,EVO.per==='1d'?H.dates.length-1:s.last):{eur:null,pct:null},first=(d.transactions_list||[]).filter(t=>t.side==='buy'&&(p.listing_id?t.listing_id===p.listing_id:t.symbol===p.symbol)).sort((a,b)=>String(a.trade_at).localeCompare(String(b.trade_at)))[0];
      return `<tr data-position="${J.esc(p.key)}" data-key="${J.esc(key)}" tabindex="0" aria-selected="${ANALYSIS.focus===key}"><td><button type="button" class="position-open" data-select="${J.esc(key)}"><b>${J.esc(p.symbol)}</b> <span>${J.esc(p.name_catalogue||p.name||p.symbol)}</span></button><small>${first?J.date(first.trade_at):'Date indisponible'}</small></td><td data-label="Valeur · poids"><b>${J.eur(p.value)}</b><small>${J.pct(p.weight,1,false)}</small></td><td data-label="Sur la période" class="${J.cls(r?.eur)}"><b>${J.eur(r?.eur)}</b><small>${J.pct(r?.pct,1)}</small></td><td data-label="Depuis les achats" class="${J.cls(c.eur)}"><b>${J.eur(c.eur)}</b><small>${J.pct(c.pct,1)}</small></td><td data-label="Recul observé">${i.protection?.available?'−'+J.num(i.protection.drop_pct,1)+' %':'Indisponible'}</td><td data-label="Surveillance">${statusBadge(i)}</td></tr>`;
    }).join('')||'<tr><td colspan="6" class="empty">Aucune position détenue. Les gains des ventes restent dans le résumé et les contributions.</td></tr>'}</tbody></table>`;
  }
  function bindTable() {
    J.$$('#positions-table [data-key]').forEach(row=>{
      const open=()=>{focusAnalysis(row.dataset.key,true);J.$('#position-detail').scrollIntoView({block:'nearest',behavior:'smooth'})};
      row.onclick=open;row.onkeydown=e=>{if(e.target===row&&['Enter',' '].includes(e.key)){e.preventDefault();open()}};
    });
  }
  function renderContributions(s) {
    const rows=[...s.rows].sort((a,b)=>a.eur===null?1:b.eur===null?-1:a.eur<0&&b.eur<0?a.eur-b.eur:a.eur<0?-1:b.eur<0?1:b.eur-a.eur);
    const max=Math.max(1,...rows.map(r=>Math.abs(r.eur||0))),negative=rows.filter(r=>r.eur!==null&&r.eur<0),missing=rows.filter(r=>r.eur===null).length;
    J.$('#contributions').innerHTML=`<h3>Ce qui fait gagner ou perdre</h3><p class="small muted">${EVO.unit==='pct'?'Contribution au rendement global · points de pourcentage':'Contribution au résultat en euros'} · tri par impact réel</p>${missing?`<p class="small muted">${EVO.per==='1d'?'Certaines contributions 1 J sont indisponibles ; voir les raisons sous le graphique.':`Contributions partielles : ${missing} titre(s) non calculable(s).`}</p>`:''}<div class="contribution-list">${rows.map(r=>{
      const rank=negative.indexOf(r),label=r.eur===null?'Données insuffisantes':rank===0?'1re perte':rank===1?'2e perte':r.eur<0?'Perte':r.eur>0?'Gain':'Stable';
      return `<button class="cockpit-contribution ${ANALYSIS.focus===r.l.key?'selected':''}" data-contribution="${J.esc(r.l.key)}" data-eur="${r.eur??''}" aria-pressed="${ANALYSIS.focus===r.l.key}"><span><i style="background:${r.color}"></i><b>${J.esc(r.l.symbol)}</b><small>${label}</small></span><span class="contribution-track"><i class="${r.eur<0?'down':'up'}" style="${r.eur<0?'right':'left'}:50%;width:${50*Math.abs(r.eur||0)/max}%"></i></span><strong class="${J.cls(r.eur)}">${formatContribution(r)}</strong><small class="contribution-weight">Poids actuel ${J.pct(D.positions.find(p=>positionKey(p)===r.l.key)?.weight,1,false)}</small></button>`;
    }).join('')||'<p class="small muted">Aucune transaction.</p>'}</div><p class="small muted">Titres soldés inclus.</p>`;
    J.$$('#contributions [data-contribution]').forEach(b=>b.onclick=()=>focusAnalysis(b.dataset.contribution,true));
  }
  function renderSelection(s) {
    const r=s.rows.find(r=>r.l.key===ANALYSIS.focus),host=J.$('#selection-summary');
    if(!r){host.innerHTML='';return;}
    const p=D.positions.find(p=>positionKey(p)===r.l.key),c=perf(r.l.gain,r.l.values,r.l.purchases,0,EVO.per==='1d'?H.dates.length-1:s.last),loss=lossHistory(H.dates,r.l.gain),first=(H.trades||[]).find(t=>t.key===r.l.key&&t.side==='buy'&&!t.note);
    host.innerHTML=`<div class="selection-readout"><b>${J.esc(r.l.symbol)}</b><span>Résultat personnel (plage) <strong class="${J.cls(r.eur)}">${EVO.unit==='pct'?J.pct(r.pct,2):J.eur(r.eur)}</strong></span><span>Depuis les achats (fin de vue) <strong>${J.eur(c.eur)} · ${J.pct(c.pct,1)}</strong></span><span>Poids ${p?J.pct(p.weight,1,false):'0 % · soldée'}</span><span>Acheté depuis ${first?J.date(first.date):'date inconnue'}</span>${c.eur<0&&loss.current?`<span>Perte observée depuis ${J.date(loss.current)}</span>`:''}<button class="btn small" id="open-position">Détails et achats →</button></div>`;
    J.$('#open-position').onclick=()=>{ANALYSIS.detail=true;renderDetail(s);J.$('#position-detail').scrollIntoView({block:'nearest',behavior:'smooth'})};
  }
  function renderDetail(s) {
    const host=J.$('#position-detail'),key=ANALYSIS.focus,r=s.rows.find(r=>r.l.key===key);
    host.hidden=!ANALYSIS.detail||!r;if(host.hidden){host.innerHTML='';return;}
    const p=D.positions.find(p=>positionKey(p)===key),i=p?insight(p):null,c=perf(r.l.gain,r.l.values,r.l.purchases,0,EVO.per==='1d'?H.dates.length-1:s.last),loss=lossHistory(H.dates,r.l.gain),trades=(H.trades||[]).filter(t=>t.key===key&&t.side==='buy'&&!t.note);
    host.innerHTML=`<div class="pf-section-title"><h2>${J.esc(r.l.symbol)} · ${J.esc(r.l.name)}</h2><button class="btn small" id="close-position" aria-label="Fermer les détails">Fermer</button></div><p class="small">Mon investissement : <b class="${J.cls(c.eur)}">${J.eur(c.eur)} · ${J.pct(c.pct,1)}</b> depuis les achats, ventes comprises. Sur la période principale : <b>${J.eur(r.eur)} · ${J.pct(r.pct,1)}</b>.</p><p class="small muted">${loss.first?'Première perte observée : '+J.date(loss.first)+'. ':''}${loss.current?'Séquence de perte observée depuis le '+J.date(loss.current)+(loss.gap?' ; historique précédent incomplet.':'.'):''} Les dates décrivent les observations conservées, frais compris, sans inventer de franchissement entre deux cours.</p><details class="selected-purchases" open><summary>Mes achats · ${trades.length}</summary>${trades.map(t=>`<div><b>${t.first_buy?'Premier achat':'Achat complémentaire'} · ${J.date(t.date)}</b><span>${J.num(t.quantity,4)} titre(s) à ${tradePrice(t)} · Frais ${J.eur(t.fees_eur)} · change ${J.num(t.fx_to_eur,6)} €/unité</span></div>`).join('')}</details>${p?diagnosticDetails(p,i,D):`<p class="small muted">Position soldée : résultat réalisé conservé. Pas de diagnostic de position ouverte.</p>${Number(key)>0?`<a class="btn small" href="titre.html?id=${Number(key)}">Fiche complète ↗</a>`:''}`}${p?`<div class="row"><button class="btn small" data-detail-chart="${p.listing_id||''}" ${p.listing_id?'':'disabled'}>Cours historique · analyse approfondie</button><button class="btn small" data-detail-levels="${p.listing_id||''}" ${p.linked?'':'disabled'}>Filet et objectif</button><a class="btn small" href="titre.html?id=${p.listing_id}" ${p.listing_id?'':'hidden'}>Fiche complète ↗</a></div><p class="small muted">Le cours du titre décrit le marché ; le résultat personnel inclut transactions, frais et change. Recul de la position actuelle mesuré depuis le dernier achat encore ouvert.</p>`:''}`;
    J.$('#close-position').onclick=()=>{ANALYSIS.detail=false;host.hidden=true};
    J.$('[data-detail-chart]')?.addEventListener('click',()=>chartDialog(D,p));
    J.$('[data-detail-levels]')?.addEventListener('click',()=>levelsDialog(p));
    J.$$('#position-detail [data-lot]').forEach(b=>b.onclick=()=>lotDialog(D,D.lots.find(l=>l.tx_id==b.dataset.lot)));
  }
  function updateSummary(s) {
    const label=EVO.per==='all'?'Depuis le début':PERIODS.find(p=>p[0]===EVO.per)?.[1];
    J.$('#summary-period-label').textContent='Sur la période · '+label;
    const total=J.$('#period-g');total.className=J.cls(s.total.eur);total.textContent=(EVO.per==='1d'?'Indicatif · ':'')+J.eur(s.total.eur)+' · '+J.pct(s.total.pct,1);
    const dates=EVO.per==='1d'&&H.session?.dates.length?J.dateTime(H.session.dates[0])+' → '+J.dateTime(H.session.dates.at(-1)):H.dates.length?J.date(H.dates[s.start])+' → '+J.date(H.dates[s.last]):'aucune transaction';
    J.$('#period-reference').textContent='Couverture personnelle : '+dates+(s.start===0&&EVO.per!=='1d'?' · historique couvert depuis la première transaction.':'')+'.';
    const alerts=D.positions.filter(p=>['watch','act'].includes(insight(p).status));
    J.$('#surveillance-summary').innerHTML=alerts.length?`<span>Surveillance :</span> ${alerts.map(p=>`<button class="btn small" data-watch="${J.esc(positionKey(p))}">${J.esc(p.symbol)} · ${J.esc(insight(p).label)}</button>`).join('')}`:'<span class="small muted">Aucun signal de surveillance notable parmi les indicateurs disponibles.</span>';
    J.$$('[data-watch]').forEach(b=>b.onclick=()=>focusAnalysis(b.dataset.watch,true));
  }
  const VIEW_DEFAULT={summary:true,portfolio:true,titles:true,contributions:true,positions:true,surveillance:true};
  const DASH=Object.assign({},VIEW_DEFAULT,store('dashboard_v1')||{});
  const CHART={view:null,selected:new Set(),hidden:new Set(store('series_hidden_v1')||[]),measure:store('chart_measure')||'personal'};
  function formatContribution(r){return EVO.unit==='pct'?r.contribution_pct===null?'Indisponible':J.num(r.contribution_pct,2)+' pts':J.eur(r.eur)}
  function applyDashboard(){
    J.$('.cockpit-summary').hidden=!DASH.summary;J.$('.cockpit-positions').hidden=!DASH.positions;
    J.$('#surveillance-summary').hidden=!DASH.surveillance;J.$('#contributions').hidden=!DASH.contributions;
    J.$('#chart-pane').hidden=!DASH.portfolio&&!DASH.titles;J.$('.cockpit-analysis').hidden=!DASH.portfolio&&!DASH.titles&&!DASH.contributions;
    J.$('.cockpit-chart-grid').classList.toggle('without-contributions',!DASH.contributions);J.$('.cockpit-chart-grid').classList.toggle('without-chart',!DASH.portfolio&&!DASH.titles);
  }
  function graphTimes(){
    if(EVO.per==='1d')return (CHART.measure==='market'?H.market?.intraday?.dates:H.session?.dates)||[];
    const dates=CHART.measure==='market'?(H.market?.dates||[]):H.dates;const end=H.dates.at(-1)||dates.at(-1),reference=dates.length&&dates.at(-1)<end?[...dates,end]:dates;const i=periodStart({dates:reference});return dates.slice(i);
  }
  function renderSeries(){
    const rows=H.lines.filter(l=>D.positions.some(p=>positionKey(p)===l.key)||CHART.selected.has(l.key));
    J.$('#series-list').innerHTML=[{key:'portfolio',symbol:'Portefeuille global'},...rows].map(l=>`<span class="series-control"><label><input type="checkbox" data-series="${J.esc(l.key)}" ${l.key==='portfolio'?DASH.portfolio?'checked':'':DASH.titles&&!CHART.hidden.has(l.key)?'checked':''} ${CHART.measure==='market'&&l.key==='portfolio'?'disabled':''}>${J.esc(l.symbol)}</label>${l.key!=='portfolio'?`<button class="series-focus" data-highlight="${J.esc(l.key)}" aria-label="Mettre en évidence ${J.esc(l.symbol)}" aria-pressed="${CHART.selected.has(l.key)}">★</button>`:''}</span>`).join('');
    J.$$('[data-series]').forEach(c=>c.onchange=()=>{if(c.dataset.series==='portfolio'){DASH.portfolio=c.checked;store('dashboard_v1',DASH);J.$('[data-section="portfolio"]').checked=c.checked}else{DASH.titles=true;J.$('[data-section="titles"]').checked=true;c.checked?CHART.hidden.delete(c.dataset.series):CHART.hidden.add(c.dataset.series);store('series_hidden_v1',[...CHART.hidden]);store('dashboard_v1',DASH)}drawEvo()});
    J.$$('[data-highlight]').forEach(b=>b.onclick=()=>{const key=b.dataset.highlight;CHART.selected.has(key)?CHART.selected.delete(key):CHART.selected.add(key);ANALYSIS.focus=CHART.selected.has(key)?key:[...CHART.selected].at(-1)||null;ANALYSIS.auto=false;CHART.hidden.delete(key);drawEvo()});
  }
  function drawInteractive(keepRange=false){
    if(!H)return;const times=graphTimes(),reference=CHART.view||(times.length?{from:J.financialTime(times[0]),to:J.financialTime(times.at(-1))}:null),s=snapshot(reference),host=J.$('#evo-chart'),pct=EVO.unit==='pct',measure=CHART.measure;
    const losses=s.rows.filter(r=>r.eur!==null&&r.eur<0).sort((a,b)=>a.eur-b.eur);if(losses[0])losses[0].color='#dc2626';if(losses[1])losses[1].color='#c2410c';
    const color=key=>s.rows.find(r=>r.l.key===key)?.color||'#6366f1';
    const visible=D.positions.map(positionKey).filter(k=>!CHART.hidden.has(k));for(const k of CHART.selected)if(!visible.includes(k)&&!CHART.hidden.has(k))visible.push(k);
    const fmt=pct?v=>J.pct(v,2):v=>J.eur(v),series=[];const mapDate=(date,dates)=>dates.indexOf(date);
    const baseAt=i=>{if(i<0)return null;const start=s.start;if(start>0&&H.value[start]===null)return null;return (start?H.value[start]:0)+H.purchases[i]-(start?H.purchases[start]:0)};
    if(measure==='market'){
      const m=EVO.per==='1d'?H.market?.intraday:H.market;
      const i0=CHART.view?(m?.dates||[]).findLastIndex(t=>J.financialTime(t)<=CHART.view.from):times.length?(m?.dates||[]).indexOf(times[0]):0;
      for(const l of m?.lines||[]){if(!DASH.titles||!visible.includes(l.key))continue;const base=l.prices[i0],bad=(l.break_dates||[]).some(d=>d>times[0]&&d<=times.at(-1));
        series.push({id:l.key,label:l.symbol,color:color(l.key),values:times.map(t=>{const i=mapDate(t,m.dates);return i<0?null:pct?base>0&&!bad&&l.prices[i]!==null?100*(l.prices[i]/base-1):null:l.prices_eur?.[i]??null})});}
    }else if(EVO.per==='1d'){
      const session=H.session||{dates:[],lines:[]};
      const index=times.map(t=>session.dates.indexOf(t)),a=s.start;
      if(DASH.portfolio)series.push({id:'portfolio',label:'Portefeuille global · indicatif',color:'#0f172a',width:3,values:index.map(i=>{const g=i<0||session.gain[i]===null||session.gain[a]===null?null:session.gain[i]-session.gain[a];return g===null?null:pct?s.base>0?100*g/s.base:null:g})});
      for(const l of session.lines){if(!DASH.titles||!visible.includes(l.key))continue;const base=measure==='contribution'?s.base:l.values[a];series.push({id:l.key,label:l.symbol,color:color(l.key),values:index.map(i=>{const g=i<0||l.gain[i]===null||l.gain[a]===null?null:l.gain[i]-l.gain[a];return g===null?null:pct?base>0?100*g/base:null:g})});}
    }else{
      const indices=times.map(t=>H.dates.indexOf(t));
      if(DASH.portfolio)series.push({id:'portfolio',label:'Portefeuille global',color:'#0f172a',width:3,values:indices.map(i=>i<s.start?null:perf(H.gain,H.value,H.purchases,s.start,i)[EVO.unit])});
      for(const l of H.lines){if(!DASH.titles||!visible.includes(l.key))continue;series.push({id:l.key,label:l.symbol,color:color(l.key),values:indices.map(i=>{if(i<s.start)return null;if(measure==='contribution'&&pct){const gain=heldPerformance(l,s.start,i,'eur'),base=baseAt(i);return gain!==null&&base>0?100*gain/base:null}return heldPerformance(l,s.start,i,EVO.unit)})});}
    }
    for(const item of series){item.width=CHART.selected.has(item.id)?4:item.width||2;if(CHART.selected.size&&!CHART.selected.has(item.id))item.color=item.color.startsWith('#')?'rgba('+[1,3,5].map(i=>parseInt(item.color.slice(i,i+2),16)).join(',')+',0.65)':item.color;}
    renderContributions(s);renderSelection(s);
    const covered=times.length?J.date(times[0].slice(0,10))+' → '+J.date(times.at(-1).slice(0,10)):'aucune observation';
    J.$('#chart-window').textContent=(CHART.view?'Vue agrandie · ':'Plage graphique · ')+(CHART.view?J.date(new Date(CHART.view.from*1000).toISOString().slice(0,10))+' → '+J.date(new Date(CHART.view.to*1000).toISOString().slice(0,10)):covered)+' · classement sur cette même plage. Le résumé et le tableau gardent la période principale.';
    J.$('#chart-meaning').textContent=measure==='market'?(pct?'Cours normalisés à une date commune · 0 % = base 100, hors change':'Cours historiques convertis en euros au change daté · pas un résultat personnel'):measure==='contribution'?(pct?'Contribution au rendement global, en points · dénominateur commun au portefeuille':'Contribution en euros au résultat du portefeuille'):'Performance personnelle · frais et change inclus · en % : rendement propre de chaque série';
    const reasons=EVO.per==='1d'?(H.session?.notes||[]):H.notes||[];
    const unavailable=series.filter(x=>!x.values.some(Number.isFinite)).map(x=>x.label);
    J.$('#evo-note').textContent=[...reasons,unavailable.length?'Séries non calculables : '+unavailable.join(', ')+'.':'',measure==='market'?'Historique boursier disponible avant les achats ; les performances personnelles commencent à l’acquisition. Le portefeuille global n’a pas de cours de marché unique.':'',measure==='market'&&pct?'Une base initiale absente ou une rupture non résolue rend la comparaison indisponible.':'',pct&&!(s.base>0)?'Contribution en % non définie : capital engagé nul ou non valorisable sur cette plage.':'',measure==='market'&&!pct?'Une conversion en euros nécessite un taux historique connu à la date observée, âgé de sept jours au plus ; les valeurs sans ce taux restent indisponibles.':''].filter(Boolean).join(' ');
    const highlight=CHART.selected;
    J.financialChart(host,{times,series},{height:innerWidth<700?300:340,time:EVO.per==='1d',format:fmt,markers:purchaseMarkers(times,EVO.per==='1d',null).filter(m=>series.some(s=>s.id==='portfolio'||s.id===m.key)),selected:highlight,view:CHART.view,keepRange,onReset:()=>{CHART.view=null;drawInteractive(false)},onRange:range=>{
      const a=J.financialTime(times[0]),b=J.financialTime(times.at(-1));const view=range.from<=a&&range.to>=b?null:range;
      if(JSON.stringify(view)!==JSON.stringify(CHART.view)){CHART.view=view;drawInteractive(true)}
    }});
    renderSeries();applyDashboard();
  }
  function drawEvo(){
    if(!H||!D||!J.$('#evo-chart'))return;
    const s=snapshot();
    if(ANALYSIS.auto){const worst=s.rows.filter(r=>r.eur!==null&&r.eur<0).sort((a,b)=>a.eur-b.eur)[0];ANALYSIS.focus=worst?.l.key||null;CHART.selected=ANALYSIS.focus?new Set([ANALYSIS.focus]):new Set()}
    updateSummary(s);J.$('#positions-table').innerHTML=positionTable(D,s);bindTable();renderDetail(s);
    J.$('#clear-focus').hidden=!CHART.selected.size;J.$('#isolate-series').disabled=!CHART.selected.size;
    J.$$('#global-per button').forEach(b=>{b.classList.toggle('on',b.dataset.v===EVO.per);b.setAttribute('aria-pressed',String(b.dataset.v===EVO.per))});
    J.$$('#evo-unit button').forEach(b=>b.classList.toggle('on',b.dataset.v===EVO.unit));
    J.$('#chart-measure').value=CHART.measure;drawInteractive(true);
    const vh=J.$('#value-history');if(VIEW==='manage'&&vh){if(EVO.per==='1d'){const it=H.session||{dates:[],value:[]};J.lineChart(vh,it.dates,[{id:'value',label:'Valeur observée',values:it.value,color:'#6366f1'}],{height:220,time:true,format:J.eur})}else J.lineChart(vh,H.dates.slice(s.start),[{id:'value',label:'Valeur des titres',values:H.value.slice(s.start),color:'#6366f1'},{id:'net',label:'Achats − ventes nets de frais',values:H.net_in.slice(s.start),color:'#94a3b8'}],{height:220,format:J.eur})}
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
    list=(await J.api('portfolios')).portfolios;
    if(!list.length){page.innerHTML='<h1>Portefeuilles</h1><div class="card empty"><p>Aucun portefeuille.</p><button class="btn primary" id="first">Créer mon premier portefeuille</button></div>';J.$('#first').onclick=createPf;return;}
    if(!list.some(p=>p.id===current))current=list[0].id;
    J.$('#evo-chart')?._financial?.destroy();
    const d=D=await J.api('portfolio',{params:{id:current}});H=null;CHART.view=null;CHART.selected.clear();ANALYSIS.focus=null;ANALYSIS.auto=true;ANALYSIS.detail=false;
    history.replaceState(null,'','?id='+current);
    const etfHtml=JEtf.portfolio(d.etf_analysis);
    page.innerHTML=`${d.integrity&&!d.integrity.ok?`<div class="notice err">${d.integrity.issues.map(i=>J.esc(i.message)).join('<br>')}</div>`:''}<header class="pf-toolbar"><div><h1>Mes portefeuilles</h1><label class="sr-only" for="pf-select">Portefeuille affiché</label><select id="pf-select">${list.map(p=>`<option value="${p.id}" ${p.id===current?'selected':''}>${J.esc(p.name)}${p.is_default?' ★':''}</option>`).join('')}</select><button class="btn small" id="new-pf" aria-label="Créer un portefeuille">＋</button></div><button class="btn primary" id="add-tx">＋ Transaction</button></header><details class="dashboard-options"><summary>Personnaliser le tableau de bord</summary>${Object.entries({summary:'Résumé financier',portfolio:'Graphique global du portefeuille',titles:'Courbes des actions et ETF',contributions:'Contributions aux gains et pertes',positions:'Tableau des positions',surveillance:'Alertes et surveillance'}).map(([k,label])=>`<label><input type="checkbox" data-section="${k}" ${DASH[k]?'checked':''}>${label}</label>`).join('')}</details><div class="global-period"><span>Période principale</span>${pills('global-per',[['1d','1 jour'],['1w','1 semaine'],['1m','1 mois'],['3m','3 mois'],['6m','6 mois'],['1y','1 an'],['all','Depuis le début']],EVO.per)}</div><p id="period-reference" class="small muted"></p>
      ${d.totals.unpriced?'<div class="notice warn">Valorisation et gain total indisponibles : cours ou change manquant. Aucun prix d’achat n’est utilisé comme cours actuel.</div>':''}
      <nav class="pf-nav" id="pf-nav" role="tablist" aria-label="Espaces du portefeuille">${[['home','Mon portefeuille'],['manage','Historique et gestion']].map(([k,l])=>`<button type="button" role="tab" data-view="${k}" id="tab-${k}" aria-controls="panel-${k}">${l}</button>`).join('')}</nav>
      <section class="pf-panel" id="panel-home" data-panel="home" role="tabpanel" aria-labelledby="tab-home">${hero(d)}${analysis()}<section class="card cockpit-positions"><div class="pf-section-title"><h2>Toutes mes positions <span class="cnt">${d.positions.length}</span></h2><label>Trier <select id="position-sort">${[['loss','Plus grosses pertes'],['gain','Plus gros gains'],['impact','Impact en euros'],['pct','Performance en %'],['weight','Poids'],['drop','Recul depuis le sommet'],['attention','Surveillance']].map(([k,l])=>`<option value="${k}" ${SORT===k?'selected':''}>${l}</option>`).join('')}</select></label></div><div id="surveillance-summary" class="surveillance-summary"></div><div id="positions-table"><span class="spinner"></span></div><details class="pf-explain"><summary>Lire les colonnes</summary><p>La période commune pilote les performances. Depuis les achats : résultat cumulé, ventes comprises. Recul : position actuelle depuis le dernier achat encore ouvert. Les contributions en euros s’additionnent, les pourcentages propres aux titres ne s’additionnent pas.</p></details></section><section id="position-detail" class="card cockpit-detail" hidden></section></section>
      <section class="pf-panel" id="panel-manage" data-panel="manage" role="tabpanel" aria-labelledby="tab-manage">${section('tx','Transactions','',txBody(d))}${d.sales.length?section('sales','Ventes réalisées','',salesBody(d)):''}${d.lots.length?section('lots','Lots et réglages des alertes','',lotsBody(d)):''}${section('valuation','Valeur et mouvements d’argent','',`<p class="small muted">La valeur varie aussi avec les achats et ventes. Ces montants ne sont pas un rendement. Période commune sélectionnée en haut.</p><div id="value-history"></div>`)}${d.allocation?.rows?section('alloc','Répartition par zone','',allocBody(d.allocation)):''}${d.positions.some(p=>p.kind==='etf')&&etfHtml?section('etf','Secteurs de vos ETF','',etfHtml.replace(/^<div class="card">\s*<h2>[^<]*<\/h2>/,'<div>')):''}${splitNotice(d.positions)}${section('settings','Réglages du portefeuille','',`<div class="row"><button class="btn small" id="rename">Renommer</button>${d.portfolio.is_default?'':'<button class="btn small" id="mk-default">Définir par défaut</button>'}<button class="btn small danger" id="del-pf">Supprimer</button></div><p class="small muted">Stratégie : ${J.esc(d.portfolio.strategy?(NAMES[d.portfolio.strategy.name]||'Personnalisée'):'Croissance régulière par défaut')}. Réglage depuis l’Explorer.</p>`)}</section>`;
    folds();
    J.$('#pf-select').onchange=e=>{current=+e.target.value;render()};
    J.$$('#pf-nav [data-view]').forEach((b,index,buttons)=>{b.onclick=()=>switchView(b.dataset.view);b.onkeydown=e=>{const delta={ArrowRight:1,ArrowLeft:-1}[e.key];if(delta){e.preventDefault();const next=buttons[(index+delta+buttons.length)%buttons.length];switchView(next.dataset.view);next.focus()}}});
    J.$('#position-sort').onchange=e=>{SORT=e.target.value;store('cockpit_sort',SORT);if(H)drawEvo()};
    J.$$('#global-per button').forEach(b=>b.onclick=()=>{EVO.per=b.dataset.v;CHART.view=null;J.$('#evo-chart')._financial?.destroy();drawEvo()});
    J.$('#chart-measure').onchange=e=>{CHART.measure=e.target.value;store('chart_measure',CHART.measure);CHART.view=null;J.$('#evo-chart')._financial?.destroy();drawEvo()};
    J.$$('#evo-unit button').forEach(b=>b.onclick=()=>{EVO.unit=b.dataset.v;store('evo_unit',EVO.unit);drawEvo()});
    J.$('#purchase-markers').onchange=e=>{ANALYSIS.markers=e.target.checked;drawEvo()};
    J.$('#isolate-series').onclick=()=>{if(!CHART.selected.size)return;DASH.portfolio=false;DASH.titles=true;CHART.hidden=new Set(H.lines.filter(l=>!CHART.selected.has(l.key)).map(l=>l.key));J.$('[data-section="portfolio"]').checked=false;J.$('[data-section="titles"]').checked=true;store('dashboard_v1',DASH);store('series_hidden_v1',[...CHART.hidden]);drawEvo()};
    J.$('#show-all-series').onclick=()=>{DASH.portfolio=true;DASH.titles=true;CHART.hidden.clear();J.$('[data-section="portfolio"]').checked=true;J.$('[data-section="titles"]').checked=true;store('dashboard_v1',DASH);store('series_hidden_v1',[]);drawEvo()};
    J.$('#clear-focus').onclick=()=>{CHART.selected.clear();ANALYSIS.focus=null;ANALYSIS.auto=false;ANALYSIS.detail=false;drawEvo()};
    J.$('#refresh-history').onclick=async()=>{const id=Number(ANALYSIS.focus);if(!id){J.toast('Sélectionnez un titre lié au catalogue.');return;}const button=J.$('#refresh-history'),pid=current;button.disabled=true;try{const result=await J.post('portfolio/history-refresh',{id:pid,listing_id:id});J.toast(result.message||'Collecte ciblée terminée.');const fresh=await J.api('portfolio/history',{params:{id:pid}});if(pid!==current)return;H=fresh;CHART.view=null;J.$('#evo-chart')._financial?.destroy();drawEvo()}catch(e){J.toast(e.message)}finally{button.disabled=false}};
    J.$$('[data-section]').forEach(c=>c.onchange=()=>{DASH[c.dataset.section]=c.checked;if(!DASH.portfolio&&!DASH.titles){CHART.view=null;J.$('#evo-chart')._financial?.destroy()}store('dashboard_v1',DASH);drawEvo()});
    switchView(VIEW);
    const pid=current;
    J.api('portfolio/history',{params:{id:pid}}).then(h=>{if(pid!==current)return;H=h;drawEvo()}).catch(e=>{J.$('#evo-chart').innerHTML=`<p class="notice err">${J.esc(e.message)}</p>`;J.$('#period-g').textContent='Indisponible';J.$('#positions-table').innerHTML='<p class="notice warn">Historique indisponible : rechargez pour calculer les performances.</p>'});
    J.$('#new-pf').onclick=createPf;
    J.$('#add-tx').onclick=()=>J.txDialog({portfolios:list,portfolioId:current,onDone:render});
    J.$$('[data-lot]').forEach(b=>b.onclick=()=>lotDialog(d,d.lots.find(l=>l.tx_id==b.dataset.lot)));
    J.$$('[data-edit]').forEach(b=>b.onclick=()=>J.txDialog({portfolios:list,portfolioId:current,tx:d.transactions_list.find(t=>t.id==b.dataset.edit),onDone:render}));
    J.$$('[data-del]').forEach(b=>b.onclick=async()=>{if(await J.confirm('Supprimer la transaction','Cette transaction sera supprimée définitivement.','Supprimer')){await J.post('tx/delete',{id:+b.dataset.del});render()}});
    J.$('#alloc-prudent')?.addEventListener('click',async()=>{await J.post('portfolio/target',{id:current,target:{us:50,eu:25,emerging:25}});render()});
    J.$('#alloc-edit')?.addEventListener('click',()=>allocationDialog(d.allocation));
    J.$('#alloc-off')?.addEventListener('click',async()=>{await J.post('portfolio/target',{id:current,target:null});render()});
    J.$('#rename').onclick=()=>J.dialog({title:'Renommer',body:J.field('Nom',`<input id="nm" value="${J.esc(d.portfolio.name)}">`),actions:[{label:'Annuler',run:()=>{}},{label:'Enregistrer',cls:'primary',run:async dlg=>{await J.post('portfolio/rename',{id:current,name:J.$('#nm',dlg).value});render()}}]});
    J.$('#mk-default')?.addEventListener('click',async()=>{await J.post('portfolio/default',{id:current});render()});
    J.$('#del-pf').onclick=()=>J.dialog({title:'Supprimer le portefeuille',body:`<p>Supprimer « ${J.esc(d.portfolio.name)} » et ses ${d.transactions_list.length} transactions ? Cette action est définitive.</p>${d.transactions_list.length?J.field('Pour confirmer, tapez le nom du portefeuille','<input id="cf">'):''}`,actions:[{label:'Annuler',run:()=>{}},{label:'Supprimer',cls:'danger',run:async dlg=>{await J.post('portfolio/delete',{id:current,confirm:J.$('#cf',dlg)?.value||''});render()}}]});
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
