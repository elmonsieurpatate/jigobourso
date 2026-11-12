/* Filtre « Drawdown maximal » du catalogue par défaut. */
window.AdminCategoryDemo.filters.push({
  "id": "drawdown",
  "name": "Drawdown maximal",
  "description": "Classez l’amplitude positive du recul maximal observé depuis un sommet précédent.",
  "editable": true,
  "enabled": true,
  "measures": [
    {
      "id": "drawdown",
      "name": "Repli maximal",
      "description": "Recul maximal observé depuis un sommet précédent, exprimé en amplitude positive.",
      "unit": "%",
      "kind": "numeric",
      "domain": [],
      "supportsUnknown": true,
      "categories": [
        {
          "id": "drawdown-c0",
          "name": "Faible",
          "min": null,
          "max": 5,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#10a039",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « faible » pour cet indicateur."
        },
        {
          "id": "drawdown-c1",
          "name": "Modéré",
          "min": 5,
          "max": 10,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#a3d85d",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « modéré » pour cet indicateur."
        },
        {
          "id": "drawdown-c2",
          "name": "Élevé",
          "min": 10,
          "max": 20,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#f4c900",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « élevé » pour cet indicateur."
        },
        {
          "id": "drawdown-c3",
          "name": "Très élevé",
          "min": 20,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#ff9625",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « très élevé » pour cet indicateur."
        },
        {
          "id": "drawdown-c4",
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
