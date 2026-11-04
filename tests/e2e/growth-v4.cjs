/* Real PHP/MariaDB, synthetic prices only. Localhost is mandatory. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'/opt/codex/cua_node/lib/node_modules/playwright-core');
const assert=require('node:assert/strict'),fs=require('node:fs');
const BASE=process.env.BASE||'http://127.0.0.1:18093',OUT=process.env.SHOTS||'/tmp/growth-v4';
assert.equal(new URL(BASE).hostname,'127.0.0.1');assert.equal(process.env.JIGO_TEST_DATABASE,'1');fs.mkdirSync(OUT,{recursive:true});
(async()=>{const browser=await chromium.launch({executablePath:process.env.JIGO_CHROMIUM||'/usr/bin/chromium',args:['--no-sandbox']});const report=[];
try{for(const width of [1280,390,375]){
 const ctx=await browser.newContext({viewport:{width,height:950},hasTouch:width<600});await ctx.route('**/*',r=>new URL(r.request().url()).hostname==='127.0.0.1'?r.continue():r.abort());
 const p=await ctx.newPage(),errors=[];let calculations=0,last; p.on('pageerror',e=>errors.push(e.message));p.on('response',async r=>{if(new URL(r.url()).searchParams.get('r')==='explore'){calculations++;if(r.status()===200)last=await r.json();}});
 p.setDefaultTimeout(45000);
 const ready=()=>p.waitForFunction(()=>document.querySelector('#g-results')?.getAttribute('aria-busy')==='false');
 const action=async(fn)=>{const r=p.waitForResponse(r=>new URL(r.url()).searchParams.get('r')==='explore');await fn();const res=await r;assert.equal(res.status(),200,await res.text());await ready();return res.json();};
 await p.goto(BASE+'/login.html');await p.fill('#u','explorer_review');await p.fill('#p','synthetic-local-password');await p.click('#auth-form button.primary');await p.waitForURL('**/index.html');await ready();
 if(width===1280)assert.equal(await p.locator('#g-strategy option').count(),1);assert.equal(await p.locator('#g-strategy option[value^="builtin:"]').count(),0);assert(await p.locator('[data-period="week"]').isChecked());assert(await p.locator('[data-period="month"]').isChecked());assert(!await p.locator('[data-period="quarter"]').isChecked());assert.equal(await p.locator('[data-primary]').count(),4);
 assert(last.counts.retained>=3,JSON.stringify(last.counts));assert.equal(last.counts.secondary_masked,0);
 const before=calculations;await p.locator('[data-pid="week"][data-primary="min_slope"]').fill('.09');await p.selectOption('#g-mode','advanced');assert.equal(calculations,before);assert(await p.locator('#g-query').isVisible());assert.equal(await p.getByRole('button',{name:'Appliquer',exact:true}).count(),1);
 await p.check('#g-day');await p.fill('#g-day-return','0');const filtered=await action(()=>p.click('#g-apply'));assert(filtered.rows.every(r=>r.measures['1'].perf>=0));
 await p.click('#g-original');await action(()=>p.click('#g-apply'));await p.selectOption('#g-mode','simple');
 const original=last.rows.find(r=>r.status==='retained');assert(original.scores.simple!=null&&original.scores.complex!=null);
 const details=p.locator('details').filter({has:p.locator('#g-filters')});await details.evaluate(el=>el.open=true);
 await p.locator('[data-category="volatility"][value="c0"]').uncheck();const masked=await action(()=>p.click('#g-filter-apply'));assert(masked.counts.secondary_masked>0);
 const restored=await action(()=>p.click('#g-all'));assert.equal(restored.counts.secondary_masked,0);assert.equal(restored.rows.find(r=>r.id===original.id).scores.simple,original.scores.simple);
 await action(()=>p.selectOption('#g-sort','complex'));
 const rowId=original.id;await p.locator(`[data-detail="${rowId}"]`).click();const dialog=p.locator('dialog[open]');await dialog.waitFor();assert((await dialog.innerText()).includes('Comparaison V1'));assert(/risque|risk/i.test(await dialog.innerText()));if(width===1280){const wait=p.waitForEvent('download');await dialog.locator('#g-snapshot').click();await (await wait).saveAs(OUT+'/market-snapshot.json');}const chart=await dialog.locator('#g-detail-chart').boundingBox();assert(chart.width>200,JSON.stringify(chart));assert.equal(await dialog.evaluate(el=>el.scrollWidth>el.clientWidth+1),false);await dialog.locator('#g-detail-chart').scrollIntoViewIfNeeded();await p.screenshot({path:OUT+`/detail-${width}.png`,fullPage:false});await p.keyboard.press('Escape');
 await p.click('#g-library-open');await p.fill('#g-save-name','V4 navigateur '+width);await p.click('#g-save');await p.waitForFunction(()=>document.querySelector('#g-message').textContent.includes('enregistrée'));
 const item=p.locator('#g-library-items article').filter({hasText:'V4 navigateur '+width});await item.getByRole('button',{name:'Archiver',exact:true}).click();await p.waitForFunction(()=>document.querySelector('#g-library-items').textContent.includes('Archivée'));await item.getByRole('button',{name:'Réactiver',exact:true}).click();await p.waitForFunction(()=>!document.querySelector('#g-library-items').textContent.includes('Archivée'));
 await p.reload();await ready();assert.deepEqual(await p.selectOption('#g-mode','advanced'),['advanced']);await p.selectOption('#g-mode','simple');
 await p.fill('#g-query','SYN2');const search=await action(()=>p.click('#g-apply'));assert(search.rows.some(r=>r.symbol==='SYN2'&&r.status==='rejected'));
 assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[]);
 await p.fill('#g-query','');await action(()=>p.click('#g-apply'));await p.screenshot({path:OUT+`/explorer-${width}.png`,fullPage:true});
 if(width===1280){await p.goto(BASE+'/admin.html#explorer');await p.locator('#ga-preview').waitFor();await p.locator('[data-weight="simple:force"]').fill('99');await p.click('#ga-preview');await p.waitForFunction(()=>document.querySelector('#ga-message').textContent.includes('100'));await p.click('#ga-reset');await p.click('#ga-preview');await p.waitForFunction(()=>document.querySelector('#ga-message').textContent.includes('Configuration valide'));await p.screenshot({path:OUT+'/admin-preview.png',fullPage:true});}
 report.push({width,ok:true,checks:['default-week-month','two-primary-controls','draft-no-heavy-call','advanced-last-day','filters-reversible-score-stable','two-scores','v1-reasons','mobile-chart-width','archive-reactivate','preferences','rejected-search','no-horizontal-overflow'],errors});console.log(JSON.stringify(report.at(-1)));await ctx.close();
}}finally{await browser.close();fs.writeFileSync(OUT+'/results.json',JSON.stringify(report,null,2));}})().catch(e=>{console.error(e);process.exitCode=1;});
