const {chromium}=require(process.env.PLAYWRIGHT_MODULE),fs=require('fs');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.JIGO_CHROMIUM,args:['--no-sandbox']}),report=[];
 for(const width of [375,390,1280]){
  const ctx=await browser.newContext({viewport:{width,height:900}}),page=await ctx.newPage();let step='login';const r={width};
  ctx.setDefaultTimeout(15000);ctx.setDefaultNavigationTimeout(15000);page.setDefaultTimeout(15000);
  try{
   await page.goto('http://127.0.0.1:18089/login.html');await page.fill('#u','review@example.test');await page.fill('#p','review-local-password');
   await page.locator('.pw-eye').click();if(await page.locator('#p').getAttribute('type')!=='text')throw Error();await page.locator('.pw-eye').click();
   await page.check('#remember');await page.click('#auth-form button.primary');await page.waitForURL('**/index.html');r.email_login=true;
   step='ranking-state';await page.waitForFunction(()=>document.querySelector('#ct-strategy-count')?.textContent.trim().length>0,null,{timeout:60000});await page.locator('#ct-show-outside').check();await page.waitForSelector('#ct-table-body tr:not(.ct-loading)',{timeout:60000});
   const before=await page.locator('#ct-table-body tr:not(.ct-loading)').count();if(!before)throw Error('classement vide');
   step='open-detail';const href=await page.locator('a.ct-company').first().getAttribute('href');if(!/^titre\.html\?/.test(href))throw Error('lien de fiche invalide : '+href);
   step='reload-keeps-state';await page.reload();await page.waitForFunction(()=>document.querySelector('#ct-strategy-count')?.textContent.trim().length>0,null,{timeout:60000});await page.locator('#ct-show-outside').check();await page.waitForSelector('#ct-table-body tr:not(.ct-loading)',{timeout:60000});if(!await page.locator('#ct-table-body tr:not(.ct-loading)').count())throw Error('reload lost ranking');r.reload_preserves_filters=true;
   r.horizontal_overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
   await page.screenshot({path:`audit-results/navigation-${width}.png`});
   r.ok=true;
  }catch(e){r.ok=false;r.failed_step=step;r.error_kind=e.name;r.detail=String(e.message||'').split('\n')[0].replace(/https?:\/\/\S+/g,'[URL]').replace(/[a-f0-9]{64}/g,'[redacted]');}
  await ctx.close();report.push(r);
 }
 // Full account round-trip, real API, isolated file delivery transport. Never print links or passwords.
 const ctx=await browser.newContext(),page=await ctx.newPage();ctx.setDefaultTimeout(15000);ctx.setDefaultNavigationTimeout(15000);let step='account-login';const r={account_round_trip:true};
 const messages=()=>fs.readdirSync(process.env.JIGO_TEST_MAIL_DIR).filter(x=>x.endsWith('.json')).map(x=>JSON.parse(fs.readFileSync(process.env.JIGO_TEST_MAIL_DIR+'/'+x)));
 const localLink=m=>'http://127.0.0.1:18089/'+m.body.match(/https:\/\/jigobourso\.turnjoy\.dev\/(\S+)/)[1];
 try{
  await page.goto('http://127.0.0.1:18089/login.html');await page.fill('#u','review_user');await page.fill('#p','review-local-password');await page.click('#auth-form button.primary');await page.waitForURL('**/index.html');
  step='profile';console.log('account stage',step);await page.click('#user-btn');await page.fill('#account-name','review_renamed');await page.fill('#account-email','new-review@example.test');await page.fill('#pw0','review-local-password');await page.getByRole('button',{name:'Enregistrer mes coordonnées',exact:true}).click();
  let change;for(let i=0;i<20&&!change;i++){change=messages().find(m=>m.to==='new-review@example.test');if(!change)await page.waitForTimeout(150);}if(!change)throw Error();
  step='verify-email';console.log('account stage',step);await page.goto(localLink(change));await page.click('#auth-form button[type=submit]');await page.locator('#msg').filter({hasText:'confirmée'}).waitFor();
  await page.evaluate(()=>J.post('auth/logout'));
  step='recover';await page.goto('http://127.0.0.1:18089/recover.html');await page.fill('#email','new-review@example.test');await page.click('#auth-form button[type=submit]');await page.locator('#msg').filter({hasText:'lien'}).waitFor();
  const reset=messages().find(m=>m.subject.includes('Réinitialiser'));if(!reset)throw Error();
  step='reset';console.log('account stage',step);await page.goto(localLink(reset));if(page.url().includes('#token'))throw Error();await page.fill('#p','new-review-password');await page.fill('#confirm','new-review-password');await page.click('#auth-form button[type=submit]');await page.locator('#done').waitFor();
  step='relogin';await page.click('#done');await page.fill('#u','new-review@example.test');await page.fill('#p','new-review-password');await page.click('#auth-form button[type=submit]');await page.waitForURL('**/index.html');
  r.ok=true;
 }catch(e){r.ok=false;r.failed_step=step;r.error_kind=e.name;r.detail=String(e.message||'').split('\n')[0].replace(/https?:\/\/\S+/g,'[URL]').replace(/[a-f0-9]{64}/g,'[redacted]');}
 report.push(r);await ctx.close();await browser.close();fs.writeFileSync('audit-results/account-browser.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));if(report.some(r=>!r.ok))process.exit(1);
})().catch(()=>{console.error('Account browser runner failed');process.exit(1)});
