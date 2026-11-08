/* Chapitres : outils, données, fiabilité, glossaire, FAQ, administration (réservée). */
(function () {
  const I = n => J.icon(n), L = (window.HELP_CHAPTERS = window.HELP_CHAPTERS || []);
  L.push({
    id: 'colonnes', group: 'outils', title: 'Colonnes, tris et filtres', icon: I('sliders-horizontal'), color: '#0891b2', keywords: 'colonnes tri filtre catégories mes colonnes mes filtres ordre largeur secteur pays',
    lead: 'Rendre le tableau à votre mesure.',
    beginner: ({ H }) => `
      <h2>Vos colonnes</h2>
      <p><a href="mes-colonnes.html">Mes colonnes et tris</a> : choisissez les colonnes visibles, leur ordre, leur largeur et le tri de départ. Par défaut : score complexe, score simple, tendance en premier. L’ordre des choix de tri suit l’ordre des colonnes ; le tri par défaut est le score complexe.</p>
      <h2>Vos filtres et catégories</h2>
      <p><a href="mes-filtres.html">Mes filtres et catégories</a> liste les catégories connues (pays, secteurs, places, types) et vous laisse enregistrer, pour chaque stratégie, les filtres appliqués au départ. Vous pouvez les réinitialiser.</p>
      ${H.tip('<p>Un filtre masque des lignes. Il ne change ni les scores, ni les rangs (voir « Classements »).</p>')}
      ${H.jigo('<p>Ces réglages sont <b>à vous</b> : ils n’affectent aucun autre compte. À défaut, vous voyez la configuration commune fixée par l’administration.</p>')}`,
    expert: null
  });

  L.push({
    id: 'donnees', group: 'outils', title: 'Sources de données et fiabilité', icon: I('scan-search'), color: '#ca8a04', keywords: 'sources données yahoo financedatabase fiabilité manquantes couverture fraîcheur indéterminé tiret',
    lead: 'D’où viennent les chiffres, et quand ne faut-il pas leur faire confiance.',
    beginner: ({ H }) => `
      <h2>D’où viennent les données ?</h2>
      ${H.table(['Donnée', 'Source'], [['Prix de clôture, volume', 'Yahoo Finance'], ['Nom, pays, secteur, type, place', 'FinanceDatabase (catalogue), complété par Yahoo Finance'], ['Fiches ETF automatiques', 'Données publiques des fonds']])}
      <h2>Quand ça ne se calcule pas</h2>
      ${H.cards([{ icon: I('circle-dollar-sign'), bg: '#fef3c7', title: 'Historique trop court', text: 'Un titre récent n’a pas 252 séances : la durée « Année » est absente. Le titre peut être « indéterminé » pour cette durée.' }, { icon: I('clock'), bg: '#dbeafe', title: 'Données pas fraîches', text: 'Certaines stratégies exigent des prix récents.' }, { icon: I('search'), bg: '#fee2e2', title: 'Donnée manquante', text: 'Une cellule « — » veut dire « inconnu », pas zéro.' }])}
      ${H.warn('<p>Yahoo Finance est une source gratuite : erreurs ou retards possibles. Vérifiez un titre qui vous intéresse sur une autre source avant toute décision.</p>')}
      <p>Les composantes manquantes sont retirées du score complexe, qui est recalculé sur les composantes disponibles.</p>`,
    expert: ({ H, facts }) => `<ul><li>Fenêtre de n séances = n+1 clôtures ; cours nul ou négatif → fenêtre non calculable.</li><li>Seuil de couverture ${facts ? facts.common.threshold : 0.75} : indicateur de fiabilité seulement, il ne supprime aucune note.</li><li>R² et volatilité exigent au moins ${facts ? facts.common.min_sessions : 3} séances.</li><li>Verdict indéterminé : une mesure requise manque et aucun test n'est déjà faux.</li></ul>`
  });

  const G = [['Action', 'Part de propriété d’une entreprise cotée.'], ['ETF', 'Panier de nombreux titres, échangé comme une action.'], ['Indice', 'Mesure de l’évolution d’un groupe de titres (CAC 40…).'], ['Place', 'Marché où le titre s’échange (Paris, New York…).'], ['Séance', 'Journée de bourse.'], ['Clôture', 'Dernier prix d’une séance.'], ['Cours', 'Prix d’une part.'], ['Variation', 'Changement du prix en pourcentage.'], ['Performance', 'Variation entre le début et la fin d’une période.'], ['Tendance', 'Direction générale d’une courbe.'], ['Pente', 'Vitesse moyenne de hausse par séance.'], ['Régularité (R²)', 'Mesure de 0 à 1 : la courbe est-elle proche d’une droite ?'], ['Volatilité', 'Taille des secousses quotidiennes.'], ['Drawdown (repli)', 'Pire chute depuis un sommet.'], ['Liquidité', 'Facilité à acheter ou revendre sans bouger le prix.'], ['Volume', 'Nombre de parts échangées.'], ['Momentum', 'Élan : hausse passée hors dernier mois.'], ['Granularité', 'Durée d’analyse (jour, semaine, mois…).'], ['Critère', 'Condition du filtrage (pente, R² minimum).'], ['Retenu / exclu / indéterminé', 'Verdict du filtrage.'], ['Score simple', 'Hausse × régularité, sur 100.'], ['Score complexe', 'Moyenne pondérée de sept composantes, sur 100.'], ['Poids', 'Importance d’une durée ou d’une composante dans la moyenne.'], ['κ (kappa)', 'Réglage commun qui allège le poids des longues durées.'], ['Ancrage', 'Pénalise un titre dont la durée la plus courte est faible.'], ['Rang', 'Place dans le classement de la stratégie.'], ['Prix de revient', 'Coût moyen par part détenue, frais compris.'], ['Gain latent / réalisé', 'Non encaissé (encore détenu) / encaissé (après vente).'], ['Lot', 'Un achat, suivi pour les alertes (ordre FIFO).'], ['Dietz modifié', 'Méthode de performance neutralisant apports et retraits.']];
  L.push({
    id: 'glossaire', group: 'outils', title: 'Glossaire', icon: I('book-open'), color: '#64748b', keywords: 'glossaire définition mot lexique vocabulaire',
    lead: 'Tous les mots, en une phrase.',
    beginner: () => `<dl class="help-dl" style="display:grid;grid-template-columns:minmax(0,210px) minmax(0,1fr);gap:8px 16px">${G.map(([t, d]) => `<dt style="font-weight:700">${t}</dt><dd style="margin:0">${d}</dd>`).join('')}</dl>`, expert: null
  });

  L.push({
    id: 'faq', group: 'outils', title: 'Questions fréquentes', icon: I('lightbulb'), color: '#f59e0b', keywords: 'faq question pourquoi vide score exclu rang',
    lead: 'Les questions qui reviennent.',
    beginner: ({ H }) => [['Pourquoi ma liste est vide ?', 'Les critères sont trop exigeants. Baissez le niveau de pente ou de régularité dans « Mes critères de recherche », ou retirez une durée. Voir « Adapter une stratégie ».'], ['Un titre est exclu mais il a un bon score. Normal ?', 'Oui : le filtrage et la note sont deux étapes séparées. Voir « Critères de recherche ».'], ['Pourquoi le rang ne change pas quand je filtre ?', 'Le rang est celui de la stratégie, calculé avant vos filtres. Voir « Classements ».'], ['Une bonne note veut-elle dire « achetez » ?', 'Non. Elle décrit le passé d’un prix.'], ['Pourquoi « — » dans une cellule ?', 'Pas assez de données. Ce n’est pas zéro.'], ['Mes modifications changent-elles les autres comptes ?', 'Non : tout est personnel.'], ['Comment revenir aux réglages d’origine ?', '« Mes stratégies » → Restaurer.'], ['Pourquoi mon gain latent diffère de celui de ma banque ?', 'Méthodes de coût, frais et taux de change peuvent différer. Voir « Achats, ventes et prix de revient ».']].map(([q, a]) => H.fold(q, '<p>' + a + '</p>')).join(''), expert: null
  });

  L.push({
    id: 'admin', group: 'admin', admin: true, title: 'Administration (réservé)', icon: I('settings'), color: '#475569', keywords: 'administration admin cron journaux utilisateurs réglages invitation',
    lead: 'Pour l’administrateur seulement.',
    beginner: ({ H }) => `<ul><li><b>Utilisateurs</b> : comptes, mot d’invitation.</li><li><b>Cron et journaux</b> : planification et suivi des collectes.</li><li><b>Yahoo Finance, FinanceDatabase, Actions / ETF</b> : alimentation et contrôle du catalogue.</li><li><b>Données</b> : vue d’ensemble technique.</li><li><b>Réglages</b> : paramètres communs ; scores de référence et colonnes par défaut via <code>admin.html#scores</code> et <code>admin.html#colonnes</code>.</li></ul>${H.warn('<p>Cette rubrique n’est pas visible des comptes ordinaires, et les routes correspondantes sont protégées côté serveur.</p>')}`, expert: null
  });
})();
