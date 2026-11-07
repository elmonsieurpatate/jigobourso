/* Classement : titres réels notés par le moteur V4 ; la stratégie et les filtres choisis ici ne modifient jamais les scores. */
(async () => {
  'use strict';
  const user = await J.init('explorer'); if (!user) return;
  const $ = s => document.querySelector(s), esc = J.esc;
  const periods = [['week','Semaine',5],['month','Mois',21],['quarter','Trimestre',63],['half','6 mois',126],['year','1 an',252],['two_year','2 ans',504]];
  // Critères de RECHERCHE de chaque stratégie intégrée : lus dans le moteur (scores_admin.V4_STRATEGIES via ranking/criteria), jamais recopiés ici.
  // Ils filtrent l'affichage ; ils n'entrent ni dans les notes ni dans les rangs. Une stratégie sans critère (Momentum) a des seuils à 0 = aucun critère.
  let crit={};try{crit=(await J.api('ranking/criteria')).criteria||{};}catch(_){/* périodes actives seules si le moteur ne répond pas */}
  const FALLBACK={fast:['week','month'],regular:['month','quarter'],calm:['month','quarter'],rebound:['week','month','half'],mom6:['quarter','half'],mom12:['half','year'],momrisk:['half','year']};
  const profiles=Object.fromEntries(Object.keys(FALLBACK).map(id=>{
    const src=(crit[id]&&crit[id].periods)||Object.fromEntries(FALLBACK[id].map(k=>[k,{}])),per={},extra=[];
    for(const [k,t] of Object.entries(src)){
      if(t.slope!==undefined||t.r2!==undefined||!Object.keys(t).length)per[k]=[t.slope||0,t.r2||0];
      if(t.max_volatility!==undefined&&!extra.some(x=>x[0]==='volatility'))extra.push(['volatility','<=',t.max_volatility,'month']);
      if(t.max_drawdown!==undefined&&!extra.some(x=>x[0]==='drawdown'))extra.push(['drawdown','<=',t.max_drawdown,'month']);
      if(t.max_return!==undefined)extra.push(['return','<=',t.max_return,k]);
      if(t.min_return!==undefined)extra.push(['return','>=',t.min_return,k]);
    }
    for(const k of Object.keys(src))if(!per[k])per[k]=[0,0];                                 // période active sans pente ni R² (ex. contexte du Rebond)
    return [id,{per,extra}];
  }));
  const secondary=window.ClassementTestSecondary;
  const categoryPayload=window.ClassementTestCategoryConfig || await J.api('explorer/secondary-filters');
  const categories=secondary.normalize(categoryPayload);
  let serverView=null;try{serverView=await J.api('classement-test/strategies');}catch(_){/* page utilisable, enregistrement serveur indisponible */}
  const filters=Object.fromEntries(Object.entries(categories).map(([k,c])=>[k,[c.label,c.options]]));
  const columns = ['Titre','Place','Secteur','Cours','Var. %','Pente %/séance','R²','Volatilité','Liquidité','Volume','Recul max.','Perf. 1 mois','Score simple','Score complexe','Tendance'];
  const metrics = { slope:['Pente (% / séance)','% / séance'], r2:['R² (régression)',''], volatility:['Volatilité quotidienne','%'], drawdown:['Recul maximal','%'], return:['Rendement observé','%'], volume:['Volume moyen','titres / séance'] };
  const key = 'jigo_classement_test_v1';
  const fresh = id => { const pr=profiles[id],first=Object.values(pr.per)[0]; return { periods:Object.fromEntries(periods.map(([k]) => { const v=pr.per[k]; return [k,{enabled:!!v,slope:v?v[0]:first[0],r2:v?v[1]:first[1]}]; })), extra:(pr.extra||[]).map(([metric,op,value,period])=>({metric,op,value,period:period||'month'})), join:'and' }; };
  let state = { mode:'simple',strategy:'fast',selected:'week',profiles:Object.fromEntries(Object.keys(profiles).map(id=>[id,fresh(id)])),filters:secondary.all(categories),columns:[0,3,4,5,6,7,8,12,13,14] };
  // Seules les sauvegardes explicites de cette page sont relues. Les préférences Explorer restent séparées.
  try {
    const saved = JSON.parse(localStorage.getItem(key));
    if (saved && saved.profiles && typeof saved.profiles==='object') for (const id of Object.keys(profiles)) if (!saved.profiles[id]) saved.profiles[id]=fresh(id);     // stratégies ajoutées depuis la sauvegarde
    if (saved && ['simple','expert'].includes(saved.mode) && profiles[saved.strategy] && periods.some(([k])=>k===saved.selected) && Object.keys(profiles).every(id => {
      const p=saved.profiles?.[id]; return p && ['and','or'].includes(p.join) && Array.isArray(p.extra) && p.extra.every(x=>metrics[x.metric] && ['>=','<='].includes(x.op) && Number.isFinite(x.value) && x.value>=0) && periods.every(([k])=>typeof p.periods?.[k]?.enabled==='boolean' && Number.isFinite(p.periods[k].slope) && p.periods[k].slope>=.01 && p.periods[k].slope<=2 && Number.isFinite(p.periods[k].r2) && p.periods[k].r2>=0 && p.periods[k].r2<=1);
    }) && saved.filters && typeof saved.filters==='object' && Array.isArray(saved.cols) && saved.cols.every(n=>Number.isInteger(n)&&n>=0&&n<columns.length)) state=saved;
  } catch (_) { /* Stockage absent ou ancien : valeurs de démonstration. */ }
  const adminSelections=secondary.defaults(categoryPayload,categories);
  const userKey=String(user.id??'offline');
  let rawLocal={};try{rawLocal=JSON.parse(localStorage.getItem(key)||'{}')||{};}catch(_){}
  const byUser=rawLocal.secondaryOverridesByUser||{};
  let overrides=Object.fromEntries(Object.entries(byUser[userKey]||{}).filter(([,v])=>v&&Array.isArray(v.selected)&&Array.isArray(v.known)));
  const metadataMigration=secondary.migrateOverrides(categoryPayload,overrides);
  overrides=metadataMigration.overrides;
  if(Object.keys(metadataMigration.previous).length){
    const previous=rawLocal.secondaryMetadataPreviousByUser||{};
    rawLocal.secondaryMetadataPreviousByUser={...previous,[userKey]:{...(previous[userKey]||{}),...metadataMigration.previous}};
    rawLocal.secondaryOverridesByUser={...byUser,[userKey]:overrides};
    try{localStorage.setItem(key,JSON.stringify(rawLocal));}catch(_){/* Current session still uses the migrated preferences. */}
  }
  // Migrate explicit restrictive selections from the prior stable-label prototype once.
  if(!byUser[userKey]&&categoryPayload.schema===2&&rawLocal.filters&&rawLocal.categorySignature){
    let previous={};try{previous=JSON.parse(rawLocal.categorySignature);}catch(_){}
    for(const f of categoryPayload.definitions.filters){if(!f.editable||!categories[f.id])continue;
      const target=new Set(adminSelections[f.id]);let changed=false;
      for(const m of f.measures){const selected=rawLocal.filters[m.id],old=previous[m.id];if(!old||!Array.isArray(selected)||selected.length===old.labels.length+1)continue;
        changed=true;for(const o of categories[f.id].options.filter(o=>o.measure===m.id))target.delete(o.id);
        for(const id of selected){const name=id==='unknown'?null:old.labels[Number(String(id).slice(1))];const c=m.categories.find(c=>id==='unknown'?c.unknown:c.name===name);if(c&&c.active)target.add(m.id+'::'+c.id);}
      }
      if(changed)overrides[f.id]={selected:[...target],known:categories[f.id].options.map(o=>o.id)};
    }
  }
  // Un choix enregistré garde ses identifiants ; seules les catégories apparues depuis suivent les défauts de l'administration.
  const filtersFor=o=>Object.fromEntries(Object.entries(categories).map(([k,c])=>{
    const own=o[k],all=c.options.map(x=>x.id);if(!own)return[k,adminSelections[k]];
    const selected=new Set(own.selected.filter(id=>all.includes(id)));
    for(const id of adminSelections[k])if(!own.known.includes(id))selected.add(id);
    return[k,[...selected]];
  }));
  state.filters=filtersFor(overrides);
  state.secondaryOverridesByUser={...byUser,[userKey]:overrides};
  state.secondaryMetadataPreviousByUser=rawLocal.secondaryMetadataPreviousByUser||{};
  function saveLocalSelection(id){
    if(id)overrides[id]={selected:[...state.filters[id]],known:categories[id].options.map(o=>o.id)};
    ovBy[state.strategy]=overrides;
  }
  if(metadataMigration.notices.length)queueMicrotask(()=>feedback('Préférences regroupées : vérifiez les filtres géographiques, sectoriels et de places. Les anciennes sélections sont conservées sur cet appareil.'));
  const categorySignature=JSON.stringify(categoryPayload.definitions||categoryPayload.categories);
  state.categorySignature=categorySignature;
  // Jeu fictif immuable. Le formulaire de stratégie n'entre jamais dans son calcul.
  let intrinsicRows=[],loadError=null,scoreLabel='',loading=true,universe=0,defaultSort='simple';
  const tableState={sort:'simple',direction:'desc',page:1,pageSize:50,userSorted:false,verdict:'retained',query:new URLSearchParams(location.search).get('q')||''};
  let activeFilter=null, filterQuery='';
  const config = () => state.profiles[state.strategy];
  const isPrimary = r => r.metric === 'slope' || r.metric === 'r2';
  const rule = (metric,period,value,op='>=') => ({kind:'rule',metric,period,value,op});
  const group = (children=[],join='and') => ({kind:'group',join,children});
  function validTree(n,depth=0) {
    if(!n || depth>6) return false;
    if(n.kind==='group') return ['and','or'].includes(n.join) && Array.isArray(n.children) && n.children.length<=50 && n.children.every(x=>validTree(x,depth+1));
    return n.kind==='rule' && metrics[n.metric] && ['>=','<=','>','<','='].includes(n.op) && periods.some(([k])=>k===n.period) && Number.isFinite(n.value);
  }
  function tree() {
    const c=config();
    if(!c.tree || !validTree(c.tree) || c.tree.kind!=='group') {
      c.tree=group(periods.filter(([k])=>c.periods[k].enabled).flatMap(([k])=>['slope','r2'].map(m=>rule(m,k,c.periods[k][m]))));
      if(c.extra.length) c.tree.children.push(group(c.extra.map(x=>rule(x.metric,x.period||'month',x.value,x.op)),c.join));
    }
    return c.tree;
  }
  function leaves(n=tree(),path=[],joins=[]) {
    if(n.kind==='rule') return [{node:n,path,joins}];
    return n.children.flatMap((x,i)=>leaves(x,[...path,i],[...joins,n.join]));
  }
  function at(path) { return path===''?tree():path.split('.').reduce((n,i)=>n.children[Number(i)],tree()); }
  function project() {
    const rules=leaves().map(x=>x.node);
    periods.forEach(([k])=>{
      const p=config().periods[k], own=rules.filter(r=>isPrimary(r)&&r.period===k);
      p.enabled=own.length>0;
      ['slope','r2'].forEach(m=>{const r=own.find(r=>r.metric===m&&r.op==='>=');if(r)p[m]=r.value;});
    });
  }
  function simpleCompatible() {
    const all=leaves().filter(x=>isPrimary(x.node));
    return all.every(({node:r,joins})=>r.op==='>=' && joins.every(j=>j==='and') && r.value>=0 && r.value<=(r.metric==='slope'?2:1)) && periods.every(([k])=>{
      const own=all.filter(x=>x.node.period===k);return !own.length || (own.length===2 && new Set(own.map(x=>x.node.metric)).size===2);
    });
  }
  function setSimpleValue(metric,value) {
    config().periods[state.selected][metric]=value;
    leaves().filter(x=>x.node.metric===metric&&x.node.period===state.selected&&x.node.op==='>=').forEach(x=>x.node.value=value);
  }
  function activatePeriod(k,enabled) {
    function remove(n) {if(n.kind==='group') {n.children=n.children.filter(x=>!(x.kind==='rule'&&isPrimary(x)&&x.period===k));n.children.forEach(remove);}}
    remove(tree());
    if(enabled) ['slope','r2'].forEach(m=>tree().children.push(rule(m,k,config().periods[k][m])));
    project();
  }

  // ───── Stratégies enregistrées (MariaDB) : une configuration et des choix de filtres propres à chacune ─────
  const builtinNames={fast:'Croissance rapide',regular:'Croissance régulière',calm:'Hausse calme',rebound:'Rebond',mom6:'Momentum 6 mois (expérimental)',mom12:'Momentum 12 mois (expérimental)',momrisk:'Momentum ajusté du risque (expérimental)'};
  const names={...builtinNames},ovBy={},saved={},cloneJSON=x=>JSON.parse(JSON.stringify(x));
  let customIds=[],rev=serverView?serverView.revision:0,busy=false,meta=cloneJSON(serverView?.meta||{});
  const metaOf=id=>({icon:'📈',description:'',enabled:true,...(meta[id]||{})});
  const serverOk=!!serverView;
  const order=()=>[...Object.keys(builtinNames),...customIds];
  const seed=cloneJSON(overrides);
  for(const id of Object.keys(builtinNames)){if(serverOk)state.profiles[id]=fresh(id);ovBy[id]=cloneJSON(seed);}
  for(const it of serverView?.items||[]){names[it.id]=it.name;state.profiles[it.id]=cloneJSON(it.config);ovBy[it.id]=cloneJSON(it.filters||{});if(!it.builtin)customIds.push(it.id);}
  const enabledIds=()=>order().filter(id=>metaOf(id).enabled);
  if(serverOk&&enabledIds().includes(serverView.selected))state.strategy=serverView.selected;else if(serverOk&&enabledIds().length)state.strategy=enabledIds()[0];
  {const want=new URLSearchParams(location.search).get('strategy');if(serverOk&&want&&enabledIds().includes(want))state.strategy=want;}
  for(const id of order()){const s=state.strategy;state.strategy=id;tree();state.strategy=s;saved[id]={p:cloneJSON(state.profiles[id]),o:cloneJSON(ovBy[id])};}
  try{const l=JSON.parse(localStorage.getItem(key)||'{}')||{};if(['simple','expert'].includes(l.mode))state.mode=l.mode;if(Array.isArray(l.cols)&&l.cols.every(n=>Number.isInteger(n)&&n>=0&&n<columns.length))state.columns=l.cols;}catch(_){/* préférences d'affichage facultatives */}
  try{if(!localStorage.getItem('jigo_ct_cols_v4')){state.columns=window.matchMedia('(max-width:700px)').matches?[0,3,4,5,12,13]:[0,3,4,5,6,7,8,12,13,14];localStorage.setItem('jigo_ct_cols_v3','1');}}catch(_){/* préférence facultative */}   // colonnes essentielles par défaut (place, secteur, recul… via « Colonnes ») : pas de défilement horizontal inutile
  overrides=ovBy[state.strategy];state.filters=filtersFor(overrides);
  state.selected=periods.find(([k])=>config().periods[k].enabled)?.[0]||state.selected;
  const isDirty=id=>JSON.stringify([state.profiles[id],id===state.strategy?overrides:ovBy[id]])!==JSON.stringify([saved[id].p,saved[id].o]);
  const anyDirty=()=>order().some(isDirty);
  function renderStrategies(){
    const sel=$('#ct-strategy');
    const html=order().filter(id=>metaOf(id).enabled||id===state.strategy).map(id=>`<option value="${esc(id)}">${esc(metaOf(id).icon+' '+names[id])}${isDirty(id)?' •':''}</option>`).join('');
    if(sel.dataset.html!==html){sel.innerHTML=html;sel.dataset.html=html;}      // ne jamais reconstruire le menu à chaque clic : il se refermerait (iPhone)
    const d=$('#ct-strategy-desc'),txt=metaOf(state.strategy).description;d.textContent=txt;d.hidden=!txt;
    if(sel.value!==state.strategy)sel.value=state.strategy;
    const builtin=!!builtinNames[state.strategy];
    $('#ct-rename').hidden=builtin;$('#ct-delete').hidden=builtin;
    $('#ct-reset').textContent=builtin?'Restaurer les valeurs par défaut':'Annuler les modifications';
    $('#ct-strategy-state').textContent=!serverOk?'Enregistrement indisponible':isDirty(state.strategy)?'Modifications non enregistrées':'Enregistrée';
    $('#ct-save').disabled=!serverOk;$('#ct-duplicate').disabled=!serverOk;
  }
  const post=body=>J.post('classement-test/strategies/save',{revision:rev,...body});
  function takeView(view){rev=view.revision;meta=cloneJSON(view.meta||{});for(const it of view.items)names[it.id]=it.name;customIds=view.items.filter(i=>!i.builtin).map(i=>i.id);}
  function switchTo(id,remember=true){
    closeFilter();ovBy[state.strategy]=overrides;state.strategy=id;overrides=ovBy[id]||(ovBy[id]={});state.filters=filtersFor(overrides);
    tableState.page=1;tableState.userSorted=false;tree();project();state.selected=periods.find(([k])=>config().periods[k].enabled)?.[0]||'week';render();loadRows();
    if(remember&&serverOk)J.post('classement-test/strategies/save',{action:'select',id}).catch(()=>{});
  }
  function currentPayload(){tree();project();return {config:cloneJSON(state.profiles[state.strategy]),filters:cloneJSON(overrides)};}
  function markSaved(id){saved[id]={p:cloneJSON(state.profiles[id]),o:cloneJSON(id===state.strategy?overrides:ovBy[id])};}
  async function guarded(fn){if(busy)return;busy=true;try{await fn();}catch(e){feedback(e.message||'Action impossible.');}finally{busy=false;renderStrategies();}}
  function askName(title,initial,okLabel){return new Promise(resolve=>{let done=false;J.dialog({title,body:`<label class="field">Nom de la stratégie<input id="ct-name-input" maxlength="60" value="${esc(initial)}" autocomplete="off"></label>`,
    actions:[{label:'Annuler',run:()=>{}},{label:okLabel,cls:'primary',run:d=>{const v=d.querySelector('#ct-name-input').value.trim();if(!v){J.formError(d,'Un nom est requis.');return true;}done=true;resolve(v);}}],
    onopen:d=>{const i=d.querySelector('#ct-name-input');i.focus();i.select();}}).addEventListener('close',()=>{if(!done)resolve(null);});});}
  function uniqueCopyName(base){let n=`Copie de ${base}`,i=2;const taken=new Set(order().map(id=>names[id].toLowerCase()));while(taken.has(n.toLowerCase()))n=`Copie de ${base} (${i++})`;return n.slice(0,60);}
  window.addEventListener('beforeunload',e=>{if(anyDirty()){e.preventDefault();e.returnValue='';}});
  const fmt = n => new Intl.NumberFormat('fr-FR',{minimumFractionDigits:2,maximumFractionDigits:3}).format(n);
  let timer;
  function feedback(text) { $('#ct-feedback').textContent=text; clearTimeout(timer); timer=setTimeout(()=>$('#ct-feedback').textContent='',5500); }
  function number(value,min,max,fallback) { if(String(value).trim()==='') return fallback; const n=Number(String(value).replace(',','.'));return Number.isFinite(n)?Math.max(min,Math.min(max,n)):fallback; }
  function chart() {
    const p=config().periods[state.selected];
    const slope=p.slope/2, spread=(1-p.r2)*28, jitter=[0,1,-.7,.8,-1,.4,-.6,.3,0];
    const pts=jitter.map((j,i)=>[15+i*25,86-i*(2+slope*7)+j*spread]);
    $('#ct-chart').innerHTML=`<svg viewBox="0 0 240 110" role="img" aria-label="Illustration : pente ${fmt(p.slope)} pour cent par séance, R² ${fmt(p.r2)}"><path d="M10 95H230M10 95V10" fill="none" stroke="var(--line)"/><path d="M15 86L215 ${86-8*(2+slope*7)}" stroke="var(--ct-green)" stroke-width="2" stroke-dasharray="4 4"/><polyline points="${pts.map(p=>p.join(',')).join(' ')}" fill="none" stroke="var(--ct-accent)" stroke-width="2"/>${pts.map(([x,y])=>`<circle cx="${x}" cy="${y}" r="3.5" fill="var(--ct-accent)"/>`).join('')}</svg>`;
  }
  function preview() {
    const active=periods.filter(([k])=>config().periods[k].enabled);
    $('#ct-active-summary').textContent=active.length?`${active.length} périodes actives · ${active.map(([,l])=>l).join(' + ')}`:'Aucune période active · configuration libre';
    function text(n) {
      if(n.kind==='rule') return `<span>${metrics[n.metric][0]} ${esc(n.op)} ${fmt(n.value)} ${metrics[n.metric][1]} <em>(${periods.find(([k])=>k===n.period)[1]})</em></span>`;
      return `<div class="ct-preview-group"><b>${n.join==='and'?'TOUTES (ET)':'AU MOINS UNE (OU)'}</b>${n.children.map(x=>`<div>${text(x)}</div>`).join('')||'<span>Aucun critère</span>'}</div>`;
    }
    $('#ct-preview').innerHTML=text(tree());
    if(!loading&&typeof renderRanking==='function'){renderRanking();scheduleVerdicts();}                 // le tableau suit immédiatement les seuils / règles (affichage seulement)
    const hasEmpty = n => n.kind==='group' && (!n.children.length || n.children.some(hasEmpty));
    const valid=leaves().length>0 && !hasEmpty(tree()) && leaves().every(({node:r})=>Number.isFinite(r.value) && (r.metric!=='r2'||(r.value>=0&&r.value<=1)) && (!['volatility','drawdown','volume'].includes(r.metric)||r.value>=0));
    const badge=$('.ct-valid');badge.textContent=valid?'✓ Filtre valide':'⚠ Filtre à compléter';badge.classList.toggle('invalid',!valid);

    const advanced=leaves().filter(x=>!isPrimary(x.node)).length, compatible=simpleCompatible();
    $('#ct-extra-note').hidden=!advanced&&compatible;
    $('#ct-extra-note').textContent=compatible?`${advanced} critère(s) avancé(s) conservé(s). Consultez le mode Expert pour les modifier.`:'Règles avancées conservées : cette combinaison ne peut pas être représentée fidèlement par deux minimums. Modifiez-la en mode Expert ; les curseurs simples sont verrouillés.';
  }
  function renderSimple() {
    $('#ct-periods').innerHTML=periods.map(([k,label,n])=>`<div class="ct-period ${config().periods[k].enabled?'active':''} ${state.selected===k?'selected':''}"><button type="button" data-period="${k}" aria-pressed="${state.selected===k}">${label}<small>≈ ${n} séances</small></button><label><input type="checkbox" data-enabled="${k}" ${config().periods[k].enabled?'checked':''}>Activée</label></div>`).join('');
    const p=config().periods[state.selected];
    $('#ct-sliders').innerHTML=[['slope','Pente minimale',0,2,.001,'% / séance','Progression moyenne modélisée par séance. À 0 : aucun seuil. Masque seulement des lignes : notes et rangs ne changent pas.'],['r2','R² minimal',0,1,.001,'','Régularité : de 0 (dispersé) à 1 (aligné).']].map(([id,label,min,max,step,unit,help])=>`<div class="ct-control"><label for="ct-range-${id}">${label} · ${periods.find(([k])=>k===state.selected)[1]}</label><div class="ct-slider-row"><button type="button" data-step="${id}" data-delta="-${step}" aria-label="Diminuer ${label}">−</button><input id="ct-range-${id}" type="range" data-simple="${id}" min="${min}" max="${max}" step="${step}" value="${p[id]}" aria-label="${label}"><button type="button" data-step="${id}" data-delta="${step}" aria-label="Augmenter ${label}">+</button><div class="ct-number"><input id="ct-value-${id}" type="number" data-simple="${id}" min="${min}" max="${max}" step="${step}" value="${p[id]}" aria-label="Valeur ${label}"><span>${unit}</span></div></div><p class="ct-control-help">${help}</p></div>`).join('');
    const compatible=simpleCompatible();
    $('#ct-simple').querySelectorAll('input,button[data-step]').forEach(el=>el.disabled=!compatible);
    chart();preview();
  }
  function renderExpert() {
    function draw(n,path=[],depth=0) {
      const p=path.join('.');
      if(n.kind==='rule') return `<div class="ct-builder-row" data-path="${p}">
        <select data-rule-field="metric" aria-label="Indicateur ${p}">${Object.entries(metrics).map(([k,[l]])=>`<option value="${k}" ${n.metric===k?'selected':''}>${l}</option>`).join('')}</select>
        <select data-rule-field="op" aria-label="Opérateur ${p}">${[['>=','≥'],['<=','≤'],['>','>'],['<','<'],['=','=']].map(([v,l])=>`<option value="${esc(v)}" ${n.op===v?'selected':''}>${esc(l)}</option>`).join('')}</select>
        <input type="number" step="any" value="${Number(n.value.toFixed(3))}" data-rule-field="value" aria-label="Valeur ${p}">
        <select data-rule-field="period" aria-label="Période ${p}">${periods.map(([k,l,count])=>`<option value="${k}" ${n.period===k?'selected':''}>sur ${l.toLowerCase()} (≈ ${count} s.)</option>`).join('')}</select>
        <button type="button" class="ct-rule-remove" data-remove-node="${p}" aria-label="Supprimer le critère ${p}">×</button>
      </div>`;
      return `<div class="ct-builder-group ${depth?'nested':''}" data-group-path="${p}"><div class="ct-group-operator"><select data-group-join="${p}" aria-label="Combinaison ${depth?'du groupe '+p:'principale'}"><option value="and" ${n.join==='and'?'selected':''}>ET</option><option value="or" ${n.join==='or'?'selected':''}>OU</option></select></div><div class="ct-group-content">${n.children.map((x,i)=>draw(x,[...path,i],depth+1)).join('')||'<p class="ct-no-rules">Aucun critère dans ce groupe.</p>'}<div class="ct-group-actions"><button type="button" data-add-node="${p}">＋ Ajouter un critère</button>${depth<4?`<button type="button" data-add-group="${p}">＋ Groupe ET / OU</button>`:''}${depth?`<button type="button" data-remove-node="${p}" class="ct-delete-group">Supprimer le groupe</button>`:''}</div></div></div>`;
    }
    $('#ct-rules').innerHTML=draw(tree());
    preview();
  }
  function renderFilters() {
    $('#ct-filter-source').textContent=(categoryPayload.source_label||'Catégories administrateur')+' · bornes en lecture seule'+(Object.keys(state.secondaryMetadataPreviousByUser[userKey]||{}).length?' · anciennes préférences regroupées : vérifiez vos sélections':'');
    if(categoryPayload.schema===2)document.querySelector('.ct-filter-logic').textContent='Un filtre retient un titre si l’une de ses catégories est cochée ; les filtres se combinent. Les scores et les rangs ne changent jamais.';
    const drawIndicator=([k,c])=>`<div class="ct-multi" data-indicator="${k}"><button type="button" class="ct-multi-trigger" data-open-filter="${k}" title="${esc(c.label)} · ${esc(c.unit)}" aria-expanded="${activeFilter===k}" aria-controls="ct-list-${k}"><span>${esc(c.label)}</span><b data-count="${k}">${state.filters[k].length} / ${c.options.length}</b><span aria-hidden="true">⌄</span></button><div class="ct-multi-popup" id="ct-list-${k}" ${activeFilter===k?'':'hidden'}><label class="ct-category-search"><span aria-hidden="true">⌕</span><input type="search" data-category-search="${k}" placeholder="Rechercher une catégorie…" aria-label="Rechercher une catégorie : ${esc(c.label)}" value="${activeFilter===k?esc(filterQuery):''}"></label><div class="ct-category-options" role="group" aria-label="Catégories : ${esc(c.label)}">${c.options.map(o=>`<label class="ct-category-option" data-search-text="${esc(o.label.toLocaleLowerCase('fr'))}"><input type="checkbox" data-filter="${k}" data-category="${o.id}" ${state.filters[k].includes(o.id)?'checked':''}><i style="background:${o.color}" aria-hidden="true"></i><span>${esc(o.label)}</span><small>${esc(o.range)}</small></label>`).join('')}</div><p class="ct-no-category" hidden>Aucune catégorie correspondante.</p><footer><span data-selected-count="${k}">${state.filters[k].length} / ${c.options.length} sélectionnées</span><button type="button" data-all-indicator="${k}">Tout sélectionner</button><button type="button" data-close-filter="${k}" aria-label="Fermer ${esc(c.label)}">Fermer</button></footer></div></div>`;
    const primaryKeys=categoryPayload.schema===2?['volatility','liquidity','volume','positive','spikes','concentration']:['volatility','turnover_eur','avg_volume','drawdown','up_fraction','gain_share'];
    const isPrimary=([k,c])=>categoryPayload.schema===2?c.group==='main':primaryKeys.includes(k);
    const primary=Object.entries(categories).filter(isPrimary),other=Object.entries(categories).filter(e=>!isPrimary(e));
    $('#ct-filters').innerHTML=Object.keys(categories).length?`<div class="ct-filter-main">${primary.map(drawIndicator).join('')}</div>${other.length?`<details class="ct-more-filters"><summary>Autres indicateurs (${other.length}) <span id="ct-more-count"></span></summary><div class="ct-filter-main">${other.map(drawIndicator).join('')}</div></details>`:''}`:'<p>Aucun filtre actif. Les définitions restent accessibles dans l’administration.</p>';
    filterSummary();
    if(activeFilter) searchCategories(activeFilter,filterQuery);
  }
  function isPrimaryKey(k){const c=categories[k];return categoryPayload.schema===2?c?.group==='main':['volatility','turnover_eur','avg_volume','drawdown','up_fraction','gain_share'].includes(k);}
  function filterSummary() {
    const changed=Object.keys(categories).filter(k=>state.filters[k].length!==categories[k].options.length);
    const more=$('#ct-more-count');if(more)more.textContent=changed.filter(k=>!isPrimaryKey(k)).length+' filtre(s) actif(s)';
    $('#ct-filter-summary').textContent=changed.length?`${changed.length} / ${Object.keys(categories).length}`:'Tout inclus';
    for(const [k,c] of Object.entries(categories)) {
      const trigger=$(`[data-open-filter="${k}"]`);
      if(!trigger)continue;
      trigger.classList.toggle('filtered',state.filters[k].length!==c.options.length);
      $(`[data-count="${k}"]`).textContent=`${state.filters[k].length} / ${c.options.length}`;
      $(`[data-selected-count="${k}"]`).textContent=`${state.filters[k].length} / ${c.options.length} sélectionnées`;
    }
    renderRanking();
  }
  function searchCategories(key,query) {
    const popup=$(`#ct-list-${key}`),needle=query.trim().toLocaleLowerCase('fr');let shown=0;
    popup.querySelectorAll('[data-search-text]').forEach(el=>{el.hidden=!el.dataset.searchText.includes(needle);if(!el.hidden)shown++;});
    popup.querySelector('.ct-no-category').hidden=shown!==0;
  }
  function positionFilter(k) {
    const popup=$(`#ct-list-${k}`);
    if(getComputedStyle(popup).position!=='absolute')return;
    popup.style.left='0';popup.style.right='auto';
    if(popup.getBoundingClientRect().right>innerWidth-12){popup.style.left='auto';popup.style.right='0';}
    if(popup.getBoundingClientRect().left<12){popup.style.left=(12-popup.parentElement.getBoundingClientRect().left)+'px';popup.style.right='auto';}
  }
  function closeFilter(restoreFocus=false) {
    const old=activeFilter;activeFilter=null;filterQuery='';
    if(old){$(`#ct-list-${old}`).hidden=true;$(`[data-open-filter="${old}"]`).setAttribute('aria-expanded','false');if(restoreFocus)$(`[data-open-filter="${old}"]`).focus();}
  }
  const columnKeys=['name','market','sector','price','change','slope','r2','volatility','turnover','avgVolume','drawdown','perfMonth','simple','complex','trend'];
  const columnTitles=columns;
  const MEASURE={volatility:'volatility',turnover:'turnover_eur',avgVolume:'avg_volume',drawdown:'drawdown',perfMonth:'perf-month',simple:'score_simple_v4',complex:'score_complex_v4'};
  const eur=n=>n===null||n===undefined?'—':new Intl.NumberFormat('fr-FR',{style:'currency',currency:'EUR',maximumFractionDigits:n>=1000?0:2}).format(n);
  const money=eur;
  function percent(n,sign=false){return n===null||n===undefined?'—':new Intl.NumberFormat('fr-FR',{minimumFractionDigits:2,maximumFractionDigits:2,signDisplay:sign?'exceptZero':'auto'}).format(n)+' %';}
  const num0=n=>n===null||n===undefined?'—':new Intl.NumberFormat('fr-FR',{maximumFractionDigits:0}).format(n);
  const score1=n=>n===null||n===undefined?'—':new Intl.NumberFormat('fr-FR',{minimumFractionDigits:1,maximumFractionDigits:1}).format(n);
  // Catégories de l'administration : la couleur d'un chiffre est celle de la catégorie du filtre correspondant.
  const defs=(categoryPayload.definitions&&categoryPayload.definitions.filters)||[];
  const measureOf=Object.create(null),filterOfMeasure=Object.create(null);
  for(const f of defs)for(const m of f.measures||[]){measureOf[m.id]=m;filterOfMeasure[m.id]=f;}
  const inside=(c,v)=>(c.min===null||v>c.min||(v===c.min&&c.minIncluded))&&(c.max===null||v<c.max||(v===c.max&&c.maxIncluded));
  function categoryOf(measureId,value){
    const m=measureOf[measureId];if(!m)return null;
    const unknown=m.categories.find(c=>c.unknown)||null;
    if(value===null||value===undefined||Number.isNaN(value))return unknown;
    if(m.kind==='enum')return m.categories.find(c=>!c.unknown&&(c.values||[]).includes(String(value)))||unknown;
    return m.categories.find(c=>!c.unknown&&inside(c,value))||unknown;
  }
  const tinted=(measureId,value,text)=>{const c=categoryOf(measureId,value);return c&&c.color?`<span class="ct-cat" style="--cat:${esc(c.color)}" title="${esc(c.name)}">${text}</span>`:text;};
  const hue=s=>{let h=0;for(const ch of s)h=(h*31+ch.charCodeAt(0))%360;return `hsl(${h} 45% 42%)`;};
  // La fiche s'ouvre dans une autre fenêtre : elle reçoit l'identifiant de la stratégie et, si les réglages ne sont pas enregistrés, un brouillon sous une clé de contexte (localStorage, même origine).
  // Brouillon introuvable côté fiche ⇒ elle l'indique et ne rend aucun verdict : jamais de remplacement silencieux par d'autres réglages.
  const ctxKey=s=>{let h=0;for(const c of s)h=(h*31+c.charCodeAt(0))|0;return (h>>>0).toString(36);};
  function sheetHref(id){
    let q='titre.html?src=explorer&id='+encodeURIComponent(id)+'&ct='+encodeURIComponent(state.strategy);
    if(typeof isDirty==='function'&&serverOk&&isDirty(state.strategy)){
      const spec=specNow(),json=JSON.stringify({id:state.strategy,spec}),k=ctxKey(json);
      try{localStorage.setItem('jigo_ct_ctx:'+k,json);}catch(_){/* la fiche signalera un contexte introuvable */}
      q+='&ctx='+k;
    }
    return q;
  }
  // Valeurs des mesures de filtres : reconstituées depuis les champs de la ligne (une valeur absente reste null, jamais 0).
  function secondaryOf(r){
    const x=r.extra||{},perf=r.perf||{};
    return {volatility:r.volatility,turnover_eur:r.turnover_eur,avg_volume:r.avg_volume,up_fraction:x.up_fraction??null,gain_share:x.gain_share??null,drawdown:r.drawdown,
      'perf-week':perf.week??null,'perf-month':perf.month??null,'perf-quarter':perf.quarter??null,quality:x.quality??null,freshness:null,coverage:x.coverage??null,
      score_simple_v4:r.simple,score_complex_v4:r.complex};
  }
  function toRow(r){
    return {id:r.id,rank:r.rank_complex,rankSimple:r.rank_simple,rankComplex:r.rank_complex,posSimple:r.pos_simple,posComplex:r.pos_complex,tieSimple:r.tie_simple||1,tieComplex:r.tie_complex||1,symbol:r.symbol,name:r.name,mic:r.mic,currency:r.currency,kind:r.kind,country:r.country,category:r.category,group:r.group,
      price:r.price_eur,priceNative:r.price,change:r.change,slope:r.slope,r2:r.r2,volatility:r.volatility,drawdown:r.drawdown,turnover:r.turnover_eur,liquiditySource:r.liquidity_source,avgVolume:r.avg_volume,
      perf:r.perf||{},perfMonth:r.perf&&r.perf.month!==undefined?r.perf.month:null,simple:r.simple,complex:r.complex,simpleStatus:r.simple_status,complexStatus:r.complex_status,score:r.complex,
      isin:r.isin,points:r.curve||[],color:hue(r.symbol),secondary:secondaryOf(r),periods:r.periods||{},held:!!r.held,lastClose:r.last_close,quality:r.quality,status:r.status||'undetermined'};
  }
  // Une ligne appartient à une catégorie par mesure (filtres à seuils) ou par groupe (pays, secteur, place, type). Un filtre retient la ligne si l'une de ses catégories est cochée (OU) ; les filtres se combinent en ET.
  function rowOptions(row,k){
    row._o=row._o||{};
    if(row._o[k])return row._o[k];
    const f=defs.find(x=>x.id===k);let out=[];
    if(f&&f.editable)out=(f.measures||[]).map(m=>{const c=categoryOf(m.id,row.secondary[m.id]);return c?m.id+'::'+c.id:null;}).filter(Boolean);
    else if(f)out=[row.group&&row.group[k]||'unknown'];
    return row._o[k]=out;
  }
  function applySecondary(rows){
    if(categoryPayload.schema!==2)return secondary.apply(rows,state.filters,categories);
    const active=Object.entries(categories).filter(([k,c])=>state.filters[k]&&state.filters[k].length!==c.options.length);
    if(!active.length)return [...rows];
    return rows.filter(row=>active.every(([k])=>rowOptions(row,k).some(id=>state.filters[k].includes(id))));
  }
  // Aucune admission : tous les titres évalués sont classés. Seuls les filtres secondaires masquent des lignes (affichage), sans toucher aux scores ni aux rangs.
  // Critères de recherche de la stratégie (pente / R² du mode Simple, règles du mode Expert) : ils servent à RECHERCHER les titres du profil. Ils ne modifient jamais une note ni un rang :
  // l'univers noté reste complet, un titre hors critères reste noté et classé (« Ignorer les critères » l'affiche). Un seuil à 0 est sans effet.
  // Statut de stratégie (retenue / exclue / indéterminée) : calculé par le serveur (moteur unique `criteria`, le même que l'administration et la fiche), jamais ici.
  // Il ne change ni note ni rang. Une donnée manquante donne « indéterminée », jamais « exclue » ; « Toutes » les montre toutes.
  const STATUS={retained:['Retenue','ok'],excluded:['Exclue','no'],undetermined:['Indéterminée','na']};
  const statusBadge=row=>{const [t,c]=STATUS[row.status]||STATUS.undetermined;return `<i class="ct-status ${c}" title="Statut de la stratégie : ${t.toLowerCase()}. Détail dans la fiche du titre.">${t}</i>`;};
  // base = titres notés (recherche texte comprise) ; scoped = base moins les filtres secondaires (c'est le périmètre des compteurs) ; rows = scoped selon Retenues / Exclues / Toutes.
  function visibleRows(){
    const needle=tableState.query.trim().toLocaleLowerCase('fr');
    const base=needle?intrinsicRows.filter(r=>(r.symbol+' '+r.name+' '+(r.isin||'')).toLocaleLowerCase('fr').includes(needle)):intrinsicRows;
    const scoped=applySecondary(base);
    const counts={retained:0,excluded:0,undetermined:0,all:scoped.length};
    for(const r of scoped)counts[r.status in counts?r.status:'undetermined']++;
    const rows=tableState.verdict==='all'?scoped:scoped.filter(r=>r.status===tableState.verdict);
    return {base,scoped,counts,rows};
  }
  function spark(row){
    if(!row.points.length)return '<span class="ct-missing">Indisponible</span>';
    const lo=Math.min(...row.points),hi=Math.max(...row.points),span=hi-lo||1;
    const pts=row.points.map((v,i)=>[4+i*96/Math.max(1,row.points.length-1),25-(v-lo)*21/span]);
    const up=row.points[row.points.length-1]>=row.points[0];
    return `<svg class="ct-mini-curve ${up?'positive':'negative'}" viewBox="0 0 104 30" role="img" aria-label="Clôtures des 21 dernières séances : ${up?'hausse':'baisse'}"><polyline points="${pts.map(p=>p.map(n=>n.toFixed(1)).join(',')).join(' ')}"/><circle cx="${pts.at(-1)[0]}" cy="${pts.at(-1)[1]}" r="2"/></svg>`;
  }
  const sectorLabel=row=>{const f=defs.find(x=>x.id==='sector'),g=(categoryPayload.defaults&&null)||null;const v=f&&(f.values||[]).find(x=>x.id===(row.group&&row.group.sector));return v?v.label:null;};
  function rowCell(row,key){
    if(key==='name')return `<a class="ct-company" href="${esc(sheetHref(row.id))}" target="_blank" rel="noopener" aria-label="Ouvrir la fiche de ${esc(row.symbol)} dans un nouvel onglet"><span class="ct-company-mark" style="--mark:${row.color}" aria-hidden="true">${esc(row.symbol.slice(0,2))}</span><span class="ct-company-text"><b>${esc(row.symbol)}${row.kind==='etf'?' <i class="ct-kind">ETF</i>':''}${row.held?' <i class="ct-kind held">détenu</i>':''}</b><span>${esc(row.name)}</span></span>${statusBadge(row)}</a>`;
    if(key==='market')return `<b>${esc(row.mic)}</b><span class="ct-sub">${esc(row.country||'Pays inconnu')} · ${esc(row.currency||'—')}</span>`;
    if(key==='sector'){const g=sectorLabel(row);return row.category?`<b>${esc(row.category)}</b><span class="ct-sub">${esc(g||'')}</span>`:'<span class="ct-missing">Inconnu</span>';}
    if(key==='price')return `${eur(row.price)}${row.currency&&row.currency!=='EUR'&&row.priceNative!==null?`<span class="ct-sub">${esc(new Intl.NumberFormat('fr-FR',{maximumFractionDigits:2}).format(row.priceNative))} ${esc(row.currency)}</span>`:''}`;
    if(key==='change')return `<span class="${row.change>0?'up':row.change<0?'down':''}">${percent(row.change,true)}</span>`;
    if(key==='slope')return `<span class="${row.slope>0?'up':row.slope<0?'down':''}">${percent(row.slope,true)}</span>`;
    if(key==='r2')return row.r2===null?'—':fmt(row.r2);
    if(key==='volatility')return tinted(MEASURE.volatility,row.volatility,percent(row.volatility));
    if(key==='turnover')return tinted(MEASURE.turnover,row.turnover,row.turnover===null?'—':eur(row.turnover))+(row.liquiditySource==='estimated'?'<span class="ct-sub" title="Moyenne trimestrielle du volume × cours : estimation">estimée</span>':'');
    if(key==='avgVolume')return tinted(MEASURE.avgVolume,row.avgVolume,num0(row.avgVolume));
    if(key==='drawdown')return tinted(MEASURE.drawdown,row.drawdown,row.drawdown===null?'—':percent(-row.drawdown));
    if(key==='perfMonth')return tinted(MEASURE.perfMonth,row.perfMonth,percent(row.perfMonth,true));
    if(key==='simple'||key==='complex')return `<span class="ct-score">${tinted(MEASURE[key],row[key],score1(row[key]))}</span>`;
    return spark(row);
  }
  function renderColumns(){
    state.columns=[...new Set([0,...state.columns])];
    $('#ct-columns').innerHTML=columns.map((l,i)=>`<label class="ct-option"><input type="checkbox" data-column="${i}" ${state.columns.includes(i)?'checked':''} ${i===0?'disabled':''}>${l}</label>`).join('');
    renderRanking();
  }
  const scoreKeyOf=()=>tableState.sort==='complex'?'complex':tableState.sort==='simple'?'simple':defaultSort;     // score dont le rang est affiché
  const rankKey=()=>scoreKeyOf()==='simple'?'rankSimple':'rankComplex';
  const posKey=()=>scoreKeyOf()==='simple'?'posSimple':'posComplex';
  const tieKey=()=>scoreKeyOf()==='simple'?'tieSimple':'tieComplex';
  const rankCell=row=>{const r=row[rankKey()];return r==null?'—':row[tieKey()]>1?`<span title="Ex æquo : ${row[tieKey()]} titres ont exactement ce score">=${r}</span>`:String(r);};
  function renderRanking(){
    if(loading){$('#ct-table-body').innerHTML='<tr class="ct-loading"><td colspan="20"><span class="spinner"></span> Chargement des titres…</td></tr>';$('#ct-empty-results').hidden=true;$('#ct-result-count').textContent='';return;}
    const selected=columnKeys.map((key,i)=>({key,i,label:columnTitles[i]})).filter(x=>state.columns.includes(x.i));
    const {base,scoped,counts,rows:filtered}=visibleRows();
    const rows=[...filtered].sort((a,b)=>{
      const isScore=tableState.sort==='simple'||tableState.sort==='complex';
      const av=isScore?(a[posKey()]==null?null:-a[posKey()]):a[tableState.sort],bv=isScore?(b[posKey()]==null?null:-b[posKey()]):b[tableState.sort];
      if((av===null||av===undefined)&&!(bv===null||bv===undefined))return 1;if((bv===null||bv===undefined)&&!(av===null||av===undefined))return -1;
      const compare=(av===null||av===undefined)?0:typeof av==='string'?av.localeCompare(bv,'fr'):av-bv;
      return (tableState.direction==='asc'?compare:-compare)||(a[posKey()]??1e9)-(b[posKey()]??1e9)||a.id-b.id;
    });
    const pages=Math.max(1,Math.ceil(rows.length/tableState.pageSize));tableState.page=Math.min(Math.max(1,tableState.page),pages);
    const start=(tableState.page-1)*tableState.pageSize,pageRows=rows.slice(start,start+tableState.pageSize);
    $('#ct-result-count').textContent=loadError?'':`${num0(rows.length)} titre${rows.length>1?'s':''}`+(rows.length!==intrinsicRows.length?` sur ${num0(intrinsicRows.length)} évalués`:'');
    $('#ct-table-head').innerHTML=`<th scope="col" class="ct-rank-cell" title="Rang général sur tous les titres notés (${tableState.sort==='simple'?'score simple':'score complexe'}), conservé lors du filtrage">#</th>`+selected.map(({key,label})=>`<th scope="col" class="${key==='name'?'ct-name-heading':''}" ${key!=='trend'?`aria-sort="${key===tableState.sort?(tableState.direction==='asc'?'ascending':'descending'):'none'}"`:''}>${key!=='trend'?`<button type="button" data-sort-column="${key}" aria-label="Trier par ${esc(label)}">${label}${key===tableState.sort?(tableState.direction==='asc'?' ↑':' ↓'):''}</button>`:label}</th>`).join('');
    $('#ct-table-body').innerHTML=pageRows.map(row=>`<tr data-row="${row.id}"><td class="ct-rank-cell" data-label="Rang">${rankCell(row)}</td>${selected.map(({key,label})=>`<td class="ct-cell-${key}" data-label="${esc(label)}">${rowCell(row,key)}</td>`).join('')}</tr>`).join('');
    $('#ct-empty-results').hidden=rows.length!==0||!!loadError;
    const searched=!!tableState.query.trim(),masked=base.length-scoped.length,unevaluated=Math.max(0,universe-intrinsicRows.length);
    $('#ct-strategy-count').textContent=loadError?'':`${num0(intrinsicRows.length)} titres évalués · ${num0(unevaluated)} non évaluables (données insuffisantes) · ${num0(counts.excluded)} exclus par la stratégie · ${counts.undetermined?num0(counts.undetermined)+' indéterminés (données manquantes) · ':''}${num0(masked)} masqués par vos filtres · ${num0(filtered.length)} affichés${searched?` (recherche : ${num0(base.length)} correspondances)`:''}. Critères et filtres n’agissent que sur l’affichage : notes et rangs ne changent pas.${scoreLabel?` Stratégie : ${scoreLabel}.`:''}`;
    $('#ct-masked-count').textContent=`${num0(masked)} titre${masked>1?'s':''} masqué${masked>1?'s':''}`;
    $('#ct-masked-count').classList.toggle('has-hidden',masked>0);
    document.querySelectorAll('#ct-verdict [data-verdict]').forEach(b=>{const k=b.dataset.verdict;b.setAttribute('aria-checked',String(k===tableState.verdict));b.querySelector('b').textContent=num0(counts[k]);});
    const und=$('#ct-undetermined');if(und){und.hidden=!counts.undetermined||tableState.verdict==='all';und.textContent=`${num0(counts.undetermined)} titre${counts.undetermined>1?'s':''} indéterminé${counts.undetermined>1?'s':''} (données manquantes) : visible${counts.undetermined>1?'s':''} dans « Toutes ».`;}
    $('#ct-page-range').textContent=loadError?loadError:rows.length?`Affichage de ${start+1} à ${Math.min(start+tableState.pageSize,rows.length)} sur ${rows.length} titres`:'Aucun titre visible';
    $('#ct-pages').innerHTML=`<button type="button" data-demo-page="${tableState.page-1}" ${tableState.page===1?'disabled':''} aria-label="Page précédente">‹</button>${Array.from({length:Math.min(pages,9)},(_,i)=>{const n=pages<=9?i+1:Math.min(Math.max(1,tableState.page-4),pages-8)+i;return `<button type="button" data-demo-page="${n}" ${tableState.page===n?'aria-current="page"':''} aria-label="Page ${n}">${n}</button>`;}).join('')}<button type="button" data-demo-page="${tableState.page+1}" ${tableState.page===pages?'disabled':''} aria-label="Page suivante">›</button>`;
    $('#ct-sort').value=tableState.sort;$('#ct-page-size').value=String(tableState.pageSize);
    $('#ct-sort-direction').textContent=tableState.direction==='desc'?'↓':'↑';$('#ct-sort-direction').setAttribute('aria-label',`Passer au tri ${tableState.direction==='desc'?'croissant':'décroissant'}`);
  }
  function sortBy(key){tableState.userSorted=true;tableState.direction=tableState.sort===key?(tableState.direction==='desc'?'asc':'desc'):(key==='name'||key==='market'||key==='sector'?'asc':'desc');tableState.sort=key;tableState.page=1;renderRanking();}
  function render() {
    renderStrategies();
    document.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.mode===state.mode));
    $('#ct-simple').hidden=state.mode!=='simple';$('#ct-expert').hidden=state.mode!=='expert';
    renderSimple();renderExpert();renderFilters();renderColumns();
  }
  $('#ct-page').addEventListener('click',e=>{
    const b=e.target.closest('button');if(!b)return;
    if(b.dataset.demoPage!==undefined){tableState.page=Number(b.dataset.demoPage);renderRanking();}
    else if(b.dataset.sortColumn)sortBy(b.dataset.sortColumn);
    else if(b.dataset.openFilter){const k=b.dataset.openFilter,was=activeFilter;closeFilter();if(was!==k){activeFilter=k;$(`#ct-list-${k}`).hidden=false;$(`[data-open-filter="${k}"]`).setAttribute('aria-expanded','true');$(`#ct-list-${k} input[type=search]`).value='';searchCategories(k,'');if(!matchMedia('(max-width:700px)').matches&&!matchMedia('(pointer:coarse)').matches)$(`#ct-list-${k} input[type=search]`).focus();positionFilter(k);}}
    else if(b.dataset.closeFilter)closeFilter(true);
    else if(b.dataset.allIndicator){tableState.page=1;const k=b.dataset.allIndicator;state.filters[k]=categories[k].options.map(o=>o.id);saveLocalSelection(k);$(`#ct-list-${k}`).querySelectorAll('input[type=checkbox]').forEach(el=>el.checked=true);filterSummary();}
    else if(b.dataset.mode){closeFilter();state.mode=b.dataset.mode;project();render();}
    else if(b.dataset.period){state.selected=b.dataset.period;renderSimple();}
    else if(b.dataset.step){const f=b.dataset.step,p=config().periods[state.selected];setSimpleValue(f,Number(Math.max(f==='slope'?.01:0,Math.min(f==='slope'?2:1,p[f]+Number(b.dataset.delta))).toFixed(3)));renderSimple();}
    else if(b.dataset.addNode!==undefined){at(b.dataset.addNode).children.push(rule('volatility',state.selected,2,'<='));renderExpert();}
    else if(b.dataset.addGroup!==undefined){at(b.dataset.addGroup).children.push(group([rule('volatility',state.selected,2,'<='),rule('drawdown',state.selected,15,'<=')]));renderExpert();}
    else if(b.dataset.removeNode!==undefined){const path=b.dataset.removeNode.split('.'),i=Number(path.pop());at(path.join('.')).children.splice(i,1);project();renderExpert();}
    else if(b.dataset.action==='reset') $('#ct-reset').click();
    else if(b.dataset.action==='save') $('#ct-save').click();
  });
  $('#ct-page').addEventListener('input',e=>{
    const el=e.target;
    if(el.dataset.categorySearch){filterQuery=el.value;searchCategories(el.dataset.categorySearch,el.value);}
    if(el.dataset.simple){const f=el.dataset.simple,p=config().periods[state.selected];setSimpleValue(f,number(el.value,0,f==='slope'?2:1,p[f]));$(`#ct-${el.type==='range'?'value':'range'}-${f}`).value=p[f];chart();preview();}
    if(el.dataset.ruleField==='value'){const r=at(el.closest('[data-path]').dataset.path);r.value=number(el.value,-1e12,1e12,r.value);project();preview();}
  });
  $('#ct-page').addEventListener('change',e=>{
    const el=e.target;
    if(el.dataset.simple) el.value=config().periods[state.selected][el.dataset.simple];
    if(el.dataset.enabled){activatePeriod(el.dataset.enabled,el.checked);renderSimple();renderExpert();}
    if(el.dataset.filter){tableState.page=1;const list=state.filters[el.dataset.filter],id=el.dataset.category;state.filters[el.dataset.filter]=el.checked?[...new Set([...list,id])]:list.filter(v=>v!==id);saveLocalSelection(el.dataset.filter);filterSummary();}
    if(el.dataset.column!==undefined){const n=Number(el.dataset.column);state.columns=el.checked?[...new Set([...state.columns,n])]:state.columns.filter(v=>v!==n);renderColumns();}
    if(el.dataset.ruleField){const r=at(el.closest('[data-path]').dataset.path),f=el.dataset.ruleField;r[f]=f==='value'?number(el.value,-1e12,1e12,r.value):el.value;if(f==='value')el.value=r.value;project();preview();}
    if(el.dataset.groupJoin!==undefined){at(el.dataset.groupJoin).join=el.value;project();preview();}
  });
  $('#ct-strategy').onchange=e=>switchTo(e.target.value);
  for(const t of ['input','change','click'])$('#ct-page').addEventListener(t,e=>{if(e.target.id!=='ct-strategy')queueMicrotask(renderStrategies);});
  $('#ct-tab-rules').onclick=()=>$('#ct-rules').scrollIntoView({behavior:'smooth',block:'nearest'});
  $('#ct-tab-manage').onclick=()=>{$('#ct-filter-panel').open=true;$('#ct-filter-panel').scrollIntoView({behavior:'smooth',block:'start'});};
  $('#ct-tab-queries').onclick=()=>{
    const has=localStorage.getItem(key)!==null;
    J.dialog({title:'Requêtes locales de test',body:`<p>${has?'Un état de recherche est enregistré sur cet appareil.':'Aucune recherche enregistrée sur cet appareil.'}</p><p>Chaque stratégie, avec ses règles et ses choix de filtres, est enregistrée dans votre compte avec « Enregistrer la stratégie ».</p>`,actions:[{label:'Fermer',run:()=>{}},...(has?[{label:'Recharger la sauvegarde',run:()=>location.reload()}]:[])]});
  };
  document.addEventListener('click',e=>{if(activeFilter&&!e.target.closest('.ct-multi'))closeFilter();});
  window.addEventListener('resize',()=>closeFilter());
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&activeFilter){e.preventDefault();closeFilter(true);}});
  $('#ct-filter-panel').addEventListener('toggle',()=>{if(!$('#ct-filter-panel').open)closeFilter();});
  for(const id of ['ct-all-filters','ct-none-filters','ct-reset-filters']) $('#'+id).onclick=e=>{e.preventDefault();e.stopPropagation();tableState.page=1;
    if(id==='ct-reset-filters'){overrides={};state.filters=secondary.defaults(categoryPayload,categories);saveLocalSelection();}
    else if(id==='ct-all-filters'){state.filters=secondary.all(categories);for(const k of Object.keys(categories))saveLocalSelection(k);}
    else{state.filters=Object.fromEntries(Object.keys(categories).map(k=>[k,[]]));for(const k of Object.keys(categories))saveLocalSelection(k);}
    renderFilters();};
  document.querySelectorAll('#ct-verdict [data-verdict]').forEach(b=>b.onclick=()=>{tableState.verdict=b.dataset.verdict;tableState.page=1;renderRanking();});
  $('#ct-reset').onclick=()=>guarded(async()=>{
    const id=state.strategy,builtin=!!builtinNames[id];
    if(!await J.confirm(builtin?'Restaurer les valeurs par défaut':'Annuler les modifications',builtin?`« ${names[id]} » reprendra ses valeurs d’origine (périodes, seuils, règles et filtres). Les autres stratégies ne changent pas.`:`« ${names[id]} » reviendra à sa dernière version enregistrée.`,builtin?'Restaurer':'Annuler les modifications'))return;
    if(builtin){
      if(serverOk)takeView(await post({action:'restore',id}));
      state.profiles[id]=fresh(id);overrides={};ovBy[id]=overrides;
    }else{state.profiles[id]=cloneJSON(saved[id].p);overrides=cloneJSON(saved[id].o);ovBy[id]=overrides;}
    state.filters=filtersFor(overrides);tree();project();markSaved(id);state.selected=periods.find(([k])=>config().periods[k].enabled)?.[0]||'week';render();
    feedback(builtin?'Valeurs par défaut restaurées.':'Modifications annulées.');
  });
  $('#ct-save').onclick=()=>guarded(async()=>{
    const id=state.strategy;takeView(await post({action:'save',id,...currentPayload()}));markSaved(id);
    try{localStorage.setItem(key,JSON.stringify({mode:state.mode,cols:state.columns}));}catch(_){/* préférences d'affichage seulement */}
    feedback(`Stratégie « ${names[id]} » enregistrée.`);
  });
  $('#ct-duplicate').onclick=()=>guarded(async()=>{
    const from=state.strategy,wasDirty=isDirty(from),name=await askName('Enregistrer sous un nouveau nom',uniqueCopyName(names[from]),'Enregistrer');if(!name)return;
    const payload=currentPayload(),view=await post({action:'create',name,...payload}),nid=view.selected;takeView(view);
    state.profiles[nid]=cloneJSON(payload.config);ovBy[nid]=cloneJSON(payload.filters);markSaved(nid);
    /* l'original retrouve sa dernière version enregistrée : les modifications vivent désormais dans la nouvelle stratégie */
    state.profiles[from]=cloneJSON(saved[from].p);overrides=cloneJSON(saved[from].o);
    switchTo(nid,false);
    feedback(wasDirty?`« ${name} » enregistrée avec vos modifications ; « ${names[from]} » est inchangée.`:`« ${name} » créée à partir de « ${names[from]} ».`);
  });
  $('#ct-rename').onclick=()=>guarded(async()=>{
    const id=state.strategy,name=await askName('Renommer la stratégie',names[id],'Renommer');if(!name)return;
    takeView(await post({action:'rename',id,name}));feedback(`Stratégie renommée « ${names[id]} ».`);
  });
  $('#ct-delete').onclick=()=>guarded(async()=>{
    const id=state.strategy;if(!await J.confirm('Supprimer la stratégie',`« ${names[id]} » sera supprimée définitivement. Les autres stratégies ne changent pas.`,'Supprimer'))return;
    const label=names[id];takeView(await post({action:'delete',id}));delete state.profiles[id];delete ovBy[id];delete saved[id];
    const nxt=enabledIds().filter(x=>x!==id)[0]||'fast';overrides=ovBy[nxt];state.strategy=nxt;switchTo(nxt);feedback(`Stratégie « ${label} » supprimée.`);
  });
  $('#ct-search').value=tableState.query;$('#ct-search').oninput=e=>{tableState.query=e.target.value;tableState.page=1;renderRanking();};
  $('#ct-sort').onchange=e=>{tableState.userSorted=true;tableState.sort=e.target.value;tableState.direction=['name','market','sector'].includes(e.target.value)?'asc':'desc';tableState.page=1;renderRanking();};
  $('#ct-sort-direction').onclick=()=>{tableState.direction=tableState.direction==='desc'?'asc':'desc';tableState.page=1;renderRanking();};
  $('#ct-page-size').onchange=e=>{tableState.pageSize=Number(e.target.value);tableState.page=1;renderRanking();};
  $('#ct-show-demo-all').onclick=()=>{tableState.verdict='all';tableState.query='';const q=$('#ct-search');if(q)q.value='';tableState.page=1;state.filters=secondary.all(categories);for(const k of Object.keys(categories))saveLocalSelection(k);renderFilters();};
  $('#ct-apply').onclick=()=>feedback('Réglages conservés. Le tableau présente des données fictives, indépendantes de la stratégie.');
  // Critères en cours de modification : le serveur recalcule les statuts avec le même moteur (aucune évaluation locale) ; scores et rangs ne bougent pas.
  let verdictSeq=0,verdictTimer=null,appliedSpec=null;
  const specNow=()=>{tree();project();return cloneJSON(config());};
  function scheduleVerdicts(){clearTimeout(verdictTimer);if(JSON.stringify(specNow())===appliedSpec)return;verdictTimer=setTimeout(refreshVerdicts,250);}
  async function refreshVerdicts(){
    const my=++verdictSeq,want=state.strategy,spec=specNow(),json=JSON.stringify(spec);
    try{const d=await J.post('ranking/verdicts',{strategy:want,config:spec});if(my!==verdictSeq||want!==state.strategy)return;for(const r of intrinsicRows)r.status=d.status[r.id]||'undetermined';appliedSpec=json;renderRanking();}
    catch(e){if(my===verdictSeq)feedback('Statuts de stratégie non actualisés : '+(e.message||'erreur'));}
  }
  let loadSeq=0;
  async function loadRows(){
    const my=++loadSeq,want=state.strategy;loading=true;
    $('#ct-table-body').innerHTML='<tr class="ct-loading"><td colspan="20"><span class="spinner"></span> Chargement des titres…</td></tr>';
    try{const data=await J.api('ranking/table',{params:{strategy:want}});if(my!==loadSeq)return;intrinsicRows=data.rows.map(toRow);universe=data.universe||intrinsicRows.length;defaultSort=data.default_sort==='complex'?'complex':'simple';if(!tableState.userSorted){tableState.sort=defaultSort;tableState.direction='desc';}loadError=null;scoreLabel=data.label||'';appliedSpec=null;loading=false;}
    catch(e){if(my!==loadSeq)return;intrinsicRows=[];loadError='Classement indisponible : '+(e.message||'erreur de chargement');loading=false;}
    renderRanking();scheduleVerdicts();                                   // lignes chargées avec les réglages ENREGISTRÉS : si la page affiche un brouillon, les statuts suivent le brouillon
  }
  tree();project();render();loadRows();
})().catch(error=>{const p=document.querySelector('#ct-feedback');p.textContent='Impossible d’ouvrir la page de test : '+error.message;});

// Bloc « Stratégie » : réglages repliés par défaut (Afficher / Masquer), choix mémorisé dans ce navigateur.
(function(){
  const panel=document.querySelector('.ct-panel[aria-label="Stratégie et critères"]'),head=panel&&panel.querySelector('.ct-strategy');
  if(!head||head.querySelector('.ct-fold'))return;
  let open=false;                                   // toujours masqués à l'ouverture de la page
  const b=document.createElement('button');b.type='button';b.className='btn small ct-fold';b.setAttribute('aria-controls','ct-simple ct-expert');
  const apply=()=>{panel.classList.toggle('ct-collapsed',!open);b.setAttribute('aria-expanded',String(open));b.textContent=open?'Masquer les réglages':'Afficher les réglages';};
  b.onclick=()=>{open=!open;apply();};
  (head.querySelector('.ct-strategy-tools')||head).appendChild(b);apply();
})();
