/* Inscription : validation claire, retour honnête sur l'e-mail de bienvenue, connexion automatique puis accueil vers l'aide. */
(() => {
  const $ = s => document.querySelector(s), E = J.esc, form = $('#register'), err = $('#err'), btn = $('#go');
  const fail = m => { err.textContent = m; err.hidden = false; err.scrollIntoView({ block: 'nearest' }); };
  J.api('auth/me').then(r => { if (r && r.user) location.href = 'index.html'; else if (r && r.registration_open === false) { form.querySelectorAll('input,button').forEach(x => x.disabled = true); fail('Les inscriptions sont fermées pour le moment. Contactez l’administrateur.'); } }).catch(() => { });
  form.onsubmit = async e => {
    e.preventDefault(); err.hidden = true;
    const v = { username: $('#name').value.trim(), email: $('#email').value.trim(), password: $('#p').value, code: $('#code').value.trim() };
    if (!/^[A-Za-z0-9_.-]{3,30}$/.test(v.username)) return fail('Pseudo : 3 à 30 caractères (lettres, chiffres, _ . -).');
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v.email)) return fail('Saisissez une adresse e-mail valide.');
    if (v.password.length < 10) return fail('Le mot de passe doit contenir au moins 10 caractères.');
    if (!v.code) return fail('Le mot d’invitation est nécessaire.');
    btn.disabled = true; btn.textContent = 'Création en cours…';
    try {
      const r = await J.post('auth/register', v);
      let logged = true; try { await J.post('auth/login', { username: v.username, password: v.password, remember: false }); } catch (_) { logged = false; }
      $('#box').innerHTML = `<h1>Bienvenue, ${E(v.username)} !</h1><div class="notice" role="status"><b>Votre compte est créé.</b></div>
        <p>${r.welcome_mail ? `Un e-mail de bienvenue vient d’être envoyé à <b>${E(v.email)}</b> (pensez à regarder les courriers indésirables).` : `Nous n’avons pas pu envoyer l’e-mail de bienvenue à <b>${E(v.email)}</b>. Votre compte fonctionne normalement ; vérifiez l’adresse dans « Mon compte ».`}</p>
        <p>Pour bien démarrer, lisez le centre d’aide : il explique la bourse et Jigobourso pas à pas.</p>
        <p>${logged ? '<a class="btn primary" href="aide.html#/bienvenue">Découvrir l’aide</a> <a class="btn" href="index.html">Aller à l’Explorer</a>' : '<a class="btn primary" href="login.html">Me connecter</a>'}</p>`;
      if (logged) setTimeout(() => { location.href = 'aide.html#/bienvenue'; }, 6000);
    } catch (x) { fail(x.message || 'La création du compte a échoué. Réessayez.'); btn.disabled = false; btn.textContent = 'Créer mon compte'; }
  };
  if (J.passwordEyes) J.passwordEyes(form);
})();
