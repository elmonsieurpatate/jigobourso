// Statut des stratégies : Retenues | Exclues | Toutes dans le Classement, scores et rangs inchangés, fiche cohérente, contexte absent ⇒ jamais « Retenue ».
const {chromium}=require(process.env.PLAYWRIGHT_MODULE),fs=require('fs');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.JIGO_CHROMIUM,args:['--no-sandbox']}),report=[];
 for(const width of [390,1280]){
  const ctx=await browser.newContext({viewport:{width,height:900}}),page=await ctx.newPage(),errors=[],r={width};
  page.setDefaultTimeout(30000);page.on('pageerror',e=>errors.push(e.message));
  try{
   await page.goto('http://127.0.0.1:18089/login.html');await page.fill('#u','review_user');await page.fill('#p','review-local-password');await page.click('#auth-form button.primary');await page.waitForURL('**/index.html');
   await page.waitForFunction(()=>document.querySelector('#ct-strategy-count')?.textContent.trim().length>0,null,{timeout:60000});
   const read=async()=>page.evaluate(()=>({counts:Object.fromEntries([...document.querySelectorAll('#ct-verdict [data-verdict]')].map(b=>[b.dataset.verdict,+b.querySelector('b').textContent.replace(/\D/g,'')])),
     checked:[...document.querySelectorAll('#ct-verdict [aria-checked=true]')].map(b=>b.dataset.verdict),
     rows:[...document.querySelectorAll('#ct-table-body tr[data-row]')].map(t=>({id:t.dataset.row,rank:t.querySelector('.ct-rank-cell').textContent.trim(),status:t.querySelector('.ct-status')?.textContent})),
     overflow:document.documentElement.scrollWidth>innerWidth}));
   const set=async m=>{await page.locator(`#ct-verdict [data-verdict="${m}"]`).click();await page.waitForTimeout(200);return read();};
   await page.locator('#ct-strategy').selectOption('fast');await page.waitForTimeout(1500);
   await page.locator('#ct-page-size').selectOption('100').catch(()=>{});
   const ret=await read();if(ret.checked[0]!=='retained')throw new Error('Défaut du Classement : Retenues attendu');
   const exc=await set('excluded'),all=await set('all');
   r.counts=all.counts;
   if(all.counts.all<all.counts.retained+all.counts.excluded)throw new Error('Compteurs incohérents '+JSON.stringify(all.counts));
   if(ret.counts.all!==all.counts.all||exc.counts.excluded!==all.counts.excluded)throw new Error('Les compteurs changent avec le mode');
   if(all.rows.length>0&&all.rows.some(x=>!x.status))throw new Error('Badge de statut absent');
   const byId=Object.fromEntries(all.rows.map(x=>[x.id,x]));
   for(const x of ret.rows)if(byId[x.id]&&(byId[x.id].rank!==x.rank||x.status!=='Retenue'))throw new Error('Rang ou statut différent selon le mode (retenues)');
   for(const x of exc.rows)if(byId[x.id]&&(byId[x.id].rank!==x.rank||x.status!=='Exclue'))throw new Error('Rang ou statut différent selon le mode (exclues)');
   if(all.overflow)throw new Error('Débordement horizontal');
   r.rows={retained:ret.rows.length,excluded:exc.rows.length,all:all.rows.length};
   // fiche d'un titre retenu et d'un titre exclu, avec le contexte de la stratégie
   const open=async(id,extra='')=>{const href=await page.evaluate(i=>{const a=document.querySelector(`tr[data-row="${i}"] a.ct-company`);return a&&a.getAttribute('href');},id);const url='http://127.0.0.1:18089/'+(href||`titre.html?src=explorer&id=${id}&ct=fast`)+extra;await page.goto(url+'#analyse');await page.locator('.hero').waitFor();await page.waitForSelector('#main .card');return page.evaluate(()=>({badge:(/Statut stratégie : (Retenue|Exclue|Indéterminée)/.exec(document.querySelector('.hero').textContent)||[''])[0],main:document.querySelector('#main').textContent,overflow:document.documentElement.scrollWidth>innerWidth,wide:[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,5).map(e=>e.tagName+'.'+e.className+' '+Math.round(e.getBoundingClientRect().right)),scores:document.body.textContent.includes('Scores V4')}));};
   const statusOf=t=>/Statut stratégie[^R E I]*(Retenue|Exclue|Indéterminée)/.exec(t||'');
   await page.locator('#ct-strategy').selectOption('mom6');await page.waitForFunction(()=>document.querySelector('#ct-strategy').value==='mom6');await page.waitForTimeout(1500);
   const free=await read();r.momentum=free.counts;
   if(free.counts.retained!==free.counts.all||free.counts.excluded!==0)throw new Error('Stratégie sans critère : tout doit être retenu '+JSON.stringify(free.counts));
   ret.rows=free.rows;
   if(ret.rows.length){const f=await open(ret.rows[0].id);if(!/Retenue/.test(f.badge||''))throw new Error('Fiche retenue : '+f.badge);if(!f.main.includes('Stratégie appliquée'))throw new Error('Analyse V4 absente');if(f.overflow)throw new Error('Fiche : débordement '+JSON.stringify(f.wide));}
   if(exc.rows.length){const f=await open(exc.rows[0].id);if(!/Exclue/.test(f.badge||''))throw new Error('Fiche exclue : '+f.badge);if(!/non respecté/.test(f.main))throw new Error('Raisons absentes');if(!/% par séance/.test(f.main))throw new Error('Unité de pente absente');}
   // brouillon annoncé mais introuvable : jamais « Retenue »
   const lost=await open(all.rows[0].id,'&ctx=inexistant');if(/Retenue/.test(lost.badge||'')||!/Contexte de stratégie introuvable/.test(lost.main))throw new Error('Contexte perdu : verdict rendu');
   // sans contexte du tout (stratégie inconnue)
   await page.goto('http://127.0.0.1:18089/titre.html?src=explorer&id=1&ct=cs-inconnu#analyse');await page.locator('.hero').waitFor();await page.waitForSelector('#main .card, #main .notice');
   if(!(await page.locator('#main').textContent()).includes('Contexte de stratégie introuvable'))throw new Error('Stratégie inconnue : contexte attendu introuvable');
   // modification en direct des critères (non enregistrée) : le serveur recalcule les statuts, rangs inchangés ; la fiche reçoit le brouillon
   await page.goto('http://127.0.0.1:18089/index.html');await page.waitForFunction(()=>document.querySelector('#ct-strategy-count')?.textContent.trim().length>0,null,{timeout:60000});
   await page.locator('#ct-strategy').selectOption('fast');await page.waitForTimeout(1500);
   await page.locator('#ct-verdict [data-verdict="all"]').click();
   const before=await read();if(before.counts.retained!==0)throw new Error('Départ : aucun titre retenu attendu');
   await page.evaluate(()=>{for(const k of ['week','month']){document.querySelector(`[data-period="${k}"]`).click();const i=document.querySelector('#ct-sliders input[data-simple="slope"]');i.value=0;i.dispatchEvent(new Event('input',{bubbles:true}));}});
   await page.waitForFunction(()=>+document.querySelector('#ct-verdict [data-verdict="retained"] b').textContent.replace(/\D/g,'')>0,null,{timeout:15000});
   const edited=await read();r.edited=edited.counts;
   if(edited.counts.retained!==edited.counts.all)throw new Error('Critères à zéro : tout doit être retenu '+JSON.stringify(edited.counts));
   if(JSON.stringify(edited.rows.map(x=>[x.id,x.rank]))!==JSON.stringify(before.rows.map(x=>[x.id,x.rank])))throw new Error('Les rangs changent avec les critères');
   if(/non actualisés/.test(await page.locator('#ct-feedback').textContent()))throw new Error('Statuts non actualisés');
   const draft=await open(edited.rows[0].id);
   if(!/Retenue/.test(draft.badge||'')||!/non enregistrés/.test(draft.main))throw new Error('Fiche : brouillon non transmis '+draft.badge);
   // administration des scores
   await page.goto('http://127.0.0.1:18089/admin.html#scores');await page.waitForTimeout(1500);
   const adm=await page.evaluate(async()=>{const o={};for(const v of ['retained','excluded','all'])o[v]=(await J.post('admin/scores/ranking',{strategy:'growth_v4',which:'simple',limit:100,verdict:v})).listing;return o;});
   r.admin={retained:adm.retained.total,excluded:adm.excluded.total,all:adm.all.total,counts:adm.all.counts};
   if(adm.all.total!==before.counts.all||adm.retained.total!==before.counts.retained||adm.excluded.total!==before.counts.excluded)throw new Error('Scores et Classement : effectifs différents '+JSON.stringify(r.admin));
   const clRank=Object.fromEntries(before.rows.map(x=>[x.id,x.rank.replace('=','')]));
   if(adm.all.rows.some(x=>String(x.rank)!==clRank[x.id]))throw new Error('Rangs différents entre Scores et Classement');
   await page.waitForSelector('[data-a="rk-verdict"]',{timeout:20000}).catch(()=>{});
   r.errors=errors;r.completed=true;
  }catch(e){r.error=e.message;await page.screenshot({path:`audit-results/status-error-${width}.png`}).catch(()=>{});r.errors=errors;}
  report.push(r);await ctx.close();
 }
 await browser.close();console.log(JSON.stringify(report));if(report.some(r=>!r.completed||r.errors.length))process.exit(1);
})();
