/* Filtre « Liquidité » du catalogue par défaut. */
window.AdminCategoryDemo.filters.push({
  "id": "liquidity",
  "name": "Liquidité",
  "description": "Classez les montants échangés en euros par jour. Historique et estimation cotée restent deux sources distinctes.",
  "editable": true,
  "enabled": true,
  "measures": [
    {
      "id": "turnover_eur",
      "name": "Montant historique",
      "description": "Montant moyen négocié calculé sur les volumes historiques et les cours convertis en euros.",
      "unit": "€/jour",
      "kind": "numeric",
      "domain": [],
      "supportsUnknown": true,
      "categories": [
        {
          "id": "turnover_eur-c0",
          "name": "Limité",
          "min": null,
          "max": 1000000,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#f04452",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « limité » pour cet indicateur."
        },
        {
          "id": "turnover_eur-c1",
          "name": "Intermédiaire",
          "min": 1000000,
          "max": 2000000,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#ff9625",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « intermédiaire » pour cet indicateur."
        },
        {
          "id": "turnover_eur-c2",
          "name": "Important",
          "min": 2000000,
          "max": 4000000,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#a8d85d",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « important » pour cet indicateur."
        },
        {
          "id": "turnover_eur-c3",
          "name": "Très important",
          "min": 4000000,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#10a039",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « très important » pour cet indicateur."
        },
        {
          "id": "turnover_eur-c4",
          "name": "Inconnue",
          "min": null,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#a5afbf",
          "active": true,
          "unknown": true,
          "values": [],
          "description": "Donnée absente pour cette mesure."
        }
      ]
    },
    {
      "id": "quoted_turnover",
      "name": "Montant coté Yahoo · trois mois",
      "description": "Montant quotidien estimé à partir du volume moyen coté Yahoo sur trois mois. Source distincte de l’historique.",
      "unit": "€/jour",
      "kind": "numeric",
      "domain": [],
      "supportsUnknown": true,
      "categories": [
        {
          "id": "quoted_turnover-c0",
          "name": "Limité",
          "min": null,
          "max": 1000000,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#f04452",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « limité » pour cet indicateur."
        },
        {
          "id": "quoted_turnover-c1",
          "name": "Intermédiaire",
          "min": 1000000,
          "max": 2000000,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#ff9625",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « intermédiaire » pour cet indicateur."
        },
        {
          "id": "quoted_turnover-c2",
          "name": "Important",
          "min": 2000000,
          "max": 4000000,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#a8d85d",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « important » pour cet indicateur."
        },
        {
          "id": "quoted_turnover-c3",
          "name": "Très important",
          "min": 4000000,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#10a039",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « très important » pour cet indicateur."
        },
        {
          "id": "quoted_turnover-c4",
          "name": "Inconnue",
          "min": null,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#a5afbf",
          "active": true,
          "unknown": true,
          "values": [],
          "description": "Donnée absente pour cette mesure."
        }
      ]
    }
  ]
});
