/* Administration des portefeuilles : dialogues partagés par « Mes portefeuilles » et la page d'un portefeuille.
   Création, modification, argent (dépôt, retrait, dividende, frais), conversion vers les liquidités, réinitialisation, suppression.
   Aucun calcul ici : toutes les règles (solde, refus, confirmation) sont côté serveur ; ce module affiche et envoie. */
(() => {
  const today = () => new Date().toISOString().slice(0, 10);
  const KIND_LABEL = { virtual: "Virtuel", real: "Réel" };
  const MOVE_LABEL = {
    initial_capital: "Capital initial",
    deposit: "Dépôt",
    withdrawal: "Retrait",
    dividend: "Dividende",
    fee: "Frais",
  };
  const COUNT_LABEL = {
    transactions: "transactions",
    cash_movements: "mouvements d’argent",
    cash_corrections: "corrections d’argent",
    lot_origins: "stratégies d’origine d’achat",
    lot_settings: "réglages de lots",
    levels: "niveaux stop / objectif",
    targets: "objectifs de répartition",
    alert_rules: "règles d’alerte",
    watch: "surveillances",
    watch_log: "journaux de surveillance",
    plan_rules: "règles de plan",
  };
  const iconSelect = (icons, value) =>
    `<select id="pf-icon"><option value="">Aucune</option>${(icons || []).map((i) => `<option ${i === value ? "selected" : ""}>${i}</option>`).join("")}</select>`;
  const countsHtml = (counts) => {
    const rows = Object.entries(counts).filter(([, n]) => n > 0);
    return rows.length
      ? `<ul>${rows.map(([k, n]) => `<li><b>${n}</b> ${J.esc(COUNT_LABEL[k] || k)}</li>`).join("")}</ul>`
      : "<p class='small muted'>Aucune donnée liée.</p>";
  };
  const exportLink = (id) =>
    `<p class="small"><a href="api.php?r=export&id=${id}" download>Exporter les transactions (CSV) avant de continuer</a></p>`;

  function create({ icons, onDone }) {
    const kindHelp = {
      virtual:
        "Simulation : les achats sont limités aux liquidités disponibles, sans marge. Le capital initial est obligatoire.",
      real: "Suivi d’un compte réel : le capital initial est facultatif ; un solde négatif est signalé (dépôt manquant ?) mais toléré.",
    };
    J.dialog({
      title: "Nouveau portefeuille",
      body:
        J.field("Nom", '<input id="pf-name" maxlength="100" autofocus>') +
        J.field(
          "Type",
          `<select id="pf-kind"><option value="virtual">Virtuel (simulation)</option><option value="real">Réel</option></select>`,
        ) +
        `<p class="small muted" id="pf-kind-help">${kindHelp.virtual}</p>` +
        J.field("Capital initial (€)", '<input id="pf-capital" inputmode="decimal" placeholder="1000">') +
        J.field("Icône", iconSelect(icons)) +
        J.field("Description (facultative)", '<input id="pf-desc" maxlength="280">'),
      onopen: (d) => {
        J.$("#pf-kind", d).onchange = (e) => (J.$("#pf-kind-help", d).textContent = kindHelp[e.target.value]);
      },
      actions: [
        { label: "Annuler", run: () => {} },
        {
          label: "Créer",
          cls: "primary",
          run: async (d) => {
            const r = await J.post("portfolio/create", {
              name: J.$("#pf-name", d).value,
              kind: J.$("#pf-kind", d).value,
              initial_capital: J.$("#pf-capital", d).value,
              icon: J.$("#pf-icon", d).value,
              description: J.$("#pf-desc", d).value,
            });
            onDone(r.id);
          },
        },
      ],
    });
  }

  function edit({ portfolio, icons, onDone }) {
    J.dialog({
      title: "Modifier le portefeuille",
      body:
        J.field("Nom", `<input id="pf-name" maxlength="100" value="${J.esc(portfolio.name)}">`) +
        J.field("Icône", iconSelect(icons, portfolio.icon)) +
        J.field("Description", `<input id="pf-desc" maxlength="280" value="${J.esc(portfolio.description || "")}">`),
      actions: [
        { label: "Annuler", run: () => {} },
        {
          label: "Enregistrer",
          cls: "primary",
          run: async (d) => {
            await J.post("portfolio/update", {
              id: portfolio.id,
              name: J.$("#pf-name", d).value,
              icon: J.$("#pf-icon", d).value,
              description: J.$("#pf-desc", d).value,
            });
            onDone();
          },
        },
      ],
    });
  }

  /* Dépôt, retrait, dividende ou frais ; `move` renseigné = correction d'un mouvement existant (le type ne change pas). */
  function money({ portfolioId, kind, move, onDone }) {
    const k = move ? move.kind : kind;
    const dividend = k === "dividend";
    const titles = {
      deposit: "Ajouter de l’argent",
      withdrawal: "Retirer de l’argent",
      dividend: "Enregistrer un dividende",
      fee: "Frais de compte",
      initial_capital: "Corriger le capital initial",
    };
    const v = (x, d = "") => (move && move[x] != null ? String(+move[x] || move[x]) : d);
    J.dialog({
      title: move ? "Corriger : " + MOVE_LABEL[k].toLowerCase() : titles[k],
      body:
        `<p class="small muted">${k === "dividend" ? "Saisissez le montant réellement crédité." : k === "fee" ? "Un frais de compte est une perte." : "Un dépôt ou un retrait n’est jamais un gain ni une perte."}</p>` +
        J.field(
          dividend ? "Montant crédité" : "Montant (€)",
          `<input id="mv-amount" inputmode="decimal" value="${J.esc(v("amount_net"))}">`,
        ) +
        (dividend
          ? J.field("Devise", `<input id="mv-cur" maxlength="3" value="${J.esc(v("currency", "EUR"))}">`) +
            J.field(
              "Taux vers l’euro (si devise étrangère)",
              `<input id="mv-fx" inputmode="decimal" value="${move && move.currency !== "EUR" ? J.esc(v("fx_to_eur")) : ""}">`,
            ) +
            J.field(
              "Montant brut (facultatif)",
              `<input id="mv-gross" inputmode="decimal" value="${J.esc(v("gross_amount"))}">`,
            ) +
            J.field(
              "Retenue à la source (facultatif)",
              `<input id="mv-tax" inputmode="decimal" value="${J.esc(v("withholding_tax"))}">`,
            )
          : "") +
        J.field(
          "Date",
          `<input id="mv-date" type="date" max="${today()}" value="${move ? String(move.occurred_at).slice(0, 10) : today()}">`,
        ) +
        J.field("Note (facultative)", `<input id="mv-note" maxlength="500" value="${J.esc(v("note"))}">`),
      actions: [
        { label: "Annuler", run: () => {} },
        {
          label: move ? "Enregistrer la correction" : "Enregistrer",
          cls: "primary",
          run: async (d) => {
            const body = {
              amount: J.$("#mv-amount", d).value,
              occurred_at: J.$("#mv-date", d).value,
              note: J.$("#mv-note", d).value,
            };
            if (dividend) {
              body.currency = J.$("#mv-cur", d).value || "EUR";
              body.fx_to_eur = J.$("#mv-fx", d).value;
              body.gross_amount = J.$("#mv-gross", d).value;
              body.withholding_tax = J.$("#mv-tax", d).value;
            }
            if (move) await J.post("cash/update", { id: move.id, ...body });
            else await J.post("cash/add", { portfolio_id: portfolioId, kind: k, ...body });
            onDone();
          },
        },
      ],
    });
  }

  async function reset({ portfolio, onDone }) {
    const p = await J.api("portfolio/reset-preview", { params: { id: portfolio.id } });
    const cash = p.cash_model === "cash";
    J.dialog({
      title: "Réinitialiser « " + portfolio.name + " »",
      body:
        `<p>Toutes les opérations et données de suivi seront supprimées. Conservés : ${p.keeps.join(", ")}.</p>${countsHtml(p.counts)}${exportLink(portfolio.id)}` +
        (cash
          ? J.field("Nouveau capital initial (€, facultatif)", '<input id="rs-capital" inputmode="decimal">')
          : "") +
        J.field("Tapez le nom du portefeuille pour confirmer", '<input id="rs-confirm" autocomplete="off">'),
      actions: [
        { label: "Annuler", run: () => {} },
        {
          label: "Réinitialiser",
          cls: "danger",
          run: async (d) => {
            await J.post("portfolio/reset", {
              id: portfolio.id,
              confirm: J.$("#rs-confirm", d).value,
              initial_capital: cash ? J.$("#rs-capital", d).value : "",
            });
            onDone();
          },
        },
      ],
    });
  }

  async function remove({ portfolio, onDone }) {
    const p = await J.api("portfolio/delete-preview", { params: { id: portfolio.id } });
    J.dialog({
      title: "Supprimer définitivement « " + portfolio.name + " »",
      body:
        `<p>Cette action est <b>définitive</b> : le portefeuille et toutes ses données propres disparaissent. Les données partagées (titres, cours) et vos stratégies sauvegardées ne sont pas touchées.</p>${countsHtml(p.counts)}${exportLink(portfolio.id)}` +
        (p.new_default
          ? `<p class="small">« ${J.esc(p.new_default.name)} » deviendra le portefeuille par défaut.</p>`
          : "") +
        (p.has_data
          ? J.field("Tapez le nom du portefeuille pour confirmer", '<input id="dl-confirm" autocomplete="off">')
          : ""),
      actions: [
        { label: "Annuler", run: () => {} },
        {
          label: "Supprimer définitivement",
          cls: "danger",
          run: async (d) => {
            await J.post("portfolio/delete", { id: portfolio.id, confirm: J.$("#dl-confirm", d)?.value || "" });
            onDone();
          },
        },
      ],
    });
  }

  async function archive({ portfolio, onDone }) {
    try {
      const r = await J.post("portfolio/archive", { id: portfolio.id });
      onDone(r);
    } catch (e) {
      if (!/seul portefeuille actif/.test(e.message)) throw e;
      if (await J.confirm("Archiver sans portefeuille par défaut", e.message, "Archiver quand même")) {
        await J.post("portfolio/archive", { id: portfolio.id, no_default: true });
        onDone();
      }
    }
  }

  /* Conversion legacy → liquidités : saisie, aperçu en lecture seule, validation. Rien n'est écrit avant « Convertir ». */
  function convert({ portfolio, onDone }) {
    let preview = null;
    const body = (d) => {
      const kind = J.$("#cv-kind", d).value,
        mode = J.$("#cv-mode", d).value;
      const out = { id: portfolio.id, kind, mode };
      if (mode === "from_date") {
        out.date = J.$("#cv-date", d).value;
        out.opening_balance = J.$("#cv-open", d).value;
      } else {
        out.deposits = J.$("#cv-deps", d)
          .value.split("\n")
          .map((l) => l.trim())
          .filter(Boolean)
          .map((l) => {
            const [date, amount] = l.split(/\s+/);
            return { date, amount };
          });
      }
      return out;
    };
    const d = J.dialog({
      title: "Convertir « " + portfolio.name + " » au modèle avec liquidités",
      body:
        `<p class="small muted">Vos transactions ne sont jamais modifiées. Aucun dépôt n’est inventé : vous déclarez vous-même le solde ou les dépôts. L’aperçu ne modifie rien.</p>` +
        J.field(
          "Type",
          '<select id="cv-kind"><option value="real">Réel</option><option value="virtual">Virtuel</option></select>',
        ) +
        J.field(
          "Méthode",
          '<select id="cv-mode"><option value="from_date">À partir d’une date, avec un solde d’ouverture déclaré</option><option value="full">Reconstituer tout l’historique avec mes dépôts passés</option></select>',
        ) +
        `<div id="cv-from">${J.field("Date de départ des liquidités", `<input id="cv-date" type="date" max="${today()}" value="${today()}">`)}${J.field("Solde d’ouverture (€, 0 = non renseigné)", '<input id="cv-open" inputmode="decimal" value="0">')}<p class="small muted">Les opérations antérieures restent calculées selon l’ancien modèle ; les deux périodes ne sont jamais mélangées silencieusement.</p></div>` +
        `<div id="cv-full" hidden>${J.field("Dépôts passés (une ligne par dépôt : AAAA-MM-JJ montant)", '<textarea id="cv-deps" rows="5" placeholder="2026-05-04 1500"></textarea>')}</div>` +
        '<div id="cv-preview" class="small"></div>',
      onopen: (dlg) => {
        const sync = () => {
          const full = J.$("#cv-mode", dlg).value === "full";
          J.$("#cv-from", dlg).hidden = full;
          J.$("#cv-full", dlg).hidden = !full;
          preview = null;
          J.$("#cv-preview", dlg).innerHTML = "";
          J.$$(".foot button", dlg)[2].disabled = true;
        };
        J.$("#cv-mode", dlg).onchange = sync;
        dlg.addEventListener("input", () => {
          preview = null;
          J.$$(".foot button", dlg)[2].disabled = true;
        });
        J.$$(".foot button", dlg)[2].disabled = true;
      },
      actions: [
        { label: "Annuler", run: () => {} },
        {
          label: "Aperçu",
          run: async (dlg) => {
            preview = await J.post("portfolio/convert-preview", body(dlg));
            const p = preview;
            J.$("#cv-preview", dlg).innerHTML =
              `<div class="notice ${p.ok ? "ok" : "err"}"><b>Solde après conversion : ${J.eur(p.balance)}</b>${p.value_with_cash != null ? ` · valeur avec liquidités : ${J.eur(p.value_with_cash)}` : ""}<br>${p.operations_in_model} opération(s) dans le nouveau modèle, ${p.legacy_operations} dans l’ancien.</div>` +
              (p.warnings.length ? `<ul>${p.warnings.map((w) => `<li>${J.esc(w)}</li>`).join("")}</ul>` : "") +
              (p.needed_opening > 0
                ? `<p>Il manquerait au minimum <b>${J.eur(p.needed_opening)}</b> au point le plus bas : à corriger dans vos dépôts si nécessaire.</p>`
                : "") +
              (p.negatives.length
                ? `<p class="small">Soldes négatifs : ${p.negatives
                    .slice(0, 5)
                    .map((n) => `${J.date(n.at)} (${J.eur(n.balance)})`)
                    .join(", ")}</p>`
                : "");
            J.$$(".foot button", dlg)[2].disabled = !p.ok;
            return true;
          },
        },
        {
          label: "Convertir",
          cls: "primary",
          run: async (dlg) => {
            if (!preview) throw new Error("Lancez d’abord l’aperçu");
            await J.post("portfolio/convert", { ...body(dlg), confirm: true, plan_hash: preview.plan_hash });
            onDone();
          },
        },
      ],
    });
    return d;
  }

  async function undoConvert({ portfolio, onDone }) {
    const p = await J.api("portfolio/convert-undo-preview", { params: { id: portfolio.id } });
    if (!p.possible) {
      J.dialog({
        title: "Annulation impossible",
        body: `<p>${J.esc(p.reason || "")}</p>${p.blockers.length ? `<ul>${p.blockers.map((b) => `<li>${b.type === "movement" ? "Mouvement d’argent" : "Transaction"} n° ${b.id} : ${J.esc(b.detail)}</li>`).join("")}</ul>` : ""}<p class="small muted">Supprimez ou corrigez ces opérations d’abord : l’annulation ne doit jamais rendre l’historique incohérent.</p>`,
        actions: [{ label: "Fermer", run: () => {} }],
      });
      return;
    }
    if (
      await J.confirm(
        "Annuler la conversion",
        "Les liquidités ajoutées par la conversion seront retirées ; vos transactions restent intactes.",
        "Annuler la conversion",
      )
    ) {
      await J.post("portfolio/convert-undo", { id: portfolio.id, confirm: true });
      onDone();
    }
  }

  /* Section « Argent » d'un portefeuille à liquidités : solde, boutons, historique des mouvements corrigeables. */
  async function cashPanel(host, portfolio, onChange) {
    const r = await J.api("portfolio/cash", { params: { id: portfolio.id } });
    if (!r.cash) {
      host.innerHTML = `<p class="small muted">Ce portefeuille fonctionne sans liquidités (ancien modèle) : ses résultats restent calculés comme avant.</p><button type="button" class="btn sm" id="cash-convert">Convertir au modèle avec liquidités…</button>`;
      J.$("#cash-convert", host).onclick = () => convert({ portfolio, onDone: onChange });
      return;
    }
    const c = r.cash,
      locked = portfolio.archived;
    host.innerHTML =
      `<p><b>${J.eur(c.balance)}</b> de liquidités · ${KIND_LABEL[c.kind]}${c.negative ? ' <span class="badge wait">solde négatif à une date : dépôt manquant ?</span>' : ""}</p>` +
      (locked
        ? '<p class="small muted">Portefeuille archivé : lecture seule.</p>'
        : `<p><button type="button" class="btn sm" data-mv="deposit">Ajouter de l’argent</button> <button type="button" class="btn sm" data-mv="withdrawal">Retirer</button> <button type="button" class="btn sm" data-mv="dividend">Dividende</button> <button type="button" class="btn sm" data-mv="fee">Frais</button>${c.converted_at ? ' <button type="button" class="btn sm" id="cash-undo">Annuler la conversion…</button>' : ""}</p>`) +
      `<div class="table-wrap"><table>${J.table.head(["Date", "Type", ["Montant", "num"], ["Solde après", "num"], "Note", ""])}<tbody>${
        r.movements
          .map(
            (m) =>
              `<tr><td data-l="Date">${J.date(m.occurred_at)}</td><td data-l="Type">${MOVE_LABEL[m.kind]}${m.source === "conversion" ? ' <span class="small muted">(conversion)</span>' : ""}</td><td class="num" data-l="Montant">${["withdrawal", "fee"].includes(m.kind) ? "−" : "+"}${J.eur(m.amount_net)}${m.currency !== "EUR" ? ` ${J.esc(m.currency)}` : ""}</td><td class="num" data-l="Solde après">${m.balance_after == null ? "" : J.eur(m.balance_after)}</td><td data-l="Note">${J.esc(m.note || "")}</td><td>${locked ? "" : `<button type="button" class="btn sm" data-fix="${m.id}">Corriger</button> <button type="button" class="btn sm" data-rm="${m.id}">Supprimer</button>`}</td></tr>`,
          )
          .join("") || '<tr><td colspan="6" class="small muted">Aucun mouvement.</td></tr>'
      }</tbody></table></div>` +
      (r.audit.length
        ? `<p class="small muted">${r.audit.length} correction(s) enregistrée(s) dans le journal.</p>`
        : "");
    J.$$("[data-mv]", host).forEach(
      (b) => (b.onclick = () => money({ portfolioId: portfolio.id, kind: b.dataset.mv, onDone: onChange })),
    );
    J.$$("[data-fix]", host).forEach(
      (b) =>
        (b.onclick = () =>
          money({ portfolioId: portfolio.id, move: r.movements.find((m) => m.id == b.dataset.fix), onDone: onChange })),
    );
    J.$$("[data-rm]", host).forEach(
      (b) =>
        (b.onclick = async () => {
          if (
            await J.confirm(
              "Supprimer le mouvement",
              "Le solde et l’historique seront recalculés ; refusé si une opération en dépend.",
              "Supprimer",
            )
          ) {
            await J.post("cash/delete", { id: +b.dataset.rm });
            onChange();
          }
        }),
    );
    J.$("#cash-undo", host)?.addEventListener("click", () => undoConvert({ portfolio, onDone: onChange }));
  }

  window.PFAdmin = { create, edit, money, reset, remove, archive, convert, undoConvert, cashPanel, KIND_LABEL };
})();
