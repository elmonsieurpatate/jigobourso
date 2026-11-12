/* Centre d'aide interactif : un chapitre à la fois, sommaire latéral, fil d'Ariane, progression, Précédent / Suivant, recherche, modes Débutant / Expert, mémorisation du dernier chapitre.
   Les chapitres sont déclarés dans help-ch-*.js (window.HELP_CHAPTERS.push({...})). Les chiffres des stratégies viennent du moteur (route help/facts) ; les exemples sont fictifs. */
(async () => {
  const me = await J.init('aide'); if (!me) return;
  const E = J.esc, root = J.$('#help'), $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const store = { get: k => { try { return localStorage.getItem(k); } catch (_) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (_) { /* facultatif */ } } };
  const GROUPS = [['demarrer', 'Pour démarrer'], ['bourse', 'Les bases de la bourse'], ['mesures', 'Lire un cours de bourse'], ['jigo', 'Jigobourso : chercher et noter'], ['strategies', 'Les 7 stratégies'], ['patrimoine', 'Mon portefeuille'], ['outils', 'Outils et fiabilité'], ['admin', 'Administration']];
  const ALIAS = { 'premiers-pas': 'bienvenue', parcours: 'parcours', bases: 'action-etf', strategies: 'strategies-vue', adaptees: 'adapter', criteres: 'criteres', scores: 'scores', classements: 'classements', indicateurs: 'indicateurs', fiches: 'fiches', portefeuille: 'portefeuille', gains: 'gains', performances: 'performance-portefeuille', colonnes: 'colonnes', donnees: 'donnees', glossaire: 'glossaire', faq: 'faq', administration: 'admin', explorer: 'explorer',
    'strategie-fast': 'strat-fast', 'strategie-regular': 'strat-regular', 'strategie-calm': 'strat-calm', 'strategie-rebound': 'strat-rebound', 'strategie-mom6': 'strat-mom6', 'strategie-mom12': 'strat-mom12', 'strategie-momrisk': 'strat-momrisk', 'strategie-personnelles': 'adapter' };
  let level = (me.prefs || {}).help_level === 'expert' ? 'expert' : 'beginner', facts = null, meta = {}, current = null, seen = new Set();
  try { seen = new Set(JSON.parse(store.get('jigo_help_seen') || '[]')); } catch (_) { seen = new Set(); }

  /* ───── composants de mise en page partagés par tous les chapitres ───── */
  const H = {
    box: (kind, title, html) => `<aside class="hb hb-${kind}"><div class="hb-t">${E(title)}</div><div class="hb-c">${html}</div></aside>`,
    tip: (html, t = 'À retenir') => H.box('tip', t, html), example: (html, t = 'Exemple') => H.box('example', t, html), jigo: (html, t = 'Dans Jigobourso') => H.box('jigo', t, html), warn: (html, t = 'Attention') => H.box('warn', t, html),
    fig: (svg, cap) => `<div class="hf">${svg}${cap ? `<figcaption>${cap}</figcaption>` : ''}</div>`,
    fold: (title, html, open) => `<details class="hd" ${open ? 'open' : ''}><summary>${title}</summary><div>${html}</div></details>`,
    steps: items => `<ol class="hs">${items.map((s, i) => `<li><span class="hs-n">${i + 1}</span><div><h4>${s[0]}</h4>${s[1]}</div></li>`).join('')}</ol>`,
    cards: items => `<div class="hcards">${items.map(c => `<div class="hcard" ${c.href ? `data-go="${E(c.href)}" tabindex="0" role="link"` : ''}><span class="hcard-i" style="background:${c.bg || 'var(--accent-soft)'}">${c.icon || ''}</span><b>${c.title}</b><p>${c.text}</p></div>`).join('')}</div>`,
    table: (head, rows, cls = '') => `<div class="sui-scroll"><table class="sui-cmp ${cls}"><thead><tr>${head.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map((c, i) => i ? `<td>${c}</td>` : `<th scope="row">${c}</th>`).join('')}</tr>`).join('')}</tbody></table></div>`,
    demo: (name, extra = '') => `<div class="hdemo" data-demo="${E(name)}" ${extra}></div>`,
    quiz: (id, qs) => `<section class="hq" data-quiz="${E(id)}"><h3>Testez-vous</h3>${qs.map((q, i) => `<div class="hq-q" data-i="${i}"><p><b>${i + 1}.</b> ${q.q}</p>${q.o.map((o, j) => `<button type="button" class="hq-o" data-j="${j}" data-ok="${j === q.a ? 1 : 0}">${o}</button>`).join('')}<div class="hq-r" hidden>${q.why}</div></div>`).join('')}<div class="hq-s small muted"></div></section>`,
    fmt: (v, d = 1) => HC.f1(v, d), pct: (v, d = 1) => HC.f1(v, d) + ' %'
  };
  const ctx = () => ({ facts, level, H, HM: window.HM, HC: window.HC, meta, me, go, E });

  /* ───── registre ───── */
  const chapters = () => (window.HELP_CHAPTERS || []).filter(c => !c.admin || me.is_admin);
  const byId = id => chapters().find(c => c.id === id);
  const order = () => { const g = Object.fromEntries(GROUPS.map((x, i) => [x[0], i])); return chapters().map((c, i) => [c, i]).sort((a, b) => (g[a[0].group] - g[b[0].group]) || (a[1] - b[1])).map(x => x[0]); };

  function renderToc(filter) {
    const list = order(), term = (filter || '').trim();
    const matches = term ? search(term) : null;
    $('#h-toc').innerHTML = GROUPS.map(([gid, gl]) => {
      const cs = list.filter(c => c.group === gid && (!matches || matches.has(c.id))); if (!cs.length) return '';
      return `<div class="ht-g"><div class="ht-gl">${E(gl)}</div>${cs.map(c => `<a href="#/${E(c.id)}" class="ht-i ${c.parent ? 'sub' : ''} ${current && current.id === c.id ? 'on' : ''} ${seen.has(c.id) ? 'seen' : ''}" data-id="${E(c.id)}">${c.icon ? `<span class="ht-ic" style="color:${c.color || 'var(--accent)'}">${c.icon}</span>` : ''}<span>${E(c.title)}</span>${seen.has(c.id) ? '<i class="ht-ok" aria-label="vu">✓</i>' : ''}</a>`).join('')}</div>`;
    }).join('') || '<p class="muted small" style="padding:8px">Aucun résultat. Essayez un autre mot.</p>';
  }
  let index = null;
  function buildIndex() { if (index) return; const clean = h => String(h).replace(/<[^>]+>/g, ' ').toLowerCase(); index = chapters().map(c => ({ id: c.id, title: c.title.toLowerCase(), kw: (c.keywords || '').toLowerCase(), text: clean(safe(c, 'beginner') + ' ' + safe(c, 'expert')) })); }
  /* Résultats triés par pertinence : titre > mots-clés > texte (nombre d'occurrences). */
  function ranked(term) { buildIndex(); const words = term.toLowerCase().split(/\s+/).filter(Boolean), phrase = term.toLowerCase().trim();
    return index.map(x => { const all = x.title + ' ' + x.kw + ' ' + x.text; if (!words.every(w => all.includes(w))) return null; let sc = 0; if (x.title.includes(phrase)) sc += 1000; else if (words.every(w => x.title.includes(w))) sc += 600; if (x.kw.includes(phrase)) sc += 300; words.forEach(w => { if (x.kw.includes(w)) sc += 60; sc += Math.min(40, x.text.split(w).length - 1); }); return [x.id, sc]; }).filter(Boolean).sort((a, b) => b[1] - a[1]).map(x => x[0]); }
  function search(term) { return new Set(ranked(term)); }
  function safe(c, k) { try { return typeof c[k] === 'function' ? (c[k](ctx()) || '') : (c[k] || ''); } catch (e) { return ''; } }

  /* ───── affichage d'un chapitre ───── */
  function open(id, opts = {}) {
    id = ALIAS[id] || id; const list = order(); let c = byId(id) || list[0]; if (!c) return;
    current = c; const i = list.indexOf(c), prev = list[i - 1], next = list[i + 1], hasExpert = !!c.expert;
    const parent = c.parent ? byId(c.parent) : null, gl = (GROUPS.find(g => g[0] === c.group) || [0, ''])[1];
    const body = level === 'expert' && hasExpert ? safe(c, 'expert') : safe(c, 'beginner');
    const crumbs = [`<a href="#/bienvenue">Aide</a>`, E(gl), parent ? `<a href="#/${E(parent.id)}">${E(parent.title)}</a>` : '', `<b>${E(c.title)}</b>`].filter(Boolean).join(' <span aria-hidden="true">›</span> ');
    seen.add(c.id); store.set('jigo_help_seen', JSON.stringify([...seen])); store.set('jigo_help_last', c.id);
    if (!opts.silent) J.post('auth/prefs', { help_last: c.id }).then(r => { me.prefs = r.prefs; }).catch(() => { });
    const pct = Math.round(100 * list.filter(x => seen.has(x.id)).length / list.length);
    $('#h-main').innerHTML = `<nav class="h-crumb" aria-label="Fil d’Ariane">${crumbs}</nav>
      <header class="h-head"><span class="h-ico" style="background:color-mix(in srgb, ${c.color || '#2563eb'} 16%, transparent);color:${c.color || '#2563eb'}">${c.icon || ''}</span><div><h1>${E(c.title)}</h1>${c.lead ? `<p class="h-lead">${c.lead}</p>` : ''}</div></header>
      ${hasExpert ? `<div class="h-levelbar">${level === 'expert' ? `Vous lisez la version <b>Expert</b> (formules, paramètres, limites). <button class="btn sm" data-level="beginner">Revenir au niveau Débutant</button>` : `Version <b>Débutant</b>. Envie d’aller plus loin ? <button class="btn sm" data-level="expert">Approfondir (Expert)</button>`}</div>` : ''}
      <article class="h-body">${body}</article>
      ${c.quiz ? '' : ''}
      <footer class="h-nav">${prev ? `<a class="btn" href="#/${E(prev.id)}">← ${E(prev.title)}</a>` : '<span></span>'}<span class="h-prog" title="Progression"><i style="width:${pct}%"></i><small>${list.filter(x => seen.has(x.id)).length} / ${list.length} chapitres vus</small></span>${next ? `<a class="btn primary" href="#/${E(next.id)}">${E(next.title)} →</a>` : '<span></span>'}</footer>`;
    mount(c); renderToc($('#h-q').value); closeDrawer();
    if (!opts.keepScroll) window.scrollTo({ top: 0 });
    document.title = c.title + ' — Aide — Jigobourso';
  }
  function mount(c) {
    const el = $('#h-main');
    $$('[data-level]', el).forEach(b => b.onclick = () => setLevel(b.dataset.level));
    $$('[data-go]', el).forEach(b => { const go2 = () => { location.hash = '#/' + b.dataset.go; }; b.onclick = go2; b.onkeydown = e => { if (e.key === 'Enter') go2(); }; });
    $$('[data-quiz]', el).forEach(q => { let good = 0, done = 0; const total = $$('.hq-q', q).length;
      $$('.hq-o', q).forEach(b => b.onclick = () => { const box = b.closest('.hq-q'); if (box.dataset.done) return; box.dataset.done = 1; done++; const ok = b.dataset.ok === '1'; if (ok) good++; b.classList.add(ok ? 'good' : 'bad'); $$('.hq-o', box).forEach(x => { if (x.dataset.ok === '1') x.classList.add('good'); x.disabled = true; }); const r = $('.hq-r', box); r.hidden = false; r.classList.toggle('bad', !ok); $('.hq-s', q).textContent = done === total ? `Résultat : ${good} / ${total}.${good === total ? ' Bravo !' : ' Relisez les explications ci-dessus puis réessayez.'}` : ''; }); });
    if (typeof c.mount === 'function') { try { c.mount(el, ctx()); } catch (e) { console.error(e); el.insertAdjacentHTML('beforeend', '<div class="notice err">Cette démonstration n’a pas pu se charger.</div>'); } }
  }
  const go = id => { location.hash = '#/' + id; };
  function setLevel(l) { level = l; $$('[data-mode]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.mode === level))); J.post('auth/prefs', { help_level: level }).then(r => { me.prefs = r.prefs; }).catch(() => { }); index = null; if (current) open(current.id, { keepScroll: true, silent: true }); }
  function closeDrawer() { root.classList.remove('toc-open'); }

  /* ───── amorçage ───── */
  root.innerHTML = `<div class="h-top"><button class="btn sm h-burger" type="button" id="h-burger" aria-expanded="false" aria-controls="h-side">☰ Sommaire</button>
    <div class="help-mode" role="group" aria-label="Niveau de détail"><button type="button" data-mode="beginner" aria-pressed="${level === 'beginner'}">Débutant</button><button type="button" data-mode="expert" aria-pressed="${level === 'expert'}">Expert</button></div></div>
    <div class="h-layout"><aside class="h-side" id="h-side" aria-label="Sommaire de l’aide"><label class="h-search"><span class="sr-only">Rechercher dans l’aide</span><input id="h-q" type="search" placeholder="Rechercher : pente, ETF, lots…" autocomplete="off"></label><nav id="h-toc"></nav></aside><div class="h-read"><div id="h-main" class="h-main" tabindex="-1"><div class="empty"><span class="spinner"></span></div></div></div></div>`;
  $$('[data-mode]').forEach(b => b.onclick = () => setLevel(b.dataset.mode));
  $('#h-burger').onclick = () => { const o = root.classList.toggle('toc-open'); $('#h-burger').setAttribute('aria-expanded', String(o)); };
  $('#h-q').oninput = e => { renderToc(e.target.value); const t = e.target.value.trim(); if (t) { const best = ranked(t)[0], hit = best && byId(best); if (hit && e.inputType !== 'deleteContentBackward' && t.length >= 3) { /* ouverture directe de la meilleure rubrique */ if (!current || current.id !== hit.id) { history.replaceState(null, '', '#/' + hit.id); open(hit.id, { silent: true }); } } } };
  $('#h-q').onkeydown = e => { if (e.key === 'Enter') { const best = ranked(e.target.value)[0]; if (best) go(best); } };
  try { facts = await J.api('help/facts'); } catch (e) { facts = null; }
  try { meta = (await J.api('classement-test/strategies')).meta || {}; SUI.setMeta(meta); } catch (e) { meta = {}; }
  const route = () => { const h = decodeURIComponent(location.hash.replace(/^#\/?/, '')); const last = store.get('jigo_help_last') || (me.prefs || {}).help_last; open(h || last || 'bienvenue', { silent: !h }); };
  addEventListener('hashchange', route);
  renderToc(''); route();
})();
