/* Portefeuille V4 — détail d'une ligne : en-tête compact et trois onglets (Chiffres, Graphique, Plan de suivi).
   Chargé après pf-home.js, dont il lit l'état et les aides par window.PFHomeX ; expose window.PfDetail { MAIN, openDetail, renderPlan }. */
(function (root) {
  "use strict";
  const PFM = root.PFM,
    isNum = PFM.isNum;
  const X = root.PFHomeX,
    { S } = X;
  const {
    I,
    all,
    bindBox,
    boxHtml,
    cl,
    drawBox,
    esc,
    eur,
    lastIdx,
    mDates,
    mk,
    open,
    pc,
    perName,
    pkey,
    planOf,
    reloadTracking,
    sg,
    stats,
    table,
    taxOf,
  } = X;
  /* ───────── détail : en-tête compact, trois onglets (Chiffres, Graphique, Plan de suivi) ───────── */
  const MAIN = {
    modes: [
      ["perso", "Mon investissement"],
      ["market", "Historique des cours"],
    ],
    pf: true,
    keys: () => open().map(pkey),
  };
  const DETC = (key) => ({
    modes: [
      ["perso", "Mon investissement"],
      ["market", "Historique des cours"],
    ],
    pf: false,
    keys: () => [key],
  });
  const ROWS = ["1d", "2d", "5d", "1w", "2w", "1m", "3m", "6m", "1y", "2y", "3y", "5y", "10y", "all"];
  const rowName = (per) => (per === "all" ? "Depuis l’achat" : perName(per));
  /** Résultat personnel par période : uniquement sur la partie détenue ; jamais de performance avant l'achat. Apports neutralisés (résultat = variation du gain). */
  function persoRows(l) {
    const H = X.C().H,
      first = PFM.firstActive(l),
      fd = first == null ? null : H.dates[first];
    return ROWS.map((per) => {
      const lab = rowName(per);
      if (first == null) return { lab, na: "Aucun achat enregistré sur ce titre." };
      const w = PFM.resolveWindow(H, per);
      if (w.i1 < first) return { lab, na: "Titre pas encore détenu." };
      const partial = per !== "all" && w.i0 < first,
        r = PFM.position(H, l, partial ? Object.assign({}, w, { i0: -1 }) : w);
      if (!isNum(r.result)) return { lab, na: r.reason || "Indisponible." };
      return {
        lab,
        eur: r.result,
        pct: r.pct,
        note: partial
          ? "Partiel : depuis l’achat du " + J.date(fd)
          : w.clipped
            ? "Historique plus court que la période"
            : "",
      };
    });
  }
  /** Variation du cours du titre (marché) : indépendante de vos achats. € par titre au change du jour. */
  function marketRows(key, l) {
    const M = mk(),
      ln = M.lines.find((x) => x.key === key),
      dates = mDates(),
      H = X.C().H,
      first = l ? PFM.firstActive(l) : null,
      fd = first == null ? null : H.dates[first];
    return ROWS.map((per) => {
      const lab = rowName(per);
      if (!ln) return { lab, na: "Aucun cours disponible pour ce titre." };
      let i1 = ln.prices.length - 1;
      while (i1 >= 0 && !isNum(ln.prices[i1])) i1--;
      if (i1 < 0) return { lab, na: "Aucun cours." };
      let i0;
      if (per === "all") {
        if (!fd) return { lab, na: "Aucun achat enregistré." };
        i0 = lastIdx(dates, fd);
      } else {
        const w = PFM.resolveWindow({ dates }, per);
        i0 = w.i0;
        if (i0 < 0) return { lab, na: "Cours disponibles seulement depuis le " + J.date(dates[0]) + "." };
      }
      if (i0 < 0 || !isNum(ln.prices[i0])) return { lab, na: "Cours de départ indisponible." };
      const e0 = ln.prices_eur[i0],
        e1 = ln.prices_eur[i1];
      return {
        lab,
        eur: isNum(e0) && isNum(e1) ? e1 - e0 : null,
        pct: 100 * (ln.prices[i1] / ln.prices[i0] - 1),
        note: "",
      };
    });
  }
  function figuresHtml(x) {
    const rows = S.fig === "market" ? marketRows(x.key, x.l) : x.l ? persoRows(x.l) : [],
      mk2 = S.fig === "market";
    return `<div class="px-tw"><table class="px-t px-fig">${J.table.head(["Période", [mk2 ? "Variation € / titre" : "Gain / perte €", "num"], [mk2 ? "Variation du cours %" : "Performance %", "num"]])}<tbody>${rows.map((r) => (r.na ? `<tr><td data-l="Période"><b>${r.lab}</b></td><td colspan="2" class="px-na">Indisponible : ${esc(r.na)}</td></tr>` : `<tr><td data-l="Période"><b>${r.lab}</b>${r.note ? `<small class="px-part">${esc(r.note)}</small>` : ""}</td><td class="num ${cl(r.eur)}" data-l="${mk2 ? "Variation €" : "Gain / perte"}">${mk2 ? sg(r.eur) : sg(r.eur)}</td><td class="num ${cl(r.pct)}" data-l="Performance">${pc(r.pct)}</td></tr>`)).join("")}</tbody></table></div>
      <p class="px-note">${mk2 ? "Variation du cours, indépendante de vos achats (cours de clôture, dernier cours connu pour la fin)." : "Votre résultat sur la période, calculé uniquement sur la partie détenue : les apports d’argent ne sont jamais comptés comme des gains, les gains réalisés par vos ventes sont conservés. 1J à 1S : clôtures quotidiennes."}</p>`;
  }
  function lotStrategy(lo) {
    const pl = S.tr && S.tr.positions[String(lo.listing_id)],
      o = pl && (pl.origins || []).find((z) => z.tx === lo.tx_id && z.label);
    return o ? o.label : "Non renseignée";
  }
  let detailAc = null; // écouteurs de la fenêtre de détail ouverte : retirés à la fermeture ou au remplacement
  function openDetail(key, goPlan) {
    if (detailAc) detailAc.abort();
    S.sel = key;
    S.fig = "perso";
    S.tab = goPlan ? "suivi" : "chiffres";
    const st = stats(),
      x = st.rows.find((r) => r.key === key);
    if (!x) return;
    const { p, l } = x,
      closed = !(p.qty > 0),
      cur = p.price_currency || p.currency;
    const lots = (X.C().D.lots || []).filter((lo) =>
        p.listing_id ? lo.listing_id === p.listing_id : lo.symbol === p.symbol,
      ),
      trades = (X.C().H.trades || [])
        .filter((t) => t.key === key && !t.note)
        .sort((a, b) => String(b.trade_at).localeCompare(String(a.trade_at)));
    const sales = (X.C().D.sales || []).filter((s) =>
        p.listing_id ? s.listing_id === p.listing_id : s.symbol === p.symbol,
      ),
      re = sales.reduce((n, s) => n + (s.gain || 0), 0),
      lat = closed ? 0 : p.value - p.cost,
      tp = taxOf([Math.max(0, re)], lat, x.gain, l ? l.purchases[l.purchases.length - 1] || 0 : 0);
    Object.assign(S.det, { mode: "perso", per: "all", unit: "pct", view: null, focus: null });
    S.det.hidden.clear();
    const root = J.$("#px-drawer-root"),
      prev = document.activeElement,
      kv = (k, v) => `<div><dt>${k}</dt><dd>${v}</dd></div>`;
    root.innerHTML = `<div class="px-back" data-close></div><aside class="px-drawer" role="dialog" aria-modal="true" aria-label="Détail ${esc(p.symbol)}"><header class="px-dh"><div class="px-id"><h2>${esc(p.symbol)} <span>${esc(p.name_catalogue || p.name || "")}</span></h2><dl class="px-kv2 px-hk">${kv("Cours", closed ? "–" : J.money(p.price, cur))}${kv("Prix de revient", closed ? "–" : eur(p.avg_cost))}${kv("Résultat global", `<span class="${cl(x.gain)}">${sg(x.gain)} · ${pc(x.pctv, 1)}</span>`)}</dl></div>
      <div class="px-ha px-dact">${p.listing_id ? `<a class="btn" href="titre.html?id=${p.listing_id}&from=portefeuille" target="_blank" rel="noopener">Analyse du titre ${I.ext}</a>` : ""}<button type="button" class="btn primary" data-buy="${esc(key)}">Acheter</button><button type="button" class="btn" data-sell="${esc(key)}" ${closed ? "disabled" : ""}>Vendre</button><button type="button" class="btn" data-close aria-label="Fermer le détail">✕</button></div></header>
      <div class="px-tabs2" role="tablist" aria-label="Détail du titre">${[
        ["chiffres", "Chiffres"],
        ["graphique", "Graphique"],
        ["suivi", "Plan de suivi"],
      ]
        .map(
          ([k, lb]) =>
            `<button type="button" role="tab" data-tab="${k}" aria-selected="${S.tab === k}" class="${S.tab === k ? "on" : ""}">${lb}</button>`,
        )
        .join("")}</div>
      <div class="px-db">
       <section data-panel="chiffres" ${S.tab === "chiffres" ? "" : "hidden"}><h3>Combien ai-je gagné ou perdu sur ce titre ?</h3>
        <dl class="px-kv2 px-origin">${kv("Depuis l’origine", `<span class="${cl(x.gain)}">${sg(x.gain)}</span>`)}${kv("dont réalisé (ventes)", `<span class="${cl(re)}">${sg(re)}</span>`)}${kv("dont latent", closed ? "–" : `<span class="${cl(lat)}">${sg(lat)}</span>`)}${kv("Après impôts (estimé)", `<span class="${cl(tp.net)}">${sg(tp.net)} · ${pc(tp.pct, 1)}</span>`)}${kv("Quantité", closed ? "0" : J.num(p.qty, 4))}</dl>
        <div class="px-seg px-figseg" id="px-figseg" aria-label="Type de chiffres"><button type="button" data-fig="perso" class="on" aria-pressed="true">Mon résultat</button><button type="button" data-fig="market" aria-pressed="false">Variation du cours</button></div>
        <div id="px-fig">${figuresHtml(x)}</div>
        <h3>Mes achats et ventes</h3><div class="px-tw"><table class="px-t px-ops">${J.table.head(["Date", "Opération", ["Quantité", "num"], ["Prix", "num"], ["Frais", "num"], ["Résultat réalisé", "num"]])}<tbody>${
          trades
            .map((t) => {
              const s = t.side === "sell" ? sales.find((z) => z.tx_id === t.id) : null;
              return `<tr><td data-l="Date">${J.date(t.date)}</td><td data-l="Opération"><b>${t.side === "sell" ? "Vente" : "Achat"}</b></td><td class="num" data-l="Quantité">${J.num(t.quantity, 4)}</td><td class="num" data-l="Prix">${J.num(t.unit_price, 4)} ${esc(t.currency || "")}</td><td class="num" data-l="Frais">${eur(t.fees_eur)}</td><td class="num ${s ? cl(s.gain) : ""}" data-l="Réalisé">${s ? sg(s.gain) : "–"}</td></tr>`;
            })
            .join("") || '<tr><td colspan="6" class="px-note">Aucune opération.</td></tr>'
        }</tbody></table></div>
        ${lots.length ? `<details class="px-tech"><summary>Détails techniques : lots d’achat restants</summary><div class="px-list">${lots.map((lo) => `<div><span>${J.date(lo.trade_at)}</span><b>${J.num(lo.remaining, 4)} titre(s)</b><span>Stratégie d’origine : ${esc(lotStrategy(lo))}</span><button type="button" class="btn sm" data-lot="${lo.tx_id}">Régler cet achat</button></div>`).join("")}</div></details>` : ""}</section>
       <section data-panel="graphique" ${S.tab === "graphique" ? "" : "hidden"}>${boxHtml(S.det, DETC(key))}</section>
       <section data-panel="suivi" ${S.tab === "suivi" ? "" : "hidden"}><div id="px-plan-body"></div></section></div></aside>`;
    root.hidden = false;
    document.body.classList.add("px-lock");
    let boxed = false;
    const close = () => {
      root.hidden = true;
      root.innerHTML = "";
      S.sel = null;
      document.body.classList.remove("px-lock");
      if (detailAc) detailAc.abort();
      detailAc = null;
      prev && prev.focus && prev.focus();
    };
    const esc2 = (e) => {
      if (e.key === "Escape" && !document.querySelector("dialog[open]")) close();
    };
    detailAc = new AbortController();
    document.addEventListener("keydown", esc2, { signal: detailAc.signal });
    const showTab = (k) => {
      S.tab = k;
      root.querySelectorAll("[data-tab]").forEach((b) => {
        const on = b.dataset.tab === k;
        b.classList.toggle("on", on);
        b.setAttribute("aria-selected", String(on));
      });
      root.querySelectorAll("[data-panel]").forEach((s) => {
        s.hidden = s.dataset.panel !== k;
      });
      if (k === "graphique") {
        if (!boxed) {
          boxed = true;
          bindBox(S.det, DETC(key));
        } else drawBox(S.det, DETC(key));
      }
    };
    root.onclick = (e) => {
      if (e.target.closest("[data-close]")) return close();
      const tb = e.target.closest("[data-tab]");
      if (tb) return showTab(tb.dataset.tab);
      const fg = e.target.closest("[data-fig]");
      if (fg) {
        S.fig = fg.dataset.fig;
        root.querySelectorAll("[data-fig]").forEach((b) => {
          b.classList.toggle("on", b === fg);
          b.setAttribute("aria-pressed", String(b === fg));
        });
        J.$("#px-fig").innerHTML = figuresHtml(x);
        return;
      }
      const lo = e.target.closest("[data-lot]");
      if (lo) return X.C().helpers.lot(X.C().D.lots.find((z) => z.tx_id == lo.dataset.lot));
      const b = e.target.closest("[data-buy],[data-sell]");
      if (b) return X.C().helpers.trade(b.dataset.buy || b.dataset.sell, b.dataset.sell ? "sell" : "buy");
    };
    renderPlan(x);
    showTab(S.tab);
    root.querySelector(".px-dact [data-close]").focus();
  }
  function renderPlan(x) {
    const host = J.$("#px-plan-body"),
      p = x.p;
    if (!host) return;
    if (!p.listing_id) {
      host.innerHTML = '<p class="px-note">Ce titre n’a pas de cotation suivie : aucun plan de suivi possible.</p>';
      return;
    }
    if (!S.tr && !S.trErr && S.trP) {
      host.innerHTML = '<p class="px-note">Chargement du plan de suivi…</p>';
      S.trP.then(() => {
        if (J.$("#px-plan-body") === host) renderPlan(x);
      });
      return;
    }
    if (!S.tr || !root.PlanSuivi) {
      host.innerHTML = `<p class="notice err">${esc(S.trErr || "Plan de suivi indisponible")}</p>`;
      return;
    }
    const pl = planOf(p);
    if (!pl) {
      host.innerHTML = '<p class="notice err">Plan de suivi indisponible pour ce titre.</p>';
      return;
    }
    root.PlanSuivi.render(host, {
      plan: pl,
      strategies: S.tr.strategies,
      portfolio: X.C().current,
      listing: p.listing_id,
      reload: reloadTracking,
    });
  }

  /* ───────── rendu ───────── */
  root.PfDetail = { MAIN, openDetail, renderPlan };
})(typeof window !== "undefined" ? window : globalThis);
