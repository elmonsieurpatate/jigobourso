// Sonde de mise en page : mesure sur les vraies pages, rendues dans un navigateur, ce que les feuilles CSS produisent.
//  - débordement horizontal (une page ne doit jamais dépasser la fenêtre) ;
//  - écarts verticaux entre blocs consécutifs (enfants de main, de #page, des cartes) ;
//  - valeurs réellement rendues : espacements, tailles de police, interlignages, rayons, z-index.
// Usage : BASE=… USER_NAME=… PASS=… PLAYWRIGHT_MODULE=… JIGO_CHROMIUM=… node scripts/probe_layout.cjs [--out fichier.json] [--compare avant.json]
const fs = require('fs'), path = require('path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');
const BASE = process.env.BASE || 'http://127.0.0.1:18089';
const arg = n => { const i = process.argv.indexOf(n); return i > 0 ? process.argv[i + 1] : null; };
const PUBLIC = path.join(__dirname, '../app/public');

function pagesList() {
  const pages = fs.readdirSync(PUBLIC).filter(f => f.endsWith('.html') && !/^(login|recover|reset|verify-email|register)/.test(f));
  for (const t of ['fdb', 'yahoo', 'titres', 'cron', 'logs', 'users', 'scores', 'colonnes', 'settings']) pages.push('admin.html#' + t);
  for (const id of [1, 2]) for (const t of ['cours', 'analyse', 'fiche']) pages.push('titre.html?id=' + id + '#' + t);
  pages.push('aide.html#/intro');
  return pages;
}

function measure() {
  const vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const out = { gaps: [], gapsDetail: [], spacing: {}, font: {}, line: {}, radius: {}, z: {}, overflow: [], pageOverflow: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth), height: Math.round(document.documentElement.scrollHeight) };
  const bump = (o, k) => { o[k] = (o[k] || 0) + 1; };
  const vw = document.documentElement.clientWidth;
  for (const e of document.querySelectorAll('body *')) {
    if (!vis(e)) continue;
    const s = getComputedStyle(e), r = e.getBoundingClientRect();
    if (r.right > vw + 1 && !e.closest('.table-wrap,.tbl-scroll,[class*="scroll"],pre,svg,canvas') && s.position !== 'fixed') out.overflow.push((e.id ? '#' + e.id : '') + '.' + String(e.className).split(' ')[0] + ' ' + e.tagName + ' +' + Math.round(r.right - vw));
    for (const p of ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'marginTop', 'marginBottom', 'rowGap', 'columnGap']) { const v = s[p]; if (v && v !== '0px' && v !== 'normal' && v !== 'auto') bump(out.spacing, v); }
    if (e.children.length || e.textContent.trim()) bump(out.font, s.fontSize);
    if (e.childNodes.length && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) bump(out.line, s.lineHeight === 'normal' ? 'normal' : (parseFloat(s.lineHeight) / parseFloat(s.fontSize)).toFixed(2));
    if (s.borderTopLeftRadius !== '0px') bump(out.radius, s.borderTopLeftRadius);
    if (s.zIndex !== 'auto') bump(out.z, s.zIndex);
  }
  const stacks = [document.querySelector('main'), document.getElementById('page'), ...document.querySelectorAll('.card')].filter(Boolean);
  for (const st of stacks) {
    const kids = [...st.children].filter(vis);
    for (let i = 1; i < kids.length; i++) {
      const a = kids[i - 1].getBoundingClientRect(), b = kids[i].getBoundingClientRect();
      if (b.top >= a.bottom - 0.5 && b.left < a.right) {
        const g = Math.round((b.top - a.bottom) * 10) / 10, d = n => n.tagName.toLowerCase() + (n.id ? '#' + n.id : '') + String(n.className).split(' ').filter(Boolean).slice(0, 2).map(c => '.' + c).join('');
        out.gaps.push(g); out.gapsDetail.push([g, d(st), d(kids[i - 1]), d(kids[i])]);
      }
    }
  }
  return out;
}

function compare(a, b) {
  let n = 0;
  for (const k of Object.keys(b)) {
    const A = a[k], B = b[k];
    if (!A) { console.log('NOUVEAU', k); continue; }
    const dh = B.height - A.height, dg = JSON.stringify(A.gaps) !== JSON.stringify(B.gaps), oo = B.overflow.length - A.overflow.length;
    if (dh || dg || oo) { n++; console.log(k.padEnd(46), 'hauteur', (dh >= 0 ? '+' : '') + dh, 'écarts', dg ? 'modifiés' : 'identiques', 'débordements', A.overflow.length + '→' + B.overflow.length); }
  }
  console.log(n ? n + ' page(s) modifiée(s)' : 'mise en page identique');
}

(async () => {
  if (arg('--compare') && !arg('--out')) { compare(JSON.parse(fs.readFileSync(arg('--compare'))), JSON.parse(fs.readFileSync(arg('--now')))); return; }
  const browser = await chromium.launch({ executablePath: process.env.JIGO_CHROMIUM });
  const res = {};
  for (const w of [1280, 390]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: 900 } }), page = await ctx.newPage();
    await page.goto(BASE + '/login.html'); await page.fill('#u', process.env.USER_NAME); await page.fill('#p', process.env.PASS);
    await page.click('#auth-form button.primary'); await page.waitForURL('**/index.html');
    for (const p of pagesList()) {
      try { await page.goto(BASE + '/' + p, { waitUntil: 'networkidle', timeout: 60000 }); } catch (e) { continue; }
      await page.waitForTimeout(900);
      res[w + ' ' + p] = await page.evaluate(measure);
      if (arg('--shots') && w === 1280) { fs.mkdirSync(arg('--shots'), { recursive: true }); await page.screenshot({ path: path.join(arg('--shots'), p.replace(/[^a-z0-9]+/gi, '_') + '.png'), fullPage: true }); }
    }
    await ctx.close();
  }
  await browser.close();
  if (arg('--out')) fs.writeFileSync(arg('--out'), JSON.stringify(res));
  const agg = k => { const t = {}; for (const r of Object.values(res)) for (const [v, n] of Object.entries(r[k])) t[v] = (t[v] || 0) + n; return t; };
  console.log('pages mesurées :', Object.keys(res).length);
  for (const k of ['spacing', 'font', 'line', 'radius', 'z']) console.log(k.padEnd(8), Object.keys(agg(k)).length, 'valeurs rendues distinctes');
  const gaps = {}; for (const r of Object.values(res)) r.gaps.forEach(g => { gaps[g] = (gaps[g] || 0) + 1; });
  console.log('écarts verticaux entre blocs :', Object.keys(gaps).length, 'valeurs distinctes ->', Object.entries(gaps).sort((a, b) => b[1] - a[1]).slice(0, 12).map(([g, n]) => g + 'px×' + n).join(' '));
  const ov = Object.entries(res).filter(([, r]) => r.overflow.length);
  const po = Object.entries(res).filter(([, r]) => r.pageOverflow > 0);
  console.log('pages dont le défilement horizontal apparaît (scrollWidth > fenêtre) :', po.length, po.map(([k, r]) => k + ' +' + r.pageOverflow).join(' ; '));
  console.log('pages avec élément dépassant la fenêtre (hors zones défilantes) :', ov.length); ov.slice(0, 20).forEach(([k, r]) => console.log('  ', k, r.overflow.slice(0, 3).join(' | ')));
  if (arg('--compare')) compare(JSON.parse(fs.readFileSync(arg('--compare'))), res);
})();
