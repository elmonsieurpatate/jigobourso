/* Menu de l'Explorer dans un vrai Chrome : cartes de stratégie (dont les deux Momentum), bulles d'aide, curseurs de critères, raccourcis Prix / Volume / Capitalisation / Europe (PEA), mobile sans débordement. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const BASE='http://127.0.0.1:18089';
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.JIGO_CHROMIUM,args:['--no-sandbox']}),out={checks:{},errors:[]};
 const ctx=await browser.newContext({viewport:{width:1440,height:1100}}),page=await ctx.newPage();
 page.setDefaultTimeout(20000);page.on('pageerror',e=>out.errors.push(e.message));page.on('console',m=>{if(m.type()==='error'&&!/favicon/.test(m.location().url||''))out.errors.push(m.text())});
 const ok=(name,cond,detail)=>{out.checks[name]=!!cond;if(!cond)out.errors.push('KO '+name+(detail===undefined?'':' : '+JSON.stringify(detail)))};
 try{
  await page.goto(BASE+'/login.html');await page.fill('#u','review_user');await page.fill('#p','review-local-password');await page.click('#auth-form button.primary');await page.waitForURL('**/index.html');
  await page.evaluate(()=>{localStorage.clear();sessionStorage.clear()});await page.goto(BASE+'/index.html');
  await page.locator('#strats .strat').first().waitFor();await page.locator('.rtable tbody tr').first().waitFor();
  const keys=await page.locator('#strats .strat-grid .strat').evaluateAll(l=>l.map(e=>e.dataset.k));
  ok('six_cartes_dans_l_ordre',JSON.stringify(keys)===JSON.stringify(['regular','fast','recovery','low_volatility','momentum','momentum12']),keys);
  ok('cartes_libelles',(await page.locator('#strats').innerText()).includes('Momentum 6 mois')&&(await page.locator('#strats').innerText()).includes('252 → 21 séances'));
  await page.click('.strat[data-k="momentum12"]');await page.waitForTimeout(1200);
  ok('momentum12_actif',await page.locator('.strat.on[data-k="momentum12"]').count()===1);
  ok('resume_momentum12',/momentum 12 mois/.test(await page.locator('#strategy-summary').innerText()));
  ok('curseurs_inactifs_pour_momentum',await page.locator('.sl.off').count()>=3);
  await page.click('.q[data-help="momentum12"]');await page.locator('.helppop').waitFor();
  const help=await page.locator('.helppop').innerText();ok('aide_avec_mention_des_risques',/Aucune performance n’est garantie/.test(help)&&/12 mois/.test(help),help.slice(0,80));
  await page.keyboard.press('Escape');ok('aide_fermee',await page.locator('.helppop').count()===0);
  await page.click('.strat[data-k="regular"]');await page.waitForTimeout(1000);
  ok('curseur_regularite_lit_la_strategie',(await page.inputValue('.sl[data-s="r2"] input.lo'))==='0,56');
  await page.fill('.sl[data-s="slope3"] input.lo','40');await page.keyboard.press('Enter');await page.waitForTimeout(1500);
  ok('reglage_devient_personnalise',/Vos réglages/.test(await page.locator('#strats .strat.on').first().innerText()));
  const slope=await page.evaluate(()=>JSON.parse(localStorage.getItem('jigo_explorer2')).config.periods.find(p=>p.id==='quarter').min_slope);
  ok('pente_convertie_en_rythme_par_seance',Math.abs(slope-0.13361)<0.001,slope);
  const th=page.locator('.sl[data-s="vol3"] .dr-th.hi'),box=await th.boundingBox();
  await page.mouse.move(box.x+10,box.y+10);await page.mouse.down();await page.mouse.move(box.x-90,box.y+10,{steps:6});await page.mouse.up();await page.waitForTimeout(1500);
  const vol=parseFloat((await page.inputValue('.sl[data-s="vol3"] input.hi')).replace(',','.'));ok('volatilite_max_deplacee',vol<9.9,vol);
  await page.selectOption('#f-price','10|50');await page.selectOption('#f-volume','100000');await page.selectOption('#cap','mid');await page.selectOption('#market','__pea');await page.waitForTimeout(1500);
  ok('raccourcis_ecrivent_dans_le_tiroir',(await page.inputValue('#min_price'))==='10'&&(await page.inputValue('#budget'))==='50'&&(await page.inputValue('#min_volume'))==='100000');
  ok('drapeau_europe',(await page.locator('#market-flag svg circle').count())>=12);
  await page.reload();await page.locator('#strats .strat').first().waitFor();await page.waitForTimeout(1200);
  ok('choix_conserves_au_rechargement',(await page.inputValue('#f-price'))==='10|50'&&(await page.inputValue('#market'))==='__pea'&&(await page.inputValue('#cap'))==='mid');
  await page.click('#reset-filters');await page.waitForTimeout(800);
  ok('reinitialisation',(await page.inputValue('#f-price'))===''&&(await page.inputValue('#market'))===''&&(await page.inputValue('#cap'))==='');
  for(const width of [375,390,1280]){await page.setViewportSize({width,height:900});await page.waitForTimeout(400);ok('pas_de_debordement_'+width,!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)))}
 }catch(e){out.errors.push('exception '+e.message)}
 console.log(JSON.stringify(out));await browser.close();process.exit(out.errors.length?1:0);
})();
