const {chromium}=require(process.env.PLAYWRIGHT_MODULE),fs=require('fs');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.JIGO_CHROMIUM,args:['--no-sandbox']}),report=[];
 for(const width of [375,390,1280]){
  const ctx=await browser.newContext({viewport:{width,height:900}}),page=await ctx.newPage(),errors=[];
  page.setDefaultTimeout(20000);page.on('pageerror',e=>errors.push(e.message));
  const r={width,synthetic_local_database:true};
  try{
   await page.goto('http://127.0.0.1:18089/login.html');await page.fill('#u','review_user');await page.fill('#p','review-local-password');await page.click('#auth-form button.primary');await page.waitForURL('**/index.html');
   await page.locator('.rtable tbody tr').first().waitFor();r.login=true;r.explorer_rows=await page.locator('.rtable tbody tr').count();r.explorer_overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
   await page.screenshot({path:`audit-results/explorer-${width}.png`});
   await page.goto('http://127.0.0.1:18089/titre.html?id=1');await page.locator('.hero').waitFor();await page.locator('svg.price-svg').waitFor();r.sheet_chart=true;r.sheet_overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
   await page.screenshot({path:`audit-results/sheet-${width}.png`});
   await page.locator('#add').click();await page.locator('dialog').waitFor();r.portfolio_picker=await page.locator('#tx-pf').count()>0;await page.keyboard.press('Escape');
   await page.goto('http://127.0.0.1:18089/admin.html');await page.locator('#page').waitFor();await page.waitForTimeout(1500);r.admin_navigation=await page.locator('#side').count()>0;
   r.errors=errors;r.completed=true;
  }catch(e){r.error=e.message;await page.screenshot({path:`audit-results/error-${width}.png`}).catch(()=>{});r.errors=errors;}
  report.push(r);await ctx.close();
 }
 await browser.close();fs.writeFileSync('audit-results/browser.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));if(report.some(r=>!r.completed || r.errors.length || r.explorer_overflow || r.sheet_overflow || !r.portfolio_picker))process.exit(1);
})().catch(e=>{console.error(e);process.exit(1)});
