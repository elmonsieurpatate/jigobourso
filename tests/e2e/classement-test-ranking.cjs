const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const UI=require('./classement-test-harness.cjs');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const BASE=process.env.BASE||'http://127.0.0.1:18121',OUT=process.env.AUDIT_OUT||'/tmp/classement-test-ranking';
assert.equal(new URL(BASE).hostname,'127.0.0.1');fs.mkdirSync(OUT,{recursive:true});
const root=path.join(__dirname,'../..'),payload=JSON.parse(fs.readFileSync(path.join(root,'app/config/classement_test_categories.json'),'utf8'));
const env={window:{},Intl};for(const file of ['classement-test-filters.js','classement-test-demo.js'])vm.runInNewContext(fs.readFileSync(path.join(root,'app/public/assets',file),'utf8'),env);
const source=env.window.ClassementTestDemo.rows(payload),before=JSON.stringify(source),F=env.window.ClassementTestSecondary,cats=F.normalize(payload);
assert.equal(source.length,30);assert.ok(Object.isFrozen(source)&&Object.isFrozen(source[0]));
const chosen=F.all(cats);chosen.volatility=['c0'];const expectedIds=Array.from(F.apply(source,chosen,cats),r=>r.id);
assert.ok(expectedIds.length>0&&expectedIds.length<30);assert.equal(JSON.stringify(source),before);
(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']}),report=[];
try{for(const theme of ['light','dark'])for(const width of [1440,1280,390,375]){
 const c=await b.newContext({viewport:{width,height:1100},isMobile:width<600,hasTouch:width<600}),calls=[];
 await c.route('**/api.php?**',r=>{const route=new URL(r.request().url()).searchParams.get('r');calls.push(route);assert.equal(r.request().method(),'GET');assert.ok(['auth/me','portfolios','explorer/secondary-filters'].includes(route));return r.fulfill({json:route==='auth/me'?{user:{username:'Test',prefs:{theme}}}:route==='explorer/secondary-filters'?payload:{portfolios:[]}});});
 const p=await c.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto(BASE+'/classement-test.html');await p.locator('[data-demo-row]').first().waitFor();
 if(width<700){await UI.options(p);await p.locator('#ct-full-view').check();await p.locator('.ct-options>summary').click();}
 const ids=async()=>p.locator('[data-demo-row]').evaluateAll(es=>es.map(e=>Number(e.dataset.demoRow)));
 assert.equal(await p.locator('[data-demo-row]').count(),10);assert.deepEqual(await ids(),Array.from({length:10},(_,i)=>i+1));assert.match(await p.locator('#ct-result-count').innerText(),/30 titres/);assert.equal(await p.locator('.ct-demo-badge').innerText(),'Données fictives');
 await p.getByRole('button',{name:'Page 2',exact:true}).click();assert.deepEqual(await ids(),Array.from({length:10},(_,i)=>i+11));
 await UI.settings(p);await p.locator('[data-mode="expert"]').click();await UI.close(p);assert.deepEqual(await ids(),Array.from({length:10},(_,i)=>i+11),'Mode switch keeps table page');
 await p.getByRole('button',{name:'Page 3',exact:true}).click();assert.equal(await p.locator('[data-demo-row="30"] .ct-cell-price').innerText(),'—');assert.equal(await p.locator('[data-demo-row="30"] .ct-cell-trend').innerText(),'Indisponible');
 await UI.size(p,'20');assert.equal(await p.locator('[data-demo-row]').count(),20);
 await p.locator('#ct-sort').selectOption('price');await p.locator('#ct-sort-direction').click();assert.equal((await ids())[0],27); // Cheapest known fictitious price; nulls stay last.
 await UI.size(p,'50');assert.equal((await ids()).at(-1),30);
 await p.locator('#ct-sort').selectOption('score');assert.deepEqual(await ids(),Array.from({length:30},(_,i)=>i+1));
 if(width>700){await p.locator('[data-sort-column="score"]').click();assert.equal((await ids())[0],30);await p.locator('[data-sort-column="score"]').click();assert.equal((await ids())[0],1);}
 await UI.options(p);await p.locator('.ct-columns summary').click();await p.locator('[data-column="5"]').uncheck();assert.equal(await p.locator('.ct-cell-volatility').count(),0);await p.locator('[data-column="5"]').check();assert.equal(await p.locator('.ct-cell-volatility').count(),30);await p.locator('.ct-columns summary').click();await p.locator('.ct-options>summary').click();
 await p.locator('[data-demo-details="1"]').click();assert.match(await p.locator('dialog[open]').innerText(),/inventées/);await p.locator('dialog .foot').getByRole('button',{name:'Fermer',exact:true}).click();
 const snapshot=await ids();await UI.settings(p);await p.locator('#ct-strategy').selectOption('calm');await p.locator('#ct-apply').click();assert.deepEqual(await ids(),snapshot,'No primary rule or strategy calculation');
 await UI.settings(p,'filters');await p.locator('[data-open-filter="volatility"]').click();for(const id of ['c1','c2','c3','unknown'])await p.locator(`[data-filter="volatility"][data-category="${id}"]`).uncheck();
 await p.locator('#ct-apply').click();assert.deepEqual(await ids(),expectedIds);assert.equal(await p.locator('#ct-masked-count').innerText(),`${30-expectedIds.length} titres masqués`);
 const scores=await p.locator('[data-demo-row]').evaluateAll(es=>es.map(e=>({id:Number(e.dataset.demoRow),rank:Number(e.querySelector('.ct-rank-cell').textContent),score:Number(e.querySelector('.ct-score').textContent)})));
 for(const actual of scores){const row=source.find(r=>r.id===actual.id);assert.equal(actual.rank,row.rank);assert.equal(actual.score,row.score);}
 await UI.settings(p,'filters');await p.locator('[data-open-filter="volatility"]').click();await p.locator('[data-filter="volatility"][data-category="c0"]').uncheck();await p.locator('#ct-apply').click();assert.equal(await p.locator('[data-demo-row]').count(),0);assert.equal(await p.locator('#ct-empty-results').isVisible(),true);await p.keyboard.press('Escape');
 await p.locator('#ct-show-demo-all').click();assert.equal(await p.locator('[data-demo-row]').count(),30);assert.equal(await p.locator('#ct-masked-count').innerText(),'0 titre masqué');
 await UI.size(p,'10');await UI.settings(p,'filters');await p.evaluate(()=>{document.querySelector('#ct-feedback').textContent='';scrollTo(0,0)});
 assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 if(width<700){assert.equal(await p.locator('.ct-table-wrap').evaluate(e=>e.scrollWidth>e.clientWidth),true);assert.equal(await p.locator('[data-demo-row]').first().evaluate(e=>getComputedStyle(e).display),'table-row');}
 assert.deepEqual(errors,[]);await p.screenshot({path:`${OUT}/${theme}-${width}.png`,fullPage:true});report.push({theme,width,passed:true,checks:['30-labelled-fictitious-rows','page-navigation','nulls-last','sort-both-directions','columns','row-details','primary-form-independent','secondary-masking-counts','scores-and-intrinsic-rank-preserved','zero-state-reset','responsive-no-overflow'],apiCalls:calls});console.log(JSON.stringify(report.at(-1)));await c.close();
}}finally{await b.close();fs.writeFileSync(OUT+'/results.json',JSON.stringify(report,null,2));}})().catch(e=>{console.error(e);process.exitCode=1});
