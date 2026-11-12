/* Filtre « Qualité des données » du catalogue par défaut. */
window.AdminCategoryDemo.filters.push({
  "id": "quality",
  "name": "Qualité des données",
  "description": "Configurez uniquement les états et mesures effectivement disponibles : qualité, fraîcheur et couverture. Aucun score de qualité fictif n’est calculé.",
  "editable": true,
  "enabled": true,
  "measures": [
    {
      "id": "quality",
      "name": "Continuité des données",
      "description": "État de continuité de l’historique : complet, partiel ou rupture. Aucune nouvelle mesure n’est créée ici.",
      "unit": "code 0 complète / 1 partielle / 2 rupture",
      "kind": "enum",
      "domain": [
        {
          "value": "0",
          "label": "Complète"
        },
        {
          "value": "1",
          "label": "Partielle"
        },
        {
          "value": "2",
          "label": "Rupture"
        }
      ],
      "supportsUnknown": true,
      "categories": [
        {
          "id": "quality-c0",
          "name": "Complète",
          "min": null,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#10a039",
          "active": true,
          "unknown": false,
          "values": [
            "0"
          ],
          "description": "Classe « complète » pour cet indicateur."
        },
        {
          "id": "quality-c1",
          "name": "Partielle",
          "min": null,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#f4c900",
          "active": true,
          "unknown": false,
          "values": [
            "1"
          ],
          "description": "Classe « partielle » pour cet indicateur."
        },
        {
          "id": "quality-c2",
          "name": "Rupture",
          "min": null,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#f04452",
          "active": true,
          "unknown": false,
          "values": [
            "2"
          ],
          "description": "Classe « rupture » pour cet indicateur."
        },
        {
          "id": "quality-c3",
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
      "id": "freshness",
      "name": "Fraîcheur des clôtures",
      "description": "État de fraîcheur des clôtures. Catégories fondées sur des états, pas sur un intervalle numérique éditable.",
      "unit": "code 0 récent / 1 ancien",
      "kind": "enum",
      "domain": [
        {
          "value": "0",
          "label": "À jour"
        },
        {
          "value": "1",
          "label": "Ancienne"
        }
      ],
      "supportsUnknown": true,
      "categories": [
        {
          "id": "freshness-c0",
          "name": "À jour",
          "min": null,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#10a039",
          "active": true,
          "unknown": false,
          "values": [
            "0"
          ],
          "description": "Classe « à jour » pour cet indicateur."
        },
        {
          "id": "freshness-c1",
          "name": "Ancienne",
          "min": null,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#ff9625",
          "active": true,
          "unknown": false,
          "values": [
            "1"
          ],
          "description": "Classe « ancienne » pour cet indicateur."
        },
        {
          "id": "freshness-c2",
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
      "id": "coverage",
      "name": "Couverture des historiques",
      "description": "Proportion de clôtures disponibles par rapport aux séances attendues. Valeur entre 0 et 1.",
      "unit": "%",
      "kind": "numeric",
      "domain": [],
      "supportsUnknown": true,
      "categories": [
        {
          "id": "coverage-c0",
          "name": "Absente",
          "min": null,
          "max": 0,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#f04452",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « absente » pour cet indicateur."
        },
        {
          "id": "coverage-c1",
          "name": "Partielle",
          "min": 0,
          "max": 99.9999,
          "minIncluded": false,
          "maxIncluded": true,
          "color": "#ff9625",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « partielle » pour cet indicateur."
        },
        {
          "id": "coverage-c2",
          "name": "Complète",
          "min": 99.9999,
          "max": null,
          "minIncluded": false,
          "maxIncluded": false,
          "color": "#10a039",
          "active": true,
          "unknown": false,
          "values": [],
          "description": "Classe « complète » pour cet indicateur."
        },
        {
          "id": "coverage-c3",
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
