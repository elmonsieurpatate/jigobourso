/* Administration : construire le catalogue à la main, dans l'ordre (FinanceDatabase → Yahoo → historiques), consulter les titres, suivre le cron. */
(async () => {
  if (!(await J.init("admin", { admin: true }))) return;
  const page = J.$("#page");
  const TABS = ["fdb", "yahoo", "titres", "cron", "logs", "users", "scores", "colonnes", "settings"];
  const LEGACY = { data: "fdb", catalogue: "fdb", overview: "fdb", jobs: "logs", run: "logs", schedule: "cron" };
  const hashTab = () => {
    const h = location.hash.slice(1);
    return TABS.includes(h) ? h : LEGACY[h] || "fdb";
  };
  let tab = hashTab();
  const TITLES = {
    fdb: "FinanceDatabase",
    yahoo: "Yahoo Finance",
    titres: "Actions / ETF",
    cron: "Cron",
    logs: "Journaux",
    users: "Utilisateurs",
    scores: "Configuration des scores (V4)",
    colonnes: "Colonnes, tris et affichage des tableaux",
    settings: "Réglages",
  };
  const AC = window.AdminCore;
  AC.page = page;
  AC.tab = () => tab;
  async function render() {
    page.innerHTML = '<div class="empty"><span class="spinner"></span></div>';
    J.$(".page-head h1").textContent = "Administration · " + TITLES[tab];
    J.$(".page-head p").textContent = "Règles de filtrage, entonnoirs, traitements, planification, journaux, comptes.";
    try {
      await { ...AC.tabs, scores, colonnes }[tab]();
    } catch (e) {
      page.innerHTML = `<div class="notice err">${J.esc(e.message)}</div>`;
    }
  }
  window.addEventListener("hashchange", () => {
    const t = hashTab();
    if (t !== tab) {
      tab = t;
      render();
    }
  });

  async function scores() {
    J.$(".page-head p").textContent =
      "Méthode de notation commune (scores simple et complexe) et ses paramètres par stratégie.";
    await AdminScores.render(page);
  }
  async function colonnes() {
    J.$(".page-head p").textContent =
      "Colonnes visibles, ordre, largeurs, tri et filtres initiaux des tableaux Explorer et Scores, sur ordinateur et mobile.";
    await AdminColumns.render(page);
  }
  AC.render = render;
  render();
})();
