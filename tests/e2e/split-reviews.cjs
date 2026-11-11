/* Test avec l'API PHP réelle et une base jetable préparée par split_review_seed.py. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright'),assert=require('node:assert/strict');
const BASE=process.env.BASE||'http://127.0.0.1:18193';assert.equal(new URL(BASE).hostname,'127.0.0.1');
(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});try{
 const ctx=await b.newContext({viewport:{width:390,height:844}}),p=await ctx.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));
 const api=(route,data)=>ctx.request.post(BASE+'/api.php?r='+route,{data});
 const login=await api('auth/login',{username:'split-admin',password:'split-review-local-only'});assert.equal(login.status(),200);const me=(await (await ctx.request.get(BASE+'/api.php?r=auth/me')).json()).user;
 await p.goto(BASE+'/splits.html');await p.locator('.sr-card[data-lid="1"]').waitFor();
 assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 await p.screenshot({path:'/tmp/split-review-mobile.png',fullPage:true});
 const card=p.locator('.sr-card[data-lid="1"]');await card.locator('[name=new]').fill('2.5');await card.locator('[name=note]').fill('Test de contrôle');await card.getByRole('button',{name:'Appliquer le split',exact:true}).click();await p.locator('dialog[open]').getByRole('button',{name:'Appliquer le split',exact:true}).click();await card.locator('.sr-error').filter({hasText:'n’explique pas'}).waitFor();
 await card.locator('[name=new]').fill('250');await card.locator('[name=source]').fill('https://example.com/issuer-notice');await card.getByRole('button',{name:'Appliquer le split',exact:true}).click();await p.locator('dialog[open]').getByRole('button',{name:'Appliquer le split',exact:true}).click();await p.locator('#sr-feedback').filter({hasText:'Split confirmé'}).waitFor();
 await p.locator('[data-filter=applied]').click();await p.locator('#sr-rows[data-state=applied][aria-busy=false]').waitFor();await p.locator('.sr-card[data-lid="1"]').waitFor();assert.equal(await p.locator('.sr-card[data-lid="1"] form').count(),0);
 const d=await (await ctx.request.get(BASE+'/api.php?r=admin/splits&state=applied')).json();assert.equal(d.rows.length,1);assert.equal(+d.rows[0].reviewed_ratio,250);assert.equal(d.rows[0].history.length,1);assert.equal(d.rows[0].history[0].actor_id,me.id);
 const again=await api('admin/splits/decide',{listing_id:1,event_date:'2026-10-27',decision:'applied',old_shares:1,new_shares:250,note:'Même décision',revision:0,actor_id:99999});assert.equal(again.status(),200);assert.equal((await again.json()).changed,false);
 await p.locator('[data-filter=pending]').click();await p.locator('#sr-rows[data-state=pending][aria-busy=false]').waitFor();await p.locator('.sr-card[data-lid="2"]').getByRole('button',{name:'Ce n’est pas un split'}).click();await p.locator('#sr-feedback').filter({hasText:'Split refusé'}).waitFor();await p.locator('[data-filter=rejected]').click();await p.locator('#sr-rows[data-state=rejected][aria-busy=false]').waitFor();await p.locator('.sr-card[data-lid="2"]').getByRole('button',{name:'Réexaminer'}).click();await p.locator('#sr-feedback').filter({hasText:'remis en attente'}).waitFor();
 await p.setViewportSize({width:1280,height:900});await p.locator('[data-filter=all]').click();await p.locator('#sr-rows[data-state=all][aria-busy=false]').waitFor();await p.locator('.sr-card[data-lid="1"]').waitFor();await p.screenshot({path:'/tmp/split-review-desktop.png',fullPage:true});assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 const anon=await b.newContext();assert.equal((await anon.request.get(BASE+'/api.php?r=admin/splits')).status(),401);await anon.close();
 const user=await b.newContext();await user.request.post(BASE+'/api.php?r=auth/login',{data:{username:'split-user',password:'split-review-local-only'}});for(const route of ['admin/splits','admin/splits/scan','admin/splits/decide'])assert.equal((route==='admin/splits'?await user.request.get(BASE+'/api.php?r='+route):await user.request.post(BASE+'/api.php?r='+route,{data:{}})).status(),403);await user.close();
 assert.equal((await ctx.request.post(BASE+'/api.php?r=admin/splits/scan',{data:{},headers:{Origin:'https://other.invalid'}})).status(),403);
 assert.deepEqual(errors,[]);console.log('OK API réelle : appliquer, ratio incorrect, refus/réexamen, audit, idempotence, droits ; mobile et desktop');
 await ctx.close();
}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
