/* Filtre « Volume moyen échangé » du catalogue par défaut. */
window.AdminCategoryDemo.filters.push({
  "id": "volume",
  "name": "Volume moyen échangé",
  "description": "Classez le nombre moyen de titres échangés par séance, sans le confondre avec un montant en euros.",
  "editable": true,
  "enabled": true,
  "measures": [
    {
      "id": "avg_volume",
      "name": "Volume historique",
      "description": "Volume moyen historique, en titres par séance, sans mesurer la croissance des volumes.",
      "unit": "titres/séance",
      "kind": "numeric",
      "domain": [],
      "supportsUnknown": true,
      "categories": [
        {
          "id": "avg_volume-c0",
          "name": "Très faible",
          "min": null,
          "max": 10000,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#10a039",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « très faible » pour cet indicateur."
        },
        {
          "id": "avg_volume-c1",
          "name": "Faible",
          "min": 10000,
          "max": 100000,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#a3d85d",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « faible » pour cet indicateur."
        },
        {
          "id": "avg_volume-c2",
          "name": "Moyen",
          "min": 100000,
          "max": 1000000,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#f4c900",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « moyen » pour cet indicateur."
        },
        {
          "id": "avg_volume-c3",
          "name": "Important",
          "min": 1000000,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#ff9625",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « important » pour cet indicateur."
        },
        {
          "id": "avg_volume-c4",
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
