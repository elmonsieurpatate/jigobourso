"""Mise en forme des messages affichés."""


def fr(x, digits=1):
    """Nombre à la française (virgule décimale)."""
    return f'{x:.{digits}f}'.replace('.', ',')
