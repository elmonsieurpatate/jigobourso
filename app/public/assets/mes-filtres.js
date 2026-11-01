/* Gestion des réglages de départ personnalisés et des filtres enregistrés. */
(async () => {
  const user = await J.init('explorer'); if (!user) return;
  const page = J.$('#page');
  const labels = {
    regular: ['Croissance régulière', 'Repère les hausses soutenues sur plusieurs périodes.'],
    fast: ['Hausse rapide', 'Repère les progressions marquées sur les périodes courtes.'],
    recovery: ['Rebond', 'Repère les titres qui repartent après une période faible.'],
    low_volatility: ['Hausse calme', 'Repère les hausses avec des variations plus modérées.'],
    momentum: ['Momentum 6 mois', 'Classement de la progression passée sur six mois.'],
    momentum12: ['Momentum 12 mois', 'Classement de la progression passée sur douze mois.'],
    momentum_risk: ['Momentum ajusté du risque', 'Tendance au-dessus d’une moyenne 200 jours ascendante, momentum 6/12 mois pénalisé selon volatilité et repli. Essai.']
  };
  const icons = ['📈', '⚡', '🔎', '🛡️', '🌱', '📊', '💼', '⭐'];
  let currentState = {};
  try { currentState = JSON.parse(sessionStorage.getItem('jigo_explorer2') || localStorage.getItem('jigo_explorer2') || '{}'); } catch (_) {}
  const availability = (() => { try { return JSON.parse(localStorage.getItem('jigo_strategy_availability') || '{}'); } catch (_) { return {}; } })();
  const enabled = key => availability[key] !== false;
  const storeAvailability = () => localStorage.setItem('jigo_strategy_availability', JSON.stringify(availability));
  const safeState = (config, view, label, preset = 'custom', base = null) => {
    const state = { preset, base, label, config, status: view.status || 'retained', page: 1, level: 'guided', compare: false,
      sort: view.sort || 'rank', dir: view.dir || 'asc', size: 20, view };
    try { localStorage.setItem('jigo_explorer2', JSON.stringify(state)); sessionStorage.setItem('jigo_explorer2', JSON.stringify(state)); } catch (_) { }
  };
  const viewSummary = v => {
    const bits = [];
    if (v.q) bits.push('Recherche : ' + v.q);
    if (v.kind) bits.push(v.kind === 'etf' ? 'ETF' : 'Actions');
    if (v.market) bits.push('Place : ' + v.market);
    if (v.tradable === false) bits.push('Tous les niveaux de négociabilité');
    if (v.owned_only) bits.push('Titres détenus uniquement');
    const status = { retained: 'Retenus', rejected: 'Écartés', unknown: 'Non évaluables', all: 'Tous' }[v.status];
    if (status && status !== 'Retenus') bits.push('Affichage : ' + status.toLowerCase());
    const extra = ['budget', 'min_price', 'min_score', 'max_volatility', 'max_drawdown', 'min_volume'].filter(k => v[k] !== undefined && v[k] !== '');
    if (extra.length) bits.push(extra.length + ' filtre' + (extra.length > 1 ? 's' : '') + ' avancé' + (extra.length > 1 ? 's' : ''));
    return bits.length ? bits.join(' · ') : 'Aucun filtre pratique : le classement complet est affiché.';
  };
  const periodSummary = c => (c.periods || []).filter(p => p.enabled).map(p => J.PERIODS[p.id] || p.id).join(' + ') || 'Aucune période activée';
  const setName = (name, config, view) => J.dialog({ title: 'Renommer ce filtre', body: J.field('Nom du filtre', `<input id="rename-filter" maxlength="80" value="${J.esc(name)}" autofocus>`), actions: [
    { label: 'Annuler', run: () => {} },
    { label: 'Enregistrer', cls: 'primary', run: async d => {
      const next = J.$('#rename-filter', d).value.trim();
      if (!next) { J.formError(d, 'Donnez un nom à ce filtre.'); return true; }
      if (next !== name && searches.some(s => s.name.toLocaleLowerCase() === next.toLocaleLowerCase())) { J.formError(d, 'Un filtre porte déjà ce nom.'); return true; }
      await J.post('search/save', { name: next, config, view });
      if (next !== name) { const old = searches.find(s => s.name === name); if (old) await J.post('search/delete', { id: +old.id }); }
      await render(); return false;
    } }
  ] });
  const editNote = s => J.dialog({ title: 'Icône et note du filtre', body: `<label class="field">Icône<select id="filter-icon">${icons.map(i => `<option value="${J.esc(i)}" ${(s.view || {}).icon === i ? 'selected' : ''}>${J.esc(i)}</option>`).join('')}</select></label><label class="field">Note · à quoi sert ce filtre ?<textarea id="filter-description" maxlength="300" rows="3" placeholder="Ex. Repérer les ETF énergie qui progressent sur plusieurs périodes.">${J.esc((s.view || {}).description || '')}</textarea></label><p class="small muted">La note vous aide à vous rappeler l’objectif du filtre. Elle ne change aucun critère ni aucun classement.</p>`, actions: [
    { label: 'Annuler', run: () => {} },
    { label: 'Enregistrer', cls: 'primary', run: async () => { const view = { ...(s.view || {}), icon: J.$('#filter-icon').value, description: J.$('#filter-description').value.trim() }; await J.post('search/save', { name: s.name, config: s.config, view }); await render(); } }
  ] });
  let P, mine = {}, searches = [];
  async function render() {
    [P, mine, searches] = await Promise.all([
      J.api('strategy/presets'), J.api('presets/mine').then(r => r.presets || {}).catch(() => ({})),
      J.api('searches').then(r => r.searches || []).catch(() => [])
    ]);
    const presets = Object.keys(P.presets || {}).map(k => {
      const info = labels[k] || [k, 'Réglage de stratégie']; const custom = mine[k];
      const config = custom ? custom.config : P.presets[k], view = custom ? custom.view : {};
      const active = (currentState.preset === k || (currentState.preset === 'custom' && currentState.base === k)) && !currentState.label;
      return `<article class="card filter-card strategy-manage-card"><div class="row between"><div><h3>${J.esc(info[0])}</h3><span class="small muted">${J.esc(periodSummary(config))}${custom ? ' · Personnalisée' : ''}</span><span class="small muted strategy-detail">${custom ? `Modifiée le ${J.dateTime(custom.updated_at)}${view && Object.keys(view).length ? ' · ' + J.esc(viewSummary(view)) : ''}` : 'Utilise les critères initiaux de Jigobourso.'}</span></div><span class="badge ${enabled('preset:' + k) ? 'ok' : 'info'}">${enabled('preset:' + k) ? 'Disponible · Active' : 'Indisponible'}</span></div>
        <div class="filter-actions"><button class="btn small ${enabled('preset:' + k) ? '' : 'primary'}" data-toggle-strategy="preset:${J.esc(k)}">${enabled('preset:' + k) ? 'Désactiver' : 'Activer'}</button><a class="btn small" href="index.html?preset=${encodeURIComponent(k)}&edit=1">Modifier</a><button class="btn small" data-reset-preset="${J.esc(k)}" ${custom ? '' : 'disabled'}>Réinitialiser</button></div></article>`;
    }).join('');
    const own = searches.map(s => { const key = 'search:' + s.id; return `<article class="card filter-card strategy-manage-card"><div class="row between"><div class="filter-title"><span class="filter-icon" aria-hidden="true">${J.esc(s.view?.icon || '🔎')}</span><div><h3>${J.esc(s.name)}</h3><span class="small muted">${J.esc(s.view?.description || 'Filtre personnel')}</span><span class="small muted strategy-detail">${J.esc(viewSummary(s.view || {}))}</span></div></div><span class="badge ${enabled(key) ? 'ok' : 'info'}">${enabled(key) ? 'Disponible · Active' : 'Indisponible'}</span></div>
      <div class="filter-actions"><button class="btn small ${enabled(key) ? '' : 'primary'}" data-toggle-strategy="${key}">${enabled(key) ? 'Désactiver' : 'Activer'}</button><button class="btn small" data-use-search="${+s.id}">Utiliser</button><button class="btn small" data-edit-search="${+s.id}" aria-label="Modifier ${J.esc(s.name)}">Modifier</button><button class="btn small" data-edit-note="${+s.id}" aria-label="Icône et note de ${J.esc(s.name)}">Icône/note</button><button class="btn small" data-rename-search="${+s.id}" aria-label="Renommer ${J.esc(s.name)}">Renommer</button><button class="btn small danger" data-delete-search="${+s.id}" aria-label="Supprimer ${J.esc(s.name)}">Supprimer</button></div></article>`; }).join('');
    page.innerHTML = `<div class="page-head"><div><h1>Mes filtres</h1><p>Retrouvez vos réglages de stratégie et vos filtres enregistrés. Les modifier change les critères de recherche, pas les données ni les scores financiers.</p></div><a class="btn" href="index.html">← Retour au classement</a></div>
      <section class="card" style="padding:18px"><div class="row between"><div><h2 style="margin:0">Mes stratégies</h2><p class="small muted" style="margin:4px 0 0">Personnalisez un profil de départ ou restaurez son réglage initial.</p></div></div><div class="manage-grid" style="margin-top:14px">${presets}</div></section>
      <section class="card" style="padding:18px;margin-top:14px"><div class="row between"><div><h2 style="margin:0">Filtres enregistrés</h2><p class="small muted" style="margin:4px 0 0">Une recherche sauvegarde aussi le texte saisi, les cases, la visibilité, le tri et le statut affiché.</p></div><a class="btn small" href="index.html">Créer depuis l’Explorer</a></div>
        <div class="manage-grid" style="margin-top:14px">${own || '<div class="empty" style="grid-column:1/-1">Aucun filtre enregistré. Dans l’Explorer, réglez vos critères et filtres, puis sélectionnez « Enregistrer ».</div>'}</div></section>`;
    page.onclick = async e => {
      const b = e.target.closest('button[data-toggle-strategy],button[data-reset-preset],button[data-use-search],button[data-edit-search],button[data-edit-note],button[data-rename-search],button[data-delete-search]'); if (!b) return;
      try {
        if (b.dataset.toggleStrategy) {
          const key = b.dataset.toggleStrategy; availability[key] = !enabled(key); storeAvailability();
          if (!availability[key] && ((key.startsWith('preset:') && (currentState.preset === key.slice(7) || currentState.base === key.slice(7))) || (key.startsWith('search:') && currentState.label === searches.find(s => +s.id === +key.slice(7))?.name))) {
            const fallback = P.presets.regular; safeState(fallback, {}, null, 'regular', 'regular'); currentState = JSON.parse(localStorage.getItem('jigo_explorer2') || '{}');
          }
          await render();
        } else if (b.dataset.resetPreset) {
          const k = b.dataset.resetPreset, name = labels[k]?.[0] || k;
          if (await J.confirm('Réinitialiser la stratégie', `Le réglage personnalisé de « ${name} » sera supprimé.`, 'Réinitialiser')) { await J.post('preset/reset', { preset: k }); await render(); }
        } else {
          const s = searches.find(x => +x.id === +(b.dataset.useSearch || b.dataset.editSearch || b.dataset.editNote || b.dataset.renameSearch || b.dataset.deleteSearch)); if (!s) return;
          if (b.dataset.editNote) editNote(s);
          else if (b.dataset.renameSearch) setName(s.name, s.config, s.view || {});
          else if (b.dataset.deleteSearch && await J.confirm('Supprimer ce filtre', `« ${s.name} » sera supprimé.`, 'Supprimer')) { await J.post('search/delete', { id: +s.id }); await render(); }
          else if (b.dataset.useSearch || b.dataset.editSearch) {
            const edit = !!b.dataset.editSearch;
            safeState(s.config, s.view || {}, s.name);
            location.href = edit ? 'index.html?edit=1' : 'index.html';
          }
        }
      } catch (err) { J.toast(err.message || 'Une erreur est survenue.'); }
    };
  }
  try { await render(); } catch (e) { page.innerHTML = `<div class="notice err">${J.esc(e.message)}</div>`; }
})();
