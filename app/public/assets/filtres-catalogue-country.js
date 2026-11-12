/* Filtre « Zone géographique » du catalogue par défaut. */
window.AdminCategoryDemo.filters.push({
  "id": "country",
  "name": "Zone géographique",
  "description": "Zone du pays de rattachement de l’instrument, indépendante de sa cotation.",
  "provenance": "instruments.country : pays de rattachement, pas la place de cotation.",
  "editable": false,
  "enabled": true,
  "measures": [],
  "values": [
    {
      "id": "country:us",
      "label": "États-Unis",
      "value": "country:us",
      "count": 0
    },
    {
      "id": "country:europe",
      "label": "Europe",
      "value": "country:europe",
      "count": 0
    },
    {
      "id": "country:emerging",
      "label": "Pays émergents",
      "value": "country:emerging",
      "count": 0
    },
    {
      "id": "country:other",
      "label": "Autres",
      "value": "country:other",
      "count": 0
    },
    {
      "id": "unknown",
      "label": "Inconnue",
      "value": null,
      "count": 0
    }
  ]
});
