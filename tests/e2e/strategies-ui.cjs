// Refonte stratégies : deux comptes (admin / ordinaire), menu, permissions serveur, sélecteur à badges, bandeau, fenêtre d'information, adaptation privée, restaurations, Aide (modes, 7 fiches, recherche), colonnes personnelles, mobile.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const BASE='http://127.0.0.1:18089/',must=(c,m)=>{if(!c)throw new Error(m);};
const login=async(browser,u,p,width=1280)=>{const ctx=await browser.newContext({viewport:{width,height:900}}),pg=await ctx.newPage(),errors=[];pg.setDefaultTimeout(30000);pg.on('pageerror',e=>errors.push(e.message));
  await pg.goto(BASE+'login.html');await pg.fill('#u',u);await pg.fill('#p',p);await pg.click('#auth-form button.primary');await pg.waitForURL('**/index.html');return {ctx,pg,errors};};
// appels API depuis la page (même client que l'interface : J.api / J.post)
const api=(pg,route,body)=>pg.evaluate(async([r,b])=>{try{const j=b?await J.post(r,b):await J.api(r);return {status:200,json:j};}catch(e){return {status:e.status||0,json:null,message:e.message};}},[route,body]);
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.JIGO_CHROMIUM,args:['--no-sandbox']});
 try{
  const A=await login(browser,'review_user','review-local-password'),U=await login(browser,'plain_user','plain-local-password');
  const ready=async pg=>{await pg.waitForFunction(()=>/Cliquez sur/.test(document.querySelector('#ct-ranking-status')?.textContent||''),null,{timeout:60000});await pg.click('#ct-apply');return pg.waitForFunction(()=>document.querySelector('#ct-strategy-count')?.textContent.trim().length>0&&document.querySelector('.sui-pick'),null,{timeout:60000});};
  await ready(A.pg);await ready(U.pg);
  // 1. menu : l'administration technique n'a que 7 entrées, absente pour un compte ordinaire ; menu Explorer personnel
  const sub=async(pg,id)=>pg.$$eval(`[data-sub="${id}"] .sv`,a=>a.map(x=>x.textContent.trim()));
  must(!(await U.pg.$('[data-sub="admin"]')),'Menu admin visible pour un compte ordinaire');
  const adm=await sub(A.pg,'admin');must(JSON.stringify(adm)===JSON.stringify(['FinanceDatabase','Yahoo Finance','Actions / ETF','Cron','Journaux','Splits','Données','Utilisateurs','Réglages']),'Menu admin : '+adm);
  const exp=await sub(U.pg,'explorer');must(JSON.stringify(exp)===JSON.stringify(['Recherche et résultats','Mes stratégies','Mes critères de recherche','Mes paramètres de scores','Mes colonnes et tris','Mes filtres et catégories']),'Menu Explorer : '+exp);
  must(await U.pg.$('#nav a[href="aide.html"]'),'Lien Aide absent');
  must(!(await U.pg.$('#nav a[href^="donnees.html"]')),'Menu Données visible pour un compte ordinaire');must((await api(U.pg,'data/overview')).json===null,'data/overview ouvert à un compte ordinaire');must((await api(A.pg,'data/overview')).json!==null,'data/overview refusé à l administrateur');
  // 2. permissions serveur
  for(const r of ['admin/scores','admin/table-layouts','admin/users']){const x=await api(U.pg,r);must(x.json===null,'Route admin ouverte à un compte ordinaire : '+r);}
  must((await api(A.pg,'admin/scores')).json!==null,'Admin refusé');
  // 3. sélecteur groupé : 7 intégrées Officielles, une entrée chacune
  const opts=async pg=>{await pg.click('.sui-pick-btn');const o=await pg.$$eval('.sui-opt',x=>x.map(e=>({id:e.dataset.id,label:e.querySelector('.grow').textContent.trim(),badge:e.querySelector('.badge').textContent.trim()})));const g=await pg.$$eval('.sui-grp',x=>x.map(e=>e.textContent.trim()));await pg.keyboard.press('Escape');return {o,g};};
  const u=await opts(U.pg);
  must(/^Stratégies intégrées \(7\)$/i.test(u.g[0]),'Groupe : '+u.g);must(u.o.filter(x=>x.badge.toLowerCase()==='officielle').length===7,'7 Officielles attendues : '+JSON.stringify(u.o));
  must(new Set(u.o.map(x=>x.label)).size===u.o.length,'Doublon de stratégie');
  must(await U.pg.$('.sui-banner'),'Bandeau absent');
  // 4. texte de la stratégie affiché une seule fois (sous le sélecteur), avec lien vers la fiche
  must(/montent très vite/.test(await U.pg.textContent('#ct-strategy-desc')),'Texte de la stratégie absent sous le sélecteur');must(await U.pg.$('.sui-pick-btn .sui-ico svg'),'Icône par défaut absente du sélecteur');must(!(await U.pg.$('#ct-info')),'Bouton d’info redondant encore présent');must(await U.pg.$('#ct-strategy-desc a[href^="aide.html#strategie-"]'),'Lien vers la fiche d’aide absent');const so=await U.pg.$$eval('#ct-sort option',o=>o.map(x=>x.value));const co=await U.pg.$$eval('#ct-table-head th',t=>t.map(x=>x.dataset.sortColumn).filter(Boolean));must(so[0]==='complex'&&so[1]==='simple'&&so[2]==='trend'||so[0]==='complex','Ordre des choix de tri : '+so.slice(0,4));
  // 5. adaptation privée : le compte ordinaire adapte Hausse calme, l'admin reste Officielle
  const state=(await api(U.pg,'my/scores')).json,calm=state.strategies.find(s=>s.name==='calm_rise');must(calm,'Profil calm_rise absent');
  const prof=JSON.parse(JSON.stringify(calm.current));Object.values(prof.periods).forEach(x=>delete x.sessions);prof.complex_weights.volatility-=5;prof.complex_weights.up_days+=5;
  const sv=await api(U.pg,'my/scores/save',{name:'calm_rise',profile:{name:'calm_rise',...prof}});must(sv.json,'Enregistrement refusé : '+sv.message);
  const st=async pg=>Object.fromEntries((await api(pg,'strategies/status')).json.strategies.map(s=>[s.name,s]));
  let su=await st(U.pg);const sa=await st(A.pg);
  must(su.calm_rise.status==='adapted'&&su.calm_rise.scores.modified>=1&&su.calm_rise.criteria.state==='official','Statut utilisateur : '+JSON.stringify(su.calm_rise));
  must(sa.calm_rise.status==='official','L’adaptation fuit vers un autre compte');
  must(['growth_v4','growth_regular','calm_rise','rebound','momentum_6m','momentum_12m','momentum_risk'].every(k=>su[k]),'7 stratégies attendues');
  await U.pg.goto(BASE+'mes-strategies.html');await U.pg.waitForSelector('[data-act="restore-scores"]');
  must((await U.pg.$$('[data-act="compare"]')).length===1,'Comparaison attendue pour une seule stratégie');
  await U.pg.click('[data-act="compare"]');must(await U.pg.$('.sui-cmp .mod'),'Tableau de comparaison absent');
  await U.pg.click('[data-act="restore-scores"]');await U.pg.locator('.btn.primary:has-text("Restaurer")').last().click();await U.pg.waitForTimeout(800);
  su=await st(U.pg);must(su.calm_rise.status==='official','Restauration des scores : '+su.calm_rise.status);
  // 6. pages personnelles
  await U.pg.goto(BASE+'mes-scores.html');await U.pg.waitForSelector('[data-a="tab"]');
  must(!(await U.pg.$$eval('[data-a="tab"]',b=>b.some(x=>/Suivi/.test(x.textContent)))),'Onglet de suivi visible côté utilisateur');
  await U.pg.goto(BASE+'mes-colonnes.html');await U.pg.waitForSelector('.ac-list');
  await U.pg.goto(BASE+'mes-filtres.html');await U.pg.waitForSelector('#ac-filter-select option',{state:'attached'});must(!U.pg.url().endsWith('index.html'),'Mes filtres redirige encore vers l Explorer');must((await U.pg.$$('[data-category-id]')).length>0,'Options éditables absentes de Mes filtres');
  // 7. Aide : cours interactif (un chapitre à la fois), recherche, modes, 7 fiches, démo pente/régularité, simulateur, section admin
  await U.pg.goto(BASE+'aide.html');await U.pg.waitForSelector('.h-body');
  must((await U.pg.$$('.h-body')).length===1,'Un seul chapitre attendu à l’écran');must(/Bienvenue/.test(await U.pg.textContent('.h-head h1')),'Premier chapitre : Bienvenue');
  must(!(await U.pg.$('#h-toc a[data-id="admin"]')),'Chapitre admin visible pour un compte ordinaire');
  must((await U.pg.$$('#h-toc a[data-id^="strat-"]')).length===8,'7 fiches + comparaison attendues dans le sommaire');
  await U.pg.click('#h-toc a[data-id="pente-regularite"]');await U.pg.waitForSelector('[data-demo=pr] svg');
  must((await U.pg.$$('[data-demo=pr] svg.hc-svg')).length===2,'Deux courbes attendues dans la démo');
  for(let i=0;i<4;i++)await U.pg.click('[data-demo=pr] button:has-text("Étape suivante")');
  must(/R² 1[,.]00/.test(await U.pg.textContent('[data-demo=pr]')),'Étape 5 sans R² d’Aurore');
  must(/Performance/.test(await U.pg.textContent('[data-demo=pr] table'))&&/Régularité/.test(await U.pg.textContent('[data-demo=pr] table')),'Tableau de la démo incomplet');
  await U.pg.click('.h-nav .btn.primary');await U.pg.waitForTimeout(300);must(!/Tendance, pente/.test(await U.pg.textContent('.h-head h1')),'Bouton Suivant sans effet');
  // chapitre scores : simulateur sans effet sur les vrais réglages
  const before=JSON.stringify((await api(U.pg,'my/scores')).json.strategies.map(x=>x.current));
  await U.pg.click('#h-toc a[data-id="scores"]');await U.pg.waitForSelector('[data-demo=sim] input[data-k]');
  const top0=await U.pg.textContent('[data-demo=sim] tbody tr:first-child th');await U.pg.fill('[data-demo=sim] input[data-k="volatility"]','100');await U.pg.fill('[data-demo=sim] input[data-k="dynamics"]','0');await U.pg.waitForTimeout(200);
  must(JSON.stringify((await api(U.pg,'my/scores')).json.strategies.map(x=>x.current))===before,'Le simulateur a modifié des réglages réels');
  must((await U.pg.$$('[data-demo=sim] tbody tr')).length===5,'5 titres fictifs attendus');
  // fiches des 7 stratégies, ancres historiques et lien depuis l’Explorer
  for(const id of ['fast','regular','calm','rebound','mom6','mom12','momrisk']){await U.pg.goto(BASE+'aide.html#strategie-'+id);await U.pg.waitForSelector('.h-body svg.hc-svg');must(/Les vrais critères/.test(await U.pg.textContent('.h-body')),'Fiche incomplète : '+id);}
  await U.pg.goto(BASE+'aide.html#strategie-fast');await U.pg.waitForSelector('[data-demo=fastdemo] table');must(/Comment Croissance rapide fonctionne/.test(await U.pg.textContent('.h-body')),'Explication détaillée de Croissance rapide absente');must((await U.pg.$$('[data-demo=fastdemo] tbody tr')).length===6,'Démo Croissance rapide incomplète');
  await U.pg.goto(BASE+'aide.html#strategie-fast');await U.pg.waitForSelector('.h-body');
  await U.pg.click('[data-mode="expert"]');await U.pg.waitForSelector('.h-body table');must(/Pente min/.test(await U.pg.textContent('.h-body')),'Fiche Expert sans seuil de pente');
  await U.pg.waitForTimeout(500);await U.pg.reload();await U.pg.waitForSelector('.h-body');must(await U.pg.getAttribute('[data-mode="expert"]','aria-pressed')==='true','Mode Expert non mémorisé');
  // recherche : ouvre directement le bon chapitre
  await U.pg.fill('#h-q','prix de revient');await U.pg.waitForTimeout(400);must(/Achats, ventes/.test(await U.pg.textContent('.h-head h1')),'Recherche : mauvais chapitre');
  await U.pg.fill('#h-q','');await U.pg.click('[data-mode="beginner"]');
  // dernier chapitre mémorisé à la réouverture sans ancre
  await U.pg.goto(BASE+'aide.html#/glossaire');await U.pg.waitForSelector('.help-dl');await U.pg.goto(BASE+'aide.html');await U.pg.waitForSelector('.help-dl');must(/Glossaire/.test(await U.pg.textContent('.h-head h1')),'Dernier chapitre non mémorisé');
  await U.pg.goto(BASE+'aide.html#/action-etf');await U.pg.waitForSelector('[data-quiz]');await U.pg.click('[data-quiz] .hq-o[data-ok="1"]');must(await U.pg.$('.hq-o.good'),'Quiz sans retour');
  await A.pg.goto(BASE+'aide.html');await A.pg.waitForSelector('#h-toc a[data-id="admin"]');
  // mot d'invitation visible de l'administrateur seulement
  must((await api(A.pg,'admin/settings',{name:'invite_code',value:'motdetest'})).json,'Mot d’invitation non enregistré');
  must((await api(A.pg,'admin/system')).json.settings.invite_code==='m'+'•'.repeat(8),'Mot d’invitation : l’administrateur doit le voir masqué (première lettre et longueur), jamais en clair');
  must((await api(U.pg,'admin/system')).json===null,'admin/system ouvert à un compte ordinaire');
  // 8. mobile : pas de débordement horizontal
  const M=await login(browser,'plain_user','plain-local-password',390);
  for(const f of ['aide.html','mes-strategies.html','mes-scores.html','index.html']){await M.pg.goto(BASE+f);await M.pg.waitForTimeout(1500);const over=await M.pg.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1?[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1&&!e.closest('.ct-table-wrap,.sui-scroll,table')).slice(0,6).map(e=>e.tagName+'.'+e.className+':'+Math.round(e.getBoundingClientRect().right)):null);must(!over,'Débordement horizontal mobile : '+f+' '+JSON.stringify(over));}
  const errs=[...A.errors,...U.errors,...M.errors];must(!errs.length,'Erreurs JS : '+errs.join(' | '));
  console.log('OK');
 }catch(e){console.error('FAIL',e.message);process.exitCode=1;}
 await browser.close();
})();
