/* Administration — onglets FinanceDatabase et Yahoo Finance */
(() => {
  "use strict";
  const AC = window.AdminCore;
  const {
    nf,
    run,
    poll,
    runBar,
    jobLine,
    bindJobLinks,
    filterForm,
    bindForm,
    saveThen,
    explainBox,
    funnelBlock,
    bindFunnel,
  } = AC;
  // ───────── FinanceDatabase ─────────
  async function fdb() {
    const s = await J.api("admin/fdb"),
      imp = s.import,
      lv = s.filters,
      f = s.funnel;
    const none = !imp.raw_rows;
    const template = J.$("#admin-fdb-template");
    AC.page.replaceChildren(template.content.cloneNode(true));
    J.$("#fdb-import-info").innerHTML = imp.load
      ? `<div class="admin-import-metrics"><div><span>Dernier import</span><strong>${J.dateTime(imp.load.loaded_at)}</strong></div><div><span>Lignes conservées</span><strong>${nf(imp.raw_rows)}</strong></div></div><p class="small muted">Source ${J.esc(imp.source)} · version ${J.esc(imp.load.commit)} · ${nf(imp.load.rows_read)} lignes lues.</p>${none ? '<p class="notice warn">Cet import utilise l’ancienne version. Relancez-le pour activer le filtrage.</p>' : ""}`
      : '<div class="admin-empty-state"><strong>Aucun import effectué</strong><p>Importez FinanceDatabase pour constituer le catalogue de départ.</p></div>';
    J.$("#fdb-import-job").innerHTML = jobLine(imp.last);
    J.$("#fdb-filter-status").innerHTML = lv.pending
      ? '<span class="badge warn">Réglages en attente</span> Les filtres ont changé depuis le dernier traitement.'
      : "Valeurs actuelles enregistrées. Le catalogue ne change qu’après un nouveau filtrage.";
    J.$("#fdb-filter-form").innerHTML = filterForm(lv, { places: s.places, categories: s.categories });
    J.$("#fdb-technical-list").innerHTML = lv.technical
      .map((t) => `<p class="small"><b>${J.esc(t.label)}</b> · ${J.esc(t.role)}</p>`)
      .join("");
    J.$("#go-filter").disabled = none;
    if (none) J.$("#go-filter").title = "Importez d’abord FinanceDatabase";
    J.$("#go-reset").disabled = !!lv.is_default;
    J.$("#fdb-results").innerHTML = none
      ? '<div class="admin-empty-state"><strong>Pas encore de résultat</strong><p>Importez les données, puis lancez le filtrage.</p></div>'
      : funnelBlock(f.steps, "catalogue", f.run);
    J.$("#fdb-next").innerHTML = none
      ? ""
      : `Résultat transmis à Yahoo : <b>${nf(f.steps[f.steps.length - 1].kept)} titres</b>. <a href="#yahoo">Continuer vers Yahoo Finance →</a>`;
    J.$$("a[data-hist]").forEach((a) => (a.onclick = () => AC.titresFilter({ final: "1", daily: a.dataset.hist })));
    bindForm();
    bindJobLinks();
    poll();
    J.$("#go-import").onclick = () =>
      run(
        "fdb_import",
        "Importer FinanceDatabase",
        "Télécharge FinanceDatabase (quelques minutes) et remplace les données brutes stockées. Aucun filtre n’est appliqué, vos portefeuilles ne sont pas touchés.",
      );
    J.$("#go-filter").onclick = () => saveThen("catalogue", "fdb_filter");
    J.$("#go-reset").onclick = async () => {
      if (
        await J.confirm(
          "Valeurs par défaut",
          "Tous les filtres FinanceDatabase reviennent à leur configuration d’origine (non appliquée tant que vous ne cliquez pas sur « Filtrer »).",
          "Restaurer",
        )
      ) {
        await J.post("admin/rules/reset", { level: "catalogue" });
        AC.render();
      }
    };
    if (!none) {
      bindFunnel("catalogue", f.steps, f.run);
      explainBox(J.$("#explain"));
    }
  }

  // ───────── Yahoo Finance ─────────
  async function yahoo() {
    const s = await J.api("admin/yahoo"),
      info = s.info,
      lv = s.filters,
      f = s.funnel,
      fin = s.final,
      st = info.stats,
      cov = fin.coverage,
      h = fin.stats,
      dp = cov.depth || {};
    const hist = fin.last_history,
      many = (x) => (x == null ? "–" : nf(x));
    AC.page.innerHTML = `${runBar()}${s.pending.map((p) => `<div class="notice mb-3">${J.esc(p)}</div>`).join("")}
      <div class="card"><h2>A · Importer les informations Yahoo</h2><p class="small muted mb-2">Pour les titres issus du filtrage FinanceDatabase : cours, devise, volume moyen, capitalisation. Pas encore d’historique.</p>
        <div class="grid cols-2"><div>${info.last ? `<p class="m-0">Dernier import : <b>${J.dateTime(info.last.finished_at || info.last.started_at)}</b></p>` : '<p class="m-0"><b>Jamais importé.</b></p>'}
          ${st ? `<div class="grid cols-4 mt-2"><div class="kpi"><span class="l">Demandés</span><span class="v">${nf(st.requested)}</span></div><div class="kpi"><span class="l">Récupérés</span><span class="v">${nf(st.recovered)}</span></div><div class="kpi"><span class="l">Manquants</span><span class="v">${nf(st.missing)}</span></div><div class="kpi"><span class="l">En erreur</span><span class="v ${st.errors ? "warn" : ""}">${nf(st.errors)}</span></div></div>` : ""}
          <p class="small muted mt-2">${nf(info.asked_now)} titres seraient interrogés maintenant.</p></div>
          <div><div class="small">${jobLine(info.last)}</div><button class="btn primary mt-3" id="go-info">Importer les informations Yahoo</button></div></div></div>
      <div class="card mt-4"><h2>B · Filtres Yahoo</h2><p class="small muted">Réapplicables aux informations déjà stockées, sans appeler Yahoo. ${lv.pending ? '<b class="warn">Filtres modifiés depuis le dernier filtrage.</b>' : ""}</p>
        ${filterForm(lv)}<div class="row gap-s"><button class="btn primary" id="go-filter" ${info.quotes ? "" : 'disabled title="Importez d’abord les informations Yahoo"'}>Filtrer</button><button class="btn" id="go-reset" ${lv.is_default ? "disabled" : ""}>Valeurs par défaut</button></div>
        <h3 class="mt-4 mb-2">Résultats du filtrage</h3>${funnelBlock(f.steps, "yahoo", f.run)}</div>
      <div id="explain" class="mt-4"></div>
      <div class="card card-accent mt-4"><h2>C · Mon catalogue final et ses historiques</h2>
        <div class="grid cols-4"><div class="kpi"><span class="l">Titres du catalogue</span><span class="v">${nf(fin.total)}</span><span class="small muted">${nf(fin.equity)} actions · ${nf(fin.etf)} ETF</span></div>
          <div class="kpi"><span class="l">Cinq ans complets</span><span class="v">${nf(dp.complete)}</span><span class="small muted">${nf(dp.target || fin.full)} séances présentes${dp.complete ? ' · <a href="#titres" data-hist="complete">voir</a>' : ""}</span></div>
          <div class="kpi"><span class="l">Titres récents</span><span class="v">${nf(dp.recent)}</span><span class="small muted">plus jeunes que cinq ans : rien de plus ancien chez Yahoo${dp.recent ? ' · <a href="#titres" data-hist="recent">voir</a>' : ""}</span></div>
          <div class="kpi"><span class="l">Séances manquantes</span><span class="v ${dp.incomplete ? "warn" : ""}">${nf(dp.incomplete)}</span><span class="small muted">${nf(dp.holes)} jours omis par Yahoo${dp.incomplete ? ' · <a href="#titres" data-hist="incomplete">voir les titres</a>' : ""}</span></div></div>
        <p class="small mt-2">À traiter : <b class="${dp.pending ? "warn" : ""}">${nf(dp.pending)}</b> titres pas encore vérifiés${dp.pending ? ' (<a href="#titres" data-hist="pending">voir</a>)' : ""} · <span class="${dp.absent ? "warn" : ""}">${nf(dp.absent)} sans aucun cours${dp.absent ? ' (<a href="#titres" data-hist="absent">voir</a>)' : ""}</span> · ${nf(dp.unavailable)} indisponibles chez Yahoo · <span class="${dp.error ? "warn" : ""}">${nf(dp.error)} en erreur (repris automatiquement)</span>. Une seule définition de « complet » : <b>${nf(dp.target || fin.full)} séances</b> présentes, comme dans le traitement « Historique de cinq ans ». Un titre plus jeune ne peut pas les avoir ; les fermetures exceptionnelles d’une place ne comptent pas comme des séances manquantes.</p>
        <p class="small muted mt-2 mb-2">Cotations principales retenues : ${nf(fin.total)}${fin.held_extra ? ` · ${fin.held_extra} titre(s) détenu(s) hors catalogue, toujours valorisés` : ""}. Dernière séance en base : ${cov.last_day ? J.date(cov.last_day) : "–"}. Dernière mise à jour des historiques : <b>${hist ? J.dateTime(hist.finished_at || hist.started_at) : "jamais"}</b>.</p>
        <button class="btn primary lg" id="go-history" ${fin.total ? "" : 'disabled title="Le catalogue final est vide : filtrez d’abord Yahoo"'}>Importer / mettre à jour les historiques</button>
        <button class="btn ml-2" id="go-gaps" ${fin.total ? "" : "disabled"} title="Un appel Yahoo par titre dont l’année est incomplète">Combler les clôtures manquantes</button>
        <button class="btn ml-2" id="go-volumes" ${fin.total ? "" : "disabled"} title="Un appel Yahoo par titre : un an de volumes quotidiens">Collecter les volumes quotidiens</button>
        <button class="btn ml-2" id="go-deep" ${fin.total ? "" : "disabled"} title="Un appel Yahoo par titre : jusqu’à ${dp.target || fin.full} séances de clôtures et de volumes. Le cron complète aussi les nouveaux titres et les erreurs.">Historique de cinq ans</button>
        <p class="small mt-2">Volumes quotidiens : <b>${nf(cov.volume_checked)}</b> titres traités sur <b>${nf(cov.volume_titles)}</b> · liquidité réelle pour <b>${nf(cov.volume_real_liquidity)}</b> titres · <span class="${cov.volume_errors ? "warn" : ""}">${nf(cov.volume_errors)} en échec (repris automatiquement)</span> · dernière collecte : <b>${cov.volume_last ? J.dateTime(cov.volume_last) : "jamais"}</b>. L’entretien automatique renouvelle les volumes à chaque nouvelle séance.</p>
        <p class="small mt-2">Clôtures manquantes sur la dernière année : <b>${nf(cov.gap_days)}</b> séances sur <b>${nf(cov.gap_titles)}</b> titres${cov.gap_titles ? ` (dont ${nf(cov.gap_small)} titres à 1 ou 2 séances seulement)` : ""}. Un titre déjà essayé aujourd’hui n’est pas redemandé : s’il reste incomplet, c’est que Yahoo n’a pas ces jours.</p>
        <p class="small muted mt-2">Récupère les clôtures quotidiennes récentes manquantes (sans retélécharger l’existant ; la profondeur de ${fin.full} séances est assurée par « Historique de cinq ans » et par le cron), complète les barres de 15 minutes des deux dernières séances, puis recalcule les indicateurs. Le cron entretient ensuite ces historiques automatiquement.</p>
        ${
          h
            ? `<h3 class="mt-4 mb-2">Résultat de la dernière mise à jour</h3><div class="table-wrap"><table>${J.table.head(["", ["Titres", "num"], ["Déjà à jour", "num"], ["Interrogés", "num"], ["Données ajoutées", "num"], ["Déjà présentes", "num"], ["Sans réponse", "num"]])}<tbody>
          <tr><td>Clôtures quotidiennes</td><td class="num">${many(h.daily.titles)}</td><td class="num">${many(h.daily.up_to_date)}</td><td class="num">${many(h.daily.asked)}</td><td class="num">${many(h.daily.added)}</td><td class="num">${many(h.daily.present)}</td><td class="num ${h.daily.errors ? "warn" : ""}">${many(h.daily.errors)}</td></tr>
          <tr><td>Barres de 15 minutes</td><td class="num">${many(h.intraday.titles)}</td><td class="num">${many(h.intraday.up_to_date)}</td><td class="num">${many(h.intraday.asked)}</td><td class="num">${many(h.intraday.added)}</td><td class="num">${many(h.intraday.present)}</td><td class="num ${h.intraday.errors ? "warn" : ""}">${many(h.intraday.errors)}</td></tr></tbody></table></div>
          ${h.intraday.unknown_hours ? `<p class="small muted">${nf(h.intraday.unknown_hours)} titres de places sans horaires connus : clôtures quotidiennes seulement.</p>` : ""}<div class="small">${jobLine(hist)}</div>`
            : ""
        }</div>`;
    bindForm();
    bindJobLinks();
    poll();
    J.$("#go-info").onclick = () =>
      run(
        "yahoo_info",
        "Importer les informations Yahoo",
        "Interroge Yahoo Finance pour " +
          nf(info.asked_now) +
          " titres (plusieurs minutes). Aucun historique n’est téléchargé.",
      );
    J.$("#go-filter").onclick = () => saveThen("prefilter", "yahoo_filter");
    J.$("#go-reset").onclick = async () => {
      if (
        await J.confirm(
          "Valeurs par défaut",
          "Les filtres Yahoo reviennent à leur configuration d’origine (non appliquée tant que vous ne cliquez pas sur « Filtrer »).",
          "Restaurer",
        )
      ) {
        await J.post("admin/rules/reset", { level: "prefilter" });
        AC.render();
      }
    };
    J.$("#go-history").onclick = () =>
      run(
        "history",
        "Importer / mettre à jour les historiques",
        "Travaille sur les " +
          nf(fin.total) +
          " titres du catalogue final. Ça peut durer longtemps la première fois ; la progression s’affiche en haut de page.",
      );
    J.$("#go-gaps").onclick = () =>
      run(
        "gaps",
        "Combler les clôtures manquantes",
        "Interroge Yahoo (un appel par titre) pour chaque titre dont la dernière année a des séances manquantes, ajoute uniquement les jours absents, puis recalcule les indicateurs. Plusieurs minutes ; reprenable si Yahoo limite les appels.",
      );
    J.$("#go-deep").onclick = () =>
      run(
        "history_deep",
        "Historique de cinq ans",
        "Interroge Yahoo (un appel par titre, 4 en parallèle) pour compléter jusqu’à 1 260 séances de clôtures et de volumes pour tout le catalogue, sans jamais modifier une clôture existante, puis recalcule les indicateurs. Plusieurs dizaines de minutes ; reprenable : les titres déjà traités sont sautés. Aucune stratégie n’est modifiée : les scores n’utilisent que leurs périodes actives.",
      );
    J.$("#go-volumes").onclick = () =>
      run(
        "volumes",
        "Collecter les volumes quotidiens",
        "Interroge Yahoo (un appel par titre, 4 en parallèle) pour récupérer un an de volumes quotidiens, sans toucher aux clôtures, puis recalcule liquidités, indicateurs et classements. Reprenable : les titres déjà traités sont sautés.",
      );
    bindFunnel("yahoo", f.steps, f.run);
    explainBox(J.$("#explain"));
  }

  Object.assign(AC.tabs, { fdb, yahoo });
})();
