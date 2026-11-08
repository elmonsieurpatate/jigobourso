/* Mes filtres et catégories : catalogue des catégories disponibles et filtres enregistrés par stratégie (propres au compte), avec réinitialisation. Les filtres n'agissent que sur l'affichage. */
(async () => {
  if (!await J.init('explorer')) return;
  const page = J.$('#page'), esc = J.esc, S = window.ClassementTestSecondary;
  let view, cats;
  async function load() {
    const [payload, v] = await Promise.all([J.api('explorer/secondary-filters'), J.api('classement-test/strategies')]);
    view = v; cats = S.normalize(payload); SUI.setMeta(view.meta);
  }
  const names = () => Object.fromEntries([...Object.entries(view.builtin), ...view.items.filter(i => !i.builtin).map(i => [i.id, i.name])]);
  const chips = (c, selected) => c.options.map(o => { const on = !selected || selected.includes(o.id); return `<span class="mf-chip ${on ? 'on' : 'off'}" title="${esc(o.range || '')}"><i style="background:${esc(o.color || '#64748b')}"></i>${esc(o.label)}</span>`; }).join('');
  function render(msg, err) {
    const ids = Object.keys(cats), byId = Object.fromEntries(view.items.map(i => [i.id, i])), n = names();
    const mine = Object.keys(n).map(id => {
      const f = (byId[id] && byId[id].filters) || {}, changed = Object.keys(f).filter(k => cats[k] && f[k] && Array.isArray(f[k].selected) && !(cats[k].options.every(o => f[k].selected.includes(o.id))));
      return { id, name: n[id], changed, f };
    });
    page.innerHTML = (msg ? `<div class="notice ${err ? 'err' : ''}" role="status" style="margin-bottom:12px">${esc(msg)}</div>` : '') +
      `<h2>Mes filtres par stratégie</h2><div class="sui-cards">${mine.map(m => `<article class="sui-card"><div class="sui-head">${SUI.ico(m.id, view.builtin[m.id] ? 'builtin' : 'personal')}<div><h3>${esc(m.name)}</h3><div class="small muted">${m.changed.length ? m.changed.length + ' filtre' + (m.changed.length > 1 ? 's' : '') + ' personnalisé' + (m.changed.length > 1 ? 's' : '') : 'Aucun filtre : tout est affiché'}</div></div></div>
        ${m.changed.map(k => `<div><b class="small">${esc(cats[k].label)}</b><div class="mf-row">${chips(cats[k], m.f[k].selected)}</div></div>`).join('')}
        <div class="row gap-s">${m.changed.length ? `<button class="btn small" data-reset="${esc(m.id)}">Réinitialiser ces filtres</button>` : ''}<a class="btn small" href="index.html?strategy=${encodeURIComponent(m.id)}">Modifier dans l’Explorer</a></div></article>`).join('')}</div>
      <h2 style="margin-top:28px">Catégories disponibles</h2><p class="muted small">Ces catégories sont définies par l’administration. Dans l’Explorer, cochez ou décochez-les : seules les catégories cochées restent affichées. Survolez une pastille pour voir son détail.</p>
      <div class="sui-cards">${ids.map(k => `<article class="sui-card"><h3>${esc(cats[k].label)}</h3><div class="small muted">${cats[k].group === 'main' ? 'Filtre principal' : 'Filtre complémentaire'}${cats[k].unit ? ' · ' + esc(cats[k].unit) : ''}</div><div class="mf-row">${chips(cats[k], null)}</div></article>`).join('')}</div>`;
    J.$$('[data-reset]', page).forEach(b => b.onclick = async () => {
      const id = b.dataset.reset, it = byId[id], nm = n[id];
      if (!await J.confirm('Réinitialiser les filtres', `Les filtres de « ${nm} » seront remis à zéro (tout est affiché). Les réglages de la stratégie ne changent pas.`, 'Réinitialiser')) return;
      try { view = await J.post('classement-test/strategies/save', { revision: view.revision, action: 'save', id, config: it.config, filters: {} }); render(`Filtres de « ${nm} » réinitialisés.`); }
      catch (e) { render(e.message || 'Action impossible.', true); }
    });
  }
  try { await load(); render(); } catch (e) { page.innerHTML = `<div class="notice err">Filtres indisponibles : ${esc(e.message)}</div>`; }
})();
