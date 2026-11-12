/* Page Portefeuilles — l'essentiel d'abord : valeur et gain, courbe compacte, ce qui fait bouger, positions ; le reste replié. */
(async () => {
  const user = await J.init('portefeuilles'); if (!user) return;
  const page = J.$('#page');
  let list = (await J.api('portfolios')).portfolios;
  let current = +new URLSearchParams(location.search).get('id') || (list.find(p => p.is_default) || list[0] || {}).id;
  const NAMES = { regular: 'Croissance régulière', fast: 'Croissance rapide', recovery: 'Rebond', low_volatility: 'Hausse calme', momentum: 'Momentum 6 mois (essai)', momentum12: 'Momentum 12 mois (essai)', momentum_risk: 'Momentum ajusté du risque (essai)' };
  const PAL = ['#6366f1', '#14b8a6', '#f59e0b', '#ec4899', '#3b82f6', '#84cc16', '#a855f7', '#ef4444', '#06b6d4', '#eab308', '#64748b', '#22c55e'];
  const store = J.store.fn('jigo_pf_');
  const EVO = { mode: ['portfolio','positions'].includes(store('cockpit_mode')) ? store('cockpit_mode') : 'positions', per: 'all', unit: 'pct', hidden: new Set(store('evo_hidden') || []) };
  const PERIODS = [['1d', '1 J', 0], ['1w', '1 S', 8], ['1m', '1 M', 31], ['3m', '3 M', 92], ['6m', '6 M', 183], ['1y', '1 A', 366], ['all', 'Tout', 0]];
  const px = (v, c) => v === null || v === undefined ? '–' : J.money(v, c || 'EUR');
  const eur0 = v => J.eur(v, 0), sgn = v => v === null || v === undefined ? '–' : (v > 0 ? '+' : v < 0 ? '−' : '') + J.eur(Math.abs(v), 2);
  const pills = (id, items, cur) => `<div class="seg" id="${id}">${items.map(([k, l]) => `<button type="button" data-v="${k}" class="${k === cur ? 'on' : ''}">${l}</button>`).join('')}</div>`;
  const splitNotice = positions => positions.filter(p => p.splits_applied && p.splits_applied.length).map(p => `<div class="notice mt-3"><b>${J.esc(p.name_catalogue || p.name || p.symbol)}</b> : ${p.splits_applied.map(a => a.ratio >= 1 ? `split ${J.num(a.ratio, 2)} pour 1` : `regroupement ${J.num(1 / a.ratio, 2)} pour 1`).join(', ')} pris en compte automatiquement : la quantité affichée est celle d’aujourd’hui, le prix de revient total est inchangé.</div>`).join('');
  const ANALYSIS = { markers: true, focus: null, auto: false, separate: false, detail: false };
  let VIEW = 'home';
  let POSITION_SCOPE='open', TX_FILTER={key:'',side:'',from:'',to:''};
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
      h.addEventListener('click', e => { if (e.target.closest('button, a, input, select, .seg')) return; c.classList.toggle('folded'); h.setAttribute('aria-expanded',String(!c.classList.contains('folded'))); const f = Object.assign({}, FOLD_DEFAULT, store('folds2') || {}); f[c.dataset.fold] = c.classList.contains('folded'); store('folds2', f); if (c.dataset.fold === 'valuation' && !c.classList.contains('folded')) drawEvo(); });
    });
  }

  const positionKey=p=>p.listing_id?String(p.listing_id):'S'+p.symbol.toUpperCase();
  function switchView(view) {
    VIEW=view;
    J.$$('#pf-nav [data-view]').forEach(b=>{const active=b.dataset.view===view;b.classList.toggle('on',active);b.setAttribute('aria-selected',String(active));b.tabIndex=active?0:-1});
    J.$$('.pf-panel').forEach(e=>e.hidden=e.dataset.panel!==view);
    if(H)drawEvo();
  }
  function tradePosition(key,side){const p=[...D.positions,...D.closed].find(p=>positionKey(p)===key);if(!p)return;J.txDialog({portfolios:list,portfolioId:current,listing:{id:p.listing_id,symbol:p.symbol,name:p.name_catalogue||p.name||p.symbol,currency:p.price_currency||p.currency,price:p.price},side,quantity:side==='sell'?p.qty:'',onDone:render})}
  function openHistory(id=null,key=null){const tx0=D.transactions_list.find(t=>t.id===id);TX_FILTER.key=key||(tx0?positionKey(tx0):'');TX_FILTER.side='';TX_FILTER.from='';TX_FILTER.to='';renderTransactions();switchView('manage');const fold=J.$('[data-fold="tx"]');fold.classList.remove('folded');fold.querySelector('.fold-h').setAttribute('aria-expanded','true');const row=id?J.$(`[data-tx-row="${id}"]`):null;row?.classList.add('tx-target');(row||fold).scrollIntoView({block:'center',behavior:'smooth'});row?.focus()}
  function drawEvo(){
    if(!H||!D)return;
    const vh=J.$('#value-history');if(VIEW==='manage'&&vh){J.lineChart(vh,H.dates,[{id:'value',label:'Valeur des titres',values:H.value,color:'#6366f1'},{id:'net',label:'Achats − ventes nets de frais',values:H.net_in,color:'#94a3b8'}],{height:220,format:J.eur})}
    if(J.$('#pf-home')&&VIEW==='home')PFHome.mount(J.$('#pf-home'),{D,H,current,name:(list.find(x=>x.id===current)||{}).name,keep:true,helpers:{trade:tradePosition,lot:l=>lotDialog(D,l),add:()=>J.txDialog({portfolios:list,portfolioId:current,onDone:render}),history:(id,key)=>openHistory(id||null,key||null)}});
  }
  /* ── Alertes, ventes, répartition, transactions : repliés par défaut ── */
  function lotsBody(d) {
    const groups = new Map();
    d.lots.forEach(l => { const label=l.alert?(l.alert.own_strategy?l.alert.strategy_label:'Non renseignée (règles par défaut : '+l.alert.strategy_label+')'):'Non renseignée', rule=l.alert?.rules||{}, key=label+JSON.stringify([rule.days,rule.drop,rule.off,rule.exit]); if(!groups.has(key))groups.set(key,{label,rule,lots:[]});groups.get(key).lots.push(l); });
    return `<p class="small muted">Les règles communes sont regroupées par stratégie et réglages effectifs. Les réglages individuels restent accessibles à la demande. Aucune vente n’est automatique.</p>${[...groups.values()].map(({label,rule,lots})=>`<details><summary>${J.esc(label)} · ${lots.length} achat(s)</summary><p class="small muted">${rule.off?'Alertes désactivées':`Rappel : ${rule.days || 'aucun'} jours · recul : ${rule.drop ? J.num(rule.drop,1)+' %' : 'sans seuil'}${rule.exit==='momentum_negative'?' · momentum 6 mois négatif':rule.exit==='below_ma50'?' · sous la moyenne 50 j':''}`}</p>${lots.map(l=>`<div class="lot-detail"><b>${J.esc(l.name||l.symbol)}</b> · ${J.date(l.trade_at)} · ${J.num(l.remaining,4)} titre(s) ${l.alert?.rules?.personal?'<span class="badge accent">personnalisé</span>':''}${J.riskBar(l.alert?.risk, { compact: true })}<button class="btn sm" data-lot="${l.tx_id}">Régler cet achat</button></div>`).join('')}</details>`).join('')}`;
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
      <div class="row mt-2">${a.target ? '<button class="btn sm" id="alloc-edit">Modifier la cible</button><button class="btn sm" id="alloc-off">Retirer la cible</button>' : '<button class="btn sm primary" id="alloc-prudent">Utiliser 50 / 25 / 25</button><button class="btn sm" id="alloc-edit">Autre répartition…</button>'}
        ${['us', 'eu', 'emerging'].map(z => `<a class="btn sm" href="index.html?kind=large_etf&geo_region=${z}&max_fee=0.3" target="_blank" rel="noopener">Gros ETF ${z === 'us' ? 'US' : z === 'eu' ? 'Europe' : 'émergents'}</a>`).join('')}</div>`;
  }
  function txBody(d){return `<div class="tx-filters"><label>Titre <select id="tx-filter-key"><option value="">Tous</option>${[...d.positions,...d.closed].map(p=>`<option value="${J.esc(positionKey(p))}">${J.esc(p.symbol)}${p.qty===0?' · clôturée':''}</option>`).join('')}</select></label><label>Opération <select id="tx-filter-side"><option value="">Achats et ventes</option><option value="buy">Achats</option><option value="sell">Ventes</option></select></label><label>Du <input type="date" id="tx-filter-from"></label><label>Au <input type="date" id="tx-filter-to"></label><a class="btn sm" href="api.php?r=export&id=${current}">Exporter en CSV</a></div><div id="tx-totals" class="small"></div><div class="table-wrap"><table><thead><tr><th>Date</th><th>Titre</th><th>Quantité</th><th>Prix · devise</th><th>Frais € · change</th><th>Réalisé · PMP</th><th></th></tr></thead><tbody id="tx-rows"></tbody></table></div>`}
  function renderTransactions(){
    if(!D||!J.$('#tx-rows'))return;
    for(const k of ['key','side','from','to']){const el=J.$('#tx-filter-'+k);el.value=TX_FILTER[k];el.onchange=()=>{TX_FILTER[k]=el.value;renderTransactions()}}
    const rows=D.transactions_list.filter(t=>(!TX_FILTER.key||positionKey(t)===TX_FILTER.key)&&(!TX_FILTER.side||t.side===TX_FILTER.side)&&(!TX_FILTER.from||t.trade_at.slice(0,10)>=TX_FILTER.from)&&(!TX_FILTER.to||t.trade_at.slice(0,10)<=TX_FILTER.to));
    const sales=D.sales.filter(x=>rows.some(t=>t.id===x.tx_id)),gains=sales.reduce((n,x)=>n+Math.max(0,x.gain),0),losses=sales.reduce((n,x)=>n+Math.min(0,x.gain),0);
    J.$('#tx-totals').textContent='Sur les opérations filtrées : gains réalisés '+J.eur(gains)+' · pertes réalisées '+J.eur(losses)+' · net '+J.eur(gains+losses)+' · frais '+J.eur(rows.reduce((n,x)=>n+Number(x.fees||0),0));
    J.$('#tx-rows').innerHTML=rows.map(t=>{const sale=D.sales.find(x=>x.tx_id===t.id),closed=D.closed.some(p=>positionKey(p)===positionKey(t));return `<tr data-tx-row="${t.id}" tabindex="-1"><td>${J.date(t.trade_at)}</td><td><span class="badge ${t.side==='buy'?'ok':'wait'}">${t.side==='buy'?'Achat':'Vente'}</span> <b>${J.esc(t.symbol)}</b>${closed?' · clôturée':''}<small>${J.esc(t.name||'')}</small></td><td>${J.num(+t.quantity,4)}</td><td>${J.money(+t.unit_price,t.currency)}</td><td>${J.eur(+t.fees)}<small>${J.num(+t.fx_to_eur,6)} €/unité</small></td><td>${sale?J.eur(sale.gain)+' · '+J.pct(sale.gain_pct,1)+'<small>Net '+J.eur(sale.proceeds)+' · Coût '+J.eur(sale.cost)+'</small>':t.side==='sell'?'Indisponible':'—'}</td><td><button class="btn sm" data-graph="${J.esc(positionKey(t))}">Graphique</button> <button class="btn sm" data-edit="${t.id}">Modifier</button> <button class="btn sm danger" data-del="${t.id}" aria-label="Supprimer">✕</button></td></tr>`}).join('')||'<tr><td colspan="7">Aucune transaction pour ces filtres.</td></tr>';
    J.$$('#tx-rows [data-graph]').forEach(b=>b.onclick=()=>{PFHome.state.sel=b.dataset.graph;PFHome.state.dmetric='market';switchView('home')});
    J.$$('#tx-rows [data-edit]').forEach(b=>b.onclick=()=>J.txDialog({portfolios:list,portfolioId:current,tx:D.transactions_list.find(t=>t.id==b.dataset.edit),onDone:render}));
    J.$$('#tx-rows [data-del]').forEach(b=>b.onclick=async()=>{if(await J.confirm('Supprimer la transaction','Cette transaction sera supprimée définitivement.','Supprimer')){await J.post('tx/delete',{id:+b.dataset.del});render()}});
  }

  async function render() {
    list=(await J.api('portfolios')).portfolios;
    if(!list.length){page.innerHTML='<h1>Portefeuilles</h1><div class="card empty"><p>Aucun portefeuille.</p><button class="btn primary" id="first">Créer mon premier portefeuille</button></div>';J.$('#first').onclick=createPf;return;}
    if(!list.some(p=>p.id===current))current=list[0].id;
    const d=D=await J.api('portfolio',{params:{id:current}});H=null;PFHome.state.sel=null;PFHome.state.zoom=null;
    history.replaceState(null,'','?id='+current);
    const etfHtml=JEtf.portfolio(d.etf_analysis);
    page.innerHTML=`${d.integrity&&!d.integrity.ok?`<div class="notice err">${d.integrity.issues.map(i=>J.esc(i.message)).join('<br>')}</div>`:''}<header class="pf-toolbar"><div><h1>Mes portefeuilles</h1><label class="sr-only" for="pf-select">Portefeuille affiché</label><select id="pf-select">${list.map(p=>`<option value="${p.id}" ${p.id===current?'selected':''}>${J.esc(p.name)}${p.is_default?' ★':''}</option>`).join('')}</select><button class="btn sm" id="new-pf" aria-label="Créer un portefeuille">＋</button></div><button class="btn primary" id="add-tx">＋ Transaction</button></header>${d.totals.unpriced?'<div class="notice warn">Valorisation et gain total indisponibles : cours ou change manquant. Aucun prix d’achat n’est utilisé comme cours actuel.</div>':''}
      <nav class="pf-nav" id="pf-nav" role="tablist" aria-label="Espaces du portefeuille">${[['home','Mon portefeuille'],['manage','Historique et gestion']].map(([k,l])=>`<button type="button" role="tab" data-view="${k}" id="tab-${k}" aria-controls="panel-${k}">${l}</button>`).join('')}</nav>
      <section class="pf-panel" id="panel-home" data-panel="home" role="tabpanel" aria-labelledby="tab-home"><div id="pf-home" class="pf-home"><span class="spinner"></span></div></section>
      <section class="pf-panel" id="panel-manage" data-panel="manage" role="tabpanel" aria-labelledby="tab-manage"><button type="button" class="btn sm" id="back-home">← Retour au portefeuille</button>${section('tx','Transactions','',txBody(d))}${d.sales.length?section('sales','Ventes réalisées','',salesBody(d)):''}${d.lots.length?section('lots','Lots et réglages','',lotsBody(d)):''}${section('valuation','Valeur et mouvements d’argent','',`<p class="small muted">La valeur varie aussi avec les achats et ventes. Ces montants ne sont pas un rendement. Période commune sélectionnée en haut.</p><div id="value-history"></div>`)}${d.allocation?.rows?section('alloc','Répartition par zone','',allocBody(d.allocation)):''}${d.positions.some(p=>p.kind==='etf')&&etfHtml?section('etf','Secteurs de vos ETF','',etfHtml.replace(/^<div class="card">\s*<h2>[^<]*<\/h2>/,'<div>')):''}${splitNotice(d.positions)}${section('settings','Réglages du portefeuille','',`<div class="row"><button class="btn sm" id="rename">Renommer</button>${d.portfolio.is_default?'':'<button class="btn sm" id="mk-default">Définir par défaut</button>'}<button class="btn sm danger" id="del-pf">Supprimer</button></div><p class="small muted">Stratégie : ${J.esc(d.portfolio.strategy?(NAMES[d.portfolio.strategy.name]||'Personnalisée'):'Croissance régulière par défaut')}. Réglage depuis l’Explorer.</p>`)}</section>`;
    folds();
    J.$('#pf-select').onchange=e=>{current=+e.target.value;render()};
    J.$$('#pf-nav [data-view]').forEach((b,index,buttons)=>{b.onclick=()=>switchView(b.dataset.view);b.onkeydown=e=>{const delta={ArrowRight:1,ArrowLeft:-1}[e.key];if(delta){e.preventDefault();const next=buttons[(index+delta+buttons.length)%buttons.length];switchView(next.dataset.view);next.focus()}}});
    J.$('#back-home').onclick=()=>{switchView('home');scrollTo(0,0)};
    switchView(VIEW);
    const pid=current;
    J.api('portfolio/history',{params:{id:pid}}).then(h=>{if(pid!==current)return;H=h;drawEvo()}).catch(e=>{const hm=J.$('#pf-home');if(hm)hm.innerHTML=`<p class="notice err">Historique indisponible : ${J.esc(e.message)}. Rechargez la page.</p>`});
    J.$('#new-pf').onclick=createPf;
    J.$('#add-tx').onclick=()=>J.txDialog({portfolios:list,portfolioId:current,onDone:render});
    J.$$('[data-lot]').forEach(b=>b.onclick=()=>lotDialog(d,d.lots.find(l=>l.tx_id==b.dataset.lot)));
    renderTransactions();
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
    J.dialog({ title: 'Achat du ' + J.date(l.trade_at) + ' · ' + (l.name || l.symbol), body: `${a.risk ? `<div class="lot-risk">${J.riskBar(a.risk)}${J.riskDetail(a.risk)}</div>` : ''}<p class="small muted">Laissez vide pour garder la valeur par défaut de la stratégie${a.rules ? ` (actuellement : ${a.rules.days ? a.rules.days + ' jours' : 'pas de durée'}, ${a.rules.drop ? '−' + a.rules.drop + ' %' : 'pas de seuil de recul'})` : ''}.</p>
      ${J.field('Stratégie de cet achat', `<select id="lt-st">${opts}</select>`)}${J.field('Rappel après (jours de détention)', `<input id="lt-days" inputmode="numeric" value="${s.alert_days ?? ''}" placeholder="défaut de la stratégie">`)}${J.field('Alerte si recul depuis le plus haut (%)', `<input id="lt-drop" inputmode="decimal" value="${s.alert_drop_pct ?? ''}" placeholder="défaut de la stratégie">`)}`,
      actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async dlg => { const v = i => J.$(i, dlg).value.trim().replace(',', '.'); try { await J.post('lot/settings', { tx_id: l.tx_id, strategy: v('#lt-st'), alert_days: v('#lt-days'), alert_drop_pct: v('#lt-drop') }); } catch (e) { J.formError(dlg, e.message); return true; } render(); } }] });
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
