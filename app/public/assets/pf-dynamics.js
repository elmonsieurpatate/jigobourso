/* Matrice : rendu seul ; calculs moteur, gains du registre et styles Halo. */
(function (root) {
  "use strict";
  const esc = J.esc;
  const REASONS = {
    history: "Historique insuffisant",
    missing: "Clôture attendue manquante (aucun cours interpolé)",
    break: "Rupture de série ou opération financière non résolue",
    calendar: "Calendrier boursier indisponible",
  };
  const pct = (v) => (Number.isFinite(v) ? J.pctS(v, 2) : "—");
  function cell(c, info) {
    if (!c)
      return '<td class="pfd-cell" title="Titre non lié au catalogue ou données indisponibles">—<small>—</small></td>';
    const why = REASONS[c.reason] || "",
      prev = REASONS[c.previous_reason] || "",
      arrow = { up: "↗", flat: "→", down: "↘" }[c.arrow] || "",
      detail = `${c.start || "?"} → ${c.end || "?"} : ${pct(c.return)}. Fenêtre précédente : ${c.previous_start || "?"} → ${c.start || "?"}, ${pct(c.previous)}. ${why || prev || "Données disponibles"}. Base ${info.basis === "adjusted" ? "ajustée" : "cours avec traitement des splits du moteur"}, devise ${info.currency || "inconnue"}. Flèche neutre jusqu’à ±${J.num(c.neutral_points, 3)} point(s).`;
    return `<td class="pfd-cell pfd-${esc(c.heat)}" tabindex="0" role="button" aria-label="Détail de cette période" title="${esc(detail)}"><strong>${pct(c.return)}</strong><small class="pfd-dynamic pfd-dynamic-${esc(c.arrow || "missing")}">${c.delta === null ? "—" : `${arrow} ${Math.abs(c.delta) > 1e-10 && Math.abs(c.delta) < 0.0001 ? (c.delta > 0 ? "+<0,0001" : "−<0,0001") : J.numS(c.delta, Math.abs(c.delta) < 0.01 && Math.abs(c.delta) > 1e-10 ? 4 : 2)} pt`}</small></td>`;
  }
  function html(data, positions, error, sort) {
    const heading = '<div class="px-ph"><h2>Performance et dynamique des actions</h2></div>',
      details = `<details class="px-meta"><summary>Lire le tableau et comprendre les calculs</summary><p>En haut : rendement du cours en devise de cotation, indépendamment de votre achat. En dessous : différence en points entre deux fenêtres successives de même durée, sans chevauchement des rendements. Une hausse peut avoir un fond vert et une pastille rouge si elle ralentit ; une baisse peut avoir un fond rouge et une pastille verte si elle se modère.</p><p>1J, 2J, 3J, 1S et 2S : 1, 2, 3, 5 et 10 séances terminées. De 1M à 4A : mois et années calendaires, borne ramenée à la dernière séance cotée antérieure. Les séances en cours sont exclues. Dates, devise, base de prix et raisons d’indisponibilité : infobulle de chaque cellule. Aucune clôture manquante n’est inventée.</p><p>Depuis achat : plus-value latente en euros et rendement du coût restant, frais et change du registre inclus ; les gains sur les quantités déjà vendues restent dans le bilan et l’historique. Ce pourcentage personnel n’est pas le TWR.</p><p>Les nuances sont calibrées par la racine carrée du nombre de séances : neutralité ±0,05 %, hausse intermédiaire +1 %, forte hausse +3 % et forte baisse −3 % pour une séance, multipliés par √n pour n séances. Flèche neutre : ±0,05 × √(2n) point ; l’écart numérique reste toujours affiché. Les six nuances décrivent un mouvement, sans prédiction ni modification des scores.</p><p>Quatre ans de performance demandent quatre ans de cours ; sa dynamique demande huit ans. La rétention actuelle couvre environ cinq ans : une comparaison plus ancienne peut donc être indisponible. « — » signifie un historique insuffisant, un trou, un calendrier absent ou une rupture non résolue. Les prix ajustés fiables et complets sont utilisés lorsqu’ils existent ; sinon le traitement habituel des splits est conservé, sans prétendre réinvestir les dividendes.</p></details>`;
    if (!data)
      return `<section class="px-card pf-dynamics">${heading}${error ? `<p class="notice err">Tableau indisponible : ${esc(error)} <button type="button" class="btn sm" data-market-retry>Réessayer</button></p>` : '<p class="empty"><span class="spinner"></span> Chargement des onze horizons…</p>'}${details}</section>`;
    const horizons = data.horizons,
      rows = positions.filter((p) => p.qty > 1e-9),
      value = (p, key) =>
        key === "title"
          ? p.symbol
          : key === "buy"
            ? p.unrealized_pct
            : (data.listings[p.listing_id]?.cells[key]?.return ?? null),
      sorted = J.table.sortRows(rows, [sort], value, (a, b) => J.table.cmp(a.symbol, b.symbol)),
      cols = [
        { label: "Action", sort: "market:title", cls: "pfd-title" },
        {
          label: "Depuis achat",
          sort: "market:buy",
          num: true,
          title: "Plus-value latente de la quantité encore détenue : euros et % du coût restant",
        },
        ...horizons.map((h, i) => ({
          label: h.label,
          sort: "market:" + h.key,
          num: true,
          cls: i === 0 || horizons[i - 1].group !== h.group ? "pfd-group" : "",
        })),
      ],
      headSort = { key: "market:" + sort.key, dir: sort.dir },
      body = sorted
        .map((p) => {
          const info = data.listings[p.listing_id],
            buy = Number.isFinite(p.unrealized) ? J.eurS(p.unrealized) : "—";
          return `<tr><td class="pfd-title">${p.listing_id ? `<a href="titre.html?id=${p.listing_id}&from=portefeuille"><b>${esc(p.symbol)}</b></a>` : `<b>${esc(p.symbol)}</b>`}<small>${esc(p.name_catalogue || p.name || "")}</small></td><td class="pfd-cell pfd-personal"><strong>${buy}</strong><small>${pct(p.unrealized_pct)}</small></td>${horizons.map((h) => cell(info?.cells[h.key], info)).join("")}</tr>`;
        })
        .join("");
    return `<section class="px-card pf-dynamics">${heading}<p class="small muted">Fond = performance du cours · Pastille et flèche : vert = amélioration, rouge = dégradation, gris = variation faible. Courts : 1J–2S · Intermédiaires : 1M–6M · Longs : 1A–4A.</p><div class="pfd-scroll" role="region" aria-label="Performances multi-périodes, défilement horizontal" tabindex="0"><table class="pfd-table">${J.table.head(cols, headSort)}<tbody>${body || '<tr><td colspan="13">Aucune position actuellement détenue.</td></tr>'}</tbody></table></div><div class="pfd-legend small"><span class="pfd-gain-strong">Forte hausse</span><span class="pfd-gain">Hausse modérée</span><span class="pfd-gain-soft">Faible hausse</span><span class="pfd-neutral">Stable</span><span class="pfd-loss-soft">Baisse modérée</span><span class="pfd-loss-strong">Forte baisse</span></div>${details}</section>`;
  }
  root.PFDynamics = { html };
})(window);
