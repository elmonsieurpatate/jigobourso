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
  const ready=pg=>pg.waitForFunction(()=>document.querySelector('#ct-strategy-count')?.textContent.trim().length>0&&document.querySelector('.sui-pick'),null,{timeout:60000});
  await ready(A.pg);await ready(U.pg);
  // 1. menu : l'administration technique n'a que 7 entrées, absente pour un compte ordinaire ; menu Explorer personnel
  const sub=async(pg,id)=>pg.$$eval(`[data-sub="${id}"] .sv`,a=>a.map(x=>x.textContent.trim()));
  must(!(await U.pg.$('[data-sub="admin"]')),'Menu admin visible pour un compte ordinaire');
  const adm=await sub(A.pg,'admin');must(JSON.stringify(adm)===JSON.stringify(['FinanceDatabase','Yahoo Finance','Actions / ETF','Cron','Journaux','Utilisateurs','Réglages']),'Menu admin : '+adm);
  const exp=await sub(U.pg,'explorer');must(JSON.stringify(exp)===JSON.stringify(['Recherche et résultats','Mes stratégies','Mes critères de recherche','Mes paramètres de scores','Mes colonnes et tris','Mes filtres et catégories']),'Menu Explorer : '+exp);
  must(await U.pg.$('#nav a[href="aide.html"]'),'Lien Aide absent');
  // 2. permissions serveur
  for(const r of ['admin/scores','admin/table-layouts','admin/users']){const x=await api(U.pg,r);must(x.json===null,'Route admin ouverte à un compte ordinaire : '+r);}
  must((await api(A.pg,'admin/scores')).json!==null,'Admin refusé');
  // 3. sélecteur groupé : 7 intégrées Officielles, une entrée chacune
  const opts=async pg=>{await pg.click('.sui-pick-btn');const o=await pg.$$eval('.sui-opt',x=>x.map(e=>({id:e.dataset.id,label:e.querySelector('.grow').textContent.trim(),badge:e.querySelector('.sui-badge').textContent.trim()})));const g=await pg.$$eval('.sui-grp',x=>x.map(e=>e.textContent.trim()));await pg.keyboard.press('Escape');return {o,g};};
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
  // 7. Aide : modes, 7 fiches, recherche, section admin
  await U.pg.goto(BASE+'aide.html');await U.pg.waitForSelector('#strategies .sui-card');
  must((await U.pg.$$('#strategies article[id^="strategie-"]')).length===7,'7 fiches attendues');
  must(await U.pg.$('#strategies table.sui-cmp'),'Comparatif absent');must(await U.pg.$('#scores .sui-comp'),'Cartes des composantes de score absentes');must(/pente/i.test(await U.pg.textContent('#premiers-pas'))&&/filtrage/i.test(await U.pg.textContent('#premiers-pas')),'Introduction de l’aide incomplète');must(await U.pg.$eval('#help-nav a',a=>a.getAttribute('href'))==='#premiers-pas','Aide : première rubrique');
  must(!(await U.pg.$('#administration')),'Rubrique admin visible pour un compte ordinaire');
  await U.pg.click('[data-mode="expert"]');await U.pg.waitForSelector('#strategie-fast table.sui-cmp');
  must(/pente ≥/.test(await U.pg.textContent('#strategie-fast')),'Fiche Expert sans seuil de pente');
  await U.pg.waitForTimeout(500);await U.pg.reload();await U.pg.waitForSelector('#strategies .sui-card');must(await U.pg.getAttribute('[data-mode="expert"]','aria-pressed')==='true','Mode Expert non mémorisé');
  await U.pg.fill('#help-q','lots');await U.pg.waitForTimeout(200);must(await U.pg.$('#achats-ventes'),'Recherche « lots » sans résultat');
  await U.pg.fill('#help-q','');await U.pg.click('[data-mode="beginner"]');await U.pg.waitForSelector('#parcours .help-path');must((await U.pg.$$('#scores .sui-comp')).length===10,'Composantes du score : 10 cartes attendues');must((await U.pg.$$('#parcours .help-path > li')).length===6,'Parcours guidé : 6 étapes attendues');must((await U.pg.$$('#parcours .help-if')).length>=4,'Parcours : encadrés « Si… alors… » absents');
  must(/Consumer Discretionary/.test(await U.pg.textContent('#bases'))&&/Place de cotation/.test(await U.pg.textContent('#bases'))&&/ETF/.test(await U.pg.textContent('#bases')),'Bases de la bourse incomplètes');
  await A.pg.goto(BASE+'aide.html');await A.pg.waitForSelector('#administration');
  // mot d'invitation visible de l'administrateur seulement
  must((await api(A.pg,'admin/settings',{name:'invite_code',value:'motdetest'})).json,'Mot d’invitation non enregistré');
  must((await api(A.pg,'admin/system')).json.settings.invite_code==='motdetest','Mot d’invitation non visible de l’administrateur');
  must((await api(U.pg,'admin/system')).json===null,'admin/system ouvert à un compte ordinaire');
  // 8. mobile : pas de débordement horizontal
  const M=await login(browser,'plain_user','plain-local-password',390);
  for(const f of ['aide.html','mes-strategies.html','mes-scores.html','index.html']){await M.pg.goto(BASE+f);await M.pg.waitForTimeout(1500);const over=await M.pg.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1?[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1&&!e.closest('.ct-table-wrap,.sui-scroll,table')).slice(0,6).map(e=>e.tagName+'.'+e.className+':'+Math.round(e.getBoundingClientRect().right)):null);must(!over,'Débordement horizontal mobile : '+f+' '+JSON.stringify(over));}
  const errs=[...A.errors,...U.errors,...M.errors];must(!errs.length,'Erreurs JS : '+errs.join(' | '));
  console.log('OK');
 }catch(e){console.error('FAIL',e.message);process.exitCode=1;}
 await browser.close();
})();
