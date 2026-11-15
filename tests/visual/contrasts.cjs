// Contrats de contraste sur les vraies couleurs calculées par Chromium (WCAG 2.2).
// Textes usuels : 4,5:1. Séries/lignes graphiques : 3:1 contre leur surface.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');
const galleryServer = require('./gallery-server.cjs');
(async () => {
  const gallery = await galleryServer();
  const browser = await chromium.launch({ executablePath: process.env.JIGO_CHROMIUM });
  try {
    const page = await browser.newPage();
    await page.goto(gallery.url);
    await page.addStyleTag({ content: '* { transition: none !important; animation: none !important; }' });
    const failures = []; let checked = 0;
    for (const theme of ['light', 'dark']) {
      const result = await page.evaluate(theme => {
        document.documentElement.dataset.theme = theme;
        const canvas = document.createElement('canvas'), ctx = canvas.getContext('2d');
        canvas.width = canvas.height = 1;
        const swatch = document.createElement('i'); document.body.append(swatch);
        const rgb = color => {
          swatch.style.color = color;
          ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = getComputedStyle(swatch).color; ctx.fillRect(0, 0, 1, 1);
          return [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3);
        };
        const lum = c => rgb(c).map(v => v / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4).reduce((s, v, i) => s + v * [.2126, .7152, .0722][i], 0);
        const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
        const bad = []; let n = 0;
        const check = (name, ink, bg, min) => { const r = ratio(ink, bg); n++; if (r < min) bad.push(`${name}: ${r.toFixed(2)} < ${min}`); };
        for (const bg of ['bg', 'surface', 'surface-2', 'halo-highlight', 'halo-control']) {
          for (const fg of ['text', 'muted', 'accent', 'ok', 'danger', 'warn', 'info']) check(`${fg}/${bg}`, `var(--${fg})`, `var(--${bg})`, 4.5);
        }
        for (const kind of ['accent', 'ok', 'warn', 'danger', 'info']) check(`${kind}-ink/soft`, `var(--${kind === 'accent' ? kind : kind + '-ink'})`, `var(--${kind}-soft)`, 4.5);
        for (const bg of ['surface', 'surface-2', 'halo-highlight']) {
          for (const fg of ['chart-ma', 'chart-ma2', 'chart-level', ...Array.from({ length: 12 }, (_, i) => `series-${i + 1}`)]) check(`${fg}/${bg}`, `var(--${fg})`, `var(--${bg})`, 3);
        }
        for (const bg of ['#dbeafe', '#dcfce7', '#ffedd5', '#f3e8ff']) check('icône aide/' + bg, 'var(--data-icon-ink)', bg, 3);
        check('repère numéroté', 'var(--accent-ink)', 'var(--accent)', 4.5);
        for (const bg of ['side-bg', 'side-bg-2']) for (const fg of ['side-ink', 'side-muted', 'side-active-ink']) check(`${fg}/${bg}`, `var(--${fg})`, `var(--${bg})`, 4.5);
        const primary = getComputedStyle(document.querySelector('.btn.primary'));
        // Le minimum du dégradé est atteint à une extrémité (interpolation sRGB).
        for (const stop of primary.backgroundImage.match(/(?:rgba?|color)\([^()]+\)/g) || []) check('primary/gradient', primary.color, stop, 4.5);
        swatch.remove(); return { n, bad };
      }, theme);
      checked += result.n; failures.push(...result.bad.map(s => `${theme}: ${s}`));
    }
    if (failures.length) throw new Error(failures.join('\n'));
    console.log(`Contrastes : ${checked} paires conformes (clair/sombre, textes et séries).`);
  } finally { await browser.close(); await gallery.close(); }
})().catch(e => { console.error(e.message); process.exitCode = 1; });
