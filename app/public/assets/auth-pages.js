(async()=>{
 const mode=document.body.dataset.auth, msg=J.$('#msg'), form=J.$('#auth-form'), params=new URLSearchParams(location.hash.slice(1)), token=params.get('token')||'';
 if(token)history.replaceState(null,'',location.pathname); // token remains in this closure only
 const tell=(text,error=false)=>{msg.textContent=text;msg.hidden=false;msg.className='notice '+(error?'err':'ok');};
 const next=new URLSearchParams(location.search).get('next'),safe=next&&/^[a-z]+\.html(\?[^\s]*)?$/i.test(next)?next:'index.html';
 if(mode==='login'){const r=await J.api('auth/me').catch(()=>({}));if(r.user){location.replace(safe);return;}const up=J.$('#up-link');if(up)up.hidden=!r.registration_open;}
 if(['reset','verify'].includes(mode)&&!token){tell('Lien invalide ou expiré. Demandez un nouveau lien.',true);form.hidden=true;return;}
 form.onsubmit=async e=>{e.preventDefault();const submit=form.querySelector('[type=submit]');submit.disabled=true;msg.hidden=true;
 try{
  if(mode==='login'){await J.post('auth/login',{username:J.$('#u').value,password:J.$('#p').value,remember:J.$('#remember').checked});location.replace(safe);}
  if(mode==='recover'){const r=await J.post('auth/recover',{email:J.$('#email').value});tell(r.message);}
  if(mode==='reset'){if(J.$('#p').value!==J.$('#confirm').value)throw Error('Les deux mots de passe ne correspondent pas.');await J.post('auth/reset',{token,new:J.$('#p').value});form.hidden=true;tell('Mot de passe enregistré. Vous pouvez vous connecter avec votre e-mail ou votre pseudo.');J.$('#done').hidden=false;}
  if(mode==='verify'){await J.post('auth/verify-email',{token});form.hidden=true;tell('Nouvelle adresse e-mail confirmée. Elle est maintenant utilisable pour vous connecter.');}
 }catch(e){tell(e.message,true);}finally{submit.disabled=false;}};
})();
