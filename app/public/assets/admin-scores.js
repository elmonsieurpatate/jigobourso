/* Administration → Scores (V4) : un moteur de notation commun, des profils de stratégie, une simulation sur titres réels, le suivi des calculs.
   Toutes les valeurs viennent du moteur (admin/scores*). Aucune donnée d'exemple : sans données, les écrans le disent. */
(function () {
  const TABS = [
    ["config", "Configuration du moteur"],
    ["profils", "Profils de stratégies"],
    ["simulation", "Simulation & exemples"],
    ["suivi", "Suivi des calculs"],
  ];
  const $ = J.$;
  const E = J.esc;
  const fmt = (v, d = 1) => J.num(v, d);
  const clone = (o) => JSON.parse(JSON.stringify(o));

  let MINE = false;
  const P = () => (MINE ? "my/scores" : "admin/scores");
  let root,
    S,
    draft,
    savedJson,
    sel,
    rkWhich = "simple",
    rkCat = null,
    rkVerdict = "all",
    rkSorts = [],
    tl = null,
    rkMore = false,
    rank = null,
    confBusy = false,
    confFail = false,
    confStale = false,
    tab = "config",
    scoreTab = "simple",
    mon = null,
    monErr = null,
    sim = null,
    simWin = 0,
    simBusy = false,
    simQ = "",
    useDraft = true,
    error = "";
  const autoCache = J.asyncMemo(
    (args) => J.post(P() + "/preview", args).then((r) => r.weights),
    () => paint(),
  );

  const v4 = () => S.strategies.filter((s) => s.engine === "v4");
  const strat = () => S.strategies.find((s) => s.name === sel);
  const prof = () => draft.profiles[sel];
  const labels = () => S.period_labels;
  const active = (p) => S.scoring_periods.filter((id) => p.periods[id].enabled);
  const dirty = () => JSON.stringify(draft) !== savedJson;
  const payloadFor = (name) => {
    const p = clone(draft.profiles[name]);
    Object.values(p.periods).forEach((x) => delete x.sessions);
    return { name, ...p };
  };
  const payload = () => payloadFor(sel);
  const savedProfiles = () => JSON.parse(savedJson).profiles;

  // Gabarits HTML : admin-scores-view.js lit l'état courant par ces accesseurs et renvoie du HTML (jamais d'écriture dans la page).
  const ctx = {
    get S() {
      return S;
    },
    get draft() {
      return draft;
    },
    get sel() {
      return sel;
    },
    get tab() {
      return tab;
    },
    get scoreTab() {
      return scoreTab;
    },
    get rank() {
      return rank;
    },
    get rkWhich() {
      return rkWhich;
    },
    get rkCat() {
      return rkCat;
    },
    get rkVerdict() {
      return rkVerdict;
    },
    get rkMore() {
      return rkMore;
    },
    get confBusy() {
      return confBusy;
    },
    get confFail() {
      return confFail;
    },
    get confStale() {
      return confStale;
    },
    get simQ() {
      return simQ;
    },
    get simBusy() {
      return simBusy;
    },
    get mon() {
      return mon;
    },
    get monErr() {
      return monErr;
    },
    get sim() {
      return sim;
    },
    get simWin() {
      return simWin;
    },
    get root() {
      return root;
    },
    get useDraft() {
      return useDraft;
    },
    get MINE() {
      return MINE;
    },
    get chart() {
      return chart;
    },
    set chart(v) {
      chart = v;
    },
    v4: () => v4(),
    strat: () => strat(),
    prof: () => prof(),
    labels: () => labels(),
    active: (p) => active(p),
    weightsOf: (p) => weightsOf(p),
    autoWeights: (p) => autoWeights(p),
    sum: (o) => sum(o),
    layoutNow: () => layoutNow(),
    get rkSorts() {
      return rkSorts;
    },
  };
  const { chartCard, configView, profilesView, simulationView, monitorView, readout, rankColumns, stratPicker } =
    AdminScoresView(ctx);

  function reset() {
    draft = { global: { kappa: S.global.kappa, threshold: S.global.threshold, anchor: S.global.anchor }, profiles: {} };
    v4().forEach((s) => {
      draft.profiles[s.name] = clone(s.current);
    });
    savedJson = JSON.stringify(draft);
    error = "";
  }

  // Poids automatiques des périodes actives, calculés par le moteur (jamais recopiés ici).
  const weightKey = (p) => draft.global.kappa + "|" + active(p).join(",");
  const previewErrors = () => {
    const current = new Set(
      v4()
        .map((s) => draft.profiles[s.name])
        .filter(Boolean)
        .map(weightKey),
    );
    return autoCache.errors().filter((e) => current.has(e.key));
  };
  function autoWeights(p) {
    const ids = active(p),
      key = weightKey(p);
    const entry = autoCache.read(key, { kappa: draft.global.kappa, periods: ids });
    if (entry.state === "ready") return entry.value;
    const st = strat();
    return st &&
      JSON.stringify(Object.keys(st.auto_weights).sort()) === JSON.stringify(ids.toSorted()) &&
      draft.global.kappa === S.global.kappa
      ? st.auto_weights
      : null;
  }
  const weightsOf = (p) => (p.weights_mode === "custom" ? p.weights : autoWeights(p));
  const sum = (o) => Object.values(o).reduce((a, b) => a + (+b || 0), 0);

  async function load() {
    S = await J.api(P());
    tl = await TableLayout.load();
    if (!sel || !S.strategies.find((s) => s.name === sel)) sel = (v4()[0] || S.strategies[0]).name;
    reset();
  }

  async function render(page, opts) {
    MINE = !!(opts && opts.mine);
    root = page;
    root.innerHTML = '<div class="empty"><span class="spinner"></span></div>';
    await load();
    initRank();
    root.onchange = onChange;
    root.oninput = onInput;
    root.onclick = onClick;
    root.onpointermove = chartMove;
    root.onpointerdown = chartMove;
    root.onpointerleave = chartLeave;
    root.onpointerup = (e) => {
      if (e.pointerType === "touch") setTimeout(chartLeave, 2500);
    };
    root.onkeydown = (e) => {
      if (e.key === "Enter" && !e.isComposing && e.target.id === "as-q") {
        simQ = e.target.value;
        runSim(null);
      }
    };
    if (!window.__asResize) {
      window.__asResize = true;
      let tm;
      window.addEventListener("resize", () => {
        clearTimeout(tm);
        tm = setTimeout(() => {
          if (tab === "simulation" && sim && sim.result && $("#as-ch")) {
            const w = $("#as-body").clientWidth;
            if (chart && Math.abs(w - 40 - chart.W) > 8) paint();
          }
        }, 200);
      });
    }
    skeleton();
    paint();
  }

  // ───────────── mise en page ─────────────
  // Squelette posé une fois : la barre d'actions n'est jamais remplacée (un clic sur « Enregistrer » juste après une saisie ne se perd pas) ;
  // seuls l'onglet courant et l'état de la barre sont mis à jour.
  function skeleton() {
    root.innerHTML = `<div class="as">
      <div class="notice as-principle"><b>Principe V4 : un moteur unique pour toutes les stratégies.</b> Le score simple mesure uniquement la pente et le R² des périodes sélectionnées ; le score complexe ajoute séances positives, concentration, volatilité, drawdown, liquidité et l’ancrage récent. Chaque stratégie choisit ses périodes, ses seuils et ses pondérations, sans changer la méthode de calcul. Tous les titres évaluables sont notés et classés ; les filtres d’affichage (page « Filtres et catégories ») n’entrent jamais dans une note.</div>
      <div class="tabs as-tabs" id="as-tabs"></div><div id="as-err"></div><div id="as-body"></div>
      <div class="as-bar"><div id="as-status"></div><div class="row gap-s">
        <button class="btn" data-a="cancel">Annuler les modifications</button>
        <button class="btn" data-a="restore">Restaurer les valeurs par défaut…</button>
        <button class="btn primary" data-a="save">Enregistrer les modifications</button></div></div></div>`;
  }

  function paintBar() {
    const st = strat(),
      d = dirty(),
      at = (st && st.saved_at) || S.global.saved_at;
    $("#as-status").innerHTML = d
      ? '<span class="as-dirty">● Modifications non enregistrées</span>'
      : at
        ? `<span class="as-saved">✓ Configuration enregistrée le ${E(J.dateTime(at))}</span>`
        : '<span class="as-saved">✓ Valeurs par défaut en vigueur</span>';
    $("[data-a=cancel]", root).disabled = !d;
    $("[data-a=save]", root).disabled = !(d && isV4Valid());
  }

  function paintBody() {
    const st = strat(),
      isV4 = st && st.engine === "v4";
    $("#as-tabs").innerHTML = TABS.filter((t) => !(MINE && t[0] === "suivi"))
      .map(([k, t]) => `<button data-a="tab" data-v="${k}" class="${tab === k ? "on" : ""}">${t}</button>`)
      .join("");
    const failedPreviews = previewErrors();
    $("#as-err").innerHTML =
      (error ? `<div class="notice err mb-3">${E(error)}</div>` : "") +
      (failedPreviews.length
        ? `<div class="notice err mb-3" role="alert">Aperçu des pondérations indisponible : ${E(failedPreviews[0].error)} <button type="button" class="btn sm" data-a="retry-weights">Réessayer l’aperçu</button></div>`
        : "");
    $("#as-body").innerHTML =
      tab === "config"
        ? configView(st, isV4)
        : tab === "profils"
          ? profilesView()
          : tab === "simulation"
            ? simulationView(isV4)
            : monitorView();
    if (MINE && tab === "config") {
      // réglages communs : propres à l'administration, lecture seule pour un utilisateur
      $("#as-body").insertAdjacentHTML(
        "afterbegin",
        '<div class="notice mb-3">Les réglages communs (priorité aux périodes courtes, seuil de fiabilité, ancrage) sont fixés par l’administration. Vos adaptations se font dans « Profils de stratégies » et ne concernent que votre compte.</div>',
      );
      document
        .querySelectorAll("#as-body [data-a=kappa],#as-body [data-a=anchor],#as-body [data-a=thr]")
        .forEach((e) => {
          e.disabled = true;
        });
    }
    if (tab === "suivi" && !mon && !monErr && !MINE) loadMonitor();
    if (tab === "profils" && !rank && !confBusy && !confFail && st && st.engine === "v4") runConf();
  }

  function paint() {
    if (!$("#as-body")) skeleton();
    paintBody();
    paintBar();
  }
  const later = () => setTimeout(paint, 0); // redessin différé quand on sort d'un champ (évite de remplacer le DOM pendant l'événement « blur »)

  // Graphique interactif : cours réels, axes datés, fenêtre au choix (granularités de notation), lecture au survol ou au toucher.
  let chart = null;
  function chartMove(e) {
    const hit = e.target.closest && e.target.closest("#as-hit");
    if (!hit || !chart) return;
    const r = hit.getBoundingClientRect(),
      f = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)),
      i = Math.round(f * (chart.pts.length - 1));
    const cur = $("#as-cur"),
      dot = $("#as-dot"),
      x = chart.X(i),
      y = chart.Y(chart.pts[i].p);
    cur.setAttribute("x1", x);
    cur.setAttribute("x2", x);
    dot.setAttribute("cx", x);
    dot.setAttribute("cy", y);
    cur.classList.remove("is-off");
    dot.classList.remove("is-off");
    $("#as-read").innerHTML = readout(i);
  }
  function chartLeave() {
    if (!chart || !$("#as-cur")) return;
    $("#as-cur").classList.add("is-off");
    $("#as-dot").classList.add("is-off");
    $("#as-read").innerHTML = readout(chart.pts.length - 1);
  }

  // Colonnes, tri et statut initiaux : Administration → Colonnes (configuration « scores » de l'affichage courant). Le choix fait ensuite dans le tableau reste prioritaire.
  const SC_FALLBACK = () => ["rank", "name", "status", "trend", "simple", "complex"].map((id) => [id, true]);
  const layoutNow = () => TableLayout.get(tl, "scores", TableLayout.device(), SC_FALLBACK());
  function initRank() {
    const l = layoutNow();
    rkVerdict = (l.filters && l.filters.verdict) || "all";
    rkSorts = (l.sort || []).map((x) => ({ ...x }));
    if (rkSorts[0] && ["simple", "complex"].includes(rkSorts[0].key)) rkWhich = rkSorts[0].key;
    if (!window.__asLayoutWatch) {
      window.__asLayoutWatch = true;
      TableLayout.onChange(() => {
        if (rank && $("#as-rktable")) paintBody();
      });
    }
  }
  const rankBody = (extra) => {
    const body = {
      strategy: sel,
      which: rkWhich,
      category: rkCat,
      verdict: rkVerdict,
      sort: rkSorts,
      limit: 25,
      ...extra,
    };
    if (dirty()) body.draft = { global: draft.global, profile: payload() };
    return body;
  };
  async function runConf(keepCat) {
    confBusy = true;
    confFail = false;
    confStale = false;
    if (!keepCat) rkCat = null;
    paintBody();
    try {
      rank = await J.post(P() + "/ranking", rankBody({ offset: 0 }));
      error = "";
    } catch (e) {
      rank = null;
      confFail = true;
      error = e.message;
    }
    confBusy = false;
    paint();
  }
  async function rankMore() {
    rkMore = true;
    paintBody();
    try {
      const r = await J.post(P() + "/ranking", rankBody({ offset: rank.listing.rows.length }));
      rank.listing.rows = rank.listing.rows.concat(r.listing.rows);
      rank.listing.total = r.listing.total;
    } catch (e) {
      error = e.message;
    }
    rkMore = false;
    paint();
  }

  // ───────────── simulation ─────────────
  async function runSim(id) {
    simBusy = true;
    paint();
    try {
      const body = { strategy: sel, q: id ? "" : simQ, listing_id: id || null };
      if (useDraft && dirty() && strat().engine === "v4") body.draft = { global: draft.global, profile: payload() };
      sim = await J.post(P() + "/simulate", body);
    } catch (e) {
      sim = null;
      error = e.message;
    }
    simBusy = false;
    paint();
  }

  // ───────────── suivi ─────────────
  async function loadMonitor() {
    try {
      mon = await J.api("admin/scores/monitor");
      monErr = null;
    } catch (e) {
      monErr = e.message;
    }
    paint();
  }
  // ───────────── actions ─────────────
  function isV4Valid() {
    return v4().every((s) => {
      const p = draft.profiles[s.name];
      const ids = active(p);
      if (!ids.length) return false;
      if (
        p.weights_mode === "custom" &&
        Math.abs(sum(Object.fromEntries(ids.map((i) => [i, p.weights[i]]))) - 100) > 0.05
      )
        return false;
      return Math.abs(sum(p.complex_weights) - 100) <= 0.05;
    });
  }

  function onInput(e) {
    const t = e.target;
    if (t.dataset.a === "cw") {
      const k = t.dataset.k;
      prof().complex_weights[k] = +t.value || 0;
      paintBar();
      const tot = sum(prof().complex_weights);
      const el = $("#cw-total");
      if (el) {
        el.textContent = fmt(tot, 1) + " %";
        el.parentElement.className = "as-total " + (Math.abs(tot - 100) <= 0.05 ? "ok" : "ko");
      }
      const b = $("#cwb-" + k),
        pc = $("#cwp-" + k);
      if (b) b.style.width = Math.min(100, +t.value || 0) + "%";
      if (pc) pc.textContent = fmt(+t.value || 0, 0) + " %";
    } else if (t.id === "as-q") simQ = t.value;
  }

  function onChange(e) {
    const t = e.target,
      a = t.dataset.a,
      p = sel && draft.profiles[sel];
    if (a === "strategy") {
      const keep = tab === "simulation" && sim && sim.title ? sim.title.id : null;
      sel = t.value;
      rank = null;
      if (keep) {
        runSim(keep);
        return;
      }
      sim = null;
      later();
    } else if (a === "active") {
      const on = t.checked,
        q = prof();
      if (!on && active(q).length <= 1) {
        t.checked = true;
        J.toast("Au moins une granularité doit rester active");
        return;
      }
      q.periods[t.dataset.p].enabled = on;
      if (q.weights_mode === "custom") {
        if (on) q.weights[t.dataset.p] = 0;
        else delete q.weights[t.dataset.p];
      }
      later();
    } else if (a === "req") {
      p.periods[t.dataset.p].require_history = t.checked;
      confStale = true;
      paintBar();
    } else if (a === "pw") {
      p.weights[t.dataset.p] = +t.value || 0;
      const tot = sum(Object.fromEntries(active(p).map((i) => [i, p.weights[i]]))),
        el = $("#pw-total");
      if (el) {
        el.className = "as-total " + (Math.abs(tot - 100) <= 0.05 ? "ok" : "ko");
        el.innerHTML = `Pondération totale : <b>${fmt(tot, 1)} %</b>${Math.abs(tot - 100) > 0.05 ? " — doit faire 100 %" : ""}`;
      }
      paintBar();
    } else if (a === "cw") {
      p.complex_weights[t.dataset.k] = +t.value || 0;
      paintBar();
    } else if (a === "tune") {
      const k = t.dataset.k,
        R = S.design.tuning_ranges[k];
      p.tuning = p.tuning || clone(S.design.tuning);
      p.tuning[k] = R ? Math.min(R[1], Math.max(R[0], +t.value || S.design.tuning[k])) : t.value;
      confStale = true;
      paintBar();
      later();
    } else if (a === "kappa") {
      draft.global.kappa = +t.value;
      paintBar();
      later();
    } else if (a === "anchor") {
      draft.global.anchor = Math.min(1, Math.max(0, +t.value || 0));
      paintBar();
    } else if (a === "thr") {
      draft.global.threshold = +t.value;
      paintBar();
    } else if (a === "thr-p") {
      p.periods[t.dataset.p][t.dataset.f] = t.value === "" ? null : +t.value;
      confStale = true;
      paintBar();
    } else if (a === "day-on") {
      p.day_filter.enabled = t.checked;
      confStale = true;
      paint();
    } else if (a === "day-min") {
      p.day_filter.min_return = +t.value || 0;
      confStale = true;
      paintBar();
    } else if (a === "liq") {
      p.liquidity[t.dataset.f] = t.value === "" ? null : Math.round(+t.value * 1e6);
      confStale = true;
      paintBar();
    } else if (a === "fresh") {
      p.technical.require_fresh = t.checked;
      confStale = true;
      paintBar();
    } else if (a === "use-draft") {
      useDraft = t.checked;
    }
  }

  function toCustom() {
    const p = prof(),
      w = autoWeights(p) || {},
      ids = active(p);
    let acc = 0;
    p.weights = {};
    ids.forEach((i, n) => {
      const v = n === ids.length - 1 ? Math.round((100 - acc) * 10) / 10 : Math.round((w[i] || 0) * 10) / 10;
      p.weights[i] = v;
      acc += v;
    });
    p.weights_mode = "custom";
  }

  async function onClick(e) {
    const sb = e.target.closest("[data-sort]");
    if (sb) {
      const v = sb.dataset.sort;
      rkSorts = [J.table.nextSort(rkSorts[0], v, rankColumns[v].dir || "desc")];
      if (["simple", "complex"].includes(v)) {
        rkWhich = v;
        rkCat = null;
      }
      return runConf(true);
    }
    const t = e.target.closest("[data-a]");
    if (!t || t.tagName === "INPUT" || t.tagName === "SELECT") return;
    const a = t.dataset.a,
      v = t.dataset.v;
    if (a === "retry-weights") {
      previewErrors().forEach((e) => autoCache.retry(e.key));
      paint();
    } else if (a === "tab") {
      tab = v;
      error = "";
      paint();
    } else if (a === "score") {
      scoreTab = v;
      paint();
    } else if (a === "mode") {
      if (v === "custom") toCustom();
      else {
        prof().weights_mode = "auto";
        prof().weights = {};
      }
      paint();
    } else if (a === "pw-auto") {
      prof().weights_mode = "auto";
      prof().weights = {};
      paint();
    } else if (a === "cw-norm") {
      const p = prof(),
        tot = sum(p.complex_weights) || 1;
      let acc = 0;
      const keys = Object.keys(p.complex_weights);
      keys.forEach((k, i) => {
        const x =
          i === keys.length - 1
            ? Math.round((100 - acc) * 10) / 10
            : Math.round((p.complex_weights[k] / tot) * 1000) / 10;
        p.complex_weights[k] = x;
        acc += x;
      });
      paint();
    } else if (a === "tune-reset") {
      prof().tuning = prof().tuning || clone(S.design.tuning);
      prof().tuning[t.dataset.k] = S.design.tuning[t.dataset.k];
      confStale = true;
      paint();
    } else if (a === "cw-ref") {
      prof().complex_weights = clone(S.design.complex_weights);
      paint();
    } else if (a === "open") {
      sel = v;
      tab = "profils";
      sim = null;
      rank = null;
      paint();
    } else if (a === "conf-run") {
      runConf(true);
    } else if (a === "rk-which") {
      rkWhich = v;
      rkSorts = [{ key: v, dir: "desc" }];
      rkCat = null;
      runConf(true);
    } else if (a === "rk-cat") {
      rkCat = v || null;
      runConf(true);
    } else if (a === "rk-verdict") {
      rkVerdict = v;
      runConf(true);
    } else if (a === "rk-more") rankMore();
    else if (a === "cancel") {
      reset();
      rank = null;
      paint();
    } else if (a === "save") save();
    else if (a === "restore") restore();
    else if (a === "sim-run") {
      simQ = ($("#as-q") || {}).value || "";
      runSim(null);
    } else if (a === "sim-pick") runSim(+t.dataset.id);
    else if (a === "sim-win") {
      simWin = +v;
      paint();
    } else if (a === "mon-refresh") {
      mon = null;
      monErr = null;
      paint();
    }
  }

  async function save() {
    try {
      const before = savedProfiles(),
        changed = v4()
          .map((s) => s.name)
          .filter((n) => JSON.stringify(draft.profiles[n]) !== JSON.stringify(before[n]));
      if (!changed.length && !MINE) S = await J.post(P() + "/save", { global: draft.global });
      for (const [i, n] of changed.entries())
        S = await J.post(
          P() + "/save",
          i === 0 && !MINE ? { global: draft.global, profile: payloadFor(n) } : { profile: payloadFor(n) },
        );
      reset();
      autoCache.clear();
      mon = null;
      sim = null;
      rank = null;
      J.toast("Configuration enregistrée");
    } catch (e) {
      error = e.message;
      J.toast(e.message);
    }
    paint();
  }

  function restore() {
    const st = strat(),
      name = st && st.engine === "v4" ? st.label : "la stratégie";
    J.dialog({
      title: "Restaurer les valeurs par défaut",
      body: `<p class="as-hint">Choisissez ce qui revient aux valeurs proposées. Les modifications non enregistrées seront perdues.</p>
      <label class="as-rad"><input type="radio" name="rs" value="profile" checked> Le profil « ${E(name)} » (périodes, seuils, poids)</label>
      ${
        MINE
          ? ""
          : `<label class="as-rad"><input type="radio" name="rs" value="global"> Les réglages communs (priorité aux périodes courtes, couverture minimale)</label>
      <label class="as-rad"><input type="radio" name="rs" value="all"> Tout (communs et tous les profils V4)</label>`
      }`,
      actions: [
        { label: "Annuler", run: () => {} },
        {
          label: "Restaurer",
          cls: "primary",
          run: async (d) => {
            const scope = ($("input[name=rs]:checked", d) || {}).value || "profile";
            try {
              S = await J.post(
                P() + "/save",
                scope === "profile"
                  ? { reset: "profile", name: st && st.engine === "v4" ? sel : v4()[0].name }
                  : { reset: scope },
              );
              reset();
              autoCache.clear();
              sim = null;
              rank = null;
              J.toast("Valeurs par défaut rétablies");
            } catch (e) {
              J.toast(e.message);
            }
            paint();
          },
        },
      ],
    });
  }

  window.AdminScores = { render };
})();
