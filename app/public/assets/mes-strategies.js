/* Page Mes stratégies : nom, icône, explications, activation, suppression des stratégies du Classement test (MariaDB, par utilisateur). */
(async () => {
  if (!await J.init('explorer')) return;
  const page = J.$('#page'), esc = J.esc;
  let view = null, editing = null, status = {}, open = new Set(location.hash === '#criteres' ? ['*'] : new URLSearchParams(location.search).getAll('id'));
  const loadStatus = async () => { try { status = Object.fromEntries((await J.api('strategies/status')).strategies.map(s => [s.id, s])); } catch (_) { status = {}; } };
  const val = v => v == null ? 'aucun seuil' : typeof v === 'object' ? JSON.stringify(v) : String(typeof v === 'number' ? +v.toFixed(4) : v);
  const rowsOf = d => d.length ? `<div class="sui-scroll"><table class="sui-cmp"><thead><tr><th>Paramètre</th><th>Officiel</th><th>Le vôtre</th></tr></thead><tbody>${d.map(x => `<tr class="mod"><td>${esc(x.key)}</td><td>${esc(val(x.official))}</td><td>${esc(val(x.mine))}</td></tr>`).join('')}</tbody></table></div>` : '';
  const statusBlock = r => {
    const st = status[r.id]; if (!st || st.kind !== 'builtin') return '';
    const part = (label, p, act) => `<div class="row gap-s small" style="align-items:center"><b>${label}</b> ${SUI.badge(p.state)}${p.modified ? ` <span class="muted">${p.modified} paramètre${p.modified > 1 ? 's' : ''} modifié${p.modified > 1 ? 's' : ''}</span> <button class="btn sm" data-act="${act}" data-id="${esc(r.id)}">${J.icon('undo', 'sui-ic')} Restaurer</button>` : ''}</div>`;
    const showing = open.has('*') || open.has(r.id);
    return `<div style="margin-top:8px;display:grid;gap:4px">${part('Critères de recherche', st.criteria, 'restore-criteria')}${part('Calcul des scores', st.scores, 'restore-scores')}
      <div class="row gap-s">${st.status === 'adapted' ? `<button class="btn sm" data-act="compare" data-id="${esc(r.id)}" aria-expanded="${showing}">${J.icon('compare', 'sui-ic')} Comparer à l’officielle</button><button class="btn sm" data-act="restore-all" data-id="${esc(r.id)}">Tout restaurer</button>` : ''}<a class="btn sm" href="mes-scores.html">Modifier les scores</a><a class="btn sm" href="index.html?strategy=${encodeURIComponent(r.id)}">Modifier les critères</a></div>
      ${showing && st.status === 'adapted' ? `${st.criteria.details.length ? '<h4 class="mt-2 mb-1">Critères de recherche</h4>' + rowsOf(st.criteria.details) : ''}${st.scores.details.length ? '<h4 class="mt-2 mb-1">Calcul des scores</h4>' + rowsOf(st.scores.details) : ''}` : ''}</div>`;
  };
  const post = body => J.post('classement-test/strategies/save', { revision: view.revision, ...body });
  const meta = id => ({ icon: 'trending-up', description: '', enabled: true, ...((view.meta || {})[id] || {}) });
  const when = s => { try { return new Date(String(s).replace(' ', 'T') + (/Z|[+-]\d\d:?\d\d$/.test(s) ? '' : 'Z')).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' }); } catch (_) { return ''; } };
  const rows = () => {
    const byId = Object.fromEntries(view.items.map(i => [i.id, i]));
    return [...Object.entries(view.builtin).map(([id, name]) => ({ id, name, builtin: true, row: byId[id] || null })),
      ...view.items.filter(i => !i.builtin).map(i => ({ id: i.id, name: i.name, builtin: false, row: i }))];
  };
  function form(r) {
    const m = meta(r.id);
    return `<form class="ms-form" data-id="${esc(r.id)}" style="margin-top:12px;display:grid;gap:12px">
      <label class="field">Nom<input name="name" maxlength="60" value="${esc(r.name)}" ${r.builtin ? 'readonly title="Le nom d’une stratégie fournie ne change pas"' : ''} autocomplete="off"></label>
      <fieldset style="border:0;padding:0;margin:0"><legend class="small muted mb-2">Icône</legend><div class="row gap-s" role="radiogroup" aria-label="Icône">${view.icons.map(ic => `<label class="pointer"><input type="radio" name="icon" value="${esc(ic)}" ${ic === m.icon ? 'checked' : ''} style="position:absolute;opacity:0"><span class="ms-ic" style="display:inline-flex;width:38px;height:38px;align-items:center;justify-content:center;border:1px solid var(--line);border-radius:10px;" title="${esc(ic)}">${SUI.glyph(ic)}</span></label>`).join('')}</div></fieldset>
      <label class="field">Explications <span class="small muted">(300 caractères max)</span><textarea name="description" rows="3" maxlength="300">${esc(m.description)}</textarea></label>
      <div class="row gap-s"><button type="submit" class="btn sm primary">Enregistrer</button><button type="button" class="btn sm" data-act="cancel">Annuler</button>${r.builtin ? `<button type="button" class="btn sm" data-act="restore" data-id="${esc(r.id)}" title="Remet les réglages d’origine (seuils, périodes, filtres)" style="margin-left:auto">Restaurer par défaut</button>` : ''}</div></form>`;
  }
  function render(msg, err) {
    SUI.setMeta(view.meta);
    const custom = view.items.filter(i => !i.builtin).length;
    page.innerHTML = (msg ? `<div class="notice ${err ? 'err' : ''} mb-3" role="status">${esc(msg)}</div>` : '') +
      `<div class="row between mb-3"><span class="muted">${custom} / ${view.max_custom} stratégie(s) personnelle(s)</span><a class="btn primary" href="index.html">Créer depuis le Classement test</a></div>` +
      rows().map(r => {
        const m = meta(r.id), off = !m.enabled;
        return `<div class="card tight" style="margin-bottom:10px;${off ? 'opacity:.8' : ''}"><div class="row between" style="align-items:flex-start">
          <div class="row" style="flex-wrap:nowrap;align-items:flex-start;min-width:0">${SUI.ico(r.id, r.builtin ? 'builtin' : 'personal')}<div style="min-width:0"><b>${esc(r.name)}</b> ${SUI.badge(status[r.id] ? status[r.id].status : r.builtin ? 'official' : 'personal')} ${off ? ' <span class="badge sm">Désactivée</span>' : ''}${r.id === view.selected ? ' <span class="badge sm ok outline">Dernière utilisée</span>' : ''}
          <div class="small muted" style="white-space:pre-line;max-width:70ch">${esc(m.description || 'Aucune explication.')} <a href="aide.html#strategie-${esc(r.builtin ? r.id : 'personnelles')}">Fiche d’aide</a></div>${statusBlock(r)}
          <div class="small muted">${r.row ? (r.builtin ? 'Réglages modifiés' : 'Enregistrée') + ' le ' + esc(when(r.row.updated_at)) : 'Valeurs d’origine'}</div></div></div>
          <div class="row gap-s"><label class="row gap-s small pointer"><input type="checkbox" data-act="toggle" data-id="${esc(r.id)}" ${m.enabled ? 'checked' : ''}> Active</label>
          <button class="btn sm" data-act="edit" data-id="${esc(r.id)}">Modifier</button>
          ${m.enabled ? `<a class="btn sm primary" href="index.html?strategy=${encodeURIComponent(r.id)}">Ouvrir</a>` : ''}
          ${r.builtin ? '' : `<button class="btn sm" data-act="copy" data-id="${esc(r.id)}">Dupliquer</button><button class="btn sm danger" data-act="delete" data-id="${esc(r.id)}">Supprimer</button>`}</div></div>
          ${editing === r.id ? form(r) : ''}</div>`;
      }).join('');
    J.$$('[data-act]', page).forEach(b => { const a = b.dataset.act; if (a === 'toggle') b.onchange = () => act(a, b.dataset.id, b.checked); else b.onclick = () => a === 'cancel' ? (editing = null, render()) : act(a, b.dataset.id); });
    J.$$('.ms-form', page).forEach(f => f.onsubmit = e => { e.preventDefault(); act('save-meta', f.dataset.id, new FormData(f)); });
  }
  function askName(initial) {
    return new Promise(resolve => { let done = false;
      J.dialog({ title: 'Dupliquer la stratégie', body: `<label class="field">Nom de la copie<input id="ms-name" maxlength="60" value="${esc(initial)}" autocomplete="off"></label>`,
        actions: [{ label: 'Annuler', run: () => { } }, { label: 'Dupliquer', cls: 'primary', run: d => { const v = d.querySelector('#ms-name').value.trim(); if (!v) { J.formError(d, 'Un nom est requis.'); return true; } done = true; resolve(v); } }],
        onopen: d => { const i = d.querySelector('#ms-name'); i.focus(); i.select(); } }).addEventListener('close', () => { if (!done) resolve(null); }); });
  }
  async function act(a, id, arg) {
    const it = view.items.find(i => i.id === id), name = view.builtin[id] || it?.name || '';
    try {
      if (a === 'edit') { editing = editing === id ? null : id; render(); }
      else if (a === 'save-meta') { view = await post({ action: 'meta', id, name: arg.get('name'), icon: arg.get('icon'), description: arg.get('description') }); editing = null; render(`« ${arg.get('name')} » enregistrée.`); }
      else if (a === 'toggle') { view = await post({ action: 'meta', id, enabled: arg }); render(arg ? `« ${name} » activée.` : `« ${name} » désactivée : elle n’apparaît plus dans le Classement test.`); }
      else if (a === 'copy') {
        const taken = new Set([...Object.values(view.builtin), ...view.items.map(i => i.name)].map(x => x.toLowerCase())); let n = `Copie de ${name}`, k = 2; while (taken.has(n.toLowerCase())) n = `Copie de ${name} (${k++})`;
        n = await askName(n.slice(0, 60)); if (!n) return;
        const keep = view.selected, m = meta(id);
        view = await post({ action: 'create', name: n, config: it.config, filters: it.filters, icon: m.icon, description: m.description });
        try { view = await J.post('classement-test/strategies/save', { action: 'select', id: keep }); } catch (_) { }
        render(`« ${n} » créée.`);
      }
      else if (a === 'delete') { if (!await J.confirm('Supprimer la stratégie', `« ${name} » sera supprimée définitivement. Les autres stratégies ne changent pas.`, 'Supprimer')) return; view = await post({ action: 'delete', id }); if (editing === id) editing = null; render(`« ${name} » supprimée.`); }
      else if (a === 'compare') { open.has(id) ? open.delete(id) : open.add(id); open.delete('*'); render(); }
      else if (a === 'restore-scores') { if (!await J.confirm('Restaurer les scores', `Le calcul des scores de « ${name} » reprendra les valeurs officielles. Vos critères de recherche ne changent pas.`, 'Restaurer')) return; await J.post('my/scores/save', { reset: 'profile', name: status[id].name }); await loadStatus(); render(`« ${name} » : scores restaurés.`); }
      else if (a === 'restore-criteria') { if (!await J.confirm('Restaurer les critères', `Les critères de recherche de « ${name} » reprendront les valeurs officielles. Vos réglages de scores ne changent pas.`, 'Restaurer')) return; view = await post({ action: 'restore', id }); await loadStatus(); render(`« ${name} » : critères restaurés.`); }
      else if (a === 'restore-all') { if (!await J.confirm('Tout restaurer', `« ${name} » redeviendra entièrement officielle (critères et scores).`, 'Tout restaurer')) return; view = await post({ action: 'restore', id }); await J.post('my/scores/save', { reset: 'profile', name: status[id].name }); await loadStatus(); render(`« ${name} » : redevenue officielle.`); }
      else if (a === 'restore') { if (!await J.confirm('Restaurer les valeurs par défaut', `Les réglages de « ${name} » reprendront leurs valeurs d’origine (nom, icône et explications restent). Les autres stratégies ne changent pas.`, 'Restaurer')) return; view = await post({ action: 'restore', id }); await loadStatus(); render(`« ${name} » : valeurs par défaut restaurées.`); }
    } catch (e) {
      if (/autre session|Rechargez/i.test(e.message || '')) { try { view = await J.api('classement-test/strategies'); } catch (_) { } }
      render(e.message || 'Action impossible.', true);
    }
  }
  try { view = await J.api('classement-test/strategies'); await loadStatus(); render(); const tgt = new URLSearchParams(location.search).get('id'); const el = tgt && page.querySelector(`[data-act="compare"][data-id="${CSS.escape(tgt)}"]`); if (el) el.scrollIntoView({ block: 'center' }); }
  catch (e) { page.innerHTML = `<div class="notice err">Stratégies indisponibles : ${esc(e.message)}</div>`; }
})();
