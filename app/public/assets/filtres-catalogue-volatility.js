/* Filtre « Volatilité » du catalogue par défaut. */
window.AdminCategoryDemo.filters.push({
  "id": "volatility",
  "name": "Volatilité",
  "description": "Mesurez l’amplitude des variations quotidiennes sur la fenêtre de référence. Les bornes sont exprimées en % par séance.",
  "editable": true,
  "enabled": true,
  "measures": [
    {
      "id": "volatility",
      "name": "Volatilité",
      "description": "Dispersion des variations quotidiennes des cours, en pourcentage par séance.",
      "unit": "%/séance",
      "kind": "numeric",
      "domain": [],
      "supportsUnknown": true,
      "categories": [
        {
          "id": "volatility-very-low",
          "name": "Très faible",
          "min": null,
          "max": 0.75,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#08a02f",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Variations quotidiennes très limitées dans cette démonstration."
        },
        {
          "id": "volatility-c0",
          "name": "Faible",
          "min": 0.75,
          "max": 1.5,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#a8db6c",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Amplitude quotidienne limitée."
        },
        {
          "id": "volatility-c1",
          "name": "Modérée",
          "min": 1.5,
          "max": 3,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#f7d400",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Variations quotidiennes intermédiaires."
        },
        {
          "id": "volatility-c2",
          "name": "Élevée",
          "min": 3,
          "max": 5,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#ff9c28",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Variations quotidiennes importantes."
        },
        {
          "id": "volatility-c3",
          "name": "Très élevée",
          "min": 5,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#f04452",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Très forte amplitude quotidienne."
        },
        {
          "id": "volatility-c4",
          "name": "Inconnue",
          "min": null,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#a5afbf",
          "active": true,
          "unknown": true,
          "values": [],
          "description": "Volatilité indisponible."
        }
      ]
    }
  ]
});
