/* Page Mes stratégies : liste des stratégies du Classement test (MariaDB, par utilisateur). */
(async () => {
  if (!await J.init('explorer')) return;
  const page = J.$('#page'), esc = J.esc;
  let view = null;
  const post = body => J.post('classement-test/strategies/save', { revision: view.revision, ...body });
  function askName(title, initial, okLabel) {
    return new Promise(resolve => {
      let done = false;
      J.dialog({ title, body: `<label class="field">Nom de la stratégie<input id="ms-name" maxlength="60" value="${esc(initial)}" autocomplete="off"></label>`,
        actions: [{ label: 'Annuler', run: () => { } }, { label: okLabel, cls: 'primary', run: d => { const v = d.querySelector('#ms-name').value.trim(); if (!v) { J.formError(d, 'Un nom est requis.'); return true; } done = true; resolve(v); } }],
        onopen: d => { const i = d.querySelector('#ms-name'); i.focus(); i.select(); } }).addEventListener('close', () => { if (!done) resolve(null); });
    });
  }
  const when = s => { try { return new Date(s.replace(' ', 'T') + (/Z|[+-]\d\d:?\d\d$/.test(s) ? '' : 'Z')).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' }); } catch (_) { return ''; } };
  function rows() {
    const byId = Object.fromEntries(view.items.map(i => [i.id, i]));
    const list = [];
    for (const [id, name] of Object.entries(view.builtin)) list.push({ id, name, builtin: true, mod: byId[id] || null });
    for (const it of view.items) if (!it.builtin) list.push({ id: it.id, name: it.name, builtin: false, mod: it });
    return list;
  }
  function render(msg, err) {
    const custom = view.items.filter(i => !i.builtin).length;
    page.innerHTML = (msg ? `<div class="notice ${err ? 'err' : ''}" role="status" style="margin-bottom:12px">${esc(msg)}</div>` : '') +
      `<div class="row between" style="margin-bottom:12px"><span class="muted">${custom} / ${view.max_custom} stratégie(s) personnelle(s)</span><a class="btn primary" href="classement-test.html">Créer depuis le Classement test</a></div>` +
      rows().map(r => `<div class="card tight" style="margin-bottom:10px"><div class="row between"><div><b>${esc(r.name)}</b> ${r.builtin ? '<span class="tag">Fournie</span>' : '<span class="tag held">Personnelle</span>'}${r.id === view.selected ? ' <span class="tag open">Dernière utilisée</span>' : ''}` +
        `<div class="small muted">${r.mod ? (r.builtin ? 'Modifiée' : 'Enregistrée') + ' le ' + esc(when(r.mod.updated_at)) : 'Valeurs d’origine'}</div></div>` +
        `<div class="row gap-s"><a class="btn small primary" href="classement-test.html?strategy=${encodeURIComponent(r.id)}">Ouvrir / modifier</a>` +
        (r.builtin ? (r.mod ? `<button class="btn small" data-act="restore" data-id="${esc(r.id)}">Restaurer les valeurs par défaut</button>` : '') :
          `<button class="btn small" data-act="rename" data-id="${esc(r.id)}">Renommer</button><button class="btn small" data-act="copy" data-id="${esc(r.id)}">Dupliquer</button><button class="btn small danger" data-act="delete" data-id="${esc(r.id)}">Supprimer</button>`) +
        `</div></div></div>`).join('');
    J.$$('button[data-act]', page).forEach(b => b.onclick = () => act(b.dataset.act, b.dataset.id));
  }
  async function act(a, id) {
    const it = view.items.find(i => i.id === id), name = (view.builtin[id] || it?.name || '');
    try {
      if (a === 'rename') { const n = await askName('Renommer la stratégie', name, 'Renommer'); if (!n) return; view = await post({ action: 'rename', id, name: n }); render(`Stratégie renommée « ${n} ».`); }
      else if (a === 'copy') {
        const taken = new Set([...Object.values(view.builtin), ...view.items.map(i => i.name)].map(x => x.toLowerCase())); let n = `Copie de ${name}`, k = 2; while (taken.has(n.toLowerCase())) n = `Copie de ${name} (${k++})`;
        n = await askName('Dupliquer la stratégie', n.slice(0, 60), 'Dupliquer'); if (!n) return;
        const keep = view.selected; view = await post({ action: 'create', name: n, config: it.config, filters: it.filters });
        view = await J.post('classement-test/strategies/save', { action: 'select', id: keep }).catch(() => view); render(`« ${n} » créée.`);
      }
      else if (a === 'delete') { if (!await J.confirm('Supprimer la stratégie', `« ${name} » sera supprimée définitivement. Les autres stratégies ne changent pas.`, 'Supprimer')) return; view = await post({ action: 'delete', id }); render(`« ${name} » supprimée.`); }
      else if (a === 'restore') { if (!await J.confirm('Restaurer les valeurs par défaut', `« ${name} » reprendra ses valeurs d’origine. Les autres stratégies ne changent pas.`, 'Restaurer')) return; view = await post({ action: 'restore', id }); render(`« ${name} » restaurée.`); }
    } catch (e) {
      if (e.status === 409 || /autre session|Rechargez/i.test(e.message || '')) { try { view = await J.api('classement-test/strategies'); } catch (_) { } }
      render(e.message || 'Action impossible.', true);
    }
  }
  try { view = await J.api('classement-test/strategies'); render(); }
  catch (e) { page.innerHTML = `<div class="notice err">Stratégies indisponibles : ${esc(e.message)}</div>`; }
})();
