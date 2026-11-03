/* Six financial regressions retained across the two-space portfolio UI. */
const assert=require('node:assert/strict'),fs=require('node:fs');const{chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const BASE=process.env.BASE||'http://127.0.0.1:18090',OUT=process.env.AUDIT_OUT||'/tmp/jigobourso-portfolio-regression';
assert.equal(process.env.JIGO_TEST_DATABASE,'1');assert.equal(new URL(BASE).hostname,'127.0.0.1');fs.mkdirSync(OUT,{recursive:true});
(async()=>{const b=await chromium.launch({executablePath:process.env.JIGO_CHROMIUM||'/usr/bin/chromium',args:['--no-sandbox']}),report=[];
try{for(const width of [1280,390,375]){
 const ctx=await b.newContext({viewport:{width,height:1000},isMobile:width<600,hasTouch:width<600});await ctx.route('**/*',r=>new URL(r.request().url()).hostname==='127.0.0.1'?r.continue():r.abort());assert.equal((await ctx.request.post(BASE+'/api.php?r=auth/login',{data:{username:'audit_portfolio',password:'audit-local-validation-2026'}})).status(),200);
 const page=await ctx.newPage(),errors=[],checks=[];page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(15000);
 const get=async(route,id)=>(await ctx.request.get(BASE+'/api.php?r='+route+'&id='+id)).json();
 const open=async id=>{await page.goto(BASE+'/portefeuilles.html?id='+id);await page.locator('#positions-table tbody').waitFor();};
 await open(1);const history=await get('portfolio/history',1);
 await page.waitForFunction(()=>document.querySelector('#evo-chart')?._financial);
 let minWidth=Infinity;
 for(const period of ['1w','1m','3m','6m','1y','all']){
  await page.locator(`#global-per [data-v="${period}"]`).click();
  for(const mode of ['personal','contribution'])for(const unit of ['eur','pct']){
   await page.locator('#chart-measure').selectOption(mode);await page.locator(`#evo-unit [data-v="${unit}"]`).click();
   const c=await page.evaluate(()=>{const d=document.querySelector('#evo-chart')._financial.getState().data;return {series:d.series,xs:d.times.map(t=>new Date(t*1000).toISOString().slice(0,10))}}),svg=await page.locator('.fc-plot').boundingBox();assert.ok(svg.width>=250);minWidth=Math.min(minWidth,svg.width);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   const i0=history.dates.indexOf(c.xs[0]),last=history.dates.length-1;
   const oracle=l=>{const gain=l.gain[last]-(i0?l.gain[i0]:0),base=(i0?(l.values||l.value)[i0]:0)+l.purchases[last]-(i0?l.purchases[i0]:0);return unit==='eur'?gain:base>0?100*gain/base:null};
   assert.ok(Math.abs(c.series.find(s=>s.id==='portfolio').values.at(-1)-oracle(history))<1e-8);for(const line of history.lines){const expected=mode==='contribution'&&unit==='pct'?100*(line.gain[last]-(i0?line.gain[i0]:0))/((i0?history.value[i0]:0)+history.purchases[last]-(i0?history.purchases[i0]:0)):oracle(line);assert.ok(Math.abs(c.series.find(s=>s.id===line.key).values.at(-1)-expected)<1e-8);}
   const contributions=await page.locator('[data-contribution]').evaluateAll(es=>es.map(e=>Number(e.dataset.eur)));const sum=contributions.reduce((a,b)=>a+b,0),expected=history.gain[last]-(i0?history.gain[i0]:0);assert.ok(Math.abs(sum-expected)<.031);
   if(period==='all'&&unit==='pct')assert.ok(Math.abs(c.series[0].values.at(-1)-100*233.4/3942)<.001,'purchases denominator, sales not subtracted');
   checks.push({period,mode,unit});
  }
 }
 await page.locator('#global-per [data-v="1d"]').click();const session=(await get('portfolio/history',1)).session;const chart=await page.evaluate(()=>document.querySelector('#evo-chart')._financial.getState().data);assert.ok(Math.abs(chart.series.find(s=>s.id==='portfolio').values.at(-1)-session.pct.at(-1))<1e-8);assert.match(await page.locator('#period-g').innerText(),/Indicatif/);checks.push({period:'1d',mode:'personal',unit:'pct'});
 // Momentum retains points of percent; FIFO lots follow a split without later transactions.
 const data=await get('portfolio',1);const alpha=data.lots.find(l=>l.symbol==='ALPHA');assert.equal(alpha.alert.alerts.find(a=>a.kind==='momentum').value,-.1);assert.equal(data.insights.L1.protection.cost_eur,2265);
 const split=await get('portfolio',2);assert.equal(split.positions[0].qty,20);assert.equal(split.lots.reduce((s,l)=>s+l.remaining,0),20);assert.equal(split.totals.cost,1000);assert.equal(split.totals.total_gain,200);
 await open(3);await page.locator('#chart-measure').selectOption('personal');assert.match(await page.locator('#period-g').innerText(),/20,00/);assert.match(await page.locator('.hero-g').innerText(),/20,00/);
 await open(4);const missing=await get('portfolio',4),hist=await get('portfolio/history',4);assert.equal(missing.positions[0].price,null);assert.equal(hist.gain.at(-1),null);assert.equal(hist.value.at(-1),null);assert.equal(await page.locator('.hero-v').innerText(),'–');assert.match(await page.locator('#contributions').innerText(),/non calculable/);
 assert.deepEqual(errors,[]);report.push({width,combinations:checks.length,minGraphWidth:minWidth,errors});fs.writeFileSync(OUT+'/results.json',JSON.stringify(report,null,2));console.log(report.at(-1));await ctx.close();
}}finally{await b.close()}})().catch(e=>{console.error(e);process.exitCode=1});
