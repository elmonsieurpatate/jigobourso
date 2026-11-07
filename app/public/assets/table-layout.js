/* Réglages d'affichage des tableaux (colonnes, ordre, largeurs, tri et filtres initiaux), définis dans Administration → Colonnes.
   Quatre configurations indépendantes : page (explorer | scores) × affichage (desktop | mobile). Lecture seule ici ; l'écriture est réservée à l'administration. */
window.TableLayout = (() => {
  const mq = window.matchMedia('(max-width:700px)');
  const device = () => (mq.matches ? 'mobile' : 'desktop');
  let cache = null;
  async function load() {
    if (cache) return cache;
    try { cache = await J.api('table-layouts'); } catch (_) { cache = null; }
    return cache;
  }
  /* Configuration effective ; `fallback` = colonnes {id,visible} connues de la page si le serveur ne répond pas. */
  function get(data, page, dev, fallback) {
    const c = data && data.layouts && data.layouts[page + '.' + dev];
    if (c) return { ...c, revision: data.revision, catalog: data.catalog[page].columns, fromServer: true };
    return { columns: fallback.map(([id, visible]) => ({ id, visible, width: null })), sort: [], filters: {}, revision: -1, catalog: null, fromServer: false };
  }
  function onChange(fn) { mq.addEventListener('change', fn); }
  return { device, load, get, onChange };
})();
