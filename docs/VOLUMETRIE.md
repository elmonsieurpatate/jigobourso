# Volumétrie — mesure sur base jetable (28/10/2026)

Méthode : `scripts/volumetry_test.sql` sur MariaDB 10.11 locale (port 33307), tables `ROW_FORMAT=COMPRESSED`, données **synthétiques** (prix à 6 décimales avec bruit : compressent moins bien que de vrais cours, donc estimation prudente).
Charge : 153 000 cotations, 5 510 titres admis × 400 séances, 4 500 titres × 20 séances × 30 créneaux de 15 min, 19 842 `latest_prices`, 8 fenêtres de métriques par titre admis.

| Table | Lignes | Mo (données + index) |
|---|---:|---:|
| daily_prices | 2 101 915 | 92,9 |
| intraday_prices (15 min, 20 séances) | 2 713 759 | 91,4 |
| listings | 152 507 | 9,6 |
| strategy_metrics | 43 978 | 3,5 |
| latest_prices | 19 968 | 1,5 |
| instruments | 20 079 | 1,5 |
| series_state | 5 614 | 0,5 |
| **Total** | | **201 Mo** |

Contre 2 320 Mo aujourd'hui (≈ 9 %). Marge pour 30 séances 15 min : ≈ +45 Mo ; pour 60 séances : ≈ +180 Mo.
Non mesuré : espace disque réel des fichiers (`information_schema` seulement), index `wdbi_*` automatiques d'Hostinger, pic de migration. À revalider sur de vraies données exportées en P0.
