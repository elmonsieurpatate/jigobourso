/* Plan de suivi d'une position : jauge de prix, tendance, risque, recul, momentum 6−1 et conseil.
   Données calculées par le moteur (engine/analytics/position_plan.py, route tracking/state) ; ce fichier ne fait que les afficher.
   Aucune vente automatique, aucun objectif de gain, aucun niveau personnel modifié sans action explicite de l'utilisateur. */
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
    gear: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    i: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M12 11v5.5M12 7.6v.4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
  };
  const TONE = { ok: 'ok', info: 'info', watch: 'watch', alert: 'alert', na: 'na' };
  const TONE_ICON = { ok: 'ok', info: 'info', watch: 'warn', alert: 'warn', na: 'info' };
  const RISK_CLASS = { low: 'r-low', moderate: 'r-mod', high: 'r-high', very_high: 'r-vhigh' };

  /** Libellé court pour le tableau des positions (colonne « Suivi ») : état du plan, jamais « vendre ». */
  function chip(pl) {
    if (!pl) return { k: 'na', t: 'Chargement…', rank: 5 };
    if (pl.status === 'unavailable') return { k: 'na', t: 'Indisponible', rank: 4 };
    const a = pl.advice || {};
    if (a.tone === 'alert') return { k: 'ko', t: 'Protection atteinte', rank: 0 };
    if (a.tone === 'watch') return { k: 'na', t: 'Vigilance', rank: 1 };
    if (a.tone === 'info') return { k: 'info', t: 'Risque ' + (pl.risk ? pl.risk.label.toLowerCase() : ''), rank: 2 };
    if (a.tone === 'na') return { k: 'none', t: 'Suivi partiel', rank: 4 };
    return { k: 'ok', t: 'Aucun signal', rank: 3 };
  }

  /** Échelle de la jauge : linéaire, ou logarithmique quand l'écart entre le plus bas et le plus haut dépasse ×3 (fortes progressions). */
  function scale(vals) {
    const v = vals.filter(x => isNum(x) && x > 0), lo = Math.min(...v) * 0.96, hi = Math.max(...v) * 1.04, log = hi / lo > 3;
    const f = log ? Math.log : x => x, a = f(lo), b = f(hi);
    return { log, lo, hi, at: x => Math.max(0, Math.min(100, 100 * (f(x) - a) / (b - a))) };
  }

  function markers(pl) {
    const P = pl.prices, cur = P.current, out = [];
    const add = (id, label, value, sub, cls, icon) => { if (isNum(value) && value > 0) out.push({ id, label, value, sub, cls, icon }); };
    add('personal', 'Protection perso', P.personal, isNum(P.personal) ? pc(100 * (P.personal / cur - 1)) : '', 'ps-m-personal', 'shield');
    add('suggested', 'Protection suggérée', P.suggested, isNum(P.suggested) ? pc(100 * (P.suggested / cur - 1)) : '', 'ps-m-suggested', 'shield');
    add('pru', 'PRU', P.pru, '', 'ps-m-pru', 'tick');
    add('current', 'Cours actuel', cur, pc(pl.gain && pl.gain.pct), 'ps-m-current', 'dot');
    add('high', 'Plus-haut', P.high, pc(-pl.recul_pct), 'ps-m-high', 'hdot');
    return out;
  }

  function gauge(pl) {
    const P = pl.prices, m = markers(pl), sc = scale(m.map(x => x.value));
    // dégradé ancré sur les niveaux : rouge sous la plus basse protection, jaune au PRU, vert au-dessus. La couleur situe le cours, elle ne dit pas « vendre ».
    const prot = m.filter(x => x.id === 'personal' || x.id === 'suggested').map(x => sc.at(x.value)), xp = isNum(P.pru) ? sc.at(P.pru) : 50;
    const lowest = prot.length ? Math.min(...prot) : Math.max(0, xp - 25), mid = prot.length ? (lowest + xp) / 2 : (lowest + xp) / 2;
    const grad = `linear-gradient(90deg,#d6342d 0%,#d6342d ${Math.max(lowest - 4, 0).toFixed(1)}%,#ea6a1e ${lowest.toFixed(1)}%,#f0a30a ${mid.toFixed(1)}%,#e6c200 ${xp.toFixed(1)}%,#7fb11e ${Math.min(xp + (100 - xp) * 0.35, 100).toFixed(1)}%,#1f8f4e ${Math.min(xp + (100 - xp) * 0.75, 100).toFixed(1)}%,#14783f 100%)`;
    const sorted = m.slice().sort((a, b) => sc.at(a.value) - sc.at(b.value));
    // alternance de niveaux d'étiquettes pour éviter les chevauchements
    const tier = {}; let last = []; sorted.forEach(x => { const xv = sc.at(x.value); let t = 0; while (last[t] !== undefined && xv - last[t] < 17) t++; tier[x.id] = t; last[t] = xv; });
    const rows = Math.max(...Object.values(tier)) + 1;
    const mk = x => { const xv = sc.at(x.value), t = tier[x.id];
      const sym = x.icon === 'shield' ? ICON.shield(x.id === 'personal' ? 'own' : 'sug') : x.icon === 'tick' ? '<i class="ps-tick"></i>' : x.icon === 'dot' ? '<i class="ps-dot"></i>' : '<i class="ps-hdot"></i>';
      return { sym: `<span class="ps-mk ${x.cls}" style="left:${xv.toFixed(2)}%">${sym}</span>`,
        lab: `<span class="ps-lb ${x.cls}" style="left:${xv.toFixed(2)}%;top:${t * 62}px"><b>${esc(x.label)}</b><strong>${eur(x.value)}</strong>${x.sub ? `<em class="${x.id === 'current' ? cl(pl.gain && pl.gain.pct) : x.id === 'high' ? 'down' : x.id === 'personal' ? 'down' : 'sug'}">${x.sub}</em>` : ''}</span>`,
        leg: `<li class="${x.cls}"><span>${x.icon === 'shield' ? ICON.shield(x.id === 'personal' ? 'own' : 'sug') : x.icon === 'tick' ? '<i class="ps-tick"></i>' : x.icon === 'dot' ? '<i class="ps-dot"></i>' : '<i class="ps-hdot"></i>'}</span><b>${esc(x.label)}</b><strong>${eur(x.value)}</strong>${x.sub ? `<em>${x.sub}</em>` : ''}</li>` }; };
    const parts = sorted.map(mk);
    const note = sc.log ? '<small class="ps-scale">Échelle logarithmique (forte progression) : les distances sont proportionnelles aux variations en %.</small>' : '';
    return `<div class="ps-gauge" role="img" aria-label="Jauge de prix : ${sorted.map(x => esc(x.label) + ' ' + eur(x.value)).join(', ')}">
      <div class="ps-track" style="background:${grad}">${parts.map(p => p.sym).join('')}</div>
      <div class="ps-labels" style="height:${rows * 62}px">${parts.map(p => p.lab).join('')}</div>
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

  function adviceBox(pl) {
    const a = pl.advice || { tone: 'na', headline: 'Suivi indisponible.', detail: '', why: [] }, tone = TONE[a.tone] || 'na';
    return `<div class="ps-advice ${tone}" role="status"><span class="ps-ai">${ICON[TONE_ICON[tone]]}</span><div><b>${esc(a.headline)}</b><p>${esc(a.detail)}</p>
      ${a.why && a.why.length ? `<details><summary>Pourquoi ce message ?</summary><ul>${a.why.map(w => `<li>${esc(w)}</li>`).join('')}</ul></details>` : ''}</div></div>`;
  }

  function header(pl) {
    const g = pl.gain || {}, ws = pl.watch;
    const st = pl.strategy || {}, label = st.label ? esc(st.label) : 'Stratégie non définie';
    return `<div class="ps-head"><div class="ps-id"><div class="ps-t"><strong>${esc(pl.symbol)}</strong><span class="ps-chip ${st.support === 'undefined' ? 'neutral' : ''}" title="Stratégie de surveillance de la position">${label}</span></div><small>${esc(pl.name || '')}</small></div>
      <div class="ps-gain ${cl(g.pct)}"><strong>${pc(g.pct)}</strong><span>${sgn(g.eur)}</span></div></div>`;
  }

  function originsLine(pl) {
    const o = (pl.origins || []).filter(x => x.label);
    if (!o.length) return '';
    const by = {}; o.forEach(x => { by[x.label] = (by[x.label] || 0) + 1; });
    return `<p class="ps-origin">Stratégie d’origine des achats (historique, inchangée) : ${Object.entries(by).map(([l, n]) => esc(l) + (n > 1 ? ' × ' + n : '')).join(' · ')}.</p>`;
  }

  /** Rend la carte complète dans `host`. ctx : { plan, strategies, portfolio, listing, reload() }. */
  function render(host, ctx) {
    const pl = ctx.plan;
    if (!pl) { host.innerHTML = '<p class="notice err">Plan de suivi indisponible. Rechargez la page.</p>'; return; }
    if (pl.status === 'unavailable' || !pl.prices) {
      host.innerHTML = `<section class="ps-card">${header(pl)}${adviceBox(pl)}</section>`; return;
    }
    const sug = isNum(pl.prices.suggested);
    host.innerHTML = `<section class="ps-card">${header(pl)}${gauge(pl)}${tiles(pl)}${adviceBox(pl)}
      ${(pl.notes || []).length ? `<ul class="ps-notes">${pl.notes.map(n => `<li>${esc(n)}</li>`).join('')}</ul>` : ''}
      ${originsLine(pl)}
      <div class="ps-foot"><p>${ICON.i}<span><b>Protection suggérée</b> : repère de risque fondé sur le plus-haut depuis l’ouverture et la volatilité, jamais un ordre de vente ${sug ? `(${esc(J.num(pl.suggested.distance_pct, 1))} % sous le plus-haut : pire repli à 21 séances dépassé dans 1 cas sur 10 pour une volatilité comparable)` : ''}. Aucun objectif de gain n’est fixé.${pl.personal && isNum(pl.personal.target) ? ` Objectif personnel enregistré : ${esc(J.num(pl.personal.target, 2))} ${esc(pl.personal.currency || '')} (conservé, non utilisé par le suivi).` : ''}</span></p>
        <button type="button" class="btn small ps-set" data-ps-settings>${ICON.gear} Paramètres du suivi</button></div>
      <details class="ps-method"><summary>Méthode et limites</summary><div>${esc((pl.strategy && pl.strategy.note) || '')}<p>Calculs sur les clôtures corrigées des splits, en euros au change du jour. Étude : un seul cycle d’environ 14 mois, ~9 600 titres ; les seuils (bandes de volatilité, centile 90) ne sont pas validés sur d’autres cycles. L’alerte de tendance (momentum 6−1 négatif) a un effet historique modeste et ne prédit pas la baisse suivante. Le dernier mois est exclu du momentum.</p></div></details></section>`;
    host.querySelector('[data-ps-settings]').onclick = () => settings(ctx);
  }

  /** Paramètres : stratégie de surveillance (changeable) et protection personnelle (jamais écrasée sans enregistrement explicite). L'objectif personnel est conservé tel quel. */
  function settings(ctx) {
    const pl = ctx.plan, cur = (pl.watch && pl.watch.key) || '';
    const opts = '<option value="">Aucune (suivi neutre)</option>' + (ctx.strategies || []).map(s => `<option value="${esc(s.key)}" ${s.key === cur ? 'selected' : ''}>${esc(s.label)}${s.custom ? ' (personnelle)' : ''}</option>`).join('');
    const stop = pl.personal && isNum(pl.personal.stop) ? pl.personal.stop : '', cc = (pl.personal && pl.personal.currency) || '';
    J.dialog({ title: 'Paramètres du suivi · ' + (pl.symbol || ''), body: `<p class="small muted">La stratégie de surveillance détermine seulement les alertes de tendance affichées. Elle ne modifie ni tes achats, ni leur stratégie d’origine.</p>
      ${J.field('Stratégie de surveillance de la position', `<select id="ps-st">${opts}</select>`)}
      ${J.field(`Ma protection personnelle (prix en ${cc || 'devise du titre'}, vide = aucune)`, `<input id="ps-stop" inputmode="decimal" value="${stop === '' ? '' : esc(stop)}" placeholder="aucune">`)}
      <p class="small muted">Ce niveau t’appartient : le suivi ne le déplace jamais et ne le remplace pas par la protection suggérée.</p>`,
      actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async dlg => {
        const st = J.$('#ps-st', dlg).value, raw = J.$('#ps-stop', dlg).value.trim().replace(',', '.');
        if (raw !== '' && !(+raw > 0)) throw new Error('Prix de protection invalide');
        if (st !== cur) await J.post('tracking/strategy', { portfolio_id: ctx.portfolio, listing_id: ctx.listing, strategy: st || null });
        const prev = pl.personal && isNum(pl.personal.stop) ? pl.personal.stop : null;
        if ((raw === '' ? null : +raw) !== prev) await J.post('position/levels', { portfolio_id: ctx.portfolio, listing_id: ctx.listing, stop: raw === '' ? null : raw, target: pl.personal && isNum(pl.personal.target) ? pl.personal.target : null });
        await ctx.reload();
      } }] });
  }

  root.PlanSuivi = { render, chip, gauge, scale, markers };
})(typeof window !== 'undefined' ? window : globalThis);
