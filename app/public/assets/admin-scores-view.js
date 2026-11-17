/* Administration → Scores (V4) : gabarits HTML des écrans (configuration, profils, graphique, classement, cartes) et tables de libellés.
   Aucune écriture dans la page : chaque fonction lit l'état courant via `ctx` (accesseurs fournis par admin-scores.js) et renvoie du HTML. */
window.AdminScoresView = (ctx) => {
  const $ = J.$,
    E = J.esc,
    fmt = (v, d = 1) => J.num(v, d);
  const { v4, strat, prof, labels, active, weightsOf, autoWeights, sum } = ctx;
  const rankColumns = {
    rank: { cell: (r) => (r.rank == null ? "—" : r.rank), cls: "as-c-rank", dir: "asc" },
    name: {
      cell: (r) => `<b>${E(r.symbol)}</b> <span class="muted">${E(r.name)}</span>`,
      cls: "as-c-name",
      dir: "asc",
    },
    status: { cell: (r) => statusBadge(r.status), dir: "asc" },
    kind: { cell: (r) => (r.kind === "etf" ? "ETF" : "Action"), dir: "asc" },
    market: { cell: (r) => E(r.mic), dir: "asc" },
    change: {
      cell: (r) =>
        r.change == null
          ? "—"
          : `<span class="${r.change > 0 ? "up" : r.change < 0 ? "down" : ""}">${r.change > 0 ? "+" : ""}${J.num(r.change, 2)} %</span>`,
      cls: "as-c-num",
    },
    trend: { cell: (r) => spark(r.curve), nosort: true },
    simple: { cell: (r) => scoreCell(r.simple, r.simple_status, ctx.rkWhich === "simple"), cls: "as-c-num" },
    complex: { cell: (r) => scoreCell(r.complex, r.complex_status, ctx.rkWhich === "complex"), cls: "as-c-num" },
  };
  function rankTable(rows) {
    const l = ctx.layoutNow(),
      cat = l.catalog || Object.keys(rankColumns).map((id) => ({ id, label: id }));
    const label = (id) => (cat.find((c) => c.id === id) || {}).label || id;
    const hint = (id) => (cat.find((c) => c.id === id) || {}).hint || "";
    const cols = l.columns.filter((c) => rankColumns[c.id] && c.visible);
    const prim = ctx.rkSorts[0] || { key: ctx.rkWhich, dir: "desc" };
    const w = (c) => (c.width ? ` data-style="width:${c.width}px;min-width:${c.width}px"` : "");
    return `<div class="as-rkwrap"><table class="dense as-rktable" id="as-rktable">${J.table.head(
      cols.map((c) => ({
        label: E(label(c.id)),
        cls: rankColumns[c.id].cls || "",
        scope: "col",
        title: hint(c.id) || "",
        width: c.width,
        sort: rankColumns[c.id].nosort ? "" : c.id,
      })),
      prim,
    )}
      <tbody>${rows.map((r) => `<tr>${cols.map((c) => `<td class="${rankColumns[c.id].cls || ""}"${w(c)} data-label="${E(label(c.id))}">${rankColumns[c.id].cell(r)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  }

  const COMPLEX = [
    ["dynamics", "Dynamique", "Croissance lissée de la période, ramenée à l’échelle de saturation."],
    ["r2", "Régularité (R²)", "Part de la trajectoire expliquée par une tendance régulière."],
    ["up_days", "Séances positives", "Proportion de séances en hausse."],
    [
      "concentration",
      "Concentration des gains",
      "Poids du plus gros pic dans la hausse (moins c’est concentré, mieux c’est).",
    ],
    ["volatility", "Volatilité", "Amplitude des variations quotidiennes (plus c’est calme, mieux c’est)."],
    ["drawdown", "Drawdown (recul max)", "Pire recul depuis un sommet sur la période."],
    ["liquidity", "Liquidité", "Valeur échangée réelle moyenne par jour sur chaque période active."],
    [
      "acceleration",
      "Accélération",
      "Écart des pentes par séance entre les deux moitiés de chaque période (0 dans le profil de référence).",
    ],
    [
      "momentum",
      "Momentum par période",
      "Rendement de chaque période hors les max(1, min(21, arrondi(séances/12))) dernières séances, saturé comme la dynamique sur la durée mesurée (0 dans le profil de référence).",
    ],
    [
      "recovery",
      "Rebond par période",
      "Fraction récupérée du plus grand recul interne à chaque période, modulée par sa profondeur (saturation à 10 %). Une hausse continue vaut 0.",
    ],
  ];
  const TUNING = [
    [
      "sat_a",
      "Saturation de la dynamique",
      "% sur 5 séances",
      "Croissance (en % sur 5 séances ; (séances/5)^0,52 pour les autres périodes) à laquelle la note de dynamique atteint 100. Plus elle est haute, plus il faut une hausse violente pour saturer : à 17 une semaine à +17 % vaut déjà 100, à 40 il faut +40 %. Sert au score simple et au score complexe.",
    ],
    [
      "accel_ref",
      "Référence d’accélération",
      "coefficient",
      "Écart de pente (par séance) pour lequel la note d’accélération vaut 100 : saturation(demi-période) ÷ demi-période × ce coefficient. Le garde-fou utilise les R² des deux moitiés.",
    ],
    [
      "vol_mode",
      "Notation de la volatilité",
      "méthode",
      "Absolue : 100 à 1 %/séance, 0 à 5 %/séance. Relative à la pente : rapport volatilité ÷ pente (plancher de pente 0,3 %), 100 à 1 et 0 à 4 : une forte hausse peu heurtée n’est plus écrasée, une pente nulle ou négative reste à 0. Le drawdown et la liquidité restent notés à part.",
    ],
  ];
  const VOLMODES = { absolute: "Absolue (1 % → 5 %/séance)", relative: "Relative à la pente" };
  const CLABEL = Object.fromEntries(COMPLEX.map((c) => [c[0], c[1]]));
  const SIMPLE = [
    [
      "Dynamique",
      "Pente de chaque période, ramenée à une croissance sur la période puis à une échelle de saturation (A % × (séances/5)^0,52 ; A = réglage de la stratégie, 17 par défaut). 100 % = croissance saturée. Moyenne pondérée des périodes mesurables.",
      "facteur de 0 à 1",
    ],
    [
      "Régularité",
      "R² de chaque période, chacun pesant min(1, séances/21) car un R² sur peu de séances est bruité. Moyenne pondérée des périodes où le R² est mesuré.",
      "facteur de 0 à 1",
    ],
  ];
  const LASTDAY =
    "Jour (1 séance) : granularité facultative, à 0 % par défaut. Quand elle a un poids, elle ne note que la variation entre les deux dernières séances clôturées (Dynamique) ; elle n’a ni R², ni volatilité, ni repli, ni accélération. Sans poids, la dernière séance compte comme les autres séances dans les mesures de chaque période.";

  function strategyPicker() {
    return `<label class="as-lbl">Stratégie sélectionnée</label><select data-a="strategy" class="as-select">
      <optgroup label="Moteur commun V4">${v4()
        .map((s) => `<option value="${E(s.name)}" ${s.name === ctx.sel ? "selected" : ""}>${E(s.label)}</option>`)
        .join("")}</optgroup></select>`;
  }

  function configView(st, isV4) {
    if (!isV4)
      return `<div class="as-grid"><div class="card">${strategyPicker()}</div><div class="card as-span2">${historicView(st)}</div></div>`;
    const p = prof(),
      w = weightsOf(p),
      ids = active(p),
      custom = p.weights_mode === "custom";
    const total = custom ? sum(p.weights) : w ? sum(w) : 0;
    return `<div class="as-grid">
      <div class="card">${strategyPicker()}
        <div class="seg as-seg"><button data-a="mode" data-v="auto" class="${custom ? "" : "on"}">Automatique</button><button data-a="mode" data-v="custom" class="${custom ? "on" : ""}">Personnalisé</button></div>
        <p class="as-hint">${custom ? "Vous fixez vous-même le poids de chaque période (total 100 %)." : "Les poids des périodes sont calculés automatiquement : les périodes courtes comptent davantage (réglable plus bas)."}</p>
        <h3 class="as-h">Périodes (granularités) actives</h3>
        ${Object.keys(p.periods)
          .filter((id) => p.periods[id].enabled || id.startsWith("custom_"))
          .map((id) => {
            const x = p.periods[id],
              on = x.enabled;
            return `<div class="as-period"><label><input type="checkbox" data-a="active" data-p="${id}" ${on ? "checked" : ""}> ${E(labels()[id] || `${x.sessions} séances`)} <span class="muted">(${x.sessions} séance${x.sessions > 1 ? "s" : ""})</span></label>${id.startsWith("custom_") && !ctx.sel.startsWith("ct:") ? `<button type="button" data-a="remove-custom" data-p="${id}" aria-label="Supprimer cette période">×</button>` : ""}
            ${!on ? '<span class="as-w muted">—</span>' : custom ? `<span class="as-w"><input type="number" class="as-num" data-a="pw" data-p="${id}" min="0" max="100" step="0.1" value="${p.weights[id] ?? 0}"> %</span>` : `<span class="as-w as-pill">${w && w[id] !== undefined ? fmt(w[id], 1) + " %" : "…"}</span>`}</div>`;
          })
          .join("")}
        <details><summary>Ajouter une période prédéfinie</summary>${ctx.S.scoring_periods
          .filter((id) => !p.periods[id].enabled)
          .map(
            (id) =>
              `<label><input type="checkbox" data-a="active" data-p="${id}"> ${E(labels()[id])} (${p.periods[id].sessions} séances)</label>`,
          )
          .join(" ")}</details>
        ${ctx.sel.startsWith("ct:") ? '<p class="as-hint">Ajoutez les périodes de cette stratégie depuis le Classement ; réglez leurs poids et seuils ici.</p>' : '<div class="as-period"><input id="as-custom-sessions" type="number" min="3" max="1260" step="1" placeholder="Séances personnalisées" aria-label="Nombre de séances"><button type="button" data-a="add-custom">Créer</button></div>'}
        <div class="as-total ${Math.abs(total - 100) <= 0.05 ? "ok" : "ko"}" id="pw-total">Pondération totale : <b>${fmt(total, 1)} %</b>${Math.abs(total - 100) > 0.05 && ids.length ? " — doit faire 100 %" : ""}</div>
        ${custom ? '<button class="btn sm" data-a="pw-auto">Répartir automatiquement</button>' : ""}
        <p class="as-hint">${ids.length} période${ids.length > 1 ? "s" : ""} active${ids.length > 1 ? "s" : ""} sur ${ctx.S.scoring_periods.length}. <b>Jour</b> (1 séance) est facultatif : désactivé et à 0 % par défaut, il n’a jamais de poids automatique. Pour l’utiliser, passez en mode Personnalisé et donnez-lui un poids ; seule la variation d’une séance est notée (ni R², ni volatilité, ni repli sur une séance : il faut au moins ${ctx.S.formula.min_sessions} séances pour les mesurer). Tant qu’il reste à 0 %, les notes ne changent pas.</p></div>
      <div class="card"><div class="row between"><div class="seg"><button data-a="score" data-v="simple" class="${ctx.scoreTab === "simple" ? "on" : ""}">Score simple</button><button data-a="score" data-v="complex" class="${ctx.scoreTab === "complex" ? "on" : ""}">Score complexe</button></div><span class="badge accent">Note sur 100</span></div>
        ${ctx.scoreTab === "simple" ? simpleView() : complexView(p)}</div>
      <div class="card"><h3 class="as-h">Paramètres généraux (moteur commun)</h3>
        <div class="as-field"><label>Priorité aux périodes courtes <span class="as-i" title="Symbole κ. À 0, chaque séance pèse pareil donc les longues périodes dominent. Plus la valeur est haute, plus la semaine et le mois pèsent. Ne sert qu’aux poids automatiques.">ⓘ</span></label><input type="number" class="as-num" data-a="kappa" min="0" max="0.95" step="0.05" value="${ctx.draft.global.kappa}"></div>
        <p class="as-hint">Valeur 0 à 0,95 · proposée : ${ctx.S.design.kappa}. Commun à toutes les stratégies.</p>
        <div class="as-field"><label>Seuil de fiabilité (couverture) <span class="as-i" title="Information seulement : sous ce seuil, la note est calculée mais signalée « peu fiable ». Elle n’est jamais supprimée et ce seuil ne change aucune note.">ⓘ</span></label><input type="number" class="as-num" data-a="thr" min="0.1" max="1" step="0.05" value="${ctx.draft.global.threshold}"></div>
        <p class="as-hint">Valeur 0,1 à 1 · proposée : ${ctx.S.design.threshold}. Information seulement.</p>
        <div class="as-field"><label>Ancrage récent du score complexe <span class="as-i" title="Pénalise progressivement le score complexe quand la période la plus courte est faible : note × (1 − λ × (1 − vigueur de la période courte)). 0 = neutralisé, 0,5 = valeur actuelle, 1 = maximal. Ne touche pas au score simple.">ⓘ</span></label><input type="number" class="as-num" data-a="anchor" min="0" max="1" step="0.05" value="${ctx.draft.global.anchor}"></div>
        <p class="as-hint">Valeur 0 à 1 · proposée : ${ctx.S.design.anchor}. À 0, aucune pénalité. Détail dans l’onglet « Score complexe ».</p></div></div>`;
  }

  function simpleView() {
    const f = ctx.S.formula;
    return `<h3 class="as-h">Score simple (croissance et régularité)</h3><p class="as-hint">Mesure la force de la tendance (pente) et sa régularité (R²) sur les périodes sélectionnées. Rien d’autre.</p>
      <div class="as-formula">Score simple = 100 × <b>Dynamique</b> (pente) × <b>Régularité</b> (R²) <span class="muted">(plafonné à 100)</span></div>
      <h3 class="as-h">Composantes (formule validée, non modifiable)</h3>
      ${SIMPLE.map(([n, d, e]) => `<div class="as-comp"><div class="row between"><b>${n}</b><span class="badge">${e}</span></div><p class="as-hint">${d}</p></div>`).join("")}
      <div class="notice warn as-lastday">${LASTDAY}</div>
      <p class="as-hint">Les périodes sont combinées avec les poids de la colonne de gauche. Si une période n’a pas assez d’historique, la note est calculée sur les périodes disponibles (poids renormalisés) et marquée « données incomplètes » : le titre reste classé (minimum ${fmt(f.min_sessions, 0)} séances par période).</p>`;
  }

  function complexView(p) {
    const cw = p.complex_weights,
      total = sum(cw);
    return `<h3 class="as-h">Score complexe (qualité globale) <span class="as-i" title="Somme pondérée de notes 0-100. Ces poids sont propres au profil ; les valeurs proposées sont celles du profil de référence « Croissance rapide ».">ⓘ</span></h3>
      <div class="as-total ${Math.abs(total - 100) <= 0.05 ? "ok" : "ko"}">Total : <b id="cw-total">${fmt(total, 1)} %</b></div>
      ${COMPLEX.map(([k, n, d]) => `<div class="as-cw"><span title="${E(d)}">${n}</span><input type="number" class="as-num" data-a="cw" data-k="${k}" min="0" max="100" step="0.5" value="${cw[k] ?? 0}"><span class="as-bar-bg"><span class="as-bar-fg" id="cwb-${k}" data-style="width:${Math.min(100, cw[k] || 0)}%"></span></span><span class="as-pct" id="cwp-${k}">${fmt(cw[k], 0)} %</span></div>`).join("")}
      <div class="row gap-s mt-3"><button class="btn sm" data-a="cw-norm">Normaliser à 100</button><button class="btn sm" data-a="cw-ref">Valeurs de référence</button></div>
      ${tuningCard(p)}
      <h3 class="as-h mt-4">Ancrage récent (λ = ${fmt(ctx.draft.global.anchor, 2)})</h3>
      <div class="as-formula">Note finale = somme pondérée × <b>(1 − λ × (1 − g))</b>, où g = min(1, dynamique de la période la plus courte ÷ 32), entre 0 et 1.</div>
      <p class="as-hint">Si la période courte (la semaine) garde une dynamique d’au moins 32 sur 100, g = 1 et rien n’est retiré. Plus elle faiblit, plus la note baisse, jusqu’à −λ (−50 % à λ = 0,5) pour une semaine plate ou négative. <b>λ = 0 neutralise l’ancrage.</b> Réglage commun à toutes les stratégies (onglet « Configuration du moteur »). Il ne concerne pas le score simple.</p>
      <p class="as-hint">Sur la base actuelle, la semaine faible pèse déjà dans la dynamique et dans les composantes amorties par g : l’ancrage s’y ajoute. Pour un titre à semaine plate, les deux premiers canaux retirent environ 35 % de la note et l’ancrage 0,5 porte la perte totale à environ 68 %. Le classement reste stable (corrélation de rang 0,996 entre λ = 0 et λ = 0,5, 93 titres communs sur le top 100) : l’ancrage sert surtout à départager les titres encore actifs de ceux qui ont calé.</p>
      <p class="as-hint">La liquidité est mesurée dans chaque période active avec les seuls volumes réels disponibles, puis combinée selon les poids de la stratégie. Le profil de référence (Dynamique 40, R² 15, séances positives 5, concentration 7, volatilité 15, drawdown 8, liquidité 10) est celui de Croissance rapide.</p>`;
  }

  function tuningCard(p) {
    const t = p.tuning || ctx.S.design.tuning,
      d = ctx.S.design.tuning,
      R = ctx.S.design.tuning_ranges;
    const field = ([k, n, unit, help]) => {
      const dflt = d[k],
        cur = t[k],
        same = cur === dflt;
      const input =
        k === "vol_mode"
          ? `<select class="as-select as-tsel" data-a="tune" data-k="${k}">${ctx.S.design.vol_modes.map((v) => `<option value="${v}" ${v === cur ? "selected" : ""}>${E(VOLMODES[v])}</option>`).join("")}</select>`
          : `<input type="number" class="as-num" data-a="tune" data-k="${k}" min="${R[k][0]}" max="${R[k][1]}" step="${k === "sat_a" ? 1 : 0.05}" value="${cur}"> <span class="muted as-unit">${unit}</span>`;
      const shown = k === "vol_mode" ? VOLMODES[dflt] : dflt;
      return `<div class="as-tune"><div class="as-tune-head"><b>${n}</b> <span class="as-i" title="${E(help)}">ⓘ</span></div><div class="as-tune-ctl">${input}</div>
        <p class="as-hint">${E(help)}</p><p class="as-hint as-tune-def">Valeur par défaut : <b>${E(shown)}</b>${k in R ? ` · bornes ${R[k][0]} à ${R[k][1]}` : ""} ${same ? "" : `<button class="btn sm" data-a="tune-reset" data-k="${k}">Valeur par défaut</button>`}</p></div>`;
    };
    return `<h3 class="as-h mt-4">Normalisations de cette stratégie (réglages avancés)</h3>
      <p class="as-hint">Propres à la stratégie sélectionnée : elles changent les notes de cette stratégie et d’aucune autre.</p>${TUNING.map(field).join("")}`;
  }

  function historicView(st) {
    return `<div class="notice warn"><b>Moteur historique.</b> « ${E(st.label)} » utilise encore le classement par percentiles : il ne passe pas par les scores V4 et ne se règle pas ici. Aucun de ses réglages n’est modifié par cette page.</div>
      <p class="as-hint mt-3">Périodes actives : ${st.periods.length ? st.periods.map((i) => E(labels()[i] || i)).join(", ") : "aucune"}.</p>
      ${st.components.length ? `<div class="table-wrap"><table>${J.table.head(["Composante", "Période", ["Poids", "num"]])}<tbody>${st.components.map((c) => `<tr><td>${E(c.metric)}</td><td>${E(labels()[c.period] || c.period)}</td><td class="num">${fmt(c.weight, 2)}</td></tr>`).join("")}</tbody></table></div>` : '<p class="muted">Aucune composante de score pondérée.</p>'}`;
  }

  function profilesView() {
    const row = (s) => {
      if (s.engine === "v4") {
        const p = ctx.draft.profiles[s.name],
          ids = active(p),
          w = p.weights_mode === "custom" ? p.weights : s.name === ctx.sel ? autoWeights(p) : s.auto_weights;
        return `<tr><td><b>${E(s.label)}</b><br><small class="muted">${E(s.note)}</small></td><td><span class="badge ok">Moteur commun V4</span></td><td>${ids.map((i) => `${E(labels()[i] || `${p.periods[i].sessions} séances`)}${w && w[i] !== undefined ? " <b>" + fmt(w[i], 1) + " %</b>" : ""}`).join("<br>") || "—"}</td><td>${p.weights_mode === "custom" ? "Personnalisée" : "Automatique"}</td><td>${s.customised ? '<span class="badge warn">Modifié</span>' : "Valeurs initiales"}</td><td class="num"><button class="btn sm" data-a="open" data-v="${E(s.name)}">Configurer</button></td></tr>`;
      }
      return `<tr class="as-legacy"><td>${E(s.label)}</td><td><span class="badge">Ancien moteur</span></td><td>${s.periods.map((i) => E(labels()[i] || i)).join("<br>") || "—"}</td><td>Percentiles</td><td>Préservé</td><td></td></tr>`;
    };
    const pe = ctx.S.personal,
      st = strat(),
      p = st && st.engine === "v4" ? prof() : null;
    return `<div class="card"><h3 class="as-h">Profils de stratégies</h3>
      <div class="table-wrap"><table>${J.table.head(["Stratégie", "Moteur", "Granularités et poids", "Pondération", "État", ""])}<tbody>
      <tr class="as-group"><td colspan="6">Moteur commun V4 — mêmes calculs de score, seuls les réglages changent</td></tr>${v4().map(row).join("")}
</tbody></table></div>
      ${pe ? `<p class="as-hint">Stratégies personnelles : ${pe.total ? `${pe.total} enregistrée${pe.total > 1 ? "s" : ""}, dont ${pe.common_engine} sur le moteur commun et ${pe.historic} sur un ancien moteur (non migrées).` : "aucune enregistrée sur cette base."}${pe.configurable.length ? " Configurables ici : " + pe.configurable.map((c) => E(c.name)).join(", ") + "." : ""}</p>` : ""}</div>
      ${p ? technicalCard(p) + previewCard() : ""}`;
  }

  function technicalCard(p) {
    const thresholdFields = [
      ["min_slope", "Pente min."],
      ["min_r2", "R² min."],
      ["min_return", "Rendement min."],
      ["max_return", "Rendement max."],
      ["max_spike_share", "Concentration max."],
      ["max_volatility", "Volatilité max."],
      ["min_up_fraction", "Séances positives min."],
      ["max_drawdown", "Repli max."],
    ];
    return `<div class="card"><h3 class="as-h">Données et exclusions techniques</h3>
      <p class="as-hint">Politique des données manquantes (moteur V4.2), sans effet de seuil :</p>
      <ul class="as-hint as-list"><li><b>Historique suffisant</b> : note normale.</li>
        <li><b>Données incomplètes ou historique réduit</b> (une période, une mesure ou la liquidité manque) : la note est calculée sur les composantes disponibles, dont les poids sont renormalisés — sans bonus ni pénalité. Le titre est classé et marqué « incomplet » avec sa couverture.</li>
        <li><b>Calcul impossible</b> (aucune période mesurable, ou aucune régularité mesurable) : note « indisponible » avec la raison ; jamais un zéro ni une note favorable inventés.</li></ul>
      <label class="row gap-s mt-2"><input type="checkbox" data-a="fresh" ${p.technical.require_fresh ? "checked" : ""}> Exiger des cours récents (contrôle technique : un cours périmé rend le titre non évaluable)</label>
      <h3 class="as-h mt-3">Seuils des périodes actives</h3>${active(p)
        .map(
          (id) =>
            `<details><summary>${E(labels()[id] || `${p.periods[id].sessions} séances`)}</summary><label><input type="checkbox" data-a="req" data-p="${id}" ${p.periods[id].require_history ? "checked" : ""}> Historique requis</label>${thresholdFields
              .filter(([key]) => id !== "day" || ["min_return", "max_return"].includes(key))
              .map(
                ([key, label]) =>
                  `<label class="as-field">${label}<input type="number" step="any" class="as-num" data-a="thr-p" data-p="${id}" data-f="${key}" value="${p.periods[id][key] ?? ""}"></label>`,
              )
              .join("")}</details>`,
        )
        .join("")}
      <p class="as-hint">Seuil de fiabilité : <b>${fmt(100 * ctx.draft.global.threshold, 0)} %</b> de couverture (réglage commun, onglet « Configuration du moteur »). En dessous, la note est calculée mais signalée « peu fiable » ; aucun titre n’est supprimé.</p></div>`;
  }

  function dist(d) {
    const max = Math.max(1, ...d.histogram);
    return `<div class="as-hist">${d.histogram.map((n, i) => `<span title="${i * 10}–${i * 10 + 10} : ${n} titres"><i data-style="height:${Math.round((100 * n) / max)}%"></i><small>${i * 10}</small></span>`).join("")}</div>
      <p class="as-hint">Médiane <b>${fmt(d.median, 1)}</b> · quartiles ${fmt(d.p25, 1)} – ${fmt(d.p75, 1)} · 90e centile ${fmt(d.p90, 1)} · maximum ${fmt(d.max, 1)}</p>`;
  }

  function rankTop(rows) {
    return rows.length
      ? `<table class="as-mini"><tbody>${rows.map((r) => `<tr><td class="num">${r.rank}</td><td><b>${E(r.symbol)}</b> <span class="muted">${E(r.name)}</span></td><td class="num">${fmt(r.score, 1)}</td><td>${r.status === "partiel" ? '<span class="badge warn">incomplet</span>' : ""}</td></tr>`).join("")}</tbody></table>`
      : '<p class="muted">Aucun titre noté.</p>';
  }

  // Courbe de cours : points réels uniquement, rien d'interpolé. Vert si la période finit au-dessus de son début, rouge sinon.
  function spark(vals, w = 96, h = 26) {
    if (!vals || vals.length < 2) return `<span class="as-nocurve muted" title="Historique insuffisant">—</span>`;
    const lo = Math.min(...vals),
      hi = Math.max(...vals),
      span = hi - lo || 1,
      n = vals.length - 1;
    const pts = vals
      .map((v, i) => `${((i * (w - 2)) / n + 1).toFixed(1)},${(h - 2 - ((v - lo) / span) * (h - 4)).toFixed(1)}`)
      .join(" ");
    const up = vals[vals.length - 1] >= vals[0],
      chg = vals[0] ? (vals[n] / vals[0] - 1) * 100 : null;
    const tip = `${n} séances : ${fmt(vals[0], 2)} → ${fmt(vals[n], 2)}${chg === null ? "" : " (" + (chg >= 0 ? "+" : "") + fmt(chg, 1) + " %)"}`;
    return `<svg class="as-spark ${up ? "up" : "dn"}" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-label="${tip}"><title>${tip}</title><polyline points="${pts}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>`;
  }

  const winSessions = () => {
    const w = ctx.sim.windows || [],
      act = w.filter((x) => x.active).map((x) => x.sessions);
    return w.some((x) => x.sessions === ctx.simWin)
      ? ctx.simWin
      : act.length
        ? Math.max(...act)
        : w.length
          ? w[w.length - 1].sessions
          : 0;
  };
  function chartCard() {
    const all = ctx.sim.curve || [],
      wins = ctx.sim.windows || [],
      L = labels();
    if (all.length < 2) return '<p class="muted">Pas assez d’historique pour tracer la courbe.</p>';
    const n = Math.min(winSessions(), all.length - 1),
      pts = all.slice(-(n + 1)),
      W = Math.max(260, Math.floor((ctx.root && $("#as-body") ? $("#as-body").clientWidth : 360) - 40)),
      H = W < 480 ? 210 : 250;
    const m = { l: 50, r: 10, t: 14, b: 26 },
      iw = W - m.l - m.r,
      ih = H - m.t - m.b;
    const ps = pts.map((x) => x.p),
      lo0 = Math.min(...ps),
      hi0 = Math.max(...ps),
      pad = (hi0 - lo0) * 0.08 || hi0 * 0.01 || 1,
      lo = lo0 - pad,
      hi = hi0 + pad;
    const X = (i) => m.l + (i * iw) / (pts.length - 1),
      Y = (v) => m.t + ((hi - v) / (hi - lo)) * ih;
    const yt = [0, 1, 2, 3].map((k) => lo + ((hi - lo) * k) / 3),
      nt = Math.min(pts.length, W < 480 ? 3 : 5);
    const xt = [
      ...new Set(Array.from({ length: nt }, (_, j) => Math.round((j * (pts.length - 1)) / Math.max(1, nt - 1)))),
    ];
    const up = ps[ps.length - 1] >= ps[0],
      chg = ps[0] ? (ps[ps.length - 1] / ps[0] - 1) * 100 : null;
    const marks = wins
      .filter((x) => x.active && x.sessions < n)
      .map((x) => ({ i: pts.length - 1 - x.sessions, lab: L[x.id] || x.id }));
    ctx.chart = { pts, X, Y, m, W, H, ih, first: ps[0] };
    const line = pts.map((x, i) => `${X(i).toFixed(1)},${Y(x.p).toFixed(1)}`).join(" ");
    return `<div class="as-chart"><div class="as-win" role="group" aria-label="Fenêtre du graphique">${wins.map((x) => `<button class="${x.sessions === n ? "on" : ""}" data-a="sim-win" data-v="${x.sessions}">${E(L[x.id] || x.id)}<small>${x.sessions} séances${x.active ? " · stratégie" : ""}</small></button>`).join("")}</div>
      <div class="as-read" id="as-read" aria-live="polite">${readout(pts.length - 1)}</div>
      <svg id="as-ch" class="as-ch ${up ? "up" : "dn"}" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Courbe des cours sur ${n} séances">
        ${yt.map((v) => `<line class="g" x1="${m.l}" x2="${W - m.r}" y1="${Y(v).toFixed(1)}" y2="${Y(v).toFixed(1)}"/><text class="t" x="${m.l - 6}" y="${(Y(v) + 4).toFixed(1)}" text-anchor="end">${fmt(v, hi - lo < 5 ? 2 : hi - lo < 50 ? 1 : 0)}</text>`).join("")}
        ${marks.map((k) => `<line class="mk" x1="${X(k.i).toFixed(1)}" x2="${X(k.i).toFixed(1)}" y1="${m.t}" y2="${m.t + ih}"/><text class="t mkt" x="${(X(k.i) + 3).toFixed(1)}" y="${m.t + 10}">début ${E(k.lab.toLowerCase())}</text>`).join("")}
        ${xt.map((i, k) => `<text class="t" x="${X(i).toFixed(1)}" y="${H - 7}" text-anchor="${i === 0 ? "start" : i === pts.length - 1 ? "end" : "middle"}">${J.dayShort(pts[i].d)}</text>`).join("")}
        <polyline points="${line}" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
        <line id="as-cur" class="cur is-off" x1="0" x2="0" y1="${m.t}" y2="${m.t + ih}"/><circle class="is-off" id="as-dot" r="4.5" cx="0" cy="0"/>
        <rect id="as-hit" x="${m.l}" y="${m.t}" width="${iw}" height="${ih}" fill="transparent"/></svg>
      <p class="as-hint">Cours de clôture réels sur les ${n} dernières séances (du ${J.dayShort(pts[0].d)} au ${J.dayShort(pts[pts.length - 1].d)})${chg === null ? "" : " · <b>" + (chg >= 0 ? "+" : "") + fmt(chg, 1) + " %</b>"}. Survolez ou touchez le graphique pour lire le cours de chaque séance.</p></div>`;
  }
  function readout(i) {
    if (!ctx.chart) return "";
    const x = ctx.chart.pts[i],
      prev = ctx.chart.pts[i - 1],
      since = ctx.chart.first ? (x.p / ctx.chart.first - 1) * 100 : null,
      day = prev && prev.p ? (x.p / prev.p - 1) * 100 : null,
      sg = (v) => (v >= 0 ? "+" : "") + fmt(v, 1) + " %";
    return `<b>${E(J.dayFull(x.d))}</b> · cours <b>${fmt(x.p, 2)}</b>${since === null ? "" : ` · <span class="${since >= 0 ? "pos" : "neg"}">${sg(since)}</span> depuis le début`}${day === null ? "" : ` · <span class="${day >= 0 ? "pos" : "neg"}">${sg(day)}</span> sur la séance`}`;
  }

  const scoreCell = (v, st, main) =>
    `<span class="as-sc ${main ? "main" : ""}">${v === null || v === undefined ? '<span class="muted">inconnu</span>' : `<b>${fmt(v, 1)}</b>`}<span class="as-flag" ${st === "partiel" ? 'title="Note calculée sur des données incomplètes (une période ou une mesure manque) : les poids restent répartis sur les composantes disponibles." aria-label="données incomplètes"' : 'aria-hidden="true"'}>${st === "partiel" ? "*" : ""}</span></span>`;
  // Une ligne de classement : rang, nom, courbe, scores à droite. `which` met en avant le score qui sert au classement.
  // Statut de stratégie (critères de recherche) : même moteur que le Classement et la fiche ; il ne change ni la note ni le rang.
  const STATUS = { retained: ["Retenue", "ok"], excluded: ["Exclue", "no"], undetermined: ["Indéterminée", "na"] };
  const statusBadge = (st) => {
    if (!st) return "";
    const [t, k] = STATUS[st] || STATUS.undetermined;
    return `<i class="as-status ${k}" title="Statut de la stratégie : ${t.toLowerCase()}. Détail dans la fiche du titre.">${t}</i>`;
  };
  const verdictBar = (n) =>
    `<div class="seg" role="radiogroup" aria-label="Statut de stratégie : titres affichés">${[
      ["retained", "Retenues"],
      ["excluded", "Exclues"],
      ["all", "Toutes"],
    ]
      .map(
        ([k, l]) =>
          `<button data-a="rk-verdict" data-v="${k}" role="radio" aria-checked="${ctx.rkVerdict === k}" class="${ctx.rkVerdict === k ? "on" : ""}">${l} <b>${J.num(n ? n[k] : 0, 0)}</b></button>`,
      )
      .join(
        "",
      )}</div>${n && n.undetermined ? `<span class="as-hint m-0">${J.num(n.undetermined, 0)} indéterminé${n.undetermined > 1 ? "s" : ""} (données manquantes), visible${n.undetermined > 1 ? "s" : ""} dans « Toutes ».</span>` : ""}${c0ctx()}`;
  const c0ctx = () =>
    ctx.rank && ctx.rank.listing && ctx.rank.listing.context === "missing"
      ? '<span class="as-hint warn m-0">Critères de cette stratégie introuvables : statuts indéterminés.</span>'
      : "";
  function rowHtml(r, which, pick) {
    return `<div class="as-rk ${pick ? "pick" : ""}" ${pick ? `data-a="sim-pick" data-id="${r.id}" tabindex="0" role="button"` : ""}><span class="as-rk-n">${r.rank ?? "—"}</span>
      <span class="as-rk-name"><b>${E(r.symbol)}</b> <span class="muted">${E(r.name)}</span> ${statusBadge(r.status)}</span>${spark(r.curve)}
      <span class="as-rk-sc"><span class="as-rk-l">Simple</span>${scoreCell(r.simple, r.simple_status, which === "simple")}<span class="as-rk-l">Complexe</span>${scoreCell(r.complex, r.complex_status, which === "complex")}</span></div>`;
  }
  const stratPicker = () =>
    `<select data-a="strategy" class="as-select" aria-label="Stratégie">${v4()
      .map((s) => `<option value="${E(s.name)}" ${s.name === ctx.sel ? "selected" : ""}>${E(s.label)}</option>`)
      .join("")}</select>`;
  const granText = (g) =>
    g
      ? `${(g.periods || []).map((x) => E(labels()[x.id] || x.id)).join(" + ")} — courbes sur ${g.sessions} séances`
      : "";

  function previewCard() {
    const c = ctx.rank,
      s = c ? c.summary : null,
      st = strat();
    const block = (key, label) => {
      const x = s[key],
        rel = c.compared && c.compared[key];
      return `<div class="as-rankcol"><h4 class="as-h">${label}</h4>
        <div class="as-tiles as-tiles3"><div class="as-tile"><span>Notés et classés</span><b>${J.num(x.ranked, 0)}</b><small>sur ${J.num(s.universe, 0)} titres</small></div>
          <div class="as-tile"><span>Note indisponible</span><b>${J.num(x.unavailable, 0)}</b><small>calcul impossible ou mesures absentes</small></div>
          <div class="as-tile"><span>Données incomplètes</span><b>${J.num(x.reduced_history, 0)}</b><small>${J.num(x.unreliable, 0)} sous le seuil de fiabilité</small></div></div>
        ${dist(x.distribution)}
        ${rel ? `<p class="as-hint"><b>Effet de vos modifications :</b> ${J.num(rel.score_changed, 0)} notes changent ; rang médian déplacé de ${J.num(rel.median_shift, 0)} ; ${J.num(rel.moved_over_10, 0)} titres bougent de plus de 10 places ; dans le top ${rel.top} : ${rel.top_entered} entrée${rel.top_entered > 1 ? "s" : ""}, ${rel.top_left} sortie${rel.top_left > 1 ? "s" : ""}.</p>` : ""}</div>`;
    };
    return `<div class="card"><div class="row between u-flex-wrap-wrap u-gap-8px"><h3 class="as-h m-0">Classement général sur la base actuelle</h3><button class="btn sm" data-a="conf-run">${ctx.confBusy ? "Calcul…" : "Recalculer"}</button></div>
      <div class="row gap-s u-flex-wrap-wrap u-margin-8px-0"><span class="muted">Stratégie :</span> ${stratPicker()}<span class="as-hint m-0">${c ? granText(c.granularity) : ""}</span></div>
      ${ctx.confStale ? '<p class="as-hint warn">Réglages modifiés depuis ce calcul : cliquez sur « Recalculer ».</p>' : ""}
      ${
        ctx.confBusy && !c
          ? '<div class="empty"><span class="spinner"></span></div>'
          : !c
            ? `<p class="muted">${ctx.confFail ? "Calcul impossible : voir le message ci-dessus." : "Calcul au premier affichage."}</p>`
            : s.universe === 0
              ? '<div class="notice warn mt-2">Aucun titre dans cette base : rien à noter. Aucune valeur d’exemple n’est affichée.</div>'
              : `
        <p class="as-hint">Stratégie « ${E(st ? st.label : "")} » : ${granText(c.granularity)}. Tous les titres évaluables sont notés et classés, du meilleur au moins bon. Le rang est le rang général : choisir une catégorie ne le change pas.</p>
        <div class="row between u-flex-wrap-wrap u-gap-8px"><div class="seg"><button data-a="rk-which" data-v="simple" class="${ctx.rkWhich === "simple" ? "on" : ""}">Classé par score simple</button><button data-a="rk-which" data-v="complex" class="${ctx.rkWhich === "complex" ? "on" : ""}">Classé par score complexe</button></div>${verdictBar(c.listing.counts)}</div>
        <div class="as-chips mt-2 mb-2"><button class="btn sm ${ctx.rkCat ? "" : "primary"}" data-a="rk-cat" data-v="">Toutes <b>${J.num(
          c.listing.categories.reduce((a, x) => a + x.count, 0),
          0,
        )}</b></button>
          ${c.listing.categories.map((k) => `<button class="btn sm ${ctx.rkCat === k.id ? "primary" : ""}" data-a="rk-cat" data-v="${E(k.id)}"><i class="as-dot" data-style="background:${E(k.color || "#999")}"></i> ${E(k.name)} <b>${J.num(k.count, 0)}</b></button>`).join("")}</div>
        ${c.listing.rows.length ? rankTable(c.listing.rows) : '<p class="muted">Aucun titre dans cette catégorie.</p>'}
        <p class="as-hint">* note calculée sur des données incomplètes. Ce classement porte sur tous les titres notés ; la page Classement présente les mêmes titres, dans le même ordre, avec les mêmes notes et les mêmes rangs (rang commun « = » pour des notes strictement identiques). Seuls ses filtres secondaires peuvent masquer des lignes.</p>
        ${c.listing.rows.length < c.listing.total ? `<div class="mt-2"><button class="btn sm" data-a="rk-more" ${ctx.rkMore ? "disabled" : ""}>${ctx.rkMore ? "Chargement…" : `Afficher la suite (${c.listing.rows.length} sur ${J.num(c.listing.total, 0)})`}</button></div>` : `<p class="as-hint">${J.num(c.listing.total, 0)} titre${c.listing.total > 1 ? "s" : ""}.</p>`}
        <div class="as-ranks mt-4">${block("simple", "Score simple")}${block("complex", "Score complexe")}</div>
        ${s.unavailable_reasons.length ? `<p class="as-hint"><b>Pourquoi une note est indisponible :</b> ${s.unavailable_reasons.map((r) => `${E(r.reason)} (${J.num(r.count, 0)})`).join(" · ")}${s.no_inputs ? ` · ${J.num(s.no_inputs, 0)} titres sans mesures de score calculées` : ""}.</p>` : s.no_inputs ? `<p class="as-hint">${J.num(s.no_inputs, 0)} titres sans mesures de score calculées.</p>` : ""}
        <p class="as-hint">Moteur de notation version ${c.engine_version}. Poids réels des périodes : ${c.weights.map((w) => `${E(labels()[w.id] || `${w.sessions} séances`)} <b>${fmt(100 * w.weight, 1)} %</b>`).join(" · ")} (κ = ${fmt(c.kappa, 2)}${c.weights.some((w) => w.custom) ? ", poids personnalisés" : ", automatiques"}).</p>`
      }</div>`;
  }
  function simulationView(isV4) {
    const { sim, simQ, simBusy, useDraft } = ctx;
    if (!isV4)
      return `<div class="notice warn">La simulation porte sur une stratégie V4. Choisissez-en une ci-dessous.<div class="mt-2">${stratPicker()}</div></div>`;
    const cands =
      sim && sim.candidates && sim.candidates.length > 1
        ? `<div class="as-chips"><span class="muted">Autres correspondances :</span> ${sim.candidates.map((c) => `<button class="btn sm" data-a="sim-pick" data-id="${c.id}">${E(c.symbol)} <span class="muted">${E(c.name)}</span></button>`).join(" ")}</div>`
        : "";
    return `<div class="card"><div class="row gap-s u-flex-wrap-wrap u-margin-bottom-8px"><span class="muted">Stratégie :</span> ${stratPicker()}</div>
        ${sim && sim.granularity ? `<p class="as-hint mb-2">${granText({ periods: sim.periods, sessions: sim.granularity })}</p>` : ""}
        <div class="as-searchrow"><input id="as-q" class="as-search" type="search" enterkeyhint="search" placeholder="Symbole, nom ou ISIN d’un titre noté" value="${E(simQ)}"><button class="btn primary" data-a="sim-run">Décomposer</button></div>
        <label class="row gap-s as-chk mt-2"><input type="checkbox" data-a="use-draft" ${useDraft ? "checked" : ""}> avec mes modifications non enregistrées</label>${cands}</div>
      <div id="as-sim">${simBusy ? '<div class="empty"><span class="spinner"></span></div>' : simBody()}</div>`;
  }

  function simBody() {
    const { sim } = ctx;
    if (!sim)
      return '<div class="empty">Cherchez un titre réel (symbole, nom ou ISIN) puis cliquez sur « Décomposer ».</div>';
    if (sim.empty)
      return `<div class="card"><div class="notice warn"><b>Aucune donnée à décomposer.</b> ${E(sim.reason)} Rien n’est remplacé par des exemples fictifs.</div></div>`;
    if (sim.not_found)
      return '<div class="card"><div class="notice warn">Aucun titre noté ne correspond à cette recherche.</div></div>';
    if (!sim.result)
      return '<div class="empty">Cherchez un titre réel (symbole, nom ou ISIN) puis cliquez sur « Décomposer ».</div>';
    const r = sim.result,
      ids = sim.periods.map((x) => x.id),
      L = labels();
    const rk = sim.ranks || {},
      rkOf = (cls) => {
        const x = rk[cls === "s" ? "simple" : "complex"];
        return x && x.rank ? `rang <b>${x.rank}</b> sur ${J.num(x.of, 0)} · ` : "";
      };
    const sc = (o, cls) =>
      `<div class="as-score ${cls}"><span>${cls === "s" ? "Score simple" : "Score complexe"}</span><b>${o.score === null ? "inconnu" : fmt(o.score, 1)}</b>${o.score === null ? "" : " / 100"}<small>${rkOf(cls)}${o.status === "ok" ? "données complètes" : o.status === "partiel" ? "données incomplètes" : E(o.why || "")} · couverture ${fmt(100 * (o.coverage || 0), 0)} %${o.score !== null && o.reliable === false ? " · peu fiable" : ""}</small></div>`;
    const cell = (c, key, unit, d, pid) => {
      if (!c) return '<td class="num muted">—</td>';
      if (pid === "day" && key !== "growth")
        return '<td class="num muted" title="Une seule séance : cette mesure n’existe pas">sans objet</td>';
      const raw = c.raw || {};
      const val = key === "growth" ? c.growth : raw[key];
      const note =
        c[
          key === "growth"
            ? "dynamics"
            : {
                r2: "r2",
                up_fraction: "up_days",
                spike_share: "concentration",
                accel: "acceleration",
                volatility: "volatility",
                drawdown: "drawdown",
              }[key]
        ];
      return `<td class="num">${val === null || val === undefined ? '<span class="muted">indisponible</span>' : fmt(unit === "%" ? val * (["up_fraction", "spike_share"].includes(key) ? 100 : 1) : val, d) + (unit ? " " + unit : "")}${note === null || note === undefined ? "" : `<br><small class="muted">note ${fmt(note, 0)}</small>`}</td>`;
    };
    const rows = [
      ["Croissance (Dynamique)", "growth", "%", 2],
      ["Régularité (R²)", "r2", "", 2],
      ["Séances positives", "up_fraction", "%", 0],
      ["Plus gros pic ÷ hausse nette", "spike_share", "%", 0],
      ["Accélération (écart de pente)", "accel", "", 3],
      ["Volatilité (par séance)", "volatility", "%", 2],
      ["Drawdown", "drawdown", "%", 1],
    ];
    const s = r.simple,
      c = r.complex,
      liq = r.liquidity || {};
    return `<div class="card"><div class="row between u-flex-wrap-wrap u-gap-12px"><div><h3 class="as-h m-0">${E(sim.title.name)}</h3><span class="muted">${E(sim.title.symbol)} · ${E(sim.title.mic)} · ${sim.title.kind === "etf" ? "ETF" : "Action"}</span></div><div class="as-scores">${sc(s, "s")}${sc(c, "c")}</div></div>
      ${sim.tuning ? `<p class="as-hint">Normalisations utilisées par le calcul : saturation de dynamique <b>${fmt(sim.tuning.sat_a, 1)}</b> · référence d’accélération <b>${fmt(sim.tuning.accel_ref, 2)}</b> · volatilité <b>${E(VOLMODES[sim.tuning.vol_mode] || sim.tuning.vol_mode)}</b>.</p>` : ""}
      ${chartCard()}
      <div class="table-wrap"><table class="as-dec">${J.table.head(["Mesure", ...ids.map((i) => ({ label: `${E(L[i])}<br><small class="muted">poids réel ${fmt(100 * ((r.weights_effective || {})[i] || 0), 1)} %${r.periods[i] ? "" : " (période sans données)"}</small>`, num: true }))])}<tbody>
        ${rows.map(([n, k, u, d]) => `<tr><td>${n}</td>${ids.map((i) => cell(r.periods[i], k, u, d, i)).join("")}</tr>`).join("")}</tbody></table></div>
      <div class="as-two"><div><h4 class="as-h">Score simple (pente × R²)</h4>${
        s.score === null
          ? `<p class="muted">${E(s.why || "")}</p>`
          : `<p>100 × Dynamique <b>${fmt(s.dynamics, 2)}</b> × Régularité <b>${fmt(s.quality, 2)}</b> = <b>${fmt(s.score, 1)}</b></p>
          <table class="as-mini">${J.table.head(["Période", ["Poids réel", "num"], ["Pente", "num"], ["R²", "num"], ["Fiabilité R²", "num"]])}<tbody>${Object.entries(
            s.parts || {},
          )
            .map(
              ([k, v]) =>
                `<tr><td>${E(L[k] || k)}</td><td class="num">${fmt(100 * v.weight, 1)} %</td><td class="num">${fmt(v.slope, 2)} %/s</td><td class="num">${v.r2 === null ? '<span class="muted">indisponible</span>' : fmt(v.r2, 2)}</td><td class="num">${v.r2_reliability === null ? "—" : fmt(100 * v.r2_reliability, 0) + " %"}</td></tr>`,
            )
            .join("")}</tbody></table>
          <p class="as-hint">Complétude : couverture ${fmt(100 * (s.coverage || 0), 0)} % ${s.status === "ok" ? "(pente et R² mesurés sur toutes les périodes)" : "(une période n’a pas de R² ou de pente : elle sort du calcul, poids renormalisés)"}.</p>`
      }</div>
        <div><h4 class="as-h">Score complexe (somme pondérée)</h4>${
          c.score === null
            ? `<p class="muted">${E(c.why || "")}</p>`
            : `<table class="as-mini"><tbody>${Object.entries(c.contributions)
                .map(
                  ([k, v]) =>
                    `<tr><td>${E(CLABEL[k] || k)}</td><td class="num">${v.value === null ? '<span class="muted">indisponible — hors calcul</span>' : `poids ${fmt(100 * v.weight, 1)} %${Math.abs(v.weight_effective - v.weight) > 0.0005 ? " → réel " + fmt(100 * v.weight_effective, 1) + " %" : ""}`}</td><td class="num">${v.value === null ? "" : "note " + fmt(v.value, 0)}</td><td class="num">${v.points === null ? "" : "<b>+" + fmt(v.points_effective, 1) + "</b>"}</td></tr>`,
                )
                .join(
                  "",
                )}</tbody></table><p class="as-hint">Total ${fmt(c.raw_total, 1)} × ancrage récent ${fmt(c.anchor, 2)} (λ = ${fmt(c.anchor_lambda, 2)}, vigueur de la période courte ${fmt(100 * (c.anchor_gate ?? 0), 0)} %) = <b>${fmt(c.score, 1)}</b>. Complétude : couverture ${fmt(100 * (c.coverage || 0), 0)} %${c.status === "ok" ? "" : " — score partiel, composantes absentes hors calcul"}.</p>`
        }</div></div>
      <p class="as-hint">Liquidité : ${liq.turnover_eur != null ? fmt(liq.turnover_eur / 1e6, 1) + " M€/jour (" + (liq.source === "daily" ? "volumes quotidiens réels" : "estimée, moyenne trimestrielle") + ") · note " + fmt(liq.note, 0) : "indisponible"}. ${r.missing && (r.missing.secondary.length || r.missing.optional_periods.length || r.missing.required_periods.length) ? "<b>Qualité des données :</b> périodes sans historique : " + (E(r.missing.required_periods.concat(r.missing.optional_periods).join(", ")) || "aucune") + " · mesures indisponibles : " + (E(r.missing.secondary.join(", ")) || "aucune") + ". Elles sortent du calcul et les poids restants sont renormalisés (ni bonus ni pénalité)." : "<b>Qualité des données :</b> complète."}</p></div>`;
  }

  function monitorView() {
    const { mon, monErr } = ctx;
    if (monErr) return `<div class="notice err">${E(monErr)}</div>`;
    if (!mon) return '<div class="empty"><span class="spinner"></span></div>';
    const m = mon,
      l = m.liquidity,
      n = m.rated,
      pct = (a, b) => (b ? fmt((100 * a) / b, 0) + " %" : "—");
    const stat = (k) =>
      `<div class="as-tile"><span>${k === "simple" ? "Score simple" : "Score complexe"}</span><b>${J.num(m.counts[k].ok + m.counts[k].partiel, 0)}</b><small>notés et classés · ${J.num(m.counts[k].ok, 0)} complets · ${J.num(m.counts[k].partiel, 0)} incomplets · ${J.num(m.counts[k].inconnu + Math.max(0, l.universe - n), 0)} indisponibles</small></div>`;
    return `${n === 0 ? '<div class="notice warn mb-3"><b>Aucun titre noté.</b> Les mesures de score se remplissent au calcul nocturne ; cette base n’en contient pas encore. Aucune valeur d’exemple n’est affichée.</div>' : ""}
      <div class="as-tiles"><div class="as-tile"><span>Titres notés</span><b>${J.num(n, 0)}</b><small>sur ${J.num(l.universe, 0)} titres recommandables</small></div>${stat("simple")}${stat("complex")}
        <div class="as-tile"><span>Couverture des données</span><b>${m.coverage.median === null ? "—" : fmt(100 * m.coverage.median, 0) + " %"}</b><small>médiane · minimum ${m.coverage.min === null ? "—" : fmt(100 * m.coverage.min, 0) + " %"} · ${J.num(m.coverage.full, 0)} complets</small></div></div>
      <div class="as-grid2"><div class="card"><h3 class="as-h">Fraîcheur des données</h3><table class="as-mini"><tbody>
        <tr><td>Dernier cours connu</td><td class="num">${m.freshness.last_close ? E(m.freshness.last_close) : "—"}</td></tr>
        <tr><td>Dernier calcul des indicateurs</td><td class="num">${m.freshness.computed_at ? E(J.dateTime(m.freshness.computed_at)) : "—"}</td></tr>
        <tr><td>Dernier traitement réussi</td><td class="num">${m.last_success ? E(m.last_success.type) + " · " + E(J.dateTime(m.last_success.at)) : "aucun"}</td></tr>
        <tr><td>Titres au dernier cours ancien (&gt; 5 jours)</td><td class="num">${J.num(m.freshness.stale_titles, 0)}</td></tr></tbody></table></div>
        <div class="card"><h3 class="as-h">Liquidité : volumes réels ou estimés</h3><table class="as-mini"><tbody>
        <tr><td>Volumes quotidiens réels</td><td class="num">${J.num(l.daily, 0)}</td><td class="num">${pct(l.daily, l.universe)}</td></tr>
        <tr><td>Estimée (moyenne trimestrielle)</td><td class="num">${J.num(l.estimated, 0)}</td><td class="num">${pct(l.estimated, l.universe)}</td></tr>
        <tr><td>Inconnue</td><td class="num">${J.num(l.unknown, 0)}</td><td class="num">${pct(l.unknown, l.universe)}</td></tr></tbody></table>
        <p class="as-hint">Collecte des volumes quotidiens : <b>${m.volume_collection ? "activée" : "désactivée"}</b> · dernière vérification : ${l.volume_checked_at ? E(J.dateTime(l.volume_checked_at)) : "jamais"}. L’estimation surestime d’environ 12 % en médiane.</p></div></div>
      <div class="card"><div class="row between"><h3 class="as-h m-0">Erreurs de calcul récentes</h3><button class="btn sm" data-a="mon-refresh">Actualiser</button></div>
        ${m.problems.length ? `<table class="as-mini"><tbody>${m.problems.map((p) => `<tr><td>${E(J.dateTime(p.at))}</td><td>${E(p.type)}</td><td><span class="badge ${p.status === "failed" ? "ko" : "wait"}">${E(p.status)}</span></td><td>${p.errors ? J.num(p.errors, 0) + " erreur(s)" : ""} ${E(p.summary || "")}</td></tr>`).join("")}</tbody></table>` : '<p class="muted">Aucune erreur récente enregistrée.</p>'}</div>`;
  }

  return {
    simulationView,
    monitorView,
    rankColumns,
    COMPLEX,
    TUNING,
    VOLMODES,
    CLABEL,
    SIMPLE,
    LASTDAY,
    strategyPicker,
    configView,
    simpleView,
    complexView,
    tuningCard,
    historicView,
    profilesView,
    technicalCard,
    dist,
    rankTop,
    spark,
    winSessions,
    chartCard,
    readout,
    scoreCell,
    STATUS,
    statusBadge,
    verdictBar,
    c0ctx,
    rowHtml,
    stratPicker,
    granText,
    previewCard,
  };
};
