/* Liste déroulante à choix multiple : la valeur reste dans un champ caché (valeurs séparées par « | »), lu et écrit comme n'importe quel champ. */
(() => {
  const SEP = '|';
  const parse = v => (v || '').split(SEP).filter(Boolean);
  window.JMulti = function (input, label) {
    const root = document.createElement('div');
    root.className = 'ms';
    root.innerHTML = '<button type="button" class="ms-btn" aria-haspopup="listbox" aria-expanded="false"><span class="ms-txt"></span></button><div class="ms-pop" hidden><input type="search" class="ms-q" placeholder="Filtrer la liste" aria-label="Filtrer la liste"><div class="ms-list" role="listbox" aria-multiselectable="true"></div><div class="ms-foot"><button type="button" class="btn small ms-clear">Tout décocher</button><button type="button" class="btn small primary ms-ok">Fermer</button></div></div>';
    input.insertAdjacentElement('afterend', root);
    const btn = root.querySelector('.ms-btn'), pop = root.querySelector('.ms-pop'), list = root.querySelector('.ms-list'), q = root.querySelector('.ms-q');
    const raw = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
    let options = [];                                   // [valeur, libellé, effectif]
    const chosen = () => parse(raw.get.call(input));
    function render() {
      const sel = new Set(chosen()), term = q.value.trim().toLocaleLowerCase('fr');
      root.querySelector('.ms-txt').textContent = sel.size === 0 ? 'Tous' : sel.size === 1 ? (options.find(o => o[0] === [...sel][0]) || [0, [...sel][0]])[1] : sel.size + ' sélectionnés';
      btn.classList.toggle('has', sel.size > 0);
      list.replaceChildren(...options.filter(o => !term || o[1].toLocaleLowerCase('fr').includes(term)).map(([v, l, n]) => {
        const row = document.createElement('label'); row.className = 'ms-row';
        const cb = document.createElement('input'); cb.type = 'checkbox'; cb.checked = sel.has(v);
        cb.onchange = () => { cb.checked ? sel.add(v) : sel.delete(v); commit([...sel]); };
        const t = document.createElement('span'); t.textContent = l;
        const c = document.createElement('span'); c.className = 'muted small'; c.textContent = n ?? '';
        row.append(cb, t, c); return row;
      }));
    }
    function commit(values) { raw.set.call(input, values.join(SEP)); render(); input.dispatchEvent(new Event('change', { bubbles: true })); }
    Object.defineProperty(input, 'value', { get() { return raw.get.call(input); }, set(v) { raw.set.call(input, v); render(); } });
    const open = on => { pop.hidden = !on; btn.setAttribute('aria-expanded', on); if (on) { q.value = ''; render(); q.focus(); } };
    btn.onclick = () => open(pop.hidden);
    root.querySelector('.ms-ok').onclick = () => { open(false); btn.focus(); };
    root.querySelector('.ms-clear').onclick = () => commit([]);
    q.oninput = render;
    root.addEventListener('keydown', e => { if (e.key === 'Escape' && !pop.hidden) { open(false); btn.focus(); } });
    document.addEventListener('click', e => { if (!root.contains(e.target)) open(false); });
    render();
    return { set(entries) { options = entries; render(); } };
  };
})();
