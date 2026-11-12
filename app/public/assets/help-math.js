/* Calculs pédagogiques de l'aide : reproduction fidèle (JavaScript) des mesures et des scores du moteur Python (engine/analytics/series/measures.py, score_inputs.py, scores.py).
   Aucune donnée réelle ni aucun réglage de l'utilisateur n'est lu ni modifié : tout travaille sur des exemples fictifs.
   Un test (tests/fast/test_help_math.py) compare ces fonctions au moteur Python sur plusieurs cas : toute divergence fait échouer le test. */
(function (root) {
  'use strict';
  const clamp = (x, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, x));
  const SAT_A = 17, SAT_B = 0.52, GATE_FLOOR = 32, RELIABILITY = 21, KAPPA = 0.7;
  const SESSIONS = { day: 1, week: 5, month: 21, quarter: 63, half: 126, year: 252 };
  const LABELS = { day: 'Jour', week: 'Semaine', month: 'Mois', quarter: 'Trimestre', half: 'Semestre', year: 'Année' };
  const COMPLEX_DEFAULT = { dynamics: 40, r2: 15, up_days: 5, concentration: 7, volatility: 15, drawdown: 8, liquidity: 10 };

  /** Mesures d'une fenêtre de n+1 clôtures (mêmes formules que measures.window_metrics). */
  function metrics(closes) {
    const n = closes.length - 1;
    if (n < 2 || closes.some(c => !(c > 0))) return null;
    const logs = closes.map(Math.log), steps = [];
    for (let i = 0; i < n; i++) steps.push(logs[i + 1] - logs[i]);
    let peak = closes[0], worst = 0;
    for (const c of closes) { peak = Math.max(peak, c); worst = Math.max(worst, 1 - c / peak); }
    const meanT = n / 2, meanY = logs.reduce((a, b) => a + b, 0) / (n + 1);
    let sxx = 0, sxy = 0, syy = 0;
    logs.forEach((y, t) => { sxx += (t - meanT) ** 2; sxy += (t - meanT) * (y - meanY); syy += (y - meanY) ** 2; });
    const b = sxy / sxx, a = meanY - b * meanT;
    const out = { sessions: n, perf: 100 * Math.expm1(logs[n] - logs[0]), slope: 100 * Math.expm1(b), r2: syy === 0 ? 1 : Math.min(1, (sxy * sxy) / (sxx * syy)), volatility: null, drawdown: 100 * worst, intercept: a, slope_log: b };
    if (n >= 3) { const m = steps.reduce((x, y) => x + y, 0) / n; out.volatility = 100 * Math.sqrt(steps.reduce((x, s) => x + (s - m) ** 2, 0) / (n - 1)); }
    return out;
  }
  /** Part des séances en hausse et poids de la meilleure séance dans la hausse totale (score_inputs.path_inputs). */
  function pathInputs(closes) {
    if (closes.length < 3) return { up_fraction: null, spike_share: null };
    const steps = []; for (let i = 1; i < closes.length; i++) steps.push(closes[i] / closes[i - 1] - 1);
    const total = Math.log(closes[closes.length - 1] / closes[0]);
    return { up_fraction: steps.filter(s => s > 0).length / steps.length, spike_share: total > 0 ? Math.log1p(Math.max(...steps)) / total : 1 };
  }
  /** Mesures complètes de la dernière fenêtre de n séances d'une série. */
  function windowOf(closes, n) { const w = closes.slice(closes.length - 1 - n); const m = metrics(w); return m ? Object.assign(m, pathInputs(w)) : null; }

  const saturation = (n, a = SAT_A) => a * Math.pow(n / 5, SAT_B);
  const growth = (slope, n) => slope <= -100 ? -100 : 100 * Math.expm1(n * Math.log1p(slope / 100));
  function liquidityNote(eur) { if (eur == null || !(eur >= 0)) return null; if (eur === 0) return 0; return 100 * clamp(Math.log10(Math.max(eur, 1) / 2e6) / Math.log10(50e6 / 2e6)); }
  /** Notes 0-100 d'une période (scores.period_components, hors jour et accélération). */
  function components(m, n, satA = SAT_A) {
    if (!m || m.slope == null || n < 3) return null;
    const g = growth(m.slope, n), dyn = 100 * clamp(g / saturation(n, satA));
    return { growth: g, dynamics: dyn, gate: clamp(dyn / GATE_FLOOR), r2: 100 * clamp((m.r2 - 0.5) / 0.45), up_days: 100 * clamp((m.up_fraction - 0.4) / 0.4),
      concentration: 100 * clamp((0.60 - m.spike_share) / 0.50), volatility: 100 * clamp((5 - m.volatility) / 4), drawdown: 100 * clamp((15 - m.drawdown) / 15), raw: m };
  }
  /** Poids automatiques des durées (scores.auto_weights). */
  function autoWeights(ids, kappa = KAPPA) {
    const ns = ids.map(i => SESSIONS[i]).sort((a, b) => a - b); let prev = 1; const raw = {};
    ns.forEach(n => { raw[n] = Math.max(Math.pow(n, 1 - kappa) - Math.pow(prev, 1 - kappa), 1e-12); prev = n; });
    const tot = Object.values(raw).reduce((a, b) => a + b, 0), out = {};
    ids.forEach(i => { out[i] = raw[SESSIONS[i]] / tot; });
    return out;
  }
  /** Score simple = 100 × Dynamique × Régularité (scores._simple). periods : [{id, comp}], weights : {id: poids qui somment à 1}. */
  function simple(periods, weights) {
    let D = 0, num = 0, den = 0;
    for (const p of periods) { const w = weights[p.id] || 0; if (!p.comp || w <= 0) continue; D += w * p.comp.dynamics / 100; const rel = Math.min(1, SESSIONS[p.id] / RELIABILITY); num += w * rel * Math.max(p.comp.raw.r2, 0); den += w * rel; }
    if (den <= 0) return { score: null };
    const Q = num / den; return { score: Math.min(100, 100 * D * Q), dynamics: D, quality: Q };
  }
  /** Score complexe (scores._complex) : moyenne pondérée des notes, composantes liquidité par titre, ancrage récent. */
  function complex(periods, weights, cw, liquidity, anchor = 0.5) {
    const avail = periods.filter(p => p.comp && (weights[p.id] || 0) > 0), wtot = avail.reduce((a, p) => a + weights[p.id], 0);
    if (!avail.length) return { score: null };
    const eff = {}; avail.forEach(p => { eff[p.id] = weights[p.id] / wtot; });
    const wsum = Object.values(cw).reduce((a, b) => a + b, 0) || 1; let total = 0, availW = 0; const contrib = {};
    for (const [key, weight] of Object.entries(cw)) {
      if (!(weight > 0)) continue; const w = weight / wsum;
      if (key === 'liquidity') { if (liquidity != null) { total += w * liquidity / 100; availW += w; contrib[key] = { weight: w, value: liquidity }; } continue; }
      let s = 0, cv = 0;
      for (const p of avail) { const v = p.comp[key]; if (v == null) continue; const gate = key === 'dynamics' ? 1 : p.comp.gate; s += eff[p.id] * gate * v; cv += eff[p.id]; }
      if (cv <= 0) continue; s /= cv; total += w * s / 100; availW += w; contrib[key] = { weight: w, value: s };
    }
    if (availW <= 1e-12) return { score: null };
    const base = total / availW, shortest = avail.slice().sort((a, b) => SESSIONS[a.id] - SESSIONS[b.id])[0], mult = 1 - anchor * (1 - shortest.comp.gate);
    Object.values(contrib).forEach(c => { c.share = c.weight / availW; });
    return { score: 100 * base * mult, raw: 100 * base, anchor: mult, contrib };
  }
  /** Évalue un titre : mesures par durée, notes, scores. title : {closes, liquidity}. ids : durées actives. */
  function evaluate(title, ids, opts) {
    const o = Object.assign({ kappa: KAPPA, anchor: 0.5, cw: COMPLEX_DEFAULT, satA: SAT_A, weights: null }, opts || {});
    const weights = o.weights || autoWeights(ids, o.kappa);
    const periods = ids.map(id => { const m = windowOf(title.closes, SESSIONS[id]); return { id, m, comp: components(m, SESSIONS[id], o.satA) }; });
    const liq = liquidityNote(title.liquidity);
    return { periods, weights, liquidity: liq, simple: simple(periods, weights), complex: complex(periods, weights, o.cw, liq, o.anchor) };
  }
  /** Rangs (rang = 1 + nombre de scores strictement plus grands ; ex æquo partagent le rang). */
  function ranks(scores) { const out = {}; for (const [k, v] of Object.entries(scores)) out[k] = v == null ? null : 1 + Object.values(scores).filter(x => x != null && x > v).length; return out; }

  /** Série fictive déterministe : log-cours = départ + pente·t + amplitude·sin(2π·cycles·t/N) ; mêmes extrémités quelle que soit l'amplitude. */
  function series(n, totalPct, amp, cycles, start = 100, noise = 0, seed = 1) {
    const out = []; let s = seed * 9301 + 49297;
    const rnd = () => { s = (s * 9301 + 49297) % 233280; return s / 233280 - 0.5; };
    const b = Math.log(1 + totalPct / 100) / n;
    for (let t = 0; t <= n; t++) out.push(start * Math.exp(b * t + amp * Math.sin(2 * Math.PI * cycles * t / n) + (t === 0 || t === n ? 0 : noise * rnd())));
    return out;
  }
  /** Série en tronçons : points [[séance, cours]] reliés linéairement en log (pour illustrer un comportement). */
  function path(points, noise = 0, seed = 3) {
    const out = []; let s = seed * 7919 + 13;
    const rnd = () => { s = (s * 9301 + 49297) % 233280; return s / 233280 - 0.5; };
    for (let i = 0; i < points.length - 1; i++) { const [t0, p0] = points[i], [t1, p1] = points[i + 1]; for (let t = t0; t < t1; t++) { const f = (t - t0) / (t1 - t0); out.push(p0 * Math.pow(p1 / p0, f) * (1 + (t === 0 ? 0 : noise * rnd()))); } }
    out.push(points[points.length - 1][1]); return out;
  }
  /** FIFO : lots d'achat [{qty, price}] puis ventes [{qty, price}] → lots restants, gain réalisé, prix de revient. */
  function fifo(buys, sells) {
    const lots = buys.map(b => ({ qty: b.qty, price: b.price, left: b.qty })); let realized = 0; const detail = [];
    for (const s of sells) { let need = s.qty; for (const l of lots) { if (need <= 0) break; const take = Math.min(l.left, need); if (take > 0) { l.left -= take; need -= take; const g = take * (s.price - l.price); realized += g; detail.push({ take, from: l.price, to: s.price, gain: g }); } } if (need > 1e-9) return { error: 'vente sans achat connu' }; }
    const rest = lots.filter(l => l.left > 1e-9), qty = rest.reduce((a, l) => a + l.left, 0), cost = rest.reduce((a, l) => a + l.left * l.price, 0);
    return { lots, rest, qty, cost, avg: qty ? cost / qty : null, realized, detail };
  }
  /** Modified Dietz sur une période : gain / (capital de départ + apports pondérés par le temps restant). */
  function dietz(start, end, flows) { const gain = end - start - flows.reduce((a, f) => a + f.amount, 0); const den = start + flows.reduce((a, f) => a + f.amount * (1 - f.t), 0); return { gain, den, perf: den > 0 ? 100 * gain / den : null }; }

  const api = { clamp, SESSIONS, LABELS, COMPLEX_DEFAULT, metrics, pathInputs, windowOf, saturation, growth, liquidityNote, components, autoWeights, simple, complex, evaluate, ranks, series, path, fifo, dietz };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.HM = api;
})(typeof window !== 'undefined' ? window : globalThis);
