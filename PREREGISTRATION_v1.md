# Pré-enregistrement — « Pile de sleeves décorrélées » (projet 04)

Rédigé le 2026-10-13 vers 01h15, AVANT toute ligne de code et tout calcul de performance.
Ce fichier est figé : il est commité seul, et son empreinte SHA-256 figure dans le message
de commit. Toute modification ultérieure doit apparaître comme un AVENANT daté en bas de
fichier, jamais comme une réécriture.

## 1. Question

Peut-on atteindre un Sharpe net > 2 hors échantillon en empilant des stratégies simples,
tirées de la littérature, aux paramètres FIXÉS d'avance, sur nos données réelles (60 actifs,
coûts réels par actif), sans aucune sélection par la performance passée ?

Attente honnête (écrite avant de voir les chiffres) : non. Sous indépendance, il faut
environ 16 sleeves de Sharpe 0,5 pour atteindre 2 ; les sleeves seront corrélées et
plusieurs seront négatives après coûts. Attente réaliste pour la pile : Sharpe VAL entre
−0,2 et +0,8. Le livrable est la mesure, quelle qu'elle soit.

## 2. Données (lecture seule)

- Prix 1 h : `C:\Users\MSI\Desktop\stage awb\data\processed\univers\<ACTIF>_1h.csv`
  (`datetime,close`, heure EST fixe UTC−5).
- Prix 1 minute : `C:\Users\MSI\Desktop\stage awb\data\histdata_raw\<ACTIF>\<ACTIF>_<AAAA>.zip`
  et `_<AAAAMM>.zip` (`AAAA.MM.JJ,HH:MM,open,high,low,close,volume`, BID, EST fixe UTC−5).
- Coûts : `coordination/frais_editable.csv` du worktree ; coût par jambe =
  `frais_editable_override` s'il est renseigné, sinon `frais_bps_par_jambe` ; indices
  figés à 12 bps/jambe. Tout résultat avec un autre coût est invalide.
- Actifs exclus (morts) : WTIUSD, ETXEUR, XAUAUD/XAUCHF/XAUEUR/XAUGBP, UDXUSD, GRXEUR.

## 3. Découpage temporel

TRAIN 2010-01-01 → 2018-12-31 (préchauffage + calibration des échelles) ; VAL 2019-01-01 →
2022-12-31 (évaluation) ; TEST 2023-01-01 → fin des données : ouvert UNE SEULE FOIS par le
script `ouvrir_test.py`, qui refuse de tourner si `results/test_ouvert.json` existe déjà.

## 4. Conventions communes

- Instantané quotidien : dernier close 1 h à ou avant 11h00 EST de chaque jour ouvré
  (fixing global retenu par PIVOT-0). Prix manquant : report du dernier prix connu au plus
  3 jours pour le signal ; rendement d'un jour sans prix = 0.
- Exécution des sleeves quotidiennes : position décidée avec les données ≤ instantané J,
  exécutée à l'instantané J+1, elle gagne le rendement J+1 → J+2 (décalage d'un jour plein,
  plus strict que T+1 min).
- Exécution des sleeves intrajournalières : signal à la minute m, entrée à l'open de la
  minute m+1, sortie à l'open de la minute qui suit la fin de fenêtre.
- Coût : `coût_bps(actif) × |Δ poids notionnel|` à chaque changement de position (une
  ouverture puis une fermeture = deux jambes).
- Fuseaux : les fenêtres « heure locale » sont converties depuis EST fixe via
  `Etc/GMT+5` → `Europe/London`, `Asia/Tokyo`, `America/New_York` (gère l'heure d'été).
- Chaque sleeve vise 10 % de volatilité annuelle ex ante (vol EWMA des actifs, demi-vie
  36 jours, calculée sur le passé seulement). Rendements quotidiens, annualisation √252.

## 5. Les 7 sleeves (paramètres figés, aucune grille)

| # | Sleeve | Source | Univers | Règle figée |
|---|---|---|---|---|
| S1 | Trend following EWMAC | Carver (2015), Moskowitz-Ooi-Pedersen (2012) | tous les actifs non exclus | moyenne des prévisions EWMAC(16,64), (32,128), (64,256) ; chaque prévision = (EMA_rapide − EMA_lente) / vol prix EWMA 36 j × échelle fixe (3,75 ; 2,65 ; 1,87), plafond ±20 ; position ∝ prévision/10 ; tampon de rebalancement 10 % |
| S2 | Momentum cross-sectionnel devises | Menkhoff-Sarno-Schmeling-Schrimpf (2012) | EUR, GBP, AUD, NZD, CAD, CHF, JPY, NOK, SEK contre USD | rendement 63 j ; chaque vendredi : long les 3 meilleures, short les 3 pires, poids égaux en risque |
| S3 | Retournement court terme devises | littérature reversal FX | mêmes 9 devises | rendement 5 j ; chaque vendredi : long les 3 pires, short les 3 meilleures |
| S4 | Saisonnalité intrajournalière | Breedon-Ranaldo (2013) | EURUSD, GBPUSD, USDCHF (fenêtre Londres 08h-14h), USDJPY, AUDUSD, NZDUSD (fenêtre Tokyo 09h-15h) | vendre la devise étrangère contre USD pendant SA fenêtre domestique, à plat sinon |
| S5 | Fixing de fin de mois | Melvin-Prins (2015) | EURUSD/FRXEUR, GBPUSD/UKXGBP, USDJPY/JPXJPY, AUDUSD/AUXAUD contre SPXUSD | dernier jour ouvré du mois, 06h00→10h00 EST : si l'indice US a surperformé l'indice étranger depuis le début du mois (mesuré à 06h00 EST), vendre l'USD contre la devise, sinon acheter |
| S6 | Exposition actions gérée par la volatilité | Moreira-Muir (2017) | SPXUSD, NSXUSD, UKXGBP, JPXJPY, FRXEUR, HKXHKD, AUXAUD | long seulement, rebal mensuel, poids = c / variance réalisée du mois précédent, levier plafonné à 2, c tel que la vol moyenne TRAIN = 10 % |
| S7 | Momentum intrajournalier indice US | Gao-Han-Li-Zhou (2018) | SPXUSD | signal = rendement close 16h00 ET veille → 10h00 ET ; entrée 15h30 ET dans le sens du signal, sortie 16h00 ET |

## 6. Combinaison (pas de sélection)

Les 7 sleeves sont TOUTES gardées. Poids de la pile ∝ 1 / volatilité réalisée de chaque
sleeve sur TRAIN uniquement, puis mise à l'échelle de la pile à 10 % de vol (sur TRAIN).
Aucun poids ne dépend d'un Sharpe. Aucune sleeve n'est retirée après avoir vu VAL.

## 7. Statistiques

Sharpe net annualisé, rendement, volatilité, drawdown maximal, rotation, coût annuel ;
IC 95 % du Sharpe par bootstrap stationnaire (blocs moyens 20 jours, 5 000 tirages) ;
t de Newey-West de la moyenne quotidienne + correction de Holm sur les 7 sleeves ;
PSR(0) et Deflated Sharpe Ratio avec N = 8 essais (7 sleeves + la pile) et la variance
des 8 Sharpe VAL ; corrélations entre sleeves.

## 8. Gates (sur la pile)

- G1 : Sharpe net VAL ≥ 1,0.
- G2 : borne basse de l'IC 95 % bootstrap du Sharpe VAL > 0.
- G3 : DSR VAL (N = 8) ≥ 0,95.
- G4 : TEST (lecture unique) : Sharpe net > 0 ET ≥ 0,5 × Sharpe VAL (cohérence, leçon 7).
- Objectif utilisateur (non bloquant, rapporté tel quel) : Sharpe net ≥ 2.

Verdict `SUCCES` seulement si G1 à G4 passent, sinon `ECHEC` avec tous les chiffres, dans
`results/verdict_alpha.json`. Le TEST n'est ouvert que si G1 et G2 passent ; sinon il
reste scellé et le verdict le dit.

## 9. Ce qui est interdit

Changer un paramètre du §5 après avoir vu VAL ; ajouter ou retirer une sleeve ; changer
les poids ; relancer le TEST. Une idée nouvelle née de la lecture de VAL = un NOUVEAU
pré-enregistrement, avec N d'essais cumulé.

## AVENANTS

(aucun)
