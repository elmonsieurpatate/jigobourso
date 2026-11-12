/* Thème avant le premier affichage : valeur enregistrée (clair / sombre / auto), sinon réglage du système. */
(function () {
  var t = 'auto';
  try { t = localStorage.getItem('jigo_theme') || 'auto'; } catch (e) { }
  var dark = t === 'dark' || (t !== 'light' && matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
})();
