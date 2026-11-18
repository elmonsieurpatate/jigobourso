/* Page « Mes portefeuilles » : liste, état et actions d'administration. Les règles et les refus sont côté serveur (services/portfolio_admin.php, cash.php). */
(async () => {
  if (!(await J.init("portefeuilles"))) return;
  const page = J.$("#page");
  let icons = [];

  const model = (p) =>
    p.cash_model === "cash"
      ? PFAdmin.KIND_LABEL[p.kind]
      : '<span class="badge wait" title="Sans liquidités : résultats calculés comme avant">Ancien modèle</span>';

  function card(p) {
    const cash = p.cash_model === "cash";
    const btn = (a, l, cls = "") =>
      `<button type="button" class="btn sm ${cls}" data-a="${a}" data-id="${p.id}">${l}</button>`;
    return `<div class="card tight">
      <div class="row between u-align-items-flex-start">
        <div class="row u-flex-wrap-nowrap u-align-items-flex-start u-min-width-0">
          <span class="sui-ico" aria-hidden="true">${J.esc(p.icon || "💼")}</span>
          <div class="u-min-width-0"><a href="portefeuilles.html?id=${p.id}"><b>${J.esc(p.name)}</b></a> ${model(p)}${p.is_default ? ' <span class="badge ok">Par défaut</span>' : ""}${p.archived ? ' <span class="badge">Archivé</span>' : ""}
            <div class="small muted">${p.description ? J.esc(p.description) : "Aucune description."}</div></div>
        </div>
        <div class="u-text-align-right"><div class="small muted">Valeur des titres</div><b>${p.totals.value == null ? "—" : J.eur(p.totals.value)}</b>
          ${cash ? `<div class="small muted">Liquidités : <b>${J.eur(p.cash.balance)}</b></div>` : ""}</div>
      </div>
      <div class="row gap-s mt-2">${p.archived ? btn("unarchive", "Désarchiver") : btn("edit", "Modifier")}${cash && !p.archived ? btn("deposit", "Ajouter de l’argent", "primary") + btn("withdrawal", "Retirer de l’argent") : ""}${!cash && !p.archived ? btn("convert", "Convertir…") : ""}${!p.archived && !p.is_default ? btn("default", "Par défaut") : ""}${p.archived ? "" : btn("archive", "Archiver") + btn("reset", "Réinitialiser")}${btn("delete", "Supprimer", "danger")}</div></div>`;
  }

  const table = (list) => `<div class="u-display-grid u-gap-12px">${list.map(card).join("")}</div>`;

  const fail = (e) =>
    J.dialog({
      title: "Action impossible",
      body: `<p>${J.esc(e.message)}</p>`,
      actions: [{ label: "Fermer", run: () => {} }],
    });

  async function render() {
    const r = await J.api("portfolios");
    icons = r.icons;
    const active = r.portfolios.filter((p) => !p.archived),
      archived = r.portfolios.filter((p) => p.archived);
    page.innerHTML =
      `<h2 class="mb-2">Portefeuilles actifs</h2>${active.length ? table(active) : '<p class="muted">Aucun portefeuille actif.</p>'}` +
      (archived.length
        ? `<h2 class="mt-4 mb-2">Archivés</h2><p class="small muted mb-2">Consultables, en lecture seule, exclus du bilan courant.</p>${table(archived)}`
        : "");
    J.$$("[data-a]", page).forEach((b) => {
      const p = r.portfolios.find((x) => x.id == b.dataset.id);
      b.onclick = () => act(b.dataset.a, p).catch(fail);
    });
  }

  async function act(a, p) {
    const done = () => render();
    const portfolio = { id: p.id, name: p.name, icon: p.icon, description: p.description, archived: p.archived };
    if (a === "edit") return PFAdmin.edit({ portfolio, icons, onDone: done });
    if (a === "deposit" || a === "withdrawal") return PFAdmin.money({ portfolioId: p.id, kind: a, onDone: done });
    if (a === "convert") return PFAdmin.convert({ portfolio, onDone: done });
    if (a === "default") {
      await J.post("portfolio/default", { id: p.id });
      return done();
    }
    if (a === "archive") return PFAdmin.archive({ portfolio, onDone: done });
    if (a === "unarchive") {
      await J.post("portfolio/unarchive", { id: p.id });
      return done();
    }
    if (a === "reset") return PFAdmin.reset({ portfolio: { ...portfolio, cash_model: p.cash_model }, onDone: done });
    if (a === "delete") return PFAdmin.remove({ portfolio, onDone: done });
  }

  J.$("#pfm-new").onclick = () =>
    PFAdmin.create({ icons, onDone: (id) => (location.href = "portefeuilles.html?id=" + id) });
  render().catch(fail);
})();
