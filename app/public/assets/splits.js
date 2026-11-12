/* Splits suspects : décisions administratives explicites, avec aperçu et historique. */
(async()=>{
  'use strict';
  if(!await J.init('admin',{admin:true}))return;
  const $=s=>document.querySelector(s),esc=J.esc;
  const labels={pending:'À examiner',applied:'Appliqués',rejected:'Refusés',confirmed:'Confirmés automatiquement',all:'Tous'};
  let filter='pending',query='',page=1,rows=[],busy=false,loadSequence=0,sort='magnitude_desc',minRatio='1';
  const format=new Intl.NumberFormat('fr-FR',{maximumFractionDigits:6});
  const num=v=>v==null?'—':format.format(+v);
  const date=v=>v?J.date(v):'—';
  const say=(text,error=false)=>{const el=$('#sr-feedback');el.hidden=false;el.className='notice'+(error?' err':'');el.textContent=text;};
  const price=(v,c)=>v==null?'—':num(v)+' '+esc(c||'');
  function preview(card){
    const old=Number(card.querySelector('[name=old]').value),next=Number(card.querySelector('[name=new]').value),r=next/old;
    card.querySelector('.sr-preview').textContent=old>0&&next>0&&Number.isFinite(r)?`${num(old)} ancienne(s) part(s) → ${num(next)} nouvelle(s). Quantité × ${num(r)}, prix de revient unitaire ÷ ${num(r)}. Coût total inchangé.`:'Indiquez le nombre de parts anciennes et nouvelles.';
  }
  function card(r){
    const state=r.state,ratio=+(r.reviewed_ratio||r.proposed_ratio),isOpen=state==='pending',editable=isOpen||state==='rejected';
    const old=ratio>=1?1:1/ratio,next=ratio>=1?ratio:1;
    const history=(r.history||[]).map(h=>`<li><b>${esc(labels[h.decision]||h.decision)}</b> · ${esc(J.dateTime(h.created_at))} · administrateur #${h.actor_id}${h.ratio?' · ratio ×'+num(h.ratio):''}<br>${esc(h.note||'')}${h.source_url?`<br><a href="${esc(h.source_url)}" target="_blank" rel="noopener noreferrer">Source enregistrée ↗</a>`:''}</li>`).join('');
    return `<article class="sr-card" data-lid="${r.listing_id}" data-day="${esc(r.event_date)}"><header class="sr-title"><div><h2>${esc(r.symbol)} · ${esc(r.name)}</h2><small>${esc(r.isin||'ISIN non renseigné')} · ${esc(r.mic)}</small></div><span class="badge ${state==='pending'?'warn':state==='applied'||state==='confirmed'?'ok':''}">${esc(labels[state])}</span></header>
      <p class="sr-meta">Saut du <b>${date(r.event_date)}</b> · variation à la détection ${J.pct(100*(+r.price_ratio-1),2)} · ratio proposé × ${num(ratio)}</p>
      <div class="sr-prices"><div><small>Clôture précédente</small><strong>${price(r.price_before,r.currency)}</strong></div><span aria-hidden="true">→</span><div><small>Clôture du jour</small><strong>${price(r.price_after,r.currency)}</strong></div></div>
      <p class="small muted">${r.vendor_state==='confirmed'?'Split confirmé.':r.vendor_state==='real_move'?'Yahoo n’a pas confirmé de split lors du dernier contrôle.':'Saut détecté, sans confirmation à ce stade.'} ${r.checked_at?'Dernier contrôle : '+date(r.checked_at)+'.':''}</p>
      <div class="sr-links"><a href="titre.html?id=${r.listing_id}" target="_blank" rel="noopener">Fiche du titre ↗</a><a href="https://finance.yahoo.com/quote/${encodeURIComponent(r.symbol)}/history/?filter=stockSplits" target="_blank" rel="noopener noreferrer">Splits Yahoo ↗</a><a href="https://www.google.com/search?q=${encodeURIComponent((r.isin||r.symbol)+' split '+r.event_date)}" target="_blank" rel="noopener noreferrer">Chercher un avis officiel ↗</a></div>
      ${isOpen?`<form class="sr-form"><div class="sr-ratio"><label>Parts anciennes<input name="old" type="number" step="any" min="0.00000001" value="${old}" required></label><label>Parts nouvelles<input name="new" type="number" step="any" min="0.00000001" value="${next}" required></label></div><p class="sr-preview"></p><div class="sr-source"><label>Lien de la source<input name="source" type="url" placeholder="https://…" maxlength="1000" value="${esc(r.source_url||'')}"></label><label>Explication / référence<textarea name="note" maxlength="1000" placeholder="Avis de l’émetteur, information du courtier…">${esc(r.note||'')}</textarea></label></div><p class="sr-error" role="alert" hidden></p><div class="sr-actions"><button class="btn primary" type="submit">Appliquer le split</button><button class="btn" type="button" data-decision="rejected">Ce n’est pas un split</button></div></form>`:state==='rejected'?'<p class="sr-locked">Refus conservé : la vérification automatique ne peut pas le remplacer.</p><button class="btn" data-decision="pending">Réexaminer</button>':'<p class="sr-locked">Opération confirmée. Le split n’est pas appliqué une deuxième fois et les transactions d’origine sont conservées.</p>'}
      <details><summary>Détection et historique des décisions</summary><p>Détecté le ${date(r.detected_at)}. Contrôles fournisseur : ${r.checks||0}. ${editable?'Le ratio est une proposition à vérifier, pas une preuve.':''}</p>${history?`<ol class="sr-history">${history}</ol>`:'<p>Aucune décision manuelle enregistrée.</p>'}</details></article>`;
  }
  async function load(){
    const sequence=++loadSequence,view=filter;
    $('#sr-refresh').disabled=true;$('#sr-rows').setAttribute('aria-busy','true');
    try{
      const d=await J.api('admin/splits',{params:{state:view,q:query,page,sort,min_ratio:minRatio}});if(sequence!==loadSequence)return;rows=d.rows;page=d.page;
      $('#sr-rows').dataset.state=view;
      $('#sr-tabs').innerHTML=Object.entries(labels).map(([k,v])=>`<button class="btn sm" data-filter="${k}" aria-current="${k===filter}">${esc(v)} <b>${k==='all'?Object.values(d.counts).reduce((a,n)=>a+n,0):d.counts[k]||0}</b></button>`).join('');
      $('#sr-summary').textContent=`${d.total} cas · page ${page} / ${d.pages}. Les décisions s’appliquent aux données de marché communes.`;
      $('#sr-recompute').hidden=!d.recompute_pending;
      $('#sr-rows').innerHTML=rows.length?rows.map(card).join(''):'<div class="sr-empty card"><h2>Aucun cas dans cette vue</h2><p class="muted">Utilisez « Tous » pour voir les opérations déjà traitées, ou lancez une détection.</p></div>';
      document.querySelectorAll('.sr-form').forEach(f=>preview(f.closest('.sr-card')));
      $('#sr-pages').innerHTML=`<button class="btn sm" data-page="${page-1}" ${page===1?'disabled':''}>Précédente</button><span>${page} / ${d.pages}</span><button class="btn sm" data-page="${page+1}" ${page===d.pages?'disabled':''}>Suivante</button>`;
    }catch(e){if(sequence===loadSequence)say(e.message||'Impossible de charger les splits.',true);}
    finally{if(sequence===loadSequence){$('#sr-refresh').disabled=false;$('#sr-rows').setAttribute('aria-busy','false');}}
  }
  async function decide(el,decision){
    if(busy)return;
    const row=rows.find(r=>String(r.listing_id)===el.dataset.lid&&r.event_date===el.dataset.day),form=el.querySelector('form'),error=el.querySelector('.sr-error');
    const data={listing_id:row.listing_id,event_date:row.event_date,revision:+row.revision,decision};
    if(form){data.old_shares=form.elements.old.value;data.new_shares=form.elements.new.value;data.source_url=form.elements.source.value;data.note=form.elements.note.value;}
    if(decision==='applied'){
      if(!form.reportValidity())return;
      if(!data.source_url.trim()&&data.note.trim().length<3){error.hidden=false;error.textContent='Ajoutez une source ou une explication pour confirmer.';return;}
      const text=`${row.symbol}, ${date(row.event_date)} : ${num(+data.old_shares)} ancienne(s) part(s) deviennent ${num(+data.new_shares)} nouvelle(s). Les cours historiques, performances et quantités détenues seront ajustés pour tous les utilisateurs. Les achats et ventes d’origine ne sont pas réécrits.`;
      busy=true;
      try{if(!await J.confirm('Confirmer ce split',text,'Appliquer le split')){busy=false;return;}}catch(e){busy=false;throw e;}
    }
    busy=true;el.querySelectorAll('button').forEach(b=>b.disabled=true);
    try{const result=await J.post('admin/splits/decide',data);say(decision==='applied'?'Split confirmé. Recalcul des performances demandé.':decision==='rejected'?'Split refusé. Cette décision est conservée.':'Cas remis en attente.');await load();}
    catch(e){if(error){error.hidden=false;error.textContent=e.message;}else say(e.message,true);}
    finally{busy=false;el.querySelectorAll('button').forEach(b=>b.disabled=false);}
  }
  $('#sr-rows').addEventListener('input',e=>{if(['old','new'].includes(e.target.name))preview(e.target.closest('.sr-card'));});
  $('#sr-rows').addEventListener('submit',e=>{e.preventDefault();decide(e.target.closest('.sr-card'),'applied');});
  $('#sr-rows').addEventListener('click',e=>{const b=e.target.closest('[data-decision]');if(b)decide(b.closest('.sr-card'),b.dataset.decision);});
  $('#sr-tabs').onclick=e=>{const b=e.target.closest('[data-filter]');if(b){filter=b.dataset.filter;page=1;load();}};
  $('#sr-pages').onclick=e=>{const b=e.target.closest('[data-page]');if(b){page=+b.dataset.page;load();}};
  $('#sr-search').onsubmit=e=>{e.preventDefault();query=$('#sr-query').value;page=1;load();};
  $('#sr-sort').onchange=e=>{sort=e.target.value;page=1;load();};
  $('#sr-min-ratio').onchange=e=>{minRatio=e.target.value;page=1;load();};
  $('#sr-refresh').onclick=()=>load();
  $('#sr-scan').onclick=async()=>{const b=$('#sr-scan');b.disabled=true;b.textContent='Détection en cours…';try{const d=await J.post('admin/splits/scan',{});say(`${d.detected} nouveau(x) cas détecté(s).`);await load();}catch(e){say(e.message,true);}finally{b.disabled=false;b.textContent='Détecter les nouveaux cas';}};
  await load();
})().catch(e=>{const el=document.querySelector('#sr-feedback');el.hidden=false;el.textContent=e.message;});
