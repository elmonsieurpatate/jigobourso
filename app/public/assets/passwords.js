/* Visibility concerns only the characters currently typed in this browser. */
(() => {
if (J.passwordEyes) return;
J.passwordEyes = (root = document) => {
  root.querySelectorAll('input[type="password"]').forEach(input => {
    if (input.dataset.eye) return; input.dataset.eye='1';
    const wrap=document.createElement('div');wrap.className='pw-wrap';input.parentNode.insertBefore(wrap,input);wrap.appendChild(input);
    const b=document.createElement('button');b.type='button';b.className='btn small pw-eye';b.innerHTML='<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>'; b.setAttribute('aria-label','Afficher le mot de passe');b.setAttribute('aria-pressed','false');
    b.onclick=()=>{const show=input.type==='password';input.type=show?'text':'password';b.style.opacity=show?'0.6':'1';b.setAttribute('aria-label',show?'Masquer le mot de passe':'Afficher le mot de passe');b.setAttribute('aria-pressed',String(show));};wrap.appendChild(b);
  });
};
J.passwordEyes();
new MutationObserver(()=>J.passwordEyes()).observe(document.body,{childList:true,subtree:true});

})();
