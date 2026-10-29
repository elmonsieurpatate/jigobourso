(async () => {
  if (!await J.init('bilan')) return;
  const b = await J.api('bilan'), t = b.totals, page = J.$('#page');
  page.innerHTML = `${t.partial ? `<div class="notice warn">Coût, gains et plus-values calculés <b>sans</b> ${t.excluded.length} position${t.excluded.length > 1 ? 's' : ''} incomplète${t.excluded.length > 1 ? 's' : ''} (taux de change historique manquant ou registre incohérent) : ${t.excluded.map(J.esc).join(', ')}. Corrigez ces transactions dans le portefeuille concerné pour les inclure ; la valeur totale, elle, les compte.</div>` : ''}<div class="grid cols-4">
    <div class="card kpi"><span class="l">Valeur totale</span><span class="v">${J.eur(t.value, 0)}</span></div>
    <div class="card kpi"><span class="l">Gain total (latent + réalisé)</span><span class="v ${J.cls(t.total_gain)}">${J.eur(t.total_gain, 0)}</span></div>
    <div class="card kpi"><span class="l">Latent</span><span class="v ${J.cls(t.unrealized)}">${J.eur(t.unrealized, 0)}</span><span class="small ${J.cls(t.unrealized)}">${J.pct(t.unrealized_pct)}</span></div>
    <div class="card kpi"><span class="l">Réalisé</span><span class="v ${J.cls(t.realized)}">${J.eur(t.realized, 0)}</span><span class="small muted">frais ${J.eur(t.fees)}</span></div></div>
    ${t.unpriced ? `<div class="notice warn" style="margin-top:14px">${t.unpriced} position(s) sans cours : la valeur est sous-estimée.</div>` : ''}
    <div class="card" style="margin-top:16px"><h2>Par portefeuille</h2><div class="table-wrap"><table><thead><tr><th>Portefeuille</th><th class="num">Positions</th><th class="num">Investi</th><th class="num">Valeur</th><th class="num">Latent</th><th class="num">Réalisé</th></tr></thead><tbody>
    ${b.portfolios.map(p => `<tr><td><a href="portefeuilles.html?id=${p.id}"><b>${J.esc(p.name)}</b></a></td><td class="num">${p.positions}</td><td class="num">${J.eur(p.totals.cost, 0)}</td><td class="num">${J.eur(p.totals.value, 0)}</td><td class="num ${J.cls(p.totals.unrealized)}">${J.eur(p.totals.unrealized, 0)} <span class="small">${J.pct(p.totals.unrealized_pct, 1)}</span></td><td class="num ${J.cls(p.totals.realized)}">${J.eur(p.totals.realized, 0)}</td></tr>`).join('') || '<tr><td colspan="6" class="empty">Aucun portefeuille.</td></tr>'}</tbody></table></div></div>
    <div class="card"><h2>Plus-values réalisées par année</h2><div id="years"></div></div>
    <p class="small muted">Méthode : prix de revient moyen pondéré, frais inclus dans le coût d’achat et déduits du produit des ventes, conversions au taux historique enregistré à chaque transaction ; un taux manquant est signalé et ne sera jamais remplacé par le taux courant. Document informatif, hors calcul fiscal.</p>`;
  J.barChart(J.$('#years'), Object.entries(b.realized_by_year));
})();
