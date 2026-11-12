/* Filtre « Rendements par horizon » du catalogue par défaut. */
window.AdminCategoryDemo.filters.push({
  "id": "returns",
  "name": "Rendements par horizon",
  "description": "Les catégories sont propres à chaque horizon. Ces performances historiques ne sont pas des prévisions.",
  "editable": true,
  "enabled": true,
  "measures": [
    {
      "id": "perf-week",
      "name": "1 semaine · ≈ 5 séances",
      "description": "Variation observée entre les bornes de la fenêtre de référence, indépendante du score.",
      "unit": "%",
      "kind": "numeric",
      "domain": [],
      "supportsUnknown": true,
      "categories": [
        {
          "id": "perf-week-c0",
          "name": "Nul ou négatif",
          "min": null,
          "max": 0,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#f04452",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « nul ou négatif » pour cet indicateur."
        },
        {
          "id": "perf-week-c1",
          "name": "Hausse limitée",
          "min": 0,
          "max": 5,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#ff9625",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « hausse limitée » pour cet indicateur."
        },
        {
          "id": "perf-week-c2",
          "name": "Hausse marquée",
          "min": 5,
          "max": 15,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#a8d85d",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « hausse marquée » pour cet indicateur."
        },
        {
          "id": "perf-week-c3",
          "name": "Hausse forte",
          "min": 15,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#10a039",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « hausse forte » pour cet indicateur."
        },
        {
          "id": "perf-week-c4",
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
      "id": "perf-month",
      "name": "1 mois · ≈ 21 séances",
      "description": "Variation observée entre les bornes de la fenêtre de référence, indépendante du score.",
      "unit": "%",
      "kind": "numeric",
      "domain": [],
      "supportsUnknown": true,
      "categories": [
        {
          "id": "perf-month-c0",
          "name": "Nul ou négatif",
          "min": null,
          "max": 0,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#f04452",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « nul ou négatif » pour cet indicateur."
        },
        {
          "id": "perf-month-c1",
          "name": "Hausse limitée",
          "min": 0,
          "max": 5,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#ff9625",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « hausse limitée » pour cet indicateur."
        },
        {
          "id": "perf-month-c2",
          "name": "Hausse marquée",
          "min": 5,
          "max": 15,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#a8d85d",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « hausse marquée » pour cet indicateur."
        },
        {
          "id": "perf-month-c3",
          "name": "Hausse forte",
          "min": 15,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#10a039",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « hausse forte » pour cet indicateur."
        },
        {
          "id": "perf-month-c4",
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
      "id": "perf-quarter",
      "name": "3 mois · ≈ 63 séances",
      "description": "Variation observée entre les bornes de la fenêtre de référence, indépendante du score.",
      "unit": "%",
      "kind": "numeric",
      "domain": [],
      "supportsUnknown": true,
      "categories": [
        {
          "id": "perf-quarter-c0",
          "name": "Nul ou négatif",
          "min": null,
          "max": 0,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#f04452",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « nul ou négatif » pour cet indicateur."
        },
        {
          "id": "perf-quarter-c1",
          "name": "Hausse limitée",
          "min": 0,
          "max": 5,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#ff9625",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « hausse limitée » pour cet indicateur."
        },
        {
          "id": "perf-quarter-c2",
          "name": "Hausse marquée",
          "min": 5,
          "max": 15,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#a8d85d",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « hausse marquée » pour cet indicateur."
        },
        {
          "id": "perf-quarter-c3",
          "name": "Hausse forte",
          "min": 15,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#10a039",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « hausse forte » pour cet indicateur."
        },
        {
          "id": "perf-quarter-c4",
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
