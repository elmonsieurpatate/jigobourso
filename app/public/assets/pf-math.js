/* Calculs du Portefeuille (module pur, testé sous Node). Entrée : l'historique du moteur (route portfolio/history) :
   dates, value, net_in, gain, purchases, lines[{key, symbol, name, values, net_in, purchases, quantities, gain}], trades[], performance{factors}, market{dates, lines[{key, prices}]}.
   Définitions (identiques à l'infobulle de l'interface) :
   - Résultat de période (€) = gain(fin) − gain(début), où gain = valeur − apports nets (plus-values latentes + réalisées) : indépendant des apports et retraits.
   - Performance hors mouvements = produit des facteurs quotidiens Dietz modifié du moteur (performance.linked) sur la période ; indisponible si un jour manque.
   - Rendement d'une position sur la période = résultat de période ÷ (valeur de départ + achats de la période).
   - Contribution (points) = résultat de période de la position ÷ (valeur de départ du portefeuille + achats de la période du portefeuille).
   Aucune valeur n'est inventée : un point manquant reste manquant. */
(function (root) {
  'use strict';
  const PERIODS = [['1d', '1J'], ['2d', '2J'], ['5d', '5J'], ['1w', '1S'], ['2w', '2S'], ['1m', '1M'], ['3m', '3M'], ['6m', '6M'], ['1y', '1A'], ['2y', '2A'], ['3y', '3A'], ['5y', '5A'], ['10y', '10A'], ['max', 'Max'], ['all', 'Depuis le début']];
  const MONTHS = { '1m': 1, '3m': 3, '6m': 6, '1y': 12, '2y': 24, '3y': 36, '5y': 60, '10y': 120 };
  const SESSIONS = { '1d': 1, '2d': 2, '5d': 5 };
  const isNum = v => typeof v === 'number' && isFinite(v);
  const at = (a, i) => (i < 0 ? 0 : a[i]);

  function shift(dateStr, period) {
    const d = new Date(dateStr + 'T00:00:00Z');
    if (period === '1w' || period === '2w') { d.setUTCDate(d.getUTCDate() - (period === '1w' ? 7 : 14)); return d.toISOString().slice(0, 10); }
    const day = d.getUTCDate(); d.setUTCDate(1); d.setUTCMonth(d.getUTCMonth() - MONTHS[period]);       // fin de mois : 31 mars − 1 mois = 28 février, jamais 3 mars
    d.setUTCDate(Math.min(day, new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate()));
    return d.toISOString().slice(0, 10);
  }
  /** Fenêtre d'analyse : i0 = indice de référence (état de clôture à la veille du début, −1 = avant le premier point), i1 = dernier point.
   *  `zoom` = {from, to} (dates) remplace la période prédéfinie. */
  function resolveWindow(H, period, zoom) {
    const n = H.dates.length;
    if (!n) return { i0: -1, i1: -1, empty: true, period, clipped: false };
    let i1 = n - 1, i0, clipped = false, from;
    if (zoom && zoom.from && zoom.to) {
      i1 = lastIdx(H.dates, zoom.to); i0 = lastIdx(H.dates, zoom.from) - 1; if (i0 < -1) i0 = -1;
      if (i1 < 0) return { i0: -1, i1: -1, empty: true, period: 'zoom', clipped: false };
      return { i0, i1, period: 'zoom', zoom: true, startDate: H.dates[Math.max(0, i0 + 1)], endDate: H.dates[i1], clipped: false };
    }
    if (period === 'all' || period === 'max') i0 = -1;
    else if (SESSIONS[period]) { i0 = i1 - SESSIONS[period]; if (i0 < 0) { i0 = -1; clipped = true; } }
    else {
      from = shift(H.dates[i1], period); i0 = lastIdx(H.dates, from);
      if (i0 < 0 || H.dates[0] > from) { i0 = -1; clipped = H.dates[0] > from; }
    }
    return { i0, i1, period, startDate: H.dates[Math.max(0, i0 + 1)], endDate: H.dates[i1], clipped, from };
  }
  function lastIdx(dates, d) { let r = -1; for (let i = 0; i < dates.length; i++) { if (dates[i] <= d) r = i; else break; } return r; }
  /** Dernier indice ≤ i où la série a une valeur (les trous ne sont jamais comblés : on signale l'écart). */
  function validAtOrBefore(a, i) { for (let k = i; k >= 0; k--) if (isNum(a[k])) return k; return -2; }

  /** Résultat et performance du portefeuille sur la fenêtre. */
  function portfolio(H, w) {
    const out = { result: null, base: null, pct: null, pctReason: null, startValue: 0, endValue: null, flows: null, purchases: null, endIndex: w.i1, approxEnd: false };
    if (w.empty) return out;
    let e = w.i1; if (!isNum(H.gain[e])) { e = validAtOrBefore(H.gain, e); out.approxEnd = e >= 0; }
    if (e < 0) return Object.assign(out, { pctReason: 'Valorisation indisponible : cours ou change manquants.' });
    out.endIndex = e; out.endValue = H.value[e];
    const g0 = w.i0 < 0 ? 0 : H.gain[w.i0];
    if (!isNum(g0)) return Object.assign(out, { pctReason: 'Valorisation de départ indisponible (cours manquant à cette date).' });
    out.result = H.gain[e] - g0;
    out.startValue = w.i0 < 0 ? 0 : (isNum(H.value[w.i0]) ? H.value[w.i0] : null);
    out.purchases = at(H.purchases, e) - at(H.purchases, w.i0);
    out.flows = at(H.net_in, e) - at(H.net_in, w.i0);
    out.base = (out.startValue || 0) + out.purchases;
    // performance hors mouvements : produit des facteurs de la fenêtre
    const f = (H.performance && H.performance.factors) || [];
    let prod = 1, ok = true, miss = null, count = 0;
    for (let k = w.i0 + 1; k <= e; k++) {
      if (!isNum(f[k])) { ok = false; miss = H.dates[k]; break; }
      prod *= f[k]; count++;
    }
    if (ok && count > 0) out.pct = 100 * (prod - 1);
    else if (!ok) out.pctReason = 'Performance hors mouvements indisponible : jour sans valorisation fiable (' + miss + ').';
    else out.pctReason = 'Période trop courte pour une performance.';
    return out;
  }

  /** Résultat d'une position sur la fenêtre. */
  function position(H, line, w, hist) {
    const out = { result: null, base: null, pct: null, startValue: null, endValue: null, purchases: null, sinceBuy: null, sinceBuyPct: null, firstIdx: null, reason: null };
    const vals = line.values, gains = line.gain;
    let e = w.i1; if (!isNum(gains[e])) e = validAtOrBefore(gains, e);
    if (e < 0) { out.reason = reasonFor(H, line); return out; }
    const first = firstActive(line);
    out.firstIdx = first;
    const g0 = w.i0 < 0 ? 0 : gains[w.i0];
    if (!isNum(g0)) { out.reason = 'Valorisation de départ indisponible (cours manquant à la date de référence).'; return out; }
    out.result = gains[e] - g0;
    out.startValue = w.i0 < 0 ? 0 : vals[w.i0];
    out.endValue = vals[e];
    out.purchases = at(line.purchases, e) - at(line.purchases, w.i0);
    out.base = (out.startValue || 0) + out.purchases;
    out.pct = out.base > 1e-9 ? 100 * out.result / out.base : null;
    out.sinceBuy = gains[e];
    out.sinceBuyPct = line.purchases[e] > 1e-9 ? 100 * gains[e] / line.purchases[e] : null;
    return out;
  }
  function firstActive(line) { for (let i = 0; i < line.purchases.length; i++) if (line.purchases[i] > 0) return i; return null; }
  function reasonFor(H, line) {
    const miss = [], vals = line.values;
    for (let i = 0; i < vals.length; i++) if (vals[i] === null) miss.push(H.dates[i]);
    if (!miss.length) return 'Aucune donnée sur la période.';
    return 'Cours ou change manquants du ' + miss[0] + ' au ' + miss[miss.length - 1] + ' (' + miss.length + ' date' + (miss.length > 1 ? 's' : '') + '), sans estimation possible.';
  }

  /** Contribution en points de la position au résultat du portefeuille. */
  function contribution(posRes, pf) { return isNum(posRes.result) && pf.base > 1e-9 ? 100 * posRes.result / pf.base : null; }

  /** Cours de marché ramené sur les dates de l'historique (dernier cours connu, jamais d'interpolation). */
  function marketOnDates(H, key) {
    const m = H.market; if (!m || !m.lines) return null;
    const ln = m.lines.find(l => l.key === key); if (!ln) return null;
    const out = []; let j = 0, last = null;
    for (const d of H.dates) { while (j < m.dates.length && m.dates[j].slice(0, 10) <= d) { if (isNum(ln.prices[j])) last = ln.prices[j]; j++; } out.push(last); }
    return out;
  }

  /** Série d'une courbe sur la fenêtre. metric : 'result' | 'value' (€) ; 'perf' | 'market' (%).
   *  Renvoie {x: dates, y: valeurs|null, note}. Le portefeuille (key 'pf') utilise les facteurs Dietz en mode %. */
  function series(H, w, key, metric) {
    const xs = [], ys = []; let note = null;
    const start = Math.max(0, w.i0 + 1);
    const line = key === 'pf' ? null : H.lines.find(l => l.key === key);
    if (key !== 'pf' && !line) return { x: xs, y: ys, note: 'Série inconnue' };
    const include = start - 1 >= 0 ? start - 1 : null;              // point de référence (ligne zéro) = clôture précédant la fenêtre
    const idxs = []; if (include !== null) idxs.push(include); for (let i = start; i <= w.i1; i++) idxs.push(i);
    let mk = null; if (metric === 'market') { mk = marketOnDates(H, key); if (!mk) return { x: xs, y: ys, note: 'Cours de marché indisponible' }; }
    let chain = 1, broken = false, refGain = null, refPur = null, refVal = null, refPrice = null;
    const f = (H.performance && H.performance.factors) || [];
    for (const i of idxs) {
      let y = null;
      const isRef = i === include;
      if (key === 'pf') {
        if (metric === 'value') y = H.value[i];
        else if (metric === 'result') { if (isRef) refGain = H.gain[i]; y = isNum(H.gain[i]) && isNum(refGain ?? 0) ? H.gain[i] - (refGain ?? 0) : null; }
        else {                                              // perf hors mouvements
          if (isRef) { y = 0; }
          else if (!broken && isNum(f[i])) { chain *= f[i]; y = 100 * (chain - 1); }
          else { if (!broken) note = 'Performance interrompue à partir du ' + H.dates[i] + ' (jour sans valorisation fiable).'; broken = true; y = null; }
        }
      } else {
        if (metric === 'value') y = line.values[i];
        else if (metric === 'result') { if (isRef) refGain = line.gain[i]; y = isNum(line.gain[i]) ? line.gain[i] - (refGain ?? 0) : null; }
        else if (metric === 'perf') {
          if (isRef) { refGain = line.gain[i]; refPur = line.purchases[i]; refVal = line.values[i]; y = 0; }
          else { const base = (refVal || 0) + (line.purchases[i] - (refPur || 0)); y = isNum(line.gain[i]) && base > 1e-9 ? 100 * (line.gain[i] - (refGain || 0)) / base : null; }
        } else {                                            // cours de marché rebasé
          const p = mk[i]; if (refPrice === null && isNum(p) && (include === null || isRef || line.quantities[i] > 0 || line.purchases[i] > 0)) refPrice = p;
          y = isNum(p) && refPrice ? 100 * (p / refPrice - 1) : null;
        }
      }
      xs.push(H.dates[i]); ys.push(isNum(y) ? y : null);
    }
    // une position n'existe qu'après son premier achat : avant, aucune courbe (pas de zéro trompeur)
    if (line) { const fa = firstActive(line); for (let k = 0; k < xs.length; k++) if (fa === null || idxs[k] < fa) ys[k] = null; }
    return { x: xs, y: ys, note };
  }

  /** Recul depuis le plus haut cours observé depuis le premier achat. */
  function drawdownFromHigh(H, line) {
    const pr = marketOnDates(H, line.key); if (!pr) return null;
    const fa = firstActive(line); if (fa === null) return null;
    let hi = null, last = null;
    for (let i = fa; i < pr.length; i++) if (isNum(pr[i])) { hi = hi === null ? pr[i] : Math.max(hi, pr[i]); last = pr[i]; }
    return hi && last ? 100 * (last / hi - 1) : null;
  }
  /** Plus haut résultat personnel observé et recul depuis ce maximum (€ et points de gain). */
  function personalPeak(line) {
    let peak = null, idx = null; line.gain.forEach((g, i) => { if (isNum(g) && (peak === null || g > peak)) { peak = g; idx = i; } });
    let last = null; for (let i = line.gain.length - 1; i >= 0; i--) if (isNum(line.gain[i])) { last = line.gain[i]; break; }
    return { peak, idx, last, drop: peak !== null && last !== null ? last - peak : null };
  }
  /** Compte de titres distincts (jamais de lots). */
  function countTitles(rows) { return new Set(rows.map(r => r.key)).size; }

  const api = { PERIODS, resolveWindow, portfolio, position, contribution, series, drawdownFromHigh, personalPeak, marketOnDates, firstActive, reasonFor, countTitles, isNum };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.PFM = api;
})(typeof window !== 'undefined' ? window : globalThis);
