/* Explorateur — persistance locale : seul fichier de la page qui connaît les clés de stockage.
   Clés (J.store, JSON, jamais d'exception) :
   - jigo_classement_test_v1 : sauvegardes explicites de la page (profils, filtres, surcharges par compte) et préférence de mode ;
   - jigo_ct_vis_v5 : colonnes visibles choisies par la personne, valables pour une révision de la disposition et un appareil ;
   - jigo_ct_ctx:<id> (texte) : réglages transmis à la fiche d'un titre ouverte dans un autre onglet (lue par titre.js).
   Chargé avant explorer.js ; expose window.ExplorerStore. */
(() => {
  "use strict";
  const KEY = "jigo_classement_test_v1",
    VIS_KEY = "jigo_ct_vis_v5";
  window.ExplorerStore = {
    KEY,
    readSaved: () => J.store.get(KEY),
    readLocal: () => J.store.get(KEY, {}) || {},
    write: (value) => J.store.set(KEY, value),
    has: () => J.store.has(KEY),
    readVisibility: () => J.store.get(VIS_KEY),
    writeVisibility: (value) => J.store.set(VIS_KEY, value),
    handoff: (id, json) => J.store.text.set("jigo_ct_ctx:" + id, json),
  };
})();
