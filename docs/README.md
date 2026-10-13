# `docs/` : le tableau de bord interactif (GitHub Pages) et les pages de détail

Page statique qui permet de choisir les conditions de départ (nombre de trades minimum, jours actifs, Sharpe TRAIN minimum, drawdown TRAIN maximum, fréquence, classe d'actifs), de combiner les sleeves retenues et de lire la courbe finale sur TRAIN puis VAL (déjà vue lors d'un projet antérieur, voir le README), avec métriques et voyant « Overfit ? ».
La sélection n'utilise que TRAIN ; le TEST n'apparaît jamais. Pas de serveur nécessaire : ouvrir `index.html` (les données sont dans `data.js`) ou publier le dossier avec GitHub Pages.

| Fichier | Rôle |
|---|---|
| `index.html` | La page (copie du gabarit commun de tableau de bord) ; charge Plotly depuis cdnjs. |
| `data.json` | Rendements quotidiens nets des 7 sleeves et de la pile, statistiques TRAIN, filtres. Généré. |
| `data.js` | Même contenu que `data.json`, sous la forme `window.DATA = ...`, pour l'ouverture directe en `file://`. Généré. |
| `.nojekyll` | Fichier vide : demande à GitHub Pages de servir les fichiers tels quels. |
| `resultats_detailles.md` | Tous les chiffres par sleeve et pour la pile, gates, poids, figures de lecture, lecture détaillée. Tableaux générés par `scripts/generer_readme_tete.py`. |
| `approfondissement.md` | EXPLORATOIRE : contrôle positif, sensibilité aux coûts, sept questions (Q1 à Q7), ce qu'il faudrait pour un Sharpe > 2, références de pratique. |

Régénérer `data.json`, `data.js` et la page : `python scripts/exporter_dashboard.py` (lit `results/`, aucune donnée de marché requise).
