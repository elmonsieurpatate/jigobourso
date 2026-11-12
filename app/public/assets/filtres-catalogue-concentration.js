/* Filtre « Concentration des gains » du catalogue par défaut. */
window.AdminCategoryDemo.filters.push({
  "id": "concentration",
  "name": "Concentration des gains",
  "description": "Trois définitions distinctes sont disponibles. Les catégories de chaque mesure sont indépendantes.",
  "editable": true,
  "enabled": true,
  "measures": [
    {
      "id": "gain_share",
      "name": "Meilleure hausse log / hausses positives log",
      "description": "Part de la meilleure hausse logarithmique dans la somme des hausses logarithmiques positives.",
      "unit": "%",
      "kind": "numeric",
      "domain": [],
      "supportsUnknown": true,
      "categories": [
        {
          "id": "gain_share-c0",
          "name": "Répartie",
          "min": null,
          "max": 20,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#10a039",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « répartie » pour cet indicateur."
        },
        {
          "id": "gain_share-c1",
          "name": "Modérée",
          "min": 20,
          "max": 40,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#a3d85d",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « modérée » pour cet indicateur."
        },
        {
          "id": "gain_share-c2",
          "name": "Concentrée",
          "min": 40,
          "max": 60,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#f4c900",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « concentrée » pour cet indicateur."
        },
        {
          "id": "gain_share-c3",
          "name": "Très concentrée",
          "min": 60,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#ff9625",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « très concentrée » pour cet indicateur."
        },
        {
          "id": "gain_share-c4",
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
      "id": "gain_net_share",
      "name": "Meilleure hausse simple / gain net simple",
      "description": "Rapport de la meilleure hausse simple au gain net simple. Peut dépasser 100 %.",
      "unit": "%",
      "kind": "numeric",
      "domain": [],
      "supportsUnknown": true,
      "categories": [
        {
          "id": "gain_net_share-c0",
          "name": "Limitée",
          "min": null,
          "max": 25,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#10a039",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « limitée » pour cet indicateur."
        },
        {
          "id": "gain_net_share-c1",
          "name": "Modérée",
          "min": 25,
          "max": 50,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#a3d85d",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « modérée » pour cet indicateur."
        },
        {
          "id": "gain_net_share-c2",
          "name": "Importante",
          "min": 50,
          "max": 100,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#f4c900",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « importante » pour cet indicateur."
        },
        {
          "id": "gain_net_share-c3",
          "name": "Supérieure au gain net",
          "min": 100,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#ff9625",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « supérieure au gain net » pour cet indicateur."
        },
        {
          "id": "gain_net_share-c4",
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
      "id": "log_net_share",
      "name": "Meilleure hausse log / gain net log",
      "description": "Rapport de la meilleure hausse logarithmique au gain net logarithmique. Distinct des deux autres concentrations.",
      "unit": "%",
      "kind": "numeric",
      "domain": [],
      "supportsUnknown": true,
      "categories": [
        {
          "id": "log_net_share-c0",
          "name": "Limitée",
          "min": null,
          "max": 25,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#10a039",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « limitée » pour cet indicateur."
        },
        {
          "id": "log_net_share-c1",
          "name": "Modérée",
          "min": 25,
          "max": 50,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#a3d85d",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « modérée » pour cet indicateur."
        },
        {
          "id": "log_net_share-c2",
          "name": "Importante",
          "min": 50,
          "max": 100,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#f4c900",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « importante » pour cet indicateur."
        },
        {
          "id": "log_net_share-c3",
          "name": "Supérieure au gain net",
          "min": 100,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#ff9625",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « supérieure au gain net » pour cet indicateur."
        },
        {
          "id": "log_net_share-c4",
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
