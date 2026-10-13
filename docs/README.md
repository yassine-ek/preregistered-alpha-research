# `docs/` : le tableau de bord interactif (GitHub Pages)

Page statique qui permet de choisir les conditions de départ (nombre de trades minimum, jours actifs, Sharpe TRAIN minimum, drawdown TRAIN maximum, fréquence, classe d'actifs), de combiner les sleeves retenues et de lire la courbe finale sur TRAIN puis VAL (hors échantillon), avec métriques et voyant « Overfit ? ».
La sélection n'utilise que TRAIN ; le TEST n'apparaît jamais. Pas de serveur nécessaire : ouvrir `index.html` (les données sont dans `data.js`) ou publier le dossier avec GitHub Pages.

| Fichier | Rôle |
|---|---|
| `index.html` | La page (copie du gabarit commun des projets) ; charge Plotly depuis cdnjs. |
| `data.json` | Rendements quotidiens nets des 7 sleeves et de la pile, statistiques TRAIN, filtres. Généré. |
| `data.js` | Même contenu que `data.json`, sous la forme `window.DATA = ...`, pour l'ouverture directe en `file://`. Généré. |
| `.nojekyll` | Fichier vide : demande à GitHub Pages de servir les fichiers tels quels. |

Régénérer `data.json`, `data.js` et la page : `python scripts/exporter_dashboard.py` (lit `results/`, aucune donnée de marché requise).
