# Design de l'interface

Identité : marine (`--brand`) pour la structure, émeraude (`--accent`) pour l'action et la hausse, or (`--gold`) pour les repères ; thème clair et sombre.
Principes : (1) une page = une question (Explorer : quoi acheter ; Fiche : comprendre un titre ; Portefeuilles : ce que je détiens ; Suivi : la méthode marche-t-elle ; Données : d'où vient ce que je vois) ; (2) chaque chiffre porte sa source, sa date et son unité ; (3) filtres avancés dans un tiroir, jamais retirés ; (4) une donnée absente est signalée, jamais inventée ; (5) tableaux triables, graphiques au survol, tout fonctionne à 390 px.
Composants : `page-head`, `sourcebar` (bandeau de sources), `kpi-strip`, `filters`, `rtable`, `tag`, `chip`, `seg`, `metric-grid`, `hero`, graphiques SVG sans dépendance (`charts.js` cours quotidien, `intraday.js` séances de 15 minutes).
Fiche titre : onglets Cours · Intraday 15 min · Analyse de la stratégie · Données et qualité · Contenu du fonds (ETF).
