/* Restauration et migrations de l’état local : aucun DOM, aucun réseau ni accès au stockage.
   Les données d’entrée sont copiées ; le contrôleur décide s’il persiste writeBack. */
(() => {
  "use strict";
  window.ExplorerSession = {
    restore({ user, profiles, categoryPayload, categories, saved, rawLocal }) {
      const M = window.ExplorerModel,
        secondary = window.ClassementTestSecondary;
      const withDay = M.withDay,
        fresh = (id) => M.fresh(profiles, id);
      saved = saved ? M.cloneJSON(saved) : null;
      rawLocal = M.cloneJSON(rawLocal || {});
      let writeBack = false;
      let state = {
        mode: "simple",
        strategy: "fast",
        selected: "week",
        profiles: Object.fromEntries(Object.keys(profiles).map((id) => [id, fresh(id)])),
        filters: secondary.all(categories),
      };
      // Seules les sauvegardes explicites de cette page sont relues. Les préférences Explorer restent séparées.
      try {
        if (saved && saved.profiles && typeof saved.profiles === "object")
          for (const id of Object.keys(profiles))
            if (!saved.profiles[id]) saved.profiles[id] = fresh(id);
            else withDay(saved.profiles[id]); // stratégies ajoutées depuis la sauvegarde
        if (M.isValidSaved(saved, profiles)) state = saved;
      } catch (_) {
        /* Stockage absent ou ancien : valeurs de démonstration. */
      }
      const adminSelections = secondary.defaults(categoryPayload, categories);
      const userKey = String(user.id ?? "offline");
      const byUser = rawLocal.secondaryOverridesByUser || {};
      let overrides = Object.fromEntries(
        Object.entries(byUser[userKey] || {}).filter(
          ([, v]) => v && Array.isArray(v.selected) && Array.isArray(v.known),
        ),
      );
      const metadataMigration = secondary.migrateOverrides(categoryPayload, overrides);
      overrides = metadataMigration.overrides;
      if (Object.keys(metadataMigration.previous).length) {
        const previous = rawLocal.secondaryMetadataPreviousByUser || {};
        rawLocal.secondaryMetadataPreviousByUser = {
          ...previous,
          [userKey]: { ...(previous[userKey] || {}), ...metadataMigration.previous },
        };
        rawLocal.secondaryOverridesByUser = { ...byUser, [userKey]: overrides };
        try {
          writeBack = true;
        } catch (_) {
          /* Current session still uses the migrated preferences. */
        }
      }
      // Migrate explicit restrictive selections from the prior stable-label prototype once.
      if (!byUser[userKey] && categoryPayload.schema === 2 && rawLocal.filters && rawLocal.categorySignature) {
        let previous = {};
        try {
          previous = JSON.parse(rawLocal.categorySignature);
        } catch (_) {}
        for (const f of categoryPayload.definitions.filters) {
          if (!f.editable || !categories[f.id]) continue;
          const target = new Set(adminSelections[f.id]);
          let changed = false;
          for (const m of f.measures) {
            const selected = rawLocal.filters[m.id],
              old = previous[m.id];
            if (!old || !Array.isArray(selected) || selected.length === old.labels.length + 1) continue;
            changed = true;
            for (const o of categories[f.id].options.filter((o) => o.measure === m.id)) target.delete(o.id);
            for (const id of selected) {
              const name = id === "unknown" ? null : old.labels[Number(String(id).slice(1))];
              const c = m.categories.find((c) => (id === "unknown" ? c.unknown : c.name === name));
              if (c && c.active) target.add(m.id + "::" + c.id);
            }
          }
          if (changed) overrides[f.id] = { selected: [...target], known: categories[f.id].options.map((o) => o.id) };
        }
      }
      // Un choix enregistré garde ses identifiants ; seules les catégories apparues depuis suivent les défauts de l'administration.
      const filtersFor = (o) => M.filtersFor(o, categories, adminSelections);
      state.filters = filtersFor(overrides);
      state.secondaryOverridesByUser = { ...byUser, [userKey]: overrides };
      state.secondaryMetadataPreviousByUser = rawLocal.secondaryMetadataPreviousByUser || {};
      return { state, overrides, adminSelections, metadataMigration, userKey, filtersFor, rawLocal, writeBack };
    },
  };
})();
