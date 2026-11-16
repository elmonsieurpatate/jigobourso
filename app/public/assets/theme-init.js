/* Thème avant le premier affichage : valeur enregistrée (clair / sombre / auto), sinon réglage du système. */
(function () {
  var t = "auto";
  try {
    t = localStorage.getItem("jigo_theme") || "auto";
  } catch (e) {}
  var dark = t === "dark" || (t !== "light" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  // Le navigateur adapte aussi barres de défilement et champs : la méta suit le choix (clair, sombre ou les deux en mode auto).
  var m = document.querySelector('meta[name="color-scheme"]');
  if (!m) {
    m = document.createElement("meta");
    m.name = "color-scheme";
    document.head.appendChild(m);
  }
  m.content = t === "dark" || t === "light" ? t : "light dark";
})();
