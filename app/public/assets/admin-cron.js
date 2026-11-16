/* Administration — onglets Cron et Journaux (rattrapage, planification, journaux, fiche d’un traitement) */
(() => {
  "use strict";
  const AC = window.AdminCore;
  const { STATE, TSTATE, jobName, nf, dur, run, poll, runBar, bindJobLinks, funnelTable } = AC;
  // ───────── rattrapage automatique (cron) ─────────
  function catchupCard(k, c) {
    const open = k.open || [],
      lost = k.unrecoverable || [],
      d = k.daily || {};
    const pending = open.length + (d.waiting || 0);
    const upToDate = !pending && !lost.length && !d.given_up;
    const head =
      lost.length || d.given_up
        ? ["danger", "Des données ne sont pas récupérables"]
        : pending
          ? ["warn", "Rattrapage en cours"]
          : ["ok", "Tout est à jour"];
    return `<div class="card mt-4"><div class="row between"><h2 class="m-0">Rattrapage automatique</h2><span class="badge ${head[0]}">${head[1]}</span></div>
      <p class="small muted">À chaque passage du cron : les barres de 15 minutes manquantes des ${k.sessions_kept} dernières séances et les clôtures quotidiennes en retard sont redemandées, avec un délai croissant entre les tentatives (aucune intervention nécessaire, même après une panne de Yahoo ou du cron). Un créneau sans transaction n’est pas un manque : seuls les vrais trous sont rattrapés.</p>
      ${k.cooldown_until ? `<div class="notice">Yahoo a refusé les requêtes (429) : rattrapage en pause jusqu’à ${J.dateTime(k.cooldown_until)} UTC.</div>` : ""}
      <p class="small mt-2 mb-2">Dernière vérification des trous : <b>${k.last_check ? J.dateTime(k.last_check) + " UTC" : "jamais"}</b>${upToDate && k.last_check ? " · aucun retard connu" : ""}</p>
      ${open.length ? `<h3 class="mt-3 mb-1">Barres de 15 minutes à compléter</h3><div class="table-wrap"><table>${J.table.head(["Place", "Séance", "Titres", "Tentatives", "Depuis", "Prochaine tentative", "Constat"])}<tbody>${open.map((o) => `<tr><td>${J.esc(o.mic)}</td><td>${J.esc(o.session)}</td><td class="num">${o.titles == null ? "tous" : nf(o.titles)}</td><td class="num">${o.tries}</td><td>${J.dateTime(o.since)}</td><td>${J.dateTime(o.next_try)}</td><td class="small">${J.esc(o.note)}</td></tr>`).join("")}</tbody></table></div>` : ""}
      ${d.waiting || d.given_up ? `<h3 class="mt-3 mb-1">Clôtures quotidiennes</h3><p class="small m-0">${nf(d.waiting)} titre(s) en attente de leur dernière clôture (nouvelle tentative automatique) · ${nf(d.given_up)} abandonné(s) après 24 h (le fournisseur ne publie pas cette clôture)${d.sample && d.sample.length ? " · par ex. " + J.esc(d.sample.join(", ")) : ""}</p>` : ""}
      ${lost.length ? `<h3 class="mt-3 mb-1">Non récupérables</h3>${lost.map((u) => `<div class="reason fail mb-2"><span class="mark">✗</span><span class="small"><b>${J.esc(u.mic)} · séance du ${J.esc(u.session)}</b> · abandonnée le ${J.dateTime(u.at)} après ${u.tries} tentative(s)<br>${J.esc(u.why)}</span></div>`).join("")}` : ""}</div>`;
  }

  // ───────── Cron ─────────
  async function cron() {
    const s = await J.api("admin/cron"),
      c = s.cron,
      site = s.site;
    const yes = c.observed && c.state === "ok";
    const st = (t) => t.stats;
    AC.page.innerHTML = `${runBar()}
      <div class="card"><h2>Le cron fonctionne-t-il ?</h2>
        <div class="grid cols-4"><div class="kpi"><span class="l">Cron installé et observé</span><span class="v"><span class="badge ${yes ? "ok" : "danger"}">${yes ? "Oui" : "Non"}</span></span><span class="small muted">${J.esc(c.label)}</span></div>
          <div class="kpi"><span class="l">Dernier passage réel</span><span class="v sm">${c.last_at ? J.dateTime(c.last_at) : "jamais"}</span><span class="small muted">${c.last_at ? J.esc(c.last_done || "rien à faire") + " · durée " + dur(c.last_duration_s) : ""}</span></div>
          <div class="kpi"><span class="l">Prochain passage attendu</span><span class="v sm">${c.next_at ? J.dateTime(c.next_at) : "–"}</span><span class="small muted">réglé : toutes les <input class="u-width-56px" id="cr-int" type="number" min="1" max="60" value="${c.expected_minutes}"> min<br>${c.measured_minutes ? "observé : toutes les " + c.measured_minutes + " min (médiane des " + c.passes_seen + " derniers passages)" : "fréquence réelle : mesure en cours (" + c.passes_seen + " passage" + (c.passes_seen > 1 ? "s" : "") + " vu" + (c.passes_seen > 1 ? "s" : "") + ")"}</span></div>
          <div class="kpi"><span class="l">Clé cron sur le site</span><span class="v sm">${site.cron_key_present ? "Présente" : "Absente"}</span><span class="small muted">adresse : ${J.esc(site.cron_path)}</span></div></div>
        ${s.diagnosis.length ? `<div class="notice mt-3"><b>Diagnostic</b><ul class="u-margin-6px-0-0-18px">${s.diagnosis.map((d) => `<li class="small">${J.esc(d)}</li>`).join("")}</ul></div>` : '<p class="small muted mt-3">Aucun problème détectable.</p>'}
        ${!site.cron_key_present ? '<div class="notice err mt-3">Le site n’a pas de clé cron : l’adresse du cron répondra « clé absente ».</div>' : ""}
        <div class="row gap-s u-margin-top-12px u-flex-wrap-wrap"><button class="btn" id="cr-test">Tester le déclenchement</button><button class="btn" id="cr-run">Lancer une collecte maintenant</button><button class="btn" id="cr-maint">Lancer l’entretien maintenant</button><button class="btn" id="cr-etf">Relancer les ETF seuls</button><span class="small muted">Le test lance un passage comme le ferait le cron, sans le compter comme passage du cron. La collecte lance « Importer / mettre à jour les historiques ».</span></div>
        ${c.last_test ? `<p class="small muted mt-2">Dernier test manuel : ${J.dateTime(c.last_test.at)} · ${J.esc(c.last_test.done || "")}</p>` : ""}</div>
      <div class="card mt-4"><div class="row between"><h2 class="m-0">Ce que fait le cron</h2><button class="btn primary" id="cr-save">Enregistrer</button></div>
        <p class="small muted">Uniquement l’entretien des historiques et cotations du catalogue final (et des titres détenus). Il n’importe jamais FinanceDatabase, ne filtre jamais, ne change jamais le catalogue. Après la collecte quotidienne, les indicateurs de l’Explorer sont recalculés sans nouvelle sélection.</p>
        <div class="grid cols-2">${s.tasks
          .map((t) => {
            const k = st(t);
            return `<div class="card m-0"><div class="row between"><b>${J.esc(t.label)}</b><label class="small row gap-s"><input type="checkbox" data-t="${t.id}" data-f="enabled" ${t.enabled ? "checked" : ""}> active</label></div>
          <p class="small muted mt-1 mb-1">${J.esc(t.help)}</p>${Object.entries(t.params)
            .map(
              ([key, p]) =>
                `<div class="small">${J.esc(p.label)} <input class="u-width-64px" type="number" aria-label="${J.esc(p.label)}" data-t="${t.id}" data-f="${key}" min="${p.min}" max="${p.max}" value="${p.value}"></div>`,
            )
            .join("")}
          <p class="mt-2 mb-1"><span class="badge ${TSTATE[t.state][0]}">${TSTATE[t.state][1]}</span> <span class="small muted">${J.esc(t.state_detail)}</span></p>
          <div class="small">Dernière collecte : ${t.last ? J.dateTime(t.last.started_at) + " · " + dur(t.last.duration_s) + " (moyenne " + dur(t.avg_duration_s) + ")" : "jamais"}<br>Prochaine : ${t.next ? J.dateTime(t.next) + " UTC" : "–"}</div>
          ${k ? `<div class="table-wrap"><table><tbody><tr><td>Titres traités</td><td class="num">${nf(k.titles)}</td></tr><tr><td>Déjà à jour / complets</td><td class="num">${nf(k.up_to_date)}</td></tr><tr><td>Données ajoutées</td><td class="num">${nf(k.added)}</td></tr><tr><td>Déjà présentes</td><td class="num">${nf(k.present)}</td></tr><tr><td>Sans réponse ou en erreur</td><td class="num ${k.errors ? "warn" : ""}">${nf(k.errors)}</td></tr></tbody></table></div><div class="small muted">Dernier passage : ${J.dateTime(k.at)}</div>` : '<p class="small muted">Aucun chiffre : pas encore de collecte.</p>'}
          ${t.last ? `<div class="small"><a href="#" data-job="${t.last.id}">Détail de la dernière exécution</a></div>` : ""}</div>`;
          })
          .join("")}</div>
        ${s.maintenance ? `<p class="small muted mt-3">Dernier entretien après collecte : ${J.dateTime(s.maintenance.started_at)} · ${dur(s.maintenance.duration_s)} · ${J.esc(s.maintenance.summary || "")} <a href="#" data-job="${s.maintenance.id}">Détail</a></p>` : ""}</div>
      ${catchupCard(s.catchup, c)}
      <div class="card mt-4"><h2>Erreurs du cron <span class="small muted">· 7 derniers jours</span></h2>
        ${s.errors.length ? s.errors.map((l) => `<div class="reason ${l.level === "error" ? "fail" : "missing"} mb-2"><span class="mark">${l.level === "error" ? "✗" : "!"}</span><span class="small"><b>${J.esc(l.source === "passage du cron" ? "Passage du cron · " + l.job_type : jobName(l.job_type))}</b> · ${J.dateTime(l.at)}<br>${J.esc(l.message)} ${l.job_id ? `<a href="#" data-job="${l.job_id}">Détail</a>` : ""}</span></div>`).join("") : '<span class="muted">Aucune erreur enregistrée sur 7 jours (traitements, passages, appels).</span>'}
        ${site.log_errors && site.log_errors.length ? `<h3 class="mt-4 mb-2">Journal brut du cron (logs/cron.log) — lignes d’erreur</h3><pre class="small u-white-space-pre-wrap u-margin-0 u-max-height-200px u-overflow-auto">${J.esc(site.log_errors.join("\n"))}</pre>` : '<p class="small muted mt-3">Journal brut du cron : aucune ligne d’erreur.</p>'}
        ${site.rejected && site.rejected.length ? `<h3 class="mt-4 mb-2">Appels du cron refusés (mauvaise clé, clé absente…)</h3><pre class="small u-white-space-pre-wrap u-margin-0 u-max-height-160px u-overflow-auto">${J.esc(site.rejected.join("\n"))}</pre>` : '<p class="small muted mt-2">Aucun appel refusé.</p>'}</div>`;
    bindJobLinks();
    poll();
    J.$("#cr-save").onclick = async () => {
      const cfg = { cron_interval_minutes: +J.$("#cr-int").value };
      J.$$("[data-t]").forEach((el) => {
        const t = el.dataset.t;
        cfg[t] = cfg[t] || {};
        cfg[t][el.dataset.f] = el.type === "checkbox" ? el.checked : +el.value;
      });
      try {
        await J.post("admin/cron/save", cfg);
        J.toast("Planification enregistrée");
        AC.render();
      } catch (e) {
        J.toast(e.message);
      }
    };
    J.$("#cr-test").onclick = async () => {
      try {
        const r = await J.post("admin/cron/test");
        J.toast(r.note);
        setTimeout(AC.render, 6000);
      } catch (e) {
        J.toast(e.message);
      }
    };
    J.$("#cr-maint").onclick = () =>
      run(
        "maintenance",
        "Lancer l’entretien maintenant",
        "Sauvegarde des données utilisateur, cours, indicateurs, ETF, suivi, rétention. Démarre tout de suite ; refusé si un calcul est déjà en cours.",
      );
    J.$("#cr-etf").onclick = () =>
      run(
        "etf",
        "Relancer la similarité des ETF",
        "Recalcule seulement la similarité des ETF. Ne touche ni aux classements ni aux sauvegardes.",
      );
    J.$("#cr-run").onclick = () =>
      run(
        "history",
        "Lancer une collecte maintenant",
        "Lance « Importer / mettre à jour les historiques » sur le catalogue final.",
      );
  }

  // ───────── journaux ─────────
  const lf = { type: "", status: "", trigger: "", since: "", all: "", page: 1 };
  async function logs() {
    const r = await J.api("admin/jobs", { params: Object.fromEntries(Object.entries(lf).filter(([, v]) => v !== "")) });
    const opt = (cur, list) =>
      list.map(([v, l]) => `<option value="${v}" ${cur === v ? "selected" : ""}>${l}</option>`).join("");
    AC.page.innerHTML = `<div class="card flush"><div class="row card-bar"><select id="lf-t"><option value="">Tous les types</option>${opt(
      lf.type,
      [
        ["fdb_import", "Import FinanceDatabase"],
        ["fdb_filter", "Filtrage FinanceDatabase"],
        ["yahoo_info", "Import des informations Yahoo"],
        ["yahoo_filter", "Filtrage Yahoo"],
        ["history", "Mise à jour des historiques"],
        ["maintenance", "Entretien après collecte"],
        ["intraday", "Barres 15 min"],
        ["daily", "Clôtures quotidiennes"],
      ],
    )}</select>
      <select id="lf-s"><option value="">Tous statuts</option>${opt(
        lf.status,
        Object.entries(STATE).map(([k, v]) => [k, v[1]]),
      )}</select><select id="lf-g"><option value="">Manuel et auto</option>${opt(lf.trigger, [
        ["admin", "Manuel"],
        ["cron", "Automatique"],
      ])}</select><input id="lf-d" type="date" value="${J.esc(lf.since)}"><label class="small row gap-s"><input id="lf-a" type="checkbox" ${lf.all ? "checked" : ""}> Inclure les collectes automatiques réussies</label></div>
      <div class="table-wrap"><table>${J.table.head(["#", "Traitement", "Départ", "Durée", "Origine", "Statut", ["OK", "num"], ["Erreurs", "num"], "Résumé"])}<tbody>
      ${r.jobs.map((j) => `<tr data-job="${j.id}" class="pointer"><td>${j.id}</td><td>${J.esc(jobName(j.job_type))}</td><td>${J.dateTime(j.started_at)}</td><td>${dur(j.duration_s)}</td><td>${j.trigger_by === "admin" ? "Manuel" : "Auto"}</td><td><span class="badge ${STATE[j.status][0]}">${STATE[j.status][1]}</span></td><td class="num">${j.items_ok ?? "–"}</td><td class="num">${j.items_error}</td><td class="small muted">${J.esc(j.summary || "")}</td></tr>`).join("") || '<tr><td colspan="9" class="empty">Aucun traitement.</td></tr>'}</tbody></table></div>
      <div class="row between card-bar card-bar-sm"><span class="muted small">${nf(r.total)} traitements</span><span class="row gap-s"><button class="btn sm" id="lp" ${r.page <= 1 ? "disabled" : ""}>←</button><span class="small">Page ${r.page} / ${r.pages}</span><button class="btn sm" id="ln" ${r.page >= r.pages ? "disabled" : ""}>→</button></span></div></div>`;
    const go = () => {
      lf.type = J.$("#lf-t").value;
      lf.status = J.$("#lf-s").value;
      lf.trigger = J.$("#lf-g").value;
      lf.since = J.$("#lf-d").value;
      lf.all = J.$("#lf-a").checked ? "1" : "";
      lf.page = 1;
      logs();
    };
    ["lf-t", "lf-s", "lf-g", "lf-d", "lf-a"].forEach((i) => (J.$("#" + i).onchange = go));
    J.$("#lp").onclick = () => {
      lf.page--;
      logs();
    };
    J.$("#ln").onclick = () => {
      lf.page++;
      logs();
    };
    J.$$("tr[data-job]").forEach((tr) => (tr.onclick = () => jobDialog(tr.dataset.job)));
  }
  // Contenu du détail d'un traitement ; relu toutes les 3 s tant que le traitement tourne.
  function jobBody(d) {
    const j = d.job;
    const funnels = Object.entries(d.funnels)
      .filter(([, v]) => v.length)
      .map(
        ([k, v]) =>
          `<h4>Entonnoir ${k === "catalogue" ? "FinanceDatabase" : "Yahoo Finance"} (figé à la fin du traitement)</h4>${funnelTable(v)}`,
      )
      .join("");
    return `<p class="small">Départ ${J.dateTime(j.started_at)} · fin ${j.finished_at ? J.dateTime(j.finished_at) : "–"} · ${j.items_ok ?? "–"} réussis · ${j.items_error} erreurs · <span class="badge ${STATE[j.status][0]}">${STATE[j.status][1]}</span><br>${J.esc(j.summary || "")}</p>
      ${d.steps.length ? `<h4>Étapes</h4><div class="table-wrap"><table>${J.table.head(["#", "Étape", ["Durée", "num"], "Détail"])}<tbody>${d.steps.map((s) => `<tr><td>${s.seq}</td><td>${J.esc(s.name)}</td><td class="num">${dur(s.duration_ms / 1000)}</td><td class="small">${J.esc(s.detail || "")}</td></tr>`).join("")}</tbody></table></div>` : '<p class="muted small">Ce traitement n’a pas enregistré d’étapes détaillées.</p>'}
      ${funnels}<p class="small muted">Pour consulter les titres exclus à chaque étape : <a href="#fdb">FinanceDatabase</a> · <a href="#yahoo">Yahoo Finance</a> (état de la dernière exécution).</p>
      <h4>Messages</h4>${d.logs.map((l) => `<div class="reason ${l.level === "error" ? "fail" : "missing"} mb-2"><span class="mark">${l.level === "error" ? "✗" : "!"}</span><span class="small">${J.dateTime(l.logged_at)} · ${J.esc(l.message)}</span></div>`).join("") || '<p class="muted">Aucun message : traitement sans incident.</p>'}`;
  }
  async function jobDialog(id) {
    let d = await J.api("admin/job", { params: { id } });
    const dlg = J.dialog({
      title: "Traitement n° " + d.job.id + " · " + jobName(d.job.job_type),
      wide: true,
      body: `<div class="job-live">${jobBody(d)}</div>`,
      actions: [{ label: "Fermer", run: () => {} }],
    });
    if (!["running", "queued"].includes(d.job.status)) return;
    const timer = setInterval(async () => {
      try {
        d = await J.api("admin/job", { params: { id } });
        dlg.querySelector(".job-live").innerHTML = jobBody(d);
        if (!["running", "queued"].includes(d.job.status)) clearInterval(timer);
      } catch (e) {
        clearInterval(timer);
      }
    }, 3000);
    dlg.addEventListener("close", () => clearInterval(timer));
  }

  Object.assign(AC.tabs, { cron, logs });
  AC.jobDialog = jobDialog; // utilisée par les lignes de traitement de admin-common.js
})();
