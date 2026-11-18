/* Portefeuille avec liquidités : cartes de bilan, graphique unique (deux vues, trois modes) et tableau des positions clôturées.
   Uniquement pour les portefeuilles à liquidités ; les portefeuilles « ancien modèle » gardent leur affichage (pf-home.js).
   Aucun calcul financier ici : tout vient de portfolio/performance (engine/analytics/portfolio/cash_performance.py, adaptateur series/cash_history.py).
   Le graphique réutilise J.financialChart, les classes px-* et le tableau J.table de l'ensemble du site. */
(function (root) {
  "use strict";
  const PFM = root.PFM,
    esc = J.esc,
    isNum = (v) => typeof v === "number" && isFinite(v);
  const sg = (v) => J.eurS(v),
    cl = (v) => (isNum(v) ? (v > 0.004 ? "up" : v < -0.004 ? "down" : "") : ""),
    pc = (v, d = 2) => (isNum(v) ? J.pctS(v * 100, d) : "–");
  const cache = new Map();
  const last = (a) => {
    for (let i = (a || []).length - 1; i >= 0; i--) if (isNum(a[i])) return a[i];
    return null;
  };

  /** Données du portefeuille (une requête par version : la version change à chaque opération ou mouvement d'argent). */
  function load(id, version) {
    const key = id + "|" + version;
    if (!cache.has(key))
      cache.set(
        key,
        J.api("portfolio/performance", { params: { id } }).catch((e) => {
          cache.delete(key);
          throw e;
        }),
      );
    return cache.get(key);
  }
  const usable = (P) => !!(P && P.model === "cash" && P.days && P.days.length && P.chart);

  /* ───────── « Mon argent » : chiffres du bilan (composant .metric du site) ───────── */
  const metric = (label, value, sub, tone = "") =>
    `<div class="metric"><span class="l">${label}</span><div class="v ${tone}">${value}</div><span class="s">${sub}</span></div>`;
  function money(P, tax) {
    const F = P.chart.full,
      s = P.summary || {},
      value = last(F.value),
      cash = last(F.cash),
      sec = last(F.securities),
      gain = last(F.gain),
      real = last(F.realized),
      lat = last(F.latent),
      c = last(F.twr.central),
      lo = last(F.twr.low),
      hi = last(F.twr.high),
      est = F.estimated.filter(Boolean).length,
      mwr = P.mwr && isNum(P.mwr.period) ? P.mwr.period : null,
      cap = last(P.net_contributions),
      net = isNum(gain) ? gain - tax.inc - tax.soc : null,
      taxTotal = tax.inc + tax.soc;
    const share =
      isNum(cash) && isNum(value) && value > 0
        ? J.num((100 * cash) / value, 1) + " % du portefeuille"
        : "Argent non investi";
    const perf = `${pc(c)} ${J.badge("TWR", "info", { sm: true, title: "Rendement pondéré par le temps : les dépôts et retraits sont neutralisés" })} ${J.badge(est ? "estimé" : "exact", est ? "warn" : "ok", { sm: true, title: est ? "Un jour comporte un apport dont l’heure par rapport aux cours est inconnue : le pourcentage est encadré" : "Tous les jours sont calculables exactement" })}`;
    const perfSub = est
      ? `Entre ${pc(lo)} et ${pc(hi)} selon l’heure des apports`
      : mwr !== null
        ? `Euros investis : ${pc(mwr)}`
        : "Rendement pondéré par le temps";
    const parts = [
      ["Capital initial", s.initial_capital],
      ["Dépôts", s.deposit],
      ["Retraits", s.withdrawal],
      ["Dividendes", s.dividend],
      ["Frais de compte", s.fee],
    ];
    return `<section class="px-card"><h2>Mon argent</h2><p class="small muted">Bilan global de ce portefeuille, toutes opérations comprises.</p>
      <div class="pf-kpis">${metric("Capital net apporté", J.eur(cap), "Capital initial + dépôts − retraits externes")}${metric("Liquidités", J.eur(cash), share)}${metric("Valeur des actions", J.eur(sec), "Valeur de marché des positions détenues")}${metric("Gain total", sg(gain), `${isNum(gain) && cap > 0 ? pc(gain / cap) : "—"} · rendement simple sur le capital net apporté`, cl(gain))}</div><p class="small muted">Valeur totale : ${J.eur(value)} · ${perf} · ${perfSub}</p>
      <dl class="px-kv"><div><dt>Gains réalisés</dt><dd class="${cl(real)}">${sg(real)}</dd></div><div><dt>Gains latents</dt><dd class="${cl(lat)}">${sg(lat)}</dd></div><div><dt>Impôts estimés</dt><dd class="down">−${J.eur(taxTotal)}</dd></div><div><dt>Résultat net</dt><dd class="${cl(net)}">${sg(net)}${isNum(net) && cap > 0 ? ` (${pc(net / cap)})` : ""}</dd></div></dl>
      <details class="px-meta"><summary>Capital, mouvements d’argent et méthode de calcul</summary>
      <ul>${parts.map(([l, v]) => `<li>${l} : <b>${J.eur(v || 0)}</b></li>`).join("")}</ul>
      <p>Gain total = liquidités + valeur des actions − capital net apporté. Le rendement simple = gain total / capital net apporté (indisponible si ce capital est nul ou négatif) ; il ne neutralise pas la date des apports et ne remplace pas le TWR. Les ventes ne sont pas des retraits externes.</p><p>Chaque jour, la valeur du portefeuille (liquidités comprises) est comparée à celle de la veille. Les <b>achats et ventes</b> ne sont jamais des apports : l’argent reste dans le portefeuille. Seuls les <b>dépôts et retraits</b> sont neutralisés. C’est le <b>TWR</b>.</p>
      <p>Un jour sans dépôt ni retrait est exact. Un jour avec dépôt ou retrait est une <b>estimation encadrée</b> : l’heure exacte par rapport aux cours du jour est inconnue. Le <b>gain en euros</b> n’a aucune incertitude ; seul le pourcentage en a une.</p>
      <p>Les impôts sont une estimation indicative (PFU 30 %, compte-titres) : hors PEA, reports de pertes, dividendes et situation personnelle.</p>
      ${(P.notes || []).map((n) => `<p class="small muted">${esc(n)}</p>`).join("")}</details></section>`;
  }

  /* ───────── graphique ───────── */
  const VIEWS = [
    ["full", "Portefeuille complet"],
    ["open", "Positions actuelles"],
  ];
  const MODES = [
    ["value", "Valeur"],
    ["perf", "Performance"],
    ["gain", "Gains"],
    ["market", "Cours"],
  ];
  const UNITS = [
    ["pct", "%"],
    ["eur", "€"],
  ];
  const ST = {
    // réglages remis à zéro à chaque chargement de la page (rien n'est mémorisé)
    view: "full",
    mode: "value",
    per: "all",
    unit: "pct",
    marks: true,
    zero: false,
    token: 0,
    shown: null,
    vis: {},
  };
  const sym = (P, k) => (P.symbols && P.symbols[k]) || (P.positions[k] && P.positions[k].name) || k;
  const color = (P, k) => `var(--series-${(Object.keys(P.positions).indexOf(k) % 12) + 1})`;

  /** Fenêtre de la période : indices à tracer (point de référence = clôture précédant la fenêtre, base 0 des courbes cumulées). */
  function window_(P, per) {
    const w = PFM.resolveWindow({ dates: P.days }, per),
      from = Math.max(0, w.i0 + 1),
      idx = [];
    const ref = w.i0 >= 0 ? w.i0 : null;
    if (ref !== null) idx.push(ref);
    for (let i = from; i <= w.i1; i++) idx.push(i);
    return { idx, ref, w };
  }
  /** Cumul rebasé : écart au point de référence (valeurs additives : gains, contributions). */
  const diff = (a, win) => win.idx.map((i) => (isNum(a[i]) ? a[i] - (win.ref === null ? 0 : (a[win.ref] ?? 0)) : null));
  /** Rendement rebasé : (1+r_i)/(1+r_ref)−1 (rendements cumulés d'une chaîne). */
  const rebase = (a, win) =>
    win.idx.map((i) => {
      if (!isNum(a[i])) return null;
      const b = win.ref === null ? 0 : a[win.ref];
      return isNum(b) || win.ref === null ? (1 + a[i]) / (1 + (b || 0)) - 1 : null;
    });
  const pick = (a, win) => win.idx.map((i) => (isNum(a[i]) ? a[i] : null));
  /** Valeur d'un titre : vide quand il n'est pas détenu (pas de ligne à zéro avant l'achat ni après la vente). */
  const held = (a, win) => win.idx.map((i) => (isNum(a[i]) && a[i] > 1e-9 ? a[i] : null));
  /** Classe de la pastille de légende (couleurs définies dans la feuille de style : c0 = texte, c1…c12 = séries). */
  const swatch = (c) => {
    const m = /series-(\d+)/.exec(c);
    return m ? "c" + m[1] : "c0";
  };
  const eurFmt = (v) => J.eur(v, 2);

  function build(P, st) {
    const C = P.chart,
      V = st.view === "full" ? C.full : C.open,
      win = window_(P, st.per),
      notes = [];
    if (!V)
      return {
        times: [],
        series: [],
        fmt: eurFmt,
        def: "Aucun titre n’est détenu aujourd’hui : cette vue est vide.",
        zero: false,
        notes,
        win,
      };
    const out = [];
    const add = (id, label, values, o = {}) =>
      out.push({
        id: st.view + ":" + st.mode + ":" + id,
        label,
        values,
        color: o.color || "var(--text)",
        width: o.width || 2,
        hide: !!o.hide,
      });
    const keys = st.view === "full" ? Object.keys(C.full.holdings) : V.keys;
    const names = (k) => sym(P, k);
    let fmt = eurFmt,
      def = "",
      zero = false;
    if (st.view === "full" && st.mode === "value") {
      add("value", "Valeur totale", pick(V.value, win), { width: 2.6 });
      add("sec", "Titres", pick(V.securities, win), { color: "var(--series-2)" });
      add("cash", "Liquidités", pick(V.cash, win), { color: "var(--series-5)" });
      keys.forEach((k) => add("k" + k, names(k), held(V.holdings[k].value, win), { color: color(P, k) }));
      def =
        "Valeur du portefeuille en euros : titres et liquidités. Les courbes de chaque titre sont masquées : cliquez une pastille pour les afficher.";
    } else if (st.view === "full" && st.mode === "perf") {
      zero = true;
      fmt = (v) => J.numS(v, 2) + " pt";
      add(
        "twr",
        "Performance globale",
        rebase(V.twr.central, win).map((v) => (v === null ? null : v * 100)),
        { width: 2.6 },
      );
      keys.forEach((k) =>
        add(
          "k" + k,
          names(k),
          diff(V.holdings[k].contribution, win).map((v) => (v === null ? null : v * 100)),
          { color: color(P, k) },
        ),
      );
      if (isNum(last(V.fees_contribution || [])) && Math.abs(last(V.fees_contribution)) > 1e-9)
        add(
          "fees",
          "Frais de compte",
          diff(V.fees_contribution, win).map((v) => (v === null ? null : v * 100)),
          { color: "var(--series-12)" },
        );
      def =
        "Performance (en points de %) : la courbe épaisse est la performance globale (TWR, liquidités comprises) ; chaque autre courbe est la contribution du titre, en points de cette performance. Les contributions se somment ; les rendements des titres ne se somment pas.";
      if (win.ref !== null)
        notes.push(
          "Sur une sous-période, une contribution est l’écart de contribution cumulée : leur somme approche le rendement de la période sans l’égaler exactement.",
        );
    } else if (st.view === "full") {
      zero = true;
      add("gain", "Gain total", diff(V.gain, win), { width: 2.6 });
      add("real", "Gains réalisés", diff(V.realized, win), { color: "var(--series-3)" });
      add("lat", "Gains latents", pick(V.latent, win), { color: "var(--series-4)" });
      keys.forEach((k) => add("k" + k, names(k), diff(V.holdings[k].gain, win), { color: color(P, k) }));
      def =
        "Gains en euros : total = réalisés (titres vendus, conservés après la vente) + latents (titres encore détenus). Les gains par titre sont masqués par défaut.";
    } else if (st.mode === "value") {
      add("value", "Positions actuelles", pick(V.value, win), { width: 2.6 });
      keys.forEach((k) => add("k" + k, names(k), held(V.holdings[k].value, win), { color: color(P, k) }));
      def =
        "Valeur de marché des seuls titres encore détenus aujourd’hui, en euros. Aucun titre vendu, aucune liquidité.";
    } else if (st.mode === "perf") {
      zero = true;
      fmt = (v) => J.pctS(v, 2);
      add(
        "twr",
        "Positions actuelles (agrégé)",
        rebase(V.twr.central, win).map((v) => (v === null ? null : v * 100)),
        { width: 2.6 },
      );
      keys.forEach((k) =>
        add(
          "k" + k,
          names(k),
          rebase(V.holdings[k].twr, win).map((v) => (v === null ? null : v * 100)),
          { color: color(P, k) },
        ),
      );
      def =
        "Performance en % : la courbe épaisse est la performance agrégée des titres encore détenus (TWR du sous-portefeuille, hors liquidités et titres vendus). Chaque autre courbe est le rendement du titre depuis son achat : ces rendements ne s’additionnent pas.";
    } else {
      zero = true;
      add("gain", "Gain des positions actuelles", diff(V.gain, win), { width: 2.6 });
      add("real", "dont réalisé (ventes partielles)", diff(V.realized, win), { color: "var(--series-3)" });
      add("lat", "dont latent (quantités détenues)", pick(V.latent, win), { color: "var(--series-4)" });
      keys.forEach((k) => add("k" + k, names(k), diff(V.holdings[k].gain, win), { color: color(P, k) }));
      def =
        "Gains en euros des titres encore détenus : ce qui est déjà encaissé sur des ventes partielles, et le latent sur les quantités conservées.";
    }
    if (V.estimated.slice(win.ref === null ? 0 : win.ref).some(Boolean) && st.mode === "perf")
      notes.push(
        "Certains jours sont estimés (apport ou achat en cours de journée) : le pourcentage est encadré, le gain en euros reste exact.",
      );
    return { times: win.idx.map((i) => P.days[i]), series: out, fmt, def, zero, notes, win, time: false };
  }

  /** Repères d'achat et de vente de la fenêtre affichée (tous les titres de la vue) ; l'heure est conservée en séance. */
  function markers(P, st, out, keys) {
    if (!ST.marks || !out.times.length) return [];
    const a = String(out.times[0]).slice(0, 10),
      b = String(out.times[out.times.length - 1]).slice(0, 10);
    return (P.trades || [])
      .filter((t) => {
        const d = String(t.at).slice(0, 10);
        return d >= a && d <= b && keys.has(t.key);
      })
      .map((t) => ({
        x: out.time ? String(t.at).replace(" ", "T") : String(t.at).slice(0, 10),
        kind: t.kind === "sell" ? "sell" : "buy",
        key: t.key,
        symbol: t.symbol || t.key,
        id: t.id,
        label: (t.kind === "sell" ? "Vente " : "Achat ") + (t.symbol || t.key),
        detail:
          J.num(t.qty, 4) +
          " × " +
          J.num(t.price, 4) +
          " €" +
          (t.kind === "sell" && isNum(t.realized) ? " — gain réalisé " + sg(t.realized) : ""),
      }));
  }

  /** Titres de la vue (clés de listing) : tous pour le portefeuille complet, les titres détenus pour les positions actuelles. */
  const viewKeys = (P, st) =>
    new Set(st.view === "full" ? Object.keys(P.chart.full.holdings) : P.chart.open ? P.chart.open.keys : []);

  /** Titres dont on affiche les repères : ceux dont la courbe est visible ; si seules des courbes globales sont affichées, tous les titres de la vue (dans tous les modes). */
  const vkey = (s) => String(s.id).split(":").pop();
  function shownKeys(P, st, vis) {
    const all = viewKeys(P, st),
      own = vis
        .map((s) => vkey(s))
        .filter((k) => k[0] === "k" && all.has(k.slice(1)))
        .map((k) => k.slice(1));
    return own.length ? new Set(own) : all;
  }

  function side(P) {
    const F = P.chart.full,
      n = F.gain.length,
      day = n > 1 && isNum(F.gain[n - 1]) && isNum(F.gain[n - 2]) ? F.gain[n - 1] - F.gain[n - 2] : null,
      dayPct =
        n > 1 && isNum(F.twr.central[n - 1]) && isNum(F.twr.central[n - 2])
          ? (1 + F.twr.central[n - 1]) / (1 + F.twr.central[n - 2]) - 1
          : null;
    const ps = Object.keys(P.positions).map((k) => ({ k, p: P.positions[k] }));
    const sales = (P.trades || [])
        .filter((t) => t.kind === "sell" && isNum(t.realized))
        .sort((a, b) => b.realized - a.realized),
      weak = ps
        .filter((x) => x.p.status === "open" && isNum(x.p.gain_total))
        .sort((a, b) => a.p.gain_total - b.p.gain_total)[0];
    const line = (g, r) => `${sg(g)} (${pc(r)})`;
    return `<div class="pf-side">${metric("Depuis le début", line(last(F.gain), last(F.twr.central)), "Gain total et performance", cl(last(F.gain)))}${metric("Dernière séance", day === null ? "–" : line(day, dayPct), "Variation de la valeur totale", cl(day))}${sales[0] ? metric("Meilleure vente", `${esc(sales[0].symbol || "")} ${sg(sales[0].realized)}`, "Gain réalisé", cl(sales[0].realized)) : ""}${weak ? metric("Position la plus faible", `${esc(sym(P, weak.k))} ${line(weak.p.gain_total, weak.p.twr)}`, "Parmi les titres détenus", cl(weak.p.gain_total)) : ""}</div>`;
  }
  function boxHtml(P) {
    return `<section class="px-card" id="pfc-card"><div class="px-ph"><h2>Évolution du portefeuille</h2><div data-k="view">${J.seg(VIEWS, ST.view, "data-v", { label: "Vue du graphique" })}</div></div>
      <div class="px-top"><div data-k="mode">${J.seg(MODES, ST.mode, "data-v", { label: "Type de graphique" })}</div><div data-k="unit" id="pfc-unit" ${ST.mode === "market" ? "" : "hidden"}>${J.seg(UNITS, ST.unit, "data-v", { label: "Unité" })}</div>
      <div class="px-per" data-k="per" role="group" aria-label="Période">${PFM.PERIODS.map(([k, l]) => `<button type="button" data-v="${k}" class="${ST.per === k ? "on" : ""}" aria-pressed="${ST.per === k}">${l}</button>`).join("")}</div></div>
      <div class="pf-evo"><div class="px-box" id="pfc-box"><p class="px-cur" id="pfc-cur"></p><p class="small muted" id="pfc-def"></p><div class="px-plot" id="pfc-plot"></div><div class="px-leg" id="pfc-leg"></div><label class="px-chk"><input type="checkbox" id="pfc-marks" ${ST.marks ? "checked" : ""}> Afficher les achats et les ventes</label> <label class="px-chk"><input type="checkbox" id="pfc-zero" ${ST.zero ? "checked" : ""}> Afficher la ligne 0</label><div id="pfc-notes"></div></div>${side(P)}</div>
      <details class="px-meta"><summary>Comment est calculée la vue « Positions actuelles » ?</summary>
        <p>On reconstitue un <b>sous-portefeuille</b> qui ne contient que les titres encore détenus aujourd’hui, achetés aux mêmes dates, quantités et prix que vos opérations, sans liquidités. Sa performance est un TWR : chaque achat ou vente de ces titres est un apport ou un retrait neutralisé.</p>
        <ul><li><b>Dates d’achat différentes</b> : un titre n’entre dans le calcul qu’à son premier achat ; avant, il ne pèse rien.</li><li><b>Achats supplémentaires</b> : un apport neutralisé, seule la variation de cours sur le capital en place compte.</li><li><b>Ventes partielles</b> : un retrait neutralisé ; le gain déjà encaissé reste dans « dont réalisé », le non encaissé est dans « dont latent ».</li><li><b>Titres entièrement vendus</b> : absents de cette vue.</li></ul>
        <p><b>Analyse rétrospective</b> : cette vue regarde les titres détenus <i>aujourd’hui</i>. Si l’un d’eux est entièrement vendu demain, il disparaîtra aussi de son historique. Ce n’est pas l’historique de ce qui était détenu à chaque date : pour cela, utilisez « Portefeuille complet ».</p>
        <p>Ces pourcentages ne se comparent pas à la performance globale : ni les liquidités ni les titres vendus n’y figurent.</p>
        <p>Le mode « Cours » montre l’historique de cotation des titres (barres de 15 minutes sur les dernières séances), indépendamment de vos achats.</p></details></section>`;
  }

  /** Courbes du mode « Cours » : même source que l'ancien graphique (cotations, barres de 15 minutes), pour les titres de la vue. */
  async function marketOut(P, st) {
    const X = root.PFHomeX,
      keys = (st.view === "full" ? X.all() : X.open()).filter((p) => p.listing_id).map(X.pkey);
    const o = await root.PFHome.build({ mode: "market", per: st.per, unit: st.unit }, { keys, pf: false });
    const pct = st.unit === "pct";
    return {
      times: o.times,
      series: o.series.map((x) => ({ ...x, id: "m:k" + x.id, hide: false })),
      fmt: pct ? (v) => J.pctS(v, 2) : (v) => J.eur(v, 2),
      def:
        "Cours de cotation des titres de la vue" +
        (pct ? " rebasés à 0 % au début de la période" : " convertis en euros") +
        " : ce n’est pas la valeur de vos positions. " +
        (o.ref || ""),
      zero: pct,
      notes: o.meta.notes,
      time: o.intraday,
      win: null,
    };
  }

  async function draw(host, P, hooks) {
    const plot = host.querySelector("#pfc-plot");
    if (!plot) return;
    const st = ST,
      token = ++st.token;
    let out;
    try {
      out = st.mode === "market" ? await marketOut(P, st) : build(P, st);
    } catch (e) {
      if (token !== st.token) return;
      plot._financial && plot._financial.destroy();
      plot.innerHTML = `<div class="notice err">Impossible de charger les données : ${esc(e.message)}</div>`;
      return;
    }
    if (token !== st.token) return;
    // un titre masqué ou affiché l'est dans les quatre onglets ; les courbes globales gardent leur choix propre
    const isTitle = (s) => /^k/.test(vkey(s));
    const hidden = (s) =>
      isTitle(s) && st.shown ? !st.shown.has(vkey(s)) : vkey(s) in st.vis ? st.vis[vkey(s)] : s.hide;
    const vis = out.series.filter((s) => !hidden(s));
    host.querySelector("#pfc-cur").innerHTML =
      `<b>${esc(PFM.PERIODS.find(([k]) => k === st.per)[1])}</b> · ${MODES.find(([k]) => k === st.mode)[1]} · ${VIEWS.find(([k]) => k === st.view)[1]}`;
    host.querySelector("#pfc-def").textContent = out.def;
    const sold = Object.keys(P.positions)
      .filter((k) => P.positions[k].status === "closed")
      .map((k) => sym(P, k));
    host.querySelector("#pfc-notes").innerHTML =
      out.notes.map((n) => `<p class="small muted">${esc(n)}</p>`).join("") +
      (st.view === "full" && sold.length && st.mode !== "market"
        ? `<p class="notice info">Les titres vendus (${esc(sold.join(", "))}) restent dans l’historique et contribuent à la performance globale, mais ne font plus partie des positions actuelles.</p>`
        : "");
    if (!out.times.length || !vis.some((s) => s.values.some(isNum))) {
      plot._financial && plot._financial.destroy();
      plot.innerHTML =
        '<div class="px-empty">Aucune valeur disponible sur cette période pour les courbes affichées.</div>';
    } else {
      if (!plot._financial) plot.innerHTML = "";
      J.financialChart(
        plot,
        { times: out.times, series: vis },
        {
          height: innerWidth < 600 ? 250 : 330,
          time: out.time,
          format: out.fmt,
          zero: out.zero,
          zeroLine: st.zero,
          markers: markers(P, st, out, shownKeys(P, st, vis)),
          selected: st.focus ? new Set([st.focus]) : new Set(),
          onSelect: (id) => {
            st.focus = id && id !== st.focus ? id : null;
            draw(host, P, hooks);
          },
          onTransaction: (id) => hooks && hooks.history && hooks.history(id),
        },
      );
    }
    host.querySelector("#pfc-leg").innerHTML = out.series
      .map((s) => {
        const v = last(s.values);
        return `<button type="button" class="badge outline px-chip ${hidden(s) ? "off" : ""}" data-sid="${esc(s.id)}" aria-pressed="${!hidden(s)}"><i class="${swatch(s.color)}"></i>${esc(s.label)} <b class="${cl(v)}">${isNum(v) ? out.fmt(v) : "n/d"}</b></button>`;
      })
      .join("");
    host.querySelectorAll("[data-sid]").forEach(
      (b) =>
        (b.onclick = () => {
          const s = out.series.find((x) => x.id === b.dataset.sid);
          if (isTitle(s)) {
            if (!st.shown) st.shown = new Set(out.series.filter((x) => isTitle(x) && !hidden(x)).map(vkey));
            st.shown.has(vkey(s)) ? st.shown.delete(vkey(s)) : st.shown.add(vkey(s));
          } else st.vis[vkey(s)] = !hidden(s);
          draw(host, P, hooks);
        }),
    );
  }

  /** Chiffres par titre sur une période : gain en euros, rendement (TWR du titre rebasé), contribution en points de la performance globale. */
  function periodStats(P, per) {
    const win = window_(P, per),
      F = P.chart.full,
      end = (a) => {
        const v = a.length ? a[a.length - 1] : null;
        return isNum(v) ? v : null;
      },
      total = end(diff(F.gain, win)),
      rows = {};
    for (const k of Object.keys(F.holdings)) {
      const H = F.holdings[k],
        g = end(diff(H.gain, win)),
        r = end(rebase(H.twr, win)),
        c = end(diff(H.contribution, win));
      rows[k] = {
        gain: g,
        twr: r,
        contribution: c,
        share: isNum(g) && isNum(total) && Math.abs(total) > 1e-9 ? g / Math.abs(total) : null,
      };
    }
    return { total, rows };
  }

  /** Monte le graphique dans `host` (carte déjà insérée par boxHtml). */
  function mountChart(host, P, hooks) {
    host.querySelectorAll("[data-k]").forEach(
      (g) =>
        (g.onclick = (e) => {
          const b = e.target.closest("button[data-v]");
          if (!b || ST[g.dataset.k] === b.dataset.v) return;
          ST[g.dataset.k] = b.dataset.v;
          ST.focus = null;
          g.querySelectorAll("button").forEach((x) => {
            const on = x.dataset.v === b.dataset.v;
            x.classList.toggle("on", on);
            if (g.classList.contains("px-per")) x.setAttribute("aria-pressed", String(on));
          });
          host.querySelector("#pfc-unit").hidden = ST.mode !== "market";
          draw(host, P, hooks);
        }),
    );
    host.querySelector("#pfc-marks").onchange = (e) => {
      ST.marks = e.target.checked;
      draw(host, P, hooks);
    };
    host.querySelector("#pfc-zero").onchange = (e) => {
      ST.zero = e.target.checked;
      draw(host, P, hooks);
    };
    draw(host, P, hooks);
  }

  root.PFPerf2 = {
    periodStats,
    load,
    usable,
    money,
    boxHtml,
    mountChart,
  };
})(window);
