/* Filtre « Titres facilement négociables » dans un vrai Chrome : activé par défaut, un clic pour tout voir, préférence conservée, rang d'origine visible, explications des fiches. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE),fs=require('fs');
const BASE='http://127.0.0.1:18089';
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.JIGO_CHROMIUM,args:['--no-sandbox']}),out={checks:{},errors:[]};
 const ctx=await browser.newContext({viewport:{width:1280,height:900}}),page=await ctx.newPage();
 page.setDefaultTimeout(20000);page.on('pageerror',e=>out.errors.push(e.message));page.on('console',m=>{if(m.type()==='error')out.errors.push(m.text())});
 const ok=(name,cond,detail)=>{out.checks[name]=!!cond;if(!cond)out.errors.push('KO '+name+(detail===undefined?'':' : '+JSON.stringify(detail)))};
 const rows=async()=>{await page.locator('.rtable tbody tr').first().waitFor();return page.locator('.rtable tbody tr .name .sub').allInnerTexts()};
 const symbols=async()=>(await rows()).map(t=>t.split(' · ')[0].trim());
 const load=async()=>{await page.goto(BASE+'/index.html');await page.locator('#tradable').waitFor();await page.locator('.rtable tbody tr').first().waitFor();await page.locator('#size').selectOption('100');await page.waitForTimeout(800)};
 const retry=async(fn)=>{for(let i=0;i<20;i++){if(await fn())return true;await page.waitForTimeout(250)}return false};
 try{
  await page.goto(BASE+'/login.html');await page.fill('#u','review_user');await page.fill('#p','review-local-password');await page.click('#auth-form button.primary');await page.waitForURL('**/index.html');
  await page.evaluate(()=>{localStorage.clear();sessionStorage.clear()});
  await load();
  ok('actif_par_defaut',await page.locator('#tradable').isChecked());
  const on=await symbols();
  const limited=['TEST03.PA','TEST04.PA','TEST05.PA','TEST06.PA','TEST07.PA','TEST08.PA'];
  ok('limitees_masquees',limited.every(s=>!on.includes(s)),on.slice(0,10));
  ok('visibles_presentes',on.includes('TEST09.PA')||on.includes('TEST13.PA')||on.length>0,on.length);
  const note=await page.locator('#tradable-note').innerText();
  ok('note_masques',/masqué/.test(note),note);
  ok('rang_original_affiche',await page.locator('.rtable tbody tr .rk .sub').first().innerText().then(t=>/^rang \d+/.test(t),()=>false));
  // un clic : tout le catalogue
  await page.locator('#tradable').uncheck();
  ok('tout_affiche',await retry(async()=>{const all=await symbols();return limited.every(s=>all.includes(s))}));
  const off=await symbols();
  const masked=Number((note.match(/(\d+)\s+titre/)||[])[1]);
  ok('compte_coherent',masked>0&&off.length-on.length===masked,{masked,on:on.length,off:off.length});
  ok('note_tout_affiche',/Tous les titres/.test(await page.locator('#tradable-note').innerText()));
  // préférence conservée à la navigation
  await load();
  ok('preference_conservee',!(await page.locator('#tradable').isChecked()));
  await page.locator('#tradable').check();
  await load();
  ok('reactive_conservee',await page.locator('#tradable').isChecked());
  // fiches : explication cohérente avec le filtre
  const sheet=async(id)=>{await page.goto(BASE+'/titre.html?id='+id);await page.locator('.hero').waitFor();await page.waitForTimeout(600);return page.locator('#main').innerText()};
  const limitedSheet=await sheet(3);
  ok('fiche_limitee_accessible',/Négociabilité limitée/.test(limitedSheet)&&/décochez/.test(limitedSheet),limitedSheet.slice(0,300));
  const easySheet=await sheet(14);
  ok('fiche_facile',/Facilement négociable/.test(easySheet)&&!/n’apparaît pas dans les classements/.test(easySheet));
  const watch=await sheet(9);
  ok('fiche_vigilance',/à surveiller/i.test(watch));
  const unknown=await sheet(1004);
  ok('fiche_inconnue',/non déterminée/.test(unknown)&&/ne signifie pas qu’il est peu liquide/.test(unknown),unknown.slice(0,300));
  out.overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  ok('pas_de_debordement',!out.overflow);
  await page.setViewportSize({width:375,height:800});await load();
  ok('mobile_sans_debordement',!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)));
  ok('mobile_option_visible',await page.locator('#tradable').isVisible());
  await page.screenshot({path:'audit-results/tradability-375.png'});
 }catch(e){out.errors.push('exception : '+e.message)}
 await browser.close();
 fs.writeFileSync('audit-results/tradability.json',JSON.stringify(out,null,2));console.log(JSON.stringify(out));
 if(out.errors.length||Object.values(out.checks).some(v=>!v)){console.log('::error title=Navigateur négociabilité::'+JSON.stringify(out).slice(0,1500));process.exit(1)}
})();
