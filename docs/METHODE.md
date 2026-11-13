# Méthode de calcul (V2)

## Mesures sur une fenêtre de n séances (n+1 clôtures)
Toutes sur le logarithme du cours : une hausse de 10 % suivie d'une baisse de 10 % ne s'annule pas, et un titre à 5 € se compare à un titre à 500 €.

| Mesure | Définition |
|---|---|
| Pente | pente de la régression de ln(cours) sur le temps, en % par séance : 100·(e^b − 1) |
| R² | part de la variance de ln(cours) expliquée par cette droite (0 à 1). Mesure la **régularité** de la hausse |
| Performance | variation entre la première et la dernière clôture, en % |
| Volatilité | écart-type des variations quotidiennes de ln(cours), en % par séance (≥ 3 séances) |
| Repli maximal | plus forte baisse depuis un sommet de la fenêtre, en % |
| ER (efficacité) | rendement net / distance parcourue, en ln : +1 = montée sans repli, 0 = aller-retour, négatif = baisse |

Abandonné par rapport à l'ancien moteur : **accélération** (définition ambiguë), **exposant k** du classement. Les cours bruts et ajustés ne sont jamais mélangés (ajustés si toute la série en a). Les clôtures viennent de Yahoo Spark, déjà corrigées des splits.

## Données douteuses
Un saut de cours d'une séance à l'autre de plus de ×1,6 (ou ÷1,6), sans split connu, est une **rupture** : aucune fenêtre qui la traverse n'est évaluée, le titre est « non évaluable » sur ces périodes. Série trop courte, dernière clôture plus ancienne que celle de la place : « non évaluable » (jamais « écarté »).

### Fenêtres et séances absentes
Une fenêtre de `n` séances est désormais formée des `n+1` dates de clôture attendues par le calendrier de la place, et non des `n+1` dernières lignes présentes en base. Les calendriers Xetra, Euronext, Londres, les places américaines et les autres places prises en charge excluent week-ends et jours fériés propres au marché. Une place sans calendrier pris en charge est déclarée non évaluable : le moteur ne suppose pas qu'elle ouvre du lundi au vendredi.

La pente et le R² régressent sur l'indice réel de chaque séance attendue. Ils restent calculables si au moins `ceil(80 % × clôtures attendues)` sont présentes et si au moins trois points sont disponibles. Ce minimum laisse passer une séance manquante isolée sur une courte fenêtre (5/6) sans compresser le temps; il n'accepte pas les fenêtres extrêmement creuses. Il ne modifie aucun seuil de stratégie. La performance entre bornes exige les deux clôtures de bord. Le cas WHCA.AS atteint tout juste ce plancher sur les 64 dernières clôtures (52/64); son R² sur ces dates est 0,469, sous le seuil existant de 0,556 : le titre échoue donc au critère de régularité au lieu d'être artificiellement retenu.

La performance reste calculable entre les deux bornes si elles existent. En revanche, volatilité quotidienne, repli maximal et ER décrivent un chemin : ils sont indisponibles dès qu'une séance attendue manque, car le mouvement à l'intérieur de l'intervalle absent est inconnu. Aucune clôture n'est recopiée et aucune interpolation n'est faite. Les moyennes mobiles et la variation du jour exigent elles aussi les clôtures précises de leurs séances calendaires.

## Verdicts
- **Retenu** : tous les critères actifs de toutes les périodes actives sont satisfaits.
- **Écarté** : au moins un critère mesuré échoue (même si une autre mesure manque).
- **Non évaluable** : rien n'échoue, mais une mesure manque.
- **Exclu** (catalogue/préfiltre, pas la stratégie) : jamais évalué, jamais recommandé.
Chaque verdict conserve la liste de ses raisons (période, critère, valeur, seuil, résultat).

## Classement
Pour chaque période active, percentile du score (pente, performance, régularité ou −volatilité selon le mode) parmi les titres **retenus du même groupe** (actions ou ETF) ; score final = moyenne pondérée des percentiles (0–100). Départage : symbole.

## Stratégies de départ (propositions, modifiables)
Niveaux de pente = temps pour doubler à ce rythme : doux 8 ans (0,034 %/séance), modéré 4 ans (0,069 ≈ +19 %/an), fort 2 ans (0,138), très fort 1 an (0,276 %/séance = 100·(2^(1/252)−1) ≈ +100 %/an). Régularité par résidu de la droite : souple (R² ≥ 0,56), équilibrée (≥ 0,75), stricte (≥ 0,89).
- **Croissance régulière** : mois et trimestre, pente modérée (≥ 0,069 %/séance), R² souple (≥ 0,56). Classement par régularité. → 191 actions et 67 ETF retenus (≈ 4 %).
- **Croissance rapide** : semaine (pente très forte, performance ≥ 0) et mois (pente très forte, performance ≥ 12 %). Classement par performance. → 389 actions, 11 ETF (≈ 8 %).
- **Rebond** : semaine et mois en hausse douce (R² souple) alors que le semestre n'a pas progressé de plus de 10 %. Classement par pente. → 196 actions, 497 ETF.
- **Hausse calme** : mois et trimestre, pente douce, R² souple, volatilité ≤ 1,5 %/séance (≈ 24 % annualisée), repli ≤ 20 %. Classement par stabilité. → 38 actions, 45 ETF (≈ 0,9 % de l'univers : volontairement très sélective, car seule une minorité de titres respecte le plafond de volatilité, surtout quand le marché est agité ; contrairement aux autres profils, elle ne vise pas 4 à 8 %).

Calibrage du 28/10/2026 sur 9 700 titres réels. Avec les seuils initiaux, « régulière » ne retenait que 52 actions (R² 0,75 sur deux périodes) et « calme » 4 : trop peu pour offrir un choix. Variantes testées : voir l'historique du calibrage dans ce paragraphe ; les réglages restent modifiables par l'utilisateur.

## Stratégies « Momentum 6 mois » et « Momentum 12 mois » (essai, 31/10/2026)

- **Mesure** : variation du cours, en %, entre J−126 et J−21 séances (6 mois) ou entre J−252 et J−21 séances (12 mois). Le dernier mois est volontairement ignoré. Aucun seuil : seul le rang compte (percentile parmi les titres retenus du même groupe, actions et ETF classés séparément).
- **Fiabilité** : la mesure utilise le calendrier de la place (127 ou 253 séances attendues). Une clôture absente à l'une des deux dates, un historique trop court ou une rupture de cours non expliquée après le début de la fenêtre rendent le titre « non évaluable » : jamais d'estimation, jamais de cours futur.
- **Même définition que les tests** : ce qui est calculé est le signal `mom_6_1` / `mom_12_1` de `scripts/backtest_walkforward.py` (rapport `c[-22] / c[-127] - 1` et `c[-22] / c[-253] - 1` sur les clôtures visibles).
- **Stockage** : `series_state.momentum_6m` et `series_state.momentum_12m`, recalculés avec les autres indicateurs. Le profil expérimental `momentum_risk` ajoute les moyennes 200 jours et leur orientation, puis agrège les rangs centiles du momentum 6/12 mois (35/45 %) et inverse les rangs de volatilité/repli annuel (10/10 %). Il décrit des données passées ; il ne constitue pas une validation prédictive.
- **Ce que l'historique a montré** (titres encore cotés aujourd'hui, périodes déjà consultées, donc à lire avec prudence) : le classement du Momentum 6-1 a présenté un avantage moyen sur l'ensemble des titres négociables, qui diminue quand la liquidité exigée augmente et après frais (excès net d'environ +0,5 point par mois pour un rééquilibrage mensuel, non établi statistiquement) ; pertes brutales possibles (mois à plus de −25 %, baisses de plus de 50 % depuis un sommet) ; sélections concentrées sur des titres volatils et sur un même pays. Le Momentum 12-1 donne des résultats voisins, sans différence statistiquement établie avec le 6-1. **Aucune performance n'est promise** ; les profils sont signalés « essai » dans l'interface et le suivi réel (page Suivi, 21 et 63 séances) servira à les confirmer sur des observations nouvelles.
- **Les quatre profils existants ne changent pas** (empreintes vérifiées par test).

## Pastilles, filtres de niveau et résumé du profil
Information seulement : rien de ce qui suit n'entre dans un score, un classement, un critère ou un filtre de stratégie.
- **Période des pastilles.** Régularité (R²) et volatilité/repli se mesurent sur la période de la stratégie active (la plus longue période cochée, ramenée à 1 semaine, 1 mois, 3 mois, 6 mois ou 1 an) : la pastille l'indique (« Régulière · 1 mois »). La négociabilité se mesure sur une autre durée, indépendante de la stratégie : volume moyen 3 mois × cours (« Facilement négociable · 3 mois »).
- **Filtres Régularité / Volatilité / Négociabilité** (Explorer, filtres avancés). Listes à choix multiple comme Pays et Catégorie : rien de coché = tout (même chose que tout cocher). Niveaux = ceux des pastilles (vert, orange, rouge, inconnu), avec leurs effectifs. Ils **masquent seulement**, après le classement, comme le filtre « Titres facilement négociables » : rang et score du catalogue inchangés, ordre relatif inchangé ; un titre retrouvé par son symbole ou son ISIN exact n'est jamais masqué. Ils se cumulent entre eux et avec les autres filtres. Coût : ≈ 90 ms pour les 9 600 titres.
- **Résumé du profil** (fiche d'un titre). « Points forts », « Points de vigilance » et une appréciation descriptive : **Très favorable, Favorable, Mitigé, Défavorable, Indéterminé**. Ce n'est ni une note chiffrée, ni une consigne d'achat ou de vente. Règles, dans l'ordre :
  1. *Indéterminé* : tendance non mesurée sur la période, historique court, ou au moins deux des trois pastilles inconnues (l'inconnu reste inconnu).
  2. *Défavorable* : courbe en baisse sur la période, ou trois risques importants (rouges) ou plus.
  3. *Mitigé* : pas de tendance nette, ou un à deux risques importants, ou une tendance récente qui contredit celle de fond, ou au moins deux points de vigilance (oranges).
  4. *Très favorable* : hausse forte (pente ≥ « fort », temps pour doubler ≤ 2 ans) et régularité, volatilité, négociabilité toutes vertes, aucun autre point de vigilance, aucune pastille inconnue.
  5. *Favorable* : le reste des cas en hausse, avec au plus un point de vigilance.
  Un risque important (rouge) interdit donc « Favorable » et « Très favorable », même pour une très forte hausse. Une hausse ≥ 100 % sur la période est signalée comme point de vigilance (un mouvement aussi rapide peut se retourner vite). La rupture de cours est un risque important ; un historique incomplet ou un cours ancien un point de vigilance.
  *Tendance récente contre tendance de fond* : d'après les performances déjà mesurées sur 1 semaine, 1 mois, 3 mois, 6 mois et 1 an, on signale un repli récent (≤ −5 % sur 1 mois ou 1 semaine) dans une hausse de fond (≥ +10 % sur une période plus longue), ou un rebond récent (≥ +10 %) dans une baisse de fond (≤ −10 %). Sans mesure de fond, rien n'est affirmé. Les avis des analystes n'entrent pas dans l'appréciation.

## Préfiltre de liquidité (réglable en Administration)
Cours ≥ 2 € ; liquidité (cours × volume moyen 3 mois, en euros) ≥ 1 M€/jour pour une action, ≥ 250 k€/jour pour un ETF. Sans cotation Yahoo : pas de décision (le titre n'est ni collecté ni recommandé). Exemple : DVDG.DE, 131 titres/jour à 42 € ≈ 5 520 €/jour → exclu.

## Cotation principale (règle R1)
Place d'origine (pays de l'émetteur) si le produit y est coté ; sinon plus forte liquidité en euros ; départage : devise euro, puis ordre alphabétique. Exemple : SAP → Xetra (SAP.DE).

## Collecte
Tick toutes les 15 minutes : barres de 15 min des places ouvertes (+ dernier créneau), clôtures quotidiennes une fois la séance publiée (30 min après la fermeture). Nuit (02 h UTC) : Quote, taux de change, préfiltre, cotation principale, mesures, détection/réparation des trous, rétention (580 jours / 20 séances). Un jour sans aucune barre pour une place est un jour férié, pas un trou.

**Clôtures manquantes.** La collecte quotidienne utilise le point d'accès groupé « spark » de Yahoo, qui omet parfois des jours au milieu de l'année ; le point d'accès « chart » (un titre par appel) les possède. L'étape d'entretien « Clôtures manquantes » interroge « chart » pour les titres dont l'année est incomplète (`series_state.coverage_252 < 1`), les moins troués d'abord, par lots de 150 (60 s maximum, arrêt au premier 429, un même titre n'est repris qu'après 30 jours). Elle n'ajoute que les jours absents et réglés (`INSERT IGNORE`) : une clôture existante n'est jamais modifiée. Les titres qui deviennent complets deviennent évaluables aux calculs suivants (leurs rangs peuvent changer). Administration → carte C → « Combler les clôtures manquantes » traite d'un coup tout le catalogue (sans plafond ni délai), puis recalcule les indicateurs ; relançable si Yahoo limite les appels. Mesure sur 120 titres incomplets : 302 clôtures ajoutées, 77 titres complets, 36 s ; les titres à plus de 5 trous sont surtout de vrais manques de Yahoo.

## Ordre de la recherche (Explorer et fiche)
1. Univers : toutes les cotations éligibles (`v_recommendable` : sélectionnées et principales). Jamais une cotation exclue, quels que soient les critères ou les filtres.
2. Filtres de l'utilisateur (type, place, pays, catégorie, PEA, détenus, place ouverte, budget, prix, volatilité et repli maximaux, volume, données à jour) : ils déterminent les titres examinés. Les filtres numériques utilisent les mesures de la plus longue période active.
3. Évaluation de ces titres selon la configuration réellement choisie (périodes, seuils, filtres techniques). Un profil prédéfini ne fait que préremplir cette configuration : modifiée, elle est appliquée telle quelle (`name` = `custom`). « Recherche libre » = aucun critère de départ.
4. Classement : rang et score sont des percentiles parmi les titres retenus de la sélection, par groupe (actions / ETF). Changer les filtres change donc le classement ; le score minimum s'applique après.
5. Pagination, uniquement après les étapes précédentes. Les nombres « titres examinés sur N » et « résultats » sont affichés.
La fiche d'un titre reçoit la même configuration et les mêmes filtres (depuis l'Explorer : `titre.html?src=explorer`) ; elle annonce « Verdict calculé selon … » et permet de choisir un profil ou la stratégie d'un portefeuille. Sans configuration transmise, le réglage par défaut est annoncé comme tel.
Recherches enregistrées : critères + filtres + tri (table `explorer_saved`, type `search`).

## Limites connues des données et des calculs (audit fonctionnel du 29/10/2026)
- **Rendements hors dividendes.** Les clôtures viennent de Yahoo (Spark) : ajustées des splits par Yahoo, pas des dividendes (`adj_close_px` reste vide). Un fonds ou une action qui distribue est donc désavantagé par rapport à une part de capitalisation de même performance totale.
- **Splits.** Les cours de Yahoo (Spark et Chart) ne sont pas toujours ajustés des splits : pour certains titres (constaté : DHY, TACK) le saut reste dans les données et le split est déclaré à part (`events.splits` de l'API Chart). `adj_close_px` reste donc vide et ne sert pas à corriger. Un saut de cours qui ressemble à un ratio usuel (×2, ÷10, ×3/2…) est noté dans `split_log` ; Yahoo est ensuite interrogé : un split déclaré à la même date (± 5 jours) dont le ratio explique le saut (± 15 %) est confirmé et écrit dans `corporate_events` ; le calcul des séries divise alors les clôtures antérieures par ce ratio. Sans déclaration, le saut passe en `real_move` : ce statut veut dire seulement « Yahoo n'a pas déclaré de split qui l'explique au moment de la vérification » ; ce n'est ni une preuve que le mouvement est réel, ni une preuve qu'aucun split n'existe (Yahoo peut déclarer un split avec retard). Rien n'est corrigé et le titre reste « non évaluable » sur les fenêtres qui le traversent (seuil : variation d'une séance au-delà de ×1,6 ou ÷1,6), avec un motif affiché « saut de cours inhabituel dans la période » (jamais « calendrier indisponible »). **Revérification bornée (`splits.recheck`, étape de la maintenance, migration `20261102_split_log_recheck`)** : un saut `real_move` est interrogé de nouveau 7 jours après la vérification initiale, puis 14 jours après la deuxième réponse, soit au plus 3 réponses de Yahoo au total, et seulement pendant 60 jours après le saut ; au plus 30 titres par passage. Une déclaration tardive cohérente le fait passer en `confirmed` (écrit dans `corporate_events`, séries ajustées au calcul suivant, quantités des portefeuilles ajustées par le registre). Une réponse absente ou illisible n'est jamais comptée comme une vérification (nouvel essai 3 jours plus tard) ; une limitation de Yahoo arrête le passage en gardant le travail déjà fait. Sans les colonnes de la migration, le code se comporte comme avant (aucune revérification).
- **Portefeuilles et splits.** Un split ou un regroupement confirmé par le fournisseur (`split_log`, statut « confirmed ») est appliqué automatiquement par le registre : à la date de l'événement, la quantité détenue est multipliée par le ratio, le coût total ne change pas, et une vente d'après-split est contrôlée sur la quantité ajustée. Une correction faite à la main avant (achat à prix 0 à partir de la date du split) est reconnue et n'est pas comptée deux fois. Dividendes et liquidités ne sont pas gérés.
- **Totaux d'un portefeuille et du Bilan.** Coût, plus-values et gains ne portent que sur les positions calculables : une transaction sans taux de change historique (ou une vente supérieure à la quantité détenue) exclut **ce titre** de ces totaux, signalé nommément, sans effacer les résultats des autres titres ni des autres portefeuilles. La valeur totale compte toutes les positions.
- **Jours fériés.** Il n'y a pas de calendrier : un jour est considéré férié quand la collecte quotidienne de la place est passée après la clôture, presque sans erreur, et que moins de 5 % des titres suivis ont une clôture ce jour-là. Une panne de Yahoo (beaucoup d'erreurs) n'est jamais prise pour un férié.
- **PEA.** « PEA probable » = action d'une société de l'UE ou de l'EEE (siège d'après FinanceDatabase) cotée sur une place européenne. Les ETF sont toujours « à vérifier » : leur éligibilité dépend de l'indice et du domicile, que les données ne donnent pas.
- **Catalogue.** Les noms servent à écarter bons de souscription, droits, unités de SPAC et ETF à effet de levier ; « Multi Units Luxembourg - Lyxor… » ou « Short Duration » ne sont plus pris pour des dérivés. Après modification des règles : refaire « Filtrer FinanceDatabase », « Importer les informations Yahoo » puis « Filtrer Yahoo » pour réintégrer les titres libérés.
- **Suivi des classements.** L'écart à l'univers compare moyenne à moyenne. Les classements de jours voisins se chevauchent (« Cas » n'est pas un nombre d'observations indépendantes) et la plupart des jours sont « reconstitués » à partir de l'univers actuel (biais de survie) : à lire comme une description, pas comme une preuve.
- **Sources.** Yahoo est interrogé par des points d'accès non officiels ; FinanceDatabase peut être épinglé avec `JIGO_FDB_REF` (commit ou étiquette) pour un catalogue reproductible.
- **« Cours ancien ».** Un titre peu échangé (ETF de niche) peut n'avoir aucune transaction depuis 30 minutes sans que rien ne soit anormal : son cours est alors le dernier échange, toujours d'actualité. Le cours est « ancien » si son dernier échange date d'avant la dernière clôture due, ou, pendant la séance, si NI le dernier échange NI la dernière collecte de 15 minutes de la place ne datent de moins de 30 minutes (donnée réellement ancienne : collecte arrêtée). L'heure de référence est l'horloge UTC du serveur ; les heures d'ouverture sont celles de la place (`market/hours.py`).
- **Erreurs de données corrigées (affichées sur la fiche, « Données corrigées »).** (1) Un saut de ×100 ou ÷100 (± 6 %) est un changement d'unité (livres/pence, rands/cents…) : l'historique antérieur est mis à l'échelle de la dernière unité, le vrai mouvement restant est conservé. (2) Un cours isolé à plus de ×4 ou ÷4 de ses deux voisines, qui se ressemblent (à ×1,6 près), est une erreur ponctuelle : il est ignoré, sans être remplacé par un prix inventé. Rien d'autre n'est modifié : un vrai mouvement, même violent, reste une rupture (« non évaluable » sur les fenêtres qui le traversent). Effet mesuré sur la production : 14 titres concernés, les mesures de tous les autres sont identiques, aucun changement dans les 20 premiers des quatre profils.

## Négociabilité : le filtre « Titres facilement négociables »

- **Mesure unique** : valeur échangée par jour ≈ volume moyen sur 3 mois (Yahoo Quote) × cours converti en euros. C'est une estimation fournisseur, pas du volume exécuté. C'est la seule donnée de volume fiable que nous stockons (pas de volume journalier, pas de spread).
- **Trois niveaux, un seul calcul** (`engine.analytics.series.signals.liquidity`, utilisé par le filtre, la pastille du classement et la fiche) : *facilement négociable* ≥ 4 × le minimum du préfiltre, *à surveiller* entre 2 × et 4 ×, *négociabilité limitée* en dessous de 2 ×. Avec les minimums actuels (1 M€ action, 250 k€ ETF) : actions 2 M€ / 4 M€, ETF 500 k€ / 1 M€. Justification : un ordre de 10 000 € ne doit pas dépasser environ 0,5 % de la valeur échangée en un jour pour une action et 2 % pour un ETF (les teneurs de marché élargissent la liquidité réelle des ETF).
- **Données absentes ou plus vieilles que 10 jours** : « négociabilité non déterminée », jamais « limitée ». Ces titres restent affichés.
- **Le filtre masque seulement, après le classement.** Rang et score restent ceux du catalogue (aucun recalcul) ; les suivants remontent dans la liste (colonne « # » = position dans la liste filtrée). Désactivé, l'ordre et les scores sont identiques à avant. La pagination s'applique après le filtre. Un titre détenu n'est jamais masqué ; un titre trouvé par son symbole ou son ISIN exact reste affiché avec sa mention. Le Suivi des classements n'est pas filtré.
- **Indicateurs complémentaires, jamais des critères** : part des créneaux de 15 min avec une bougie (note de fiche sous 70 %), et, pour un ETF européen dont le nom indique des actions américaines, rappel que les échanges peuvent être moins fréquents avant l'ouverture de Wall Street. Une bougie manquante n'est pas une absence d'échange.
- **Limites** : un seul chiffre de volume par titre (moyenne 3 mois) ; pas de spread ; pas de volume par créneau horaire ; l'exposition américaine d'un ETF n'est déduite que de son nom.


## Avis des analystes, taille et activité récente (30/10/2026)

- **Analystes** : consensus relevé par Yahoo pour les ACTIONS seulement (« 1.8 - Buy » devient « Achat (1,8) » ; 1 = achat fort, 5 = vente forte). Information externe : ce n'est pas une recommandation de Jigobourso et il n'entre dans aucun score, filtre ou classement. Absent = « — », jamais un défaut du titre. Jamais affiché pour un ETF.
- **Catégorie de taille** (fiche action) : d'après la capitalisation convertie en euros (micro < 300 M€, petite < 2 Md€, moyenne < 10 Md€, grande < 200 Md€, très grande au-delà) ; non indiquée quand la devise est en pence.
- **Activité récente** : le volume moyen sur 10 jours est comparé à celui sur 3 mois ; au-delà de ×1,5 ou en dessous de ×0,67, la fiche l'explique. C'est un signal d'activité, pas de liquidité durable ni de volatilité. Les seuils du filtre « Titres facilement négociables » ne changent pas.
- Non retenus faute de fiabilité (inventaire du 30/10/2026) : bid/ask (valeurs à 0, ask inférieur au bid), rendement de distribution et ratio cours/valeur comptable des ETF, indice suivi (absent de la réponse).

## Portefeuilles : gains, pourcentages et cours manquants (audit du 03/11/2026)

- **Résumé depuis le début** : gain total = latent + réalisé, frais compris. Le pourcentage est ce gain divisé par les **achats cumulés, frais compris** (`invested_total`). Les produits des ventes ne réduisent pas le dénominateur. Le coût restant des positions (`cost`, libellé « Investi ») et les apports nets (achats moins ventes nettes) sont deux notions distinctes de ces achats cumulés.
- **Sur une période** : gain = variation de la valeur moins les apports nets de la période ; pourcentage = gain / (**valeur à la borne de départ + achats de la période, frais compris**). Pour « Tout », la valeur avant le premier achat est zéro : ce calcul rejoint donc celui du résumé. Les achats sont fournis par une série cumulée `purchases`, distincte de `net_in`, au niveau du portefeuille et de chaque titre. Les ventes restent dans le gain mais ne sont jamais déduites du dénominateur. Une vente totale conserve ainsi le réalisé et son pourcentage. À capital de référence nul ou borne non valorisable, le pourcentage est indisponible. Ce ratio descriptif n'est ni un rendement annualisé, ni un TWR, ni un TRI ; sur des périodes différentes, les capitaux de référence diffèrent. Les pourcentages propres à chaque titre ne s'additionnent pas ; les gains en euros s'additionnent quand toutes les lignes sont calculables.
- **« Depuis l'achat » du tableau** : plus-value latente des quantités restantes, au prix de revient moyen pondéré. Elle n'inclut pas les gains déjà réalisés ; le gain sur « Tout » les inclut. Le graphique détaillé du titre décrit le cours hors frais et change, pas le rendement du registre.
- **Cours manquant** : aucun remplacement par un prix d'achat, aucune valorisation implicite à zéro. Une position sans cours ni clôture exploitable, ou sans change de valorisation, a une valeur et un latent `null`. La valeur totale, le latent total, les poids et le gain total sont indisponibles tant qu'une position reste non valorisable ; les coûts historiques connus et les gains réalisés restent disponibles. Le Bilan applique la même convention. Une dernière clôture disponible peut être utilisée : sa date et sa source sont indiquées ; elle n'est pas présentée comme une transaction courante. L'historique utilise la dernière observation de marché connue à chaque date et laisse des trous (`null`) avant la première observation, sans inventer de cotation. Les apports nets restent affichables indépendamment de ces trous.
- **1J** : seule la valeur en euros des **quantités actuelles**, sur la dernière séance intraday stockée, est disponible. Les mouvements intrajournaliers ne sont pas rejoués. Comparer, Gain et % sont donc explicitement désactivés pour cette période, avec explication visible ; ils redeviennent accessibles en quittant 1J. L'écart entre première et dernière barre n'est pas une plus-value depuis l'achat.
- **Splits et lots** : les quantités FIFO ouvertes sont ajustées jusqu'à aujourd'hui, comme les positions, même sans transaction après l'événement. Le coût global et le réalisé ne changent pas du seul fait d'un split. Les corrections manuelles reconnues ne sont pas appliquées deux fois.
- **Momentum des alertes** : les mesures du moteur sont déjà des pourcentages (−10 signifie −10 %) et ne sont pas multipliées par 100 pour leur affichage. Aucun seuil ou profil de classement n'est modifié.

Régressions : `make fast`, `make integ`, puis `tests/e2e/portfolio-audit.cjs` sur les trois largeurs 1280/390/375. Préparer une base **locale isolée** avec `db/schema.sql`, puis exécuter `JIGO_TEST_DATABASE=1 JIGO_DB_NAME=jigobourso_portfolio_audit PYTHONPATH=. .venv/bin/python tests/seeds/portfolio_audit_seed.py` avec les variables locales `JIGO_DB_*` et PHP disponibles. Ce script remet à zéro uniquement une base autorisée `jigobourso_it` ou `jigobourso_portfolio_audit` sur `127.0.0.1`. Démarrer PHP sur cette même base, puis lancer `JIGO_TEST_DATABASE=1 BASE=http://127.0.0.1:18090 JIGO_CHROMIUM=/chemin/chromium node tests/e2e/portfolio-audit.cjs`. `PLAYWRIGHT_MODULE` et `AUDIT_OUT` permettent de choisir le module Playwright et le dossier des résultats. Ne jamais lancer cette préparation contre la production.

## Moteur de scores V4 unique et sept stratégies (06/11/2026)

**Un seul moteur de notation** : `engine/analytics/scoring/scores.py` (`score_title`) pour le score simple et le score complexe, alimenté par `score_service.py` (cache selon les paramètres et la version des données) et réglé par `scores_admin.py`. Toutes les stratégies passent par lui : seuls leurs réglages diffèrent.

**Réglages propres à chaque stratégie** (profil enregistré dans `scores_profiles`, valeurs par défaut explicites, bornes validées, retour à la valeur par défaut dans l'administration) :

| Réglage | Défaut | Bornes | Effet |
|---|---|---|---|
| `sat_a` — saturation de la dynamique | 17 | 5 à 200 | croissance (%) sur 5 séances qui donne 100 ; `saturation(n) = sat_a·(n/5)^0,52` |
| `accel_ref` — référence d'accélération | 0,4 | 0,05 à 5 | `ref = saturation(n)/n × accel_ref` ; note = 50 + 50·clamp(accél/ref, −1, 1)·clamp(min(R², R²_préc)/0,6) |
| `vol_mode` — notation de la volatilité | `absolute` | `absolute`, `relative` | absolue : 100 à 1 %/séance, 0 à 5 % ; relative : rapport volatilité/pente (plancher de pente 0,3 %), 100 à 1, 0 à 4 |
| `momentum_horizon` | `6m` | `6m`, `12m`, `blend` | horizon de la composante « Momentum » (100 à +60 % / +100 %) |

Poids du score complexe (neuf composantes, total 100 %), **propres à chaque profil, sans repli global** (l'ancien repli de `score_service.apply_global` vers des poids communs est supprimé) : dynamique, R², séances positives, concentration, volatilité, drawdown, liquidité, accélération, **momentum** (nouveau, variation hors dernier mois, `series_state.momentum_6m/12m`) et **contexte de rebond** (nouveau, 100 si le rendement 6 mois est ≤ −10 %, 0 s'il est ≥ +20 %). Les deux dernières valent 0 par défaut : les profils enregistrés avant leur ajout ne changent pas. Une composante indisponible sort du calcul (jamais 0, jamais bonus).

**Les sept stratégies** (`scores_admin.V4_STRATEGIES`) : Croissance régulière, Croissance rapide (inchangée, une seule), Rebond, Hausse calme, Momentum 6 mois, Momentum 12 mois, Momentum ajusté du risque. Les seuils d'admission (pente, R², volatilité, drawdown, rendement 6 mois du Rebond) restent des filtres : ils n'entrent jamais dans une note. Les stratégies personnelles (`ct:<utilisateur>:<id>`) gardent leur profil.

Limite connue : le filtre « au-dessus de la moyenne 200 jours » de l'ancien profil Momentum ajusté du risque n'est pas une notation ; il reste un filtre d'affichage. Les portefeuilles, alertes et le suivi utilisent encore `strategy.py` (profils historiques) pour leurs propres décisions : à migrer séparément.

### Correction de la normalisation du score complexe (scores V5, 07/11/2026)
Le score complexe est la moyenne, pondérée par le poids entier de chaque composante disponible, des notes de composantes (chaque note étant elle-même la moyenne sur les périodes où la mesure existe). Avant la correction, le numérateur utilisait ce poids entier mais le dénominateur le multipliait par la part de périodes mesurées : un titre dont une composante n'existait que sur une partie des périodes pondérées était gonflé (jusqu'à +28 points, un score de 101,5 observé). Le dénominateur est maintenant la somme des poids des composantes disponibles. Aucun titre dont toutes les mesures existent ne change ; le score simple, les autres formules et la fiabilité (`coverage`, statut « partiel ») ne changent pas. `scores.VERSION` passe à 5 : les scores en cache sont recalculés. Mesure sur les 9 611 titres de la prod (06/11) : 16 à 787 notes complexes baissent selon la stratégie (maximum −28,0 points, Hausse calme), aucun score ne dépasse plus 100. Tests : `tests/fast/test_scores.py` (données partielles, bornes 0-100 sur 4 000 cas aléatoires, inversion de rang entre un titre complet et un titre incomplet).


## Stratégies intégrées : critères de recherche et barème de notation séparés (07/11/2026)

**STRATÉGIE** = granularités actives, pente minimale (% par séance) et R² minimum : des critères de *recherche*. Ils filtrent l'affichage du Classement (bouton « Critères appliqués / ignorés »), jamais une note ni un rang.
**SCORES** = barème (poids du score complexe, poids des granularités, saturation, référence d'accélération, score par défaut). Le rendement, la volatilité et le drawdown contribuent aux scores, sans jamais être des seuils.

Critères (niveaux historiques exacts de `strategy.py`, V2 : pente `100·expm1(ln 2 / (années·252))`, R² « flexible » = 1 − (2/3)²) :

| Stratégie | Granularités | Pente min. | R² min. |
|---|---|---|---|
| Croissance rapide | semaine, mois | 0,27543703768897265 | aucun |
| Croissance régulière | mois, trimestre | 0,06878824951818499 | 0,5555555555555556 |
| Hausse calme | mois, trimestre | 0,034388212013465085 | 0,5555555555555556 |
| Rebond | semaine, mois | 0,034388212013465085 | 0,5555555555555556 |
| Momentum 6 mois | trimestre, semestre | aucune | aucun |
| Momentum 12 mois | semestre, année | aucune | aucun |
| Momentum ajusté du risque | semestre, année | aucune | aucun |

Retirés des critères : rendement mensuel ≥ 12 % (Rapide), volatilité ≤ 1,5 % et drawdown ≤ 20 % (Hausse calme), rendement semestriel ≤ 10 % (Rebond) ; les filtres MM200 du Momentum ajusté du risque ne sont pas réactivés.
Rebond : le semestre n'a ni pente ni R² (poids 0) mais reste une période chargée, car la note « contexte de rebond » lit son rendement (100 si ≤ −10 %, 0 si ≥ +20 %).
Les performances réelles entrent dans les scores par la croissance lissée (pente de régression, dynamique), le momentum 6-1 / 12-1 mois et le contexte de rebond. Formules inchangées.

## Statut de stratégie (retenue / exclue / indéterminée)

Deux mécanismes séparés. Les **scores V4** (simple, complexe) et leurs **rangs généraux** se calculent sur tous les titres évaluables, sans aucune référence à une stratégie de recherche. Les **critères de recherche** d'une stratégie (granularités actives, pente minimale en % par séance, R² minimal, règles Expert) décident seulement du **statut** :

- **Retenue** : tous les critères actifs sont respectés (une stratégie sans critère, comme Momentum, retient tout, volontairement) ;
- **Exclue** : au moins un critère actif est mesuré et non respecté ;
- **Indéterminée** : aucun critère n'est violé mais une mesure nécessaire manque. Jamais une exclusion ; visible dans « Toutes ».

Moteur unique : `engine/analytics/scoring/criteria.py` (`normalize`, `evaluate`, `counts`), alimenté par `strategy_metrics`, utilisé par `ranking_table` (Classement, `ranking/table` et `ranking/verdicts` pour les critères en cours de modification), par `scores_admin.ranking` (page Scores/Classement, filtre `verdict`) et par la fiche (`service._v4_strategy`). Le navigateur n'évalue plus rien.

Pages : sélecteur **Retenues | Exclues | Toutes** (Classement : Retenues par défaut ; Scores : Toutes par défaut), compteurs réels sur le périmètre courant (filtres secondaires, recherche), badge « Statut stratégie » dans les tableaux. Le détail (mesure, seuil, résultat par critère) n'est que dans la fiche.

Fiche : le lien du Classement porte `ct=<stratégie>` ; des réglages non enregistrés sont déposés sous `ctx=<clé>` (localStorage, même origine). Brouillon introuvable ou stratégie inconnue : la fiche le dit et ne rend aucun verdict (indéterminée), jamais « retenue ». Scores et rangs de la fiche viennent de la stratégie V4 du contexte : mêmes valeurs que dans le Classement.

Unités : seuils et mesures de pente en % par séance ; la pente « sur période » (composée) n'est qu'une lecture et ne se compare jamais à un seuil par séance.

## Colonnes, tris et affichage des tableaux (Administration → Colonnes)

Préférences d'affichage uniquement : aucun calcul, aucun réglage de stratégie ou de score. Quatre configurations indépendantes : Explorer / Scores × ordinateur / mobile (mobile = largeur ≤ 700 px, suivie en direct).
Catalogue unique : `app/config/table_columns.json` (identifiants, libellés, tri possible, valeurs par défaut). Stockage : `settings.table_layouts` (révision optimiste), service `app/services/table_layouts.php`, routes `table-layouts`, `admin/table-layouts[/save]`.
Chaque configuration enregistre l'ordre complet des colonnes (masquées comprises : elles gardent leur position), visibilité, largeur (auto ou 48–480 px), jusqu'à trois tris, statut de stratégie initial et, pour Explorer, lignes par page. Colonne Titre toujours visible.
Compatibilité : identifiant inconnu ignoré à la lecture ; colonne ajoutée au catalogue rangée en fin avec sa visibilité par défaut ; enregistrement strict (jamais de sauvegarde silencieuse d'une configuration invalide).
Priorité : adresse (`?verdict=`, `?sort=colonne:sens`, `?page_size=`) > choix de l'utilisateur pendant la consultation > valeurs de l'administration. Tri Explorer : sur tous les résultats, valeurs absentes en dernier, égalités par rang général puis identifiant. Tri Scores : fait côté serveur sur toute la liste. Le rang global n'est jamais recalculé par un tri.
Les catégories des filtres secondaires restent dans « Filtres et catégories ».

Granularité Jour et colonne « Var. 1J (%) » : voir `docs/ADMIN_SCORES_V4.md` (section « Granularité Jour »). Jour est facultatif, désactivé et à 0 % partout par défaut ; la variation 1J est la variation entre les deux dernières séances clôturées de la place du titre, indépendante de la période choisie pour les autres indicateurs.

## Barre de risque d'un achat (portefeuille)

Pour chaque achat détenu, une barre verte / orange / rouge résume l'état du cours depuis l'achat (`engine/analytics/portfolio/risk.py`). C'est un repère : rien n'est vendu automatiquement et rien n'est prédit.

Trois signaux, notés de 0 à 2 : **tendance** (pente récente comparée à la pente longue, sur des fenêtres qui dépendent de la stratégie : rapide 21/63 séances, régulière 63/126, Momentum 126/252), **recul** depuis le plus haut observé depuis l'achat (seuil = 2 × volatilité quotidienne × √horizon, entre 6 % et 30 % ; serré pour les stratégies rapides, large pour les longues) et **stabilité** (R² qui s'effondre par rapport à la fenêtre précédente). Somme 0-1 : tendance intacte ; 2-3 : à surveiller ; 4-6 ou recul au-delà du seuil : vente à envisager. Un cours très au-dessus de sa moyenne 50 jours (+25 %) n'est qu'une information, jamais notée.

Un saut de cours (règle ×1,6) ou un historique trop court donnent « non évaluée » plutôt qu'une fausse alerte. Les réglages par achat existants (seuil de recul personnel, désactivation) s'appliquent. Les valeurs par défaut sont des points de départ modifiables, non validés par un test historique concluant (les tests de règles de sortie restent exploratoires : biais de survivance et de sélection).


## Revue manuelle des splits

La page **Administration → Splits** (`splits.html`) présente les ruptures stockées dans `split_log`, les prix avant/après, le ratio proposé et les contrôles fournisseur. La détection ne se limite plus aux ratios usuels : tout saut inexpliqué déjà repéré dans les séries peut devenir un candidat, avec un ratio estimé à vérifier.

L'administrateur choisit les parts anciennes/nouvelles et une source ou justification. L'application vérifie le sens et la cohérence du ratio avec le saut, confirme l'événement dans `corporate_events`/`split_log`, conserve la décision et son auteur dans `split_reviews` et ajoute une entrée à `split_review_history`. Les transactions d'origine ne sont pas modifiées. Un recalcul des indicateurs est lancé en arrière-plan ; la demande persistée est reprise par le cron si nécessaire. Le verrou des calculs et la révision de la décision évitent les mises à jour concurrentes ; une confirmation ne peut pas être appliquée deux fois.

Un refus ne corrige ni le cours ni les quantités et interdit la confirmation automatique ultérieure tant que le cas n'est pas remis en attente. Une opération déjà confirmée est consultable, sans bouton de modification ou d'annulation dans cette page. Ces décisions concernent les données de marché communes et nécessitent les droits administrateur.

## Mes filtres de l’Explorer

`mes-filtres.html` édite les définitions personnelles des filtres : activation, groupe, ordre, catégories, libellés, bornes, couleurs et sélections par défaut. Elle n'affiche plus de filtres par stratégie et n'écrit aucun réglage de stratégie. Les modifications sont stockées dans `settings` sous `explorer_secondary_user:<identifiant de session>`, avec contrôle de révision ; elles sont superposées aux définitions partagées lors de la lecture de l’Explorer. Les autres comptes et la configuration d’administration ne sont pas modifiés. Rétablir un filtre enlève uniquement sa personnalisation et reprend les valeurs par défaut partagées. Les métadonnées fixes (pays, secteur, place, type) restent issues du catalogue ; leur visibilité et leurs sélections par défaut sont personnalisables. Les notes et les rangs ne sont pas recalculés par cet éditeur.
