/* Page Mes stratégies : nom, icône, explications, activation, suppression des stratégies du Classement test (MariaDB, par utilisateur). */
(async () => {
  if (!await J.init('explorer')) return;
  const page = J.$('#page'), esc = J.esc;
  let view = null, editing = null;
  const post = body => J.post('classement-test/strategies/save', { revision: view.revision, ...body });
  const meta = id => ({ icon: '📈', description: '', enabled: true, ...((view.meta || {})[id] || {}) });
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
      <fieldset style="border:0;padding:0;margin:0"><legend class="small muted" style="margin-bottom:6px">Icône</legend><div class="row gap-s" role="radiogroup" aria-label="Icône">${view.icons.map(ic => `<label style="cursor:pointer"><input type="radio" name="icon" value="${esc(ic)}" ${ic === m.icon ? 'checked' : ''} style="position:absolute;opacity:0"><span class="ms-ic" style="display:inline-flex;width:38px;height:38px;align-items:center;justify-content:center;border:1px solid var(--line);border-radius:10px;font-size:1.2rem">${ic}</span></label>`).join('')}</div></fieldset>
      <label class="field">Explications <span class="small muted">(300 caractères max)</span><textarea name="description" rows="3" maxlength="300">${esc(m.description)}</textarea></label>
      <div class="row gap-s"><button type="submit" class="btn small primary">Enregistrer</button><button type="button" class="btn small" data-act="cancel">Annuler</button></div></form>`;
  }
  function render(msg, err) {
    const custom = view.items.filter(i => !i.builtin).length;
    page.innerHTML = (msg ? `<div class="notice ${err ? 'err' : ''}" role="status" style="margin-bottom:12px">${esc(msg)}</div>` : '') +
      `<div class="row between" style="margin-bottom:12px"><span class="muted">${custom} / ${view.max_custom} stratégie(s) personnelle(s)</span><a class="btn primary" href="classement-test.html">Créer depuis le Classement test</a></div>` +
      rows().map(r => {
        const m = meta(r.id), off = !m.enabled;
        return `<div class="card tight" style="margin-bottom:10px;${off ? 'opacity:.8' : ''}"><div class="row between" style="align-items:flex-start">
          <div class="row" style="flex-wrap:nowrap;align-items:flex-start;min-width:0"><span style="font-size:1.6rem;line-height:1.1" aria-hidden="true">${m.icon}</span><div style="min-width:0"><b>${esc(r.name)}</b> ${r.builtin ? '<span class="tag">Fournie</span>' : '<span class="tag held">Personnelle</span>'}${off ? ' <span class="tag">Désactivée</span>' : ''}${r.id === view.selected ? ' <span class="tag open">Dernière utilisée</span>' : ''}
          <div class="small muted" style="white-space:pre-line;max-width:70ch">${esc(m.description) || 'Aucune explication.'}</div>
          <div class="small muted">${r.row ? (r.builtin ? 'Réglages modifiés' : 'Enregistrée') + ' le ' + esc(when(r.row.updated_at)) : 'Valeurs d’origine'}</div></div></div>
          <div class="row gap-s"><label class="row gap-s small" style="cursor:pointer"><input type="checkbox" data-act="toggle" data-id="${esc(r.id)}" ${m.enabled ? 'checked' : ''}> Active</label>
          <button class="btn small" data-act="edit" data-id="${esc(r.id)}">Modifier</button>
          ${m.enabled ? `<a class="btn small primary" href="classement-test.html?strategy=${encodeURIComponent(r.id)}">Ouvrir</a>` : ''}
          ${r.builtin ? (r.row ? `<button class="btn small" data-act="restore" data-id="${esc(r.id)}">Restaurer</button>` : '') : `<button class="btn small" data-act="copy" data-id="${esc(r.id)}">Dupliquer</button><button class="btn small danger" data-act="delete" data-id="${esc(r.id)}">Supprimer</button>`}</div></div>
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
      else if (a === 'restore') { if (!await J.confirm('Restaurer les valeurs par défaut', `Les réglages de « ${name} » reprendront leurs valeurs d’origine (nom, icône et explications restent). Les autres stratégies ne changent pas.`, 'Restaurer')) return; view = await post({ action: 'restore', id }); render(`« ${name} » restaurée.`); }
    } catch (e) {
      if (/autre session|Rechargez/i.test(e.message || '')) { try { view = await J.api('classement-test/strategies'); } catch (_) { } }
      render(e.message || 'Action impossible.', true);
    }
  }
  try { view = await J.api('classement-test/strategies'); render(); }
  catch (e) { page.innerHTML = `<div class="notice err">Stratégies indisponibles : ${esc(e.message)}</div>`; }
})();
