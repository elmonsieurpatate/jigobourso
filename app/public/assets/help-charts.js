/* Graphiques pédagogiques de l'aide (SVG pur, sans dépendance) : courbes avec fenêtre surlignée et droite de tendance, barres, barres empilées. Tout est fictif et calculé dans le navigateur. */
(function () {
  'use strict';
  const esc = J.esc;
  const PAL = ['#2563eb', '#f97316', '#16a34a', '#9333ea', '#e11d48', '#0891b2', '#ca8a04', '#db2777', '#4f46e5', '#65a30d'];
  const f1 = (v, d = 1) => J.num(+v, d);
  let uid = 0;

  /** Courbes. o: {w,h, series:[{name,values,color,dash,width}], highlight:{from,to,label,color}, line:{a,b,from,to,color,label} (droite y=exp(a+b·t)), residuals:{values,a,b}, marks:[{x,y,label}], xTitle, yTitle, legend:true} */
  function line(o) {
    const w = o.w || 640, h = o.h || 260, L = 46, R = 14, T = 14, B = 34, W = w - L - R, H = h - T - B, id = 'c' + (++uid);
    const all = o.series.flatMap(s => s.values), n = Math.max(...o.series.map(s => s.values.length)) - 1;
    let lo = Math.min(...all), hi = Math.max(...all); const pad = (hi - lo) * 0.08 || 1; lo -= pad; hi += pad;
    const X = t => L + (t / n) * W, Y = v => T + (1 - (v - lo) / (hi - lo)) * H;
    let g = '';
    for (let i = 0; i <= 4; i++) { const v = lo + (hi - lo) * i / 4, y = Y(v); g += `<line x1="${L}" x2="${w - R}" y1="${y}" y2="${y}" class="hc-grid"/><text x="${L - 6}" y="${y + 4}" text-anchor="end" class="hc-tick">${f1(v, v >= 100 ? 0 : 1)}</text>`; }
    for (let i = 0; i <= 4; i++) { const t = Math.round(n * i / 4); g += `<text x="${X(t)}" y="${h - 14}" text-anchor="middle" class="hc-tick">${t}</text>`; }
    if (o.xTitle !== false) g += `<text x="${L + W / 2}" y="${h - 1}" text-anchor="middle" class="hc-axis">${esc(o.xTitle || 'séances (jours de bourse)')}</text>`;
    if (o.yTitle) g += `<text x="12" y="${T + H / 2}" transform="rotate(-90 12 ${T + H / 2})" text-anchor="middle" class="hc-axis">${esc(o.yTitle)}</text>`;
    let hl = '';
    if (o.highlight) { const x0 = X(o.highlight.from), x1 = X(o.highlight.to); hl = `<rect x="${x0}" y="${T}" width="${x1 - x0}" height="${H}" fill="${o.highlight.color || '#f59e0b'}" opacity=".13"/><text x="${(x0 + x1) / 2}" y="${T + 12}" text-anchor="middle" class="hc-tag">${esc(o.highlight.label || '')}</text>`; }
    let res = '';
    if (o.residuals) { const { values, a, b, from = 0 } = o.residuals; values.forEach((v, i) => { const t = from + i, fit = Math.exp(a + b * i); res += `<line x1="${X(t)}" x2="${X(t)}" y1="${Y(v)}" y2="${Y(fit)}" class="hc-res"/>`; }); }
    let reg = '';
    if (o.line) { const { a, b, from, to, color = '#111827' } = o.line; const m = to - from; reg = `<line x1="${X(from)}" y1="${Y(Math.exp(a))}" x2="${X(to)}" y2="${Y(Math.exp(a + b * m))}" stroke="${color}" stroke-width="2" stroke-dasharray="6 4"/>`; if (o.line.label) reg += `<text x="${X(to) - 4}" y="${Y(Math.exp(a + b * m)) - 8}" text-anchor="end" class="hc-tag" fill="${color}">${esc(o.line.label)}</text>`; }
    const paths = o.series.map((s, i) => { const c = s.color || PAL[i % PAL.length]; return `<polyline fill="none" stroke="${c}" stroke-width="${s.width || 2.4}" ${s.dash ? 'stroke-dasharray="' + s.dash + '"' : ''} stroke-linejoin="round" points="${s.values.map((v, t) => X(t * ((n) / (s.values.length - 1))).toFixed(1) + ',' + Y(v).toFixed(1)).join(' ')}"/>`; }).join('');
    let marks = '';
    (o.marks || []).forEach(m => { marks += `<circle cx="${X(m.x)}" cy="${Y(m.y)}" r="4.5" fill="${m.color || '#e11d48'}" stroke="#fff" stroke-width="1.5"/>${m.label ? `<text x="${X(m.x) + 7}" y="${Y(m.y) - 7}" class="hc-tag">${esc(m.label)}</text>` : ''}`; });
    const legend = o.series.length > 1 || o.legend ? `<div class="hc-legend">${o.series.map((s, i) => `<span><i style="background:${s.color || PAL[i % PAL.length]}"></i>${esc(s.name || '')}</span>`).join('')}${o.line ? `<span><i class="dash"></i>${esc(o.line.legend || 'droite de tendance')}</span>` : ''}</div>` : '';
    return `<figure class="hc"><svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(o.alt || 'Graphique')}" class="hc-svg">${g}${hl}${res}${reg}${paths}${marks}</svg>${legend}</figure>`;
  }
  /** Barres horizontales. items: [{label, value, color, note}] */
  function bars(items, o = {}) {
    const max = o.max || Math.max(...items.map(i => i.value), 1), fmt = o.fmt || (v => f1(v, 0));
    return `<div class="hc-bars">${items.map((it, i) => `<div class="hc-bar"><span class="hc-bl">${esc(it.label)}</span><span class="hc-bt"><i style="width:${Math.max(0, Math.min(100, 100 * it.value / max))}%;background:${it.color || PAL[i % PAL.length]}"></i></span><b>${fmt(it.value)}${it.note ? ' <small>' + esc(it.note) + '</small>' : ''}</b></div>`).join('')}</div>`;
  }
  /** Barre empilée (parts d'un total de 100). parts: [{label, value, color}] */
  function stack(parts, o = {}) {
    const tot = parts.reduce((a, p) => a + p.value, 0) || 1;
    return `<div class="hc-stack" role="img" aria-label="${esc(o.alt || 'Répartition')}">${parts.filter(p => p.value > 0).map(p => `<span style="flex:${p.value};background:${p.color}" title="${esc(p.label)} : ${f1(100 * p.value / tot, 0)} %">${p.value / tot >= 0.09 ? f1(100 * p.value / tot, 0) + '' : ''}</span>`).join('')}</div>`;
  }
  /** Mini courbe sans axes. */
  function spark(values, color = '#2563eb', w = 120, h = 36) {
    const lo = Math.min(...values), hi = Math.max(...values), n = values.length - 1;
    return `<svg viewBox="0 0 ${w} ${h}" class="hc-spark" aria-hidden="true"><polyline fill="none" stroke="${color}" stroke-width="2" points="${values.map((v, t) => (t / n * w).toFixed(1) + ',' + (h - 3 - (v - lo) / ((hi - lo) || 1) * (h - 6)).toFixed(1)).join(' ')}"/></svg>`;
  }
  window.HC = { PAL, line, bars, stack, spark, f1, esc };
})();
