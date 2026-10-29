/* Visibility concerns only the characters currently typed in this browser. */
window.J = window.J || {};
J.passwordEyes = (root = document) => {
  root.querySelectorAll('input[type="password"]').forEach(input => {
    if (input.dataset.eye) return; input.dataset.eye='1';
    const wrap=document.createElement('div');wrap.className='pw-wrap';input.parentNode.insertBefore(wrap,input);wrap.appendChild(input);
    const b=document.createElement('button');b.type='button';b.className='btn small pw-eye';b.textContent='Afficher';b.setAttribute('aria-label','Afficher le mot de passe');b.setAttribute('aria-pressed','false');
    b.onclick=()=>{const show=input.type==='password';input.type=show?'text':'password';b.textContent=show?'Masquer':'Afficher';b.setAttribute('aria-label',show?'Masquer le mot de passe':'Afficher le mot de passe');b.setAttribute('aria-pressed',String(show));};wrap.appendChild(b);
  });
};
J.passwordEyes();
new MutationObserver(()=>J.passwordEyes()).observe(document.body,{childList:true,subtree:true});
