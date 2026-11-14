#!/usr/bin/env bash
# Syntaxe PHP : tous les fichiers suivis par Git, ou ceux donnés en argument.
# Échoue (code 1) à la première erreur de syntaxe, et (code 2) si php est introuvable ou s'il n'y a aucun fichier :
# un contrôle qui ne contrôle rien ne doit jamais afficher « OK ».
set -u
PHP="${PHP:-php}"
command -v "$PHP" > /dev/null 2>&1 || { echo "php introuvable : $PHP" >&2; exit 2; }
if [ "$#" -gt 0 ]; then
  files=("$@")
else
  cd "$(dirname "$0")/.." || exit 2
  mapfile -t files < <(git ls-files '*.php')
fi
[ "${#files[@]}" -gt 0 ] || { echo "aucun fichier PHP à contrôler" >&2; exit 2; }
bad=0
for f in "${files[@]}"; do
  out=$("$PHP" -l "$f" 2>&1) || { echo "$out" >&2; bad=1; }
done
[ "$bad" -eq 0 ] || { echo "php -l : ÉCHEC" >&2; exit 1; }
echo "php -l : OK ($PHP, ${#files[@]} fichiers)"
