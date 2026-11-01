/* Réglages personnels et filtres enregistrés dans un vrai Chrome ; vérifie aussi que les filtres persistent entre Explorer et la page dédiée. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const BASE='http://127.0.0.1:18089';
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.JIGO_CHROMIUM,args:['--no-sandbox']}),out={checks:{},errors:[]};
 const ctx=await browser.newContext({viewport:{width:1440,height:1100}}),page=await ctx.newPage();
 page.setDefaultTimeout(20000);page.on('pageerror',e=>out.errors.push(e.message));page.on('console',m=>{if(m.type()==='error'&&!/favicon/.test(m.location().url||''))out.errors.push(m.text())});
 const ok=(name,cond,detail)=>{out.checks[name]=!!cond;if(!cond)out.errors.push('KO '+name+(detail===undefined?'':' : '+JSON.stringify(detail)))};
 const slope=()=>page.inputValue('.sl[data-s="slope"] input.lo');
 const setSlope=async v=>{await page.fill('.sl[data-s="slope"] input.lo',String(v));await page.keyboard.press('Enter');await page.waitForTimeout(400)};
 const dialog=()=>page.locator('dialog[open]').last();
 try{
  await page.goto(BASE+'/login.html');await page.fill('#u','review_user');await page.fill('#p','review-local-password');await page.click('#auth-form button.primary');await page.waitForURL('**/index.html');
  await page.evaluate(()=>{localStorage.clear();sessionStorage.clear()});await page.goto(BASE+'/index.html');
  await page.locator('#strats .strat').first().waitFor();await page.locator('#saved-manage').waitFor();
  // Modifier le réglage personnel de croissance rapide.
  await page.click('.strat[data-k="fast"]');await page.waitForTimeout(700);ok('reglage_depart_rapide',(await slope())==='100',await slope());
  await setSlope(30);await page.click('#apply-menu');await page.waitForTimeout(800);await page.click('#saved-save');await page.locator('#sv-target').waitFor();
  await page.selectOption('#sv-target','preset');await dialog().getByRole('button',{name:'Enregistrer'}).click();await page.waitForTimeout(700);
  ok('carte_marquee_modifiee',await page.locator('.strat[data-k="fast"] .mod').count()===1);
  await page.goto(BASE+'/mes-filtres.html');await page.locator('.filter-card').first().waitFor();
  ok('titre_mes_filtres',await page.locator('h1').innerText()==='Mes filtres');
  ok('six_profils_sur_page',await page.locator('.filter-card').count()===6);
  ok('reglage_personnel_visible',/Personnalisée/.test(await page.locator('.filter-card:has([data-reset-preset="fast"])').innerText()));
  await page.click('[data-reset-preset="fast"]');await dialog().getByRole('button',{name:'Réinitialiser'}).click();await page.waitForTimeout(700);
  ok('profil_reinitialise_sur_page',/Réglage de départ/.test(await page.locator('.filter-card:has([data-reset-preset="fast"])').innerText()));
  // Modifier une recherche, conserver VOO + négociabilité désactivée + statut Tous.
  await page.goto(BASE+'/index.html');await page.locator('#strats .strat').first().waitFor();
  await page.fill('#q','VOO');await page.locator('#status-tabs button[data-s="all"]').click();await page.waitForTimeout(500);await page.uncheck('#tradable');await page.waitForTimeout(300);
  await page.click('#saved-save');await page.fill('#sv-name','e2e filtres');await dialog().getByRole('button',{name:'Enregistrer'}).click();await page.waitForTimeout(500);
  await page.goto(BASE+'/mes-filtres.html');await page.locator('[data-edit-search]').waitFor();
  ok('filtre_enregistre_resume',/VOO/.test(await page.locator('.filter-card:has([data-edit-search])').innerText()));
  await page.click('[data-edit-note]');await page.selectOption('#filter-icon','⚡');await page.fill('#filter-description','Trouver les ETF qui bougent vite.');await dialog().getByRole('button',{name:'Enregistrer'}).click();await page.waitForTimeout(400);
  const savedCard=page.locator('.filter-card:has([data-edit-search])');
  ok('note_strategie_visible',/Trouver les ETF qui bougent vite/.test(await savedCard.innerText()));
  ok('icone_du_filtre_visible',/⚡/.test(await savedCard.innerText()));
  await page.click('[data-edit-search]');await page.waitForURL('**/index.html?edit=1');await page.waitForFunction(()=>document.querySelector('#q')?.value==='VOO'&&!document.querySelector('#editor')?.hidden);
  ok('recherche_restaurée',await page.inputValue('#q')==='VOO');
  ok('case_négociabilité_restaurée',await page.isChecked('#tradable')===false);
  ok('statut_tous_restauré',await page.locator('#status-tabs button.on').getAttribute('data-s')==='all');
  const rankingPill=page.locator('#strats .saved-strategy').filter({hasText:'e2e filtres'});
  ok('filtre_visible_avec_strategies',await rankingPill.count()===1&&await rankingPill.getAttribute('class').then(x=>x.includes('on')));
  ok('note_visible_sur_carte_strategie',/Trouver les ETF qui bougent vite/.test(await rankingPill.innerText()));
  ok('icone_visible_sur_carte_strategie',/⚡/.test(await rankingPill.innerText()));
  await page.click('.strat[data-k="regular"]');await page.waitForTimeout(400);
  ok('filtre_reste_disponible_apres_changement',await page.locator('#strats .saved-strategy').filter({hasText:'e2e filtres'}).count()===1);
  await page.locator('#strats .saved-strategy').filter({hasText:'e2e filtres'}).click();await page.waitForTimeout(400);
  ok('filtre_peut_etre_reactive',await page.locator('#strats .saved-strategy.on').filter({hasText:'e2e filtres'}).count()===1);
  // Renommer puis supprimer depuis la page (les confirmations seules restent modales).
  await page.goto(BASE+'/mes-filtres.html');await page.locator('[data-rename-search]').waitFor();await page.click('[data-rename-search]');
  await page.fill('#rename-filter','e2e renommé');await dialog().getByRole('button',{name:'Enregistrer'}).click();await page.waitForTimeout(400);
  ok('filtre_renommé',await page.getByText('e2e renommé',{exact:true}).count()===1);
  await page.click('[data-delete-search]');await dialog().getByRole('button',{name:'Supprimer'}).click();await page.waitForTimeout(400);
  ok('filtre_supprimé',await page.locator('[data-delete-search]').count()===0);
  for(const width of [375,390,1280]){await page.setViewportSize({width,height:900});await page.waitForTimeout(250);ok('pas_de_debordement_'+width,!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)))}
  await page.goto(BASE+'/index.html?manage=1');await page.waitForURL('**/mes-filtres.html');ok('ancienne_entree_redirige_vers_page',true);
 }catch(e){out.errors.push('exception '+e.message)}
 console.log(JSON.stringify(out));await browser.close();process.exit(out.errors.length?1:0);
})();
