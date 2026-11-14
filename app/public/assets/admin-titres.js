/* Administration — onglet Actions / ETF */
(() => {
  "use strict";
  const AC = window.AdminCore;
  const { nf, runBar } = AC;
  // ───────── Actions / ETF ─────────
  const tf = { q: "", kind: "", mic: "", fdb: "", yahoo: "", final: "", daily: "", sort: "name", dir: "asc", page: 1 };
  const titresLatest = J.latest();
  async function titres() {
    const ticket = titresLatest.next();
    const r = await J.api("admin/titles", {
      params: Object.fromEntries(Object.entries(tf).filter(([, v]) => v !== "")),
    });
    if (!titresLatest.isCurrent(ticket) || AC.tab() !== "titres") return; // réponse périmée ou onglet quitté
    const opt = (cur, list) =>
      list
        .map(([v, l]) => `<option value="${v}" ${String(cur) === String(v) ? "selected" : ""}>${l}</option>`)
        .join("");
    const B = {
      kept: ["ok", "Conservé"],
      removed: ["danger", "Écarté"],
      pending: ["warn", "En attente"],
      secondary: ["", "Secondaire"],
      na: ["", "–"],
      complete: ["ok", "Complet"],
      partial: ["warn", "Incomplet"],
      absent: ["danger", "Absent"],
    };
    const badge = (k) => J.badge(B[k][1], B[k][0]);
    const cols = [
      { label: "Titre", sort: "name" },
      { label: "Place · type", sort: "mic" },
      "FinanceDatabase",
      "Yahoo",
      "Mon catalogue",
      "Motif",
      { label: "Dernier cours", sort: "price_time" },
      { label: "Quotidien", sort: "closes" },
      "15 min",
      "Mise à jour / problème",
    ];
    AC.page.innerHTML = `${runBar()}<div class="card flush"><div class="row card-bar"><input id="tq" type="search" placeholder="Nom, symbole ou ISIN" value="${J.esc(tf.q)}" data-style="flex:1;min-width:180px">
        <select id="tk">${opt(tf.kind, [
          ["", "Actions et ETF"],
          ["equity", "Actions"],
          ["etf", "ETF"],
        ])}</select>
        <select id="tm"><option value="">Toutes les places</option>${r.places.map((m) => `<option ${tf.mic === m ? "selected" : ""}>${J.esc(m)}</option>`).join("")}</select>
        <select id="tfdb">${opt(tf.fdb, [
          ["", "Filtre FinanceDatabase : tous"],
          ["kept", "Conservés"],
          ["removed", "Écartés"],
        ])}</select>
        <select id="ty">${opt(tf.yahoo, [
          ["", "Filtre Yahoo : tous"],
          ["kept", "Retenus"],
          ["removed", "Écartés"],
          ["pending", "En attente"],
          ["secondary", "Cotations secondaires"],
        ])}</select>
        <select id="tfin">${opt(tf.final, [
          ["", "Catalogue : tous"],
          ["1", "Dans mon catalogue"],
          ["0", "Hors catalogue"],
        ])}</select>
        <select id="td">${opt(tf.daily, [
          ["", "Historique quotidien : tous"],
          ["complete", "Complet"],
          ["partial", "Incomplet"],
          ["absent", "Absent"],
        ])}</select></div>
      ${r.raw_total ? "" : '<div class="notice" data-style="margin:0 18px 12px">Aucun titre connu : importez et filtrez FinanceDatabase (page FinanceDatabase).</div>'}
      <div class="table-wrap"><table>${J.table.head(cols, { key: tf.sort, dir: tf.dir })}<tbody>
      ${
        r.rows
          .map(
            (
              x,
            ) => `<tr ${x.in_final && x.lid ? `data-id="${x.lid}"` : ""} class="pointer"><td><b>${J.esc(x.name)}</b><div class="small muted">${J.esc(x.symbol)} · ${J.esc(x.isin || "")} · ${J.esc(x.country || "")}${x.category ? " · " + J.esc(x.category) : ""}</div></td>
        <td>${J.esc(x.mic)}<div class="small muted">${x.kind === "etf" ? "ETF" : "Action"}</div></td><td>${badge(x.fdb_state)}</td><td>${badge(x.y_state)}</td>
        <td>${x.in_final ? '<span class="badge ok">Oui</span>' : '<span class="badge danger">Non</span>'}${x.held ? ' <span class="badge accent">détenu</span>' : ""}</td>
        <td class="small">${x.reason ? `<b>${J.esc(x.reason.stage)}</b>${x.reason.rule ? " · " + J.esc(x.reason.rule) : ""}<div class="muted">${J.esc(x.reason.detail || "")}</div>` : "–"}</td>
        <td class="num small">${x.price != null ? J.num(x.price, 2) + " " + J.esc(x.pcur || "") + `<div class="muted">${x.price_time ? J.dateTime(x.price_time) : ""}</div>` : "–"}</td>
        <td>${x.in_final ? badge(x.d_state) + `<div class="small muted">${x.closes_count != null ? x.closes_count + " séances" : ""}</div>` : "–"}</td><td>${x.in_final ? (x.intraday_state === "na" ? '<span class="small muted">non géré</span>' : badge(x.intraday_state)) : "–"}</td>
        <td class="small">${x.issue ? `<span class="warn">${J.esc(x.issue)}</span>` : x.quote_at ? "Infos Yahoo " + J.ago(x.quote_at) : "–"}</td></tr>`,
          )
          .join("") || '<tr><td colspan="10" class="empty">Aucun titre.</td></tr>'
      }</tbody></table></div>
      <div class="row between card-bar card-bar-sm"><span class="muted small">${nf(r.total)} titres sur ${nf(r.raw_total)} connus</span><span class="row gap-s"><button class="btn sm" id="tp" ${r.page <= 1 ? "disabled" : ""}>←</button><span class="small">Page ${r.page} / ${r.pages}</span><button class="btn sm" id="tn" ${r.page >= r.pages ? "disabled" : ""}>→</button></span></div></div>`;
    const go = () => {
      tf.q = J.$("#tq").value.trim();
      tf.kind = J.$("#tk").value;
      tf.mic = J.$("#tm").value;
      tf.fdb = J.$("#tfdb").value;
      tf.yahoo = J.$("#ty").value;
      tf.final = J.$("#tfin").value;
      tf.daily = J.$("#td").value;
      tf.page = 1;
      titres();
    };
    let t;
    J.$("#tq").oninput = () => {
      clearTimeout(t);
      t = setTimeout(go, 400);
    };
    ["tk", "tm", "tfdb", "ty", "tfin", "td"].forEach((i) => (J.$("#" + i).onchange = go));
    J.$("#tp").onclick = () => {
      tf.page--;
      titres();
    };
    J.$("#tn").onclick = () => {
      tf.page++;
      titres();
    };
    J.table.onSort(J.$("[data-sort]").closest("table"), (key) => {
      const n = J.table.nextSort({ key: tf.sort, dir: tf.dir }, key);
      tf.sort = n.key;
      tf.dir = n.dir;
      titres();
    });
    J.$$("tr[data-id]").forEach((tr) => (tr.onclick = () => (location.href = "titre.html?id=" + tr.dataset.id)));
  }

  Object.assign(AC.tabs, { titres });
})();
