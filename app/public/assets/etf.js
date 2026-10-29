/* ETF : informations distinctes de tout score de stratégie ; pas de requête fournisseur. */
window.JEtf = {
  similar(a) {
    if (!a) return '<p class="muted">Analyse pas encore préparée.</p>';
    return `<p class="small muted">Rendements quotidiens convertis en EUR · six mois · minimum ${a.min_common} observations communes. Calcul du ${J.date(a.built_at)}.${a.stale ? ' Analyse ancienne : à actualiser par la maintenance.' : ''}</p>
    ${(a.similar || []).length ? `<ul>${a.similar.map(x => `<li><a href="titre.html?id=${x.id}" target="_blank" rel="noopener">${J.esc(x.symbol)}</a> — ${J.esc(x.name)}<br><b>Corrélation ${J.num(x.coefficient, 3)}</b> · ${x.sessions} observations · ${J.date(x.start)} au ${J.date(x.end)}</li>`).join('')}</ul>` : `<p>${J.esc(a.reason || 'Aucun autre ETF avec une corrélation positive d’au moins 0,80 parmi les données comparables.')}</p>`}
    <details><summary>Que signifie cette similarité ?</summary><p class="small">Proche de +1 : mouvements proches sur cette période. Ce n’est ni une composition commune, ni la preuve d’un indice identique, ni une garantie pour l’avenir. Les dividendes ne sont pas intégralement pris en compte ; les horaires des places diffèrent. Une corrélation faible ne prouve pas l’absence d’exposition commune.</p></details>`;
  },
  fund(a, fallback) {
    const d = a?.profile || fallback?.data || {}, date = a?.profile_fetched_at || fallback?.fetched_at;
    const h = d.holdings || [], sectors = Object.entries(d.sectors || {});
    return `<div class="card"><h2>Dans quoi investit cet ETF ?</h2>
      ${a?.exposure?.label ? `<p><b>${J.esc(a.exposure.label)}</b><br><span class="small muted">${J.esc(a.exposure.source)} : indication de catégorie, pas une composition pondérée.</span></p>` : ''}
      <p class="small">${[d.family, d.category, d.legal_type].filter(Boolean).map(J.esc).join(' · ') || 'Caractéristiques détaillées non disponibles.'}</p>
      <p>Frais annuels : <b>${d.expense_ratio != null ? J.num(d.expense_ratio, 3) + ' %' : 'Non disponibles'}</b> · Poids des dix premières lignes : <b>${d.top10_weight != null ? J.num(d.top10_weight, 1) + ' %' : 'Non calculable avec les pondérations disponibles'}</b></p>
      <p class="small muted">Source : Yahoo Finance${date ? ', profil récupéré le ' + J.date(date) : ', aucun profil en cache'}. Date effective de composition non fournie.${a && !a.profile_usable && date ? ' Profil ancien ou non validé : exclu des calculs d’exposition du portefeuille.' : ''}</p>
      <details><summary>Participations disponibles (${h.length})</summary>${h.length ? `<table class="dense"><tbody>${h.map(x => `<tr><td>${J.esc(x.name || x.symbol || 'Ligne sans nom')}</td><td class="num">${x.weight != null ? J.num(x.weight, 2) + ' %' : 'Poids inconnu'}</td></tr>`).join('')}</tbody></table>` : '<p>Participations non fournies dans le cache. Cela ne signifie pas que le fonds ne détient rien.</p>'}</details>
      <details><summary>Secteurs disponibles</summary>${sectors.length ? `<p class="small muted">Répartition de la poche actions déclarée par Yahoo ; pas nécessairement de tout l’actif.</p>${sectors.map(([k, v]) => `<div class="row between"><span>${J.esc(k)}</span><span>${J.num(v, 2)} %</span></div>`).join('')}` : '<p>Répartition sectorielle indisponible.</p>'}</details>
      <details><summary>Pays, indice et autres caractéristiques</summary><p>Répartition géographique, indice exact, actifs sous gestion et mode de réplication : non disponibles dans les données structurées de cette V1. Ni le domicile du fonds ni sa devise ne prouvent son exposition géographique.</p><p>Un fonds de matières premières peut utiliser des contrats à terme : ses garanties en espèces ne sont pas son exposition économique. Pour les obligations et les fonds monétaires, une liste d’entreprises ne suffit pas à décrire le risque. Vérifiez le document de l’émetteur.</p></details>
      </div><div class="card"><h2>ETF aux mouvements similaires</h2>${this.similar(a)}</div>`;
  },
  concentration(c) {
    return (c?.alerts || []).map(x => `<div class="notice warn">${x.count} des ${c.sample} premiers ETF de cette vue appartiennent à « ${J.esc(x.label)} » : ${x.symbols.map(J.esc).join(', ')}. Catégorie FinanceDatabase ; pas une mesure de participations communes. Scores et ordre inchangés.</div>`).join('');
  },
  portfolio(a) {
    if (!a) return '';
    return `<div class="card"><h2>Diversification des ETF</h2><p class="small muted">${J.esc(a.valuation_basis)} Les actions directes et expositions non documentées restent dans la part inconnue.</p>
      <p>Expositions sectorielles connues : <b>${J.eur(a.known_eur)}</b> · Part inconnue : <b>${J.eur(a.unknown_eur)}${a.unknown_percent != null ? ' (' + J.num(a.unknown_percent, 1) + ' %)' : ''}</b>.</p>
      ${a.unpriced_positions ? `<p class="notice warn">${a.unpriced_positions} position(s) sans valorisation : total incomplet, pourcentages du portefeuille indisponibles.</p>` : ''}
      ${a.sectors.map(x => `<div class="row between"><span>${J.esc(x.name)}</span><span>${J.eur(x.value_eur)}${x.percent != null ? ' · ' + J.num(x.percent, 1) + ' %' : ''}</span></div>`).join('')}
      <details><summary>ETF très similaires (${a.similar_pairs.length})</summary>${a.similar_pairs.map(x => `<p>${J.esc(x.a)} / ${J.esc(x.b)} : corrélation <b>${J.num(x.coefficient, 3)}</b>, ${x.sessions} observations, ${J.date(x.start)} au ${J.date(x.end)}.</p>`).join('') || '<p>Aucune paire comparable au-dessus de 0,90. Cela ne démontre pas une bonne diversification.</p>'}<p class="small muted">Rendements EUR sur six mois, pas chevauchement des participations. ${a.unavailable_pairs} paire(s) non comparable(s) : historique, change ou cache insuffisant/ancien.</p></details></div>`;
  }
};
