/* Filtre « Marché / Place » du catalogue par défaut. */
window.AdminCategoryDemo.filters.push({
  "id": "market",
  "name": "Marché / Place",
  "description": "Zone de la place de cotation ; indépendante du pays de l’instrument.",
  "provenance": "listings.mic : localisation de la place selon une correspondance MIC explicite.",
  "editable": false,
  "enabled": true,
  "measures": [],
  "values": [
    {
      "id": "market:us",
      "label": "Marchés américains",
      "value": "market:us",
      "count": 0
    },
    {
      "id": "market:europe",
      "label": "Marchés européens",
      "value": "market:europe",
      "count": 0
    },
    {
      "id": "market:emerging",
      "label": "Marchés émergents",
      "value": "market:emerging",
      "count": 0
    },
    {
      "id": "market:other",
      "label": "Autres marchés",
      "value": "market:other",
      "count": 0
    },
    {
      "id": "unknown",
      "label": "Inconnu",
      "value": null,
      "count": 0
    }
  ]
});
