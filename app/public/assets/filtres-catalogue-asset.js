/* Filtre « Type d’actif » du catalogue par défaut. */
window.AdminCategoryDemo.filters.push({
  "id": "asset",
  "name": "Type d’actif",
  "description": "Actions et ETF uniquement, types pris en charge.",
  "provenance": "instruments.kind : equity ou etf uniquement.",
  "editable": false,
  "enabled": true,
  "measures": [],
  "values": [
    {
      "id": "asset:equity",
      "label": "Actions",
      "value": "asset:equity",
      "count": 0
    },
    {
      "id": "asset:etf",
      "label": "ETF",
      "value": "asset:etf",
      "count": 0
    }
  ]
});
