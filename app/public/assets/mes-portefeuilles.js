/* Page « Mes portefeuilles » : liste, état et actions d'administration. Les règles et les refus sont côté serveur (services/portfolio_admin.php, cash.php). */
(() => {
  const page = J.$("#page");
  let icons = [];

  const model = (p) =>
    p.cash_model === "cash"
      ? PFAdmin.KIND_LABEL[p.kind]
      : '<span class="badge wait" title="Sans liquidités : résultats calculés comme avant">Ancien modèle</span>';

  function row(p) {
    const cash = p.cash_model === "cash";
    const btn = (a, l, cls = "") =>
      `<button type="button" class="btn sm ${cls}" data-a="${a}" data-id="${p.id}">${l}</button>`;
    return `<tr class="${p.archived ? "muted" : ""}">
      <td data-l="Portefeuille"><span aria-hidden="true">${J.esc(p.icon || "💼")}</span> <a href="portefeuilles.html?id=${p.id}"><b>${J.esc(p.name)}</b></a>${p.is_default ? " ★" : ""}${p.description ? `<div class="small muted">${J.esc(p.description)}</div>` : ""}</td>
      <td data-l="Type">${model(p)}</td>
      <td class="num" data-l="Titres">${p.totals.value == null ? "—" : J.eur(p.totals.value)}</td>
      <td class="num" data-l="Liquidités">${cash ? J.eur(p.cash.balance) : "—"}</td>
      <td data-l="Actions">${btn("edit", "Modifier")}${cash && !p.archived ? btn("deposit", "+ Argent") + btn("withdrawal", "− Argent") : ""}${!cash && !p.archived ? btn("convert", "Convertir…") : ""}${!p.archived && !p.is_default ? btn("default", "Par défaut") : ""}${p.archived ? btn("unarchive", "Désarchiver") : btn("archive", "Archiver")}${p.archived ? "" : btn("reset", "Réinitialiser")}${btn("delete", "Supprimer", "danger")}</td></tr>`;
  }

  const table = (list) =>
    `<div class="table-wrap"><table>${J.table.head(["Portefeuille", "Type", ["Valeur des titres", "num"], ["Liquidités", "num"], "Actions"])}<tbody>${list.map(row).join("")}</tbody></table></div>`;

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
      `<section class="card"><h2>Portefeuilles actifs</h2>${active.length ? table(active) : '<p class="muted">Aucun portefeuille actif.</p>'}</section>` +
      (archived.length
        ? `<section class="card"><h2>Archivés</h2><p class="small muted">Consultables, en lecture seule, exclus du bilan courant.</p>${table(archived)}</section>`
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
