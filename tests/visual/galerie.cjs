// Référence visuelle stable : styles calculés des composants de design/galerie.html (clair/sombre, 1280/390 px).
// Compare à tests/visual/galerie.json ; `node tests/visual/galerie.cjs --update` régénère la référence après un changement de design VOULU.
// Captures PNG écrites dans tests/visual/out/ (ignorées par Git) pour la revue humaine.
const fs = require('fs'), path = require('path');
const http = require('http');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE);
const ROOT = path.resolve(__dirname, '../..'), REF = path.join(__dirname, 'galerie.json'), OUT = path.join(__dirname, 'out');
const PROPS = ['fontSize', 'fontWeight', 'letterSpacing', 'lineHeight', 'color', 'backgroundColor', 'borderTopWidth', 'borderTopColor', 'borderTopLeftRadius', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'height', 'width', 'boxShadow'];
const TARGETS = {
  h1: 'h1', h2: 'h2', h3: 'h3', h4: 'h4', p: 'p', small: 'p.small',
  btn: '.btn:not(.primary):not(.ghost):not(.danger):not(.sm):not(.lg):not(.icon)', btnPrimary: '.btn.primary', btnGhost: '.btn.ghost', btnDanger: '.btn.danger', btnSm: '.btn.sm', btnLg: '.btn.lg', btnIcon: '.btn.icon:not(.sm)',
  input: 'input[type=text]', number: 'input[type=number]', select: 'select', checkbox: 'input[type=checkbox]:not(.switch)', radio: 'input[type=radio]', switch: 'input.switch',
  tab: '.tabs button[aria-selected=true]', tabIdle: '.tabs button[aria-selected=false]', seg: '.seg', segOn: '.seg button.on', segOff: '.seg button:not(.on)',
  badge: '.badge:not(.accent):not(.ok):not(.warn):not(.danger):not(.info):not(.outline):not(.sm)', badgeAccent: '.badge.accent', badgeOk: '.badge.ok', badgeWarn: '.badge.warn', badgeDanger: '.badge.danger',
  card: 'section.card', notice: '.notice:not(.warn):not(.err)', noticeWarn: '.notice.warn', noticeErr: '.notice.err', kpi: '.card.kpi', th: 'th', td: 'td',
};
(async () => {
  // Servir la galerie en HTTP comme les pages réelles, y compris dans les
  // navigateurs qui interdisent file:. Le serveur écoute seulement en local.
  let server;
  let url = process.env.GALLERY_URL;
  if (!url) {
    server = http.createServer((req, res) => {
      const name = new URL(req.url, 'http://localhost').pathname;
      if (name !== '/design/galerie.html' && !/^\/app\/public\/assets\/[\w./-]+$/.test(name)) { res.writeHead(404).end(); return; }
      const file = path.resolve(ROOT, '.' + name);
      if (!file.startsWith(ROOT + path.sep)) { res.writeHead(403).end(); return; }
      const type = { '.css': 'text/css', '.js': 'application/javascript', '.html': 'text/html', '.ttf': 'font/ttf', '.svg': 'image/svg+xml' }[path.extname(file)] || 'application/octet-stream';
      fs.readFile(file, (err, data) => { res.writeHead(err ? 404 : 200, { 'Content-Type': type }); res.end(err ? '' : data); });
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    url = `http://127.0.0.1:${server.address().port}/design/galerie.html`;
  }
  const browser = await chromium.launch({ executablePath: process.env.JIGO_CHROMIUM });
  const snap = {}; fs.mkdirSync(OUT, { recursive: true });
  for (const [w, mode] of [[1280, 'light'], [1280, 'dark'], [390, 'light'], [390, 'dark']]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: 900 }, colorScheme: mode, reducedMotion: 'reduce' });
    const pg = await ctx.newPage();
    await pg.goto(url);
    await pg.evaluate(m => { document.documentElement.dataset.theme = m; }, mode);
    await pg.evaluate(async () => {
      const faces = await document.fonts.load('400 14px "Space Grotesk"');
      if (!faces.length) throw new Error('Police de référence absente');
      await document.fonts.ready;
    });
    snap[`${w}/${mode}`] = await pg.evaluate(([T, P]) => {
      const r = {};
      for (const [k, s] of Object.entries(T)) {
        const e = document.querySelector(s); if (!e) { r[k] = 'ABSENT'; continue; }
        // La forme native d'un radio relève du navigateur/OS, pas du thème.
        const c = getComputedStyle(e);
        // Le max-width en ch du titre/texte introductif dépend des métriques
        // du moteur. Vérifier la borne réelle plutôt qu'un nombre de pixels
        // propre à une version de Chromium. Les autres dimensions restent figées.
        if (k === 'h1' || k === 'p') {
          const rect = e.getBoundingClientRect(), parent = e.parentElement.getBoundingClientRect();
          if (rect.width <= 0 || rect.right > parent.right + 1 || rect.left < parent.left - 1) throw new Error(`${k}: débordement du conteneur`);
        }
        r[k] = P.map(p => k === 'radio' && p === 'borderTopLeftRadius' ? 'native' : (k === 'h1' || k === 'p') && p === 'width' ? 'intrinsic-bounded' : c[p]).join('|');
      }
      return r;
    }, [TARGETS, PROPS]);
    await pg.screenshot({ path: path.join(OUT, `galerie-${w}-${mode}.png`), fullPage: true });
    await ctx.close();
  }
  await browser.close();
  if (server) await new Promise(resolve => server.close(resolve));
  if (process.argv.includes('--update')) { fs.writeFileSync(REF, JSON.stringify(snap, null, 1) + '\n'); console.log('Référence mise à jour :', REF); return; }
  const ref = JSON.parse(fs.readFileSync(REF, 'utf8')), diffs = [];
  for (const ctx of Object.keys(snap)) for (const k of Object.keys(snap[ctx])) if (snap[ctx][k] !== (ref[ctx] || {})[k]) diffs.push(`${ctx} ${k}\n  attendu ${(ref[ctx] || {})[k]}\n  obtenu  ${snap[ctx][k]}`);
  if (diffs.length) { console.error(`ÉCART visuel (${diffs.length}) :\n` + diffs.join('\n') + '\nSi le changement est voulu : make visual-update'); process.exit(1); }
  console.log('Références visuelles : OK (' + Object.keys(snap).length + ' contextes)');
})();
