/* Graphique de cours quotidien : étendue, moyennes mobiles, volumes, infobulle. Dépend de app.js (J). */
'use strict';
(() => {
  const NS = 'http://www.w3.org/2000/svg';
  const el = (n, a = {}, t) => { const e = document.createElementNS(NS, n); for (const [k, v] of Object.entries(a)) e.setAttribute(k, v); if (t !== undefined) e.textContent = t; return e; };
  const dec = p => (p < 1 ? 4 : p < 10 ? 3 : 2);
  const sma = (vals, n) => vals.map((_, i) => (i + 1 < n ? null : vals.slice(i + 1 - n, i + 1).reduce((a, b) => a + b, 0) / n));
  const ticks = (lo, hi, n = 5) => { const span = hi - lo || 1, raw = span / n, mag = Math.pow(10, Math.floor(Math.log10(raw))), step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw) || mag * 10, out = []; for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(8)); return out; };

  /* rows : [[date ISO, clôture, volume|null]] (toute la série) ; opts : { sessions: nombre de séances affichées (0 = tout), ma20, ma50, volume, unit } */
  J.priceChart = function (host, rows, opts = {}) {
    host.innerHTML = '';
    if (!rows || rows.length < 2) { host.innerHTML = '<div class="empty">Pas assez de données pour tracer la courbe.</div>'; return; }
    const closes = rows.map(r => r[1]), m20 = sma(closes, 20), m50 = sma(closes, 50);
    const from = opts.sessions ? Math.max(0, rows.length - opts.sessions) : 0, view = rows.slice(from), n = view.length;
    const W = 1000, H = 400, L = 8, R = 66, T = 14, PH = opts.volume ? 270 : 330, VT = T + PH + 10, VH = 56, B = H - 24;
    const vals = closes.slice(from), extra = [...(opts.ma20 ? m20.slice(from) : []), ...(opts.ma50 ? m50.slice(from) : [])].filter(v => v !== null);
    const all = vals.concat(extra), hi = Math.max(...all), lo = Math.min(...all), pad = (hi - lo || hi * .01) * .07, y0 = lo - pad, y1 = hi + pad;
    const X = i => L + i * (W - L - R) / (n - 1), Y = v => T + PH * (1 - (v - y0) / (y1 - y0)), dp = dec(hi), f = v => J.num(v, dp);
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, class: 'price-svg', role: 'img', 'aria-label': 'Cours de clôture quotidiens' });
    ticks(y0, y1).forEach(v => { svg.append(el('line', { x1: L, x2: W - R, y1: Y(v), y2: Y(v), class: 'hgrid' }), el('text', { x: W - R + 8, y: Y(v) + 4, class: 'axis' }, f(v))); });
    for (let k = 0; k <= 5; k++) { const i = Math.round(k * (n - 1) / 5); svg.append(el('text', { x: X(i), y: H - 6, class: 'axis', 'text-anchor': k === 0 ? 'start' : k === 5 ? 'end' : 'middle' }, J.date(view[i][0]))); }
    const up = vals[n - 1] >= vals[0], line = vals.map((v, i) => (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1)).join('');
    svg.append(el('path', { d: `${line}L${X(n - 1)} ${T + PH}L${L} ${T + PH}Z`, class: 'area ' + (up ? 'up' : 'down') }));
    const path = (arr, cls) => { let d = '', pen = false; arr.slice(from).forEach((v, i) => { if (v === null) { pen = false; return; } d += (pen ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1); pen = true; }); if (d) svg.append(el('path', { d, class: cls })); };
    if (opts.ma50) path(m50, 'ma50'); if (opts.ma20) path(m20, 'ma20');
    svg.append(el('path', { d: line, class: 'pline ' + (up ? 'up' : 'down') }));
    if (opts.volume) {
      const vols = view.map(r => r[2]), vmax = Math.max(1, ...vols.filter(v => v !== null)), bw = Math.max(1, (W - L - R) / n * .7);
      vols.forEach((v, i) => { if (v !== null) svg.append(el('rect', { x: X(i) - bw / 2, y: VT + VH * (1 - v / vmax), width: bw, height: Math.max(.5, VH * v / vmax), class: 'vol ' + (i && vals[i] < vals[i - 1] ? 'down' : 'up') })); });
      svg.append(el('text', { x: W - R + 8, y: VT + 10, class: 'axis' }, 'Volume'));
    }
    const iMax = vals.indexOf(Math.max(...vals)), iMin = vals.indexOf(Math.min(...vals));
    [[iMax, 'haut'], [iMin, 'bas']].forEach(([i, t]) => { svg.append(el('circle', { cx: X(i), cy: Y(vals[i]), r: 3.5, class: 'extreme' }), el('text', { x: Math.min(Math.max(X(i), 60), W - R - 40), y: Y(vals[i]) + (t === 'haut' ? -8 : 15), class: 'axis', 'text-anchor': 'middle' }, f(vals[i]))); });
    svg.append(el('line', { x1: L, x2: W - R, y1: Y(vals[n - 1]), y2: Y(vals[n - 1]), class: 'lastline' }), el('rect', { x: W - R + 2, y: Y(vals[n - 1]) - 9, width: R - 4, height: 18, rx: 4, class: 'lasttag' }), el('text', { x: W - R + 6, y: Y(vals[n - 1]) + 4, class: 'lasttext' }, f(vals[n - 1])));
    const cross = el('line', { y1: T, y2: opts.volume ? VT + VH : T + PH, class: 'cross', visibility: 'hidden' }), dot = el('circle', { r: 4.5, class: 'hdot', visibility: 'hidden' }); svg.append(cross, dot);
    const tip = document.createElement('div'); tip.className = 'chart-tip'; tip.hidden = true;
    const wrap = document.createElement('div'); wrap.className = 'chart-wrap'; wrap.append(svg, tip); host.append(wrap);
    const move = ev => {
      const r = svg.getBoundingClientRect(), px = ((ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left) * W / r.width, i = Math.max(0, Math.min(n - 1, Math.round((px - L) / ((W - L - R) / (n - 1)))));
      cross.setAttribute('x1', X(i)); cross.setAttribute('x2', X(i)); cross.setAttribute('visibility', 'visible'); dot.setAttribute('cx', X(i)); dot.setAttribute('cy', Y(vals[i])); dot.setAttribute('visibility', 'visible');
      const prev = i ? vals[i - 1] : null, sinceStart = 100 * (vals[i] / vals[0] - 1), g = from + i;
      tip.innerHTML = `<b>${J.date(view[i][0])}</b><div class="tip-grid"><span>Clôture</span><b>${f(vals[i])} ${J.esc(opts.unit || '')}</b>${prev ? `<span>Vs veille</span><b class="${J.cls(vals[i] - prev)}">${J.pct(100 * (vals[i] / prev - 1))}</b>` : ''}<span>Depuis le début de la période</span><b class="${J.cls(sinceStart)}">${J.pct(sinceStart)}</b>${m20[g] !== null ? `<span>Moy. 20 j</span><b>${f(m20[g])}</b>` : ''}${m50[g] !== null ? `<span>Moy. 50 j</span><b>${f(m50[g])}</b>` : ''}<span>Volume</span><b>${view[i][2] === null ? 'absent' : J.num(view[i][2], 0)}</b></div>`;
      tip.hidden = false; const wr = wrap.getBoundingClientRect(), left = X(i) * r.width / W + (r.left - wr.left);
      tip.style.left = Math.min(Math.max(8, left + 14), wr.width - tip.offsetWidth - 8) + 'px'; tip.style.top = '8px';
    };
    const leave = () => { cross.setAttribute('visibility', 'hidden'); dot.setAttribute('visibility', 'hidden'); tip.hidden = true; };
    svg.addEventListener('mousemove', move); svg.addEventListener('mouseleave', leave); svg.addEventListener('touchmove', move, { passive: true }); svg.addEventListener('touchend', leave);
    return { perf: 100 * (vals[n - 1] / vals[0] - 1), high: Math.max(...vals), low: Math.min(...vals), from: view[0][0], to: view[n - 1][0], sessions: n };
  };
})();
