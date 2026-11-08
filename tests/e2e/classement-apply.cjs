const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs'),assert=require('assert/strict'),root=require('path').resolve(__dirname,'../../app/public')+'/';
const definitions=JSON.parse(fs.readFileSync(root+'../config/explorer_secondary_filters.json'));
const mapping=JSON.parse(fs.readFileSync(root+'../config/secondary_metadata_groups.json'));
const defaults={filters:{}};
for(const f of definitions.filters){defaults.filters[f.id]={};for(const m of f.measures)defaults.filters[f.id][m.id]={mode:'all',selected:[]};if(!f.editable){f.values=mapping.groups[f.id].map(v=>({...v,value:v.id==='unknown'?null:v.id}));defaults.filters[f.id].values={mode:'all',selected:[]};}}
const payload={schema:2,definitions,defaults,metadata_mapping:mapping};
(async()=>{const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});try{for(const width of [320,390,1280]){
const page=await browser.newPage({viewport:{width,height:850}}),errors=[],calls=[],curveCalls=[];let fail=false,empty=false,many=false,curveFail=false,release;
page.on('pageerror',e=>errors.push(e.message));
await page.route('http://jigo.test/**',async route=>{const url=new URL(route.request().url()),key=url.searchParams.get('r');if(url.pathname==='/api.php'){
let data={};if(key==='auth/me')data={user:{id:7,username:'Test',prefs:{theme:'light'}}};
if(key==='explorer/secondary-filters')data=payload;
if(key==='strategies/status')data={strategies:['fast','regular','mom12'].map(id=>({id,label:id==='fast'?'Croissance rapide':id==='regular'?'Croissance régulière':'Momentum 12 mois (expérimental)',kind:'builtin',status:'official',criteria:{state:'official'},scores:{state:'official'}}))};
if(key==='ranking/table'){
 calls.push(key);assert.equal(route.request().method(),'POST');const body=route.request().postDataJSON();assert.ok(body.config.periods);assert.equal(body.include_curves,false);
 if(release)await release.promise;if(empty)return route.fulfill({body:'',contentType:'application/json'});if(fail)return route.fulfill({status:500,json:{error:'Essai indisponible'}});
 data={rows:Array.from({length:many?120:1},(_,i)=>({id:i+1,symbol:'TEST'+i,name:'Titre témoin '+i,status:'retained',simple:75,complex:80,rank_simple:1,rank_complex:1})),label:body.strategy,universe:many?120:1};
}
if(key==='ranking/verdicts')throw new Error('Le deuxième appel de recherche doit être supprimé');
if(key==='ranking/curves'){const ids=route.request().postDataJSON().ids;curveCalls.push(ids);if(curveFail)return route.fulfill({status:503,json:{error:'Courbes indisponibles'}});data={curves:Object.fromEntries(ids.map(id=>[id,[10,11,12]]))};}
return route.fulfill({json:data});}
const path=root+(url.pathname==='/'?'index.html':url.pathname.slice(1));return route.fulfill({path,contentType:path.endsWith('.js')?'application/javascript':path.endsWith('.css')?'text/css':'text/html'});
});
await page.goto('http://jigo.test/');await page.locator('#ct-search-status').filter({hasText:'pour lancer la recherche'}).waitFor();
await page.waitForTimeout(400);assert.equal(calls.length,0);
await page.locator('.sui-pick-btn').click();await page.locator('.sui-opt[data-id="regular"]').click();await page.waitForTimeout(400);assert.equal(calls.length,0);
await page.locator('#ct-apply').click();await page.locator('#ct-search-status').filter({hasText:'Résultats à jour'}).waitFor();
assert.equal(calls.length,1);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
await page.locator('.sui-pick-btn').click();await page.locator('.sui-opt[data-id="mom12"]').click();
await page.locator('.ct-fold').click();await page.locator('#ct-none-filters').evaluate(e=>e.click());
await page.waitForTimeout(400);assert.equal(calls.length,1);assert.equal(await page.locator('#ct-table-body tr[data-row]').count(),1);assert.equal(curveCalls.length,width<700?0:1);if(width>=700)assert.deepEqual(curveCalls[0],[1]);
assert.match(await page.locator('#ct-search-status').innerText(),/Réglages modifiés/);
let resolve;release={promise:new Promise(r=>resolve=r)};await page.locator('#ct-apply').click();await page.waitForFunction(()=>document.querySelector('#ct-apply').disabled);assert.match(await page.locator('#ct-search-status').innerText(),/Recherche en cours/);
resolve();await page.waitForFunction(()=>!document.querySelector('#ct-apply').disabled);assert.equal(calls.length,2);assert.equal(await page.locator('#ct-table-body tr[data-row]').count(),0);assert.doesNotMatch(await page.locator('#ct-feedback').innerText(),/fictives/);
if(width===1280){
 many=true;curveCalls.length=0;await page.locator('#ct-all-filters').evaluate(e=>e.click());await page.locator('#ct-apply').click();await page.locator('.ct-mini-curve').first().waitFor();
 assert.equal(await page.locator('#ct-table-body tr[data-row]').count(),50);assert.equal(curveCalls.length,1);assert.equal(curveCalls[0].length,50);
 const first=new Set(curveCalls[0]);await page.getByRole('button',{name:'Page suivante',exact:true}).click();await page.locator('.ct-mini-curve').first().waitFor();assert.equal(curveCalls.length,2);assert.equal(curveCalls[1].length,50);assert.ok(curveCalls[1].every(id=>!first.has(id)));
 await page.getByRole('button',{name:'Page précédente',exact:true}).click();await page.waitForTimeout(100);assert.equal(curveCalls.length,2);
 curveFail=true;await page.locator('#ct-apply').click();await page.locator('#ct-search-status').filter({hasText:'Résultats à jour'}).waitFor();assert.equal(await page.locator('#ct-table-body tr[data-row]').count(),50);
}
empty=true;await page.locator('#ct-apply').click();await page.locator('#ct-search-status').filter({hasText:'réponse de classement invalide'}).waitFor();assert.equal(await page.locator('#ct-apply').isEnabled(),true);empty=false;
fail=true;await page.locator('#ct-apply').click();await page.locator('#ct-search-status').filter({hasText:'Résultats non actualisés'}).waitFor();assert.equal(await page.locator('#ct-apply').isEnabled(),true);
assert.deepEqual(errors,[]);console.log('OK mobile/manual apply/loading/error',width);await page.close();
}}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
