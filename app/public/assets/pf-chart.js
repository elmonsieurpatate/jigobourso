/* Graphique du Portefeuille (SVG pur) : courbes avec trous (jamais d'interpolation), infobulle à toutes les valeurs, zoom par glissement, déplacement, marqueurs d'achat/vente.
   PFChart.draw(host, {dates, series:[{id,label,color,width,y:[...],dim}], markers:[{date,sid,side,label}], fmt, zero, onZoom(from,to)|null, zoomed, onReset}) */
(function (root) {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const isNum = v => typeof v === 'number' && isFinite(v);
  const fr = d => d ? d.slice(8, 10) + '/' + d.slice(5, 7) + '/' + d.slice(0, 4) : '';

  function draw(host, o) {
    const dates = o.dates || [], n = dates.length;
    host.innerHTML = '';
    if (n < 2 || !o.series.some(s => s.y.some(isNum))) { host.innerHTML = '<div class="pfc-empty">' + esc(o.emptyText || 'Pas assez de données à tracer sur cette période.') + '</div>'; return null; }
    const W = Math.max(280, host.clientWidth || 640), H = W < 520 ? 260 : 340, R = 12, T = 12, B = 26;
    const vis = o.series.filter(s => !s.hidden);
    let lo = Infinity, hi = -Infinity; vis.forEach(s => s.y.forEach(v => { if (isNum(v)) { lo = Math.min(lo, v); hi = Math.max(hi, v); } }));
    if (!isFinite(lo)) { lo = 0; hi = 1; } if (o.zero !== false) { lo = Math.min(lo, 0); hi = Math.max(hi, 0); }
    const pad = (hi - lo) * 0.06 || 1; lo -= pad; hi += pad;
    const L = 14 + 6.2 * Math.max(...[lo, hi, (lo + hi) / 2].map(v => String((o.tick || o.fmt)(v)).length)), pw = W - L - R, ph = H - T - B;
    const X = i => L + (i / (n - 1)) * pw, Y = v => T + (1 - (v - lo) / (hi - lo)) * ph;
    const svg = document.createElementNS(NS, 'svg'); svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.setAttribute('class', 'pfc-svg'); svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', o.alt || 'Évolution du portefeuille');
    let h = '';
    for (let k = 0; k <= 4; k++) { const v = lo + (hi - lo) * k / 4, y = Y(v); h += `<line x1="${L}" x2="${W - R}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}" class="pfc-grid"/><text x="${L - 6}" y="${(y + 4).toFixed(1)}" text-anchor="end" class="pfc-tick">${esc((o.tick || o.fmt)(v))}</text>`; }
    const nt = W < 520 ? 3 : 5; for (let k = 0; k < nt; k++) { const i = Math.round((n - 1) * k / (nt - 1)); h += `<text x="${X(i).toFixed(1)}" y="${H - 8}" text-anchor="${k === 0 ? 'start' : k === nt - 1 ? 'end' : 'middle'}" class="pfc-tick">${fr(dates[i])}</text>`; }
    if (lo < 0 && hi > 0) h += `<line x1="${L}" x2="${W - R}" y1="${Y(0).toFixed(1)}" y2="${Y(0).toFixed(1)}" class="pfc-zero"/>`;
    const order = vis.slice().sort((a, b) => (a.dim ? 0 : 1) - (b.dim ? 0 : 1) || (a.width || 1.8) - (b.width || 1.8));
    for (const s of order) {
      let d = '', pen = false, last = -1, cnt = 0;
      s.y.forEach((v, i) => { if (!isNum(v)) { pen = false; return; } d += (pen ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1); pen = true; last = i; cnt++; });
      if (!cnt) continue;
      h += `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="${s.width || 1.8}" stroke-linejoin="round" stroke-linecap="round" opacity="${s.dim ? 0.35 : 1}"/>`;
      if (cnt === 1) { const i = s.y.findIndex(isNum); h += `<circle cx="${X(i).toFixed(1)}" cy="${Y(s.y[i]).toFixed(1)}" r="3" fill="${s.color}"/>`; }
    }
    const idx = {}; dates.forEach((d, i) => { idx[d] = i; });
    (o.markers || []).forEach(m => {
      const s = vis.find(x => x.id === m.sid); let i = idx[m.date]; if (i === undefined) { i = -1; for (let k = 0; k < n; k++) if (dates[k] <= m.date) i = k; }
      if (!s || i < 0 || !isNum(s.y[i])) return;
      const x = X(i), y = Y(s.y[i]), up = m.side !== 'sell';
      h += `<path d="${up ? `M${x} ${y - 7}l5 9h-10z` : `M${x} ${y + 7}l5 -9h-10z`}" fill="${up ? '#16a34a' : '#dc2626'}" stroke="#fff" stroke-width="1"><title>${esc(m.label || (up ? 'Achat' : 'Vente'))} · ${fr(m.date)}</title></path>`;
    });
    h += `<line class="pfc-cross" x1="0" x2="0" y1="${T}" y2="${T + ph}" style="display:none"/><rect class="pfc-sel" y="${T}" height="${ph}" style="display:none"/><rect class="pfc-hit" x="${L}" y="${T}" width="${pw}" height="${ph}" fill="transparent"/>`;
    svg.innerHTML = h; host.appendChild(svg);
    const tip = document.createElement('div'); tip.className = 'pfc-tip'; tip.hidden = true; host.appendChild(tip);
    const hit = svg.querySelector('.pfc-hit'), cross = svg.querySelector('.pfc-cross'), sel = svg.querySelector('.pfc-sel');
    const idxAt = ev => { const r = svg.getBoundingClientRect(), x = (ev.clientX - r.left) * (W / r.width); return Math.max(0, Math.min(n - 1, Math.round((x - L) / pw * (n - 1)))); };
    const pxAt = i => X(i);
    let drag = null;
    const show = (i, ev) => {
      cross.style.display = ''; cross.setAttribute('x1', pxAt(i)); cross.setAttribute('x2', pxAt(i));
      const rows = vis.map(s => ({ s, v: s.y[i] })).sort((a, b) => (isNum(b.v) ? b.v : -Infinity) - (isNum(a.v) ? a.v : -Infinity));
      tip.innerHTML = `<b>${fr(dates[i])}</b>` + rows.map(({ s, v }) => `<div><i style="background:${s.color}"></i><span>${esc(s.label)}</span><b>${isNum(v) ? esc(o.fmt(v)) : '<em>n/d</em>'}</b></div>`).join('');
      tip.hidden = false; const r = host.getBoundingClientRect(), x = ev.clientX - r.left, flip = x > r.width * 0.55;
      tip.style.left = flip ? 'auto' : Math.min(r.width - 170, x + 14) + 'px'; tip.style.right = flip ? Math.max(0, r.width - x + 14) + 'px' : 'auto'; tip.style.top = '8px';
    };
    hit.addEventListener('pointermove', ev => { const i = idxAt(ev); if (drag) { drag.to = i; const a = Math.min(drag.from, i), b = Math.max(drag.from, i); sel.style.display = ''; sel.setAttribute('x', pxAt(a)); sel.setAttribute('width', Math.max(1, pxAt(b) - pxAt(a))); } show(i, ev); });
    hit.addEventListener('pointerleave', () => { if (!drag) { cross.style.display = 'none'; tip.hidden = true; } });
    if (o.onZoom) {
      hit.addEventListener('pointerdown', ev => { drag = { from: idxAt(ev), to: idxAt(ev), sx: ev.clientX }; hit.setPointerCapture(ev.pointerId); });
      const end = ev => { if (!drag) return; const d = drag; drag = null; sel.style.display = 'none'; tip.hidden = true; cross.style.display = 'none'; const a = Math.min(d.from, d.to), b = Math.max(d.from, d.to); if (Math.abs(ev.clientX - d.sx) > 8 && b - a >= 2) o.onZoom(dates[a], dates[b]); };
      hit.addEventListener('pointerup', end); hit.addEventListener('pointercancel', () => { drag = null; sel.style.display = 'none'; });
    }
    return { svg };
  }
  root.PFChart = { draw, fr };
})(typeof window !== 'undefined' ? window : globalThis);
