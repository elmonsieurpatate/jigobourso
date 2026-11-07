// Var. 1J (%) et granularité Jour : en-tête, infobulle, tri numérique, critère de recherche Jour (statuts seulement), administration des scores (Jour désactivé, 0 %).
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const BASE='http://127.0.0.1:18089/',must=(c,m)=>{if(!c)throw new Error(m);};
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.JIGO_CHROMIUM,args:['--no-sandbox']}),log={};
 const ctx=await browser.newContext({viewport:{width:1280,height:900}}),p=await ctx.newPage(),errors=[];
 p.setDefaultTimeout(30000);p.on('pageerror',e=>errors.push(e.message));
 try{
  await p.goto(BASE+'login.html');await p.fill('#u','review_user');await p.fill('#p','review-local-password');await p.click('#auth-form button.primary');await p.waitForURL('**/index.html');
  const ready=async()=>p.waitForFunction(()=>document.querySelector('#ct-strategy-count')?.textContent.trim().length>0,null,{timeout:60000});
  await ready();
  await p.locator('#ct-strategy').selectOption('fast');await p.waitForTimeout(1200);
  await p.locator('#ct-verdict [data-verdict="all"]').click();await p.waitForTimeout(300);
  // 1. en-tête renommé, infobulle, jamais l'ancien intitulé
  const heads=await p.$$eval('#ct-table-head th',t=>t.map(x=>({text:x.textContent.replace(/[↑↓]/g,'').trim(),title:x.getAttribute('title')})));
  const h=heads.find(x=>x.text==='Var. 1J (%)');
  must(h,'En-tête « Var. 1J (%) » absent : '+JSON.stringify(heads));
  must(h.title==='Variation du cours entre les deux dernières séances clôturées.','Infobulle : '+h.title);
  must(!heads.some(x=>/^Var\. ?%/.test(x.text)),'Ancien intitulé « Var. % » encore affiché');
  // 2. tri numérique sur la colonne
  const col=async()=>p.$$eval('#ct-table-body td.ct-cell-change',c=>c.map(x=>parseFloat(x.textContent.replace(/\s/g,'').replace('−','-').replace(',','.').replace(/[^\d.\-]/g,''))).filter(v=>!Number.isNaN(v)));
  await p.locator('[data-sort-column="change"]').click();await p.waitForTimeout(300);
  let a=await col();must(a.length>1,'Pas assez de valeurs Var. 1J');
  const first=await p.$$eval('#ct-table-head th',t=>t.map(x=>x.getAttribute('aria-sort')));
  const asc=a.every((v,i)=>!i||a[i-1]<=v),desc=a.every((v,i)=>!i||a[i-1]>=v);must(asc||desc,'Tri numérique : '+a.join());
  await p.locator('[data-sort-column="change"]').click();await p.waitForTimeout(300);
  const b=await col();must(asc?b.every((v,i)=>!i||b[i-1]>=v):b.every((v,i)=>!i||b[i-1]<=v),'Tri inversé : '+b.join());
  log.sorted=b.slice(0,5);
  // 3. critère de recherche Jour : statuts seulement, rangs et scores inchangés
  const read=async()=>p.evaluate(()=>({counts:Object.fromEntries([...document.querySelectorAll('#ct-verdict [data-verdict]')].map(b=>[b.dataset.verdict,+b.querySelector('b').textContent.replace(/\D/g,'')])),
    rows:[...document.querySelectorAll('#ct-table-body tr[data-row]')].map(t=>({id:t.dataset.row,rank:t.querySelector('.ct-rank-cell').textContent.trim(),score:t.querySelector('.ct-score')?.textContent.trim()}))}));
  await p.evaluate(()=>{for(const k of ['week','month']){document.querySelector(`[data-period="${k}"]`).click();const i=document.querySelector('#ct-sliders input[data-simple="slope"]');i.value=0;i.dispatchEvent(new Event('input',{bubbles:true}));const r=document.querySelector('#ct-sliders input[data-simple="r2"]');r.value=0;r.dispatchEvent(new Event('input',{bubbles:true}));}});
  await p.waitForFunction(()=>+document.querySelector('#ct-verdict [data-verdict="retained"] b').textContent.replace(/\D/g,'')>0,null,{timeout:15000});
  const base=await read();log.base=base.counts;
  await p.evaluate(()=>document.querySelector('[data-period="day"]').click());
  must(await p.locator('#ct-sliders input[data-simple="return"]').count()>0,'Curseur « Variation 1J minimale » absent');
  must(await p.locator('#ct-sliders input[data-simple="slope"]').count()===0&&await p.locator('#ct-sliders input[data-simple="r2"]').count()===0,'Pente et R² ne doivent pas exister pour Jour');
  must(/1 séance\b/.test(await p.locator('[data-period="day"]').textContent()),'Libellé « 1 séance »');
  const toggleDay=async on=>p.evaluate(v=>{const c=document.querySelector('[data-enabled="day"]');c.checked=v;c.dispatchEvent(new Event('change',{bubbles:true}));},on);
  await toggleDay(true);
  const setDay=async v=>{await p.evaluate(x=>{const i=document.querySelector('#ct-sliders input[type=number][data-simple="return"]');i.value=x;i.dispatchEvent(new Event('input',{bubbles:true}));i.dispatchEvent(new Event('change',{bubbles:true}));},String(v));};
  await setDay(100);
  await p.waitForFunction(()=>+document.querySelector('#ct-verdict [data-verdict="retained"] b').textContent.replace(/\D/g,'')===0,null,{timeout:15000});
  const none=await read();log.day100=none.counts;
  must(none.counts.all===base.counts.all&&none.counts.excluded>=base.counts.excluded,'Compteurs Jour ≥ 100 % : '+JSON.stringify(none.counts));
  await setDay(-20);
  await p.waitForFunction(b=>+document.querySelector('#ct-verdict [data-verdict="retained"] b').textContent.replace(/\D/g,'')===b,base.counts.retained,{timeout:15000});
  const wide=await read();
  must(JSON.stringify(wide.rows.map(r=>[r.id,r.rank,r.score]))===JSON.stringify(base.rows.map(r=>[r.id,r.rank,r.score])),'Rangs ou scores modifiés par le critère Jour');
  await toggleDay(false);
  await p.waitForFunction(b=>+document.querySelector('#ct-verdict [data-verdict="retained"] b').textContent.replace(/\D/g,'')===b,base.counts.retained,{timeout:15000});
  // 4. administration des scores : Jour désactivé par défaut, sans poids
  await p.goto(BASE+'admin.html#scores');await p.waitForSelector('.as-period');
  const day=p.locator('.as-period',{hasText:'Jour'}).first();
  must(await day.count()>0,'Jour absent de la liste des granularités');
  must(!(await day.locator('input[data-a="active"]').isChecked()),'Jour doit être désactivé par défaut');
  must(/1 séance\b/.test(await day.textContent()),'Libellé de Jour');
  must(/Jour.{0,80}facultatif/s.test(await p.locator('#as-body').textContent()),'Explication de Jour absente');
  const rank=await p.evaluate(async()=>J.post('admin/scores/ranking',{strategy:'growth_v4',which:'simple',limit:5}));
  must(rank.listing.rows.length>0&&rank.listing.rows.some(r=>r.change!==null&&r.change!==undefined),'Var. 1J absente des lignes Scores');
  const sorted=await p.evaluate(async()=>J.post('admin/scores/ranking',{strategy:'growth_v4',which:'simple',limit:50,sort:[{key:'change',dir:'desc'}]}));
  const v=sorted.listing.rows.map(r=>r.change).filter(x=>x!==null);must(v.every((x,i)=>!i||v[i-1]>=x),'Tri serveur Var. 1J : '+v.join());
  must(errors.length===0,'Erreurs JS '+errors.join('|'));
  console.log('DAY OK '+JSON.stringify(log));
 }catch(e){console.error('DAY FAIL',e.message);await p.screenshot({path:'audit-results/day-fail.png'}).catch(()=>{});process.exitCode=1;}
 await browser.close();
})();
