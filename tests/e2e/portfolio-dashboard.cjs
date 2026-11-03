/* Portfolio V3: real local browser tests after portfolio_audit_seed.py. */
const assert=require('node:assert/strict'),fs=require('node:fs');
const{chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const BASE=process.env.BASE||'http://127.0.0.1:18090',OUT=process.env.AUDIT_OUT||'/tmp/jigobourso-dashboard';
assert.equal(process.env.JIGO_TEST_DATABASE,'1');assert.equal(new URL(BASE).hostname,'127.0.0.1');fs.mkdirSync(OUT,{recursive:true});
(async()=>{const browser=await chromium.launch({executablePath:process.env.JIGO_CHROMIUM||'/usr/bin/chromium',args:['--no-sandbox']});const report=[];
try{for(const width of [1280,390,375]){
 const ctx=await browser.newContext({viewport:{width,height:900},isMobile:width<600,hasTouch:width<600});
 await ctx.route('**/*',r=>{const u=new URL(r.request().url());if(u.hostname!=='127.0.0.1')return r.abort();if(u.searchParams.get('r')==='intraday'){u.searchParams.set('fetch','0');return r.continue({url:u.toString()})}return r.continue()});
 assert.equal((await ctx.request.post(BASE+'/api.php?r=auth/login',{data:{username:'audit_portfolio',password:'audit-local-validation-2026'}})).status(),200);
 const page=await ctx.newPage(),errors=[],r={width,checks:[]};page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(15000);
 const api=async route=>{const x=await ctx.request.get(BASE+'/api.php?r='+route);assert.equal(x.status(),200);return x.json()};
 const view=async name=>{await page.locator(`[data-view="${name}"]`).click();assert.equal(await page.locator(`[data-panel="${name}"]`).isVisible(),true)};
 console.log('dashboard',width,'overview');
 await page.goto(BASE+'/portefeuilles.html?id=1');await page.locator('.pf-summary .hero-v').waitFor();await page.waitForFunction(()=>!document.querySelector('#overview-movers .spinner'));
 assert.equal(await page.locator('#pf-nav [role="tab"]').count(),4);assert.equal(await page.locator('[data-panel="analysis"]').isVisible(),false);
 assert.match(await page.locator('.pf-summary').innerText(),/Gain net estimé/);assert.match(await page.locator('#overview-movers').innerText(),/ALPHA/);
 assert.equal(await page.getByRole('heading',{name:'Secteurs de vos ETF',exact:true}).count(),0);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.screenshot({path:`${OUT}/overview-${width}.png`,fullPage:true});r.checks.push('compact-summary','contributors','irrelevant-etf-section-hidden');
 await page.locator('[data-view="overview"]').focus();await page.keyboard.press('ArrowRight');assert.equal(await page.locator('[data-view="positions"]').getAttribute('aria-selected'),'true');r.checks.push('keyboard-tabs');
 console.log('dashboard',width,'positions');
 assert.equal(await page.locator('.pf-position').count(),3);
 for(const[sort,first]of[['loss','L4'],['gain','L1'],['weight','L1'],['drop','L1'],['attention','L1']]){await page.locator('#position-sort').selectOption(sort);assert.equal(await page.locator('.pf-position').first().getAttribute('data-position'),first)}
 const alpha=page.locator('[data-position="L1"]');assert.equal(await alpha.locator('.position-protection').isVisible(),true);assert.match(await alpha.locator('.position-protection').innerText(),/Gain rendu/);r.checks.push('gain-protection-immediately-visible');assert.match(await alpha.innerText(),/Depuis vos achats · latent/);assert.match(await alpha.innerText(),/État du titre/);
 await alpha.locator('>.position-details>summary').click();assert.match(await alpha.innerText(),/Gain rendu/);assert.match(await alpha.innerText(),/points/);assert.match(await alpha.innerText(),/Moyenne 200 j/);
 const data=await api('portfolio&id=1'),protection=data.insights.L1.protection;
 assert.equal(protection.available,true);assert.equal(protection.cost_eur,2265);assert.ok(Math.abs(protection.gain_eur-60)<1e-7);
 assert.equal(data.insights.L1.status,'act');assert.ok(data.lots.find(l=>l.symbol==='ALPHA').alert.protection.cost_eur===505);
 await page.screenshot({path:`${OUT}/positions-${width}.png`,fullPage:true});r.checks.push('five-sorts','personal-market-separated','costs-and-points');
 await alpha.locator('.position-details>details>summary').click();await alpha.locator('[data-lot]').first().click();
 await page.locator('#lt-st').selectOption('recovery');await page.locator('#lt-drop').fill('12');
 const saved=page.waitForResponse(res=>new URL(res.url()).searchParams.get('r')==='lot/settings');await page.getByRole('button',{name:'Enregistrer',exact:true}).click();assert.equal((await saved).status(),200);
 const updated=await api('portfolio&id=1'),lot=updated.lots.find(l=>l.tx_id===data.lots.find(l=>l.symbol==='ALPHA').tx_id);
 assert.equal(lot.alert.strategy,'recovery');assert.equal(lot.alert.rules.drop,12);assert.equal(lot.alert.protection.cost_eur,505);
 const restore=await ctx.request.post(BASE+'/api.php?r=lot/settings',{data:{tx_id:lot.tx_id,strategy:'momentum',alert_days:30,alert_drop_pct:20,alerts_off:false}});assert.equal(restore.status(),200);r.checks.push('lot-settings-save-no-cost-change');
 await view('positions');
 // The panel may already be open after the settings render; ensure it explicitly.
 if((await page.locator('[data-position="L1"] .position-details').getAttribute('open'))===null)await page.locator('[data-position="L1"]>.position-details>summary').click();
 await page.locator('[data-position="L1"] [data-chart]').click();await page.locator('#pc svg').waitFor();
 for(const per of ['1m','3m','6m','1y','all','buy']){await page.locator(`#pc-gr [data-v="${per}"]`).click();await page.locator('#pc svg').waitFor();assert.ok((await page.locator('#pc').boundingBox()).width>250)}
 if(width<600){await page.locator('#pc svg').scrollIntoViewIfNeeded();const b=await page.locator('#pc svg').boundingBox(),cdp=await ctx.newCDPSession(page);await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:b.x+b.width*.5,y:b.y+40}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:b.x+b.width*.6,y:b.y+40}]});assert.equal(await page.locator('#pc .chart-tip').isVisible(),true);await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});r.checks.push('touch-tooltip')}
 await page.keyboard.press('Escape');r.checks.push('individual-price-chart');
 console.log('dashboard',width,'management');await view('manage');const header=page.locator('[data-fold="tx"] .fold-h');await header.focus();const before=await header.getAttribute('aria-expanded');await page.keyboard.press('Enter');assert.notEqual(await header.getAttribute('aria-expanded'),before);
 assert.equal(await page.locator('#add-tx').isVisible(),true);r.checks.push('keyboard-folds','transaction-access');
 await view('analysis');assert.ok((await page.locator('#evo-chart').boundingBox()).width>=250);await page.locator('#evo-per [data-v="1d"]').click();assert.equal(await page.locator('#evo-unit [data-v="pct"]').isDisabled(),true);
 await view('positions');assert.match(await page.locator('#position-cards').innerText(),/Non calculé en 1 J/);
 await view('analysis');await page.locator('#evo-per [data-v="1m"]').click();await view('overview');r.checks.push('intraday-meaning-explicit');
 await page.locator('#pf-select').selectOption('4');await page.waitForFunction(()=>document.querySelector('.hero-v')?.textContent==='–');assert.match(await page.locator('#page').innerText(),/valorisation et gain total indisponibles/);
 await page.locator('#pf-select').selectOption('7');await page.locator('#overview-movers').getByText('Contributions partielles :', {exact:false}).waitFor();assert.equal(await page.locator('.hero-v').innerText(),'–');r.checks.push('partial-contributions-explicit');
 await page.locator('#pf-select').selectOption('5');await page.waitForFunction(()=>document.querySelector('.hero-v')?.textContent.replace(/\s/g,'')==='0€');assert.equal(await page.locator('#pf-nav').count(),1);r.checks.push('missing-price','empty-portfolio');
 r.errors=errors;assert.deepEqual(errors,[]);report.push(r);fs.writeFileSync(`${OUT}/results.json`,JSON.stringify(report,null,2));await ctx.close();
}}finally{await browser.close()}console.log(JSON.stringify(report));})().catch(e=>{console.error(e);process.exitCode=1});
