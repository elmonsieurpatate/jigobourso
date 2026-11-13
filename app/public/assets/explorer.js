/* Classement : titres réels notés par le moteur V4 ; la stratégie et les filtres choisis ici ne modifient jamais les scores. */
(async () => {
  'use strict';
  const user = await J.init('explorer'); if (!user) return;
  const $ = J.$, esc = J.esc, M = ExplorerModel, V = ExplorerView;
  const { periods, metrics, builtinNames, SESS, cloneJSON, withDay, isPrimary, rule, group, number } = M;
  // Critères de RECHERCHE de chaque stratégie intégrée : lus dans le moteur (scores_admin.V4_STRATEGIES via ranking/criteria), jamais recopiés ici.
  // Ils filtrent l'affichage ; ils n'entrent ni dans les notes ni dans les rangs. Une stratégie sans critère (Momentum) a des seuils à 0 = aucun critère.
  let crit={};try{crit=(await J.api('ranking/criteria')).criteria||{};}catch(_){/* périodes actives seules si le moteur ne répond pas */}
  const profiles=M.profilesFrom(crit);
  const secondary=window.ClassementTestSecondary;
  const categoryPayload=window.ClassementTestCategoryConfig || await J.api('explorer/secondary-filters');
  const categories=secondary.normalize(categoryPayload);
  let serverView=null;try{serverView=await J.api('classement-test/strategies');}catch(_){/* page utilisable, enregistrement serveur indisponible */}
  const filters=Object.fromEntries(Object.entries(categories).map(([k,c])=>[k,[c.label,c.options]]));
  const key = 'jigo_classement_test_v1';
  const fresh=id=>M.fresh(profiles,id);
  let state = { mode:'simple',strategy:'fast',selected:'week',profiles:Object.fromEntries(Object.keys(profiles).map(id=>[id,fresh(id)])),filters:secondary.all(categories) };
  // Seules les sauvegardes explicites de cette page sont relues. Les préférences Explorer restent séparées.
  try {
    const saved = J.store.get(key);
    if (saved && saved.profiles && typeof saved.profiles==='object') for (const id of Object.keys(profiles)) if (!saved.profiles[id]) saved.profiles[id]=fresh(id); else withDay(saved.profiles[id]);     // stratégies ajoutées depuis la sauvegarde
    if (M.isValidSaved(saved,profiles)) state=saved;
  } catch (_) { /* Stockage absent ou ancien : valeurs de démonstration. */ }
  const adminSelections=secondary.defaults(categoryPayload,categories);
  const userKey=String(user.id??'offline');
  let rawLocal={};try{rawLocal=(J.store.get(key,{})||{});}catch(_){}
  const byUser=rawLocal.secondaryOverridesByUser||{};
  let overrides=Object.fromEntries(Object.entries(byUser[userKey]||{}).filter(([,v])=>v&&Array.isArray(v.selected)&&Array.isArray(v.known)));
  const metadataMigration=secondary.migrateOverrides(categoryPayload,overrides);
  overrides=metadataMigration.overrides;
  if(Object.keys(metadataMigration.previous).length){
    const previous=rawLocal.secondaryMetadataPreviousByUser||{};
    rawLocal.secondaryMetadataPreviousByUser={...previous,[userKey]:{...(previous[userKey]||{}),...metadataMigration.previous}};
    rawLocal.secondaryOverridesByUser={...byUser,[userKey]:overrides};
    try{J.store.set(key,rawLocal);}catch(_){/* Current session still uses the migrated preferences. */}
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
  const filtersFor=o=>M.filtersFor(o,categories,adminSelections);
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
  // Colonnes : identifiants et libellés viennent du catalogue de l'administration (app/config/table_columns.json) ; ici, seulement la valeur de tri et le rendu de chaque identifiant.
  const REG=M.registry(()=>rankKey());
  const LEGACY_LABELS={rank:'Rang',name:'Titre',status:'Statut stratégie',market:'Place',sector:'Secteur',price:'Cours',change:'Var. 1J (%)',last_close:'Dernière clôture',slope:'Pente · mois',r2:'R² · mois',volatility:'Volatilité',turnover:'Liquidité',avgVolume:'Volume',drawdown:'Recul max.',perfMonth:'Perf. 1 mois',simple:'Score simple',complex:'Score complexe',trend:'Tendance'};
  const LEGACY_HINTS={change:'Variation du cours entre les deux dernières séances clôturées.'};
  const LEGACY_VISIBLE=()=>Object.keys(REG).map(id=>[id,(window.matchMedia('(max-width:700px)').matches?['rank','name','status','price','change','slope','simple','complex']:['rank','name','status','price','change','slope','r2','volatility','turnover','simple','complex','trend']).includes(id)]);
  const tl=await TableLayout.load();
  let layout=TableLayout.get(tl,'explorer',TableLayout.device(),LEGACY_VISIBLE());
  const catalogOf=()=>layout.catalog||Object.keys(REG).map(id=>({id,label:LEGACY_LABELS[id]||id,sortable:!REG[id].nosort}));
  const labelOf=id=>(catalogOf().find(c=>c.id===id)||{}).label||LEGACY_LABELS[id]||id;
  const hintOf=id=>(catalogOf().find(c=>c.id===id)||{}).hint||LEGACY_HINTS[id]||'';
  // Préférences personnelles de visibilité (sélecteur « Colonnes ») : valables tant que l'administrateur n'a pas modifié cette configuration.
  const visKey='jigo_ct_vis_v5';
  const personal=()=>{try{const v=J.store.get(visKey);return v&&v.rev===layout.revision&&v.dev===TableLayout.device()?v.vis:{};}catch(_){return {};}};
  let vis=personal();
  const shownColumns=()=>layout.columns.filter(c=>REG[c.id]&&(c.id==='name'||(c.id in vis?vis[c.id]:c.visible)));
  let intrinsicRows=[],loadError=null,scoreLabel='',loading=false,universe=0,defaultSort='complex';
  // Priorité : adresse (?verdict=, ?sort=colonne:sens, ?page_size=) > choix de l'utilisateur pendant la consultation > valeurs initiales de l'administration (Colonnes).
  const urlq=new URLSearchParams(location.search),urlSort=(urlq.get('sort')||'').split(':'),validSort=k=>REG[k]&&!REG[k].nosort;
  const urlSorts=validSort(urlSort[0])?[{key:urlSort[0],dir:urlSort[1]==='asc'?'asc':'desc'}]:null;
  const tableState={sorts:urlSorts||[{key:'simple',dir:'desc'}],page:1,pageSize:[25,50,100].includes(+urlq.get('page_size'))?+urlq.get('page_size'):layout.filters.page_size||50,userSorted:!!urlSorts,
    verdict:['retained','excluded','all'].includes(urlq.get('verdict'))?urlq.get('verdict'):layout.filters.verdict||'retained',query:urlq.get('q')||''};
  const sortKey=()=>tableState.sorts[0].key,sortDir=()=>tableState.sorts[0].dir;
  const configuredSorts=()=>layout.sort&&layout.sort.length?layout.sort.filter(x=>validSort(x.key)).map(x=>({...x})):[];
  const applyDefaultSort=()=>{if(tableState.userSorted)return;const c=configuredSorts();tableState.sorts=c.length?c:[{key:defaultSort,dir:'desc'}];};
  let activeFilter=null, filterQuery='';
  const config = () => state.profiles[state.strategy];
  const tree=()=>M.ensureTree(config()),leaves=()=>M.leaves(tree()),at=path=>M.at(tree(),path);
  const project=()=>M.project(config()),simpleCompatible=()=>M.simpleCompatible(config());
  const setSimpleValue=(metric,value)=>M.setSimpleValue(config(),state.selected,metric,value),activatePeriod=(k,enabled)=>M.activatePeriod(config(),k,enabled);

  // ───── Stratégies enregistrées (MariaDB) : une configuration et des choix de filtres propres à chacune ─────
  const names={...builtinNames},ovBy={},saved={};
  let customIds=[],rev=serverView?serverView.revision:0,busy=false,meta=cloneJSON(serverView?.meta||{});
  const metaOf=id=>({icon:'trending-up',description:'',enabled:true,...(meta[id]||{})});
  const serverOk=!!serverView;
  const order=()=>[...Object.keys(builtinNames),...customIds];
  const seed=cloneJSON(overrides);
  for(const id of Object.keys(builtinNames)){if(serverOk)state.profiles[id]=fresh(id);ovBy[id]=cloneJSON(seed);}
  for(const it of serverView?.items||[]){names[it.id]=it.name;state.profiles[it.id]=withDay(cloneJSON(it.config));ovBy[it.id]=cloneJSON(it.filters||{});if(!it.builtin)customIds.push(it.id);}
  const enabledIds=()=>order().filter(id=>metaOf(id).enabled);
  if(serverOk&&enabledIds().includes(serverView.selected))state.strategy=serverView.selected;else if(serverOk&&enabledIds().length)state.strategy=enabledIds()[0];
  {const want=new URLSearchParams(location.search).get('strategy');if(serverOk&&want&&enabledIds().includes(want))state.strategy=want;}
  for(const id of order()){const s=state.strategy;state.strategy=id;tree();state.strategy=s;saved[id]={p:cloneJSON(state.profiles[id]),o:cloneJSON(ovBy[id])};}
  try{const l=(J.store.get(key,{})||{});if(['simple','expert'].includes(l.mode))state.mode=l.mode;}catch(_){/* préférences d'affichage facultatives */}
  overrides=ovBy[state.strategy];state.filters=filtersFor(overrides);
  state.selected=periods.find(([k])=>config().periods[k].enabled)?.[0]||state.selected;
  let applied=null;
  const isDirty=id=>JSON.stringify([state.profiles[id],id===state.strategy?overrides:ovBy[id]])!==JSON.stringify([saved[id].p,saved[id].o]);
  const anyDirty=()=>order().some(isDirty);
  function renderStrategies(){
    const sel=$('#ct-strategy');
    const html=order().filter(id=>metaOf(id).enabled||id===state.strategy).map(id=>`<option value="${esc(id)}">${esc(names[id])}${isDirty(id)?' •':''}</option>`).join('');
    if(sel.dataset.html!==html){sel.innerHTML=html;sel.dataset.html=html;}      // ne jamais reconstruire le menu à chaque clic : il se refermerait (iPhone)
    const d=$('#ct-strategy-desc'),txt=metaOf(state.strategy).description,lnk=builtinNames[state.strategy]?state.strategy:'personnelles';d.hidden=!txt;if(d.dataset.k!==txt+'|'+lnk){d.dataset.k=txt+'|'+lnk;d.innerHTML='';const t=document.createElement('span');t.textContent=txt;const a=document.createElement('a');a.href='aide.html#strategie-'+lnk;a.textContent='Comprendre cette stratégie';d.append(t,a);}
    if(sel.value!==state.strategy)sel.value=state.strategy;
    const builtin=!!builtinNames[state.strategy];
    $('#ct-rename').hidden=builtin;$('#ct-delete').hidden=builtin;
    $('#ct-reset').textContent=builtin?'Restaurer les valeurs par défaut':'Annuler les modifications';
    $('#ct-strategy-state').textContent=!serverOk?'Enregistrement indisponible':isDirty(state.strategy)?'Modifications non enregistrées':'Enregistrée';
    $('#ct-save').disabled=!serverOk;$('#ct-duplicate').disabled=!serverOk;
    drawPicker();
    updateSearchStatus();
  }
  // Statuts Officielle / Adaptée / Personnelle (serveur) : sélecteur groupé à badges, bandeau et fenêtre d'information. Reconstruits seulement si leur contenu change.
  let suiList=null,suiKey='';
  function loadStatus(){return J.api('strategies/status').then(r=>{suiList=r.strategies;suiKey='';drawPicker();}).catch(()=>{suiList=null;});}
  function drawPicker(){
    if(!suiList||!window.SUI)return;
    const on=new Set(enabledIds().concat([state.strategy])),list=suiList.filter(s=>on.has(s.id));
    const key=JSON.stringify([list,state.strategy,meta]);if(key===suiKey)return;suiKey=key;SUI.setMeta(meta);
    SUI.picker($('#ct-strategy'),list,state.strategy);
    const cur=list.find(s=>s.id===state.strategy);
    $('#ct-strategy-banner').innerHTML=SUI.banner(cur);
  }
  const post=body=>J.post('classement-test/strategies/save',{revision:rev,...body}).then(v=>{loadStatus();return v;});
  function takeView(view){rev=view.revision;meta=cloneJSON(view.meta||{});for(const it of view.items)names[it.id]=it.name;customIds=view.items.filter(i=>!i.builtin).map(i=>i.id);}
  function switchTo(id,remember=true){
    closeFilter();ovBy[state.strategy]=overrides;state.strategy=id;overrides=ovBy[id]||(ovBy[id]={});state.filters=filtersFor(overrides);
    tableState.page=1;applyDefaultSort();tree();project();state.selected=periods.find(([k])=>config().periods[k].enabled)?.[0]||'week';render();
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
  const fmt = n => J.num(n,2,3);
  let timer;
  function feedback(text) { $('#ct-feedback').textContent=text; clearTimeout(timer); timer=setTimeout(()=>$('#ct-feedback').textContent='',5500); }
  function chart() { $('#ct-chart').innerHTML=V.chartSvg(config().periods[state.selected],state.selected); }
  function preview() {
    const active=periods.filter(([k])=>config().periods[k].enabled);
    $('#ct-active-summary').textContent=active.length?`${active.length} périodes actives · ${active.map(([,l])=>l).join(' + ')}`:'Aucune période active · configuration libre';
    $('#ct-preview').innerHTML=V.previewHtml(tree());
    updateSearchStatus();
    const valid=M.isTreeValid(tree());
    const badge=$('.ct-valid');badge.textContent=valid?'✓ Filtre valide':'⚠ Filtre à compléter';badge.classList.toggle('invalid',!valid);

    const advanced=leaves().filter(x=>!isPrimary(x.node)).length, compatible=simpleCompatible();
    $('#ct-extra-note').hidden=!advanced&&compatible;
    $('#ct-extra-note').textContent=compatible?`${advanced} critère(s) avancé(s) conservé(s). Consultez le mode Expert pour les modifier.`:'Règles avancées conservées : cette combinaison ne peut pas être représentée fidèlement par deux minimums. Modifiez-la en mode Expert ; les curseurs simples sont verrouillés.';
  }
  function renderSimple() {
    $('#ct-periods').innerHTML=V.periodsHtml(config(),state.selected);
    const p=config().periods[state.selected];
    $('#ct-sliders').innerHTML=V.slidersHtml(p,state.selected);
    const compatible=simpleCompatible();
    $('#ct-simple').querySelectorAll('input,button[data-step]').forEach(el=>el.disabled=!compatible);
    chart();preview();
  }
  function renderExpert() {
    $('#ct-rules').innerHTML=V.rulesHtml(tree());
    preview();
  }
  function renderFilters() {
    $('#ct-filter-source').textContent=(categoryPayload.source_label||'Catégories administrateur')+' · bornes en lecture seule'+(Object.keys(state.secondaryMetadataPreviousByUser[userKey]||{}).length?' · anciennes préférences regroupées : vérifiez vos sélections':'');
    const manage=document.createElement('a');manage.href='mes-filtres.html';manage.textContent='Configurer mes filtres';$('#ct-filter-source').append(' · ',manage);
    if(categoryPayload.schema===2)document.querySelector('.ct-filter-logic').textContent='Un filtre retient un titre si l’une de ses catégories est cochée ; les filtres se combinent. Les scores et les rangs ne changent jamais.';
    $('#ct-filters').innerHTML=V.filtersHtml(categories,categoryPayload.schema,state.filters,activeFilter,filterQuery);
    filterSummary();
    if(activeFilter) searchCategories(activeFilter,filterQuery);
  }
  function isPrimaryKey(k){return V.isPrimaryFilter(categoryPayload.schema,k,categories[k]||{});}
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
    const popup=$(`#ct-list-${key}`),needle=J.fold(query.trim());let shown=0;
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
  const MEASURE={volatility:'volatility',turnover:'turnover_eur',avgVolume:'avg_volume',drawdown:'drawdown',perfMonth:'perf-month',simple:'score_simple_v4',complex:'score_complex_v4'};
  const eur=n=>J.eur(n,n>=1000?0:2);
    const percent=(n,sign=false)=>J.pct(n,2,sign);
  const num0=J.int;
  const score1=n=>J.num(n,1);
  // Catégories de l'administration : la couleur d'un chiffre est celle de la catégorie du filtre correspondant.
  const defs=(categoryPayload.definitions&&categoryPayload.definitions.filters)||[];
  const {categoryOf,rowOptions}=M.categories(defs);
  const tinted=(measureId,value,text)=>{const c=categoryOf(measureId,value);return c&&c.color?`<span class="ct-cat" data-style="--cat:${esc(c.color)}" title="${esc(c.name)}">${text}</span>`:text;};
  // La fiche s'ouvre dans une autre fenêtre : elle reçoit l'identifiant de la stratégie et, si les réglages ne sont pas enregistrés, un brouillon sous une clé de contexte (localStorage, même origine).
  // Brouillon introuvable côté fiche ⇒ elle l'indique et ne rend aucun verdict : jamais de remplacement silencieux par d'autres réglages.
  const ctxKey=M.ctxKey;
  function sheetHref(id){
    const context=applied||{strategy:state.strategy,config:specNow()};
    let q='titre.html?src=explorer&id='+encodeURIComponent(id)+'&ct='+encodeURIComponent(context.strategy);
    if(context.config){
      const json=JSON.stringify({id:context.strategy,spec:context.config}),k=ctxKey(json);
      try{J.store.text.set('jigo_ct_ctx:'+k,json);}catch(_){/* la fiche signalera un contexte introuvable */}
      q+='&ctx='+k;
    }
    return q;
  }
  const toRow=M.toRow;
  function applySecondary(rows){
    const filters=applied?applied.filters:state.filters;
    if(categoryPayload.schema!==2)return secondary.apply(rows,filters,categories);
    const active=Object.entries(categories).filter(([k,c])=>filters[k]&&filters[k].length!==c.options.length);
    if(!active.length)return [...rows];
    return rows.filter(row=>active.every(([k])=>rowOptions(row,k).some(id=>filters[k].includes(id))));
  }
  // Aucune admission : tous les titres évalués sont classés. Seuls les filtres secondaires masquent des lignes (affichage), sans toucher aux scores ni aux rangs.
  // Critères de recherche de la stratégie (pente / R² du mode Simple, règles du mode Expert) : ils servent à RECHERCHER les titres du profil. Ils ne modifient jamais une note ni un rang :
  // l'univers noté reste complet, un titre hors critères reste noté et classé (« Ignorer les critères » l'affiche). Un seuil à 0 est sans effet.
  // Statut de stratégie (retenue / exclue / indéterminée) : calculé par le serveur (moteur unique `criteria`, le même que l'administration et la fiche), jamais ici.
  // Il ne change ni note ni rang. Une donnée manquante donne « indéterminée », jamais « exclue » ; « Toutes » les montre toutes.
  const statusBadge=V.statusBadge;
  // base = titres notés (recherche texte comprise) ; scoped = base moins les filtres secondaires (c'est le périmètre des compteurs) ; rows = scoped selon Retenues / Exclues / Toutes.
  function visibleRows(){
    const needle=J.fold(tableState.query.trim());
    const base=needle?intrinsicRows.filter(r=>J.fold(r.symbol+' '+r.name+' '+(r.isin||'')).includes(needle)):intrinsicRows;
    const scoped=applySecondary(base);
    const counts={retained:0,excluded:0,undetermined:0,all:scoped.length};
    for(const r of scoped)counts[r.status in counts?r.status:'undetermined']++;
    const rows=tableState.verdict==='all'?scoped:scoped.filter(r=>r.status===tableState.verdict);
    return {base,scoped,counts,rows};
  }
  const spark=V.spark;
  const sectorLabel=row=>{const f=defs.find(x=>x.id==='sector'),g=(categoryPayload.defaults&&null)||null;const v=f&&(f.values||[]).find(x=>x.id===(row.group&&row.group.sector));return v?v.label:null;};
  function rowCell(row,key){
    if(key==='rank')return rankCell(row);
    if(key==='status')return statusBadge(row);
    if(key==='kind')return row.kind==='etf'?'ETF':'Action';
    if(key==='rank_simple'||key==='rank_complex'){const w=key==='rank_simple'?'Simple':'Complex',r=row['rank'+w],t=row['tie'+w];return r==null?'—':t>1?`<span title="Ex æquo : ${t} titres ont exactement ce score">=${r}</span>`:String(r);}
    {const m=/^(perf|slope|r2)_(week|quarter|half|year)$/.exec(key);if(m){const [,f,k]=m,v=f==='perf'?(row.perf||{})[k]:(row.periods[SESS[k]]||{})[f];
      return v==null?'—':f==='r2'?fmt(v):`<span class="${v>0?'up':v<0?'down':''}">${percent(v,true)}</span>`;}}
    if(key==='name')return `<a class="ct-company" href="${esc(sheetHref(row.id))}" target="_blank" rel="noopener" aria-label="Ouvrir la fiche de ${esc(row.symbol)} dans un nouvel onglet"><span class="ct-company-mark" data-style="--mark:${row.color}" aria-hidden="true">${esc(row.symbol.slice(0,2))}</span><span class="ct-company-text"><b>${esc(row.symbol)}${row.kind==='etf'?' <i class="ct-kind">ETF</i>':''}${row.held?' <i class="ct-kind held">détenu</i>':''}</b><span>${esc(row.name)}</span>${row.category?`<span class="ct-sub ct-sector">${esc(row.category)}</span>`:''}</span></a>`;
    if(key==='market')return `<b>${esc(row.mic)}</b><span class="ct-sub">${esc(row.country||'Pays inconnu')} · ${esc(row.currency||'—')}</span>`;
    if(key==='sector'){const g=sectorLabel(row);return row.category?`<b>${esc(row.category)}</b><span class="ct-sub">${esc(g||'')}</span>`:'<span class="ct-missing">Inconnu</span>';}
    if(key==='price')return `${eur(row.price)}${row.currency&&row.currency!=='EUR'&&row.priceNative!==null?`<span class="ct-sub">${esc(J.num(row.priceNative,0,2))} ${esc(row.currency)}</span>`:''}`;
    if(key==='change')return `<span class="${row.change>0?'up':row.change<0?'down':''}">${percent(row.change,true)}</span>`;
    if(key==='last_close')return row.lastClose?esc(J.dayNumeric(row.lastClose)):'—';
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
    const shown=new Set(shownColumns().map(c=>c.id));
    $('#ct-columns').innerHTML=layout.columns.filter(c=>REG[c.id]).map(c=>`<label class="ct-option"><input type="checkbox" data-column="${esc(c.id)}" ${shown.has(c.id)?'checked':''} ${c.id==='name'?'disabled':''}>${esc(labelOf(c.id))}</label>`).join('');
    renderRanking();
  }
  const scoreKeyOf=()=>['complex','rank_complex'].includes(sortKey())?'complex':['simple','rank_simple'].includes(sortKey())?'simple':defaultSort;     // score dont le rang est affiché
  const rankKey=()=>scoreKeyOf()==='simple'?'rankSimple':'rankComplex';
  const posKey=()=>scoreKeyOf()==='simple'?'posSimple':'posComplex';
  const tieKey=()=>scoreKeyOf()==='simple'?'tieSimple':'tieComplex';
  const rankCell=row=>{const r=row[rankKey()];return r==null?'—':row[tieKey()]>1?`<span title="Ex æquo : ${row[tieKey()]} titres ont exactement ce score">=${r}</span>`:String(r);};
  function renderRanking(){
    if(!loading&&!applied&&!loadError){$('#ct-table-body').innerHTML='<tr class="ct-loading"><td colspan="20">Cliquez sur « Appliquer les réglages » pour rechercher des titres.</td></tr>';$('#ct-empty-results').hidden=true;$('#ct-result-count').textContent='';return;}
    if(loading){$('#ct-table-body').innerHTML='<tr class="ct-loading"><td colspan="20"><span class="spinner"></span> Recherche en cours…</td></tr>';$('#ct-empty-results').hidden=true;$('#ct-result-count').textContent='';return;}
    const selected=shownColumns().map(c=>({key:c.id,label:labelOf(c.id),width:c.width}));
    const {base,scoped,counts,rows:filtered}=visibleRows();
    const rows=J.table.sortRows(filtered,tableState.sorts,(r,k)=>REG[k].val(r),(a,b)=>(a[posKey()]??1e9)-(b[posKey()]??1e9)||a.id-b.id);   // jusqu'à trois critères ; égalités : ordre général du classement, puis identifiant (déterministe)
    const pages=Math.max(1,Math.ceil(rows.length/tableState.pageSize));tableState.page=Math.min(Math.max(1,tableState.page),pages);
    const start=(tableState.page-1)*tableState.pageSize,pageRows=rows.slice(start,start+tableState.pageSize);
    if(selected.some(c=>c.key==='trend'))loadPageCurves(pageRows);
    $('#ct-result-count').textContent=loadError?'':`${num0(rows.length)} titre${rows.length>1?'s':''}`+(rows.length!==intrinsicRows.length?` sur ${num0(intrinsicRows.length)} évalués`:'');
    const wstyle=w=>w?` data-style="width:${w}px;min-width:${w}px;max-width:none"`:'';
    const cls=key=>key==='rank'?'ct-rank-cell':key==='name'?'ct-name-heading':'';
    $('#ct-table-head').innerHTML=J.table.headRow(selected.map(({key,label,width})=>({label:esc(label),scope:'col',cls:cls(key),width,title:key==='rank'?`Rang général sur tous les titres notés (${scoreKeyOf()==='simple'?'score simple':'score complexe'}), conservé lors du filtrage et du tri`:hintOf(key)||'',sort:REG[key].nosort?'':key})),{key:sortKey(),dir:sortDir()});
    $('#ct-table-body').innerHTML=pageRows.map(row=>`<tr data-row="${row.id}">${selected.map(({key,label,width})=>`<td class="ct-cell-${esc(key)} ${key==='rank'?'ct-rank-cell':''}" data-label="${esc(label)}"${wstyle(width)}>${rowCell(row,key)}</td>`).join('')}</tr>`).join('');
    $('#ct-empty-results').hidden=rows.length!==0||!!loadError;
    const searched=!!tableState.query.trim(),masked=base.length-scoped.length,unevaluated=Math.max(0,universe-intrinsicRows.length);
    $('#ct-strategy-count').textContent=loadError?'':`${num0(intrinsicRows.length)} titres évalués · ${num0(unevaluated)} non évaluables (données insuffisantes) · ${num0(counts.excluded)} exclus par la stratégie · ${counts.undetermined?num0(counts.undetermined)+' indéterminés (données manquantes) · ':''}${num0(masked)} masqués par vos filtres · ${num0(filtered.length)} affichés${searched?` (recherche : ${num0(base.length)} correspondances)`:''}. Critères et filtres n’agissent que sur l’affichage : notes et rangs ne changent pas.${scoreLabel?` Stratégie : ${scoreLabel}.`:''}`;
    $('#ct-masked-count').textContent=`${num0(masked)} titre${masked>1?'s':''} masqué${masked>1?'s':''}`;
    $('#ct-masked-count').classList.toggle('has-hidden',masked>0);
    document.querySelectorAll('#ct-verdict [data-verdict]').forEach(b=>{const k=b.dataset.verdict;b.setAttribute('aria-checked',String(k===tableState.verdict));b.querySelector('b').textContent=num0(counts[k]);});
    const und=$('#ct-undetermined');if(und){und.hidden=!counts.undetermined||tableState.verdict==='all';und.textContent=`${num0(counts.undetermined)} titre${counts.undetermined>1?'s':''} indéterminé${counts.undetermined>1?'s':''} (données manquantes) : visible${counts.undetermined>1?'s':''} dans « Toutes ».`;}
    $('#ct-page-range').textContent=loadError?loadError:rows.length?`Affichage de ${start+1} à ${Math.min(start+tableState.pageSize,rows.length)} sur ${rows.length} titres`:'Aucun titre visible';
    $('#ct-pages').innerHTML=`<button type="button" data-demo-page="${tableState.page-1}" ${tableState.page===1?'disabled':''} aria-label="Page précédente">‹</button>${Array.from({length:Math.min(pages,9)},(_,i)=>{const n=pages<=9?i+1:Math.min(Math.max(1,tableState.page-4),pages-8)+i;return `<button type="button" data-demo-page="${n}" ${tableState.page===n?'aria-current="page"':''} aria-label="Page ${n}">${n}</button>`;}).join('')}<button type="button" data-demo-page="${tableState.page+1}" ${tableState.page===pages?'disabled':''} aria-label="Page suivante">›</button>`;
    $('#ct-sort').value=sortKey();$('#ct-page-size').value=String(tableState.pageSize);
    $('#ct-sort-direction').textContent=sortDir()==='desc'?'↓':'↑';$('#ct-sort-direction').setAttribute('aria-label',`Passer au tri ${sortDir()==='desc'?'croissant':'décroissant'}`);
  }
  async function loadPageCurves(rows){
    const pending=rows.filter(r=>!r.curveRequested);
    if(!applied||!pending.length)return;
    const context=applied;
    for(const row of pending){row.curveRequested=true;row.curveLoading=true;}
    try{
      const data=await J.post('ranking/curves',{ids:pending.map(r=>r.id)});
      for(const row of pending)row.points=data?.curves?.[row.id]||[];
    }catch(_){/* Une courbe indisponible ne bloque jamais les résultats. */}
    finally{
      for(const row of pending)row.curveLoading=false;
      if(context===applied)renderRanking();
    }
  }
  function sortBy(key){if(!REG[key]||REG[key].nosort)return;tableState.userSorted=true;tableState.sorts=[J.table.nextSort({key:sortKey(),dir:sortDir()},key,REG[key].dir||'desc')];tableState.page=1;renderRanking();}
  function render() {
    renderStrategies();
    document.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.mode===state.mode));
    $('#ct-simple').hidden=state.mode!=='simple';$('#ct-expert').hidden=state.mode!=='expert';
    renderSimple();renderExpert();renderFilters();renderColumns();
  }
  $('#ct-page').addEventListener('click',e=>{
    const b=e.target.closest('button');if(!b)return;
    if(b.dataset.demoPage!==undefined){tableState.page=Number(b.dataset.demoPage);renderRanking();}
    else if(b.dataset.sort)sortBy(b.dataset.sort);
    else if(b.dataset.openFilter){const k=b.dataset.openFilter,was=activeFilter;closeFilter();if(was!==k){activeFilter=k;$(`#ct-list-${k}`).hidden=false;$(`[data-open-filter="${k}"]`).setAttribute('aria-expanded','true');$(`#ct-list-${k} input[type=search]`).value='';searchCategories(k,'');if(!matchMedia('(max-width:700px)').matches&&!matchMedia('(pointer:coarse)').matches)$(`#ct-list-${k} input[type=search]`).focus();positionFilter(k);}}
    else if(b.dataset.closeFilter)closeFilter(true);
    else if(b.dataset.allIndicator){tableState.page=1;const k=b.dataset.allIndicator;state.filters[k]=categories[k].options.map(o=>o.id);saveLocalSelection(k);$(`#ct-list-${k}`).querySelectorAll('input[type=checkbox]').forEach(el=>el.checked=true);filterSummary();}
    else if(b.dataset.mode){closeFilter();state.mode=b.dataset.mode;project();render();}
    else if(b.dataset.period){state.selected=b.dataset.period;renderSimple();}
    else if(b.dataset.step){const f=b.dataset.step,p=config().periods[state.selected];setSimpleValue(f,Number(Math.max(f==='return'?-20:f==='slope'?.01:0,Math.min(f==='return'?20:f==='slope'?2:1,p[f]+Number(b.dataset.delta))).toFixed(3)));renderSimple();}
    else if(b.dataset.addNode!==undefined){at(b.dataset.addNode).children.push(rule('volatility',state.selected==='day'?'month':state.selected,2,'<='));renderExpert();}
    else if(b.dataset.addGroup!==undefined){at(b.dataset.addGroup).children.push(group([rule('volatility',state.selected==='day'?'month':state.selected,2,'<='),rule('drawdown',state.selected==='day'?'month':state.selected,15,'<=')]));renderExpert();}
    else if(b.dataset.removeNode!==undefined){const path=b.dataset.removeNode.split('.'),i=Number(path.pop());at(path.join('.')).children.splice(i,1);project();renderExpert();}
    else if(b.dataset.action==='reset') $('#ct-reset').click();
    else if(b.dataset.action==='save') $('#ct-save').click();
  });
  $('#ct-page').addEventListener('input',e=>{
    const el=e.target;
    if(el.dataset.categorySearch){filterQuery=el.value;searchCategories(el.dataset.categorySearch,el.value);}
    if(el.dataset.simple){const f=el.dataset.simple,p=config().periods[state.selected];setSimpleValue(f,number(el.value,f==='return'?-20:0,f==='return'?20:f==='slope'?2:1,p[f]));$(`#ct-${el.type==='range'?'value':'range'}-${f}`).value=p[f];chart();preview();}
    if(el.dataset.ruleField==='value'){const r=at(el.closest('[data-path]').dataset.path);r.value=number(el.value,-1e12,1e12,r.value);project();preview();}
  });
  $('#ct-page').addEventListener('change',e=>{
    const el=e.target;
    if(el.dataset.simple) el.value=config().periods[state.selected][el.dataset.simple];
    if(el.dataset.enabled){activatePeriod(el.dataset.enabled,el.checked);renderSimple();renderExpert();}
    if(el.dataset.filter){tableState.page=1;const list=state.filters[el.dataset.filter],id=el.dataset.category;state.filters[el.dataset.filter]=el.checked?[...new Set([...list,id])]:list.filter(v=>v!==id);saveLocalSelection(el.dataset.filter);filterSummary();}
    if(el.dataset.column!==undefined){vis[el.dataset.column]=el.checked;try{J.store.set(visKey,{rev:layout.revision,dev:TableLayout.device(),vis});}catch(_){/* préférence facultative */}renderColumns();}
    if(el.dataset.ruleField){const r=at(el.closest('[data-path]').dataset.path),f=el.dataset.ruleField;r[f]=f==='value'?number(el.value,-1e12,1e12,r.value):el.value;if(f==='value')el.value=r.value;project();preview();}
    if(el.dataset.groupJoin!==undefined){at(el.dataset.groupJoin).join=el.value;project();preview();}
  });
  loadStatus();
  $('#ct-strategy').onchange=e=>switchTo(e.target.value);
  for(const t of ['input','change','click'])$('#ct-page').addEventListener(t,e=>{if(e.target.id!=='ct-strategy')queueMicrotask(renderStrategies);});
  $('#ct-tab-rules').onclick=()=>$('#ct-rules').scrollIntoView({behavior:'smooth',block:'nearest'});
  $('#ct-tab-manage').onclick=()=>{$('#ct-filter-panel').open=true;$('#ct-filter-panel').scrollIntoView({behavior:'smooth',block:'start'});};
  $('#ct-tab-queries').onclick=()=>{
    const has=J.store.has(key);
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
    try{J.store.set(key,{mode:state.mode});}catch(_){/* préférences d'affichage seulement */}
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
  // Choix de tri : même ordre que les colonnes du tableau (réglage personnel), pas l'ordre du catalogue.
  function buildSortOptions(){const cat=catalogOf(),by=Object.fromEntries(cat.map(c=>[c.id,c])),order=(layout.columns||[]).map(c=>c.id).filter(id=>by[id]).concat(cat.map(c=>c.id).filter(id=>!(layout.columns||[]).some(c=>c.id===id)));
    const opts=order.map(id=>by[id]).filter(c=>REG[c.id]&&c.sortable!==false&&!REG[c.id].nosort),sel=$('#ct-sort'),keep=sel.value;
    sel.innerHTML=opts.map((c,i)=>`<option value="${esc(c.id)}">${i?'':'Trier par : '}${esc(c.label)}</option>`).join('');if(keep&&opts.some(c=>c.id===keep))sel.value=keep;}
  buildSortOptions();
  TableLayout.onChange(()=>{layout=TableLayout.get(tl,'explorer',TableLayout.device(),LEGACY_VISIBLE());vis=personal();applyDefaultSort();buildSortOptions();renderColumns();});
  $('#ct-sort').onchange=e=>{sortBy(e.target.value);};
  $('#ct-sort-direction').onclick=()=>{tableState.userSorted=true;tableState.sorts=[{key:sortKey(),dir:sortDir()==='desc'?'asc':'desc'},...tableState.sorts.slice(1)];tableState.page=1;renderRanking();};
  $('#ct-page-size').onchange=e=>{tableState.pageSize=Number(e.target.value);tableState.page=1;renderRanking();};
  $('#ct-show-demo-all').onclick=()=>{tableState.verdict='all';tableState.query='';const q=$('#ct-search');if(q)q.value='';tableState.page=1;state.filters=secondary.all(categories);for(const k of Object.keys(categories))saveLocalSelection(k);renderFilters();};
  $('#ct-apply').onclick=()=>loadRows();
  // Un instantané au clic : les modifications du formulaire restent en attente.
  const specNow=()=>{tree();project();return cloneJSON(config());};
  function updateSearchStatus(message){
    const button=$('#ct-apply'),status=$('#ct-search-status');
    button.disabled=loading;
    button.innerHTML=loading?'<span class="spinner" aria-hidden="true"></span> Recherche en cours…':'Appliquer les réglages';
    $('.ct-ranking').setAttribute('aria-busy',String(loading));
    const pending=applied&&(applied.strategy!==state.strategy||JSON.stringify(applied.config)!==JSON.stringify(config())||JSON.stringify(applied.filters)!==JSON.stringify(state.filters));
    status.textContent=message||(loading?'Recherche en cours…':loadError?loadError:pending?'Réglages modifiés : appuyez sur « Appliquer les réglages ».':applied?'Résultats à jour.':'Cliquez sur « Appliquer les réglages » pour lancer la recherche.');
    $('#ct-ranking-status').textContent=status.textContent;
  }
  async function loadRows(){
    if(loading)return;
    const request={strategy:state.strategy,config:specNow(),filters:cloneJSON(state.filters)};
    loading=true;loadError=null;updateSearchStatus();renderRanking();
    try{
      const data=await J.post('ranking/table',{strategy:request.strategy,config:request.config,include_curves:false});
      if(!data||!Array.isArray(data.rows))throw new Error('Le serveur a renvoyé une réponse de classement invalide');
      const rows=data.rows.map(toRow);
      intrinsicRows=rows;applied=request;universe=data.universe||rows.length;
      defaultSort='complex';applyDefaultSort();tableState.page=1;scoreLabel=data.label||'';
    }catch(e){
      loadError='Résultats non actualisés : '+(e.message||'erreur de chargement')+'. Réessayez avec « Appliquer les réglages ».';
    }finally{
      loading=false;renderRanking();updateSearchStatus();
    }
  }
  tree();project();render();
})().catch(error=>{const p=document.querySelector('#ct-feedback');p.textContent='Impossible d’ouvrir la page de test : '+error.message;});

// Bloc « Stratégie » : réglages repliés par défaut (Afficher / Masquer), choix mémorisé dans ce navigateur.
(function(){
  const panel=document.querySelector('.ct-panel[aria-label="Stratégie et critères"]'),head=panel&&panel.querySelector('.ct-strategy');
  if(!head||head.querySelector('.ct-fold'))return;
  let open=false;                                   // toujours masqués à l'ouverture de la page
  const b=document.createElement('button');b.type='button';b.className='btn sm ct-fold';b.setAttribute('aria-controls','ct-simple ct-expert');
  const apply=()=>{panel.classList.toggle('ct-collapsed',!open);b.setAttribute('aria-expanded',String(open));b.textContent=open?'Masquer les réglages':'Afficher les réglages';};
  b.onclick=()=>{open=!open;apply();};
  (head.querySelector('.ct-strategy-tools')||head).appendChild(b);apply();
})();
