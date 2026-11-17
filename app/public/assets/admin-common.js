/* Administration — noyau partagé : traitements (lancement et suivi), formulaire de règles, entonnoir.
   Expose window.AdminCore ; les onglets (admin-sources.js, admin-titres.js, admin-cron.js, admin-users.js) s'y enregistrent dans AdminCore.tabs ;
   admin.js (chargé en dernier) fixe AdminCore.page / tab() / render() puis affiche l'onglet. */
(() => {
  "use strict";
  const AC = (window.AdminCore = { tabs: {}, page: null, tab: () => "fdb", render: () => {} });
  const STATE = {
    completed: ["ok", "Terminé"],
    completed_with_errors: ["warn", "Terminé avec erreurs"],
    failed: ["danger", "Échec"],
    running: ["info", "En cours"],
    queued: ["info", "En attente"],
    paused: ["warn", "En pause"],
    interrupted: ["danger", "Interrompu"],
  };
  const TSTATE = {
    ok: ["ok", "Fonctionne"],
    late: ["warn", "En retard"],
    error: ["danger", "En erreur"],
    inactive: ["", "Désactivée"],
    never: ["warn", "Jamais exécutée"],
    running: ["info", "En cours"],
  };
  const JOBNAME = {
    fdb_import: "Import FinanceDatabase",
    fdb_filter: "Filtrage FinanceDatabase",
    yahoo_info: "Import des informations Yahoo",
    yahoo_filter: "Filtrage Yahoo",
    history: "Import / mise à jour des historiques",
    gaps: "Clôtures manquantes",
    volumes: "Volumes quotidiens",
    history_deep: "Historique de cinq ans",
    metrics: "Indicateurs et classements",
    etf: "Similarité des ETF",
    maintenance: "Entretien après collecte",
    catchup: "Rattrapage des données manquantes",
    intraday: "Barres de 15 min",
    daily: "Clôtures quotidiennes",
    catalogue: "Import FinanceDatabase (ancien)",
    nightly: "Analyse de nuit (ancienne)",
  };
  const jobName = (t) =>
    JOBNAME[t] || (t.includes(":") ? (JOBNAME[t.split(":")[0]] || t.split(":")[0]) + " · " + t.split(":")[1] : t);
  const nf = J.int;
  const dur = (s) =>
    s == null
      ? "–"
      : s < 90
        ? Math.round(s) + " s"
        : s < 5400
          ? Math.round(s / 60) + " min"
          : (s / 3600).toFixed(1).replace(".", ",") + " h";
  const MANUAL = [
    "fdb_import",
    "fdb_filter",
    "yahoo_info",
    "yahoo_filter",
    "history",
    "gaps",
    "volumes",
    "history_deep",
    "maintenance",
    "metrics",
    "etf",
  ];

  // ───────── lancement et suivi d'un traitement ─────────
  let polling = false;
  async function run(job, label, confirmText) {
    if (confirmText && !(await J.confirm(label, confirmText, "Lancer"))) return false;
    try {
      const stamp = new Date(Date.now() - 4000).toISOString().slice(0, 19).replace("T", " ");
      const r = await J.post("admin/run", { job });
      J.toast(r.label + " lancé");
      poll(stamp, job);
      return true;
    } catch (e) {
      J.toast(e.message);
      return false;
    }
  }
  async function poll(launchedAt, launchedJob) {
    if (polling) return;
    polling = true;
    let bar = J.$("#runbar");
    if (!bar) {
      AC.page.insertAdjacentHTML("afterbegin", '<div id="runbar" class="notice is-off"></div>');
      bar = J.$("#runbar");
    }
    let seen = false;
    const done = () => {
      polling = false;
      J.toast("Traitement terminé");
      AC.render();
    };
    for (let i = 0; i < 2000; i++) {
      let r;
      try {
        r = await J.api("admin/jobs", { params: { status: "running" } });
      } catch (e) {
        break;
      }
      const list = r.jobs.filter((j) => MANUAL.includes(j.job_type));
      if (list.length) {
        seen = true;
        bar = J.$("#runbar") || bar;
        bar.classList.remove("is-off");
        bar.innerHTML =
          '<span class="spinner"></span> <b>' +
          list.map((j) => J.esc(jobName(j.job_type))).join(", ") +
          "</b> en cours · " +
          J.esc(list[0].summary || "démarrage…") +
          ' <a href="#logs">Journaux</a>';
      } else {
        if (bar) bar.classList.add("is-off");
        if (seen) return done();
        if (launchedAt) {
          const r2 = await J.api("admin/jobs", { params: { since: launchedAt } }).catch(() => ({ jobs: [] }));
          if (r2.jobs.some((j) => j.job_type === launchedJob && !["running", "queued"].includes(j.status)))
            return done();
        } else if (i > 2) break;
      }
      await new Promise((res) => setTimeout(res, 2000));
    }
    polling = false;
  }
  const runBar = () => '<div id="runbar" class="notice is-off"></div>';
  const when = (v) => (v ? J.dateTime(v) : "jamais");
  const jobLine = (j) =>
    j
      ? `<span class="badge ${STATE[j.status][0]}">${STATE[j.status][1]}</span> ${J.dateTime(j.started_at)} · durée ${dur(j.duration_s)}${j.items_error ? ` · <span class="warn">${j.items_error} erreurs</span>` : ""}<div class="small muted">${J.esc(j.summary || "")} <a href="#" data-job="${j.id}">Détail</a></div>`
      : '<span class="muted">Jamais lancé</span>';
  const bindJobLinks = () =>
    J.$$("a[data-job]").forEach(
      (a) =>
        (a.onclick = (e) => {
          e.preventDefault();
          AC.jobDialog(a.dataset.job);
        }),
    );

  // ───────── formulaire de filtres (règles éditables) ─────────
  function filterForm(lv, { places, categories } = {}) {
    const row = (r) => {
      const c = r.current;
      let ctl = "";
      if (r.id === "types")
        ctl = ["equity", "etf"]
          .map(
            (k) =>
              `<label class="row gap-s small"><input type="checkbox" data-rule="types" data-f="${k}" ${c[k] ? "checked" : ""}> ${k === "etf" ? "ETF" : "Actions"}</label>`,
          )
          .join(" ");
      else if (r.key)
        ctl = `<span class="row gap-s"><input class="u-width-130px" type="number" aria-label="${J.esc(r.label)}" data-rule="${r.id}" data-f="${r.key}" step="${r.step}" min="0" max="${r.max}" value="${c[r.key]}"> <span class="small muted">${J.esc(r.unit)}</span></span>`;
      return `<div class="frow"><label class="row gap-s u-align-items-flex-start"><input type="checkbox" data-rule="${r.id}" data-f="enabled" ${c.enabled ? "checked" : ""}><span><b>${J.esc(r.label)}</b>${r.is_default ? "" : ' <span class="badge warn">modifié</span>'}<span class="small muted u-display-block">${J.esc(r.role)}</span></span></label>
        ${ctl ? `<div class="u-margin-4px-0-0-26px">${ctl}</div>` : ""}${r.id === "markets" ? placePicker(r, places) : r.id === "categories" ? catPicker(r, categories) : ""}
        <details class="u-margin-left-26px"><summary class="small muted pointer">Pourquoi ce filtre ?</summary><p class="small">${J.esc(r.help)}</p></details></div>`;
    };
    const groups = {};
    lv.rules.forEach((r) => (groups[r.group] = groups[r.group] || []).push(r));
    const names = { ...lv.groups, liquidity: "Prix, ancienneté du cours et liquidité" };
    return Object.entries(groups)
      .map(
        ([g, rs]) =>
          `<section class="admin-rule-group"><h3>${J.esc(names[g] || g)}</h3><div class="admin-rule-list">${rs.map(row).join("")}</div></section>`,
      )
      .join("");
  }
  function placePicker(r, places) {
    const sel = new Set(r.current.values);
    return `<div class="admin-picker"><div class="admin-picker-toolbar"><input id="pl-q" type="search" placeholder="Rechercher une place ou un code" aria-label="Rechercher une place"><span class="small muted" id="pl-n"></span>
      <div class="admin-picker-actions"><button class="btn sm" type="button" id="pl-all">Tout cocher</button><button class="btn sm" type="button" id="pl-none">Tout décocher</button><button class="btn sm" type="button" id="pl-def">Par défaut</button></div></div>
      <div id="pl-list" class="admin-place-list">
      ${places.map((p) => `<label class="admin-place" data-search="${J.esc((p.mic + " " + p.name).toLowerCase())}"><input type="checkbox" data-mic="${J.esc(p.mic)}" data-def="${p.default ? 1 : 0}" ${sel.has(p.mic) ? "checked" : ""}><span class="admin-place-copy"><span class="admin-place-name"><b>${J.esc(p.mic)}</b> ${J.esc(p.name)}</span><small>${nf(p.equity)} actions · ${nf(p.etf)} ETF${p.hours_known ? "" : " · sans barres 15 min"}</small></span></label>`).join("") || '<span class="muted small">Importez FinanceDatabase pour voir toutes les places disponibles.</span>'}</div>
      <p class="small muted mt-1">Les places sans horaires connus n’ont que les clôtures quotidiennes.</p></div>`;
  }
  function catPicker(r, cats) {
    const sel = new Set(r.current.values);
    return `<details class="u-margin-6px-0-0-26px"><summary class="small pointer">Choisir les catégories à exclure (${r.current.values.length} cochées)</summary><div class="u-display-grid u-grid-template-columns-v1 u-gap-2px-12px u-max-height-200px u-overflow-auto u-margin-top-6px">
      ${(cats || []).map((c) => `<label class="small"><input type="checkbox" data-cat="${J.esc(c.category)}" ${sel.has(c.category) ? "checked" : ""}> ${J.esc(c.category)} <span class="muted">${nf(c.n)}</span></label>`).join("") || '<span class="muted small">Aucune catégorie : importez FinanceDatabase.</span>'}</div></details>`;
  }
  function bindForm() {
    const q = J.$("#pl-q");
    if (!q) return;
    const labels = () => J.$$("#pl-list label[data-search]");
    const count = () => {
      J.$("#pl-n").textContent = J.$$("#pl-list input:checked").length + " places cochées sur " + labels().length;
    };
    q.oninput = () => {
      const t = q.value.trim().toLowerCase();
      labels().forEach((l) => (l.style.display = !t || l.dataset.search.includes(t) ? "" : "none"));
    };
    const vis = () => labels().filter((l) => l.style.display !== "none");
    J.$("#pl-all").onclick = () => {
      vis().forEach((l) => (l.querySelector("input").checked = true));
      count();
    };
    J.$("#pl-none").onclick = () => {
      vis().forEach((l) => (l.querySelector("input").checked = false));
      count();
    };
    J.$("#pl-def").onclick = () => {
      labels().forEach((l) => {
        const i = l.querySelector("input");
        i.checked = i.dataset.def === "1";
      });
      count();
    };
    J.$("#pl-list").onchange = count;
    count();
  }
  function collectForm() {
    const cfg = {};
    J.$$("[data-rule]").forEach((el) => {
      const id = el.dataset.rule;
      cfg[id] = cfg[id] || {};
      if (el.type === "checkbox") cfg[id][el.dataset.f] = el.checked;
      else cfg[id][el.dataset.f] = el.value === "" ? null : +el.value;
    });
    if (J.$("#pl-list")) {
      cfg.markets = cfg.markets || {};
      cfg.markets.values = J.$$("#pl-list input[data-mic]:checked").map((i) => i.dataset.mic);
    }
    if (J.$$("[data-cat]").length) {
      cfg.categories = cfg.categories || {};
      cfg.categories.values = J.$$("[data-cat]:checked").map((i) => i.dataset.cat);
    }
    return cfg;
  }
  async function saveThen(level, next) {
    try {
      await J.post("admin/rules/save", { level, config: collectForm() });
    } catch (e) {
      J.toast(e.message);
      return;
    }
    if (next) await run(next);
    else {
      J.toast("Filtres enregistrés");
      AC.render();
    }
  }

  // ───────── entonnoir ─────────
  function funnelTable(steps, { onItems, all = false } = {}) {
    const max = Math.max(1, ...steps.map((s) => s.before));
    steps = steps.filter(
      (s, i) => all || i === 0 || i === steps.length - 1 || s.removed > 0 || ["primary", "no_data"].includes(s.key),
    );
    return `<div class="table-wrap"><table class="funnel">${J.table.head(["Étape", "Règle et seuil", ["Avant", "num"], ["Écartés", "num"], ["Conservés", "num"], { label: "", width: 130 }, ...(onItems ? [""] : [])])}<tbody>
      ${steps
        .map(
          (s) => `<tr><td><b>${J.esc(s.label)}</b>${
            s.info && s.info.by_kind && Object.keys(s.info.by_kind).length
              ? `<div class="small muted">${Object.entries(s.info.by_kind)
                  .map(([k, v]) => `${nf(v)} ${k === "etf" ? "ETF" : "actions"}`)
                  .join(" · ")}</div>`
              : ""
          }${
            s.info && s.info.quality
              ? `<div class="small muted">${Object.entries(s.info.quality)
                  .map(([k, v]) => `${nf(v)} ${J.esc(k)}`)
                  .join(" · ")}</div>`
              : ""
          }</td>
        <td class="small">${J.esc(s.rule)}${s.info && s.info.enabled === false ? ' <span class="badge">désactivée</span>' : ""}</td><td class="num">${nf(s.before)}</td><td class="num ${s.removed ? "warn" : ""}">${s.removed ? "− " + nf(s.removed) : "0"}</td><td class="num"><b>${nf(s.kept)}</b></td>
        <td><div class="meter"><div class="meter-fill" data-style="width:${(100 * s.kept) / max}%"></div></div></td>
        ${onItems ? `<td class="num"><button class="btn sm" data-step="${s.key}">Voir les titres</button></td>` : ""}</tr>`,
        )
        .join("")}</tbody></table></div>`;
  }
  const itemsLatest = J.latest(); // une réponse tardive d'un ancien panneau ou d'une ancienne frappe n'écrase pas le panneau courant
  async function itemsPanel(stage, step, label, host) {
    const st = { q: "", kind: "", mic: "", page: 1 };
    host.innerHTML = "";
    async function load() {
      const ticket = itemsLatest.next();
      let r;
      try {
        r = await J.api("admin/funnel/items", {
          params: { stage, step, ...Object.fromEntries(Object.entries(st).filter(([, v]) => v !== "")) },
        });
      } catch (e) {
        if (itemsLatest.isCurrent(ticket)) host.innerHTML = `<div class="notice err mt-4">${J.esc(e.message)}</div>`;
        return;
      }
      if (!itemsLatest.isCurrent(ticket)) return;
      const cat = stage === "catalogue";
      host.innerHTML = `<div class="card flush mt-4"><div class="row between card-bar"><h3 class="m-0">Titres · ${J.esc(label)}</h3><button class="btn sm" id="ip-close">Fermer</button></div>
        <div class="row card-bar card-bar-sub"><input class="u-flex-1 u-min-width-160px" id="ip-q" type="search" placeholder="Nom, symbole ou ISIN" value="${J.esc(st.q)}"><select id="ip-k"><option value="">Actions et ETF</option><option value="equity" ${st.kind === "equity" ? "selected" : ""}>Actions</option><option value="etf" ${st.kind === "etf" ? "selected" : ""}>ETF</option></select><input class="u-width-130px" id="ip-m" placeholder="Place (ex. XETR)" value="${J.esc(st.mic)}"></div>
        <div class="table-wrap"><table>${J.table.head([
          "Titre",
          "Place",
          "Type",
          cat ? "Motif" : "Statut / motif",
          ...(cat
            ? []
            : [
                ["Cours (€)", "num"],
                ["Liquidité (€/jour)", "num"],
              ]),
        ])}<tbody>
        ${
          r.rows
            .map(
              (
                x,
              ) => `<tr ${x.id ? `data-id="${x.id}"` : ""} class="pointer"><td><b>${J.esc(x.name)}</b>${x.held ? ' <span class="badge accent">détenu</span>' : ""}<div class="small muted">${J.esc(x.symbol)} · ${J.esc(x.isin || "")} · ${J.esc(x.country || "")}</div></td><td>${J.esc(x.mic)}</td><td>${x.kind === "etf" ? "ETF" : "Action"}</td>
          <td class="small">${J.esc(cat ? x.removed_reason || "conservée" : x.excluded_reason || x.status + (x.is_primary ? " · principale" : ""))}</td>${cat ? "" : `<td class="num">${x.price_eur != null ? J.num(x.price_eur, 2) : "–"}</td><td class="num">${x.liquidity_eur != null ? J.num(x.liquidity_eur, 0) : "–"}</td>`}</tr>`,
            )
            .join("") || `<tr><td colspan="6" class="empty">Aucun titre.</td></tr>`
        }</tbody></table></div>
        <div class="row between card-bar card-bar-sm"><span class="muted small">${nf(r.total)} titres</span><span class="row gap-s"><button class="btn sm" id="ip-p" ${r.page <= 1 ? "disabled" : ""}>←</button><span class="small">Page ${r.page} / ${r.pages}</span><button class="btn sm" id="ip-n" ${r.page >= r.pages ? "disabled" : ""}>→</button></span></div></div>`;
      const go = () => {
        st.q = J.$("#ip-q").value.trim();
        st.kind = J.$("#ip-k").value;
        st.mic = J.$("#ip-m").value.trim().toUpperCase();
        st.page = 1;
        load();
      };
      let t;
      J.$("#ip-q").oninput = () => {
        clearTimeout(t);
        t = setTimeout(go, 350);
      };
      J.$("#ip-k").onchange = go;
      J.$("#ip-m").onchange = go;
      J.$("#ip-p").onclick = () => {
        st.page--;
        load();
      };
      J.$("#ip-n").onclick = () => {
        st.page++;
        load();
      };
      J.$("#ip-close").onclick = () => (host.innerHTML = "");
      J.$$("tr[data-id]", host).forEach(
        (tr) => (tr.onclick = () => (location.href = "titre.html?id=" + tr.dataset.id)),
      );
      host.scrollIntoView({ block: "nearest" });
    }
    await load();
  }
  function explainBox(host) {
    host.innerHTML = `<div class="card"><h2>Pourquoi ce titre a-t-il disparu ?</h2><div class="row u-gap-10px"><input class="u-flex-1" id="ex-q" placeholder="Nom, symbole ou ISIN (ex. DVDG.DE)"><button class="btn primary" id="ex-go">Expliquer</button></div><div id="ex-out" class="mt-3"></div></div>`;
    const latest = J.latest();
    const go = async () => {
      const out = J.$("#ex-out", host);
      out.innerHTML = '<span class="spinner"></span>';
      const t = latest.next();
      try {
        const r = await J.api("admin/funnel/explain", { params: { q: J.$("#ex-q", host).value } });
        if (!latest.isCurrent(t)) return;
        const mark = { passed: ["ok", "✓"], removed: ["fail", "✗"], not_reached: ["missing", "–"] };
        const line = (t) =>
          `<div class="reason ${mark[t.result][0]} mb-1"><span class="mark">${mark[t.result][1]}</span><span class="small"><b>${J.esc(t.label)}</b> · ${J.esc(t.detail || "")}${t.rule && t.result === "removed" ? `<br><span class="muted">${J.esc(t.rule)}</span>` : ""}</span></div>`;
        const warn =
          r.pending.catalogue || r.pending.yahoo
            ? `<div class="notice">Des règles ont été modifiées sans être appliquées : ce diagnostic montre le dernier résultat calculé, pas la configuration actuelle.</div>`
            : "";
        out.innerHTML =
          warn +
          (r.results
            .map(
              (
                x,
              ) => `<div class="mb-4"><b>${J.esc(x.raw.name)}</b> <span class="muted small">${J.esc(x.raw.symbol)} · ${J.esc(x.raw.mic)} · ${J.esc(x.raw.isin || "")}</span>
          <h4 class="mt-2 mb-1">Catalogue FinanceDatabase</h4>${x.catalogue.map(line).join("")}${x.yahoo.length ? '<h4 class="mt-2 mb-1">Yahoo Finance</h4>' + x.yahoo.map(line).join("") : ""}
          ${x.listing && x.listing.held ? '<p class="small">Titre détenu : toujours suivi et valorisé, même s’il est exclu.</p>' : ""}</div>`,
            )
            .join("") ||
            '<p class="muted">Aucun titre trouvé dans les données FinanceDatabase stockées. Si le catalogue n’a jamais été importé dans cette version, lancez un import complet.</p>');
      } catch (e) {
        if (!latest.isCurrent(t)) return;
        out.innerHTML = `<div class="notice err">${J.esc(e.message)}</div>`;
      }
    };
    J.$("#ex-go", host).onclick = go;
    J.$("#ex-q", host).onkeydown = (e) => {
      if (e.key === "Enter" && !e.isComposing) go();
    };
  }

  const funnelBlock = (steps, stage, run_) =>
    `<div class="row between mb-2"><span class="small muted">${run_ ? `Dernier filtrage : ${J.dateTime(run_.created_at)}` : "Pas encore de filtrage : état actuel de la base"}</span><label class="small row gap-s"><input type="checkbox" id="fn-all"> Afficher aussi les étapes sans effet</label></div><div id="fun">${funnelTable(steps, { onItems: true })}</div><div id="items"></div>`;
  function bindFunnel(stage, steps, run_) {
    const draw = () => {
      J.$("#fun").innerHTML = funnelTable(steps, { onItems: true, all: J.$("#fn-all").checked });
      bind();
    };
    const bind = () =>
      J.$$("#fun button[data-step]").forEach(
        (b) =>
          (b.onclick = () =>
            itemsPanel(stage, b.dataset.step, steps.find((s) => s.key === b.dataset.step).label, J.$("#items"))),
      );
    J.$("#fn-all").onchange = draw;
    bind();
  }

  Object.assign(AC, {
    STATE,
    TSTATE,
    JOBNAME,
    MANUAL,
    jobName,
    nf,
    dur,
    run,
    poll,
    runBar,
    when,
    jobLine,
    bindJobLinks,
    filterForm,
    placePicker,
    catPicker,
    bindForm,
    collectForm,
    saveThen,
    funnelTable,
    itemsPanel,
    explainBox,
    funnelBlock,
    bindFunnel,
  });
})();
