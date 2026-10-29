const {chromium}=require(process.env.PLAYWRIGHT_MODULE),fs=require('fs');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.JIGO_CHROMIUM,args:['--no-sandbox']}),report=[];
 for(const width of [375,390,1280]){
  const ctx=await browser.newContext({viewport:{width,height:900}}),page=await ctx.newPage();let step='login';const r={width};
  page.setDefaultTimeout(20000);
  try{
   await page.goto('http://127.0.0.1:18089/login.html');await page.fill('#u','review@example.test');await page.fill('#p','review-local-password');
   await page.locator('.pw-eye').click();if(await page.locator('#p').getAttribute('type')!=='text')throw Error();await page.locator('.pw-eye').click();
   await page.check('#remember');await page.click('#auth-form button.primary');await page.waitForURL('**/index.html');r.email_login=true;
   const config=await page.evaluate(async()=>{const r=await J.api('strategy/presets');const c=r.presets.regular;for(const p of c.periods){p.enabled=['week','month'].includes(p.id);p.min_slope=.01;p.min_r2=null;}c.ranking.mode='performance';return c;});
   step='ranking-state';await page.addInitScript(c=>{if(location.pathname!=='/index.html'||sessionStorage.getItem('account-test-seeded'))return;const s={pageKey:'/index.html',preset:'regular',config:c,status:'all',page:2,sort:'perf',dir:'desc',size:20,level:'advanced',compare:false,view:{q:'TEST',kind:'equity',budget:'1000'}};sessionStorage.setItem('jigo_explorer2',JSON.stringify(s));localStorage.setItem('jigo_explorer2',JSON.stringify(s));sessionStorage.setItem('account-test-seeded','1');},config);
   await page.reload();await page.locator('a[data-sheet]').first().waitFor();await page.locator('a[data-sheet]').first().evaluate(a=>a.scrollIntoView({block:'center'}));
   const before=await page.evaluate(()=>({state:JSON.parse(localStorage.getItem('jigo_explorer2')),y:scrollY,href:location.href}));
   if(before.state.page!==2||before.state.view.q!=='TEST')throw Error('fixture not applied');
   for(let i=0;i<2;i++){
    step='open-sheet-'+i;const [sheet]=await Promise.all([ctx.waitForEvent('page'),page.locator('a[data-sheet]').nth(i).click()]);await sheet.locator('.hero').waitFor();
    const external=await sheet.locator('a[href^="https://"]').evaluateAll(links=>links.every(a=>a.target==='_blank'&&a.rel.includes('noopener')));if(!external)throw Error();await sheet.close();
   }
   const after=await page.evaluate(()=>({state:JSON.parse(localStorage.getItem('jigo_explorer2')),y:scrollY,href:location.href}));
   if(Math.abs(before.y-after.y)>2)throw Error('scroll changed while opening sheets');
   if(before.href!==after.href||before.state.page!==after.state.page||JSON.stringify(before.state.config)!==JSON.stringify(after.state.config))throw Error('list state changed');
   step='restore-list';await page.reload();await page.locator('a[data-sheet]').first().waitFor();await page.waitForTimeout(150);const restored=await page.evaluate(()=>JSON.parse(sessionStorage.getItem('jigo_explorer2')));
   if(restored.page!==2||restored.view.q!=='TEST'||String(restored.view.budget)!=='1000'||restored.level!=='advanced')throw Error('restored state mismatch: '+JSON.stringify({page:restored.page,q:restored.view.q,budget:restored.view.budget,level:restored.level}));r.ranking_preserved=true;
   r.horizontal_overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
   await page.screenshot({path:`audit-results/navigation-${width}.png`});
   r.ok=true;
  }catch(e){r.ok=false;r.failed_step=step;r.error_kind=e.name;r.detail=String(e.message||'').split('\n')[0].replace(/https?:\/\/\S+/g,'[URL]').replace(/[a-f0-9]{64}/g,'[redacted]');}
  await ctx.close();report.push(r);
 }
 // Full account round-trip, real API, isolated file delivery transport. Never print links or passwords.
 const ctx=await browser.newContext(),page=await ctx.newPage();let step='account-login';const r={account_round_trip:true};
 const messages=()=>fs.readdirSync(process.env.JIGO_TEST_MAIL_DIR).filter(x=>x.endsWith('.json')).map(x=>JSON.parse(fs.readFileSync(process.env.JIGO_TEST_MAIL_DIR+'/'+x)));
 const localLink=m=>'http://127.0.0.1:18089/'+m.body.match(/https:\/\/jigobourso\.turnjoy\.dev\/(\S+)/)[1];
 try{
  await page.goto('http://127.0.0.1:18089/login.html');await page.fill('#u','review_user');await page.fill('#p','review-local-password');await page.click('#auth-form button.primary');await page.waitForURL('**/index.html');
  step='profile';await page.click('#user-btn');await page.fill('#account-name','review_renamed');await page.fill('#account-email','new-review@example.test');await page.fill('#pw0','review-local-password');await page.getByRole('button',{name:'Enregistrer mes coordonnées',exact:true}).click();
  await page.waitForTimeout(300);const change=messages().find(m=>m.to==='new-review@example.test');if(!change)throw Error();
  step='verify-email';await page.goto(localLink(change));await page.click('#auth-form button[type=submit]');await page.locator('#msg').filter({hasText:'confirmée'}).waitFor();
  await page.evaluate(()=>J.post('auth/logout'));
  step='recover';await page.goto('http://127.0.0.1:18089/recover.html');await page.fill('#email','new-review@example.test');await page.click('#auth-form button[type=submit]');await page.locator('#msg').filter({hasText:'lien'}).waitFor();
  const reset=messages().find(m=>m.subject.includes('Réinitialiser'));if(!reset)throw Error();
  step='reset';await page.goto(localLink(reset));if(page.url().includes('#token'))throw Error();await page.fill('#p','new-review-password');await page.fill('#confirm','new-review-password');await page.click('#auth-form button[type=submit]');await page.locator('#done').waitFor();
  step='relogin';await page.click('#done');await page.fill('#u','new-review@example.test');await page.fill('#p','new-review-password');await page.click('#auth-form button[type=submit]');await page.waitForURL('**/index.html');
  r.ok=true;
 }catch(e){r.ok=false;r.failed_step=step;r.error_kind=e.name;r.detail=String(e.message||'').split('\n')[0].replace(/https?:\/\/\S+/g,'[URL]').replace(/[a-f0-9]{64}/g,'[redacted]');}
 report.push(r);await ctx.close();await browser.close();fs.writeFileSync('audit-results/account-browser.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));if(report.some(r=>!r.ok))process.exit(1);
})().catch(()=>{console.error('Account browser runner failed');process.exit(1)});
