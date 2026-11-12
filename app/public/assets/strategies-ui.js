/* Éléments partagés des stratégies (Explorer, Mes stratégies, Aide) : icône distincte par stratégie, badge de statut, fenêtre d'information, sélecteur groupé accessible. */
(() => {
  const E = J.esc;
  const ICON = { fast: 'rocket', regular: 'trend', calm: 'leaf', rebound: 'rebound', mom6: 'clock6', mom12: 'calendar', momrisk: 'shieldcheck' };
  const STATUS = { official: 'Officielle', adapted: 'Adaptée', personal: 'Personnelle' };
  const SHORT = {
    fast: 'Cherche les titres qui montent fortement à la semaine et au mois.',
    regular: 'Cherche une hausse soutenue et régulière sur un mois et un trimestre.',
    calm: 'Cherche une hausse douce, avec peu de secousses, sur un mois et un trimestre.',
    rebound: 'Cherche les titres qui repartent à la hausse après un semestre peu avancé.',
    mom6: 'Classe selon la variation des six derniers mois, hors dernier mois.',
    mom12: 'Classe selon la variation des douze derniers mois, hors dernier mois.',
    momrisk: 'Combine le momentum 6 et 12 mois, corrigé de la volatilité et du repli.',
    personal: 'Stratégie personnelle : visible uniquement dans votre compte.' };
  let META = {};                                   // icône et explications choisies par l'utilisateur (défauts des stratégies d'origine inclus) : mêmes partout
  const setMeta = m => { META = m && typeof m === 'object' ? m : {}; };
  // Couleur propre à chaque icône (jeu varié, pas deux teintes) : valeurs choisies pour les stratégies d'origine, puis teinte déduite de la clé.
  const HUES = { 'arrow-up': '#16a34a', 'arrow-down': '#dc2626', 'arrow-left': '#d97706', 'arrow-right': '#0891b2', 'arrow-up-left': '#16a34a', 'arrow-down-left': '#dc2626', 'arrow-left-right': '#2563eb', 'chevron-up': '#16a34a', 'chevron-down': '#dc2626', 'chevrons-up': '#16a34a', 'chevrons-down': '#dc2626', 'chevrons-up-down': '#dc2626', 'arrow-big-up': '#16a34a', 'arrow-big-down': '#dc2626', 'arrow-big-up-dash': '#16a34a', 'move-up': '#16a34a', 'move-down': '#dc2626', 'move-up-right': '#16a34a', 'move-down-right': '#dc2626', 'circle-arrow-up': '#16a34a', 'circle-arrow-down': '#dc2626', 'circle-arrow-up-right': '#16a34a', 'circle-arrow-down-right': '#dc2626', 'circle-chevron-up': '#16a34a', 'circle-chevron-down': '#dc2626', 'square-arrow-up-right': '#16a34a', 'corner-right-up': '#16a34a', 'corner-right-down': '#dc2626', 'arrow-up-from-line': '#16a34a', 'arrow-down-to-line': '#dc2626', 'arrow-up-wide-narrow': '#16a34a', 'arrow-down-wide-narrow': '#dc2626', 'rotate-cw': '#2563eb', 'rotate-ccw': '#2563eb', 'trending-up-down': '#dc2626', 'chart-no-axes-column-increasing': '#0891b2', rocket: '#f97316', 'trending-up': '#16a34a', waves: '#0891b2', 'refresh-cw': '#2563eb', hourglass: '#d97706', 'calendar-days': '#7c3aed', 'shield-check': '#4f46e5', 'trending-down': '#dc2626', gem: '#0ea5e9', coins: '#ca8a04', landmark: '#475569', target: '#e11d48', sprout: '#65a30d', scale: '#0d9488', zap: '#eab308', gauge: '#9333ea', trophy: '#f59e0b', compass: '#2563eb', flame: '#ea580c' };
  const PALETTE = ['#2563eb', '#16a34a', '#f97316', '#9333ea', '#0891b2', '#e11d48', '#ca8a04', '#4f46e5', '#0d9488', '#db2777', '#65a30d', '#ea580c'];
  const hue = key => HUES[key] || PALETTE[[...String(key)].reduce((a, c) => a + c.charCodeAt(0), 0) % PALETTE.length];
  const isEmoji = key => typeof key === 'string' && key && !(window.STRATEGY_ICONS && STRATEGY_ICONS[key]) && /[^\x00-\x7f]/.test(key);
  const glyph = key => (window.STRATEGY_ICONS && STRATEGY_ICONS[key]) ? `<svg class="sui-ic" viewBox="0 0 24 24" aria-hidden="true" style="color:${hue(key)}">${STRATEGY_ICONS[key]}</svg>` : isEmoji(key) ? `<span class="sui-emoji">${E(key)}</span>` : '';
  const tint = key => (window.STRATEGY_ICONS && STRATEGY_ICONS[key]) ? `background:color-mix(in srgb, ${hue(key)} 16%, transparent)` : '';
  const icon = (id, kind) => glyph(META[id] && META[id].icon) || J.icon(kind === 'personal' ? 'user' : (ICON[id] || 'target'), 'sui-ic');
  const ico = (id, kind) => `<span class="sui-ico" aria-hidden="true" style="${tint(META[id] && META[id].icon)}">${icon(id, kind)}</span>`;
  const desc = (id, kind) => (META[id] && META[id].description) || SHORT[kind === 'personal' ? 'personal' : id] || '';
  const badge = st => `<span class="badge sm ${{ adapted: 'info', personal: 'ok' }[st] || ''}">${E(STATUS[st] || st)}</span>`;
  let pop = null;
  function closePop() { if (pop) { pop.remove(); pop = null; document.removeEventListener('keydown', onKey, true); } }
  function onKey(e) { if (e.key === 'Escape') closePop(); }
  /** Fenêtre d'information : ouverte au clic ou au clavier (pas seulement au survol), fermée par Échap ou clic extérieur. */
  function openInfo(btn, s) {
    closePop();
    const kind = s.kind || (s.builtin === false ? 'personal' : 'builtin');
    pop = document.createElement('div'); pop.className = 'sui-pop'; pop.setAttribute('role', 'dialog'); pop.setAttribute('aria-label', 'À propos de ' + s.label);
    pop.innerHTML = `<h4>${ico(s.id, kind)}<span>${E(s.label)}</span>${badge(s.status)}</h4><p>${E(desc(s.id, kind))}</p><a href="aide.html#strategie-${E(kind === 'personal' ? 'personnelles' : s.id)}">Lire la fiche complète dans l’aide</a>`;
    document.body.appendChild(pop);
    const r = btn.getBoundingClientRect(), w = pop.offsetWidth;
    pop.style.left = Math.max(12, Math.min(innerWidth - w - 12, r.left)) + 'px'; pop.style.top = Math.min(innerHeight - pop.offsetHeight - 12, r.bottom + 6) + 'px';
    document.addEventListener('keydown', onKey, true);
    setTimeout(() => document.addEventListener('click', function f(e) { if (pop && !pop.contains(e.target) && e.target !== btn) { closePop(); document.removeEventListener('click', f); } }), 0);
  }
  const infoButton = s => `<button type="button" class="sui-info" data-sui-info="${E(s.id)}" aria-label="Informations sur ${E(s.label)}" aria-haspopup="dialog">${J.icon('info', 'sui-ic')}</button>`;
  function bindInfo(root, list) { root.querySelectorAll('[data-sui-info]').forEach(b => { b.onclick = e => { e.stopPropagation(); e.preventDefault(); const s = list.find(x => x.id === b.dataset.suiInfo); if (s) openInfo(b, s); }; }); }
  /** Sélecteur groupé « STRATÉGIES INTÉGRÉES (7) » / « MES STRATÉGIES » avec badge de statut. Remplace le <select> d'origine (qui reste dans le DOM, caché, et reçoit l'événement change). */
  function picker(select, strategies, current) {
    let host = select.parentNode.querySelector('.sui-pick');
    if (!host) { host = document.createElement('div'); host.className = 'sui-pick'; select.after(host); select.classList.add('sui-native'); select.setAttribute('aria-hidden', 'true'); select.tabIndex = -1; }
    const by = Object.fromEntries(strategies.map(s => [s.id, s])), cur = by[current] || strategies[0];
    const built = strategies.filter(s => s.kind === 'builtin'), mine = strategies.filter(s => s.kind === 'personal');
    const opt = s => `<button type="button" class="sui-opt" role="option" data-id="${E(s.id)}" aria-selected="${s.id === current}">${ico(s.id, s.kind)}<span class="grow">${E(s.label)}</span>${badge(s.status)}</button>`;
    host.innerHTML = `<button type="button" class="sui-pick-btn" aria-haspopup="listbox" aria-expanded="false" aria-label="Stratégie : ${E(cur ? cur.label : '')}">${cur ? ico(cur.id, cur.kind) : ''}<span class="grow">${E(cur ? cur.label : 'Stratégie')}</span>${cur ? badge(cur.status) : ''}${J.icon('chev', 'sui-ic')}</button>
      <div class="sui-list" role="listbox" hidden><div class="sui-grp">Stratégies intégrées (${built.length})</div>${built.map(opt).join('')}${mine.length ? `<div class="sui-grp">Mes stratégies</div>${mine.map(opt).join('')}` : ''}</div>`;
    const btn = host.querySelector('.sui-pick-btn'), list = host.querySelector('.sui-list');
    const set = open => { list.hidden = !open; btn.setAttribute('aria-expanded', String(open)); if (open) (list.querySelector('[aria-selected=true]') || list.querySelector('.sui-opt')).focus(); };
    btn.onclick = () => set(list.hidden);
    list.onclick = e => { const o = e.target.closest('.sui-opt'); if (!o) return; set(false); btn.focus(); if (o.dataset.id !== select.value) { select.value = o.dataset.id; select.dispatchEvent(new Event('change', { bubbles: true })); } };
    host.onkeydown = e => {
      const opts = [...list.querySelectorAll('.sui-opt')], i = opts.indexOf(document.activeElement);
      if (e.key === 'Escape' && !list.hidden) { set(false); btn.focus(); }
      else if (e.key === 'ArrowDown' && !list.hidden) { e.preventDefault(); opts[Math.min(opts.length - 1, i + 1)].focus(); }
      else if (e.key === 'ArrowUp' && !list.hidden) { e.preventDefault(); opts[Math.max(0, i - 1)].focus(); }
    };
    document.addEventListener('click', e => { if (!host.contains(e.target)) set(false); });
  }
  /** Bandeau compact : état des critères de recherche et du calcul des scores de la stratégie choisie. */
  function banner(s) {
    if (!s) return '';
    if (s.kind === 'personal') return `<div class="sui-banner" role="status"><span>${badge('personal')}</span><span>Stratégie personnelle : critères et réglages propres à votre compte.</span><a href="mes-strategies.html">Mes stratégies</a></div>`;
    const part = (name, p) => `<span><b>${name}</b> ${badge(p.state === 'adapted' ? 'adapted' : 'official')}${p.modified ? ` <span class="muted small">${p.modified} paramètre${p.modified > 1 ? 's' : ''} modifié${p.modified > 1 ? 's' : ''}</span>` : ''}</span>`;
    return `<div class="sui-banner" role="status">${part('Critères de recherche', s.criteria)}${part('Calcul des scores', s.scores)}<a href="mes-strategies.html?id=${E(s.id)}">Comparer / restaurer</a></div>`;
  }
  window.SUI = { ICON, STATUS, SHORT, setMeta, desc, glyph, hue, tint, icon, ico, badge, infoButton, bindInfo, openInfo, picker, banner };
})();
