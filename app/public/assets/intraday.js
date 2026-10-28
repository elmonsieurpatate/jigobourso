/* Vue intrajournalière : les deux dernières séances d'un titre, une barre toutes les 15 minutes, dans le fuseau de la place.
   Aucune interpolation : un créneau sans donnée est dessiné comme un trou. Dépend de app.js (J). */
'use strict';
(() => {
  const NS = 'http://www.w3.org/2000/svg';
  const SLOT = 15 * 60000;
  const dec = p => (p < 1 ? 4 : p < 10 ? 3 : 2);
  const t = iso => new Date(iso).getTime();

  const fmt = tz => ({
    time: ms => new Intl.DateTimeFormat('fr-FR', { timeZone: tz, hour: '2-digit', minute: '2-digit', hour12: false }).format(ms),
    day: ms => new Intl.DateTimeFormat('fr-FR', { timeZone: tz, weekday: 'short', day: 'numeric', month: 'short' }).format(ms),
    dayLong: ms => new Intl.DateTimeFormat('fr-FR', { timeZone: tz, weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).format(ms),
    minute: ms => +new Intl.DateTimeFormat('en-GB', { timeZone: tz, minute: 'numeric' }).format(ms),
    zone: ms => (new Intl.DateTimeFormat('fr-FR', { timeZone: tz, timeZoneName: 'short' }).formatToParts(ms).find(p => p.type === 'timeZoneName') || {}).value || tz,
  });

  function el(name, attrs = {}, text) {
    const e = document.createElementNS(NS, name);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  const niceTicks = (lo, hi, n = 5) => {
    const span = hi - lo || 1, raw = span / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw) || mag * 10;
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(8));
    return out;
  };

  /* Dessine le graphique dans `host` (un div). opts : { mode: 'candles' | 'line' }. Renvoie rien ; remplace le contenu. */
  J.intradayChart = function (host, d, opts = {}) {
    const mode = opts.mode || 'candles', F = fmt(d.tz), sessions = d.sessions || [];
    host.innerHTML = '';
    if (!sessions.length) { host.innerHTML = '<div class="empty">Aucune barre de 15 minutes disponible pour ce titre.</div>'; return; }
    const W = 1000, H = 470, L = 64, R = 70, TOP = 38, PH = 270, GAP = 14, VH = 78, VTOP = TOP + PH + GAP, AX = VTOP + VH + 4;
    const gapBetween = 26, n = sessions.length;
    // domaine de créneaux de chaque séance (grille régulière, étendue si des barres sortent de la séance régulière)
    const dom = sessions.map(s => {
      const open = t(s.open_utc), idx = s.bars.map(b => Math.round((t(b[0]) - open) / SLOT));
      const lo = Math.min(0, ...idx), hi = Math.max(s.expected, ...idx.map(i => i + 1));
      return { s, open, lo, hi, idx };
    });
    const total = dom.reduce((a, x) => a + (x.hi - x.lo), 0), step = (W - L - R - gapBetween * (n - 1)) / total;
    let cursor = L;
    dom.forEach(x => { x.x0 = cursor; x.w = (x.hi - x.lo) * step; cursor += x.w + gapBetween; x.X = i => x.x0 + (i - x.lo) * step; });
    const all = sessions.flatMap(s => s.bars);
    const hi = Math.max(...all.map(b => b[2] ?? b[4])), lo = Math.min(...all.map(b => b[3] ?? b[4])), pad = (hi - lo || hi * .01) * .08;
    const y0 = lo - pad, y1 = hi + pad, Y = v => TOP + PH * (1 - (v - y0) / (y1 - y0));
    const vmax = Math.max(1, ...all.map(b => b[5] || 0)), VY = v => VTOP + VH * (1 - v / vmax);
    const dp = dec(hi), fp = v => J.num(v, dp);

    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, class: 'intraday-svg', role: 'img', 'aria-label': 'Graphique de 15 minutes sur deux séances' });
    const defs = el('defs'); const pat = el('pattern', { id: 'hatch', width: 6, height: 6, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' });
    pat.append(el('line', { x1: 0, y1: 0, x2: 0, y2: 6, class: 'hatch-line' })); defs.append(pat); svg.append(defs);

    niceTicks(y0, y1).forEach(v => { svg.append(el('line', { x1: L, x2: W - R, y1: Y(v), y2: Y(v), class: 'hgrid' })); svg.append(el('text', { x: L - 8, y: Y(v) + 4, class: 'axis', 'text-anchor': 'end' }, fp(v))); });
    const nowMs = t(d.now_utc);

    dom.forEach((x, si) => {
      const s = x.s, older = si < n - 1, g = el('g', { class: 'sess ' + (older ? 'older' : 'latest') });
      g.append(el('rect', { x: x.x0, y: TOP - 4, width: x.w, height: PH + VH + GAP + 8, class: 'band' + (si % 2 ? ' alt' : '') }));
      // en-tête : date locale, fuseau, état
      const open = x.open, state = s.in_progress ? 'en cours' : s.complete ? 'complète' : 'incomplète';
      g.append(el('text', { x: x.x0 + 6, y: 15, class: 'sess-title' }, F.day(open) + ' · ' + s.tz_label));
      g.append(el('text', { x: x.x0 + 6, y: 29, class: 'sess-sub' }, `${F.time(open)}–${F.time(t(s.close_utc))} · ${s.count}/${s.expected} barres · ${state}`));
      // repères horaires (heures pleines locales)
      for (let i = x.lo; i < x.hi; i++) {
        const ms = open + i * SLOT;
        if (F.minute(ms) === 0) {
          g.append(el('line', { x1: x.X(i), x2: x.X(i), y1: TOP, y2: VTOP + VH, class: 'vgrid' }));
          g.append(el('text', { x: x.X(i), y: AX + 14, class: 'axis', 'text-anchor': 'middle' }, F.time(ms)));
        }
      }
      // créneaux sans donnée (trous) et créneaux à venir
      const present = new Set(s.bars.map(b => t(b[0])));
      for (let i = 0; i < s.expected; i++) {
        const ms = open + i * SLOT;
        if (present.has(ms)) continue;
        const future = ms + SLOT > nowMs;
        g.append(el('rect', { x: x.X(i), y: TOP, width: step, height: PH + GAP + VH, class: future ? 'future' : 'hole' }, undefined));
      }
      // clôture de la séance précédente
      if (si > 0) {
        const prev = sessions[si - 1], pc = prev.bars[prev.bars.length - 1][4];
        g.append(el('line', { x1: x.x0, x2: x.x0 + x.w, y1: Y(pc), y2: Y(pc), class: 'prevclose' }));
        g.append(el('text', { x: x.x0 + x.w - 4, y: Y(pc) - 4, class: 'prevclose-label', 'text-anchor': 'end' }, 'clôture ' + F.day(t(prev.open_utc))));
      }
      // barres
      const pts = [];
      s.bars.forEach((b, i) => {
        const idx = x.idx[i], cx = x.X(idx) + step / 2, o = b[1], h = b[2], l = b[3], c = b[4], full = o !== null && h !== null && l !== null;
        const up = (o ?? c) <= c, cls = up ? 'up' : 'down';
        if (mode === 'candles' && full) {
          g.append(el('line', { x1: cx, x2: cx, y1: Y(h), y2: Y(l), class: 'wick ' + cls }));
          const top = Y(Math.max(o, c)), bh = Math.max(1.2, Math.abs(Y(o) - Y(c)));
          g.append(el('rect', { x: cx - step * .32, y: top, width: step * .64, height: bh, class: 'body ' + cls + (b[6] ? '' : ' prov') }));
        } else if (mode === 'candles') {
          g.append(el('circle', { cx, cy: Y(c), r: Math.max(1.6, step * .22), class: 'dot' }));
        }
        pts.push([cx, Y(c), idx]);
        if (b[5] !== null) g.append(el('rect', { x: cx - step * .32, y: VY(b[5]), width: step * .64, height: Math.max(.5, VTOP + VH - VY(b[5])), class: 'vol ' + cls }));
      });
      if (mode === 'line' || true) {      // la ligne des clôtures est coupée à chaque créneau manquant : rien n'est relié par-dessus un trou
        let seg = [], last = null;
        const flush = () => { if (seg.length > 1) g.append(el('polyline', { points: seg.map(p => p.join(',')).join(' '), class: 'line' + (mode === 'candles' ? ' faint' : '') })); seg = []; };
        pts.forEach(p => { if (last !== null && p[2] - last > 1) flush(); seg.push([p[0].toFixed(1), p[1].toFixed(1)]); last = p[2]; });
        flush();
      }
      svg.append(g);
    });
    svg.append(el('text', { x: L - 8, y: VTOP + 10, class: 'axis', 'text-anchor': 'end' }, 'Volume'));
    // dernier cours
    const lastBar = sessions[n - 1].bars[sessions[n - 1].bars.length - 1], lc = lastBar[4];
    svg.append(el('line', { x1: L, x2: W - R, y1: Y(lc), y2: Y(lc), class: 'lastline' }));
    svg.append(el('rect', { x: W - R + 2, y: Y(lc) - 9, width: R - 4, height: 18, rx: 4, class: 'lasttag' }));
    svg.append(el('text', { x: W - R + 6, y: Y(lc) + 4, class: 'lasttext' }, fp(lc)));
    // réticule et infobulle
    const cross = el('line', { y1: TOP, y2: VTOP + VH, class: 'cross', visibility: 'hidden' }); svg.append(cross);
    const tip = document.createElement('div'); tip.className = 'chart-tip'; tip.hidden = true;
    const wrap = document.createElement('div'); wrap.className = 'chart-wrap'; wrap.append(svg, tip); host.append(wrap);
    const slots = [];     // toutes les positions de survol : barres et trous
    dom.forEach(x => { const s = x.s; for (let i = x.lo; i < x.hi; i++) { const ms = x.open + i * SLOT, bi = s.bars.findIndex(b => t(b[0]) === ms); slots.push({ x: x.X(i) + step / 2, ms, bar: bi >= 0 ? s.bars[bi] : null, s, i }); } });
    const move = ev => {
      const r = svg.getBoundingClientRect(), px = ((ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left) * W / r.width;
      let best = null; for (const p of slots) if (best === null || Math.abs(p.x - px) < Math.abs(best.x - px)) best = p;
      if (!best || Math.abs(best.x - px) > step * 2) return leave();
      cross.setAttribute('x1', best.x); cross.setAttribute('x2', best.x); cross.setAttribute('visibility', 'visible');
      const b = best.bar, head = `<b>${F.day(best.ms)} · ${F.time(best.ms)}–${F.time(best.ms + SLOT)}</b> <span class="muted">${F.zone(best.ms)} · ${new Date(best.ms).toISOString().slice(11, 16)} UTC</span>`;
      const first = best.s.bars[0], sOpen = first[1] ?? first[4];
      tip.innerHTML = !b ? `${head}<div class="muted">${best.ms + SLOT > nowMs ? 'Créneau à venir.' : 'Aucune donnée pour ce créneau (trou de source, journée écourtée ou suspension).'}</div>` :
        `${head}<div class="tip-grid">${b[1] !== null && b[2] !== null && b[3] !== null ? `<span>Ouv.</span><b>${fp(b[1])}</b><span>Haut</span><b>${fp(b[2])}</b><span>Bas</span><b>${fp(b[3])}</b>` : '<span class="muted" style="grid-column:1/-1">Bougie complète non disponible : cours de clôture du créneau seulement.</span>'}<span>Clôt.</span><b>${fp(b[4])} ${J.esc(d.currency || '')}</b><span>Volume</span><b>${b[5] === null ? 'absent' : J.num(b[5], 0)}</b><span>Vs ouverture de séance</span><b class="${J.cls(b[4] - sOpen)}">${J.pct(100 * (b[4] / sOpen - 1), 2)}</b></div>${b[6] ? '' : '<div class="small warn">Barre provisoire : le créneau n’est pas terminé.</div>'}`;
      tip.hidden = false;
      const wr = wrap.getBoundingClientRect(), left = best.x * r.width / W + (r.left - wr.left);
      tip.style.left = Math.min(Math.max(8, left + 14), wr.width - tip.offsetWidth - 8) + 'px'; tip.style.top = '8px';
    };
    const leave = () => { cross.setAttribute('visibility', 'hidden'); tip.hidden = true; };
    svg.addEventListener('mousemove', move); svg.addEventListener('mouseleave', leave); svg.addEventListener('touchmove', move, { passive: true }); svg.addEventListener('touchend', leave);
  };

  /* Panneau complet : en-tête de source, résumés des deux séances, graphique, notes. */
  J.intradayPanel = async function (host, listingId, { onData } = {}) {
    let mode = 'candles', data = null, timer = null;
    host.innerHTML = '<div class="empty"><span class="spinner"></span> Lecture des deux dernières séances…</div>';
    const load = async fetchLive => {
      try { data = await J.api('intraday', { params: { id: listingId, fetch: fetchLive ? 1 : 0 } }); } catch (e) { host.innerHTML = `<div class="notice err">${J.esc(e.message)}</div>`; return; }
      render(); if (onData) onData(data);
      clearTimeout(timer); if (data.market_open) timer = setTimeout(() => document.body.contains(host) && load(true), 120000);
    };
    function render() {
      const d = data;
      if (!d.supported) { host.innerHTML = `<div class="notice">${J.esc(d.note)}</div>`; return; }
      const F = fmt(d.tz), last = d.last_bar_utc ? t(d.last_bar_utc) : null;
      const chips = [`<span class="chip">Barres de ${d.interval_minutes} min · aucune interpolation</span>`, `<span class="chip">Fuseau de la place : ${J.esc(d.tz)}</span>`,
        `<span class="chip">Source : ${J.esc(d.source)}</span>`,
        d.market_open ? '<span class="badge ok">Place ouverte</span>' : '<span class="badge">Place fermée</span>',
        d.delayed ? `<span class="badge wait">Différé · ${d.lag_minutes} min</span>` : '',
        last ? `<span class="chip">Dernière barre : ${F.day(last)} ${F.time(last)} ${F.zone(last)}</span>` : ''].join('');
      const cards = d.sessions.map((s, i) => {
        const m = s.summary, older = i < d.sessions.length - 1;
        return `<div class="sess-card ${older ? 'older' : 'latest'}"><div class="small muted">${older ? 'Séance précédente' : (s.in_progress ? 'Séance en cours' : 'Dernière séance')}</div>
          <b>${F.dayLong(t(s.open_utc))}</b>
          <div class="sess-line"><span>Ouv. <b>${J.num(m.open, dec(m.open))}</b></span><span>Haut <b>${J.num(m.high, dec(m.high))}</b></span><span>Bas <b>${J.num(m.low, dec(m.low))}</b></span><span>Clôt. <b>${J.num(m.close, dec(m.close))}</b></span></div>
          <div class="sess-line"><span class="${J.cls(m.change_pct)}"><b>${J.pct(m.change_pct)}</b> sur la séance</span><span>Volume <b>${m.volume === null ? 'absent' : J.num(m.volume, 0)}</b>${m.volume_complete ? '' : ' <span class="warn">(partiel)</span>'}</span></div>
          <div class="small muted">${s.count}/${s.expected} barres${s.missing.length ? ` · <span class="warn">${s.missing.length} trou(s)</span>` : ''}${s.in_progress ? ' · en cours' : s.complete ? ' · complète' : ' · incomplète'}</div></div>`;
      }).join('');
      host.innerHTML = `<div class="row between wrap-s" style="margin-bottom:10px"><div class="chips">${chips}</div>
        <div class="row gap-s"><span class="seg" id="imode"><button data-m="candles" class="${mode === 'candles' ? 'on' : ''}">Bougies</button><button data-m="line" class="${mode === 'line' ? 'on' : ''}">Ligne</button></span><button class="btn small" id="irefresh" title="Relire les barres chez Yahoo Finance">↻ Actualiser</button></div></div>
        <div class="sess-cards">${cards}</div><div id="ichart"></div>
        <div class="legend small muted"><span><i class="lg up"></i> clôture ≥ ouverture</span><span><i class="lg down"></i> clôture &lt; ouverture</span><span><i class="lg hole"></i> créneau sans donnée</span><span><i class="lg dash"></i> clôture de la séance précédente</span><span>Survolez le graphique pour le détail de chaque barre.</span></div>
        ${d.notes.length ? `<div class="notice warn" style="margin-top:10px">${d.notes.map(n => `<div>${J.esc(n)}</div>`).join('')}</div>` : ''}`;
      J.intradayChart(J.$('#ichart', host), d, { mode });
      J.$$('#imode button', host).forEach(b => b.onclick = () => { mode = b.dataset.m; render(); });
      J.$('#irefresh', host).onclick = () => load(true);
    }
    await load(true);
  };
})();
