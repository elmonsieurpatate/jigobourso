/* ETF et pastilles : informations distinctes de tout score de stratégie ; aucune requête fournisseur depuis cette page.
   Une pastille = un point de couleur + un mot + une explication. La couleur n'est jamais la seule information. */
window.JEtf = {
  LEGEND: '<span class="sig ok"><i></i>favorable selon nos critères</span> <span class="sig warn"><i></i>vigilance</span> <span class="sig bad"><i></i>risque important ou anomalie</span> <span class="sig unknown"><i></i>inconnu, insuffisant ou « rien détecté » (jamais « sans risque »)</span>',
  dot(s, withText) {
    const tip = J.esc(s.text + (s.tip ? ' — ' + s.tip : ''));
    return `<span class="sig ${J.esc(s.level)}" title="${tip}"><i aria-hidden="true"></i>${J.esc(s.label)}</span>`;
  },
  rowSignals(list) {
    return (list || []).slice(0, 3).map(s => this.dot(s)).join('');
  },
  reading(list) {
    if (!list || !list.length) return '';
    return `<div class="card"><h2>Lecture rapide</h2><ul class="reading">${list.map(s => `<li><span class="sig ${J.esc(s.level)}"><i aria-hidden="true"></i><b>${J.esc(s.label)}</b></span> <span>${J.esc(s.text)}</span>${s.tip ? `<details class="why"><summary>Seuil</summary><span class="small muted">${J.esc(s.tip)}</span></details>` : ''}</li>`).join('')}</ul>
      <p class="small muted" style="margin:8px 0 0">${this.LEGEND} Information pédagogique, distincte du score : une bonne tendance ne dit rien du risque ni de la diversification.</p></div>`;
  },
  similar(a, cmp) {
    if (!a) return '<p class="muted">Analyse pas encore préparée.</p>';
    const list = a.similar || [];
    return `<p class="small muted">Rendements hebdomadaires convertis en EUR · ${J.esc(a.min_weeks)} semaines indépendantes minimum par jour de semaine · 52 dernières semaines. Calcul du ${J.date(a.built_at)}.${a.stale ? ' Analyse ancienne : à actualiser par la maintenance.' : ''}</p>
    ${list.length ? `<ul>${list.map(x => `<li><a href="titre.html?id=${x.id}" target="_blank" rel="noopener">${J.esc(x.symbol)}</a> — ${J.esc(x.name)}<br><b>Corrélation ${J.num(x.coefficient, 2)}</b> (${J.esc(x.tier || '')}) · ${x.weeks} semaines indépendantes · ${J.date(x.start)} au ${J.date(x.end)}${x.stable === false ? ' · <span class="sig warn"><i></i>résultat instable</span>' : ''}</li>`).join('')}</ul>` : `<p>${J.esc(a.reason || 'Aucun autre ETF avec une corrélation d’au moins 0,80 parmi les données comparables.')}</p>`}
    ${this.compare(cmp)}
    <details><summary>Que signifie cette similarité ?</summary><p class="small">Proche de +1 : mouvements proches sur cette période. Chaque jour de semaine fournit des rendements qui ne se chevauchent pas ; la valeur affichée est la moyenne des cinq. « Instable » : les cinq valeurs ou les deux moitiés de la période divergent trop. Ce n’est ni une composition commune, ni la preuve d’un indice identique, ni une garantie pour l’avenir. Les dividendes ne sont pas intégralement pris en compte. Une corrélation faible ne prouve pas l’absence d’exposition commune.</p></details>`;
  },
  compare(c) {
    if (!c || c.rows.length < 2) return '';
    const fmt = {
      fee: r => r.expense_ratio != null ? J.num(r.expense_ratio, 2) + ' %' : 'inconnus',
      liq: r => r.liquidity_eur_day != null ? (r.liquidity_eur_day >= 1e6 ? J.num(r.liquidity_eur_day / 1e6, 1) + ' M€' : J.num(r.liquidity_eur_day / 1e3, 0) + ' k€') + '/jour' : 'inconnue',
      aum: r => r.total_assets != null ? (r.total_assets >= 1e9 ? J.num(r.total_assets / 1e9, 2) + ' Md' : J.num(r.total_assets / 1e6, 0) + ' M') : 'inconnus',
      yld: r => r.yield != null ? (r.yield > 0 ? 'distribue ~' + J.num(r.yield, 2) + ' %' : '0 %') : 'inconnu',
      gap: r => r.gap_log != null ? (r.gap_log >= 0 ? '+' : '') + J.num(100 * r.gap_log, 1) + ' pts' : '–',
      ov: r => r.overlap ? J.num(r.overlap.shared_weight, 1) + ' % (borne basse)' : (r === c.rows[0] ? '–' : 'composition non comparable'),
    };
    const head = c.rows.map((r, i) => `<th>${i ? `<a href="titre.html?id=${r.id}" target="_blank" rel="noopener">${J.esc(r.symbol)}</a>` : J.esc(r.symbol)}${i ? `<div class="small muted">corr. ${J.num(r.coefficient, 2)}</div>` : '<div class="small muted">cet ETF</div>'}</th>`).join('');
    const line = (label, f) => `<tr><td class="muted">${label}</td>${c.rows.map(r => `<td>${J.esc(f(r))}</td>`).join('')}</tr>`;
    return `<h3 style="margin:14px 0 6px">Ce qui les différencie</h3><div class="table-wrap cmp-wrap"><table class="dense cmp"><thead><tr><th></th>${head}</tr></thead><tbody>
      ${line('Frais annuels', fmt.fee)}${line('Liquidité', fmt.liq)}${line('Place · devise', r => (r.mic || '?') + ' · ' + (r.currency || '?'))}${line('Émetteur', r => r.family || 'inconnu')}${line('Actifs sous gestion', fmt.aum)}${line('Distribution', fmt.yld)}${line('Écart de performance 1 an (EUR)', fmt.gap)}${line('Lignes communes (10 premières)', fmt.ov)}</tbody></table></div>
      <p class="small muted">${J.esc(c.note)} Valeurs inconnues = non fournies, jamais complétées. Le « rendement de distribution » explique souvent un écart de cours entre un ETF qui distribue et son jumeau qui capitalise. Aucune recommandation.</p>`;
  },
  fund(a, fallback, cmp) {
    const d = a?.profile || fallback?.data || {}, date = a?.profile_fetched_at || fallback?.fetched_at;
    const h = d.holdings || [], sectors = Object.entries(d.sectors || {});
    return `<div class="card"><h2>Dans quoi investit cet ETF ?</h2>
      ${a?.exposure?.label ? `<p><b>${J.esc(a.exposure.label)}</b><br><span class="small muted">${J.esc(a.exposure.source)} : indication de catégorie, pas une composition pondérée.</span></p>` : ''}
      <p class="small">${[d.family, d.category, d.legal_type].filter(Boolean).map(J.esc).join(' · ') || 'Caractéristiques détaillées non disponibles.'}</p>
      <div class="metric-grid"><div class="metric"><div class="l">Frais annuels</div><div class="v">${d.expense_ratio != null ? J.num(d.expense_ratio, 3) + ' %' : '–'}</div></div>
        <div class="metric"><div class="l">Actifs sous gestion</div><div class="v">${d.total_assets != null ? J.num(d.total_assets / 1e6, 0) + ' M' + (d.total_assets_currency ? ' ' + J.esc(d.total_assets_currency) : '') : '–'}</div></div>
        <div class="metric"><div class="l">Rendement de distribution</div><div class="v">${d['yield'] != null ? J.num(d['yield'], 2) + ' %' : '–'}</div></div>
        <div class="metric"><div class="l">10 premières lignes</div><div class="v">${d.top10_weight != null ? J.num(d.top10_weight, 1) + ' %' : '–'}</div></div></div>
      <p>Frais annuels : <b>${d.expense_ratio != null ? J.num(d.expense_ratio, 3) + ' %' : 'Non disponibles'}</b> · Poids des dix premières lignes : <b>${d.top10_weight != null ? J.num(d.top10_weight, 1) + ' %' : 'Non calculable avec les pondérations disponibles'}</b> · Actifs sous gestion : <b>${d.total_assets != null ? 'fournis' : 'Non disponibles'}</b></p>
      <p class="small muted">Source : Yahoo Finance${date ? ', profil récupéré le ' + J.date(date) : ', aucun profil en cache'}. Date effective de composition non fournie.${a && !a.profile_usable && date ? ' Profil ancien ou non validé : exclu des calculs d’exposition du portefeuille.' : ''}</p>
      <details><summary>Participations disponibles (${h.length})</summary>${h.length ? `<table class="dense"><tbody>${h.map(x => `<tr><td>${J.esc(x.name || x.symbol || 'Ligne sans nom')}</td><td class="num">${x.weight != null ? J.num(x.weight, 2) + ' %' : 'Poids inconnu'}</td></tr>`).join('')}</tbody></table>` : '<p>Participations non fournies dans le cache. Cela ne signifie pas que le fonds ne détient rien.</p>'}</details>
      <details><summary>Secteurs disponibles</summary>${sectors.length ? `<p class="small muted">Répartition de la poche actions déclarée par Yahoo ; pas nécessairement de tout l’actif.</p>${sectors.map(([k, v]) => `<div class="row between"><span>${J.esc(k)}</span><span>${J.num(v, 2)} %</span></div>`).join('')}` : '<p>Répartition sectorielle indisponible.</p>'}</details>
      <details><summary>Pays, indice et autres caractéristiques</summary><p>Répartition géographique, indice exact et mode de réplication : non disponibles dans les données structurées. Ni le domicile du fonds ni sa devise ne prouvent son exposition géographique.</p><p>Un fonds de matières premières peut utiliser des contrats à terme : ses garanties en espèces ne sont pas son exposition économique. Pour les obligations et les fonds monétaires, une liste d’entreprises ne suffit pas à décrire le risque. Vérifiez le document de l’émetteur.</p></details>
      </div><div class="card"><h2>ETF aux mouvements similaires</h2>${this.similar(a, cmp)}</div>`;
  },
  concentration(c) {
    const groups = c?.groups || [];
    if (!groups.length) return '';
    const missing = c.sample - (c.analysed || 0);
    return groups.map(g => `<div class="notice warn"><span class="tag grp">Groupe ${J.esc(g.id)}</span> <b>${g.size} des ${c.sample} premiers ETF de cette vue</b> évoluent presque comme un seul${g.label ? ' (' + J.esc(g.label) + ')' : ''} : ${g.symbols.map(J.esc).join(', ')}. Ils portent l’étiquette « Groupe ${J.esc(g.id)} » dans le tableau. Corrélation hebdomadaire en EUR ≥ ${J.num(0.97, 2)} sur 52 semaines, lien direct avec le premier du groupe (la plus faible : ${J.num(g.min_coefficient, 2)})${g.unstable ? ' · <span class="sig warn"><i></i>résultat instable</span>' : ''}.</div>`).join('') +
      `<p class="small muted" style="margin:6px 0 10px">Information seulement : scores et ordre inchangés. Une corrélation ne prouve pas des participations communes.${missing > 0 ? ` ${missing} ETF de la sélection sans analyse récente.` : ''}</p>`;
  },
  portfolio(a) {
    if (!a) return '';
    const noComp = a.etf_without_composition || [];
    return `<div class="card"><h2>Diversification des ETF</h2><p class="small muted">${J.esc(a.valuation_basis)} Les actions directes et expositions non documentées restent dans la part inconnue.</p>
      ${(a.signals || []).length ? `<ul class="reading">${a.signals.map(s => `<li><span class="sig ${J.esc(s.level)}"><i aria-hidden="true"></i><b>${J.esc(s.label)}</b></span> <span>${J.esc(s.text)}</span><details class="why"><summary>Seuil</summary><span class="small muted">${J.esc(s.tip || '')}</span></details></li>`).join('')}</ul>` : ''}
      <p>Expositions sectorielles connues : <b>${J.eur(a.known_eur)}</b> · Part inconnue : <b>${J.eur(a.unknown_eur)}${a.unknown_percent != null ? ' (' + J.num(a.unknown_percent, 1) + ' %)' : ''}</b>.</p>
      ${a.unpriced_positions ? `<p class="notice warn">${a.unpriced_positions} position(s) sans valorisation : total incomplet, pourcentages du portefeuille indisponibles.</p>` : ''}
      ${(a.families || []).map(f => `<p class="notice warn"><b>${f.symbols.map(J.esc).join(', ')}</b> évoluent presque comme un seul : <b>${J.eur(f.value_eur)}${f.percent != null ? ' · ' + J.num(f.percent, 1) + ' % du portefeuille' : ''}</b> (corrélation la plus faible ${J.num(f.min_coefficient, 2)}${f.unstable ? ', résultat instable' : ''}).</p>`).join('')}
      ${a.sectors.map(x => `<div class="row between"><span>${J.esc(x.name)}</span><span>${J.eur(x.value_eur)}${x.percent != null ? ' · ' + J.num(x.percent, 1) + ' %' : ''}</span></div>`).join('')}
      ${noComp.length ? `<p class="small muted">Composition inconnue (profil absent ou ancien) : ${noComp.map(x => J.esc(x.symbol)).join(', ')}.</p>` : ''}
      <details><summary>ETF très similaires (${a.similar_pairs.length})</summary>${a.similar_pairs.map(x => `<p>${J.esc(x.a)} / ${J.esc(x.b)} : corrélation <b>${J.num(x.coefficient, 2)}</b>, ${x.weeks} semaines indépendantes, ${J.date(x.start)} au ${J.date(x.end)}${x.stable === false ? ' (instable)' : ''}.</p>`).join('') || '<p>Aucune paire comparable au-dessus de 0,90. Cela ne démontre pas une bonne diversification.</p>'}<p class="small muted">Rendements hebdomadaires en EUR sur 52 semaines, pas chevauchement des participations. ${a.unavailable_pairs} paire(s) non comparable(s) : historique, change ou cache insuffisant/ancien.</p></details></div>`;
  }
};
