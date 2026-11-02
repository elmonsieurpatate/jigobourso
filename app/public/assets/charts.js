/* Graphique de cours quotidien : étendue, moyennes mobiles, volumes, infobulle. Dépend de app.js (J). */
'use strict';
(() => {
  const NS = 'http://www.w3.org/2000/svg';
  const el = (n, a = {}, t) => { const e = document.createElementNS(NS, n); for (const [k, v] of Object.entries(a)) e.setAttribute(k, v); if (t !== undefined) e.textContent = t; return e; };
  const dec = p => (p < 1 ? 4 : p < 10 ? 3 : 2);
  const sma = (vals, n) => vals.map((_, i) => (i + 1 < n ? null : vals.slice(i + 1 - n, i + 1).reduce((a, b) => a + b, 0) / n));
  const ticks = (lo, hi, n = 5) => { const span = hi - lo || 1, raw = span / n, mag = Math.pow(10, Math.floor(Math.log10(raw))), step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw) || mag * 10, out = []; for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(8)); return out; };

  /* Plusieurs courbes sur les mêmes dates (évolution du portefeuille, titre par titre).
     series : [{ label, values: [nombre|null], color, dash, area, zero }] ; opts : { unit, format(v) , zeroLine, marks: [{date, label}] }. */
  J.lineChart = function (host, dates, series, opts = {}) {
    host.innerHTML = '';
    const n = dates.length, shown = series.filter(s => s.values.some(v => v !== null && v !== undefined));
    if (n < 2 || !shown.length) { host.innerHTML = '<div class="empty">Pas assez de données pour tracer la courbe.</div>'; return; }
    const W = 1000, H = 340, L = 8, R = 78, T = 14, PH = 296, all = [];
    shown.forEach(s => s.values.forEach(v => { if (v !== null && v !== undefined && isFinite(v)) all.push(v); }));
    if (opts.zeroLine) all.push(0);
    const hi = Math.max(...all), lo = Math.min(...all), pad = (hi - lo || Math.abs(hi) || 1) * .07, y0 = lo - pad, y1 = hi + pad;
    const X = i => L + i * (W - L - R) / (n - 1), Y = v => T + PH * (1 - (v - y0) / (y1 - y0)), fmt = opts.format || (v => J.num(v, 0));
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, class: 'price-svg multi-svg', role: 'img', 'aria-label': opts.label || 'Évolution' });
    ticks(y0, y1).forEach(v => { svg.append(el('line', { x1: L, x2: W - R, y1: Y(v), y2: Y(v), class: 'hgrid' }), el('text', { x: W - R + 8, y: Y(v) + 4, class: 'axis' }, fmt(v))); });
    for (let k = 0; k <= 5; k++) { const i = Math.round(k * (n - 1) / 5); svg.append(el('text', { x: X(i), y: H - 6, class: 'axis', 'text-anchor': k === 0 ? 'start' : k === 5 ? 'end' : 'middle' }, J.date(dates[i]))); }
    if (opts.zeroLine && y0 < 0 && y1 > 0) svg.append(el('line', { x1: L, x2: W - R, y1: Y(0), y2: Y(0), class: 'zeroline' }));
    (opts.marks || []).forEach(m => { const i = dates.findIndex(d => d >= m.date); if (i >= 0) svg.append(el('line', { x1: X(i), x2: X(i), y1: T, y2: T + PH, class: 'markline ' + (m.cls || ''), title: m.label })); });
    shown.forEach(s => {
      let d = '', pen = false;
      s.values.forEach((v, i) => { if (v === null || v === undefined) { pen = false; return; } d += (pen ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1); pen = true; });
      if (s.area) svg.append(el('path', { d: `${d}L${X(n - 1)} ${Y(Math.max(y0, Math.min(0, y1)))}L${L} ${Y(Math.max(y0, Math.min(0, y1)))}Z`, fill: s.color, opacity: .1 }));
      svg.append(el('path', { d, fill: 'none', stroke: s.color, 'stroke-width': s.width || 2, 'stroke-dasharray': s.dash || '', 'stroke-linejoin': 'round' }));
    });
    const cross = el('line', { y1: T, y2: T + PH, class: 'cross', visibility: 'hidden' }); svg.append(cross);
    const tip = document.createElement('div'); tip.className = 'chart-tip'; tip.hidden = true;
    const wrap = document.createElement('div'); wrap.className = 'chart-wrap'; wrap.append(svg, tip);
    const legend = document.createElement('div'); legend.className = 'chart-legend';
    legend.innerHTML = shown.map(s => `<span><i style="background:${s.color}${s.dash ? ';opacity:.6' : ''}"></i>${J.esc(s.label)}</span>`).join('');
    host.append(wrap, legend);
    const move = ev => {
      const r = svg.getBoundingClientRect(), px = ((ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left) * W / r.width, i = Math.max(0, Math.min(n - 1, Math.round((px - L) / ((W - L - R) / (n - 1)))));
      cross.setAttribute('x1', X(i)); cross.setAttribute('x2', X(i)); cross.setAttribute('visibility', 'visible');
      const rows = shown.map(s => [s, s.values[i]]).filter(([, v]) => v !== null && v !== undefined).sort((a, b) => b[1] - a[1]).slice(0, 12);
      tip.innerHTML = `<b>${J.date(dates[i])}</b><div class="tip-grid">${rows.map(([s, v]) => `<span><i class="dot" style="background:${s.color}"></i>${J.esc(s.label)}</span><b>${fmt(v)}</b>`).join('')}</div>`;
      tip.hidden = false; const wr = wrap.getBoundingClientRect(), left = X(i) * r.width / W + (r.left - wr.left);
      tip.style.left = Math.min(Math.max(8, left + 14), wr.width - tip.offsetWidth - 8) + 'px'; tip.style.top = '8px';
    };
    const leave = () => { cross.setAttribute('visibility', 'hidden'); tip.hidden = true; };
    svg.addEventListener('mousemove', move); svg.addEventListener('mouseleave', leave); svg.addEventListener('touchmove', move, { passive: true }); svg.addEventListener('touchend', leave);
  };

  /* rows : [[date ISO, clôture, volume|null]] (toute la série) ; opts : { sessions: nombre de séances affichées (0 = tout), ma20, ma50, volume, unit } */
  J.priceChart = function (host, rows, opts = {}) {
    host.innerHTML = '';
    if (!rows || rows.length < 2) { host.innerHTML = '<div class="empty">Pas assez de données pour tracer la courbe.</div>'; return; }
    const closes = rows.map(r => r[1]), m20 = sma(closes, 20), m50 = sma(closes, 50);
    const from = opts.sessions ? Math.max(0, rows.length - opts.sessions) : 0, view = rows.slice(from), n = view.length;
    const W = 1000, H = 400, L = 8, R = 66, T = 14, PH = opts.volume ? 270 : 330, VT = T + PH + 10, VH = 56, B = H - 24;
    const vals = closes.slice(from), extra = [...(opts.ma20 ? m20.slice(from) : []), ...(opts.ma50 ? m50.slice(from) : []), ...(opts.levels || []).map(l => l.value)].filter(v => v !== null && v !== undefined && isFinite(v));
    const all = vals.concat(extra), hi = Math.max(...all), lo = Math.min(...all), pad = (hi - lo || hi * .01) * .07, y0 = lo - pad, y1 = hi + pad;
    const X = i => L + i * (W - L - R) / (n - 1), Y = v => T + PH * (1 - (v - y0) / (y1 - y0)), dp = dec(hi), f = v => J.num(v, dp);
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, class: 'price-svg', role: 'img', 'aria-label': 'Cours de clôture quotidiens' });
    ticks(y0, y1).forEach(v => { svg.append(el('line', { x1: L, x2: W - R, y1: Y(v), y2: Y(v), class: 'hgrid' }), el('text', { x: W - R + 8, y: Y(v) + 4, class: 'axis' }, f(v))); });
    for (let k = 0; k <= 5; k++) { const i = Math.round(k * (n - 1) / 5); svg.append(el('text', { x: X(i), y: H - 6, class: 'axis', 'text-anchor': k === 0 ? 'start' : k === 5 ? 'end' : 'middle' }, (opts.intraday ? J.dateTime : J.date)(view[i][0]))); }
    const up = vals[n - 1] >= vals[0], line = vals.map((v, i) => (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1)).join('');
    svg.append(el('path', { d: `${line}L${X(n - 1)} ${T + PH}L${L} ${T + PH}Z`, class: 'area ' + (up ? 'up' : 'down') }));
    const path = (arr, cls) => { let d = '', pen = false; arr.slice(from).forEach((v, i) => { if (v === null) { pen = false; return; } d += (pen ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1); pen = true; }); if (d) svg.append(el('path', { d, class: cls })); };
    if (opts.ma50) path(m50, 'ma50'); if (opts.ma20) path(m20, 'ma20');
    svg.append(el('path', { d: line, class: 'pline ' + (up ? 'up' : 'down') }));
    // Repères facultatifs : lignes verticales datées (achats) et lignes horizontales de niveau (filet de sécurité, plus haut depuis l'achat…).
    (opts.levels || []).forEach(l => { if (l.value === null || l.value === undefined || !isFinite(l.value)) return; svg.append(el('line', { x1: L, x2: W - R, y1: Y(l.value), y2: Y(l.value), class: 'levelline ' + (l.cls || '') }), el('text', { x: W - R - 6, y: Y(l.value) - 5, 'text-anchor': 'end', class: 'axis levellabel ' + (l.cls || '') }, l.label + ' ' + f(l.value))); });
    (opts.marks || []).forEach(m => { const i = view.findIndex(r => r[0] >= m.date); if (i < 0) return; svg.append(el('line', { x1: X(i), x2: X(i), y1: T, y2: T + PH, class: 'markline' }), el('text', { x: Math.min(X(i) + 4, W - R - 60), y: T + 12, class: 'axis marklabel' }, m.label)); });
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
      tip.innerHTML = `<b>${(opts.intraday ? J.dateTime : J.date)(view[i][0])}</b><div class="tip-grid"><span>Clôture</span><b>${f(vals[i])} ${J.esc(opts.unit || '')}</b>${prev ? `<span>Vs veille</span><b class="${J.cls(vals[i] - prev)}">${J.pct(100 * (vals[i] / prev - 1))}</b>` : ''}<span>Depuis le début de la période</span><b class="${J.cls(sinceStart)}">${J.pct(sinceStart)}</b>${m20[g] !== null ? `<span>Moy. 20 j</span><b>${f(m20[g])}</b>` : ''}${m50[g] !== null ? `<span>Moy. 50 j</span><b>${f(m50[g])}</b>` : ''}<span>Volume</span><b>${view[i][2] === null ? 'absent' : J.num(view[i][2], 0)}</b></div>`;
      tip.hidden = false; const wr = wrap.getBoundingClientRect(), left = X(i) * r.width / W + (r.left - wr.left);
      tip.style.left = Math.min(Math.max(8, left + 14), wr.width - tip.offsetWidth - 8) + 'px'; tip.style.top = '8px';
    };
    const leave = () => { cross.setAttribute('visibility', 'hidden'); dot.setAttribute('visibility', 'hidden'); tip.hidden = true; };
    svg.addEventListener('mousemove', move); svg.addEventListener('mouseleave', leave); svg.addEventListener('touchmove', move, { passive: true }); svg.addEventListener('touchend', leave);
    return { perf: 100 * (vals[n - 1] / vals[0] - 1), high: Math.max(...vals), low: Math.min(...vals), from: view[0][0], to: view[n - 1][0], sessions: n };
  };
})();
