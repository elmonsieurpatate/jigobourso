/* Filtre « Secteur » du catalogue par défaut. */
window.AdminCategoryDemo.filters.push({
  "id": "sector",
  "name": "Secteur",
  "description": "Grandes familles sectorielles ; correspondances actions et catégories ETF distinctes.",
  "provenance": "instruments.kind + instruments.category : secteur action ou catégorie ETF explicitement reconnue.",
  "editable": false,
  "enabled": true,
  "measures": [],
  "values": [
    {
      "id": "sector:technology",
      "label": "Technologie",
      "value": "sector:technology",
      "count": 0
    },
    {
      "id": "sector:finance",
      "label": "Finance",
      "value": "sector:finance",
      "count": 0
    },
    {
      "id": "sector:health",
      "label": "Santé",
      "value": "sector:health",
      "count": 0
    },
    {
      "id": "sector:industry",
      "label": "Industrie",
      "value": "sector:industry",
      "count": 0
    },
    {
      "id": "sector:consumption",
      "label": "Consommation",
      "value": "sector:consumption",
      "count": 0
    },
    {
      "id": "sector:energy",
      "label": "Énergie",
      "value": "sector:energy",
      "count": 0
    },
    {
      "id": "sector:materials",
      "label": "Matériaux",
      "value": "sector:materials",
      "count": 0
    },
    {
      "id": "sector:utilities",
      "label": "Services publics",
      "value": "sector:utilities",
      "count": 0
    },
    {
      "id": "sector:real-estate",
      "label": "Immobilier",
      "value": "sector:real-estate",
      "count": 0
    },
    {
      "id": "sector:communication",
      "label": "Communication",
      "value": "sector:communication",
      "count": 0
    },
    {
      "id": "sector:other",
      "label": "Autres",
      "value": "sector:other",
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
