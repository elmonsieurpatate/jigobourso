/* Réglages personnels dans un vrai Chrome : modifier une stratégie de départ, l'enregistrer, la remettre par défaut ; enregistrer, renommer et supprimer une recherche ; menu « Gérer… ». */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const BASE='http://127.0.0.1:18089';
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.JIGO_CHROMIUM,args:['--no-sandbox']}),out={checks:{},errors:[]};
 const ctx=await browser.newContext({viewport:{width:1440,height:1100}}),page=await ctx.newPage();
 page.setDefaultTimeout(20000);page.on('pageerror',e=>out.errors.push(e.message));page.on('console',m=>{if(m.type()==='error'&&!/favicon/.test(m.location().url||''))out.errors.push(m.text())});
 const ok=(name,cond,detail)=>{out.checks[name]=!!cond;if(!cond)out.errors.push('KO '+name+(detail===undefined?'':' : '+JSON.stringify(detail)))};
 const slope=()=>page.inputValue('.sl[data-s="slope"] input.lo');
 const setSlope=async v=>{await page.fill('.sl[data-s="slope"] input.lo',String(v));await page.keyboard.press('Enter');await page.waitForTimeout(500)};
 const top=()=>page.locator('dialog[open]').last();
 try{
  await page.goto(BASE+'/login.html');await page.fill('#u','review_user');await page.fill('#p','review-local-password');await page.click('#auth-form button.primary');await page.waitForURL('**/index.html');
  await page.evaluate(()=>{localStorage.clear();sessionStorage.clear()});await page.goto(BASE+'/index.html');
  await page.locator('#strats .strat').first().waitFor();await page.locator('#saved-manage').waitFor();
  // 1. modifier « Croissance rapide » puis remplacer son réglage de départ
  await page.click('.strat[data-k="fast"]');await page.waitForTimeout(1000);
  ok('reglage_de_depart_rapide',(await slope())==='100',await slope());
  await setSlope(30);await page.click('#apply-menu');await page.waitForTimeout(1200);
  await page.click('#saved-save');await page.locator('#sv-target').waitFor();
  ok('choix_remplacer_le_reglage_propose',(await page.locator('#sv-target option').allInnerTexts()).some(t=>/Croissance rapide/.test(t)));
  await page.selectOption('#sv-target','preset');ok('nom_masque_pour_un_reglage',await page.locator('#sv-namebox').isHidden());
  await top().getByRole('button',{name:'Enregistrer'}).click();await page.waitForTimeout(1200);
  ok('carte_marquee_modifiee',await page.locator('.strat[data-k="fast"] .mod').count()===1);
  // 2. le réglage est retrouvé après rechargement et en revenant sur la carte
  await page.reload();await page.locator('#strats .strat').first().waitFor();await page.waitForTimeout(800);
  ok('marque_conservee_apres_rechargement',await page.locator('.strat[data-k="fast"] .mod').count()===1);
  await page.click('.strat[data-k="regular"]');await page.waitForTimeout(800);await page.click('.strat[data-k="fast"]');await page.waitForTimeout(1200);
  ok('reglage_personnel_reapplique',(await slope())==='30',await slope());
  ok('bouton_remettre_par_defaut_visible',await page.locator('#reset-default').isVisible()&&/Croissance rapide/.test(await page.locator('#reset-default').innerText()));
  // 3. menu Gérer : remettre par défaut
  await page.click('#saved-manage');await page.locator('dialog[open] [data-reset="fast"]').waitFor();
  ok('menu_liste_les_six_strategies',await page.locator('dialog[open] [data-use]').count()===6);
  ok('menu_signale_la_modification',/Modifiée/.test(await page.locator('dialog[open] tr:has([data-use="fast"])').innerText()));
  await page.click('dialog[open] [data-reset="fast"]');await page.waitForTimeout(400);
  await top().getByRole('button',{name:'Remettre par défaut'}).click();await page.waitForTimeout(1500);
  ok('menu_signale_le_retour_au_depart',/Réglage de départ/.test(await page.locator('dialog[open] tr:has([data-use="fast"])').innerText()));
  ok('carte_sans_marque',await page.locator('.strat[data-k="fast"] .mod').count()===0);
  await page.locator('dialog[open]').first().getByText('Fermer',{exact:true}).click();await page.waitForTimeout(500);
  ok('curseur_revenu_au_depart',(await slope())==='100',await slope());
  // 4. recherche enregistrée : créer, renommer, supprimer
  await setSlope(20);await page.click('#apply-menu');await page.waitForTimeout(1000);
  await page.click('#saved-save');await page.locator('#sv-name').waitFor();ok('cible_libre_par_defaut_apres_reglage',await page.locator('#sv-target').inputValue()==='new');
  await page.fill('#sv-name','e2e test');await top().getByRole('button',{name:'Enregistrer'}).click();await page.waitForTimeout(1200);
  ok('recherche_dans_la_liste',(await page.locator('#saved-sel option').allInnerTexts()).some(t=>/e2e test/.test(t)));
  await page.click('#saved-manage');await page.locator('dialog[open] [data-sren]').waitFor();
  await page.click('dialog[open] [data-sren]');await page.locator('#rn-name').waitFor();await page.fill('#rn-name','e2e renommée');await top().getByRole('button',{name:'Renommer'}).click();await page.waitForTimeout(1200);
  ok('recherche_renommee',/e2e renommée/.test(await page.locator('dialog[open]').first().innerText())&&!/e2e test/.test(await page.locator('dialog[open]').first().innerText()));
  await page.click('dialog[open] [data-sdel]');await page.waitForTimeout(400);await top().getByRole('button',{name:'Supprimer'}).click();await page.waitForTimeout(1200);
  ok('recherche_supprimee',/Aucune pour l’instant/.test(await page.locator('dialog[open]').first().innerText()));
  await page.locator('dialog[open]').first().getByText('Fermer',{exact:true}).click();
  // 5. aucun débordement sur téléphone
  await page.setViewportSize({width:375,height:900});await page.waitForTimeout(400);ok('pas_de_debordement_375',!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)));
 }catch(e){out.errors.push('exception '+e.message)}
 console.log(JSON.stringify(out));await browser.close();process.exit(out.errors.length?1:0);
})();
