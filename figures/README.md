# `figures/` : les images du README

Toutes les figures sont nettes de frais réels, TRAIN et VAL seulement (le TEST n'existe pas dans ces images).

| Image | Ce qu'elle montre | Script |
|---|---|---|
| `hero_equity.png` | Courbe finale : equity de la pile (base 100, échelle log), TRAIN grisé, VAL hors échantillon, drawdown par période, frais dans le titre. | `scripts/generer_figures_vitrine.py` |
| `toutes_variantes.png` | Les 7 sleeves (gris) et la pile (bleu) sur le même graphique. | `scripts/generer_figures_vitrine.py` |
| `overfit_scatter.png` | Sharpe net TRAIN (x) contre VAL (y) pour chaque variante, avec la diagonale. | `scripts/generer_figures_vitrine.py` |
| `pnl_cumule.png` | PnL cumulé net et brut de chaque sleeve et de la pile. | `scripts/run_train_val.py` |
| `sharpe_val_ic.png` | Sharpe net VAL avec IC 95 % bootstrap et Sharpe brut. | `scripts/run_train_val.py` |
| `correlations.png` | Corrélation des rendements nets entre sleeves, TRAIN et VAL. | `scripts/run_train_val.py` |
| `cout_annuel.png` | Coût annuel de chaque sleeve, TRAIN et VAL (échelle log). | `scripts/run_train_val.py` |
| `sensibilite_couts.png` | EXPLORATOIRE : Sharpe net VAL selon le multiple des coûts. | `scripts/sensibilite_couts.py` |
| `appro_q1_grinold.png` | EXPLORATOIRE : loi fondamentale, IR prédit contre réalisé, IC nécessaire. | `scripts/run_approfondissement.py` |
| `appro_q2_decroissance.png` | EXPLORATOIRE : IC selon l'horizon, gain net par jour, gain par trade contre coût. | `scripts/run_approfondissement.py` |
| `appro_q3_puissance.png` | EXPLORATOIRE : Sharpe minimal détectable selon la durée, probabilités sous Sharpe vrai 0,5. | `scripts/run_approfondissement.py` |
| `appro_q4_tests_multiples.png` | EXPLORATOIRE : Sharpe maximal attendu sans edge selon le nombre d'essais. | `scripts/run_approfondissement.py` |
| `appro_q5_sharpe_glissant.png` | EXPLORATOIRE : Sharpe glissant de chaque sleeve. | `scripts/run_approfondissement.py` |
| `appro_q5_regimes_facteur.png` | EXPLORATOIRE : Sharpe brut par régime de volatilité, exposition au facteur de marché. | `scripts/run_approfondissement.py` |
| `appro_q6_diversification.png` | EXPLORATOIRE : Sharpe de la pile selon le nombre de sleeves et la corrélation. | `scripts/run_approfondissement.py` |
| `appro_q7_capacite.png` | EXPLORATOIRE : rendement net après impact selon le capital géré. | `scripts/run_approfondissement.py` |
