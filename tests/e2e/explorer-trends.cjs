/* Real ranking curves: visibility and longest active strategy period, desktop/mobile. */
const assert=require('node:assert/strict'),fs=require('node:fs');
const{chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const BASE=process.env.BASE||'http://127.0.0.1:18089',OUT=process.env.AUDIT_OUT||'/tmp/explorer-trends';
assert.equal(process.env.JIGO_TEST_DATABASE,'1');assert.equal(new URL(BASE).hostname,'127.0.0.1');fs.mkdirSync(OUT,{recursive:true});
(async()=>{const browser=await chromium.launch({executablePath:process.env.JIGO_CHROMIUM||'/usr/bin/chromium',args:['--no-sandbox']}),report=[];
try{for(const width of [1280,860,390,375]){
 const ctx=await browser.newContext({viewport:{width,height:900}});await ctx.route('**/*',r=>new URL(r.request().url()).hostname==='127.0.0.1'?r.continue():r.abort());
 assert.equal((await ctx.request.post(BASE+'/api.php?r=auth/login',{data:{username:'review_user',password:'review-local-password'}})).status(),200);
 const p=await ctx.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));p.setDefaultTimeout(15000);
 await p.goto(BASE+'/index.html');await p.locator('.rtable tbody tr').first().waitFor();
 const selector=width<=860?'.trend-mobile':'.trend-column';const checks=[];
 for(const[preset,label,sessions]of [['regular','3 mois',63],['fast','1 mois',21],['momentum12','1 an',252]]){
  await p.locator(`.strat[data-k="${preset}"]`).click();await p.locator('#status-tabs [data-s="all"]').click();
  await p.waitForFunction(({selector,label})=>{const e=document.querySelector('.rtable tbody '+selector+' small');return e&&e.textContent===label},{selector,label});
  const curve=p.locator('.rtable tbody '+selector+' .spark').first();await curve.waitFor({state:'visible'});const box=await curve.boundingBox();assert.ok(box.width>=119&&box.height>=33);
  const id=await p.locator('.rtable tbody tr').first().getAttribute('data-id');
  const data=await p.evaluate(async()=>J.post('explore',{config:JSON.parse(localStorage.getItem('jigo_explorer2')).config,view:{status:'all',tradable:false,page_size:100}}));
  assert.equal(data.ref_sessions,sessions);assert.equal(data.curve_label,label);const row=data.rows.find(r=>String(r.id)===id);assert.ok(row&&row.curve.length>1);
  assert.equal(await curve.locator('path').last().getAttribute('d'),await p.evaluate(values=>{const el=document.createElement('div');el.innerHTML=J.spark(values);return el.querySelector('path:last-child').getAttribute('d')},row.curve));
  checks.push({preset,label,sessions,width:box.width});
 }
 assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[]);await p.screenshot({path:`${OUT}/trends-${width}.png`});report.push({width,checks,errors});console.log(JSON.stringify(report.at(-1)));await ctx.close();
}}finally{await browser.close();fs.writeFileSync(OUT+'/results.json',JSON.stringify(report,null,2))}})().catch(e=>{console.error(e);process.exitCode=1});
