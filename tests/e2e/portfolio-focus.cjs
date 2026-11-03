/* Six real local fixture positions: two overlapping pairs, DXC the largest loss. */
const assert=require('node:assert/strict'),fs=require('node:fs');
const{chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const BASE=process.env.BASE||'http://127.0.0.1:18090',OUT=process.env.AUDIT_OUT||'/tmp/jigobourso-focus';
assert.equal(process.env.JIGO_TEST_DATABASE,'1');assert.equal(new URL(BASE).hostname,'127.0.0.1');fs.mkdirSync(OUT,{recursive:true});
(async()=>{const browser=await chromium.launch({executablePath:process.env.JIGO_CHROMIUM||'/usr/bin/chromium',args:['--no-sandbox']});const report=[];
try{for(const width of [1280,390,375]){
 const ctx=await browser.newContext({viewport:{width,height:1000},isMobile:width<600,hasTouch:width<600});await ctx.route('**/*',r=>new URL(r.request().url()).hostname==='127.0.0.1'?r.continue():r.abort());
 assert.equal((await ctx.request.post(BASE+'/api.php?r=auth/login',{data:{username:'audit_portfolio',password:'audit-local-validation-2026'}})).status(),200);
 if(process.env.REPRO_BEFORE!=='1')await ctx.addInitScript(()=>{localStorage.setItem('jigo_pf_cmp_hidden',JSON.stringify(['t:11','t:12']));localStorage.setItem('jigo_pf_evo_mode2',JSON.stringify('gain'));});
 const page=await ctx.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(15000);
 await page.goto(BASE+'/portefeuilles.html?id=9');await page.waitForFunction(()=>!document.querySelector('#evo-chart .spinner')&&document.querySelector('#evo-note'));
 await page.locator('[data-view="analysis"]').click();await page.locator('#evo-per [data-v="1m"]').click();
 if(process.env.REPRO_BEFORE==='1'){
  await page.locator('#analysis-domain [data-v="market"]').click();
  const paths=await page.locator('#evo-chart path[data-series]').evaluateAll(es=>es.map(e=>e.getAttribute('d')));
  const labels=await page.locator('#evo-chart .lc-chip').count();assert.equal(labels,6);assert.equal(paths.length,6);assert.equal(new Set(paths).size,4);
  await page.screenshot({path:`${OUT}/before-${width}.png`,fullPage:true});report.push({width,legend:labels,paths:paths.length,distinctPaths:new Set(paths).size,errors});
 }else{
  assert.equal(await page.locator('#analysis-domain [data-v="personal"]').getAttribute('aria-pressed'),'true');
  assert.equal(await page.locator('#evo-chart path[data-series]').count(),7);assert.equal(await page.locator('#evo-chart path[data-series]').last().getAttribute('data-series'),'t:16');assert.equal(await page.locator('.analysis-position').count(),6);assert.equal(await page.locator('.analysis-position svg').count(),6);
  assert.match(await page.locator('#analysis-priority').innerText(),/DXC/);assert.match(await page.locator('#analysis-priority').innerText(),/[-−]21,00/);
  assert.equal(await page.locator('[data-loss]').first().getAttribute('data-loss'),'16');
  assert.equal(await page.locator('.analysis-position[data-key="16"]').getAttribute('aria-pressed'),'true');
  const curve=page.locator('#evo-chart path[data-series="t:16"]');assert.equal(await curve.getAttribute('opacity'),'1');assert.equal(await curve.getAttribute('stroke-width'),'3.5');assert.equal(await curve.getAttribute('stroke'),'#dc2626');
  assert.match(await page.locator('#analysis-detail').innerText(),/20 oct. 2026/);assert.match(await page.locator('#analysis-detail').innerText(),/Depuis vos achats/);assert.match(await page.locator('#analysis-detail').innerText(),/Première perte observée/);
  assert.equal(await page.locator('#evo-chart .lc-purchase-marker').count(),1);await page.screenshot({path:`${OUT}/default-${width}.png`,fullPage:true});
  for(const key of ['11','12','13','14','15','16']){
   await page.locator(`.analysis-position[data-key="${key}"]`).click();
   assert.equal(await page.locator(`#evo-chart path[data-series="t:${key}"]`).getAttribute('opacity'),'1');
   assert.equal(await page.locator(`.analysis-position[data-key="${key}"]`).getAttribute('aria-pressed'),'true');
   assert.match(await page.locator('#analysis-detail').innerText(),new RegExp({11:'TTAN',12:'ASO',13:'BOX',14:'FIGS',15:'VFC',16:'DXC'}[key]));
  }
  await page.locator('#analysis-losses [data-focus="16"]').click();assert.equal(await curve.getAttribute('opacity'),'1');
  await page.locator('#evo-chart .lc-chip[data-id="t:11"]').click();assert.equal(await page.locator('#evo-chart path[data-series="t:11"]').getAttribute('opacity'),'1');assert.equal(await page.locator('#evo-chart path[data-series="t:16"]').getAttribute('opacity'),'0.15');
  assert.match(await page.locator('#analysis-detail').innerText(),/Achat complémentaire/);assert.match(await page.locator('#analysis-detail').innerText(),/28 oct. 2026/);assert.match(await page.locator('#analysis-detail').innerText(),/Frais/);
  await page.locator('#evo-unit [data-v="pct"]').click();assert.equal(await page.locator('.analysis-position').count(),6);
  await page.locator('#evo-per [data-v="1w"]').click();assert.equal(await page.locator('.analysis-position').count(),6);assert.match(await page.locator('#analysis-detail').innerText(),/20 oct. 2026/);
  await page.locator('#clear-focus').click();assert.equal(await page.locator('#evo-chart path[data-series="t:11"]').getAttribute('opacity'),'1');
  await page.locator('#analysis-domain [data-v="market"]').click();assert.equal(await page.locator('.analysis-position').count(),6);if(await page.locator('#clear-focus').isVisible())await page.locator('#clear-focus').click();
  await page.locator('#analysis-domain [data-v="personal"]').click();await page.locator('#evo-per [data-v="1m"]').click();await page.locator('#evo-unit [data-v="eur"]').click();await page.locator('#analysis-losses [data-focus="16"]').click();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  assert.ok((await page.locator('#evo-chart').boundingBox()).width>=250);
  if(width<600){await page.locator('.analysis-position[data-key="12"]').tap();assert.equal(await page.locator('.analysis-position[data-key="12"]').getAttribute('aria-pressed'),'true');}
  await page.screenshot({path:`${OUT}/after-${width}.png`,fullPage:true});assert.deepEqual(errors,[]);report.push({width,positions:6,smallMultiples:6,negativeLeader:'DXC',errors});
 }
 await ctx.close();fs.writeFileSync(OUT+(process.env.REPRO_BEFORE==='1'?'/before.json':'/after.json'),JSON.stringify(report,null,2));console.log(report.at(-1));
}}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
