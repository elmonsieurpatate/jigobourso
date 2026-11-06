/* Real DOM interactions; only shell reads are stubbed. No financial engine or database. */
const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const categoryConfig=JSON.parse(fs.readFileSync(require('node:path').join(__dirname,'../../app/config/classement_test_categories.json'),'utf8'));
const BASE=process.env.BASE||'http://127.0.0.1:18121',OUT=process.env.AUDIT_OUT||'/tmp/classement-test-builder';
assert.equal(new URL(BASE).hostname,'127.0.0.1');fs.mkdirSync(OUT,{recursive:true});
(async()=>{const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']}),report=[];
try{for(const width of [1440,1280,1024,850,768,390,375]){
 const context=await browser.newContext({viewport:{width,height:1000},isMobile:width<600,hasTouch:width<600}),calls=[];
 await context.route('**/api.php?**',async route=>{const req=route.request(),r=new URL(req.url()).searchParams.get('r');calls.push({r,method:req.method()});assert.equal(req.method(),'GET');assert.ok(['auth/me','portfolios','explorer/secondary-filters'].includes(r));await route.fulfill({json:r==='auth/me'?{user:{id:1,username:'Test local',is_admin:false,prefs:{theme:'light'}}}:r==='explorer/secondary-filters'?{...categoryConfig,source:'admin',source_label:'Configuration administrateur de test'}:{portfolios:[]}});});
 const p=await context.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));
 const row=(metric,period)=>p.locator(`.ct-builder-row:has(select[data-rule-field="metric"] option[value="${metric}"]:checked):has(select[data-rule-field="period"] option[value="${period}"]:checked)`);
 const mode=async m=>p.locator(`[data-mode="${m}"]`).click();
 await p.goto(BASE+'/classement-test.html');await p.locator('.ct-period').first().waitFor();
 assert.equal(await p.locator('.ct-period.active').count(),2);
 await p.locator('#ct-value-slope').fill('0.32');await p.locator('#ct-value-slope').dispatchEvent('change');
 await p.locator('[data-period="month"]').click();await p.locator('#ct-value-r2').fill('0.84');await p.locator('#ct-value-r2').dispatchEvent('change');
 await mode('expert');assert.equal(await p.locator('.ct-builder-row').count(),4);
 assert.equal(await row('slope','week').locator('input').inputValue(),'0.32');assert.equal(await row('r2','month').locator('input').inputValue(),'0.84');
 await row('slope','month').locator('input').fill('0.27');await row('slope','month').locator('input').dispatchEvent('change');
 assert.match(await p.locator('#ct-preview').innerText(),/0,27/);
 await row('slope','week').locator('.ct-rule-remove').click();await row('r2','week').locator('.ct-rule-remove').click();
 // A real nested group, with independently editable fields and period selectors.
 await p.locator('[data-add-group=""]').click();assert.equal(await p.locator('.ct-builder-group.nested').count(),1);
 await p.locator('[data-group-join]').nth(1).selectOption('or');
 await row('drawdown','month').locator('select[data-rule-field="period"]').selectOption('quarter');
 await row('drawdown','quarter').locator('select[data-rule-field="op"]').selectOption('<');
 assert.match(await p.locator('#ct-preview').innerText(),/AU MOINS UNE/);
 assert.match(await p.locator('#ct-preview').innerText(),/Trimestre/);
 await mode('simple');assert.equal(await p.locator('[data-enabled="week"]').isChecked(),false);assert.equal(await p.locator('#ct-value-slope').inputValue(),'0.27');assert.match(await p.locator('#ct-extra-note').innerText(),/2 critère/);
 await p.locator('[data-enabled="quarter"]').check();
 await mode('expert');assert.equal(await row('slope','quarter').count(),1);assert.equal(await row('r2','quarter').count(),1);
 // An OR across primary periods is not flattened into a false simple AND.
 await p.locator('[data-group-join=""]').selectOption('or');await mode('simple');assert.equal(await p.locator('#ct-value-slope').isDisabled(),true);assert.match(await p.locator('#ct-extra-note').innerText(),/verrouillés/);
 await mode('expert');assert.equal(await p.locator('[data-group-join=""]').inputValue(),'or');await p.locator('[data-group-join=""]').selectOption('and');
 // Changing the metric is supported, not a fixed label in a static form.
 await row('volatility','month').locator('[data-rule-field="metric"]').selectOption('return');assert.equal(await row('return','month').count(),1);await row('return','month').locator('[data-rule-field="metric"]').selectOption('volatility');
 // Deeper nesting remains editable and removable.
 await p.locator('[data-add-group]').nth(1).click();assert.equal(await p.locator('.ct-builder-group.nested').count(),2);await p.locator('.ct-delete-group').last().click();assert.equal(await p.locator('.ct-builder-group.nested').count(),1);
 const bounds=await p.locator('#ct-expert').evaluate(root=>[...root.querySelectorAll('input,select,button,aside')].filter(e=>e.getBoundingClientRect().width).map(e=>{const r=e.getBoundingClientRect();return {left:r.left,right:r.right,width:r.width}}));assert.ok(bounds.every(r=>r.left>=0&&r.right<=width&&r.width>=24),JSON.stringify(bounds));
 await p.locator('#ct-filter-panel > summary').click();await p.locator('[data-open-filter="turnover_eur"]').click();await p.locator('[data-filter="turnover_eur"][data-category="c0"]').uncheck();await p.locator('[data-filter="turnover_eur"][data-category="c2"]').uncheck();assert.equal(await p.locator('[data-filter="turnover_eur"]:checked').count(),3);await p.keyboard.press('Escape');
 await p.locator('.ct-columns summary').click();await p.locator('[data-column="5"]').check();await p.locator('.ct-columns summary').click();assert.match(await p.locator('#ct-table-head').innerText(),/volatilité/i);
 await p.locator('#ct-save').click();await p.reload();await p.locator('.ct-builder-row').first().waitFor();assert.equal(await p.locator('.ct-builder-group.nested').count(),1);assert.equal(await p.locator('[data-group-join]').nth(1).inputValue(),'or');assert.equal(await row('drawdown','quarter').locator('[data-rule-field="op"]').inputValue(),'<');
 await mode('simple');await p.locator('#ct-strategy').selectOption('regular');await p.locator('#ct-strategy').selectOption('fast');await p.locator('[data-period="month"]').click();assert.equal(await p.locator('#ct-value-slope').inputValue(),'0.27');
 await mode('expert');await p.locator('#ct-apply').click();assert.equal(await p.locator('tbody tr').count(),10);assert.match(await p.locator('#ct-feedback').innerText(),/données fictives/);
 await p.evaluate(()=>{document.querySelector('#ct-feedback').textContent='';scrollTo(0,0)});
 assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[]);assert.equal(await p.evaluate(()=>localStorage.getItem('jigo_explorer2')),null);
 await p.screenshot({path:`${OUT}/expert-${width}.png`,fullPage:true});
 report.push({width,passed:true,checks:['editable-indicator-operator-value-period','nested-AND-OR-groups','live-preview','simple-expert-sync','complex-primary-logic-preserved','group-delete','per-period-activation','local-save-reload-tree','multiselect-and-columns','no-overflow','no-engine-or-write-API'],apiCalls:calls,errors});console.log(JSON.stringify(report.at(-1)));await context.close();
}}finally{await browser.close();fs.writeFileSync(OUT+'/results.json',JSON.stringify(report,null,2));}})().catch(e=>{console.error(e);process.exitCode=1});
