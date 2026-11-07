// Administration des colonnes : ordre, visibilité, largeurs, tri, filtres initiaux ; quatre configurations indépendantes ; application aux deux tableaux ; persistance.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const BASE='http://127.0.0.1:18089/';
const must=(c,m)=>{if(!c)throw new Error(m);};
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.JIGO_CHROMIUM,args:['--no-sandbox']}),log={};
 const login=async(w=1280)=>{const ctx=await browser.newContext({viewport:{width:w,height:1000}}),p=await ctx.newPage();p.setDefaultTimeout(30000);p.errors=[];p.on('pageerror',e=>p.errors.push(e.message));
   await p.goto(BASE+'login.html');await p.fill('#u','review_user');await p.fill('#p','review-local-password');await p.click('#auth-form button.primary');await p.waitForURL('**/index.html');return {ctx,p};};
 const heads=p=>p.$$eval('#ct-table-head th',t=>t.map(x=>x.textContent.replace(/[↑↓]/g,'').trim()));
 const ready=async p=>{await p.waitForFunction(()=>document.querySelector('#ct-strategy-count')?.textContent.trim().length>0,null,{timeout:60000});await p.waitForTimeout(400);};
 let {ctx,p}=await login();
 try{
  await p.goto(BASE+'admin.html#colonnes');await p.waitForSelector('.ac-list');
  const order=async()=>p.$$eval('.ac-row',r=>r.map(x=>x.dataset.id));
  const o0=await order();log.catalog=o0.length;must(o0.length>=30,'Catalogue incomplet');
  must(await p.locator('.ac-pick .seg button.on').count()===2,'Sélecteurs page/affichage');
  // monter complex en tête avec les boutons
  const i=o0.indexOf('complex');for(let k=0;k<i;k++)await p.locator('[data-up="complex"]').click();
  must((await order())[0]==='complex','Monter : complex en première position');
  // glisser-déposer : price en tête
  const h=p.locator('.ac-row[data-id="price"] [data-handle]'),t=p.locator('.ac-row').first();const hb=await h.boundingBox(),tb=await t.boundingBox();
  await p.mouse.move(hb.x+hb.width/2,hb.y+hb.height/2);await p.mouse.down();await p.mouse.move(tb.x+20,tb.y+2,{steps:8});await p.mouse.up();
  must((await order())[0]==='price','Glisser-déposer : price en tête');
  await p.locator('[data-down="price"]').click();                                   // price en deuxième position
  must((await order()).slice(0,2).join()==='complex,price','Descendre');
  // visibilité, largeur, tri, filtres
  await p.locator('[data-vis="volatility"]').uncheck();await p.locator('[data-vis="perf_week"]').check();
  await p.selectOption('[data-wmode="name"]','custom');await p.fill('[data-w="name"]','240');await p.locator('[data-w="name"]').dispatchEvent('change');
  await p.selectOption('[data-sortkey="0"]','name');await p.locator('[data-sortdir="0"][data-v="asc"]').click();
  await p.selectOption('[data-sortkey="1"]','simple');
  await p.locator('[data-verdict="all"]').click();await p.selectOption('[data-pagesize]','25');
  must(await p.locator('.ac-table thead th').count()>5,'Aperçu');
  const expected=await p.$$eval('.ac-row:not(.off) .ac-name',n=>n.map(x=>x.textContent.trim()));
  await p.locator('[data-act="save"]').click();await p.waitForSelector('.notice.ok');
  must((await p.textContent('.notice.ok')).includes('Enregistré'),'Confirmation');
  // tableau Explorer : même ordre, largeur, tri, filtres initiaux, pagination sur l'ensemble
  await p.goto(BASE+'index.html');await ready(p);
  const hd=await heads(p);log.heads=hd;
  must(JSON.stringify(hd)===JSON.stringify(expected),'Ordre des en-têtes ≠ aperçu : '+JSON.stringify(hd)+' / '+JSON.stringify(expected));
  must(hd[0]==='Score complexe'&&hd[1]==='Cours','Ordre exact');
  const cellsOrder=await p.$$eval('#ct-table-body tr:first-child td',td=>td.map(x=>x.dataset.label));
  must(JSON.stringify(cellsOrder)===JSON.stringify(hd),'Cellules ≠ en-têtes');
  must(await p.locator('#ct-verdict [aria-checked=true]').getAttribute('data-verdict')==='all','Statut initial Toutes');
  must(await p.inputValue('#ct-page-size')==='25','Lignes par page');
  const w=await p.$eval('#ct-table-head th.ct-name-heading',e=>Math.round(e.getBoundingClientRect().width));must(w>=238,'Largeur du titre '+w);
  const names=async()=>p.$$eval('#ct-table-body .ct-company-text b',n=>n.map(x=>x.textContent.trim()));
  const n1=await names();await p.locator('[data-demo-page="2"]').first().click();const n2=await names();
  const all=[...n1,...n2];must(all.length>25,'Deuxième page');
  must(JSON.stringify(all)===JSON.stringify([...all].sort((a,b)=>a.localeCompare(b,'fr'))),'Tri par nom sur plusieurs pages : '+all.join(','));
  // clic manuel prioritaire ; tri sur colonne masquée via la liste ; valeurs numériques
  await p.locator('[data-demo-page="1"]').first().click();
  await p.locator('[data-sort-column="price"]').click();const pr=await p.$$eval('#ct-table-body td.ct-cell-price',c=>c.map(x=>parseFloat(x.textContent.replace(/[^\d,]/g,'').replace(',','.'))));
  must(pr.every((v,i)=>!i||pr[i-1]>=v),'Clic manuel : cours décroissant numérique '+pr.join());
  await p.selectOption('#ct-sort','drawdown');await p.locator('#ct-columns').evaluate(e=>e.closest('details').open=true);
  await p.locator('[data-column="drawdown"]').check();
  const dd=await p.$$eval('#ct-table-body td.ct-cell-drawdown',c=>c.map(x=>parseFloat(x.textContent.replace(/[^\d,]/g,'').replace(',','.'))));
  must(dd.length>1&&dd.every((v,i)=>!i||dd[i-1]>=v),'Tri sur colonne masquée puis affichée '+dd.join());
  must((await heads(p))[0]==='Score complexe','Afficher une colonne ne change pas l’ordre');
  must(await p.locator('#ct-verdict [aria-checked=true]').getAttribute('data-verdict')==='all','Filtre conservé après changement de colonne');
  // statut : compteurs et badges toujours là
  must(await p.locator('#ct-table-body .ct-status').count()>0,'Badge de statut');
  // mobile : configuration indépendante (valeurs par défaut) ; basculement de largeur en direct
  await p.setViewportSize({width:390,height:900});await p.waitForTimeout(500);
  const hm=await heads(p);log.mobile=hm;
  must(JSON.stringify(hm)===JSON.stringify(['Rang','Titre','Statut stratégie','Cours','Var. % du jour','Pente · mois','Score simple','Score complexe']),'Mobile par défaut : '+JSON.stringify(hm));
  must(!(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth)),'Mobile : débordement de page');
  await p.setViewportSize({width:1280,height:900});await p.waitForTimeout(500);
  must((await heads(p))[0]==='Score complexe','Retour ordinateur');
  must(p.errors.length===0,'Erreurs JS '+p.errors.join('|'));
  // nouvelle connexion : persistance
  await ctx.close();({ctx,p}=await login());await ready(p);
  must(JSON.stringify(await heads(p))===JSON.stringify(hd.filter(x=>true)),'Après reconnexion');
  // Scores / Classement : configuration propre, inchangée par la précédente
  await p.goto(BASE+'admin.html#scores');await p.waitForSelector('[data-a="tab"]');await p.locator('[data-a="tab"]',{hasText:'Profils'}).click();await p.waitForSelector('#as-rktable',{timeout:60000});
  const sh=await p.$$eval('#as-rktable th',t=>t.map(x=>x.textContent.replace(/[↑↓]/g,'').trim()));log.scores=sh;
  must(JSON.stringify(sh)===JSON.stringify(['Rang','Titre','Statut stratégie','Tendance (courbe)','Score simple','Score complexe']),'Scores par défaut : '+JSON.stringify(sh));
  const rk0=await p.$$eval('#as-rktable tbody tr',r=>r.map(x=>[x.querySelector('td').textContent.trim(),x.querySelectorAll('td')[1].textContent.trim()]));
  await p.locator('[data-a="rk-sort"][data-v="name"]').click();await p.waitForTimeout(1500);
  const rk1=await p.$$eval('#as-rktable tbody tr',r=>r.map(x=>[x.querySelector('td').textContent.trim(),x.querySelectorAll('td')[1].textContent.trim()]));
  const nm=rk1.map(x=>x[1].toLowerCase());must(JSON.stringify(nm)===JSON.stringify([...nm].sort((a,b)=>a.localeCompare(b,'fr'))),'Scores : tri par titre');
  const m0=Object.fromEntries(rk0.map(x=>[x[1],x[0]]));for(const [r,n] of rk1)if(m0[n]!==undefined)must(m0[n]===r,'Scores : le rang global change avec le tri');
  // réinitialiser Explorer / ordinateur
  await p.goto(BASE+'admin.html#colonnes');await p.waitForSelector('.ac-list');
  await p.locator('[data-act="reset"]').click();await p.locator('dialog button, .modal button').filter({hasText:'Réinitialiser'}).last().click().catch(()=>{});
  await p.waitForSelector('.notice.ok',{timeout:10000});
  await p.goto(BASE+'index.html');await ready(p);
  must((await heads(p))[0]==='Rang','Après réinitialisation : ordre par défaut '+(await heads(p)).join());
  must(await p.locator('#ct-verdict [aria-checked=true]').getAttribute('data-verdict')==='retained','Statut par défaut après réinitialisation');
  must(p.errors.length===0,'Erreurs JS '+p.errors.join('|'));
  console.log(JSON.stringify({ok:true,...log}));
 }catch(e){await p.screenshot({path:'audit-results/columns-error.png'}).catch(()=>{});console.log(JSON.stringify({ok:false,error:e.message,...log}));process.exit(1);}
 await browser.close();
})();
