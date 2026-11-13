/* Bilan : le squelette est dans bilan.html ; seules les valeurs sont rendues ici. */
(async () => {
  if (!await J.init('bilan')) return;
  const b = await J.api('bilan'), t = b.totals;
  const warning = J.$('#bilan-warning');
  warning.innerHTML = `${t.partial ? `<div class="notice warn">Coût, gains et plus-values calculés <b>sans</b> ${t.excluded.length} position${t.excluded.length > 1 ? 's' : ''} incomplète${t.excluded.length > 1 ? 's' : ''} (taux de change historique manquant ou registre incohérent) : ${t.excluded.map(J.esc).join(', ')}. Corrigez ces transactions dans le portefeuille concerné pour les inclure ; la valeur totale, elle, les compte.</div>` : ''}${t.unpriced ? `<div class="notice warn">${t.unpriced} position(s) sans cours ou change exploitable : valorisation et gain total indisponibles.</div>` : ''}`;
  J.$('#bilan-value').textContent = J.eur(t.value, 0);
  for (const [id, value] of [['bilan-gain', t.total_gain], ['bilan-unrealized', t.unrealized], ['bilan-realized', t.realized]]) {
    const el = J.$('#' + id); el.textContent = J.eur(value, 0); el.classList.add(J.cls(value));
  }
  const pct = J.$('#bilan-unrealized-pct'); pct.textContent = J.pct(t.unrealized_pct); pct.classList.add(J.cls(t.unrealized));
  J.$('#bilan-fees').textContent = 'Frais ' + J.eur(t.fees);
  J.$('#bilan-rows').innerHTML = b.portfolios.map(p => `<tr><td><a href="portefeuilles.html?id=${p.id}"><b>${J.esc(p.name)}</b></a></td><td class="num">${p.positions}</td><td class="num">${J.eur(p.totals.cost, 0)}</td><td class="num">${J.eur(p.totals.value, 0)}</td><td class="num ${J.cls(p.totals.unrealized)}">${J.eur(p.totals.unrealized, 0)} <span class="small">${J.pct(p.totals.unrealized_pct, 1)}</span></td><td class="num ${J.cls(p.totals.realized)}">${J.eur(p.totals.realized, 0)}</td></tr>`).join('') || '<tr><td colspan="6" class="empty">Aucun portefeuille.</td></tr>';
  J.barChart(J.$('#years'), Object.entries(b.realized_by_year));
})();
