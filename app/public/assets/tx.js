/* Dialogue d'ajout / modification d'une transaction (partagé par la fiche titre et la page Portefeuilles). */
J.txDialog = function ({ portfolios, portfolioId, listing, tx, onDone }) {
  const editing = !!tx, today = new Date().toISOString().slice(0, 10);
  const opts = portfolios.map(p => `<option value="${p.id}" ${p.id === portfolioId ? 'selected' : ''}>${J.esc(p.name)}</option>`).join('');
  const body = `${editing ? '' : J.field('Portefeuille', `<select id="tx-pf">${opts}</select>`)}
    ${listing ? `<div class="notice">${J.esc(listing.name)} · ${J.esc(listing.symbol)} <span class="muted">(${J.esc(listing.currency || '')})</span></div>` :
      editing ? `<div class="notice">${J.esc(tx.name || tx.symbol)}</div>` : `<div id="pick">${J.field('Titre (nom, symbole ou ISIN)', '<input id="tx-q" autocomplete="off" placeholder="Rechercher dans le catalogue">')}<div id="tx-hits" class="small"></div></div>`}
    <div class="row"><span class="seg" id="tx-side"><button type="button" data-v="buy" class="on">Achat</button><button type="button" data-v="sell">Vente</button></span></div>
    <div class="grid cols-2">${J.field('Quantité', `<input id="tx-qty" inputmode="decimal" value="${tx ? tx.quantity.replace(/\.?0+$/, '') : ''}">`)}${J.field('Prix unitaire (devise du titre)', `<input id="tx-price" inputmode="decimal" value="${tx ? tx.unit_price.replace(/\.?0+$/, '') : (listing && listing.price ? +listing.price : '')}">`)}
    <div class="small muted" id="tx-hint" style="grid-column:1/-1;margin-top:-6px"></div>
    ${J.field('Frais (€)', `<input id="tx-fees" inputmode="decimal" value="${tx && tx.fees ? tx.fees.replace(/\.?0+$/, '') : ''}" placeholder="0">`)}${J.field('Date', `<input id="tx-date" type="date" max="${today}" value="${tx ? tx.trade_at.slice(0, 10) : today}">`)}
    ${listing || editing ? '' : J.field('Devise', '<input id="tx-cur" maxlength="3" value="EUR">')}${J.field('Taux vers l’euro (facultatif)', `<input id="tx-fx" inputmode="decimal" value="${tx && tx.fx_to_eur ? tx.fx_to_eur.replace(/\.?0+$/, '') : ''}" placeholder="auto">`)}</div>
    ${J.field('Note', `<input id="tx-note" maxlength="500" value="${J.esc(tx ? tx.note || '' : '')}">`)}`;
  let side = tx ? tx.side : 'buy', chosen = listing || null;
  J.dialog({
    title: editing ? 'Modifier la transaction' : 'Nouvelle transaction', body,
    actions: [{ label: 'Annuler', run: () => { } }, {
      label: 'Enregistrer', cls: 'primary', run: async d => {
        const v = id => J.$('#' + id, d)?.value ?? '';
        const common = { side, quantity: v('tx-qty'), unit_price: v('tx-price'), fees: v('tx-fees'), fx_to_eur: v('tx-fx'), trade_at: v('tx-date'), note: v('tx-note') };
        if (editing) await J.post('tx/update', { id: tx.id, ...common });
        else {
          const pf = +v('tx-pf');
          if (chosen) await J.post('tx/add', { portfolio_id: pf, listing_id: chosen.id, ...common });
          else { const sym = v('tx-q').trim(); if (!sym) throw new Error('Choisissez un titre'); await J.post('tx/add', { portfolio_id: pf, symbol: sym, currency: v('tx-cur'), ...common }); }
        }
        J.toast('Transaction enregistrée'); if (onDone) onDone();
      },
    }],
    onopen: d => {
      J.$$('#tx-side button', d).forEach(b => { b.classList.toggle('on', b.dataset.v === side); b.onclick = () => { side = b.dataset.v; J.$$('#tx-side button', d).forEach(x => x.classList.toggle('on', x === b)); }; });
      const hint = () => { const h = J.$('#tx-hint', d), p = +J.$('#tx-price', d).value.replace(',', '.'), n = +J.$('#tx-qty', d).value.replace(',', '.'), last = chosen && chosen.price ? +chosen.price : null;
        h.innerHTML = (last ? `Dernier cours connu : <b>${J.num(last, 2)}</b> ${J.esc(chosen.price_currency || chosen.currency || '')} <a href="#" id="tx-last">utiliser ce cours</a> · ` : 'Prix payé (ou que vous paierez) pour <b>une</b> part, dans la devise du titre. ') + (p > 0 && n > 0 ? `Total ≈ <b>${J.num(p * n, 2)}</b> ${J.esc((chosen && chosen.currency) || '')} hors frais` : 'Saisissez la quantité pour voir le total.');
        const a = J.$('#tx-last', d); if (a) a.onclick = e => { e.preventDefault(); J.$('#tx-price', d).value = +chosen.price; hint(); }; };
      ['tx-qty', 'tx-price'].forEach(i => J.$('#' + i, d).addEventListener('input', hint)); hint();
      const q = J.$('#tx-q', d); if (!q) return; let t;
      q.oninput = () => { clearTimeout(t); chosen = null; t = setTimeout(async () => {
        const r = await J.api('listings/search', { params: { q: q.value } });
        J.$('#tx-hits', d).innerHTML = r.results.map(x => `<div><a href="#" data-id="${x.id}">${J.esc(x.name)} — ${J.esc(x.symbol)} (${J.esc(x.mic)})</a> ${x.status === 'excluded' ? '<span class="badge ko">exclu</span>' : ''}</div>`).join('') || '<span class="muted">Aucun résultat : le symbole saisi sera enregistré tel quel.</span>';
        J.$$('#tx-hits a', d).forEach(a => a.onclick = e => { e.preventDefault(); chosen = r.results.find(x => x.id == a.dataset.id); q.value = chosen.name + ' — ' + chosen.symbol; J.$('#tx-hits', d).textContent = ''; if (chosen.price) J.$('#tx-price', d).value = +chosen.price; hint(); });
      }, 250); };
    },
  });
};
