/* Application réelle, base jetable et seed portfolio_dynamics_seed.py. */
const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const BASE=process.env.BASE||'http://127.0.0.1:18089',OUT=process.env.SHOTS;
(async()=>{const browser=await chromium.launch({executablePath:process.env.JIGO_CHROMIUM,args:['--no-sandbox']});try{
const ctx=await browser.newContext({viewport:{width:1440,height:1100}}),page=await ctx.newPage(),errors=[];
page.on('pageerror',e=>errors.push(e.message));
assert((await ctx.request.post(BASE+'/api.php?r=auth/login',{data:{username:'matrix_demo',password:'matrix-local-test-2026'},headers:{Origin:BASE}})).ok());
const list=await (await ctx.request.get(BASE+'/api.php?r=portfolios')).json();
for(const legacy of [false,true]){
 const pf=list.portfolios.find(p=>p.name===(legacy?'Démo legacy — matrice':'Démo synthétique — matrice'));
 assert(pf);
 await page.goto(BASE+'/portefeuilles.html?id='+pf.id);
 await page.locator('.pfd-table').waitFor({timeout:60000});
 assert.equal(await page.locator('.pfd-table thead th').count(),13);
 assert.deepEqual(await page.locator('.pfd-table thead th').allTextContents().then(a=>a.slice(2).map(x=>x.trim())),['1J','2J','3J','1S','2S','1M','3M','6M','1A','2A','4A']);
 assert.equal(await page.locator('.pfd-table tbody tr').count(),5);
 const contribution=page.locator('.px-card').filter({has:page.getByRole('heading',{name:'Contribution au résultat',exact:true})});
 assert((await contribution.boundingBox()).y<(await page.locator('.pf-dynamics').boundingBox()).y,'Performances après la contribution');
 const text=await page.locator('.pfd-table').innerText(); assert(!text.includes('GIBO')&&!text.includes('DXC'));
 if(legacy){await page.locator('#pfc-plot .fc-plot').waitFor();assert.match(await page.locator('#px-page').innerText(),/Vue temporaire modernisée/);assert.equal(await page.locator('.px-top [data-k="per"] button').count(),15);assert.equal(await page.locator('.pf-kpis').count(),0);}
 const raw=await (await ctx.request.get(BASE+'/api.php?r=portfolio&id='+pf.id)).json();
 const vfc=raw.positions.find(p=>p.symbol==='VFC');
 const row=page.locator('.pfd-table tbody tr').filter({hasText:'VFC'});
 assert.equal((await row.locator('.pfd-personal strong').textContent()).replace(/[\s  ]/g,''), await page.evaluate(v=>J.eurS(v).replace(/[\s  ]/g,''),vfc.unrealized));
 const api=await (await ctx.request.get(BASE+'/api.php?r=portfolio/dynamics&id='+pf.id)).json();
 assert.equal(api.listings['1001'].cells['4y'].delta!==null,true);
 assert.equal(api.listings['1003'].cells['4y'].return,null);
 assert.equal(api.listings['1003'].currency,'USD');
 await page.locator('[data-sort="market:1d"]').click();assert.equal(await page.locator('.pfd-table th[aria-sort="descending"]').count(),1);
 assert.equal(await page.locator('.pfd-table thead th').count(),13);
 if(!legacy){
  const missing=await page.evaluate(async id=>{
    const P=await J.api('portfolio/performance',{params:{id}});
    for(const key of ['value','securities','gain','latent'])P.chart.full[key][P.chart.full[key].length-1]=null;
    const html=PFPerf2.money(P,{inc:0,soc:0});
    const doc=new DOMParser().parseFromString(html,'text/html');
    return [...doc.querySelectorAll('.pf-kpis .v')].map(e=>e.textContent.trim());
  },pf.id);
  assert.equal(missing[2],'–');assert.equal(missing[3],'–');
 }
 if(!legacy){assert.equal(await page.locator('.pf-kpis .metric').count(),4);const labels=await page.locator('.pf-kpis .l').allTextContents();assert.deepEqual(labels,['Capital net apporté','Liquidités','Valeur des actions','Gain total']);}
 for(const theme of ['light','dark'])for(const width of [320,390,1440]){
  await page.setViewportSize({width,height:1100});await page.waitForTimeout(350);await page.locator(".pfd-table").waitFor({timeout:60000});await page.evaluate(t=>{document.documentElement.dataset.theme=t;J.store.set('jigo_theme',t);},theme);
  await page.locator('.pf-dynamics').scrollIntoViewIfNeeded();await page.evaluate(()=>document.fonts.ready);
  const overflow=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,nodes:[...document.querySelectorAll('body *')].filter(e=>{const r=e.getBoundingClientRect();return r.right>innerWidth+2&&r.width>0&&!e.closest('.pfd-scroll,.px-tw,.table-wrap,#side')}).slice(0,12).map(e=>[e.tagName,e.id,e.className,e.getBoundingClientRect().width])}));if(overflow.scroll>overflow.width+1){console.log(overflow);await page.screenshot({path:`${OUT||'/tmp'}/overflow.png`,fullPage:true});}assert(overflow.scroll<=overflow.width+1,'Débordement de page '+width);
  const bounds=await page.locator('.pfd-scroll').evaluate(el=>({client:el.clientWidth,scroll:el.scrollWidth}));
  if(width<600)assert(bounds.scroll>bounds.client);
  const first=await row.locator('.pfd-title').boundingBox();
  await page.locator('.pfd-scroll').evaluate(el=>el.scrollLeft=350);
  const fixed=await row.locator('.pfd-title').boundingBox();const spacing=await page.locator('.pfd-table').evaluate(e=>parseFloat(getComputedStyle(e).borderSpacing));assert(Math.abs(first.x-fixed.x)<=spacing+1,'Nom non figé');
  await page.locator('.pfd-scroll').evaluate(el=>el.scrollLeft=0);
  // Deux signaux opposés dans une même cellule : fond de performance et pastille de dynamique.
  await page.evaluate(()=>{
   const heats=['gain-strong','gain','gain-soft','neutral','loss-soft','loss-strong'],returns=[4,2,.5,0,-1,-4];
   const cells=Object.fromEntries(heats.map((h,i)=>['c'+i,{return:returns[i],previous:0,delta:i===0?-2:1,heat:h,arrow:i===0?'down':'up',neutral_points:.1,start:'2026-11-16',end:'2026-11-17',previous_start:'2026-11-13'}]));
   const data={horizons:heats.map((_,i)=>({key:'c'+i,label:'Test '+i,group:'short'})),listings:{1:{cells,currency:'EUR',basis:'adjusted'}}};
   const fixture=document.createElement('div');fixture.id='pfd-colour-fixture';fixture.innerHTML=PFDynamics.html(data,[{listing_id:1,symbol:'Styles de démonstration',qty:1,unrealized:0,unrealized_pct:0}],null,{key:'title',dir:'asc'});document.body.append(fixture);
  });
  const signals=await page.locator('#pfd-colour-fixture .pfd-cell:not(.pfd-personal)').evaluateAll(els=>els.map(e=>({heat:getComputedStyle(e).backgroundColor,ink:getComputedStyle(e).color,dynamic:getComputedStyle(e.querySelector('.pfd-dynamic')).color})));
  assert.notEqual(signals[0].dynamic,signals[4].dynamic,'Dynamique négative et positive : couleurs distinctes');
  assert.notEqual(signals[0].ink,signals[0].dynamic,'Gain et dynamique inverse indépendants');
  // Vérification du contraste calculé des six nuances avec le texte du thème.
  const contrast=await page.locator('.pfd-legend span,#pfd-colour-fixture .pfd-cell:not(.pfd-personal),#pfd-colour-fixture .pfd-dynamic').evaluateAll(els=>{
   const rgb=s=>{const canvas=document.createElement('canvas');canvas.width=canvas.height=1;const c=canvas.getContext('2d');c.fillStyle=s;c.fillRect(0,0,1,1);return [...c.getImageData(0,0,1,1).data].slice(0,3).map(x=>x/255);};
   const lum=s=>rgb(s).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4).reduce((n,x,i)=>n+x*[.2126,.7152,.0722][i],0);
   return els.map(el=>{const s=getComputedStyle(el),a=lum(s.color),b=lum(s.backgroundColor);return(Math.max(a,b)+.05)/(Math.min(a,b)+.05)});
  });assert(contrast.every(x=>x>=4.5),'Contrastes '+contrast);await page.locator('#pfd-colour-fixture').evaluate(e=>e.remove());
  if(OUT){fs.mkdirSync(OUT,{recursive:true});await page.screenshot({path:`${OUT}/matrix-${legacy?'legacy':'cash'}-${width}-${theme}.png`,fullPage:true});await page.locator('.pf-dynamics').screenshot({path:`${OUT}/table-${legacy?'legacy':'cash'}-${width}-${theme}.png`});}
 }
 await page.setViewportSize({width:1440,height:1100});
 await page.waitForTimeout(350);await page.locator('.pfd-table').waitFor({timeout:60000});
 await page.locator('.pfd-cell[role="button"]').first().click();
 await page.getByRole('dialog').waitFor();assert.match(await page.getByRole('dialog').innerText(),/Fenêtre précédente/);
 await page.getByRole('button',{name:'Fermer',exact:true}).click();
}
assert.deepEqual(errors,[]);await ctx.close();console.log('Matrice : cash et legacy, onze horizons, tri, quantités restantes, titres vendus, devises, contrastes, 320/390/1440 clair et sombre : OK');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
