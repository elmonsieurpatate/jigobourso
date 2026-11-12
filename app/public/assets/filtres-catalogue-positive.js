/* Filtre « Séances positives » du catalogue par défaut. */
window.AdminCategoryDemo.filters.push({
  "id": "positive",
  "name": "Séances positives",
  "description": "Classez la proportion des séances en hausse, affichée ici en pourcentage.",
  "editable": true,
  "enabled": true,
  "measures": [
    {
      "id": "up_fraction",
      "name": "Séances positives",
      "description": "Part des séances dont la variation est strictement positive sur la fenêtre de référence.",
      "unit": "%",
      "kind": "numeric",
      "domain": [],
      "supportsUnknown": true,
      "categories": [
        {
          "id": "up_fraction-c0",
          "name": "Peu fréquentes",
          "min": null,
          "max": 40,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#f04452",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « peu fréquentes » pour cet indicateur."
        },
        {
          "id": "up_fraction-c1",
          "name": "Partagées",
          "min": 40,
          "max": 55.00000000000001,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#ff9625",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « partagées » pour cet indicateur."
        },
        {
          "id": "up_fraction-c2",
          "name": "Fréquentes",
          "min": 55.00000000000001,
          "max": 70,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#a8d85d",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « fréquentes » pour cet indicateur."
        },
        {
          "id": "up_fraction-c3",
          "name": "Très fréquentes",
          "min": 70,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#10a039",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « très fréquentes » pour cet indicateur."
        },
        {
          "id": "up_fraction-c4",
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
