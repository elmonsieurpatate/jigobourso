/* Real local integration/browser checks for market versus investment analysis. */
const assert=require('node:assert/strict'),fs=require('node:fs');
const{chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const BASE=process.env.BASE||'http://127.0.0.1:18090',OUT=process.env.AUDIT_OUT||'/tmp/jigobourso-analysis';
assert.equal(process.env.JIGO_TEST_DATABASE,'1');assert.equal(new URL(BASE).hostname,'127.0.0.1');fs.mkdirSync(OUT,{recursive:true});
(async()=>{const browser=await chromium.launch({executablePath:process.env.JIGO_CHROMIUM||'/usr/bin/chromium',args:['--no-sandbox']});const report=[];
try{for(const width of [1280,390,375]){
const ctx=await browser.newContext({viewport:{width,height:1000},isMobile:width<600,hasTouch:width<600});
await ctx.route('**/*',r=>new URL(r.request().url()).hostname==='127.0.0.1'?r.continue():r.abort());
assert.equal((await ctx.request.post(BASE+'/api.php?r=auth/login',{data:{username:'audit_portfolio',password:'audit-local-validation-2026'}})).status(),200);
const page=await ctx.newPage(),errors=[],result={width,checks:[]};page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(15000);
await page.goto(BASE+'/portefeuilles.html?id=1');await page.waitForFunction(()=>document.querySelector('#evo-note')&&!document.querySelector('#evo-chart .spinner'));
const hist=await(await ctx.request.get(BASE+'/api.php?r=portfolio/history&id=1')).json();
assert.ok(hist.market.dates[0]<hist.dates[0]);assert.equal(hist.trades.filter(t=>t.side==='buy'&&t.date==='2026-09-01').length,2);
await page.evaluate(()=>{const original=J.lineChart;J.lineChart=(host,xs,series,options)=>{if(host.id==='evo-chart')window.chart={xs,series,options:{time:!!options.time,markers:options.markers||[]}};return original(host,xs,series,options)}});
await page.locator('[data-view="analysis"]').click();
for(const period of ['1w','1m','3m','6m','1y','all','1d']){
 await page.locator(`#evo-per [data-v="${period}"]`).click();
 for(const scale of ['index','price']){
 await page.locator(`#market-scale [data-v="${scale}"]`).click();
 const c=await page.evaluate(()=>window.chart);assert.equal(c.series.length,3);assert.equal(c.options.time,period==='1d');
 if(scale==='index')for(const s of c.series)if(s.values[0]!==null)assert.equal(s.values[0],100);
 if(scale==='price')assert.ok(c.series.some(s=>s.label.includes('USD')));
 assert.ok((await page.locator('#evo-chart').boundingBox()).width>=250);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 for(const m of c.options.markers){assert.ok(m.x>=c.xs[0].slice(0,period==='1d'?19:10));assert.ok(m.x<=c.xs.at(-1).slice(0,period==='1d'?19:10))}
 result.checks.push(period+':'+scale);
 }
}
await page.locator('#evo-per [data-v="3m"]').click();await page.locator('#market-scale [data-v="index"]').click();
assert.equal(await page.locator('.lc-purchase-marker[data-date="2026-09-01"]').count(),1,'same-day buys grouped');
assert.equal(await page.getByRole('button',{name:'2026-09-01 · Achat DOLLAR, PENCE',exact:true}).count(),1);const marker=page.locator('.lc-purchase-marker[data-date="2026-09-01"]');await marker.focus();assert.match(await page.locator('#evo-chart .lc-tip').innerText(),/DOLLAR/);assert.match(await page.locator('#evo-chart .lc-tip').innerText(),/PENCE/);assert.match(await page.locator('#evo-chart .lc-tip').innerText(),/frais/);
await page.keyboard.press('Escape');assert.equal(await page.locator('#evo-chart .lc-tip').isVisible(),false);
if(width<600){await marker.scrollIntoViewIfNeeded();const rect=await marker.locator('rect').first().boundingBox();await page.touchscreen.tap(rect.x+rect.width/2,rect.y+rect.height/2);assert.equal(await page.locator('#evo-chart .lc-tip').isVisible(),true);assert.match(await page.locator('#evo-chart .lc-tip').innerText(),/prix/)}
await page.locator('#purchase-markers').uncheck();assert.equal(await page.locator('.lc-purchase-marker').count(),0);await page.locator('#purchase-markers').check();
await page.locator('#evo-per [data-v="1w"]').click();assert.equal(await page.locator('.lc-purchase-marker').count(),0);assert.match(await page.locator('#analysis-purchases').innerText(),/2025/);
await page.locator('#analysis-purchases details').first().locator('summary').click();assert.match(await page.locator('#analysis-purchases').innerText(),/2026/);
await page.locator('#evo-chart .lc-chip[data-id="market:1"]').click();assert.equal(await page.locator('#evo-chart path[data-series="market:1"]').count(),0);await page.locator('#analysis-purchases [data-focus="1"]').click();assert.equal(await page.locator('#evo-chart path[data-series="market:1"]').count(),1);assert.equal(await page.locator('#clear-focus').isVisible(),true);let c=await page.evaluate(()=>window.chart);assert.equal(c.series.find(s=>s.id==='market:1').opacity,1);assert.equal(c.series.find(s=>s.id==='market:2').opacity,.2);
await page.locator('#clear-focus').click();assert.equal(await page.locator('#clear-focus').isVisible(),false);
await page.locator('#evo-per [data-v="1m"]').click();
const rows=await page.locator('[data-loss]').evaluateAll(es=>es.map(e=>e.dataset.loss));const at=hist.dates.findLastIndex(d=>d<='2026-10-03'),last=hist.dates.length-1;
const expected=hist.lines.map(l=>({key:l.key,g:l.gain[last]-l.gain[at]})).filter(l=>l.g<0).sort((a,b)=>a.g-b.g).map(l=>l.key);assert.deepEqual(rows,expected);assert.ok(rows.length>0);assert.match(await page.locator('#analysis-losses').innerText(),/ventes comprises/);
await page.screenshot({path:`${OUT}/analysis-market-${width}.png`,fullPage:true});
await page.locator('#analysis-domain [data-v="personal"]').click();await page.locator('#evo-mode [data-v="titles"]').click();await page.locator('#evo-unit [data-v="eur"]').click();
c=await page.evaluate(()=>window.chart);assert.equal(c.series[0].values.at(-1),hist.gain.at(-1));assert.match(await page.locator('#period-reference').innerText(),/depuis vos achats/);
await page.locator('#personal-reference').selectOption('period');c=await page.evaluate(()=>window.chart);assert.equal(c.series[0].values.at(-1),hist.gain[last]-hist.gain[at]);assert.notEqual(c.series[0].values.at(-1),hist.gain[last]);
await page.locator('#evo-per [data-v="1d"]').click();assert.equal(await page.locator('#evo-mode [data-v="titles"]').isDisabled(),true);assert.match(await page.locator('#analysis-losses').innerText(),/indisponibles en 1 J/);
await page.locator('#analysis-domain [data-v="market"]').click();assert.ok((await page.evaluate(()=>window.chart)).series.some(s=>s.values.length>1));
await page.locator('#evo-per [data-v="all"]').click();await page.locator('#market-scale [data-v="index"]').click();assert.match(await page.locator('#evo-note').innerText(),/rupture non résolue/);
await page.locator('#pf-select').selectOption('7');await page.waitForFunction(()=>document.querySelector('#analysis-losses')?.textContent.includes('partielles'));assert.equal(await page.locator('#analysis-domain [data-v="market"]').getAttribute('aria-pressed'),'true');
await page.locator('#pf-select').selectOption('3');await page.waitForFunction(()=>document.querySelectorAll('#analysis-purchases .purchase-group').length===1 && document.querySelector('#analysis-purchases')?.textContent.includes('ALPHA'));await page.locator('#analysis-domain [data-v="personal"]').click();await page.locator('#evo-mode [data-v="titles"]').click();assert.equal((await page.evaluate(()=>window.chart)).series[0].values.at(-1),20);
await page.locator('#pf-select').selectOption('8');await page.waitForFunction(()=>document.querySelector('#analysis-purchases')?.textContent.includes('Frais du premier achat 1,00'));
await page.locator('#analysis-domain [data-v="market"]').click();await page.locator('#evo-per [data-v="1d"]').click();await page.locator('#evo-chart .lc-purchase-marker').waitFor();
const intra=await page.evaluate(()=>window.chart);assert.equal(intra.options.markers.length,1);assert.ok(intra.options.markers[0].x.endsWith('09:15:00'));await page.locator('#evo-chart .lc-purchase-marker').focus();assert.match(await page.locator('#evo-chart .lc-tip').innerText(),/1,0000 titre/);result.checks.push('intraday-real-purchase-time');
result.checks.push('before-first-buy','grouped-markers','keyboard-tooltip','touch-tooltip','marker-toggle','outside-period-history','focus-curve','negative-euro-ranking','cumulative-vs-period','1d-explicit','unreliable-series','missing-quotes','fully-sold-gain');assert.deepEqual(errors,[]);result.errors=errors;report.push(result);fs.writeFileSync(OUT+'/results.json',JSON.stringify(report,null,2));await ctx.close();console.log('analysis passed',width);
}}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
