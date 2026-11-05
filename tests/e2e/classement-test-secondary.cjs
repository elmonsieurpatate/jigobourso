const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const BASE=process.env.BASE||'http://127.0.0.1:18121',OUT=process.env.AUDIT_OUT||'/tmp/classement-test-secondary';
assert.equal(new URL(BASE).hostname,'127.0.0.1');fs.mkdirSync(OUT,{recursive:true});
const fixture=JSON.parse(fs.readFileSync(path.join(__dirname,'../../app/config/classement_test_categories.json'),'utf8'));
// This deliberately differs from the proposed defaults: proves the UI reads admin configuration.
fixture.source='admin';fixture.source_label='Configuration administrateur de test';fixture.categories.volatility.bounds=[1,2,4];fixture.categories.volatility.labels[0]='Calme admin';
(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']}),report=[];
try{for(const theme of ['light','dark'])for(const width of [1440,1024,390,375]){
 const c=await b.newContext({viewport:{width,height:1000},isMobile:width<600,hasTouch:width<600}),calls=[];
 await c.route('**/api.php?**',r=>{const q=new URL(r.request().url()).searchParams.get('r');calls.push(q);assert.equal(r.request().method(),'GET');assert.ok(['auth/me','portfolios','explorer/secondary-filters'].includes(q));return r.fulfill({json:q==='auth/me'?{user:{username:'Test',is_admin:false,prefs:{theme}}}:q==='explorer/secondary-filters'?fixture:{portfolios:[]}});});
 const p=await c.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto(BASE+'/classement-test.html');await p.locator('[data-open-filter="volatility"]').waitFor({state:'attached'});
 assert.equal(await p.locator('#ct-filter-panel').evaluate(e=>e.open),false);await p.locator('#ct-filter-panel > summary').click();
 const total=await p.locator('[data-filter]').count();assert.equal(await p.locator('[data-filter]:checked').count(),total);
 await p.locator('[data-open-filter="volatility"]').click();assert.match(await p.locator('#ct-list-volatility').innerText(),/Calme admin/);assert.match(await p.locator('#ct-list-volatility').innerText(),/≤ 1 %/);
 await p.locator('[data-filter="volatility"][data-category="c0"]').uncheck();await p.locator('[data-filter="volatility"][data-category="c2"]').uncheck();assert.match(await p.locator('[data-count="volatility"]').innerText(),/3 \/ 5/);
 await p.locator('[data-category-search="volatility"]').fill('zzzz');assert.equal(await p.locator('#ct-list-volatility .ct-no-category').isVisible(),true);await p.locator('[data-category-search="volatility"]').fill('inconnu');assert.equal(await p.locator('#ct-list-volatility .ct-category-option:visible').count(),1);await p.locator('[data-category-search="volatility"]').fill('');
 const popup=await p.locator('#ct-list-volatility').boundingBox();assert.ok(popup.x>=0&&popup.x+popup.width<=width);assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await p.keyboard.press('Escape');assert.equal(await p.locator('[data-open-filter="volatility"]').getAttribute('aria-expanded'),'false');assert.equal(await p.locator('[data-open-filter="volatility"]').evaluate(e=>e===document.activeElement),true);
 await p.locator('[data-mode="expert"]').click();assert.equal(await p.locator('#ct-filter-panel').evaluate(e=>e.open),true);assert.equal(await p.locator('[data-filter="volatility"]:checked').count(),3);
 const controls=await p.locator('#ct-expert select').evaluateAll(es=>es.map(e=>{const s=getComputedStyle(e);return {repeat:s.backgroundRepeat,size:s.backgroundSize,color:s.color,bg:s.backgroundColor}}));assert.ok(controls.every(x=>x.repeat==='no-repeat'));assert.ok(controls.every(x=>x.size==='12px 8px'));assert.ok(controls.every(x=>x.color!==x.bg));
 // Every indicator can open without horizontal overflow, including the far-right one.
 const keys=Object.keys(fixture.categories);for(const key of [keys[0],keys[3],keys.at(-1)]){await p.locator('.ct-more-filters').evaluate(e=>e.open=true);await p.locator(`[data-open-filter="${key}"]`).click();const r=await p.locator(`#ct-list-${key}`).boundingBox();assert.ok(r.x>=0&&r.x+r.width<=width,`${key} outside viewport`);await p.keyboard.press('Escape');}
 await p.locator('#ct-reset-filters').click();assert.equal(await p.locator('[data-filter]:checked').count(),total);assert.equal(await p.locator('#ct-filter-panel').evaluate(e=>e.open),true);
 await p.locator('[data-open-filter="volatility"]').click();await p.locator('[data-filter="volatility"][data-category="c0"]').uncheck();await p.locator('#ct-all-filters').click();assert.equal(await p.locator('[data-filter]:checked').count(),total);
 assert.match(await p.locator('#ct-masked-count').innerText(),/^0 titre masqué$/);assert.equal(await p.locator('tbody tr').count(),10);assert.equal(await p.locator('#ct-filters input[type="number"],#ct-filters input[type="color"]').count(),0);
 await p.locator('[data-open-filter="volatility"]').click();await p.evaluate(()=>scrollTo(0,0));await p.screenshot({path:`${OUT}/${theme}-${width}.png`,fullPage:true});assert.deepEqual(errors,[]);report.push({theme,width,passed:true,categoryCount:total,apiCalls:calls});console.log(JSON.stringify(report.at(-1)));await c.close();
}}finally{await b.close();fs.writeFileSync(OUT+'/results.json',JSON.stringify(report,null,2));}})().catch(e=>{console.error(e);process.exitCode=1});
