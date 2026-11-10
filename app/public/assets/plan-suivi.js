/* Plan de suivi d'une position : jauge de prix, conseil (Conserver / Surveiller / Réévaluer / Sortie à envisager), règles automatiques ou personnalisées.
   Données calculées par le moteur (engine/analytics/position_plan.py, route tracking/state) ; ce fichier ne fait que les afficher et enregistrer les réglages demandés.
   Une seule source : la ligne de « Suivi des positions » et la carte du détail d'une position utilisent les mêmes fonctions (gauge, adviceBox) et les mêmes données.
   Aucune vente automatique, aucun objectif de gain inventé, aucune valeur personnelle écrasée sans action explicite de l'utilisateur. */
(function (root) {
  'use strict';
  const isNum = v => typeof v === 'number' && isFinite(v);
  const esc = s => J.esc(String(s == null ? '' : s));
  const eur = (v, d = 2) => isNum(v) ? J.eur(v, d) : '–';
  const pc = (v, d = 1, sign = true) => isNum(v) ? (sign && v > 0.004 ? '+' : v < -0.004 ? '−' : '') + J.num(Math.abs(v), d) + ' %' : '–';
  const sgn = v => isNum(v) ? (v > 0.004 ? '+' : v < -0.004 ? '−' : '') + J.eur(Math.abs(v), 2) : '–';
  const cl = v => isNum(v) ? (v > 0.004 ? 'up' : v < -0.004 ? 'down' : '') : '';
  const ICON = {
    shield: c => `<svg viewBox="0 0 24 24" aria-hidden="true" class="ps-shield ${c}"><path d="M12 2.5l7 2.6v6.2c0 4.6-3 8.1-7 10.2-4-2.1-7-5.6-7-10.2V5.1z" fill="currentColor"/></svg>`,
    up: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17l6-6 4 4 8-8M15 7h6v6" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    down: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7l6 6 4-4 8 8M15 17h6v-6" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    flat: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12h18M16 7l5 5-5 5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    pulse: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12h4l2.5-6 4 12 2.5-6H21" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    arrow: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 9v9H9" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    bars: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 20v-6M12 20V8M18 20v-9" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>',
    ok: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="currentColor"/><path d="M7.5 12.5l3 3 6-6.5" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    info: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="currentColor"/><path d="M12 11v6M12 7.5v.5" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/></svg>',
    warn: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.8l10 17.4H2z" fill="currentColor"/><path d="M12 9v5M12 17v.5" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/></svg>',
    exit: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="currentColor"/><path d="M8 8l8 8M16 8l-8 8" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/></svg>',
    gear: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    i: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M12 11v5.5M12 7.6v.4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
  };
  /** Quatre états de décision (jamais un ordre) + suivi partiel. tone = classe visuelle, k = classe du pastille du tableau (colonne « Suivi »). */
  const STATE = {
    exit: { label: 'Sortie à envisager', tone: 'exit', icon: 'exit', k: 'ko', rank: 0 },
    reevaluate: { label: 'Réévaluer', tone: 'reeval', icon: 'warn', k: 'rv', rank: 1 },
    watch: { label: 'Surveiller', tone: 'watch', icon: 'info', k: 'na', rank: 2 },
    keep: { label: 'Conserver', tone: 'ok', icon: 'ok', k: 'ok', rank: 3 },
    na: { label: 'Suivi partiel', tone: 'na', icon: 'info', k: 'none', rank: 4 }
  };
  const RISK_CLASS = { low: 'r-low', moderate: 'r-mod', high: 'r-high', very_high: 'r-vhigh' };
  const stateOf = pl => (pl && pl.advice && STATE[pl.advice.state]) ? pl.advice.state : 'na';
  const rule = (pl, k) => ((pl && pl.rules) || []).find(r => r.key === k) || null;

  /** Pastille pour le tableau des positions (colonne « Suivi ») et la synthèse : l'état de décision, jamais « vendre ». */
  function chip(pl) {
    if (!pl) return { k: 'na', t: 'Chargement…', rank: 5 };
    if (pl.status === 'unavailable') return { k: 'none', t: 'Indisponible', rank: 4 };
    const s = STATE[stateOf(pl)];
    return { k: s.k, t: s.label, rank: s.rank, state: stateOf(pl) };
  }

  /** Échelle de la jauge : linéaire, ou logarithmique quand l'écart entre le plus bas et le plus haut dépasse ×3 (fortes progressions). */
  function scale(vals) {
    const v = vals.filter(x => isNum(x) && x > 0), lo = Math.min(...v) * 0.96, hi = Math.max(...v) * 1.04, log = hi / lo > 3;
    const f = log ? Math.log : x => x, a = f(lo), b = f(hi);
    return { log, lo, hi, at: x => Math.max(0, Math.min(100, 100 * (f(x) - a) / (b - a))) };
  }

  /** Repères placés selon les prix réels. Protection effective : personnelle si définie (la suggestion automatique reste visible), sinon automatique. */
  function markers(pl) {
    const P = pl.prices, cur = P.current, out = [], st = rule(pl, 'stop') || {}, off = st.enabled === false, custom = st.mode === 'custom' && isNum(P.personal);
    const add = (id, label, value, sub, cls, icon, dim) => { if (isNum(value) && value > 0) out.push({ id, label, value, sub, cls: cls + (dim ? ' ps-off' : ''), icon }); };
    const dist = v => isNum(v) ? pc(100 * (v / cur - 1)) : '';
    if (custom) add('personal', 'Protection perso' + (off ? ' (désactivée)' : ''), P.personal, dist(P.personal), 'ps-m-personal', 'shield', off);
    add('suggested', custom ? 'Suggestion auto' : 'Protection auto' + (off ? ' (désactivée)' : ''), P.suggested, dist(P.suggested), 'ps-m-suggested', 'shield', off && !custom);
    add('pru', 'PRU', P.pru, '', 'ps-m-pru', 'tick');
    add('current', 'Cours actuel', cur, pc(pl.gain && pl.gain.pct), 'ps-m-current', 'dot');
    add('high', 'Plus-haut', P.high, pc(-pl.recul_pct), 'ps-m-high', 'hdot');
    const tg = rule(pl, 'target'); if (tg && tg.mode === 'custom' && isNum(P.target)) add('target', 'Objectif perso' + (tg.enabled === false ? ' (désactivé)' : ''), P.target, dist(P.target), 'ps-m-target', 'flag', tg.enabled === false);
    return out;
  }
  const symOf = x => x.icon === 'shield' ? ICON.shield(x.id === 'personal' ? 'own' : 'sug') : x.icon === 'tick' ? '<i class="ps-tick"></i>' : x.icon === 'dot' ? '<i class="ps-dot"></i>' : x.icon === 'flag' ? '<i class="ps-flagm"></i>' : '<i class="ps-hdot"></i>';

  function gauge(pl, opt) {
    const compact = !!(opt && opt.compact), TIER = compact ? 34 : 62, GAP = compact ? 30 : 17;
    const P = pl.prices, m = markers(pl), sc = scale(m.map(x => x.value));
    // dégradé ancré sur les niveaux : rouge sous la plus basse protection, jaune au PRU, vert au-dessus. Ce sont des zones de prix et de protection, pas une garantie de faible risque.
    const prot = m.filter(x => x.id === 'personal' || x.id === 'suggested').map(x => sc.at(x.value)), xp = isNum(P.pru) ? sc.at(P.pru) : 50;
    const lowest = prot.length ? Math.min(...prot) : Math.max(0, xp - 25), mid = (lowest + xp) / 2;
    const grad = `linear-gradient(90deg,#d6342d 0%,#d6342d ${Math.max(lowest - 4, 0).toFixed(1)}%,#ea6a1e ${lowest.toFixed(1)}%,#f0a30a ${mid.toFixed(1)}%,#e6c200 ${xp.toFixed(1)}%,#7fb11e ${Math.min(xp + (100 - xp) * 0.35, 100).toFixed(1)}%,#1f8f4e ${Math.min(xp + (100 - xp) * 0.75, 100).toFixed(1)}%,#14783f 100%)`;
    const sorted = m.slice().sort((a, b) => sc.at(a.value) - sc.at(b.value)), labelled = compact ? sorted.filter(x => x.id !== 'high') : sorted;
    // alternance de niveaux d'étiquettes pour éviter les chevauchements (repères très proches ou superposés)
    const tier = {}; const last = []; labelled.forEach(x => { const xv = sc.at(x.value); let t = 0; while (last[t] !== undefined && xv - last[t] < GAP) t++; tier[x.id] = t; last[t] = xv; });
    const rows = Math.max(...Object.values(tier), 0) + 1;
    const mk = x => { const xv = sc.at(x.value), t = tier[x.id] || 0, nolab = compact && x.id === 'high';
      return { sym: `<span class="ps-mk ${x.cls}" style="left:${xv.toFixed(2)}%" title="${esc(x.label)} ${eur(x.value)}">${symOf(x)}</span>`,
        lab: nolab ? '' : `<span class="ps-lb ${x.cls}" style="left:${xv.toFixed(2)}%;top:${t * TIER}px"><b>${esc(x.label)}</b><strong>${eur(x.value)}</strong>${x.sub ? `<em class="${x.id === 'current' ? cl(pl.gain && pl.gain.pct) : x.id === 'high' || x.id === 'personal' ? 'down' : 'sug'}">${x.sub}</em>` : ''}</span>`,
        leg: `<li class="${x.cls}"><span>${symOf(x)}</span><b>${esc(x.label)}</b><strong>${eur(x.value)}</strong>${x.sub ? `<em>${x.sub}</em>` : ''}</li>` }; };
    const parts = sorted.map(mk);
    const note = sc.log ? '<small class="ps-scale">Échelle logarithmique (forte progression) : les distances sont proportionnelles aux variations en %.</small>' : '';
    return `<div class="ps-gauge${compact ? ' ps-compact' : ''}" role="img" aria-label="Jauge de prix : ${sorted.map(x => esc(x.label) + ' ' + eur(x.value)).join(', ')}">
      <div class="ps-track" style="background:${grad}">${parts.map(p => p.sym).join('')}</div>
      <div class="ps-labels" style="height:${rows * TIER}px">${parts.map(p => p.lab).join('')}</div>
      <ul class="ps-legend">${parts.map(p => p.leg).join('')}</ul>${note}</div>`;
  }

  function tiles(pl) {
    const t = pl.trend, r = pl.risk, mo = pl.momentum || {};
    const trendIcon = t ? ICON[t.state] : ICON.flat;
    const mom = mo.available ? `<b class="${cl(mo.value)}">${pc(mo.value)}</b>${mo.active ? '<small class="ps-flag">alerte active</small>' : mo.negative_at_open ? '<small>déjà négatif à l’ouverture</small>' : ''}` : '<b class="ps-na">indisponible</b>';
    return `<div class="ps-tiles">
      <div class="ps-tile"><span class="ps-ic t-${t ? t.state : 'flat'}">${trendIcon}</span><div><small>Tendance (63 séances)</small><b>${t ? esc(t.label) : '<span class="ps-na">indisponible</span>'}</b></div></div>
      <div class="ps-tile"><span class="ps-ic ic-pulse">${ICON.pulse}</span><div><small>Risque (volatilité 63j)</small>${r ? `<span class="ps-risk ${RISK_CLASS[r.level]}">${esc(r.label)} (${J.num(r.sigma63, 1)} %)</span>` : '<b class="ps-na">indisponible</b>'}</div></div>
      <div class="ps-tile"><span class="ps-ic ic-down">${ICON.arrow}</span><div><small>Recul depuis le sommet</small><b>${isNum(pl.recul_pct) ? pc(-pl.recul_pct) : '–'}</b></div></div>
      <div class="ps-tile"><span class="ps-ic ic-bars">${ICON.bars}</span><div><small>Momentum 6−1</small>${mom}</div></div></div>`;
  }

  const firstSentence = t => { const s = String(t || ''), i = s.search(/[.!?](\s|$)/); return i > 0 ? s.slice(0, i + 1) : s; };

  /** Conseil principal : badge d'état + règle déclenchée + explication ; protection effective ; autres règles déclenchées et « pourquoi » consultables. */
  function adviceBox(pl, opt) {
    const compact = !!(opt && opt.compact);
    const a = pl.advice || { state: 'na', message: 'Suivi indisponible.', detail: '', why: [], others: [] }, sk = STATE[a.state] ? a.state : 'na', S = STATE[sk];
    const msg = a.message || a.headline || '', others = a.others || [];
    const more = `${compact ? `<p class="ps-full">${esc(a.detail)}</p>` : ''}${others.length ? `<div class="ps-others"><b>${others.length} autre${others.length > 1 ? 's règles déclenchées' : ' règle déclenchée'}</b><ul>${others.map(o => `<li><span class="ps-os ${STATE[o.state] ? STATE[o.state].tone : ''}">${esc(o.label)}</span> ${esc(o.text)}<small>${esc(o.detail || '')}</small></li>`).join('')}</ul></div>` : ''}${a.why && a.why.length ? `<div class="ps-why"><b>Pourquoi ce message ?</b><ul>${a.why.map(w => `<li>${esc(w)}</li>`).join('')}</ul></div>` : ''}`;
    return `<div class="ps-advice ${S.tone} st-${sk}" role="status"><span class="ps-ai">${ICON[S.icon]}</span><div class="ps-ab"><div class="ps-line"><span class="ps-state">${esc(S.label)}</span><b>${esc(msg)}</b></div>
      <p class="ps-detail">${esc(compact ? firstSentence(a.detail) : a.detail)}</p>${a.protection ? `<p class="ps-prot">${esc(a.protection)}</p>` : ''}
      ${more ? `<details class="ps-more"><summary>${compact ? 'Explication et détails' : (others.length ? 'Autres règles et explication' : 'Pourquoi ce message ?')}</summary>${more}</details>` : ''}</div></div>`;
  }

  function header(pl) {
    const g = pl.gain || {}, st = pl.strategy || {}, label = st.label ? esc(st.label) : 'Stratégie non définie';
    return `<div class="ps-head"><div class="ps-id"><div class="ps-t"><strong>${esc(pl.symbol)}</strong><span class="ps-chip ${st.support === 'undefined' ? 'neutral' : ''}" title="Stratégie de surveillance de la position">${label}</span></div><small>${esc(pl.name || '')}</small></div>
      <div class="ps-gain ${cl(g.pct)}"><strong>${pc(g.pct)}</strong><span>${sgn(g.eur)}</span></div></div>`;
  }

  function originsLine(pl) {
    const o = (pl.origins || []).filter(x => x.label);
    if (!o.length) return '';
    const by = {}; o.forEach(x => { by[x.label] = (by[x.label] || 0) + 1; });
    return `<p class="ps-origin">Stratégie d’origine des achats (historique, inchangée) : ${Object.entries(by).map(([l, n]) => esc(l) + (n > 1 ? ' × ' + n : '')).join(' · ')}.</p>`;
  }

  /** Une ligne de « Suivi des positions » (grille type tableau) : titre, performance, jauge avec protections, conseil en une ligne, actions ; le détail complet s'ouvre sous la ligne. */
  function row(pl, o) {
    o = o || {};
    const g = pl.gain || {}, st = pl.strategy || {}, sk = stateOf(pl), S = STATE[sk], key = o.key ? ` data-open="${esc(o.key)}"` : '';
    const ok = pl.status !== 'unavailable' && pl.prices, a = pl.advice || {}, id = esc(pl.listing_id);
    const hl = ok ? `<p class="psr-hl">Plus-haut depuis l’entrée : <b>${eur(pl.prices.high)}</b> · recul <b class="${pl.recul_pct > 0.004 ? 'down' : ''}">${pc(-pl.recul_pct)}</b></p>` : '';
    return `<article class="psr st-${sk}" data-ps-row="${id}" aria-label="Suivi ${esc(pl.symbol)}">
      <div class="psr-id"><button type="button" class="psr-name"${key} title="Ouvrir le détail de la position"><strong>${esc(pl.symbol)}</strong><small>${esc(pl.name || '')}</small></button>
        <span class="ps-chip ${st.support === 'undefined' ? 'neutral' : ''}" title="Stratégie de surveillance de la position">${st.label ? esc(st.label) : 'Stratégie non définie'}</span></div>
      <div class="psr-gain ${cl(g.pct)}"><strong>${pc(g.pct)}</strong><span>${sgn(g.eur)}</span></div>
      <div class="psr-gauge">${ok ? gauge(pl, { compact: true }) : '<span class="ps-na">jauge indisponible</span>'}</div>
      <div class="psr-adv ps-advice ${S.tone} st-${sk}" role="status"><span class="ps-state">${esc(S.label)}</span> <span class="psr-msg">${esc(a.message || a.headline || 'Suivi indisponible.')}</span></div>
      <div class="psr-act"><button type="button" class="btn small psr-cfg" data-ps-cfg="${id}">${ICON.gear} Configurer</button><button type="button" class="btn small psr-exp" data-ps-exp="${id}" aria-expanded="false" aria-controls="psr-more-${id}" aria-label="Afficher l’explication et les détails" title="Explication et détails"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></button></div>
      <div class="psr-more" id="psr-more-${id}" hidden>${adviceBox(pl)}${hl}</div></article>`;
  }

  /** Rend la carte complète (détail d'une position) dans `host`. ctx : { plan, strategies, portfolio, listing, reload() }. */
  function render(host, ctx) {
    const pl = ctx.plan;
    if (!pl) { host.innerHTML = '<p class="notice err">Plan de suivi indisponible. Rechargez la page.</p>'; return; }
    if (pl.status === 'unavailable' || !pl.prices) {
      host.innerHTML = `<section class="ps-card">${header(pl)}${adviceBox(pl)}</section>`; return;
    }
    const sug = isNum(pl.prices.suggested), tg = rule(pl, 'target');
    host.innerHTML = `<section class="ps-card">${header(pl)}${gauge(pl)}${tiles(pl)}${adviceBox(pl)}
      ${(pl.notes || []).length ? `<ul class="ps-notes">${pl.notes.map(n => `<li>${esc(n)}</li>`).join('')}</ul>` : ''}
      ${originsLine(pl)}
      <div class="ps-foot"><p>${ICON.i}<span><b>Protection automatique</b> : repère de risque fondé sur le plus-haut depuis l’ouverture et la volatilité, jamais un ordre de vente ${sug ? `(${esc(J.num(pl.suggested.distance_pct, 1))} % sous le plus-haut : pire repli à 21 séances dépassé dans 1 cas sur 10 pour une volatilité comparable)` : ''}. Les couleurs de la jauge sont des zones de prix, pas une garantie de faible risque. Aucun objectif de gain automatique.${tg && tg.mode === 'custom' && isNum(tg.custom) ? ` Objectif personnel : ${esc(eur(tg.custom))}.` : ''}</span></p>
        <button type="button" class="btn small ps-set" data-ps-settings>${ICON.gear} Configurer</button></div>
      <details class="ps-method"><summary>Méthode et limites</summary><div>${esc((pl.strategy && pl.strategy.note) || '')}<p>Calculs sur les clôtures corrigées des splits, en euros au change du jour. Étude : un seul cycle d’environ 14 mois, ~9 600 titres ; les seuils (bandes de volatilité, centile 90) ne sont pas validés sur d’autres cycles. L’alerte de tendance (momentum 6−1 négatif) a un effet historique modeste et ne prédit pas la baisse suivante. Le dernier mois est exclu du momentum.</p></div></details></section>`;
    host.querySelector('[data-ps-settings]').onclick = () => configure(ctx);
  }

  /* ───────── dialogue « Configurer » : stratégie de surveillance et règles (automatique par défaut, personnalisable, activable une à une) ───────── */
  const VALUE_RULES = ['stop', 'recul', 'target'];
  const HELP = {
    stop: 'Repère de protection : sous ce prix, la position passe en « Sortie à envisager ». Automatique : plus-haut depuis l’ouverture moins le repli que 9 titres comparables sur 10 ne dépassent pas sur 21 séances.',
    recul: 'Recul maximal depuis le plus-haut. Automatique : repli médian habituel (alerte « Surveiller »). Personnalisé : ton seuil, qui déclenche « Réévaluer ».',
    trend: 'Alerte quand le momentum 6−1 devient négatif après avoir été positif. Disponible selon la stratégie de surveillance (effet historique modeste).',
    risk: 'Alerte quand la volatilité sur 63 séances est élevée ou très élevée. Information de vigilance, jamais une sortie.',
    target: 'Objectif de gain facultatif, uniquement si tu en définis un : aucun objectif automatique. Atteint, il passe la position en « Sortie à envisager ».'
  };
  function configure(ctx) {
    const pl = ctx.plan, cur = (pl.watch && pl.watch.key) || '', cc = (pl.personal && pl.personal.currency) || '', fx = pl.prices && pl.prices.fx;
    const loc = v => isNum(v) && isNum(fx) && fx > 0 && cc && cc !== 'EUR' ? ` (≈ ${J.num(v / fx, 2)} ${esc(cc)})` : '';
    const opts = '<option value="">Aucune (suivi neutre)</option>' + (ctx.strategies || []).map(s => `<option value="${esc(s.key)}" ${s.key === cur ? 'selected' : ''}>${esc(s.label)}${s.custom ? ' (personnelle)' : ''}</option>`).join('');
    const rules = pl.rules || [], init = {};
    rules.forEach(r => { init[r.key] = { mode: r.mode === 'custom' ? 'custom' : 'auto', value: r.key === 'recul' ? (r.custom != null ? String(r.custom) : '') : (r.custom_local != null ? String(r.custom_local) : ''), enabled: r.enabled !== false }; });
    const autoText = r => r.key === 'stop' ? (isNum(r.auto) ? `<b>${eur(r.auto)}</b>${loc(r.auto)}` : '<span class="ps-na">indisponible</span>')
      : r.key === 'recul' ? (isNum(r.auto) ? `<b>${J.num(r.auto, 1)} %</b> (repli médian habituel)` : '<span class="ps-na">indisponible</span>')
        : r.key === 'target' ? '<b>aucun</b> (le suivi n’invente pas d’objectif)' : '';
    const block = r => { const hasVal = VALUE_RULES.includes(r.key), i = init[r.key], custom = i.mode === 'custom', unit = r.key === 'recul' ? '%' : (cc || 'devise du titre');
      return `<fieldset class="ps-rule" data-rule="${r.key}"><legend>${esc(r.label)}</legend>
        <div class="ps-rule-top"><span class="ps-tag ${custom ? 'custom' : 'auto'}" data-tag>${r.key === 'target' ? (custom ? 'Personnel' : 'Aucun') : r.key === 'trend' || r.key === 'risk' ? 'Automatique' : (custom ? 'Personnalisé' : 'Automatique')}</span>
          <label class="check"><input type="checkbox" data-en ${i.enabled ? 'checked' : ''}> Règle activée</label></div>
        ${hasVal ? `<p class="small">${r.key === 'target' ? 'Automatique : ' : 'Valeur automatique : '}${autoText(r)}</p>
          <div class="ps-rule-val"><label class="check"><input type="radio" name="m-${r.key}" value="auto" ${custom ? '' : 'checked'}> ${r.key === 'target' ? 'Aucun objectif' : 'Automatique'}</label>
            <label class="check"><input type="radio" name="m-${r.key}" value="custom" ${custom ? 'checked' : ''}> Personnalisé</label>
            <input data-val inputmode="decimal" aria-label="${esc(r.label)} personnalisé (${esc(unit)})" value="${esc(i.value)}" placeholder="${esc(unit)}" ${custom ? '' : 'disabled'}>
            <button type="button" class="btn small" data-reset ${custom ? '' : 'hidden'}>Rétablir l’automatique</button></div>` : (r.available ? '' : '')}
        <p class="small muted">${esc(HELP[r.key])}${r.note && !(hasVal && r.key === 'target') ? ' ' + esc(r.note) : ''}</p></fieldset>`; };
    const post = (r, d) => J.post('tracking/rules', Object.assign({ portfolio_id: ctx.portfolio, listing_id: ctx.listing, rule: r }, d));
    const d = J.dialog({ title: 'Configurer le suivi · ' + (pl.symbol || ''), body: `<p class="small muted">Toutes les règles sont automatiques par défaut. Une valeur personnelle devient la référence pour CETTE règle seulement : le moteur continue de calculer sa suggestion sans l’écraser. Une protection est un repère de surveillance, jamais une vente.</p>
      ${J.field('Stratégie de surveillance de la position', `<select id="ps-st">${opts}</select>`)}
      <p class="small muted">La stratégie de surveillance choisit les alertes de tendance applicables. Elle n’empêche aucun réglage personnel et ne modifie ni tes achats ni leur stratégie d’origine.</p>
      ${rules.map(block).join('')}`,
      actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async dlg => {
        const st = J.$('#ps-st', dlg).value, calls = [];
        for (const r of rules) {
          const f = dlg.querySelector(`[data-rule="${r.key}"]`), i = init[r.key], en = f.querySelector('[data-en]').checked;
          if (VALUE_RULES.includes(r.key)) {
            const mode = (f.querySelector(`input[name="m-${r.key}"]:checked`) || {}).value || 'auto', raw = f.querySelector('[data-val]').value.trim().replace(',', '.');
            if (mode === 'custom') {
              if (raw === '' || !(+raw > 0)) throw new Error(`${r.label} : indique une valeur positive ou rétablis l’automatique.`);
              if (r.key === 'recul' && +raw >= 100) throw new Error('Recul maximal : un pourcentage entre 0 et 100.');
              if (i.mode !== 'custom' || +raw !== +i.value) calls.push([r.key, { mode: 'custom', value: raw }]);
            } else if (i.mode === 'custom') calls.push([r.key, { mode: 'auto' }]);
          }
          if (en !== i.enabled) calls.push([r.key, { enabled: en }]);
        }
        try {
          if (st !== cur) await J.post('tracking/strategy', { portfolio_id: ctx.portfolio, listing_id: ctx.listing, strategy: st || null });
          for (const [k, dd] of calls) await post(k, dd);
        } finally { await ctx.reload(); }
      } }] });
    // sélection du mode : active ou grise la valeur ; « Rétablir l'automatique » agit tout de suite sur CETTE règle seulement
    d.querySelectorAll('.ps-rule').forEach(f => { const key = f.dataset.rule, inp = f.querySelector('[data-val]'), rst = f.querySelector('[data-reset]'), tag = f.querySelector('[data-tag]');
      if (!inp) return;
      f.querySelectorAll(`input[name="m-${key}"]`).forEach(rd => rd.onchange = () => { const c = rd.value === 'custom' && rd.checked; inp.disabled = !c; rst.hidden = !c; if (c) inp.focus(); });
      rst.onclick = async () => { rst.disabled = true; try { await post(key, { mode: 'auto' }); init[key].mode = 'auto'; init[key].value = ''; inp.value = ''; inp.disabled = true; rst.hidden = true; f.querySelector(`input[name="m-${key}"][value="auto"]`).checked = true; tag.textContent = key === 'target' ? 'Aucun' : 'Automatique'; tag.className = 'ps-tag auto'; await ctx.reload(); } catch (e) { J.formError(d, e.message); } finally { rst.disabled = false; } }; });
    return d;
  }

  root.PlanSuivi = { render, chip, gauge, scale, markers, row, adviceBox, configure, STATE, stateOf };
})(typeof window !== 'undefined' ? window : globalThis);
