// Navigation helpers for the results-first layout. They never modify application state directly.
exports.settings=async(p,tab='strategy')=>{if(!await p.locator('#ct-settings-panel').evaluate(d=>d.open))await p.locator(tab==='filters'?'#ct-filters-open':'#ct-settings-open').click();else await p.locator(`[data-settings-tab="${tab}"]`).click();};
exports.close=async p=>{if(await p.locator('#ct-settings-panel').evaluate(d=>d.open))await p.locator('#ct-settings-close').click();};
exports.options=async p=>{if(!await p.locator('.ct-options').evaluate(d=>d.open))await p.locator('.ct-options>summary').click();};
exports.size=async(p,value)=>{await exports.options(p);await p.locator('#ct-page-size').selectOption(value);await p.locator('.ct-options>summary').click();};
