/* Filtre « Pics de hausse / baisse » du catalogue par défaut. */
window.AdminCategoryDemo.filters.push({
  "id": "spikes",
  "name": "Pics de hausse / baisse",
  "description": "Configurez séparément les extrêmes de hausse et de baisse. Une pire séance conserve son signe négatif.",
  "editable": true,
  "enabled": true,
  "measures": [
    {
      "id": "largest_day",
      "name": "Meilleure séance",
      "description": "Meilleure variation quotidienne observée sur la fenêtre de référence.",
      "unit": "%",
      "kind": "numeric",
      "domain": [],
      "supportsUnknown": true,
      "categories": [
        {
          "id": "largest_day-c0",
          "name": "Limitée",
          "min": null,
          "max": 3,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#10a039",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « limitée » pour cet indicateur."
        },
        {
          "id": "largest_day-c1",
          "name": "Marquée",
          "min": 3,
          "max": 7,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#a3d85d",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « marquée » pour cet indicateur."
        },
        {
          "id": "largest_day-c2",
          "name": "Forte",
          "min": 7,
          "max": 15,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#f4c900",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « forte » pour cet indicateur."
        },
        {
          "id": "largest_day-c3",
          "name": "Très forte",
          "min": 15,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#ff9625",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « très forte » pour cet indicateur."
        },
        {
          "id": "largest_day-c4",
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
      "id": "worst_day",
      "name": "Pire séance",
      "description": "Pire variation quotidienne observée sur la fenêtre de référence.",
      "unit": "%",
      "kind": "numeric",
      "domain": [],
      "supportsUnknown": true,
      "categories": [
        {
          "id": "worst_day-c0",
          "name": "Très forte baisse",
          "min": null,
          "max": -10,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#f04452",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « très forte baisse » pour cet indicateur."
        },
        {
          "id": "worst_day-c1",
          "name": "Forte baisse",
          "min": -10,
          "max": -5,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#ff9625",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « forte baisse » pour cet indicateur."
        },
        {
          "id": "worst_day-c2",
          "name": "Baisse modérée",
          "min": -5,
          "max": -2,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#a8d85d",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « baisse modérée » pour cet indicateur."
        },
        {
          "id": "worst_day-c3",
          "name": "Baisse limitée",
          "min": -2,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#10a039",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « baisse limitée » pour cet indicateur."
        },
        {
          "id": "worst_day-c4",
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
