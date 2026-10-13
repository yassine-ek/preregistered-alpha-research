# Projet 04 : peut-on empiler des stratégies simples jusqu'à un Sharpe net > 2 ?

Un protocole de recherche d'alpha qui interdit de se mentir : sept stratégies de la littérature aux paramètres figés avant le premier calcul, coûts réels par actif, exécution décalée, test final scellé, statistiques déflatées. Le résultat est un échec documenté, avec toutes les courbes et tous les chiffres.

*A pre-registered alpha-research protocol: seven literature strategies with parameters frozen before any computation, real per-asset costs, delayed execution, a sealed final test. The outcome is a documented failure, with every curve and every number.*

![tests](https://img.shields.io/badge/tests-84%20passed-brightgreen) ![python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue) ![licence](https://img.shields.io/badge/licence-MIT-lightgrey)

<!-- AUTO:TETE -->
### Frais et hypothèses

| Hypothèse | Valeur |
|---|---|
| Coûts par jambe | FX : médiane 1,63 bp (48 actifs, 0,40 à 10,69) ; Indice : médiane 12,00 bp (7 actifs) ; Matière première / métal : médiane 1,91 bp (3 actifs, 0,73 à 2,53). Indices figés à 12 bp (pas d'override individuel). Coût = bp × \|Δ position\| ; ouvrir puis fermer = 2 jambes |
| Source des coûts | spreads publics de courtiers (FBS, FTS Prime, IG, Pepperstone, Tickmill, Trading 212), fichier versionné [`data/frais_editable.csv`](data/frais_editable.csv) ; millésime récent appliqué à toute la période, donc plutôt flatteur pour 2010-2015. Tout résultat calculé avec d'autres coûts est invalide |
| Non modélisé | portage et financement (swaps, intérêts), glissement au-delà du spread, impact, compensation d'ordres entre sleeves (chaque sleeve paie ses propres coûts : prudent) |
| Données | HistData 1 minute (BID) et barres 1 h dérivées ; 58 actifs liquides (FX, indices, métaux et pétrole), actifs morts exclus ; non redistribuées (voir « Reproduire ») |
| Découpage | TRAIN 2010-2018 (préchauffage, calibration des échelles) · VAL 2019-2022 (évaluation) · **TEST 2023+ : scellé**, jamais lu (`scripts/ouvrir_test.py` n'a jamais été lancé) |
| Délai d'exécution | quotidien : décision à l'instantané de 11h00, exécution le jour suivant, gain du jour suivant au surlendemain (un jour plein) ; intrajournalier : entrée à l'open de la minute qui suit le signal |
| Risque | chaque sleeve vise 10 % de volatilité annuelle ex ante (EWMA, passé seulement) ; pile à 10 % de vol sur TRAIN |
| Statistiques | IC 95 % du Sharpe par bootstrap stationnaire (blocs de 20 jours, 5000 tirages), Newey-West + Holm, PSR et DSR (8 essais). Sharpe annualisé par √252 |
| Gates (pré-enregistrées) | G1 Sharpe net VAL ≥ 1 : **−5,30** · G2 borne basse IC 95 % > 0 : **−6,31** · G3 DSR ≥ 0,95 : **< 0,001** |

### Métriques de la pile (les 7 sleeves, toutes gardées, nettes de frais)

| Métrique | TRAIN | VAL |
|---|---|---|
| Sharpe net (annualisé, √252) | −6,48 | −5,30 |
| Sharpe brut (avant frais) | 0,01 | −0,70 |
| IC 95 % bootstrap du Sharpe net | [−7,39 ; −5,64] | [−6,31 ; −4,30] |
| Rendement annualisé net | −64,8 % | −52,4 % |
| Volatilité annualisée | 10,0 % | 9,9 % |
| Drawdown max | −99,5 % | −88,9 % |
| Calmar (rendement / drawdown max) | −0,65 | −0,59 |
| Nombre de trades (ordres exécutés) | 100 520 | 50 528 |
| Taux de gain (jours actifs gagnants) | 31,6 % | 35,8 % |
| Rotation annuelle (× le capital) | 1 375× | 1 349× |
| Coût annuel (% du capital) | 64,9 % | 45,5 % |
| PSR(0) | 0,000 | 0,000 |
| DSR (8 essais) | défini sur VAL | < 0,001 |
| Nombre d'essais | 8 | 8 (7 sleeves + la pile) |
| Verdict | n/a | **ECHEC** (G1, G2, G3 en échec ; TEST scellé) |

### Chaque sleeve, TRAIN | VAL côte à côte

| Série | Sharpe net TRAIN | Sharpe net VAL | Rend. net/an TRAIN | Rend. net/an VAL | Drawdown TRAIN | Drawdown VAL | Trades TRAIN | Trades VAL | Coût/an VAL | DSR VAL |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 Trend following | 0,16 | −0,20 | 1,7 % | −2,2 % | −30 % | −19 % | 61 250 | 32 332 | 0,9 % | < 0,001 |
| S2 Momentum devises | −0,46 | −0,82 | −4,9 % | −8,9 % | −40 % | −39 % | 3 275 | 1 476 | 1,2 % | < 0,001 |
| S3 Retournement devises | −0,31 | −0,49 | −3,2 % | −5,0 % | −40 % | −26 % | 3 635 | 1 648 | 3,5 % | < 0,001 |
| S4 Saisonnalité FX | −1,91 | −1,81 | −20,1 % | −19,0 % | −86 % | −56 % | 27 200 | 12 444 | 20,5 % | < 0,001 |
| S5 Fixing fin de mois | −0,47 | −0,49 | −5,0 % | −4,1 % | −37 % | −28 % | 784 | 366 | 2,9 % | < 0,001 |
| S6 Actions vol-gérées | 0,52 | 0,07 | 5,2 % | 0,7 % | −17 % | −15 % | 654 | 336 | 0,6 % | < 0,001 |
| S7 Momentum SPX intraj. | −15,60 | −12,34 | −190,9 % | −134,2 % | −100 % | −100 % | 3 722 | 1 926 | 121,2 % | < 0,001 |
| **PILE (7 sleeves)** | −6,48 | −5,30 | −64,8 % | −52,4 % | −100 % | −89 % | 100 520 | 50 528 | 45,5 % | < 0,001 |

*Nombre de trades = ordres exécutés (quotidien : variations de position non nulles par actif ; intrajournalier : 2 ordres par position). TRAIN d'une sleeve = depuis son premier jour actif.*
<!-- /AUTO:TETE -->

![Equity nette de la pile des 7 sleeves, TRAIN grisé, VAL hors échantillon, drawdown en dessous](figures/hero_equity.png)

**Comment lire ce graphique.** Capital de la pile (les 7 sleeves, toutes gardées) en base 100, échelle logarithmique, **net de frais réels** (rappelés dans le titre). Zone grisée : TRAIN ; à droite de la ligne pointillée : VAL, hors échantillon. Le panneau du bas est le drawdown de chaque période.
Une courbe qui descend régulièrement dans les deux zones n'est pas un overfit : c'est l'absence d'edge, aggravée par des coûts supérieurs au gain brut.

<!-- AUTO:OVERFIT -->
### Overfit ou pas ? Lecture en 30 secondes

1. **Rapport Sharpe VAL / TRAIN de la pile : −5,30 / −6,48 = 0,82, mais les deux sont négatifs.** Il n'y a pas de performance qui s'effondre hors échantillon : il n'y en avait pas non plus dans l'échantillon. Seules les sleeves à Sharpe TRAIN positif seraient candidates à un overfit : S1 0,16 → −0,20 (rapport −1,25), S6 0,52 → 0,07 (rapport 0,13) ; elles se dégradent, ce qui est compatible avec du bruit (S6 est surtout du bêta actions).
2. **DSR de la pile < 0,001 pour 8 essais** (7 sleeves + la pile ; le plus grand DSR parmi les 8 séries vaut < 0,001, seuil 0,95), borne basse de l'IC 95 % du Sharpe VAL −6,31. Verdict `ECHEC`, TEST non ouvert.
3. **Choisi AVANT de voir VAL : tout.** Les 7 sleeves et leurs paramètres, les poids de la pile (∝ 1/vol TRAIN), la vol cible, les coûts, les gates et le nombre d'essais sont figés dans [`PREREGISTRATION.md`](PREREGISTRATION.md) avant le premier calcul ; aucune sélection par la performance, aucune sleeve retirée après coup (même la pire, S7). La seule modification venue après VAL (correction de l'horloge HistData, avenant 1) est déclarée comme telle plus bas.
<!-- /AUTO:OVERFIT -->

## Toutes les variantes

Rien n'est caché : les 7 sleeves et la pile, TRAIN et VAL, **y compris les échecs**. Il n'y a pas de grille de paramètres (le protocole l'interdit) : une variante est une sleeve pré-enregistrée, et la pile garde toutes les sleeves.

<!-- AUTO:VARIANTES -->
**Performance**

| Variante | Sharpe net TRAIN | Sharpe net VAL | Sharpe brut TRAIN | Sharpe brut VAL | Rend. net/an TRAIN | Rend. net/an VAL | Vol TRAIN | Vol VAL | Drawdown TRAIN | Drawdown VAL |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 Trend following | 0,16 | −0,20 | 0,23 | −0,12 | 1,7 % | −2,2 % | 10,8 % | 11,0 % | −30 % | −19 % |
| S2 Momentum devises | −0,46 | −0,82 | −0,35 | −0,71 | −4,9 % | −8,9 % | 10,6 % | 10,9 % | −40 % | −39 % |
| S3 Retournement devises | −0,31 | −0,49 | −0,02 | −0,15 | −3,2 % | −5,0 % | 10,2 % | 10,2 % | −40 % | −26 % |
| S4 Saisonnalité FX | −1,91 | −1,81 | −0,24 | 0,14 | −20,1 % | −19,0 % | 10,5 % | 10,5 % | −86 % | −56 % |
| S5 Fixing fin de mois | −0,47 | −0,49 | −0,19 | −0,15 | −5,0 % | −4,1 % | 10,5 % | 8,3 % | −37 % | −28 % |
| S6 Actions vol-gérées | 0,52 | 0,07 | 0,56 | 0,12 | 5,2 % | 0,7 % | 10,0 % | 10,1 % | −17 % | −15 % |
| S7 Momentum SPX intraj. | −15,60 | −12,34 | 0,03 | −1,29 | −190,9 % | −134,2 % | 12,2 % | 10,9 % | −100 % | −100 % |
| **PILE (7 sleeves)** | −6,48 | −5,30 | 0,01 | −0,70 | −64,8 % | −52,4 % | 10,0 % | 9,9 % | −100 % | −89 % |

**Activité, coûts et significativité**

| Variante | Calmar TRAIN | Calmar VAL | Trades TRAIN | Trades VAL | Taux de gain TRAIN | Taux de gain VAL | Rotation/an VAL | Coût/an TRAIN | Coût/an VAL | PSR(0) VAL | DSR VAL |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 Trend following | 0,06 | −0,12 | 61 250 | 32 332 | 51,3 % | 51,3 % | 34× | 0,7 % | 0,9 % | 0,341 | < 0,001 |
| S2 Momentum devises | −0,12 | −0,23 | 3 275 | 1 476 | 50,0 % | 48,6 % | 94× | 1,2 % | 1,2 % | 0,049 | < 0,001 |
| S3 Retournement devises | −0,08 | −0,20 | 3 635 | 1 648 | 48,8 % | 48,6 % | 268× | 3,0 % | 3,5 % | 0,158 | < 0,001 |
| S4 Saisonnalité FX | −0,23 | −0,34 | 27 200 | 12 444 | 44,2 % | 44,0 % | 2 221× | 17,6 % | 20,5 % | 0,000 | < 0,001 |
| S5 Fixing fin de mois | −0,14 | −0,15 | 784 | 366 | 42,9 % | 37,0 % | 474× | 3,0 % | 2,9 % | 0,159 | < 0,001 |
| S6 Actions vol-gérées | 0,31 | 0,04 | 654 | 336 | 53,8 % | 54,9 % | 5× | 0,5 % | 0,6 % | 0,553 | < 0,001 |
| S7 Momentum SPX intraj. | −1,91 | −1,35 | 3 722 | 1 926 | 8,7 % | 14,1 % | 1 010× | 191,3 % | 121,2 % | 0,000 | < 0,001 |
| **PILE (7 sleeves)** | −0,65 | −0,59 | 100 520 | 50 528 | 31,6 % | 35,8 % | 1 349× | 64,9 % | 45,5 % | 0,000 | < 0,001 |
<!-- /AUTO:VARIANTES -->

![Toutes les variantes : equity nette de chaque sleeve (gris) et de la pile (bleu)](figures/toutes_variantes.png)

**Comment lire ce graphique.** Chaque ligne grise est l'equity nette d'une sleeve (base 100, échelle logarithmique), la ligne bleue est la pile. À gauche de la ligne pointillée, TRAIN ; à droite, VAL. La plupart des sleeves dérivent vers le bas dans les deux périodes, S7 sort du cadre par le bas
(sa valeur finale est écrite en bas à gauche) ; seules S6 et S1 restent proches de 100. La pile suit les plus mauvaises, car ses poids (∝ 1/vol TRAIN) ne regardent jamais un Sharpe.

![Sharpe net TRAIN contre VAL pour chaque variante](figures/overfit_scatter.png)

**Comment lire ce graphique.** Un point par variante : Sharpe net TRAIN en abscisse, VAL en ordonnée (échelle symlog : linéaire entre −1 et 1, logarithmique au-delà, pour garder S7 et la pile visibles). Sur la diagonale, VAL = TRAIN. Un overfit se reconnaît à des points en bas à droite (beau en TRAIN, mauvais en VAL) ;
ici presque tous les points sont en bas à gauche, sur la diagonale : mauvais aux deux endroits. Les deux seules sleeves à Sharpe TRAIN positif (S6, S1) reculent en VAL.

## Tableau de bord interactif

Choisissez vous-même les conditions de départ (nombre de trades minimum, jours actifs, Sharpe TRAIN minimum, drawdown TRAIN maximum, fréquence, classe d'actifs) : seules les sleeves qui passent ces filtres sur **TRAIN** sont combinées (moyenne équipondérée),
et la courbe obtenue est affichée sur TRAIN puis VAL, avec ses métriques recalculées et un voyant « Overfit ? ». Essai instructif : mettre « Sharpe TRAIN min » à 0 ne laisse que S1 et S6, dont la combinaison paraît correcte en TRAIN puis recule en VAL, c'est l'overfit à l'œil.

- En ligne : <https://yassine-ek.github.io/alpha-research/>
- Ou ouvrir `docs/index.html` localement (les données sont dans `docs/data.js`, aucun serveur nécessaire ; sinon lancer `python -m http.server` dans `docs/`).
- Régénérer : `python scripts/exporter_dashboard.py` (lit `results/`, aucune donnée de marché requise).

La sélection n'utilise que TRAIN ; VAL est hors échantillon ; le TEST n'apparaît jamais.

## Pourquoi ce projet

Pour un éditeur de plateformes de trading (smartTrade) comme pour une équipe de trading systématique (Xrays Trading), la vraie question n'est pas « ce backtest gagne-t-il ? » mais « **qu'est-ce qui est vrai derrière** » : les coûts sont-ils réels, l'exécution est-elle décalée,
les paramètres ont-ils été choisis avant ou après avoir vu le résultat, combien d'essais ont été faits ? Ce dépôt est un cas pratique : un protocole qui interdit de se mentir (pré-enregistrement haché, test scellé, coûts réels, statistiques déflatées), appliqué à sept stratégies publiées,
et un résultat négatif publié sans maquillage. C'est aussi un argument de produit : des coûts d'exécution plus bas rendent *testables* des signaux rapides (voir la sensibilité aux coûts), mais ne créent pas d'edge.

## La question

Peut-on atteindre un **Sharpe net > 2 hors échantillon** en empilant 7 stratégies simples, tirées de la littérature,
aux **paramètres fixés d'avance**, sur nos données réelles (58 actifs liquides FX/indices/métaux/pétrole, coûts réels par actif),
**sans aucune sélection par la performance passée** ?

L'attente écrite avant tout calcul (voir le pré-enregistrement) était honnête : probablement non. Sous indépendance il faut environ 16 sleeves de Sharpe 0,5
pour atteindre 2, et les sleeves de la littérature sont corrélées, plus ou moins sensibles aux coûts. Le livrable est la **mesure**, pas un nombre flatteur.

## Méthode : le protocole figé avant le premier calcul

- Pré-enregistrement : [`PREREGISTRATION.md`](PREREGISTRATION.md), empreinte SHA-256
  `f6007427c1a455525c3e863e680e02aac4775e432783abc1ea6247b656182250` (commité seul, avant tout code).
  Une seule modification depuis : l'AVENANT 1 du 13/10 (correction de l'horloge HistData, écrite
  APRÈS la lecture de VAL et signalée comme telle) ; l'empreinte ci-dessus est celle de la version
  initiale (commit `9853f2b`).
- **Données** : barres 1 h (`<HISTDATA_DIR>/processed/univers`) pour les sleeves quotidiennes (instantané 11h00 EST, fixing global retenu par PIVOT-0) ;
  minutes HistData pour les sleeves intrajournalières (l'horloge des fichiers suit l'heure d'été : ce n'est PAS de l'EST fixe, voir « Relecture adversariale du 13/10 »). Actifs morts exclus.
- **Coûts réels** par jambe depuis [`data/frais_editable.csv`](data/frais_editable.csv) (indices à 12 bps). Coût = bps × |Δ position| ; une ouverture puis une fermeture = deux jambes.
- **Exécution décalée** : sleeves quotidiennes, décision à l'instantané J, exécution à J+1, gain J+1 → J+2 (un jour plein de décalage, plus strict que T+1 min) ;
  intrajournalier, entrée à l'open de la minute qui suit le signal, sortie à l'open de la minute qui suit la fin de fenêtre.
- **Découpage** : TRAIN 2010-2018 (préchauffage et calibration des échelles), VAL 2019-2022 (évaluation), TEST 2023+ **scellé**.
- **Vol cible** : chaque sleeve vise 10 % de volatilité annuelle ex ante (covariance EWMA, demi-vie 36 jours, passé seulement).
- **Pile** : les 7 sleeves toutes gardées, poids ∝ 1 / vol réalisée sur TRAIN, puis échelle unique à 10 % de vol sur TRAIN. Aucun poids ne dépend d'un Sharpe.
- **Statistiques** : IC 95 % du Sharpe par bootstrap stationnaire (blocs moyens de 20 jours, 5 000 tirages), t de Newey-West + correction de Holm sur les 7 sleeves,
  PSR(0) et Deflated Sharpe Ratio avec N = 8 essais (7 sleeves + la pile).
- **Gates sur la pile** : G1 Sharpe net VAL ≥ 1 ; G2 borne basse de l'IC > 0 ; G3 DSR ≥ 0,95 ; G4 TEST (lecture unique) Sharpe > 0 et ≥ 0,5 × Sharpe VAL. Objectif utilisateur, non bloquant : Sharpe ≥ 2.

| # | Sleeve | Source | Règle figée (résumé) |
|---|---|---|---|
| S1 | Trend following EWMAC | Carver 2015, Moskowitz-Ooi-Pedersen 2012 | 3 vitesses (16,64), (32,128), (64,256), prévision normalisée, tampon 10 %, 58 actifs |
| S2 | Momentum cross-sectionnel devises | Menkhoff et al. 2012 | rendement 63 j, long 3 / short 3, vendredi |
| S3 | Retournement court terme devises | littérature reversal FX | rendement 5 j, long les 3 pires, vendredi |
| S4 | Saisonnalité intrajournalière | Breedon-Ranaldo 2013 | vendre la devise étrangère pendant sa session (Londres 08h-14h, Tokyo 09h-15h) |
| S5 | Fixing de fin de mois | Melvin-Prins 2015 | dernier jour ouvré, 06h→10h EST, sens selon la surperformance SPX vs indice étranger |
| S6 | Actions gérées par la vol | Moreira-Muir 2017 | 7 indices, long seul, poids = c / variance du mois précédent, levier ≤ 2 |
| S7 | Momentum intrajournalier SPX | Gao-Han-Li-Zhou 2018 | signal veille 16h→10h ET, entrée 15h30, sortie 16h00 ET |

Toutes les interprétations prises quand une règle était ambiguë (toujours dans le sens le plus conservateur) sont dans
[`results/notes_implementation.md`](results/notes_implementation.md). Le prereg lui-même n'a pas été touché.

### Intuition et formules (pour lire les tableaux)

- **Sharpe annualisé** : `SR = moyenne(r_j) / écart-type(r_j) × √252`, sur les rendements quotidiens **nets de frais**. Intuition : combien de rendement par unité de risque, ramené à l'année.
  Sur 4 ans l'erreur-type d'un Sharpe est d'environ 0,5 : un Sharpe de 0,5 n'est donc pas distinguable de zéro, d'où les intervalles de confiance.
- **Coût** : `coût_t = Σ_actifs bps_actif × 10⁻⁴ × |Δ position_actif,t|`, et `rendement net = rendement brut − coût`. Un aller-retour intrajournalier paie deux jambes.
- **Cible de volatilité** : chaque sleeve est mise à l'échelle pour viser 10 % de vol annuelle ex ante (covariance EWMA, passé seulement). La pile pondère chaque sleeve par `1 / vol réalisée sur TRAIN`, puis applique une échelle unique ; aucun poids ne dépend d'un Sharpe.
- **PSR et DSR** (Bailey et López de Prado) : `PSR(SR*) = Φ( (SR − SR*)·√(n−1) / √(1 − γ₃·SR + (γ₄−1)/4·SR²) )`, la probabilité que le vrai Sharpe dépasse `SR*` en tenant compte de l'asymétrie `γ₃` et de l'aplatissement `γ₄`.
  Le **DSR** est le PSR contre `SR*` = le meilleur Sharpe qu'on obtiendrait par hasard en testant N stratégies (ici N = 8). Intuition : plus on essaie de variantes, plus le « meilleur » résultat est gonflé par la chance.
- **Diversification** : pour N sleeves de même Sharpe `s` et de corrélation moyenne `ρ`, `SR_pile = s·√N / √(1 + (N−1)·ρ)`. Elle multiplie un Sharpe existant, elle n'en crée pas.

## Résultats détaillés (TRAIN / VAL, TEST scellé)

Chiffres lus dans [`results/train_val.json`](results/train_val.json) (VAL = 1044 jours ; Sharpe net annualisé, coûts réels déduits).

| Série | Début actif | Sharpe net TRAIN | Sharpe net VAL | IC 95 % bootstrap VAL | Sharpe brut VAL | t NW VAL | p Holm | PSR(0) | DSR (N=8) |
|---|---|---|---|---|---|---|---|---|---|
| S1 Trend following EWMAC | 2010-12-29 | 0,16 | −0,20 | [−1,02 ; 0,64] | −0,12 | −0,41 | 1,000 | 0,341 | < 0,001 |
| S2 Momentum devises | 2010-04-06 | −0,46 | −0,82 | [−1,78 ; 0,19] | −0,71 | −1,59 | 0,555 | 0,049 | < 0,001 |
| S3 Retournement devises | 2010-04-06 | −0,31 | −0,49 | [−1,34 ; 0,40] | −0,15 | −1,02 | 1,000 | 0,158 | < 0,001 |
| S4 Saisonnalité FX | 2010-04-01 | −1,91 | −1,81 | [−2,85 ; −0,87] | 0,14 | −3,75 | 0,001 | 0,000 | < 0,001 |
| S5 Fixing fin de mois | 2010-11-30 | −0,47 | −0,49 | [−1,52 ; 0,46] | −0,15 | −1,01 | 1,000 | 0,159 | < 0,001 |
| S6 Actions vol-gérées | 2010-12-02 | 0,52 | 0,07 | [−0,80 ; 1,02] | 0,12 | 0,14 | 1,000 | 0,553 | < 0,001 |
| S7 Momentum intrajournalier SPX | 2011-02-24 | −15,60 | −12,34 | [−15,18 ; −9,74] | −1,29 | −19,49 | 0,000 | 0,000 | < 0,001 |
| **PILE (7 sleeves)** | 2011-02-24 | −6,48 | −5,30 | [−6,31 ; −4,30] | −0,70 | −10,20 | n/a | 0,000 | < 0,001 |

| Série | Rend. net/an VAL | Vol/an VAL | DD max VAL | Rotation/an VAL | Coût/an VAL | Sharpe brut TRAIN | Rend. net/an TRAIN | Coût/an TRAIN |
|---|---|---|---|---|---|---|---|---|
| S1 Trend following EWMAC | −2,2 % | 11,0 % | −19 % | 34x | 0,9 % | 0,23 | 1,7 % | 0,7 % |
| S2 Momentum devises | −8,9 % | 10,9 % | −39 % | 94x | 1,2 % | −0,35 | −4,9 % | 1,2 % |
| S3 Retournement devises | −5,0 % | 10,2 % | −26 % | 268x | 3,5 % | −0,02 | −3,2 % | 3,0 % |
| S4 Saisonnalité FX | −19,0 % | 10,5 % | −56 % | 2221x | 20,5 % | −0,24 | −20,1 % | 17,6 % |
| S5 Fixing fin de mois | −4,1 % | 8,3 % | −28 % | 474x | 2,9 % | −0,19 | −5,0 % | 3,0 % |
| S6 Actions vol-gérées | 0,7 % | 10,1 % | −15 % | 5x | 0,6 % | 0,56 | 5,2 % | 0,5 % |
| S7 Momentum intrajournalier SPX | −134,2 % | 10,9 % | −100 % | 1010x | 121,2 % | 0,03 | −190,9 % | 191,3 % |
| **PILE (7 sleeves)** | −52,4 % | 9,9 % | −89 % | 1349x | 45,5 % | 0,01 | −64,8 % | 64,9 % |

Poids de la pile et contribution de chaque sleeve (purement descriptif) :

| Sleeve | Poids de la pile (∝ 1/vol TRAIN) | Contribution annuelle au rendement net de la pile, VAL |
|---|---|---|
| S1 Trend following EWMAC | 0,140 | −0,7 % |
| S2 Momentum devises | 0,144 | −3,0 % |
| S3 Retournement devises | 0,150 | −1,8 % |
| S4 Saisonnalité FX | 0,145 | −6,5 % |
| S5 Fixing fin de mois | 0,145 | −1,4 % |
| S6 Actions vol-gérées | 0,152 | 0,2 % |
| S7 Momentum intrajournalier SPX | 0,125 | −39,2 % |

![PnL cumulé par sleeve et pile, net et brut](figures/pnl_cumule.png)

**Comment lire ce graphique.** En haut, le PnL cumulé net de frais (somme des rendements quotidiens, en fraction du capital) de chaque sleeve et de la pile ; en bas, le même brut, avant frais. La ligne pointillée sépare TRAIN (gauche) de VAL (droite).
L'écart entre les deux panneaux, c'est le coût : il est faible pour les sleeves lentes (S1, S6) et dévorant pour les rapides (S4, S7). Les séries qui sortent du cadre sont rognées, leur valeur finale est dans la légende.

![Sharpe net VAL avec intervalle de confiance à 95 %](figures/sharpe_val_ic.png)

**Comment lire ce graphique.** Une barre par série : Sharpe net sur VAL, avec son intervalle de confiance à 95 % (bootstrap) ; le losange blanc est le Sharpe brut, avant frais. La ligne verte est le seuil de la gate G1 (Sharpe 1).
Un intervalle qui contient zéro veut dire « indistinguable de zéro » ; ici aucune barre n'approche la ligne verte, et les losanges (brut) sont déjà au plus à 0,14.

![Matrices de corrélation des rendements nets, TRAIN et VAL](figures/correlations.png)

**Comment lire ce graphique.** Corrélation entre les rendements nets quotidiens des sleeves, TRAIN à gauche, VAL à droite (rouge = positive, bleu = négative). Des sleeves peu corrélées se diversifient bien, mais à condition d'avoir chacune un edge ; la seule corrélation notable est S1-S2.

![Coût annuel par sleeve, TRAIN et VAL](figures/cout_annuel.png)

**Comment lire ce graphique.** Coût annuel en pourcentage du capital (échelle logarithmique). La ligne rouge est la volatilité cible de chaque sleeve (10 %) : une sleeve dont le coût dépasse cette ligne paie plus en frais qu'elle ne prend de risque. S4 et S7 sont bien au-dessus.

### Gates et état du TEST

| Gate | Critère | Valeur | Résultat |
|---|---|---|---|
| G1 | Sharpe net VAL de la pile ≥ 1,0 | −5,30 | ÉCHOUE |
| G2 | borne basse IC 95 % bootstrap du Sharpe VAL > 0 | −6,31 | ÉCHOUE |
| G3 | DSR VAL (N = 8) ≥ 0,95 | < 0,001 | ÉCHOUE |
| G4 | TEST : Sharpe net > 0 et ≥ 0,5 × Sharpe VAL | non évalué | TEST scellé (G1 et G2 échouent) |

**Verdict : `ECHEC`**, TEST non ouvert (`scelle_G1_ou_G2_en_echec`). Détail dans [`results/verdict_alpha.json`](results/verdict_alpha.json).
Le TEST n'est ouvert que si G1 et G2 passent ; elles échouent, donc il reste scellé. `scripts/ouvrir_test.py` est écrit mais n'a **jamais été exécuté**.

## Lecture honnête

- **La pile est loin des gates** : Sharpe net VAL −5,30 (IC 95 % [−6,31 ; −4,30]), Sharpe brut VAL −0,70.
  Même avant coûts, la pile ne gagne pas d'argent en VAL : le problème n'est pas uniquement les coûts.
- **Une sleeve écrase tout** : S7 (momentum intrajournalier SPX) a un gain brut moyen par trade nul ou négatif (≈ 0 bp en TRAIN, −1,9 bp en VAL), face à 2 × 12 bps de coût
  multipliés par le levier qu'impose une vol cible de 10 % sur une demi-heure d'exposition. Son coût annuel en VAL est de 121 % du capital pour une vol de 10 %.
  La pile à poids ∝ 1/vol lui donne le même poids qu'aux autres, donc elle porte la pile à −5,30.
  Retirer S7 « pour voir » est précisément ce que le prereg interdit (retirer une sleeve après avoir vu VAL) : ce serait un nouveau pré-enregistrement avec N cumulé.
- **S4 : un signal brut quasi nul que les coûts transforment en perte nette** : Sharpe brut VAL 0,14 (non distinguable de zéro ; 0,58 avant la correction de l'horloge,
  voir « Relecture adversariale »), Sharpe net VAL −1,81. Le gain brut par trade est inférieur au coût aller-retour sur les 6 paires (VAL : +0,40 bp pour EURUSD contre 0,97 bp de coût).
- **Les sleeves quotidiennes (S1, S2, S3, S6) sont indiscernables de zéro ou négatives en VAL** : aucune ne passe Holm. S2 (momentum devises) est négative aussi en TRAIN ;
  une vérification indépendante (spread hebdomadaire équipondéré, sans notre moteur) donne le même signe, ce n'est donc pas un bug.
  S6 est la meilleure en TRAIN (Sharpe net 0,52) mais son Sharpe VAL (0,07) ne se distingue pas de zéro.
- **Corrélations faibles, sauf S1-S2** (0,58 en VAL) : l'idée « sleeves décorrélées » tient (corrélation moyenne VAL 0,026), mais décorréler des sleeves sans edge
  ne produit pas d'edge. La diversification multiplie un Sharpe moyen, elle n'en crée pas.
- **Biais corrigés par construction** : aucun fill au prix du signal (un jour plein de décalage, une minute en intrajournalier), coûts réels dès le premier calcul, pas de sélection (paramètres figés, N = 8 compté dans le DSR),
  Sharpe toujours accompagné d'un IC bootstrap, test de causalité de bout en bout (ajouter du futur ne change aucun rendement passé, vérifié à égalité exacte).

## Pourquoi Sharpe > 2 n'est pas atteint

Pour N sleeves de même Sharpe `s` et de corrélation moyenne `ρ`, le Sharpe de la pile équipondérée vaut `s·√N / √(1 + (N−1)·ρ)`.

- Il faudrait **0,81 de Sharpe net par sleeve** (N = 7, ρ̄ = 0,026 observé en VAL) ; le meilleur Sharpe net VAL est celui de S6 (0,07).
- À Sharpe individuel 0,3 il faudrait 45 sleeves indépendantes ; à 0,5, 16.
- Les coûts réels absorbent tout ce qui tourne vite : S3 (268x de rotation par an), S4 (2221x), S7 (1010x).
  Les sleeves lentes (S1, S6) ne coûtent presque rien, mais ne rapportent presque rien non plus.
- Sur 4 ans de VAL, l'erreur standard d'un Sharpe annualisé est d'environ 0,5 (IC 95 % d'environ ±1) : un Sharpe de 0,5 sur une sleeve n'est pas distinguable de zéro, d'où l'intérêt du bootstrap, de Holm et du DSR.

## Relecture adversariale du 13/10

Une relecture indépendante a trouvé **un défaut majeur, corrigé** : le prereg (§2, §4) et le code supposaient les minutes HistData en EST fixe (UTC−5). C'est faux : l'horloge des fichiers
suit l'heure d'été (ouverture hebdomadaire du FX à 17h00 toute l'année, pic NFP à 08h30 été comme hiver ; depuis 2019 elle suit le DST européen, d'où des semaines de décalage en mars et en novembre).
La règle corrigée prédit 99,7 % des 667 ouvertures de semaine EURUSD 2010-2022, contre 36 % pour l'EST fixe. Conséquence : les fenêtres de S4 (Londres, Tokyo) et de S7 (New York) étaient lues **une heure trop tôt pendant environ sept mois par an**.
Aucun paramètre n'a changé, seule la conversion heure locale → horloge des fichiers (`alpha/donnees.py`), avec tests de régression (`tests/test_horloge_donnees.py`). Effet : S4 Sharpe brut VAL 0,58 → 0,14 (net −1,41 → −1,81),
S7 brut −0,74 → −1,29 (net −12,47 → −12,34), pile −5,32 → −5,30 ; S1, S2, S3, S5 et S6 sont inchangées au bit près. Verdict `ECHEC` inchangé, TEST toujours scellé.
Détail, preuves et points mineurs non corrigés : [`results/notes_implementation.md`](results/notes_implementation.md), section « Corrections après relecture du 13/10 ».

## EXPLORATOIRE — non pré-enregistré, ne modifie pas le verdict

Sharpe net VAL 2019-2022 quand on multiplie les coûts réels du fichier par 0, 0,1, 0,25, 0,5 ou 1 (la pile est reconstruite à chaque fois par la procédure du prereg), et coût de rentabilité de chaque sleeve
(coût par jambe qui annule son rendement net moyen VAL). Calculé par [`scripts/sensibilite_couts.py`](scripts/sensibilite_couts.py), chiffres dans
[`results/sensibilite_couts_exploratoire.json`](results/sensibilite_couts_exploratoire.json), courbes dans [`figures/sensibilite_couts.png`](figures/sensibilite_couts.png). TRAIN et VAL seulement, TEST jamais chargé.

| Série | ×0 (brut) | ×0,1 | ×0,25 | ×0,5 | ×1 (coûts réels) | Coût moyen actuel (bps/jambe) | Coût de rentabilité VAL (bps/jambe) |
|---|---|---|---|---|---|---|---|
| S1 Trend following | −0,12 | −0,12 | −0,14 | −0,16 | −0,20 | 2,81 | jamais (brut VAL ≤ 0) |
| S2 Momentum devises | −0,71 | −0,72 | −0,73 | −0,76 | −0,82 | 1,27 | jamais (brut VAL ≤ 0) |
| S3 Retournement devises | −0,15 | −0,19 | −0,24 | −0,32 | −0,49 | 1,30 | jamais (brut VAL ≤ 0) |
| S4 Saisonnalité FX | 0,14 | −0,05 | −0,35 | −0,84 | −1,81 | 0,92 | 0,07 |
| S5 Fixing fin de mois | −0,15 | −0,18 | −0,23 | −0,32 | −0,49 | 0,60 | jamais (brut VAL ≤ 0) |
| S6 Actions vol-gérées | 0,12 | 0,12 | 0,11 | 0,09 | 0,07 | 12,00 | 25,27 |
| S7 Momentum SPX intrajournalier | −1,29 | −2,50 | −4,28 | −7,15 | −12,34 | 12,00 | jamais (brut VAL ≤ 0) |
| **PILE** | −0,75 | −1,27 | −2,04 | −3,25 | −5,30 | 3,38 | jamais (brut VAL ≤ 0) |

**Lecture.** (1) Même à coût nul, aucune sleeve n'atteint un Sharpe brut VAL de 0,15 et la pile reste à −0,75 : le goulot est d'abord l'edge brut, pas seulement les coûts.
(2) Les coûts ne décident que pour les sleeves rapides : S4 passe de −1,81 à −0,35 (×0,25) puis −0,05 (×0,1), mais son seuil de rentabilité (0,07 bp par jambe) est environ 14 fois sous le coût moyen du fichier (0,92 bp), pour un Sharpe brut de 0,14 non distinguable de zéro.
(3) S6, lente (5x de rotation par an), reste rentable jusqu'à 25 bps par jambe (12 bps aujourd'hui) : des coûts institutionnels la changent à peine (0,07 → 0,12).
(4) Pour un éditeur de plateformes FX comme smartTrade, dont les clients ont des coûts institutionnels (ici supposés entre ×0,1 et ×0,25 du fichier, hypothèse à confirmer avec les coûts réels d'un client), l'argument est le suivant : une exécution moins chère rend
*testables* des sleeves à forte rotation (S3, S4, S5 remontent de −0,5 / −1,8 / −0,5 à environ −0,2 / −0,05 / −0,2 à ×0,1), mais elle ne crée pas d'edge : seul un signal brut positif devient exploitable, et aucune des 7 sleeves n'en montre un sur 2019-2022.

![Sharpe net VAL selon le multiple des coûts réels](figures/sensibilite_couts.png)

**Comment lire ce graphique.** Pour chaque série, le Sharpe net VAL quand on multiplie les coûts réels par 0, 0,1, 0,25, 0,5 ou 1 (la pile est reconstruite à chaque fois). Une courbe qui monte vite vers la gauche est sensible aux coûts (sleeves rapides) ;
une courbe plate (S1, S6) ne l'est pas. Même à coût nul (point le plus à gauche), presque aucune courbe n'atteint un Sharpe positif : le goulot est l'edge brut.

## Approfondissement

> **EXPLORATOIRE — non pré-enregistré, ne modifie pas le verdict `ECHEC`.** Analyse a posteriori sur TRAIN (≤ 2018) et VAL (2019-2022) : le TEST reste scellé (lecteur 1 h strict qui s'arrête avant 2023,
> `scripts/ouvrir_test.py` jamais lancé), aucun paramètre des sleeves n'est touché, `PREREGISTRATION.md` n'est pas modifié (pas de nouvel avenant). Question directrice : **pourquoi aucune de ces 7 stratégies connues ne marche ici, et que faudrait-il de
> vrai pour un Sharpe net > 2 ?** Code : sous-paquet `alpha/approfondissement/` (`diagnostics.py`, `theorie.py`, `chargement.py`, `figures.py`, hors de `alpha/*.py` pour que l'empreinte `code_sha256` du code officiel ne bouge pas) ; chiffres : [`results/approfondissement.json`](results/approfondissement.json) ;
> carnet (un chapitre par question) : [`notebooks/approfondissement.ipynb`](notebooks/approfondissement.ipynb).

### Q1 — Combien d'IC, sur combien de paris, pour un IR de 2 ? (loi fondamentale de la gestion active)

IR ≈ TC × IC × √BR (Grinold ; Clarke-de Silva-Thorley). En VAL : TC moyen 0,94, breadth de la pile ≈ 1 792 paris indépendants/an (S4 988, S7 252, S3 277, S2 138, S1 91, S5 24, S6 23), IC par sleeve de −0,132 (S5) à +0,004 (S3).
La loi suit le Sharpe brut réalisé : corrélation 0,76 sur 14 couples (sleeve, période), écart prédit − réalisé |z| ≤ 1,1 (S7 VAL : IR prédit −1,11 pour −1,29 réalisé ; S2 VAL : −0,44 pour −0,71).
IC nécessaire pour un IR de 2 avec la breadth observée : 0,235 (S1), 0,192 (S2), 0,137 (S3), 0,064 (S4), 0,126 (S7) ; pour la pile, 0,059 sur **chaque** sleeve, contre un IC moyen observé de −0,047.
Avec l'IC de S3 (+0,004, le seul positif des sleeves quotidiennes) il faudrait 1 072 fois sa breadth. Ce qui manque est de l'IC, pas de la breadth. ![Loi fondamentale : IR prédit et IC nécessaire](figures/appro_q1_grinold.png)

**Comment lire ce graphique.** À gauche, le Sharpe brut réalisé en fonction de celui que prédit la loi fondamentale `IR ≈ TC × IC × √breadth` (cercles TRAIN, carrés VAL) : les points suivent la diagonale, donc la loi décrit bien nos sleeves. À droite, l'IC observé en VAL (barre colorée, avec ± 1,96 erreur-type) face à l'IC qu'il faudrait pour un IR de 2 (barre grise) : l'écart est dans l'IC, pas dans le nombre de paris.

### Q2 — À quelle vitesse le signal s'éteint-il, et quel horizon le coût autorise-t-il ? (décroissance du signal)

IC de S2 (momentum 63 j) négatif à tous les horizons sur TRAIN+VAL (−0,006 à 1 j, −0,109 à 60 j, t de Newey-West −3,2) : le signal est inversé. IC de S3 (retournement 5 j) négatif à 2-5 j puis positif à 10-60 j (+0,041 à 60 j, t = 2,8), alors que S3 est tenue 5 jours :
re-signalisée tous les 60 j, la règle donnerait +0,22 bps/jour (TRAIN) et +0,32 bps/jour (VAL) nets de l'exposition brute. Constat **a posteriori** (6 horizons × 4 sleeves lus) : une piste pour un nouveau pré-enregistrement, pas un résultat.
Demi-vie du signal : S1 65 j, S2 30 j, S3 2 j, S6 58 j ; celle de l'IC n'est définie que pour 2 couples sur 8 (IC le plus souvent ≤ 0). Horizon optimal sous coût : 1 − (1+u)e^(−u) = C/A avec u = h/τ (gain marginal = rendement net moyen), vérifié contre une grille dans les tests.
Intrajournalier : gain brut maximal de S4 0,39 bps/trade pour 1,96 bps de coût aller-retour ; S7 jamais positif (au mieux −0,05 bps pour 24 bps). ![Décroissance du signal et horizon sous coût](figures/appro_q2_decroissance.png)

**Comment lire ce graphique.** En haut à gauche, l'IC cumulé selon l'horizon h : au-dessus de zéro, le signal prédit encore ; au-dessous, il est inversé (S2). En haut à droite, le rendement net par jour selon l'horizon de re-signalisation : on cherche le sommet, qui dit combien de temps tenir une position avant que les coûts n'écrasent le gain. Les panneaux du bas comparent, pour S4 et S7, le gain brut par trade (courbes) au coût aller-retour (pointillé rouge).

### Q3 — Que peut-on conclure de 4 ans de VAL ? (puissance statistique)

Erreur-type du Sharpe sur 4,1 ans : 0,49 (Lo 2002). Plus petit Sharpe vrai détecté avec 80 % de puissance : 1,22 (test unilatéral 5 %), 1,62 avec Bonferroni sur 7 sleeves ; il faut 25 ans pour confirmer un vrai Sharpe de 0,5 et 99 ans pour 0,25.
Probabilité qu'un vrai Sharpe de 0,5 affiche un Sharpe VAL au plus égal à l'observé (bootstrap) : S6 17 % (non écartée), S1 4,5 % (7,7 % en analytique : limite), S5 1,9 %, S3 1,0 %, S2 0,2 %, S4 et S7 ≈ 0.
Un vrai Sharpe de 0,25 n'est écarté (P < 5 %) que pour S2, S4 et S7 : absence de preuve n'est pas preuve d'absence. ![Puissance statistique de 4 ans de VAL](figures/appro_q3_puissance.png)

**Comment lire ce graphique.** À gauche, le plus petit Sharpe vrai qu'on peut détecter selon la durée de l'historique : la ligne verticale rouge est notre VAL (4,1 ans), loin au-dessous du Sharpe qu'on voudrait confirmer. À droite, la distribution du Sharpe estimé si le vrai Sharpe valait 0,5 (bleu) ou 0 (gris) : les Sharpe observés des sleeves y sont placés pour voir s'ils sont compatibles avec un vrai Sharpe de 0,5.

### Q4 — Que vaut un Sharpe trouvé après N essais ? (tests multiples)

Sharpe maximal attendu sans aucun edge (Bailey-López de Prado, écart-type 0,49) : 0,72 pour N = 8 (simulation 0,71) ; 1,29 pour N = 134 (simulation 1,29). Nombres d'essais cités dans `docs/idees/*_verdict.json` : 9 (Étape 3, max attendu 0,75), 6 (PIVOT-1 GLOBAL, 0,64), 12 (PIVOT-1b, 0,82),
39 (Route A matrice, 1,07), 50 (FX-pur v2, 1,12), 134 (PIVOT-4, plancher déclaré « pas un plafond », 1,29) ; le projet ne tient pas de compteur cumulé unique. Sur la durée de VAL, le hasard fabrique un Sharpe de 1 après 28 essais et de 2 après 24 121 ;
selon la durée du backtest, un Sharpe de 2 sort du hasard après 26 essais (1 an), 243 (2 ans), 17 845 (4 ans), 7,3·10⁷ (8 ans). Le SR0 du prereg (6,23) est tiré par la variance de S7 ; le seuil théorique est 0,72 : le verdict ne change pas.
Un « Sharpe > 2 » issu d'une recherche répétée ne vaut quelque chose qu'après déflation par le N réel. ![Sharpe maximal attendu sans aucun edge](figures/appro_q4_tests_multiples.png)

**Comment lire ce graphique.** À gauche, le meilleur Sharpe qu'on obtient par pur hasard en testant N variantes (courbes théoriques, points = simulations) : il monte avec N ; la ligne rouge est le Sharpe 2. À droite, le nombre d'essais qu'il faut pour qu'un Sharpe de 2 sorte du hasard, selon la durée du backtest : un « Sharpe 2 » trouvé après beaucoup d'essais ne vaut rien sans déflation.

### Q5 — Pourquoi chaque sleeve échoue-t-elle ? (anatomie de l'échec)

Aucune sleeve n'a un Sharpe brut ≥ 0,30 sur TRAIN et VAL à la fois (meilleur brut VAL : 0,14). Les Sharpe annuels de S1, S2, S3, S5 et S6 sont compatibles avec un Sharpe constant (p de constance ≥ 0,43) : pas d'effet de régime, un edge nul ou négatif à toute époque.
S6 est surtout du bêta actions (corrélation 0,76 au facteur « 8 indices » en VAL, 0,84 en TRAIN). Règle de décision (explicite, écrite avant lecture du tableau) et résultat :

| Série | Sharpe brut TRAIN / VAL | Sharpe net VAL | Perte de Sharpe due aux coûts (VAL) | p de constance | Cause principale |
|---|---|---|---|---|---|
| S1 | 0,23 / −0,12 | −0,20 | 0,09 | 0,60 | pas d'alpha brut |
| S2 | −0,35 / −0,71 | −0,82 | 0,11 | 0,80 | pas d'alpha brut (signal inversé) |
| S3 | −0,02 / −0,15 | −0,49 | 0,34 | 0,90 | pas d'alpha brut |
| S4 | −0,24 / 0,14 | −1,81 | 1,96 | 0,89 | pas d'alpha brut + coût amplificateur |
| S5 | −0,19 / −0,15 | −0,49 | 0,35 | 0,61 | pas d'alpha brut |
| S6 | 0,56 / 0,12 | 0,07 | 0,06 | 0,43 | régime (bêta actions) |
| S7 | 0,03 / −1,29 | −12,34 | 11,05 | 0,00 | pas d'alpha brut + coût amplificateur |
| PILE | 0,01 / −0,70 | −5,30 | 4,60 | 0,00 | pas d'alpha brut + coût amplificateur |

![Sharpe glissant des sleeves](figures/appro_q5_sharpe_glissant.png)

**Comment lire ce graphique.** Sharpe glissant de chaque sleeve dans le temps : une courbe qui reste autour d'une valeur constante (souvent proche de zéro ou négative) dit qu'il n'y a pas de régime favorable, juste un edge absent à toute époque.

![Sharpe brut par régime de volatilité et exposition au facteur de marché](figures/appro_q5_regimes_facteur.png)

**Comment lire ce graphique.** À gauche, le Sharpe brut par régime de volatilité (terciles du facteur indices) : un edge qui n'existerait que dans un régime se verrait ici. À droite, la corrélation de chaque sleeve avec le facteur de marché : S6 y est très exposée (c'est du bêta actions), les autres peu.

### Q6 — La diversification peut-elle suffire ?

SR_pile = s √(N / (1 + (N−1) ρ̄)). Avec la corrélation moyenne observée en VAL (ρ̄ = 0,026), il faut 27 sleeves de Sharpe net 0,5 (16 si indépendantes) pour atteindre 2, ou 0,81 de Sharpe net par sleeve avec 7 sleeves ; le meilleur Sharpe net VAL ici est 0,07 (S6).
Le plafond de 0,5 de Sharpe individuel est 0,5/√ρ̄ = 3,1 ; à ρ̄ = 0,10 la pile plafonne à 1,6 et n'atteint jamais 2. Contrôle : la formule à risque égal avec les Sharpe réels prédit −5,66 pour la pile, réalisée −5,30.
La diversification multiplie un Sharpe moyen, elle n'en crée pas. ![Diversification et Sharpe de la pile](figures/appro_q6_diversification.png)

**Comment lire ce graphique.** Sharpe de la pile selon le nombre de sleeves N, pour un Sharpe individuel s et une corrélation ρ donnés (courbes). La courbe qui plafonne montre qu'à ρ non nul, ajouter des sleeves ne suffit pas ; il faut surtout des sleeves qui ont chacune un Sharpe net réel.

### Q7 (bonus) — Quelle capacité pour S1 et S6 ? (impact racine carrée)

Impact = Y σ √(Q/ADV) par ordre ; hypothèses d'ordre de grandeur **non sourcées** (ADV 1e10 $/jour par paire FX, 5e10 par indice, Y = 1 ; pas de volume dans les fichiers). À 1 Md$ l'impact annuel vaut 0,33 % (S1) et 0,22 % (S6) en VAL : la capacité n'est pas le goulot.
Capacité (rendement net avant impact = impact) : S1 TRAIN 44 Md$, S1 VAL 0 (brut négatif), S6 VAL 9 Md$ ; 1 215 Md$ pour S6 TRAIN est une extrapolation hors du domaine de validité de la loi. Capacité ∝ ADV supposé et ∝ (rendement net avant impact)².
![Capacité (impact racine carrée)](figures/appro_q7_capacite.png)

**Comment lire ce graphique.** Rendement net annuel après impact selon le capital géré, pour S1 et S6 (TRAIN en trait plein, VAL en pointillé) ; le point où la courbe passe sous zéro est la capacité. L'axe des capitaux est en dollars et les hypothèses de volume sont des ordres de grandeur non sourcés : lecture qualitative uniquement.

### Ce qu'il faudrait pour un Sharpe > 2

1. **Loi fondamentale** : pour IR = 2 avec ~1 792 paris indépendants/an, un IC de 0,059 sur chaque sleeve (« très bon » en gestion active) ; observé −0,047.
2. **Puissance** : 4 ans de VAL ne détectent qu'un Sharpe ≥ 1,22 (1,62 avec 7 tests) ; confirmer un vrai Sharpe de 0,5 prend 25 ans.
3. **Diversification** : 27 sleeves de Sharpe net réel 0,5 à ρ̄ = 0,026 (ou 0,81 par sleeve avec 7) ; le meilleur Sharpe net VAL ici est 0,07.
4. **Tests multiples** : sur 4,1 ans le hasard fabrique un Sharpe de 2 après 24 121 essais et de 1 après 28 ; un vrai résultat doit survivre à la déflation par le N réel et à un TEST lu une seule fois.
5. **Ce qui est vrai ici** : le goulot est l'edge brut (Sharpe brut VAL ≤ 0,14 pour toutes les sleeves, pile −0,70), ni les coûts, ni la capacité, ni le régime : baisser les coûts ne crée pas d'edge.

*Limites de l'approfondissement* : constats a posteriori (nombreuses lectures : horizons, périodes, sleeves), à ne traiter que comme hypothèses d'un NOUVEAU pré-enregistrement avec N d'essais cumulé ; breadth et TC sont des estimateurs fragiles ; volumes ADV supposés ;
la SE de Lo suppose des rendements iid (le bootstrap par blocs et la SE de Mertens donnent le même ordre de grandeur) ; l'IC « poolé » normalise par des rangs globaux (outil d'évaluation, ses entrées restent causales, voir `tests/test_approfondissement_ic.py`).

## Positionnement face aux dépôts GitHub

D'après notre recherche (note de recherche interne du portfolio, non publiée dans ce dépôt, 92 dépôts catalogués, 28 README lus, code non exécuté) :

- **pst-group/pysystemtrade** (Rob Carver) est la référence open source des systèmes à signaux normalisés par la volatilité, cibles de vol et coûts par instrument.
  S1 en reprend le cœur (EWMAC, échelles de prévision, plafond, tampon). Nous n'utilisons pas la bibliothèque : nous recodons le minimum pour contrôler l'horloge d'exécution.
- **bashtage/arch** fournit le bootstrap stationnaire et les tests de comparaisons multiples (SPA, StepM, MCS). Nous avons réimplémenté le bootstrap stationnaire de Politis-Romano en numpy
  (testé : longueur moyenne des blocs, couverture) pour ne pas ajouter de dépendance ; ici il n'y a pas de sélection de candidat, donc pas de SPA.
- **skfolio** (HRP, risque parité, `CombinatorialPurgedCV`) aurait pu servir à pondérer la pile ; nous avons volontairement gardé 1/vol sur TRAIN, plus simple et sans paramètre à optimiser.
- **stefan-jansen/machine-learning-for-trading** pousse une « frontière de preuve » entre exploration et confirmation et le Deflated Sharpe : c'est le gabarit de notre protocole
  (pré-enregistrement, TEST à lecture unique, DSR avec N compté).

Biais relevés dans ces dépôts et ce que fait le nôtre :

| Biais courant | Chez eux | Chez nous |
|---|---|---|
| Fill au prix du signal | exemples de vectorbt sans décalage visible ; doc freqtrade `lookahead-analysis` : biais « très facile à introduire » | un jour plein de décalage + test automatique « modifier le futur ne change pas le passé » (idée freqtrade), pour chaque sleeve et de bout en bout |
| Coûts absents ou forfaitaires | premiers exemples sans frais, commission fixe 0,2 % ; exemple NSE : gain brut 0,91 bp contre 3,5 bps de coût | coûts réels par actif, comptés à chaque jambe ; S4 et S7 retrouvent ce piège en pire : gain brut par trade nul ou négatif face au coût, net très négatif |
| Sélection in-sample / data snooping | heatmaps sur toutes les paires de fenêtres, aucun split annoncé | 7 sleeves à paramètres figés, aucune grille, N = 8 déclaré dans le DSR |
| Sharpe sans intervalle de confiance | Sharpe unique sur une série, ou 14,4 sur 19 jours | IC bootstrap, t Newey-West + Holm, PSR, DSR sur chaque sleeve et la pile |
| Données non reproductibles | données de courtier non publiables, yfinance | données HistData locales, actifs morts documentés et exclus ; ce n'est pas un audit croisé complet |

Ce que nous ne faisons pas mieux : pas d'audit de qualité croisé des minutes (cf. EURGBP au contrôle LSE), pas de PBO/CPCV (inutiles sans sélection mais utiles dès qu'on testera des variantes), pas de modèle de glissement ou d'impact (coûts statiques).

## Validation et tests

`python -m pytest -q` : **84 tests**, dont les tests qui lisent les données locales sont sautés proprement si `HISTDATA_DIR` n'est pas défini (cas de l'intégration continue). Principe : chaque brique est confrontée à une réponse connue (simulation, formule fermée, signal planté) ;
les garanties de causalité et de non-ouverture du TEST sont des tests, pas des promesses.

| Fichier | Tests | Ce qui est vérifié |
|---|---|---|
| [`test_anti_look_ahead.py`](tests/test_anti_look_ahead.py) | 6 | Modifier les données FUTURES ne change aucun poids PASSÉ, pour chacune des 7 sleeves (idée du `lookahead-analysis` de freqtrade). |
| [`test_approfondissement_diagnostics.py`](tests/test_approfondissement_diagnostics.py) | 10 | Approfondissement : breadth effective, demi-vies, règles de cause principale, profil gain/coût sur signaux plantés. |
| [`test_approfondissement_ic.py`](tests/test_approfondissement_ic.py) | 6 | Approfondissement : l'IC est calculé sans look-ahead (prévisions causales, rendement cible après le jour d'exécution, signal planté retrouvé). |
| [`test_approfondissement_test_scelle.py`](tests/test_approfondissement_test_scelle.py) | 8 | Approfondissement : lecteur 1 h strict, base sans date de TEST, verdict `ECHEC` inchangé, prereg intact, empreinte du code officiel. |
| [`test_approfondissement_theorie.py`](tests/test_approfondissement_theorie.py) | 9 | Approfondissement : formules (Sharpe max attendu, erreur-type de Lo, puissance, diversification, loi fondamentale) confrontées à des simulations. |
| [`test_causalite_bout_en_bout.py`](tests/test_causalite_bout_en_bout.py) | 1 | Même propriété de bout en bout sur données réelles : ajouter du futur ne change aucun rendement passé, à égalité exacte (données locales requises). |
| [`test_couts_moteur.py`](tests/test_couts_moteur.py) | 6 | Coûts nuls = rendement brut ; chronologie exacte de l'exécution décalée ; coûts réels lus dans `data/frais_editable.csv` ; garde-fou d'ouverture du TEST ; verdict selon le §8 du prereg. |
| [`test_dashboard_et_readme.py`](tests/test_dashboard_et_readme.py) | 5 | Tableau de bord (`docs/data.json` cohérent avec `results/`, sans TEST), blocs de chiffres du README lus dans `results/`, aucun chemin absolu de machine. |
| [`test_horloge_donnees.py`](tests/test_horloge_donnees.py) | 13 | Horloge réelle des minutes HistData (heure d'été) : conversions locale → fichiers, et ouverture hebdomadaire EURUSD prédite à plus de 98 % (cache des minutes requis). |
| [`test_sleeves_structure.py`](tests/test_sleeves_structure.py) | 5 | Structure des sleeves : long 3 / short 3 somme nulle, achat des perdants (S3), vol cible ex ante, sens du signal S5, tampon de S1. |
| [`test_stats.py`](tests/test_stats.py) | 8 | Statistiques sur données simulées de réponse connue : Sharpe, bootstrap stationnaire (couverture et longueur des blocs), Newey-West, Holm, PSR, DSR, drawdown. |
| [`test_troncature_test.py`](tests/test_troncature_test.py) | 7 | Le TEST (≥ 2023-01-01) est inaccessible depuis les chemins train/val : refus, troncature, aucune année 2023 demandée au disque (données locales requises). |

Trois garde-fous méritent d'être cités : (1) `donnees.py` lève `PermissionError` si on demande une date ≥ 2023-01-01 sans l'autorisation explicite que seul `scripts/ouvrir_test.py` donne ; (2) `ouvrir_test.py` refuse de tourner si G1 ou G2 échoue (c'est le cas) ou si le prereg a changé ;
(3) l'empreinte SHA-256 du code officiel est enregistrée (voir `results/empreinte_code.json` et `results/notes_implementation.md`, section « Mise en conformité GitHub »).

## Limites

- **VAL court** : 4 ans, 1044 jours ; l'erreur standard du Sharpe annualisé vaut environ 0,5 (IC 95 % d'environ ±1). Rien ici ne permet de dire qu'un Sharpe de 0,3 est vrai ou faux.
- **TEST jamais lu** : la conclusion `ECHEC` s'appuie sur G1 et G2 en VAL. Un TEST ne pourrait pas rattraper une pile à Sharpe net −5,3.
- **Pas de portage ni de financement** : swaps FX, intérêts de la marge, dividendes sont ignorés (positions assimilées à des CFD sans coût de détention).
  C'est favorable aux sleeves qui détiennent longtemps (S1, S6).
- **Pas de compensation d'ordres entre sleeves** : S1 long EURUSD et S4 short EURUSD paient chacun leurs coûts (prudent).
- **Coûts constants** sur toute la période (vintage récent) : les spreads 2010-2015 étaient plus larges, les résultats TRAIN sont donc plutôt flattés.
- **Calibration de S6 sur TRAIN** : la constante `c` est choisie pour que la vol TRAIN soit 10 %, ce qui rend le TRAIN de S6 en partie dans l'échantillon (prévu par le prereg).
- **Statistique DSR** : la variance des 8 Sharpe VAL est dominée par S7 (Sharpe net −12,34), ce qui gonfle la barre de déflation (6,23 en annualisé). Le DSR de la pile est de toute façon nul puisque son Sharpe est négatif.
- **Minutes HistData** : BID seulement, trous de quelques minutes tolérés (5 min max, sinon pas de trade).

## Reproduire

```bash
pip install -r requirements.txt

# 1. Sans données de marché : tests synthétiques, puis tout ce qui se régénère depuis results/ (figures, tableau de bord, tableaux du README)
python -m pytest -q                       # les tests qui lisent les données sont sautés (« skipped »)
python scripts/exporter_dashboard.py      # -> docs/data.json, docs/data.js
python scripts/generer_figures_vitrine.py # -> figures/hero_equity.png, toutes_variantes.png, overfit_scatter.png
python scripts/generer_readme_tete.py     # -> blocs de chiffres du README, lus dans results/

# 2. Avec les données locales (non redistribuées) : définir HISTDATA_DIR
export HISTDATA_DIR=/chemin/vers/donnees  # PowerShell : $env:HISTDATA_DIR = "D:/donnees"
#   HISTDATA_DIR/processed/univers/<ACTIF>_1h.csv           barres 1 h (colonnes datetime = début de barre, close)
#   HISTDATA_DIR/histdata_raw/<ACTIF>/<ACTIF>_<année>.zip   minutes HistData (BID)
# Sans la variable, le défaut est ./data/histdata (ignoré par git).
python -m pytest -q                       # suite complète : 84 tests
python scripts/run_train_val.py           # TRAIN/VAL uniquement -> results/train_val.json + figures/
python scripts/verdict.py                 # -> results/verdict_alpha.json
python scripts/auditer_reproduction_trades_frais.py  # reproduction à 1e-9, nombre de trades, frais -> results/reproduction_et_trades.json
python scripts/sensibilite_couts.py       # EXPLORATOIRE -> results/sensibilite_couts_exploratoire.json + figures/sensibilite_couts.png
python scripts/run_approfondissement.py   # EXPLORATOIRE -> results/approfondissement.json + figures/appro_*.png (~1 min)
python scripts/build_nb_alpha_04.py       # (re)génère notebooks/visite_guidee.ipynb
python scripts/build_nb_appro_04.py       # (re)génère notebooks/approfondissement.ipynb
python -m jupyter nbconvert --to notebook --execute --inplace notebooks/visite_guidee.ipynb
python -m jupyter nbconvert --to notebook --execute --inplace notebooks/approfondissement.ipynb
# scripts/ouvrir_test.py : NE PAS LANCER sauf décision explicite (refuse si G1 ou G2 échouent)
```

Les données de marché ne sont pas redistribuées (minutes HistData, BID seulement ; les barres 1 h sont un jeu dérivé préparé pour le stage, dont l'étiquette est le début de la barre, vérifié contre les minutes) : sans elles, on relit tous les chiffres dans `results/` et on régénère tout le reste, mais on ne rejoue pas le calcul.
Le chemin cité dans `PREREGISTRATION.md` est celui de la machine d'origine : le fichier est figé et haché, il n'a pas été réécrit.
Dépendances : Python 3.12+, numpy, pandas, scipy, matplotlib, pyarrow (cache parquet), pytest ; jupyter seulement pour exécuter les carnets.

## Structure du dépôt

```
.
├── README.md                    ce fichier : frais, métriques TRAIN | VAL, courbe finale, lecture « overfit ou pas ? »
├── PREREGISTRATION.md           protocole figé avant le premier calcul (+ avenant 1) ; ne jamais le modifier
├── LICENSE  requirements.txt  .gitignore  .github/workflows/tests.yml
├── alpha/                       le moteur de recherche (données, coûts, risque, sleeves, moteur, stats, gates, pipeline, graphiques)
│   └── approfondissement/       analyse exploratoire a posteriori (théorie, diagnostics, figures) ; hors empreinte du code officiel
├── scripts/                     lancement des calculs, export du tableau de bord, génération des figures et des tableaux du README
├── tests/                       suite pytest (synthétique, sauf les tests qui lisent les données locales)
├── notebooks/                   visite guidée et approfondissement (carnets exécutés)
├── results/                     sorties figées (JSON, CSV des rendements quotidiens) dont sont tirés tous les chiffres
├── figures/                     images du README (héro, toutes variantes, scatter overfit, PnL, coûts, approfondissement)
├── docs/                        tableau de bord interactif (GitHub Pages) : index.html + data.json + data.js
└── data/frais_editable.csv      coûts réels par actif (copie versionnée) ; les données de marché ne sont pas versionnées
```

Chaque dossier a son propre `README.md` (rôle et une ligne par fichier).

---

## English summary

**Question.** Can a Sharpe ratio above 2 (net of real per-asset costs, out of sample) be reached by stacking seven simple, literature-based strategies with parameters fixed in advance,
on 58 liquid FX / index / metal / oil series, with no selection on past performance?

**Protocol.** Pre-registered ([`PREREGISTRATION.md`](PREREGISTRATION.md), SHA-256 `f6007427c1a45552…`) before any code: seven sleeves (EWMAC trend, FX momentum, FX reversal,
intraday FX seasonality, month-end fixing, volatility-managed equities, intraday SPX momentum), real costs (indices 12 bps per leg), a full-day execution lag, TRAIN 2010-2018 / VAL 2019-2022 / sealed TEST 2023+,
stationary-bootstrap confidence intervals, Newey-West + Holm, PSR and Deflated Sharpe (N = 8). The stack keeps all sleeves, weighted by inverse TRAIN volatility.

**Result.** Verdict `ECHEC`; TEST left sealed because G1 and G2 fail. Stack VAL net Sharpe −5,30 (95 % CI [−6,31, −4,30]), gross −0,70;
the daily sleeves are statistically indistinguishable from zero or negative, the intraday sleeves have no gross edge worth the real costs (S4 gross 0,14 / net −1,81;
S7 costs 121 % of capital per year for a 10 % volatility target). Reaching Sharpe 2 would need about 0,81 net Sharpe per sleeve at the observed correlation (0,026); the best is 0,07.

**Honest limits.** Four-year validation window, no carry/financing, static costs, no order netting between sleeves, TEST never read.
