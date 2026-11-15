/* Administration — onglets Utilisateurs et Réglages */
(() => {
  "use strict";
  const AC = window.AdminCore;
  const { run } = AC;
  async function users() {
    const r = await J.api("admin/users");
    AC.page.innerHTML = `<div class="card"><div class="row between"><h2 class="m-0">Utilisateurs</h2><button class="btn primary" id="add-u">Créer un compte</button></div><div class="table-wrap"><table>${J.table.head(["Identifiant", "E-mail", ["Portefeuilles", "num"], "Dernière connexion", "Rôle", ""])}<tbody>
      ${r.users
        .map(
          (
            u,
          ) => `<tr><td><b>${J.esc(u.username)}</b></td><td>${J.esc(u.email || "–")}</td><td class="num">${u.portfolios}</td><td>${J.dateTime(u.last_login)}</td><td>${u.is_admin == 1 ? '<span class="badge accent">Admin</span>' : "Utilisateur"} ${u.active == 1 ? "" : '<span class="badge danger">Désactivé</span>'}</td>
        <td class="num"><button class="btn sm" data-pw="${u.id}">Mot de passe</button> <button class="btn sm" data-act="${u.id}" data-v="${u.active == 1 ? 0 : 1}">${u.active == 1 ? "Désactiver" : "Réactiver"}</button></td></tr>`,
        )
        .join("")}</tbody></table></div></div>`;
    J.$("#add-u").onclick = () =>
      J.dialog({
        title: "Créer un compte",
        body:
          J.field("Identifiant", '<input id="nu">') +
          J.field("E-mail (facultatif)", '<input id="ne" type="email">') +
          J.field(
            "Mot de passe (10 caractères minimum)",
            '<input id="np" type="password" autocomplete="new-password">',
          ) +
          '<label class="row gap-s"><input type="checkbox" id="na"> Administrateur</label>',
        actions: [
          { label: "Annuler", run: () => {} },
          {
            label: "Créer",
            cls: "primary",
            run: async (d) => {
              await J.post("admin/user/create", {
                username: J.$("#nu", d).value,
                email: J.$("#ne", d).value,
                password: J.$("#np", d).value,
                is_admin: J.$("#na", d).checked,
              });
              AC.render();
            },
          },
        ],
      });
    J.$$("[data-act]").forEach(
      (b) =>
        (b.onclick = async () => {
          await J.post("admin/user/update", { id: +b.dataset.act, active: b.dataset.v === "1" });
          AC.render();
        }),
    );
    J.$$("[data-pw]").forEach(
      (b) =>
        (b.onclick = () =>
          J.dialog({
            title: "Nouveau mot de passe",
            body:
              J.field(
                "Mot de passe (10 caractères minimum)",
                '<input id="pw" type="password" autocomplete="new-password">',
              ) + '<p class="small muted">Ses sessions ouvertes seront fermées.</p>',
            actions: [
              { label: "Annuler", run: () => {} },
              {
                label: "Enregistrer",
                cls: "primary",
                run: async (d) => {
                  await J.post("admin/user/update", { id: +b.dataset.pw, password: J.$("#pw", d).value });
                  J.toast("Mot de passe modifié");
                },
              },
            ],
          })),
    );
  }
  async function settings() {
    const s = (await J.api("admin/system")).settings;
    AC.page.innerHTML = `<div class="notice">Les seuils du catalogue et du préfiltre Yahoo se règlent désormais dans <a href="#fdb">FinanceDatabase</a> et <a href="#yahoo">Yahoo Finance</a>.</div>
      <div class="grid cols-2 mt-4"><div class="card"><h2>Historique 15 minutes</h2>${J.field("Séances conservées (5 à 60)", `<input id="ret" type="number" min="5" max="60" value="${s.intraday_retention_sessions ?? 20}">`)}<button class="btn primary mt-3" id="sv-ret">Enregistrer</button></div>
      <div class="card"><h2>Inscriptions</h2><p class="muted small">Un mot d’invitation permet aux personnes qui le connaissent de créer un compte. Vide = inscriptions fermées. ${s.invite_code ? `Mot actuel (masqué) : <b class="mono u-user-select-all" id="inv-now">${J.esc(s.invite_code)}</b>` : "Aucun mot défini : les inscriptions sont fermées."}</p>${J.field("Nouveau mot d’invitation", '<input id="inv" autocomplete="off">')}<button class="btn primary mt-3" id="sv-inv">Enregistrer</button></div></div>
      <div class="card mt-4"><h2>Base de données</h2><div id="tb"><span class="spinner"></span></div></div>`;
    const save = async (name, value) => {
      await J.post("admin/settings", { name, value });
      J.toast("Réglage enregistré");
    };
    J.$("#sv-ret").onclick = () =>
      save("intraday_retention_sessions", J.$("#ret").value).catch((e) => J.toast(e.message));
    J.$("#sv-inv").onclick = () =>
      save("invite_code", J.$("#inv").value)
        .then(AC.render)
        .catch((e) => J.toast(e.message));
    const sys = await J.api("admin/system");
    J.$("#tb").innerHTML =
      `<p class="small muted">${J.num(sys.total_mb, 0)} Mo utilisés (plafond hébergeur : 3 072 Mo)</p><div class="table-wrap u-max-height-260px u-overflow-auto"><table><tbody>${sys.tables.map((t) => `<tr><td>${J.esc(t.name)}</td><td class="num">${J.num(+t.rows, 0)} lignes</td><td class="num">${J.num(+t.mb, 1)} Mo</td></tr>`).join("")}</tbody></table></div>`;
  }
  Object.assign(AC.tabs, { users, settings });
})();
