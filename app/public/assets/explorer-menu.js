/* Menu de l'Explorer : icônes des stratégies, bulles d'aide, curseurs à deux poignées et petits schémas. Aucune donnée n'est lue ni écrite ici : le calcul reste dans explorer.js et le moteur. */
(() => {
  const SVG = (inner, w = 56, h = 36) => `<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" fill="none" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${inner}</svg>`;
  const arrow = (x, y, c, dx = -6, dy = 0) => `<path d="M${x + dx} ${y - 5} L${x} ${y} L${x + dx - 2} ${y + 4}" stroke="${c}" stroke-width="2.4"/>`;
  const ICONS = {
    regular: SVG(`<polyline points="5,28 15,22 22,24 31,16 39,13 47,8" stroke="#1f9d55" stroke-width="3"/>${[[5, 28], [15, 22], [22, 24], [31, 16], [39, 13]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="2" fill="#1f9d55" stroke="none"/>`).join('')}${arrow(47, 8, '#1f9d55', -7, 3)}`),
    fast: SVG(`<polyline points="5,29 13,17 19,25 29,10 35,19 46,6" stroke="#f59e0b" stroke-width="3"/>${arrow(46, 6, '#f59e0b', -7, 3)}`),
    recovery: SVG(`<polyline points="8,7 20,29 30,14 45,6" stroke="#e5484d" stroke-width="3"/><path d="M5 12 L10 6 M13 6 L9 11" stroke="#e5484d" stroke-width="1.8" opacity=".6"/><circle cx="20" cy="29" r="2.2" fill="#e5484d" stroke="none"/>${arrow(45, 6, '#e5484d', -7, 3)}`),
    low_volatility: SVG(`<path d="M5 27 C13 25 16 19 24 19 S36 14 40 12 S45 9 47 8" stroke="#2f80ed" stroke-width="3"/>${arrow(47, 8, '#2f80ed', -7, 3)}`),
    momentum: SVG(`<polyline points="5,29 12,21 18,25 27,12 33,16 46,5" stroke="#4f46e5" stroke-width="3"/><polyline points="5,33 14,28 22,30" stroke="#4f46e5" stroke-width="1.6" opacity=".35"/>${arrow(46, 5, '#4f46e5', -7, 3)}`),
    momentum12: SVG(`<polyline points="3,31 9,24 15,27 22,17 28,21 36,9 46,4" stroke="#4f46e5" stroke-width="3"/><polyline points="3,35 14,31 26,33" stroke="#4f46e5" stroke-width="1.6" opacity=".35"/>${arrow(46, 4, '#4f46e5', -7, 3)}`),
    free: SVG(`<circle cx="22" cy="18" r="9" stroke="#64748b" stroke-width="2.6"/><path d="M29 25 L38 33" stroke="#64748b" stroke-width="3"/>`),
    custom: SVG(`<path d="M8 12h24M40 12h6M8 26h6M22 26h24" stroke="#64748b" stroke-width="2.6"/><circle cx="36" cy="12" r="4" stroke="#64748b" stroke-width="2.4"/><circle cx="18" cy="26" r="4" stroke="#64748b" stroke-width="2.4"/>`)
  };
  const icon = k => ICONS[k] || ICONS.custom;

  /* Petits schémas au-dessus des curseurs : ils illustrent le critère et suivent la valeur choisie (simple pédagogie, aucune donnée de marché). */
  const wrap = inner => `<svg viewBox="0 0 130 44" width="130" height="44" fill="none" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${inner}</svg>`;
  function chart(kind, f) {            // f : 0..1, position du réglage
    f = Math.max(0, Math.min(1, f));
    if (kind === 'r2') {               // points qui s'écartent d'une droite quand la régularité exigée baisse
      const spread = (1 - f) * 10, jit = [3, -5, 6, -2, 5, -4];
      return wrap('<polyline points="8,36 122,10" stroke="#9db8a8" stroke-width="2"/>' + jit.map((j, i) => { const x = 14 + i * 20, y = 34 - i * 4.7; return `<circle cx="${x}" cy="${(y + j * spread / 6).toFixed(1)}" r="3" fill="#1f9d55" stroke="none"/>`; }).join(''));
    }
    if (kind === 'slope3' || kind === 'slope1') {
      const end = 36 - f * 28;
      return wrap(`<line x1="6" y1="36" x2="124" y2="36" stroke="#b6c2cf" stroke-width="1.6" stroke-dasharray="3 4"/>` +
        (kind === 'slope3' ? `<polyline points="8,38 124,${end.toFixed(1)}" stroke="#1f9d55" stroke-width="2.6"/><circle cx="124" cy="${end.toFixed(1)}" r="3" fill="#1f9d55" stroke="none"/>`
          : `<polyline points="8,36 26,30 40,34 60,22 76,26 96,14 110,18 124,${(8 + (1 - f) * 12).toFixed(1)}" stroke="#1f9d55" stroke-width="2.6"/><circle cx="124" cy="${(8 + (1 - f) * 12).toFixed(1)}" r="3" fill="#1f9d55" stroke="none"/>`));
    }
    const amp = 3 + f * 14, pts = [];
    for (let i = 0; i <= 24; i++) pts.push(`${(6 + i * 4.9).toFixed(1)},${(22 + Math.sin(i / 24 * Math.PI * 3.4) * amp).toFixed(1)}`);
    return wrap(`<polyline points="${pts.join(' ')}" stroke="#64748b" stroke-width="2.4"/>`);
  }

  /* Bulle d'aide : un seul élément, repositionné sous le « ? » cliqué ; se ferme sur Échap ou un clic ailleurs. */
  let popEl = null, popFor = null;
  function closePop() { if (popEl) { popEl.remove(); popEl = null; if (popFor) popFor.setAttribute('aria-expanded', 'false'); popFor = null; } }
  function pop(anchor, html) {
    if (popFor === anchor) return closePop();
    closePop();
    popEl = document.createElement('div'); popEl.className = 'helppop'; popEl.setAttribute('role', 'dialog'); popEl.innerHTML = html; document.body.appendChild(popEl);
    const r = anchor.getBoundingClientRect(), w = Math.min(340, innerWidth - 16);
    popEl.style.width = w + 'px'; popEl.style.left = Math.max(8, Math.min(innerWidth - w - 8, r.left + r.width / 2 - w / 2)) + 'px'; popEl.style.top = (r.bottom + scrollY + 8) + 'px';
    popFor = anchor; anchor.setAttribute('aria-expanded', 'true');
  }
  document.addEventListener('click', e => { if (popEl && !popEl.contains(e.target) && !(popFor && popFor.contains(e.target))) closePop(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closePop(); });

  /* Curseur à deux poignées. Une poignée peut être verrouillée (le critère n'existe que d'un côté : minimum ou maximum). */
  const fmt = (v, d) => v.toFixed(d).replace('.', ',');
  const parse = s => { const n = parseFloat(String(s).replace(/\s/g, '').replace(',', '.')); return isFinite(n) ? n : NaN; };
  function dualRange(host, o) {
    const dec = o.dec ?? 0, lockLo = !!(o.lockLow || o.disabled), lockHi = !!(o.lockHigh || o.disabled);
    host.innerHTML = `<div class="dr${o.disabled ? ' off' : ''}"><div class="dr-track"><i class="dr-fill"></i>
      <b class="dr-th lo${o.lockLow ? ' locked' : ''}" role="slider" tabindex="${lockLo ? -1 : 0}" aria-label="${o.label} : minimum" aria-valuemin="${o.min}" aria-valuemax="${o.max}"></b>
      <b class="dr-th hi${o.lockHigh ? ' locked' : ''}" role="slider" tabindex="${lockHi ? -1 : 0}" aria-label="${o.label} : maximum" aria-valuemin="${o.min}" aria-valuemax="${o.max}"></b></div>
      <div class="dr-vals"><input class="lo" inputmode="decimal" aria-label="${o.label} : minimum" ${lockLo ? 'disabled' : ''}><span>-</span><input class="hi" inputmode="decimal" aria-label="${o.label} : maximum" ${lockHi ? 'disabled' : ''}>${o.unit ? `<em>${o.unit}</em>` : ''}</div></div>`;
    const track = host.querySelector('.dr-track'), fill = host.querySelector('.dr-fill'), tl = host.querySelector('.dr-th.lo'), th = host.querySelector('.dr-th.hi'), il = host.querySelector('input.lo'), ih = host.querySelector('input.hi');
    let low = o.low, high = o.high, timer;
    const snap = v => Number(Math.max(o.min, Math.min(o.max, Math.round(v / o.step) * o.step)).toFixed(6));
    const pct = v => (v - o.min) / (o.max - o.min) * 100;
    function paint() {
      tl.style.left = pct(low) + '%'; th.style.left = pct(high) + '%'; fill.style.left = pct(low) + '%'; fill.style.width = (pct(high) - pct(low)) + '%';
      tl.setAttribute('aria-valuenow', low); th.setAttribute('aria-valuenow', high);
      if (document.activeElement !== il) il.value = fmt(low, dec); if (document.activeElement !== ih) ih.value = fmt(high, dec);
      if (o.onInput) o.onInput(low, high);
    }
    const commit = () => { clearTimeout(timer); timer = setTimeout(() => o.onChange && o.onChange(low, high), 250); };
    function setLow(v) { low = Math.min(snap(v), high); paint(); }
    function setHigh(v) { high = Math.max(snap(v), low); paint(); }
    const ratio = e => { const r = track.getBoundingClientRect(); return Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)); };
    [[tl, setLow, lockLo], [th, setHigh, lockHi]].forEach(([el, set, locked]) => {
      if (locked) return;
      el.addEventListener('pointerdown', e => { e.preventDefault(); el.setPointerCapture(e.pointerId); el.classList.add('drag'); el.focus(); });
      el.addEventListener('pointermove', e => { if (el.hasPointerCapture(e.pointerId)) set(o.min + ratio(e) * (o.max - o.min)); });
      el.addEventListener('pointerup', e => { if (el.hasPointerCapture(e.pointerId)) { el.releasePointerCapture(e.pointerId); el.classList.remove('drag'); commit(); } });
      el.addEventListener('keydown', e => {
        const cur = el === tl ? low : high, big = o.step * 10, d = { ArrowLeft: -o.step, ArrowDown: -o.step, ArrowRight: o.step, ArrowUp: o.step, PageDown: -big, PageUp: big }[e.key];
        if (e.key === 'Home') set(o.min); else if (e.key === 'End') set(o.max); else if (d !== undefined) set(cur + d); else return;
        e.preventDefault(); commit();
      });
    });
    if (!lockLo || !lockHi) track.addEventListener('pointerdown', e => {       // un clic sur la barre déplace la poignée active la plus proche
      if (e.target.closest('.dr-th')) return;
      const v = o.min + ratio(e) * (o.max - o.min), cands = [!lockLo && ['lo', Math.abs(v - low)], !lockHi && ['hi', Math.abs(v - high)]].filter(Boolean).sort((a, b) => a[1] - b[1]);
      if (cands[0][0] === 'lo') setLow(v); else setHigh(v);
      commit();
    });
    [[il, setLow], [ih, setHigh]].forEach(([inp, set]) => {
      const done = () => { const n = parse(inp.value); if (isFinite(n)) { set(n); commit(); } else paint(); inp.value = fmt(inp === il ? low : high, dec); };
      inp.addEventListener('change', done); inp.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); inp.blur(); } });
    });
    paint();
    return { get: () => [low, high] };
  }
  window.JMenu = { icon, chart, pop, closePop, dualRange };
})();
