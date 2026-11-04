const {chromium}=require(process.env.PLAYWRIGHT_MODULE),assert=require('node:assert/strict');
exports.assert=assert;
exports.start=async(width=1280)=>{const browser=await chromium.launch({executablePath:process.env.JIGO_CHROMIUM,args:['--no-sandbox']}),context=await browser.newContext({viewport:{width,height:900}}),page=await context.newPage();page.setDefaultTimeout(25000);const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:18089/login.html');await page.fill('#u','review_user');await page.fill('#p','review-local-password');await page.click('#auth-form button.primary');await page.waitForURL('**/index.html');await exports.ready(page);return {browser,context,page,errors};};
exports.ready=p=>p.waitForFunction(()=>document.querySelector('#results')?.getAttribute('aria-busy')==='false');
exports.apply=async p=>{const wait=p.waitForResponse(r=>new URL(r.url()).searchParams.get('r')==='explore');await p.click('#apply');const r=await wait;assert.equal(r.status(),200);await exports.ready(p);return r.json();};
exports.state=p=>p.evaluate(()=>JSON.parse(localStorage.getItem('jigo.explorer.v4.'+J.user.id)));
exports.api=(p,route,body)=>p.evaluate(async({route,body})=>body?J.post(route,body):J.api(route),{route,body});
