// Sonde de parité F08 : pour chaque élément portant une classe utilitaire u-… ou is-off, vérifie que la classe donne EXACTEMENT le même style calculé
// que l'ancien style en ligne (la déclaration appliquée en ligne sur le même élément ne doit rien changer).
// Usage : BASE=http://127.0.0.1:18089 USER_NAME=… PASS=… PLAYWRIGHT_MODULE=… JIGO_CHROMIUM=… node scripts/probe_utilities.cjs
const fs = require('fs'), path = require('path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');
const galleryServer = require('../tests/visual/gallery-server.cjs');
const BASE = process.env.BASE || 'http://127.0.0.1:18089';
const css = fs.readFileSync(path.join(__dirname, '../app/public/assets/base.css'), 'utf8');
const decl = {};
for (const m of css.matchAll(/\.((?:u-[a-z0-9-]+|is-off))\s*\{\s*([a-z-]+):\s*([^;!]+?)\s*!important\s*(?:;|(?=\}))/g)) decl[m[1]] = [m[2], m[3]];
function parity(decl) {
  const out = { n: 0, seen: [], bad: [] };
  for (const el of document.querySelectorAll('[class*="u-"], .is-off')) {
    for (const c of el.classList) {
      const d = decl[c]; if (!d) continue; out.seen.push(c); out.n++;
      const [prop, val] = d, original = el.style.cssText;
      const before = getComputedStyle(el).getPropertyValue(prop);
      const dynamic = el.style.getPropertyValue(prop);
      if (dynamic && el.style.getPropertyPriority(prop) !== 'important') {
        try {
          el.style.setProperty(prop, dynamic, 'important');
          const intended = getComputedStyle(el).getPropertyValue(prop);
          if (before !== intended) out.bad.push([c, 'style dynamique bloqué', before, intended]);
        } finally { el.style.cssText = original; }
      }
      try {
        el.style.setProperty(prop, val, 'important');
        const after = getComputedStyle(el).getPropertyValue(prop);
        if (before !== after) out.bad.push([c, before, after, el.tagName]);
      } finally { el.style.cssText = original; }
    }
  }
  return out;
}

const defined = new Set([...css.matchAll(/\.((?:u-[a-z0-9-]+|is-off))\s*\{/g)].map(m => m[1]));
if (!defined.size || defined.size !== Object.keys(decl).length) throw new Error('Une classe utilitaire échappe au parseur de déclarations');

(async () => {
  const gallery = await galleryServer();
  const browser = await chromium.launch({ executablePath: process.env.JIGO_CHROMIUM });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  let contracts = 0;
  // Toutes les classes, y compris les états rarement atteints, dans trois contextes
  // de cascade. Ce contrat ne remplace pas les parcours des vraies pages ci-dessous.
  for (const width of [390, 1280]) for (const theme of ['light', 'dark']) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(gallery.url);
    await page.evaluate(([names, theme]) => {
      document.documentElement.dataset.theme = theme;
      const host = document.createElement('section'); host.className = 'card';
      for (const name of names) for (const context of ['', 'card', 'btn']) {
        const e = document.createElement('div'); e.className = `${context} ${name}`;
        e.textContent = 'Libellé de référence'; host.append(e);
      }
      document.body.replaceChildren(host);
    }, [Object.keys(decl), theme]);
    await page.addStyleTag({ content: '* { transition: none !important; animation: none !important; }' });
    const r = await page.evaluate(parity, decl);
    if (r.seen.length !== Object.keys(decl).length * 3 || r.bad.length) throw new Error(`Contrats ${width}/${theme}: ${JSON.stringify(r.bad)}`);
    contracts += r.n;
  }
  console.log(`Contrats utilitaires : ${Object.keys(decl).length}/${Object.keys(decl).length} classes, ${contracts} comparaisons (2 thèmes × 2 largeurs × 3 contextes).`);
  if (process.argv.includes('--contracts-only')) { await browser.close(); await gallery.close(); return; }
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(BASE + '/login.html'); await page.fill('#u', process.env.USER_NAME); await page.fill('#p', process.env.PASS);
  await page.click('#auth-form button.primary'); await page.waitForURL('**/index.html');
  const pages = fs.readdirSync(path.join(__dirname, '../app/public')).filter(f => f.endsWith('.html') && !/^(login|recover|reset|verify-email)/.test(f));
  // Vues atteintes par l'adresse (onglets d'administration, chapitres d'aide, fiche d'un titre) : sans elles la plupart des gabarits ne s'affichent pas.
  for (const t of ['fdb', 'yahoo', 'titres', 'cron', 'logs', 'users', 'scores', 'colonnes', 'settings']) pages.push('admin.html#' + t);
  const help = fs.readFileSync(path.join(__dirname, '../app/public/assets/help-ch-bases.js'), 'utf8') + ['help-ch-jigo', 'help-ch-mesures', 'help-ch-outils', 'help-ch-patrimoine', 'help-ch-strat'].map(f => fs.readFileSync(path.join(__dirname, '../app/public/assets/' + f + '.js'), 'utf8')).join('');
  for (const m of new Set([...help.matchAll(/id: *['"]([a-z0-9-]+)['"]/g)].map(x => x[1]))) pages.push('aide.html#/' + m);
  for (const id of [1, 2, 3]) for (const t of ['cours', 'analyse', 'fiche']) pages.push('titre.html?id=' + id + '#' + t);
  let checked = 0, bad = [], seen = new Set(), withClass = 0;
  for (const p of pages) {
    try { await page.goto(BASE + '/' + p, { waitUntil: 'networkidle', timeout: 60000 }); } catch (e) { throw new Error(`${p}: navigation impossible: ${e.message}`); }
    await page.waitForTimeout(1200);
    const r = await page.evaluate(parity, decl);
    checked += r.n; r.seen.forEach(c => seen.add(c)); r.bad.forEach(b => bad.push([p, ...b]));
    console.log(p.padEnd(34), r.n, 'éléments', r.bad.length ? 'ÉCART ' + r.bad.length : 'ok');
  }
  console.log('classes distinctes rencontrées :', seen.size, '/', Object.keys(decl).length, ' vérifications :', checked, ' écarts :', bad.length);
  console.log('Couvertes par contrat seulement :', Object.keys(decl).filter(c => !seen.has(c)).join(', '));
  bad.slice(0, 10).forEach(b => console.log('ÉCART', JSON.stringify(b)));
  await browser.close(); await gallery.close(); process.exit(bad.length ? 1 : 0);
})();

process.on('unhandledRejection', e => { console.error(e.message); process.exit(1); });
