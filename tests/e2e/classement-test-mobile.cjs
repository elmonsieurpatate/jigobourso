/* Mobile regression: actual table geometry and filter focus, not just page overflow. */
const assert=require('node:assert/strict'),fs=require('node:fs'),cp=require('node:child_process');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const BASE=process.env.BASE||'http://127.0.0.1:18121',OUT=process.env.AUDIT_OUT||'/tmp/jigo-mobile-regression';
assert.equal(new URL(BASE).hostname,'127.0.0.1');fs.mkdirSync(OUT,{recursive:true});
const definitions=JSON.parse(fs.readFileSync('app/config/explorer_secondary_filters.json','utf8'));
const mapping=JSON.parse(fs.readFileSync('app/config/secondary_metadata_groups.json','utf8'));
const defaults={filters:{}};for(const f of definitions.filters){defaults.filters[f.id]={};for(const m of f.measures)defaults.filters[f.id][m.id]={mode:'all',selected:[]};if(!f.editable){f.values=mapping.groups[f.id].map(v=>({...v,value:v.id==='unknown'?null:v.id}));defaults.filters[f.id].values={mode:'all',selected:[]};}}
const payload={schema:2,definitions,defaults,metadata_mapping:mapping,source_label:'Configuration de test'};
(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']}),reports=[];
try{for(const phase of(process.env.REPRODUCE_MOBILE_BASELINE?['before','after']:['after']))for(const theme of['light','dark'])for(const width of[375,390,430,1280]){
 const context=await b.newContext({viewport:{width,height:850},isMobile:width<700,hasTouch:width<700,deviceScaleFactor:width<700?3:1});
 await context.route('**/api.php?**',r=>{const key=new URL(r.request().url()).searchParams.get('r');assert.equal(r.request().method(),'GET');return r.fulfill({json:key==='auth/me'?{user:{id:7,username:'Mobile',prefs:{theme}}}:key==='explorer/secondary-filters'?payload:{portfolios:[]}});});
 if(phase==='before')for(const file of['classement-test.css','classement-test.js'])await context.route('**/assets/'+file+'?*',r=>r.fulfill({contentType:file.endsWith('.css')?'text/css':'application/javascript',body:cp.execFileSync('git',['show','a47f8ca:app/public/assets/'+file],{encoding:'utf8'})}));
 const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(BASE+'/classement-test.html');await page.locator('[data-demo-row]').first().waitFor();
 const geometry=await page.locator('[data-demo-row]').first().evaluate(row=>({height:row.getBoundingClientRect().height,display:getComputedStyle(row).display,head:getComputedStyle(document.querySelector('.ct-ranking thead')).display,overflow:document.documentElement.scrollWidth>innerWidth}));
 if(width<700){if(phase==='before'){assert.equal(geometry.display,'grid');assert.ok(geometry.height>200);}else{
  assert.equal(geometry.display,'table-row');assert.ok(geometry.height<=60,JSON.stringify(geometry));assert.equal(geometry.head,'table-header-group');assert.equal(geometry.overflow,false);
  const wrap=page.locator('.ct-ranking .ct-table-wrap');assert.ok(await wrap.evaluate(el=>el.scrollWidth>el.clientWidth));await wrap.evaluate(el=>{el.scrollLeft=260;});
  const title=await page.locator('td.ct-cell-name').first().boundingBox(),box=await wrap.boundingBox();assert.ok(Math.abs(title.x-box.x)<=2,JSON.stringify({title,box}));await wrap.evaluate(el=>{el.scrollLeft=0;});
 }}
 await page.locator('.ct-ranking').scrollIntoViewIfNeeded();await page.locator('.ct-ranking').screenshot({path:`${OUT}/${phase}-${theme}-${width}-ranking.png`});
 await page.locator('#ct-filter-panel > summary').click();await page.locator('[data-open-filter="volatility"]').click();
 const search=page.locator('#ct-list-volatility input[type=search]');const focus=await search.evaluate(el=>({automatic:document.activeElement===el,size:parseFloat(getComputedStyle(el).fontSize)}));
 if(width<700&&phase==='before'){assert.equal(focus.automatic,true);assert.ok(focus.size<16);}else if(width<700){assert.equal(focus.automatic,false);assert.ok(focus.size>=16);}
 if(phase==='after'){
  const popup=await page.locator('#ct-list-volatility').boundingBox();assert.ok(popup.x>=0&&popup.x+popup.width<=width+1,JSON.stringify(popup));
  await search.click();await search.fill('modérée');assert.equal(await page.locator('#ct-list-volatility .ct-category-option:visible').count(),1);await search.fill('');await page.locator('.ct-secondary').screenshot({path:`${OUT}/${phase}-${theme}-${width}-filter-open.png`});
  const checkbox=page.locator('#ct-list-volatility input[type=checkbox]').first();await checkbox.uncheck();await page.locator('[data-close-filter="volatility"]').click();await page.locator('[data-mode="expert"]').click();assert.equal(await checkbox.isChecked(),false);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 }
 await page.locator('.ct-secondary').scrollIntoViewIfNeeded();await page.locator('.ct-secondary').screenshot({path:`${OUT}/${phase}-${theme}-${width}-filters.png`});assert.deepEqual(errors,[]);
 reports.push({phase,theme,width,...geometry,focus,passed:true});console.log(JSON.stringify(reports.at(-1)));await context.close();
}}finally{await b.close();fs.writeFileSync(OUT+'/results.json',JSON.stringify(reports,null,2));}})().catch(e=>{console.error(e);process.exitCode=1;});
