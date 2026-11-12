// Rendu réel du tableau de l'explorateur avec une réponse ranking/table simulée (la base locale n'a aucun titre classé). Prérequis : serveur PHP + base seedée, playwright-core.
const {chromium}=require('playwright-core');
const BASE=(process.env.BASE_URL||'http://127.0.0.1:18189')+'/';
const rows=[...Array(30)].map((_,i)=>({id:i+1,symbol:'T'+i,name:'Titre '+i,isin:'FR000000'+i,mic:'XPAR',currency:'EUR',kind:'stock',country:'FR',category:'x',group:{},
 status:i<20?'retained':'excluded',rank_complex:i+1,rank_simple:i+1,pos_complex:i+1,pos_simple:i+1,simple:50-i,complex:60-i,simple_status:'ok',complex_status:'ok',
 price_eur:10+i,price:10+i,change:(i%5)-2,slope:.1*i,r2:.9,volatility:20+i,drawdown:-5-i,turnover_eur:1e6*(i+1),perf:{month:i},periods:{5:{},21:{},63:{},126:{},252:{}},last_close:'2026-11-10'}));
(async()=>{
 const b=await chromium.launch({args:['--no-sandbox']});const p=await(await b.newContext()).newPage();p.setDefaultTimeout(15000);
 const errs=[];p.on('pageerror',e=>errs.push(e.message.slice(0,120)));
 await p.route('**/api.php?r=ranking%2Ftable',r=>r.fulfill({json:{rows,universe:30,label:'test',counts:{retained:20,excluded:10,undetermined:0}}}));
 await p.route('**/api.php?r=ranking/table',r=>r.fulfill({json:{rows,universe:30,label:'test',counts:{retained:20,excluded:10,undetermined:0}}}));
 await p.goto(BASE+'login.html');await p.fill('#u','plan_suivi');await p.fill('#p','plan-suivi-local-2026');await p.click('#auth-form button.primary');await p.waitForURL(u=>!/login/.test(u.pathname));
 await p.goto(BASE+'index.html');await p.waitForSelector('#ct-table-body');await p.waitForLoadState('networkidle');await p.waitForTimeout(1500);await p.getByRole('button',{name:'Appliquer les réglages'}).click();await p.waitForTimeout(1500);
 const n=await p.locator('#ct-table-body tr').count(),th=await p.locator('#ct-table-head [data-sort]').count();
 const fails=[];if(n<1)fails.push('aucune ligne');if(th<1)fails.push('aucun en-tête triable');
 if(th){const key=await p.locator('#ct-table-head [data-sort]').first().getAttribute('data-sort'),ar=()=>p.locator(`#ct-table-head [data-sort="${key}"]`).evaluate(x=>x.parentElement.getAttribute('aria-sort'));
  await p.locator(`#ct-table-head [data-sort="${key}"]`).click();const s1=await ar();await p.locator(`#ct-table-head [data-sort="${key}"]`).click();const s2=await ar();if(!s1||s1===s2)fails.push('tri inactif '+s1+'→'+s2);}
 await p.fill('#ct-search,input[type=search]','Titre 3').catch(()=>{});await p.waitForTimeout(500);
 if(errs.length)fails.push('erreurs JS: '+errs.join(' / '));
 console.log(n+' lignes, '+th+' en-têtes triables');console.log(fails.length?'KO '+fails.join(' ; '):'OK');await b.close();process.exit(fails.length?1:0);
})();
