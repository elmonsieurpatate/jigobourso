/* Administration persistante via settings ; aperçu hors ligne explicite, aucun calcul financier. */
(async () => {
  'use strict';
  const personal=!!window.JigoSecondaryPersonal;
  if(!await J.init(personal?'explorer':'admin-filtres',{admin:!personal}))return;
  const $=J.$,esc=J.esc,M=window.AdminCategoryModel;
  const crumbs=$('#crumbs');if(crumbs)crumbs.innerHTML=personal?'<span>Explorer</span><i>›</i><b>Mes filtres</b>':'<span>Administration</span><i>›</i><b>Filtres et catégories</b>';
  const store=J.store.filters;
  let loaded=await store.load(),defaults=loaded.defaults,filters=loaded.definitions.filters,saving=false;
  const offline=loaded.source==='offline';
  if(offline){$('.ac-demo-note').textContent='Aperçu hors ligne : changements en mémoire uniquement, perdus au rechargement.';$('.ac-demo-badge').textContent='Aperçu hors ligne';}
  if(!offline){const ed=filters.filter(f=>f.editable).length;$('.ac-demo-note').textContent=`${filters.length} filtres · ${ed} éditables · ${filters.length-ed} alimentés par le catalogue. Propositions initiales modifiables, non validées financièrement.`;}
  function accept(response){loaded=response;defaults=response.defaults;filters.splice(0,filters.length,...response.definitions.filters);}
  function busy(on){
    if(on)$('#ac-page').setAttribute('aria-busy','true');else $('#ac-page').removeAttribute('aria-busy');
    $('#ac-page').querySelectorAll('input,select,textarea,button').forEach(el=>{if(on){el.dataset.secondaryDisabled=el.disabled?'1':'0';el.disabled=true;}else if(el.dataset.secondaryDisabled!==undefined){el.disabled=el.dataset.secondaryDisabled==='1';delete el.dataset.secondaryDisabled;}});
  }
  async function persist(candidate){
    if(saving)throw Error('Un enregistrement est déjà en cours.');saving=true;busy(true);
    try{accept(await store.save(candidate));}finally{saving=false;busy(false);}
  }
  function selectedByDefault(id){const f=filter(),key=current()?.id||'values',s=defaults.filters[f.id]?.[key];return !s||s.mode==='all'||s.selected.includes(id);}
  function defaultBox(id,label){return `<label class="ac-default-check"><input type="checkbox" data-default-id="${esc(id)}" ${selectedByDefault(id)?'checked':''} aria-label="Inclure par défaut : ${esc(label)}"> <span class="sr-only">Incluse par défaut</span></label>`;}
  const measures=new Map();
  let selected=filters[0].id,editing=null,dirty=false,nextId=1,timer,reordering=false,tab='categories';
  const filter=()=>filters.find(x=>x.id===selected);
  const current=()=>filter().measures.find(x=>x.id===measures.get(selected))||filter().measures[0]||null;
  const icons={score_simple:'<path d="M4 19a8 8 0 1 1 16 0"/><path d="M12 19l4-6"/>',score_complex:'<path d="M4 19a8 8 0 1 1 16 0"/><path d="M12 19l4-6"/><path d="M8 19a4 4 0 0 1 8 0"/>',volatility:'<path d="M2 12h4l3-8 5 16 3-8h5"/>',liquidity:'<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v7c0 4 16 4 16 0V5M4 12v6c0 4 16 4 16 0v-6"/>',volume:'<path d="M3 21V12h4v9M10 21V7h4v14M17 21V2h4v19"/>',positive:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M7 2v6M17 2v6m-9 7 3 3 5-6"/>',spikes:'<path d="m2 18 7-8 4 4 9-12M16 2h6v6"/>',concentration:'<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M1 12h4M19 12h4"/>',drawdown:'<path d="m2 16 6-8 5 7 4-5 5 9"/>',returns:'<rect x="2" y="3" width="20" height="16" rx="2"/><path d="m5 14 4-5 5 3 5-6M7 22h10"/>',quality:'<path d="m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6zM8 12l3 3 5-6"/>',country:'<circle cx="12" cy="12" r="10"/><ellipse cx="12" cy="12" rx="4" ry="10"/><path d="M2 12h20"/>',sector:'<path d="m3 12 9-9h7l2 2v7l-9 9z"/><circle cx="16" cy="8" r="1"/>',market:'<path d="m2 8 10-6 10 6H2M4 10v9M9 10v9M15 10v9M20 10v9M2 22h20"/>',asset:'<path d="m2 7 10-5 10 5-10 5zM2 12l10 5 10-5M2 17l10 5 10-5"/>'};
  const icon=id=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[id]||icons.quality}</svg>`;
  function notify(text){$('#ac-feedback').textContent=text;clearTimeout(timer);timer=setTimeout(()=>$('#ac-feedback').textContent='',5000);}
  function renderList(){
    $('#ac-filter-select').innerHTML=[true,false].map(editable=>`<optgroup label="${editable?'Catégories éditables':'Valeurs issues des données'} (${filters.filter(f=>f.editable===editable).length})">${filters.filter(f=>f.editable===editable).map(f=>`<option value="${f.id}" ${f.id===selected?'selected':''}>${esc(f.name)}${editable?'':' (non éditable)'} · ${f.group==='main'?'principal':'autre'}</option>`).join('')}</optgroup>`).join('');
  }
  function renderTabs(){
    for(const key of ['categories','information']){
      $('#ac-tab-'+key).setAttribute('aria-selected',tab===key);$('#ac-'+key+'-panel').hidden=tab!==key;
    }
    $('#ac-measure-bar').hidden=!filter().editable||filter().measures.length<2;
  }
  function renderMain(){
    const f=filter(),i=current();
    $('#ac-indicator-title').textContent=f.name;$('#ac-indicator-icon').innerHTML=icon(f.id);
    $('#ac-filter-description').textContent=f.description;
    $('#ac-filter-type').textContent=f.editable?(i.kind==='numeric'?'Numérique':'États prédéfinis'):'Métadonnée du titre';
    $('#ac-indicator-unit').textContent=f.editable?i.unit:'Sans unité';
    $('#ac-filter-enabled').checked=f.enabled;$('#ac-filter-group').value=f.group||'other';$('#ac-disabled-note').hidden=f.enabled;
    $('#ac-editability').textContent=f.editable?'⚙ Catégories éditables':'🔒 Valeurs non éditables';$('#ac-editability').className='ac-editability '+(f.editable?'editable':'locked');
    $('#ac-guidance-title').textContent=f.editable?'ⓘ Catégories persistantes':'ⓘ Valeurs issues du catalogue';
    $('#ac-guidance-description').textContent=f.editable?'Ajoutez, modifiez ou supprimez des catégories. Elles serviront à filtrer les titres, jamais à modifier leurs scores.':'Ces groupes fixes sont en lecture seule. Leurs affectations proviennent du catalogue ; les coches règlent uniquement leur sélection par défaut.';
    $('#ac-tab-categories').innerHTML=(f.editable?'⚙ Catégories':'🔒 Valeurs disponibles')+` <span id="ac-category-count">(${f.editable?i.categories.length:f.values.length})</span>`;
    $('#ac-category-toolbar').hidden=!f.editable;$('#ac-order-note').hidden=!f.editable||!reordering;
    $('#ac-reorder').setAttribute('aria-pressed',reordering);$('#ac-reorder').textContent=reordering?'✓ Terminer l’ordre':'↕ Réordonner';
    $('#ac-measure-select').innerHTML=f.measures.map(m=>`<option value="${m.id}" ${m.id===i?.id?'selected':''}>${esc(m.name)}</option>`).join('');
    $('#ac-measure-description').textContent=i?.description||'';
    $('#ac-information-details').innerHTML=`<dt>Filtre</dt><dd>${esc(f.name)}</dd><dt>Provenance</dt><dd>${esc(f.editable?'Mesure définie par la configuration V4 ; catégories proposées modifiables et persistantes.':f.provenance)}</dd><dt>Définition</dt><dd>${esc(i?.description||f.description)}</dd><dt>Unité</dt><dd>${esc(i?.unit||'Sans unité')}</dd><dt>Modification</dt><dd>${f.editable?'Catégories enregistrées : libellé, explication, bornes / valeurs, couleur et ordre.':'Valeurs issues des données, non modifiables dans cette interface.'}</dd><dt>Effet dans l’Explorer</dt><dd>Les catégories et la visibilité sont utilisées dans les filtres du classement. Les notes et les rangs restent inchangés.</dd>`;
    if(f.editable){
      $('#ac-category-head').innerHTML='<tr><th scope="col">Ordre</th><th scope="col">Catégorie</th><th scope="col">Plage de valeurs</th><th scope="col">Couleur</th><th scope="col">Description (courte)</th><th scope="col">Par défaut</th><th scope="col">Actions</th></tr>';
      $('#ac-category-rows').innerHTML=i.categories.map((c,n)=>`<tr data-category-id="${c.id}"><td data-label="Ordre" class="ac-order"><span class="ac-drag-mark" aria-hidden="true">⠿</span><span>${n+1}</span><span class="ac-order-buttons" ${reordering?'':'hidden'}><button type="button" class="btn icon sm" data-move="${c.id}" data-delta="-1" ${n===0?'disabled':''} aria-label="Monter ${esc(c.name)}">↑</button><button type="button" class="btn icon sm" data-move="${c.id}" data-delta="1" ${n===i.categories.length-1?'disabled':''} aria-label="Descendre ${esc(c.name)}">↓</button></span></td><td data-label="Catégorie" class="ac-category-name"><span class="ac-category-chip" style="--category-color:${c.color}">${esc(c.name)}</span></td><td data-label="Plage de valeurs" class="ac-category-interval">${esc(M.interval(c,i))}${!c.unknown&&i.kind==='numeric'?` <small>${esc(i.unit)}</small>`:''}</td><td data-label="Couleur"><span class="ac-color-swatch" style="background:${c.color}" role="img" aria-label="Couleur ${c.color}"></span></td><td data-label="Description" class="ac-category-description">${esc(c.description||'—')}</td><td data-label="Par défaut">${defaultBox(c.id,c.name)}</td><td data-label="Actions" class="ac-category-actions"><button type="button" class="btn icon sm ghost" data-edit="${c.id}" aria-label="Modifier ${esc(c.name)}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 4 5 5M4 20l5-1L20 8a2 2 0 0 0-5-5L4 14z"/></svg></button><button type="button" class="btn icon sm ghost" data-delete="${c.id}" aria-label="Supprimer ${esc(c.name)}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 10v7M14 10v7"/></svg></button></td></tr>`).join('')||'<tr><td colspan="7" class="ac-no-categories">Aucune catégorie. Ajoutez une catégorie pour cette mesure.</td></tr>';
    }else{
      $('#ac-category-head').innerHTML='<tr><th scope="col">Valeur du catalogue</th><th scope="col">Provenance</th><th scope="col">Modification</th><th scope="col">Par défaut</th></tr>';
      $('#ac-category-rows').innerHTML=f.values.map(x=>`<tr class="ac-source-row"><td data-label="Valeur du catalogue"><strong>${esc(x.label)}</strong></td><td data-label="Provenance">${esc(f.provenance)}</td><td data-label="Modification"><span class="ac-readonly-pill">Lecture seule</span></td><td data-label="Par défaut">${defaultBox(x.id,x.label)}</td></tr>`).join('');
    }
    const options=f.editable?i.categories:f.values;
    const count=options.filter(o=>selectedByDefault(o.id)).length;
    $('#ac-default-summary').textContent=`${count} / ${options.length} incluses par défaut · distinct des catégories et des choix personnels`;
    renderTabs();renderValidation();
  }
  function renderValidation(){
    const box=$('#ac-validation');
    if(!filter().editable){box.className='ac-validation info';box.innerHTML='<strong>ⓘ Filtre non éditable</strong><p>Groupes fixes, affectés depuis les métadonnées du catalogue. Aucun indicateur, score ou seuil technique n’est modifié.</p>';if(loaded.migration_notices?.some(n=>n.filter_id===selected))box.innerHTML+='<p>Migration des anciennes sélections : certains groupes peuvent inclure plus de valeurs. Vérifiez les coches par défaut ; la sélection précédente est conservée.</p>';return;}
    const result=M.validate(current(),current().categories);
    box.className='ac-validation '+(!result.valid?'error':result.warnings.length?'warning':'success');
    const errors=Object.values(result.errors).flatMap(x=>Object.values(x));
    box.innerHTML=`<strong>${!result.valid?'⚠ Configuration à corriger':result.warnings.length?'⚠ Couverture à compléter':'✓ Configuration valide'}</strong>${!result.valid?`<ul>${[...new Set(errors)].map(t=>`<li>${esc(t)}</li>`).join('')}</ul>`:result.warnings.length?`<ul>${result.warnings.map(t=>`<li>${esc(t)}</li>`).join('')}</ul>`:'<p>Aucun chevauchement. Les plages et les données absentes sont couvertes.</p>'}`;
  }
  function closeEditor(){editing=null;dirty=false;$('#ac-editor').hidden=true;$('#ac-draft-state').textContent='';}
  async function mayDiscard(){return !editing||!dirty||await J.confirm('Abandonner les modifications ?','La catégorie en cours d’édition n’a pas été enregistrée.','Abandonner');}
  async function selectIndicator(id){if(id===selected||!filters.some(f=>f.id===id))return;if(!await mayDiscard()){$('#ac-filter-select').value=selected;return;}selected=id;tab='categories';reordering=false;closeEditor();renderList();renderMain();}
  function clearErrors(){for(const field of ['name','description','min','max','color','unknown','values']){const error=$('#ac-error-'+field),input=$('#ac-'+field);error.textContent='';if(input)input.removeAttribute('aria-invalid');}$('#ac-editor-warnings').innerHTML='';}
  function syncNature(){
    const unknown=$('#ac-unknown').checked,numeric=current().kind==='numeric';
    for(const id of ['min','max','interval']){$('#ac-'+id+'-wrap').hidden=unknown||!numeric;$('#ac-'+id).disabled=unknown||!numeric;}
    $('#ac-values-wrap').hidden=unknown||numeric;$('#ac-values').querySelectorAll('input').forEach(el=>el.disabled=unknown||numeric);
    $('#ac-unknown-note').hidden=!unknown;
  }
  async function openEditor(id=null){
    if(!filter().editable||!await mayDiscard())return;
    const c=id?M.copy(current().categories.find(c=>c.id===id)):{id:'new-'+nextId++,name:'',min:null,max:null,minIncluded:false,maxIncluded:false,color:'#8b80ef',active:true,unknown:false,values:[],description:''};
    editing={id,temporaryId:c.id,legacyActive:c.active};dirty=false;clearErrors();
    $('#ac-editor-title').textContent=id?'Éditer la catégorie : '+c.name:'Ajouter une catégorie';
    $('#ac-name').value=c.name;$('#ac-description').value=c.description||'';$('#ac-min').value=c.min??'';$('#ac-max').value=c.max??'';$('#ac-color').value=c.color;
    $('#ac-interval').value=(c.minIncluded?'closed':'open')+'-'+(c.maxIncluded?'closed':'open');
    $('#ac-unknown').checked=c.unknown;$('#ac-unknown').disabled=!current().supportsUnknown;
    $('#ac-values').innerHTML=(current().domain||[]).map(v=>`<label><input type="checkbox" value="${esc(v.value)}" ${c.values.includes(v.value)?'checked':''}>${esc(v.label)}</label>`).join('');
    $('#ac-editor').hidden=false;$('#ac-draft-state').textContent='Brouillon local';syncNature();
    $('#ac-editor').scrollIntoView({behavior:'instant',block:'nearest'});$('#ac-name').focus({preventScroll:true});
  }
  function readDraft(){
    const unknown=$('#ac-unknown').checked,numeric=current().kind==='numeric',parts=$('#ac-interval').value.split('-');
    const value=id=>{const el=$('#ac-'+id);return el.validity.badInput?NaN:el.value.trim()===''?null:Number(el.value);};
    const min=unknown||!numeric?null:value('min'),max=unknown||!numeric?null:value('max');
    return {id:editing.temporaryId,name:$('#ac-name').value.trim(),description:$('#ac-description').value.trim(),min,max,minIncluded:min!==null&&parts[0]==='closed',maxIncluded:max!==null&&parts[1]==='closed',color:$('#ac-color').value,active:editing.legacyActive??true,unknown,values:unknown||numeric?[]:[...$('#ac-values').querySelectorAll('input:checked')].map(el=>el.value)};
  }
  async function saveDraft(e){
    e.preventDefault();if(!editing||!filter().editable)return;clearErrors();
    const c=readDraft(),categories=current().categories.map(x=>x.id===editing.id?c:M.copy(x));if(!editing.id)categories.push(c);
    const result=M.validate(current(),categories),errors=result.errors[c.id]||{};
    if(!result.valid){
      for(const [field,text] of Object.entries(errors)){const error=$('#ac-error-'+field);if(error)error.textContent=text;const input=$('#ac-'+field);if(input)input.setAttribute('aria-invalid','true');}
      if(!Object.keys(errors).length)$('#ac-editor-warnings').textContent='La configuration contient une incohérence. Vérifiez les catégories.';
      const first=Object.keys(errors)[0];if(first&&$('#ac-'+first))$('#ac-'+first).focus();return;
    }
    const candidate=M.copy(filter());candidate.measures.find(m=>m.id===current().id).categories=categories;
    try{await persist(candidate);closeEditor();renderList();renderMain();notify(result.warnings.length?'Catégorie enregistrée. Vérifiez les avertissements de couverture.':'Catégorie enregistrée.');}catch(error){notify(error.message);}
  }
  async function removeCategory(id){
    if(!filter().editable)return;
    const indicator=current(),category=indicator.categories.find(c=>c.id===id);if(!category)return;
    if(!await J.confirm('Supprimer cette catégorie ?',`« ${category.name} » sera supprimée des réglages enregistrés. Les éventuels trous de couverture seront signalés.`,'Supprimer'))return;
    if(!await mayDiscard())return;
    const candidate=M.copy(filter());candidate.measures.find(m=>m.id===indicator.id).categories=indicator.categories.filter(c=>c.id!==id);
    await persist(candidate);closeEditor();renderList();renderMain();notify('Catégorie supprimée.');
  }
  async function moveCategory(id,delta){
    if(!filter().editable||!reordering||!await mayDiscard())return;
    const categories=current().categories,index=categories.findIndex(c=>c.id===id),target=index+delta;
    if(index<0||target<0||target>=categories.length)return;
    const candidate=M.copy(filter()),ordered=candidate.measures.find(m=>m.id===current().id).categories;
    [ordered[index],ordered[target]]=[ordered[target],ordered[index]];await persist(candidate);closeEditor();renderMain();notify('Ordre d’affichage enregistré. Bornes inchangées.');
    const button=$(`[data-move="${id}"][data-delta="${delta}"]`);if(button&&!button.disabled)button.focus({preventScroll:true});
  }
  $('#ac-page').addEventListener('click',async e=>{const b=e.target.closest('button');if(!b)return;try{
    if(b.dataset.indicator)await selectIndicator(b.dataset.indicator);
    else if(b.dataset.edit)await openEditor(b.dataset.edit);
    else if(b.dataset.delete)await removeCategory(b.dataset.delete);
    else if(b.dataset.move)await moveCategory(b.dataset.move,Number(b.dataset.delta));
  }catch(error){notify(error.message);}});
  $('#ac-filter-select').onchange=e=>selectIndicator(e.target.value);
  $('#ac-filter-group').onchange=async e=>{const next=M.copy(filter());next.group=e.target.value;try{await persist(next);renderList();renderMain();notify(next.group==='main'?'Filtre classé dans les principaux.':'Filtre classé dans les autres indicateurs.');}catch(error){e.target.value=filter().group;notify(error.message);}};
  $('#ac-filter-enabled').onchange=async e=>{const next=M.copy(filter());next.enabled=e.target.checked;try{await persist(next);renderMain();notify('Visibilité dans Explorer enregistrée.');}catch(error){e.target.checked=filter().enabled;notify(error.message);}};
  async function setDefaults(selection){if(saving){renderMain();return;}saving=true;busy(true);try{accept(await store.defaults(selected,current()?.id||'values',selection));renderMain();notify('Sélection par défaut enregistrée.');}catch(error){renderMain();notify(error.message);}finally{saving=false;busy(false);}}
  $('#ac-page').addEventListener('change',e=>{const id=e.target.dataset.defaultId;if(!id)return;const options=filter().editable?current().categories:filter().values;let chosen=options.filter(o=>selectedByDefault(o.id)).map(o=>o.id);chosen=e.target.checked?[...new Set([...chosen,id])]:chosen.filter(x=>x!==id);setDefaults({mode:'custom',selected:chosen});});
  $('#ac-default-all').onclick=()=>setDefaults({mode:'all',selected:[]});
  $('#ac-restore').onclick=async()=>{if(!await mayDiscard()||!await J.confirm(personal?'Rétablir les valeurs par défaut ?':'Restaurer les valeurs proposées ?',`Réinitialiser uniquement « ${filter().name} » : catégories, activation et sélections par défaut ? Les autres filtres sont conservés.`,'Restaurer'))return;try{accept(await store.restore(selected));closeEditor();renderList();renderMain();notify(personal?'Valeurs par défaut rétablies pour ce filtre.':'Valeurs proposées restaurées pour ce filtre.');}catch(error){notify(error.message);}};
  $('#ac-order').onclick=async()=>{
    if(!await mayDiscard())return;
    const groups={main:filters.filter(f=>f.group==='main').map(f=>f.id),other:filters.filter(f=>f.group!=='main').map(f=>f.id)};
    const name=id=>esc(filters.find(f=>f.id===id).name),titles={main:'Filtres principaux',other:'Autres indicateurs'};
    const draw=()=>['main','other'].map(g=>`<h3 class="ac-order-title">${titles[g]} (${groups[g].length})</h3><ol class="ac-order-list">${groups[g].map((id,i)=>`<li><span>${i+1}. ${name(id)}</span><span class="ac-order-btns"><button type="button" class="btn sm" data-move="${g}:${id}:-1" ${i===0?'disabled':''} aria-label="Monter ${name(id)}">↑</button><button type="button" class="btn sm" data-move="${g}:${id}:1" ${i===groups[g].length-1?'disabled':''} aria-label="Descendre ${name(id)}">↓</button></span></li>`).join('')}</ol>`).join('');
    J.dialog({title:'Ordre des filtres dans l’Explorer',body:'<p class="ac-order-note">L’Explorer affiche les filtres dans cet ordre, groupe Principal d’abord puis Autres indicateurs. Le groupe d’un filtre se règle dans le sélecteur de la page.</p><div id="ac-order-body"></div>',
      onopen:d=>{const body=d.querySelector('#ac-order-body');body.innerHTML=draw();body.onclick=e=>{const b=e.target.closest('[data-move]');if(!b)return;const [g,id,dir]=b.dataset.move.split(':'),list=groups[g],i=list.indexOf(id),j=i+Number(dir);if(j<0||j>=list.length)return;[list[i],list[j]]=[list[j],list[i]];body.innerHTML=draw();const again=body.querySelector(`[data-move="${g}:${id}:${dir}"]`)||body.querySelector(`[data-move^="${g}:${id}:"]:not([disabled])`);if(again)again.focus();};},
      actions:[{label:'Annuler',run:()=>{}},{label:'Enregistrer l’ordre',cls:'primary',run:async()=>{try{accept(await store.order([...groups.main,...groups.other]));closeEditor();renderList();renderMain();notify('Ordre des filtres enregistré.');}catch(error){J.toast(error.message);return true;}}}]});
  };
  $('#ac-reload').onclick=async()=>{if(!await mayDiscard())return;try{accept(await store.load());closeEditor();renderList();renderMain();notify('Réglages rechargés.');}catch(error){notify(error.message);}};
  $('#ac-measure-select').onchange=async e=>{const id=e.target.value,previous=current().id;if(!await mayDiscard()){e.target.value=previous;return;}if(!filter().measures.some(m=>m.id===id))return;measures.set(selected,id);reordering=false;closeEditor();renderMain();};
  $('#ac-reorder').onclick=()=>{reordering=!reordering;renderMain();};
  for(const key of ['categories','information'])$('#ac-tab-'+key).onclick=()=>{tab=key;renderTabs();};
  $('#ac-page').addEventListener('keydown',e=>{if(e.target.getAttribute('role')!=='tab'||!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();tab=(e.key==='Home'||(e.key!=='End'&&tab==='information'))?'categories':'information';renderTabs();$('#ac-tab-'+tab).focus();});
  $('#ac-add-category').onclick=()=>openEditor();$('#ac-cancel').onclick=()=>{closeEditor();$('#ac-add-category').focus();};$('#ac-close-editor').onclick=$('#ac-cancel').onclick;
  $('#ac-editor').onsubmit=saveDraft;
  $('#ac-editor').addEventListener('input',()=>{dirty=true;$('#ac-draft-state').textContent='Modifications non enregistrées';});
  $('#ac-unknown').onchange=()=>{dirty=true;syncNature();clearErrors();};
  renderList();renderMain();
})().catch(error=>{document.querySelector('#ac-feedback').textContent='Impossible de charger les filtres : '+error.message;});
