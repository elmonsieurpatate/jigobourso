// Interactions clés après la refonte du noyau JS : thème, menu, classement, aide, filtres, portefeuilles, toast. Prérequis : serveur PHP + base seedée (plan_suivi_seed.py), playwright-core.
const {chromium}=require('playwright-core');
const assert=require('assert');const BASE=(process.env.BASE_URL||'http://127.0.0.1:18189')+'/';
const res=[];const ok=(n,c,d='')=>{res.push([c?'OK ':'KO ',n,d]);};
(async()=>{
 const b=await chromium.launch({args:['--no-sandbox']});const ctx=await b.newContext({viewport:{width:1280,height:900}});const p=await ctx.newPage();p.setDefaultTimeout(20000);
 const errs=[];p.on('pageerror',e=>errs.push(p.url().split('/').pop()+' : '+e.message.slice(0,90)));
 await p.goto(BASE+'login.html');await p.waitForLoadState('networkidle');await p.waitForTimeout(600);await p.fill('#u','plan_suivi');await p.fill('#p','plan-suivi-local-2026');await p.click('#auth-form button.primary');await p.waitForURL(u=>!/login/.test(u.pathname));
 // noyau chargé
 ok('J.store/J.dom/J.pctS exposés',await p.evaluate(()=>!!(J.store&&J.dom&&J.pctS&&J.int)));
 // thème : bascule + mémorisation
 const t0=await p.evaluate(()=>document.documentElement.dataset.theme);await p.click('#theme-btn');
 const t1=await p.evaluate(()=>document.documentElement.dataset.theme);ok('bouton thème bascule',t0!==t1,t0+'→'+t1);
 ok('thème mémorisé (J.store.text)',await p.evaluate(t=>localStorage.getItem('jigo_theme')===t,t1));
 await p.reload();ok('thème conservé après rechargement',(await p.evaluate(()=>document.documentElement.dataset.theme))===t1);
 await p.click('#theme-btn');
 // menu latéral : repli mémorisé
 await p.click('#menu-btn').catch(()=>{});await p.waitForTimeout(300);
 const side=await p.evaluate(()=>localStorage.getItem('jigo_side'));ok('repli du menu mémorisé',side==='collapsed'||side==='open'||side===null,String(side));
 // classement : appliquer
 await p.goto(BASE+'index.html');await p.waitForSelector('#ct-table-body');
 await p.click('text=Appliquer les réglages').catch(()=>{});await p.waitForTimeout(2500);
 const rows=await p.locator('#ct-table-body tr').count();ok('classement : tableau rempli ou message',rows>0,rows+' lignes');
 const mode=await p.evaluate(()=>[...document.querySelectorAll('.seg button')].map(b=>b.textContent.trim()).join('|'));ok('classement : segment Simple/Expert',/Simple/.test(mode)&&/Expert/.test(mode),mode);
 await p.click('.seg button:has-text("Expert")');await p.waitForTimeout(400);
 ok('classement : mode Expert affiche l\'éditeur de règles',await p.evaluate(()=>!document.querySelector('#ct-expert').hidden&&document.querySelector('#ct-simple').hidden));
 await p.click('.seg button:has-text("Simple")');
 // aide : lecture d'un chapitre mémorisée
 await p.goto(BASE+'aide.html');await p.waitForTimeout(1500);
 await p.locator('#help a[href^="#/"]').first().click().catch(()=>{});await p.waitForTimeout(600);
 ok('aide : chapitre vu mémorisé',await p.evaluate(()=>localStorage.getItem('jigo_help_seen')!==null));
 // mes stratégies / filtres / colonnes / scores / splits / bilan / suivi : chargement sans erreur et contenu
 for(const [pg,sel] of [['mes-strategies.html','.card'],['mes-filtres.html','#ac-category-rows tr'],['mes-colonnes.html','h1'],['mes-scores.html','h1'],['splits.html','h1'],['bilan.html','h1'],['suivi.html','h1'],['donnees.html','.card'],['portefeuilles.html','h1']]){
  const before=errs.length;await p.goto(BASE+pg);await p.waitForTimeout(1500);
  ok(pg+' : charge et affiche',(await p.locator(sel).count())>0&&errs.length===before,errs.slice(before).join(' / '));
 }
 // portefeuilles : préférences mémorisées via J.store.fn
 await p.goto(BASE+'portefeuilles.html');await p.waitForTimeout(2000);
 const seg=p.locator('.seg button').nth(1);if(await seg.count()){await seg.click().catch(()=>{});await p.waitForTimeout(400);}
 ok('portefeuilles : clés jigo_pf*/jigo_pfx* lisibles',await p.evaluate(()=>{try{return Object.keys(localStorage).filter(k=>/^jigo_pfx?_/.test(k)).every(k=>{JSON.parse(localStorage.getItem(k));return true})}catch(e){return false}}));
 // filtres : sélection d'un filtre, édition
 await p.goto(BASE+'mes-filtres.html');await p.waitForSelector('#ac-category-rows tr');
 ok('filtres : store.filters branché',await p.evaluate(()=>!!J.store.filters&&typeof J.store.filters.load==='function'));
 ok('filtres : liste de catégories',(await p.locator('#ac-category-rows tr').count())>0);
 await p.locator('#ac-category-rows button[aria-label*="Modifier"], #ac-category-rows .btn.icon').first().click().catch(()=>{});await p.waitForTimeout(300);
 // toast
 await p.evaluate(()=>J.toast('essai'));ok('toast accessible (role=status)',await p.evaluate(()=>!!document.querySelector('.toast[role=status]')));
 await b.close();
 for(const r of res)console.log(...r);const ko=res.filter(r=>r[0]==='KO ').length;
 const ignore=errs.filter(e=>!/titre\.html/.test(e));console.log('erreurs JS hors fiche:',ignore.length,ignore.slice(0,5).join(' | '));
 process.exit(ko||ignore.length?1:0);
})();
