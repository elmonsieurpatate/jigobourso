/* Graphique de cours quotidien : étendue, moyennes mobiles, volumes, infobulle. Dépend de app.js (J). */
'use strict';
(() => {
  const NS = 'http://www.w3.org/2000/svg';
  const el = (n, a = {}, t) => { const e = document.createElementNS(NS, n); for (const [k, v] of Object.entries(a)) e.setAttribute(k, v); if (t !== undefined) e.textContent = t; return e; };
  const dec = p => (p < 1 ? 4 : p < 10 ? 3 : 2);
  const sma = (vals, n) => vals.map((_, i) => (i + 1 < n ? null : vals.slice(i + 1 - n, i + 1).reduce((a, b) => a + b, 0) / n));
  const ticks = (lo, hi, n = 5) => { const span = hi - lo || 1, raw = span / n, mag = Math.pow(10, Math.floor(Math.log10(raw))), step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw) || mag * 10, out = []; for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(8)); return out; };

  /* Courbes modernes et compactes (évolution du portefeuille).
     xs : dates ISO (ou date-heure si opts.time) ; series : [{ id, label, values, color, area, dash, width }]
     opts : { height, format(v), zeroLine, time, markers: [{ x, kind: 'buy'|'sell', label }], hidden: Set d'id, onToggle(id) } */
  J.lineChart = function (host, xs, series, opts = {}) {
    host.innerHTML = '';
    const hidden = opts.hidden || new Set(), n = xs.length, vis = series.filter(s => !hidden.has(s.id) && s.values.some(v => v !== null && v !== undefined));
    const W = Math.max(300, Math.round(host.clientWidth || 1000)), H = opts.height || 240, L = 4, R = opts.endLabels ? 120 : 64, T = opts.verticalMarkers ? 44 : 10, B = 26, PH = H - T - B, fmt = opts.format || (v => J.num(v, 0)), dl = opts.time ? J.dateTime : J.date;
    const wrap = document.createElement('div'); wrap.className = 'lc';
    if (n < 2 || !vis.length) { wrap.innerHTML = `<div class="lc-empty">${n < 2 ? 'Pas encore assez de données sur cette période.' : series.some(s => s.values.some(v => v !== null && v !== undefined)) ? 'Toutes les courbes sont masquées.' : 'Valorisation indisponible sur cette période.'}</div>`; host.append(wrap); }
    else {
      const all = []; vis.forEach(s => s.values.forEach(v => { if (v !== null && v !== undefined && isFinite(v)) all.push(v); })); if (opts.zeroLine) all.push(0);
      let hi = Math.max(...all), lo = Math.min(...all); if (hi === lo) { hi += Math.abs(hi) * .01 || 1; lo -= Math.abs(lo) * .01 || 1; }
      const pad = (hi - lo) * .08, y0 = lo - pad, y1 = hi + pad, X = i => L + i * (W - L - R) / (n - 1), Y = v => T + PH * (1 - (v - y0) / (y1 - y0));
      const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, class: 'lc-svg', width: W, height: H, role: opts.verticalMarkers ? 'group' : 'img', 'aria-label': opts.label || 'Évolution' });
      const defs = el('defs'); svg.append(defs);
      ticks(y0, y1, 3).forEach(v => { svg.append(el('line', { x1: L, x2: W - R, y1: Y(v), y2: Y(v), class: 'lc-grid' })); });
      if (opts.zeroLine && y0 < 0 && y1 > 0) svg.append(el('line', { x1: L, x2: W - R, y1: Y(0), y2: Y(0), class: 'lc-zero' }));
      [...vis].sort((a,b)=>(a.id===opts.selected)-(b.id===opts.selected)).forEach((s, k) => {
        let d = '', pen = false; s.values.forEach((v, i) => { if (v === null || v === undefined) { pen = false; return; } d += (pen ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1); pen = true; });
        if (s.area) { const g = el('linearGradient', { id: 'lcg' + k + '-' + (host.id || ''), x1: 0, x2: 0, y1: 0, y2: 1 }); g.append(el('stop', { offset: '0%', 'stop-color': s.color, 'stop-opacity': .28 }), el('stop', { offset: '100%', 'stop-color': s.color, 'stop-opacity': 0 })); defs.append(g);
          const base = Y(opts.zeroLine ? Math.max(y0, Math.min(0, y1)) : y0); svg.append(el('path', { d: `${d}L${X(n - 1)} ${base}L${L} ${base}Z`, fill: `url(#lcg${k}-${host.id || ''})` })); }
        svg.append(el('path', { d, fill: 'none', stroke: s.color, 'stroke-width': s.width || 2.2, 'stroke-dasharray': s.dash || '', 'stroke-linejoin': 'round', 'stroke-linecap': 'round', 'vector-effect': 'non-scaling-stroke', opacity: s.opacity ?? 1, 'data-series': s.id }));
      });
      if(opts.endLabels){
        const labels=vis.map(s=>{let i=s.values.length-1;while(i>=0&&(s.values[i]===null||s.values[i]===undefined))i--;return i>=0?{s,i,y:Y(s.values[i]),target:Y(s.values[i])}:null}).filter(Boolean).sort((a,b)=>a.y-b.y);
        const gap=Math.min(14,(PH-12)/Math.max(1,labels.length-1));
        labels.forEach((l,k)=>l.y=Math.max(T+6,l.y,k?labels[k-1].y+gap:T+6));
        if(labels.length){labels[labels.length-1].y=Math.min(T+PH-4,labels[labels.length-1].y);for(let k=labels.length-2;k>=0;k--)labels[k].y=Math.min(labels[k].y,labels[k+1].y-gap);}
        labels.forEach(l=>{svg.append(el('line',{x1:X(l.i),y1:l.target,x2:W-R+5,y2:l.y,stroke:l.s.color,'stroke-width':.6,opacity:.65}),el('text',{x:W-R+8,y:l.y+3,fill:l.s.color,class:'lc-end-label','font-weight':l.s.id===opts.selected?800:600},l.s.label));});
      }
      const groups = new Map();
      (opts.markers || []).filter(m => m.x >= (opts.time?String(xs[0]):String(xs[0]).slice(0,10)) && m.x <= (opts.time?String(xs[n-1]):String(xs[n-1]).slice(0,10))).forEach(m => {
        if (!groups.has(m.x)) groups.set(m.x, []); groups.get(m.x).push(m);
      });
      const markerTargets = [];
      groups.forEach((items, date) => {
        const i = xs.findIndex(x => x >= date), before = Math.max(0, i-1);
        const a = Date.parse(xs[before]), b = Date.parse(xs[i]), at = Date.parse(date);
        const x = i <= 0 || !Number.isFinite(a+b+at) || a === b ? X(Math.max(i,0)) : X(before)+(X(i)-X(before))*(at-a)/(b-a);
        if (!opts.verticalMarkers) { svg.append(el('circle',{cx:x,cy:T+PH+6,r:4,class:'lc-mk '+items[0].kind})); return; }
        const label = items.every(m=>m.symbol) ? 'Achat '+[...new Set(items.map(m=>m.symbol))].join(', ') : [...new Set(items.map(m=>m.label))].join(' · '), g = el('g', {class:'lc-purchase-marker',tabindex:0,role:'button','aria-label':date+' · '+label,'data-date':date});
        g.append(el('line',{x1:x,x2:x,y1:T-4,y2:T+PH,class:'lc-purchase-line'}),el('circle',{cx:x,cy:T+PH,r:4,fill:'var(--accent)'}));
        // One label per date, alternate lanes; complete tickers/details remain keyboard/touch accessible.
        const text = label.length>25 ? label.slice(0,22)+'…' : label, w = Math.min(W-L-R, Math.max(64,text.length*6+12)), lx=Math.max(L,Math.min(x-w/2,W-R-w)), y=markerTargets.length%2?22:2;
        g.append(el('rect',{x:lx,y,width:w,height:18,rx:6,class:'lc-purchase-tag'}),el('text',{x:lx+w/2,y:y+13,'text-anchor':'middle',class:'lc-purchase-text'},text),el('rect',{x:x-12,y:T-4,width:24,height:PH+12,fill:'transparent'}));
        svg.append(g); markerTargets.push({g,x,date,items});
      });
      const cross = el('line', { y1: T, y2: T + PH, class: 'lc-cross', visibility: 'hidden' }), dots = vis.map(s => el('circle', { r: 4.5, fill: s.color, class: 'lc-dot', visibility: 'hidden' }));
      svg.append(cross, ...dots);
      const axis = document.createElement('div'); axis.className = 'lc-y';
      axis.innerHTML = ticks(y0, y1, 3).map(v => `<span style="top:${(100 * Y(v) / H).toFixed(2)}%">${fmt(v)}</span>`).join('');
      const xa = document.createElement('div'); xa.className = 'lc-x';
      xa.innerHTML = (W < 520 ? [0, 1] : [0, .33, .66, 1]).map(f => Math.round(f * (n - 1))).map((i, k, a) => `<span style="left:${(100 * X(i) / W).toFixed(2)}%" class="${k === 0 ? 'first' : k === a.length - 1 ? 'last' : ''}">${dl(xs[i])}</span>`).join('');
      const tip = document.createElement('div'); tip.className = 'lc-tip'; tip.hidden = true;
      const box = document.createElement('div'); box.className = 'lc-box'; box.style.height = H + 'px'; box.append(svg, axis, xa, tip); wrap.append(box);
      let pinned=false;
      const move = ev => {
        if(pinned)return;
        const r = svg.getBoundingClientRect(), px = ((ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left) * W / r.width, i = Math.max(0, Math.min(n - 1, Math.round((px - L) / ((W - L - R) / (n - 1)))));
        cross.setAttribute('x1', X(i)); cross.setAttribute('x2', X(i)); cross.setAttribute('visibility', 'visible');
        vis.forEach((s, k) => { const v = s.values[i]; if (v === null || v === undefined) { dots[k].setAttribute('visibility', 'hidden'); return; } dots[k].setAttribute('cx', X(i)); dots[k].setAttribute('cy', Y(v)); dots[k].setAttribute('visibility', 'visible'); });
        const rows = vis.map(s => [s, s.values[i]]).filter(([, v]) => v !== null && v !== undefined).sort((a, b) => b[1] - a[1]).slice(0, 10);
        const mk = (opts.markers || []).filter(m => m.x.slice(0, 10) === String(xs[i]).slice(0, 10));
        tip.innerHTML = `<div class="lc-tip-d">${dl(xs[i])}</div>${rows.map(([s, v]) => `<div class="lc-tip-r"><i style="background:${s.color}"></i><span>${J.esc(s.label)}</span><b>${s.format ? s.format(v) : fmt(v)}</b></div>`).join('')}${mk.map(m => `<div class="lc-tip-m ${m.kind}">${J.esc(m.label)}${m.detail ? ' · '+J.esc(m.detail) : ''}</div>`).join('')}`;
        tip.hidden = false; const bx = box.getBoundingClientRect(), left = X(i) * r.width / W;
        tip.style.left = Math.max(0,Math.min(bx.width-tip.offsetWidth,left > bx.width / 2 ? left-tip.offsetWidth-14 : left+14))+'px';
      };
      const leave = () => { if(pinned)return; cross.setAttribute('visibility', 'hidden'); dots.forEach(d => d.setAttribute('visibility', 'hidden')); tip.hidden = true; };
      markerTargets.forEach(({g,x,date,items}) => {
        const show = ev => { ev.stopPropagation(); if(['touchstart','click'].includes(ev.type))pinned=true; tip.innerHTML='<div class="lc-tip-d">'+J.date(date)+'</div>'+items.map(m=>'<div class="lc-tip-m">'+J.esc(m.label)+'</div><div>'+J.esc(m.detail || '')+'</div>').join(''); tip.hidden=false; const width=box.getBoundingClientRect().width; tip.style.left=Math.max(0,Math.min(width-tip.offsetWidth,x*width/W))+'px'; };
        g.addEventListener('mouseenter',show);g.addEventListener('focus',show);g.addEventListener('click',show);g.addEventListener('touchstart',show,{passive:true});g.addEventListener('touchend',ev=>ev.stopPropagation());
        g.addEventListener('keydown',ev=>{if(['Enter',' '].includes(ev.key)){ev.preventDefault();show(ev)}if(ev.key==='Escape'){pinned=false;leave()}});g.addEventListener('blur',leave);
      });
      box.addEventListener('pointerdown',ev=>{if(!ev.target.closest('.lc-purchase-marker,.lc-tip')){pinned=false;leave()}});
      box.addEventListener('keydown',ev=>{if(ev.key==='Escape'){pinned=false;leave()}});
      svg.addEventListener('touchstart',move,{passive:true});
      svg.addEventListener('mousemove', move); svg.addEventListener('mouseleave', leave); svg.addEventListener('touchmove', move, { passive: true }); svg.addEventListener('touchend', leave);
      host.append(wrap);
    }
    if (series.length > 1 && opts.onToggle) {
      const lg = document.createElement('div'); lg.className = 'lc-legend';
      lg.innerHTML = series.map(s => `<button type="button" class="lc-chip ${hidden.has(s.id) ? 'off' : ''} ${opts.focusLegend && opts.selected===s.id?'selected':''}" data-id="${J.esc(s.id)}" aria-pressed="${opts.focusLegend ? !opts.selected || opts.selected===s.id : !hidden.has(s.id)}"><i style="background:${s.color}"></i>${J.esc(s.label)}</button>`).join('');
      lg.querySelectorAll('button').forEach(b => b.onclick = () => opts.onToggle(b.dataset.id));
      host.append(lg);
    }
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
