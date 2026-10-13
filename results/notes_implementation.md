# Notes d'implémentation : interprétations prises et limites

Ce fichier consigne tout ce que le prereg laissait ambigu ou infaisable, et le choix fait. Règle suivie : prendre l'interprétation la plus conservatrice, celle qui ne peut pas avantager la stratégie.
`PREREGISTRATION.md` n'a pas été modifié (empreinte SHA-256 `f6007427…` vérifiée à chaque lancement de `run_train_val.py` et écrite dans `train_val.json`).

## Données et horloge

1. **Instantané « 11h00 EST »** : l'étiquette `datetime` des fichiers 1 h est le DÉBUT de la barre. Vérifié contre le 1 minute (EURUSD, mars 2010) : le close 1 h égale le close de la minute `étiquette + 59 min` dans 97 % des cas (2 % à `+0`).
   Le « dernier close 1 h à ou avant 11h00 » est donc le close de la barre étiquetée **10h00** (il tombe à 10h59). La barre étiquetée 11h00 finirait à 11h59 et contiendrait une heure de futur. On prend la dernière barre d'étiquette ≤ 10h00 **du même jour** ; sinon prix manquant (NaN). Revérifié à la relecture du 13/10 : 100 % de correspondance close 1 h = close minute `étiquette + 59 min` sur 8 actifs (FX, indices, or, Brent), janvier et juillet 2013/2018/2021. Attention : « 11h00 EST » désigne ici l'étiquette de l'horloge des fichiers, qui n'est pas de l'EST fixe (voir « Corrections après relecture du 13/10 »).
2. **Jours ouvrés** = lundi à vendredi, sans calendrier de bourse. Un jour férié ou une donnée manquante donne NaN. Pour le signal : report du dernier prix connu, 3 jours au plus. Pour le PnL : le rendement d'un jour sans prix vaut 0 et, au retour du prix, le rendement rattrape l'écart (le PnL total est conservé).
3. **Horloge d'exécution des sleeves quotidiennes** (`moteur.py`) : avec `w[t]` le poids décidé à l'instantané `t`, la position détenue après `t` est `w[t-1]`, elle gagne `R[t+1]`, le coût est payé à `t` sur `|w[t-1] - w[t-2]|`. Un poids décidé à J gagne donc le rendement J+1 → J+2 (test unitaire exact dans `tests/test_couts_moteur.py`).
4. **Fenêtres intrajournalières** : le prereg dit « signal à la minute m, entrée à l'open de m+1, sortie à l'open de la minute qui suit la fin de fenêtre ». Choix : la minute-signal est la minute d'étiquette **début de fenêtre**, entrée à l'open de `début + 1 min`, sortie à l'open de `fin + 1 min` (une minute de retard aux deux bouts, jamais d'avance). Fuseaux : heure locale du marché → UTC → étiquette de l'horloge réelle des fichiers (`donnees.local_vers_horloge_donnees`). **La version initiale (conversion vers `Etc/GMT+5`, EST fixe) était fausse** : voir « Corrections après relecture du 13/10 ».
5. **Prix 1 minute manquant** : un `open` d'exécution manquant est remplacé par la première minute suivante dans une tolérance de 5 minutes (retard, jamais avance) ; au-delà, **pas de trade** (ni gain ni coût). Un `close` de signal manquant est remplacé par la dernière minute précédente (passé seulement), même tolérance.
6. **Datation du PnL intrajournalier** : un trade réalisé entre l'instantané 11h00 du jour J−1 (exclu) et celui du jour J (inclus) est daté J ; week-end reporté au lundi. Conséquence : le trade S7 du 2022-12-30 (sortie 16h01 ET) est daté 2023-01-02, hors VAL, et n'est donc pas compté (VAL s'arrête au 2022-12-30). C'est volontairement prudent : aucun PnL n'est daté avant sa réalisation.
7. **Univers de S1 = 58 actifs** : les 60 fichiers de `data/processed/univers` moins WTIUSD et GRXEUR (les autres actifs exclus du prereg n'y figurent pas). Les indices et le Brent commencent en novembre 2010 dans les fichiers 1 h ; l'indice SPX en minute commence le 2010-11-14.

## Risque et vol cible (section 4 du prereg)

8. **« Vol EWMA des actifs, demi-vie 36 jours »** : toutes les volatilités utilisent une demi-vie de 36 jours (y compris la « vol prix EWMA 36 j » de S1, lue comme demi-vie 36 j), second moment centré en 0, au moins 63 observations avant la première position. Les NaN n'entrent pas dans l'estimation (ils ne sont pas comptés comme des rendements nuls, ce qui sous-estimerait la vol des actifs récents).
9. **10 % de vol ex ante = covariance EWMA complète** (pas la somme des vols individuelles) : poids = `k_t × signal / sigma_i`, `k_t` unique par jour tel que `jours_actifs × w'Σw = 0,10²`. Plancher de vol de 1 % annuel pour dimensionner S1, S2, S3 (évite un levier démesuré sur les paires quasi gelées : USDHKD, EURDKK).
10. **Sleeves intrajournalières** : la covariance utilisée est celle des rendements de fenêtre, **décalée d'un jour** (la fenêtre du jour J n'est connue qu'une fois close). Variance annuelle ex ante = `jours_actifs_par_an × w'Σw` avec 252 jours actifs pour S4 et S7, **12 pour S5** (un jour par mois ; la covariance est estimée sur tous les jours). S4 : covariance croisée Londres/Tokyo mise à zéro (fenêtres disjointes).
    Conséquence à connaître : une exposition de 30 minutes par jour à 10 % de vol annuel impose un levier élevé (S7 : |poids| moyen 2,2 les jours de trade en VAL (2,5 avant la correction de l'horloge) ; S5 : exposition brute moyenne de 21 le jour actif, soit environ 5 par paire). Le Sharpe d'une sleeve ne dépend pas du levier, mais son coût annuel en % du capital oui, et c'est ce qui rend S7 si négative.
11. **S6** : `c` calibré par `brentq` pour que la vol annualisée réalisée de la sleeve (rendements bruts quotidiens depuis le premier jour actif jusqu'au 2018-12-31) soit exactement 10 % : `c = 0,01259`. Constante figée ensuite pour VAL et TEST. Le TRAIN de S6 est donc en partie dans l'échantillon (voulu par le prereg).

## Sleeves

12. **S1** : chaque prévision EWMAC est mise à l'échelle puis plafonnée à ±20, la prévision finale est la moyenne des trois (pas de multiplicateur de diversification des prévisions : la vol cible au niveau de la sleeve le remplace). Les EMA sont définies par leur *span* (alpha = 2/(span+1)), `min_periods` = span de l'EMA lente. Tampon : 10 % de la position à prévision 10 (taille unitaire), retour au bord le plus proche de la bande (règle de Carver).
13. **S2 et S3** : 9 paires USD (EUR, GBP, AUD, NZD directes ; CAD, CHF, JPY, NOK, SEK inversées). Décision au vendredi (donnée du vendredi 11h00, exécution au jour ouvré suivant). « Poids égaux en risque » lu comme : dans chaque jambe poids ∝ 1/σ, chaque jambe pèse 0,5 en brut, donc **somme des poids nulle** (testé), puis un facteur unique pour la vol cible. Le portefeuille n'est pris que si les 9 devises ont un signal valide ce vendredi-là ; les poids sont maintenus constants jusqu'au vendredi suivant. S3 achète les 3 pires rendements à 5 jours.
14. **S4** : paires et directions : EURUSD −1, GBPUSD −1, USDCHF +1 (fenêtre Londres 08h-14h) ; USDJPY +1, AUDUSD −1, NZDUSD −1 (fenêtre Tokyo 09h-15h). On vend la devise étrangère contre USD, donc on vend les paires XXXUSD et on achète les paires USDXXX.
15. **S5** : fin de mois = dernier jour **ouvré (lundi-vendredi) du calendrier** (règle de calendrier, pas de donnée : un historique tronqué ne crée pas de faux « fin de mois »). Le prix des indices « à 06h00 EST » est le close de la barre 1 h étiquetée 05h00 (plus économique que les minutes d'indices et strictement passé). Début de mois = premier prix valide du mois, mesuré à la même heure. Égalité exacte entre les deux performances : on achète l'USD. Paires/indices : EURUSD/FRXEUR, GBPUSD/UKXGBP, USDJPY/JPXJPY, AUDUSD/AUXAUD contre SPXUSD. Seul le FX est tradé (aucun coût d'indice).
16. **S6** : variance réalisée du mois = somme des carrés des rendements quotidiens de l'instantané, annualisée (×252/n), exigée sur au moins 10 jours valides ; levier par indice `min(c/RV, 2)` puis équipondération entre indices disponibles (jusqu'à 7). Décision au dernier jour ouvré du mois M avec la variance de M, valable pour M+1, exécution à J+1. Poids constants entre deux décisions (pas de rebalancement de dérive, pas de coût associé).
17. **S7** : rendement veille 16h00 ET → 10h00 ET calculé sur les closes de minutes étiquetées 16:00 (veille ouvrée) et 10:00 ; signal nul = pas de trade ; sortie à l'open de 16h01 ET.

## Coûts et pile

18. Coûts : `frais_editable_override` sinon `frais_bps_par_jambe` ; classes commençant par « Indice » forcées à 12 bps. Pour S2/S3 le coût d'une devise est celui de sa paire. Intrajournalier : deux jambes par trade, `2 × coût × |poids|`.
19. **Pile** : poids ∝ 1/vol réalisée **nette** de chaque sleeve sur la fenêtre TRAIN commune où les 7 sleeves sont actives (du 2011-02-24, premier jour actif de S7, au 2018-12-31), puis `kappa = 2,34` pour 10 % de vol sur cette fenêtre. Coût de la pile = somme pondérée des coûts des sleeves, **sans compensation d'ordres entre sleeves** (prudent). Les statistiques de la pile commencent au 2011-02-24.
20. **Statistiques** : Sharpe = moyenne/écart-type quotidiens × √252 (taux sans risque nul : positions assimilées à des CFD, aucun portage ni financement). Drawdown sur courbe composée. Bootstrap stationnaire de Politis-Romano réimplémenté en numpy (graine 20261013, percentiles 2,5 et 97,5). Newey-West avec `floor(4 (n/100)^(2/9))` retards et p-values normales bilatérales. Holm sur les p-values NW des 7 sleeves (pas de la pile). PSR avec kurtosis non excédentaire. DSR : `SR0 = sqrt(V)[(1−γ)Φ⁻¹(1−1/N) + γΦ⁻¹(1−1/(Ne))]` avec N = 8 et V = variance (ddof = 1) des 8 Sharpe VAL quotidiens.
21. **Étiquettes de verdict** : `ECHEC` dès que G1 ou G2 échoue (TEST scellé, statut `scelle_G1_ou_G2_en_echec`) ; `TEST_NON_OUVERT` si G1 et G2 passent mais que le TEST n'a pas été lu ; sinon `SUCCES` ssi G1 à G4 passent. Le TEST s'ouvre si G1 et G2 passent, même si G3 échoue (le prereg ne conditionne l'ouverture qu'à G1 et G2).

## Garde-fous TEST

22. `donnees.py` : toute fonction de chargement a un plafond `fin ≤ 2023-01-01` ; au-delà, `PermissionError` sauf `test_autorise=True` (réservé à `ouvrir_test.py`). Les minutes sont cachées par actif et par année (`cache/minutes/*.parquet`, gitignoré) : en mode scellé aucune année ≥ 2023 n'est même demandée au disque (testé avec un espion). La troncature est suivie d'un `assert` (aucune ligne ≥ 2023-01-01).
23. `ouvrir_test.py` n'a **pas** été exécuté. Il refuse si `results/test_ouvert.json` existe, si `train_val.json` manque, si G1 ou G2 échoue, ou si le hash du prereg a changé ; il vérifie que TRAIN/VAL recalculés sont identiques à `train_val.json` (propriété de causalité vérifiée ici sur un point de coupure intermédiaire : ajouter du futur ne change aucun rendement passé, égalité exacte) ; il écrit `test_ouvert.json` en création exclusive.

## Points fragiles et dette assumée

- Fenêtres EURUSD (Londres), USDJPY (Tokyo), SPXUSD (New York) et signal du matin : la vérification initiale « à la main » ne contrôlait que la cohérence du code avec sa propre conversion, pas l'horloge des données (d'où le défaut corrigé plus bas). Revérifié le 13/10 sur 153 fenêtres + 60 signaux du matin par une voie indépendante (zoneinfo → UTC → règle d'horloge), écart nul.
- Vérifié à la main : l'effet de S2 (spread hebdomadaire équipondéré, sans moteur) donne le même signe que la sleeve complète. Moyenne hebdomadaire −4,5 bps (TRAIN) et −5,4 bps (VAL), t ≈ −1,6 et −1,4.
- Non vérifié : qualité des minutes HistData des indices (pas d'audit croisé comme celui fait sur LSE) ; trous éventuels dans les fichiers au-delà de la tolérance de 5 minutes (11 % des jours SPX sans fenêtre S7, 1 % pour le FX).
- Les spreads sont constants (vintage 2024-2026) sur toute la période : le TRAIN est probablement flatté.
- DSR : `SR0` annualisé = 6,2, gonflé par la variance énorme du Sharpe de S7 dans l'ensemble des 8 essais. Même avec un `SR0` nul le DSR de la pile serait nul (Sharpe négatif).
- Aucune nouvelle dépendance ; `pyarrow` (déjà installé) sert au cache parquet.

## Corrections après relecture du 13/10

Relecture adversariale indépendante (scripts de vérification dans `projets_cv/_revue/scripts_04/`, synthèse dans `projets_cv/_revue/revue_04.md`). `PREREGISTRATION.md` n'a pas été modifié (SHA-256 `f6007427…` inchangé, vérifié). Le TEST est resté scellé : aucun fichier ≥ 2023 n'a été lu, aucun `cache/minutes/*_2023.parquet` n'existe, `ouvrir_test.py` n'a pas été lancé.

### Correction 1 (MAJEUR) : les minutes HistData ne sont pas en EST fixe, les fenêtres de S4 et S7 étaient décalées d'une heure l'été

**Constat.** Le prereg (§2, §4) et le code (`FUSEAU_DONNEES = "Etc/GMT+5"`) supposaient les minutes en heure EST fixe (UTC−5). L'horloge réelle des fichiers suit l'heure d'été :
- Ouverture hebdomadaire du FX (dimanche 17h00 heure de New York, soit 21h00 UTC l'été, 22h00 l'hiver) : **17h00 toute l'année** dans les fichiers (396 des 397 ouvertures de semaine en régime d'été entre 17h00 et 17h05 ; en EST fixe on attendrait 16h00 l'été).
- Pic de volatilité NFP (08h30 New York) : 08h30 sur l'horloge des fichiers l'été comme l'hiver (pic le plus fréquent chaque année de 2012 à 2022). Ouverture cash du SPX (09h30 New York) : de même.
- Deux régimes : jusqu'en 2018, heure légale de New York (DST américain) ; depuis 2019, UTC−5 pendant l'hiver européen et UTC−4 pendant l'été européen. Les deux ne diffèrent que pendant les ~5 semaines par an où les DST américain et européen diffèrent : en 2019-2022 l'ouverture hebdomadaire y apparaît à 16h00 (3 à 4 semaines par an) et le pic NFP de novembre 2021 et 2022 à 07h30, alors qu'en 2010-2018 l'ouverture reste à 17h00 dans ces semaines.
- Règle corrigée = `America/New_York` avant 2019-01-01 UTC, `Europe/London − 5 h` ensuite. Elle prédit **665 des 667 ouvertures de semaine EURUSD 2010-2022 (99,7 %)**, 660/667 pour USDJPY et 661/666 pour GBPUSD ; l'ancienne règle EST fixe n'en prédit que 36 %.
- La vérification faite à la création (note « Points fragiles » d'origine, test `test_fenetre_heure_d_ete_et_d_hiver`) était circulaire : elle vérifiait que le code lisait bien les minutes que sa propre conversion désignait, pas que cette conversion correspondait à l'horloge des données.

**Conséquences.** Pendant les mois d'heure d'été (~7 mois par an) :
- S4 : fenêtre Londres 08h-14h lue de 07h à 13h heure de Londres, fenêtre Tokyo 09h-15h lue de 08h à 14h heure de Tokyo.
- S7 : fenêtre d'entrée/sortie lue à 14h30-15h00 ET au lieu de 15h30-16h00 ; signal du matin mesuré de 15h00 ET (veille) à 09h00 ET (avant l'ouverture cash) au lieu de 16h00 → 10h00 ET.
- Pas de look-ahead (tout restait strictement passé) ; c'est une erreur de spécification des fenêtres, pas une fuite. Les sleeves quotidiennes et S5 ne sont pas concernées (instantané 11h00 et fenêtre S5 06h00-10h00 sont définis sur l'étiquette de l'horloge des fichiers et lus tels quels).

**Correction.** `alpha/donnees.py` : nouvelles fonctions `utc_vers_horloge_donnees` et `local_vers_horloge_donnees` (remplace `local_vers_est_naif`), constante `DEBUT_HORLOGE_UE`. Un fuseau égal à `FUSEAU_DONNEES` (S5) est lu tel quel. **Aucun paramètre du §5 n'a changé** (mêmes fenêtres 08h-14h Londres, 09h-15h Tokyo, 15h30-16h00 ET, mêmes règles, mêmes coûts) : seule la conversion heure locale → horloge des fichiers est corrigée, ce que le prereg demandait déjà (« gère l'heure d'été »). La décision repose sur des preuves de microstructure indépendantes de la performance (ouverture hebdomadaire, NFP, ouverture cash), établies avant d'examiner l'effet sur VAL ; elle ne doit pas être lue comme une sélection par la performance. Un avenant daté au prereg est recommandé (le fichier est figé : non fait ici).

**Tests de régression.** `tests/test_horloge_donnees.py` (13 tests : 12 conversions locales vers horloge des fichiers, dont les semaines où les DST diffèrent, et 1 test sur données réelles : l'ouverture hebdomadaire EURUSD 2010-2022 doit être prédite à plus de 98 %, alors que l'ancienne règle fait moins de 50 %). `tests/test_troncature_test.py::test_fenetre_heure_d_ete_et_d_hiver` corrigé (il encodait l'erreur : été 02h01-08h01 → 03h01-09h01). Vérifié : l'ancien code échoue sur 3 des 5 conversions testées (New York et Londres en été 2018, Tokyo en été 2022) ; les 2 autres (hiver, semaine à DST différents 2021) coïncident entre ancien et nouveau code.

**Avant / après** (`scripts/run_train_val.py` puis `scripts/verdict.py` relancés ; sauvegarde des chiffres d'avant dans `projets_cv/_revue/scripts_04/avant_train_val.json`).

| Série | Sharpe net VAL | Sharpe brut VAL | Sharpe net TRAIN | t NW VAL | p Holm | Coût/an VAL |
|---|---|---|---|---|---|---|
| S4 | −1,41 → −1,81 | 0,58 → 0,14 | −1,68 → −1,91 | −2,91 → −3,75 | 0,022 → 0,001 | 21,0 % → 20,5 % |
| S7 | −12,47 → −12,34 | −0,74 → −1,29 | −16,60 → −15,60 | −18,07 → −19,49 | 0,000 → 0,000 | 137,6 % → 121,2 % |
| PILE | −5,32 → −5,30 | −0,36 → −0,70 | −6,70 → −6,48 | −10,13 → −10,20 | n/a | 48,7 % → 45,5 % |
| S1, S2, S3, S5, S6 | inchangés au bit près | | | | | |

Autres chiffres : IC 95 % de la pile [−6,42 ; −4,23] → [−6,31 ; −4,30] ; G1 −5,32 → −5,30 ; G2 −6,42 → −6,31 ; G3 (DSR) ≈ 0 dans les deux cas ; `kappa` 2,326 → 2,345 ; `SR0` annualisé 6,32 → 6,23 ; poids de la pile S4 0,148 → 0,145 et S7 0,120 → 0,125 ; corrélation moyenne VAL 0,024 → 0,026. Gain brut moyen par trade de S7 : +0,74 → +0,04 bp (TRAIN), −0,29 → −1,90 bp (VAL) ; gain brut par trade de S4 en VAL : EURUSD +1,29 → +0,40 bp, les six paires sont maintenant sous leur coût aller-retour.
**Verdict inchangé : `ECHEC`, G1, G2 et G3 en échec, TEST scellé.** Le seul effet qualitatif : l'« effet réel » de S4 (Sharpe brut 0,58) n'était pas robuste à la bonne définition des fenêtres ; il vaut 0,14 (TRAIN −0,24).

### Constats mineurs, non corrigés (documentés)

- **DSR peu informatif** : la barre `SR0` (6,2 annualisé) est dominée par la variance du Sharpe de S7 (−12,3) et de la pile parmi les 8 essais. Formule du prereg appliquée telle quelle et vérifiée contre une implémentation indépendante ; le verdict ne change pas (G1 et G2 échouent de toute façon).
- **S5 et instantané 11h00** : définis sur l'étiquette de l'horloge des fichiers (heure de New York), conformément à la lettre du prereg (« 06h00→10h00 EST »), pas en UTC−5 physique. La fenêtre S5 se termine donc une heure avant le fixing 16h00 Londres toute l'année ; lecture alternative (UTC−5 physique) non testée car elle reviendrait à choisir un paramètre après avoir vu VAL.
- **S6, report d'un poids périmé** : si le poids mensuel d'un indice était NaN (moins de 10 jours valides ou variance nulle), `sortie.ffill()` reporterait le poids du mois précédent au lieu de passer à plat. Cas non rencontré (0 mois concerné après 2011-01), donc sans effet ; à corriger si l'univers change.
- **Univers** : fichiers existants aujourd'hui moins une liste d'exclusions fixée avec le recul (actifs morts) : léger biais de survie, déjà assumé par le prereg. Coûts constants (millésime récent) et absence de portage : limites déjà listées.

### Vérifié sans défaut (relecture)

Étiquette 1 h = début de barre, close à +59 min (100 %, 8 actifs, été et hiver) ; instantané 11h00 = barre 10h00 du même jour ; moteur (décision J → exécution J+1 → gain J+1→J+2, coût sur |Δposition| des deux jambes, fenêtres intrajournalières : 2 × coût × |poids|, pas de double comptage) ; coûts lus dans `frais_editable.csv` (58/58 actifs couverts, 0 NaN, override > frais, 8 indices à 12 bps, bps/1e4) ; dernier jour ouvré du mois (calendrier) ; règles du §5 (échelles 3,75/2,65/1,87, plafond ±20, tampon 10 %, 63 j, 5 j, vendredi, long 3/short 3, directions S4/S5, c de S6 calibré sur TRAIN) ; vol EWMA, poids de la pile et `kappa` calculés sur le passé/TRAIN ; statistiques recalculées de façon indépendante (Sharpe, t de Newey-West vs statsmodels, bootstrap vs `arch.StationaryBootstrap`, Holm, PSR, DSR avec SR0 en unités quotidiennes cohérentes) : écarts nuls ; cohérence README ↔ JSON (tous les nombres cités) ; hash du prereg.

## Mise en conformité GitHub (13/10) : chemins relatifs, empreinte du code, nombre de trades

Aucun résultat n'a changé. Cette section documente ce qui a été modifié dans le code officiel pour publier le dépôt, et pourquoi l'empreinte `code_sha256` de `results/train_val.json` reste explicable.

**Modifications (trois fichiers de `alpha/`, aucune logique de calcul).**
- `alpha/donnees.py` : `RACINE_DONNEES` n'est plus un chemin absolu de la machine d'origine ; il lit la variable d'environnement `HISTDATA_DIR` (défaut : `./data/histdata`, ignoré par git). Arborescence attendue : `processed/univers/<ACTIF>_1h.csv` et `histdata_raw/<ACTIF>/<ACTIF>_<année>.zip`. Troncature du TEST, horloge, instantanés : inchangés.
- `alpha/couts.py` : `FICHIER_FRAIS` pointe sur `data/frais_editable.csv`, copie octet pour octet (vérifiée par `cmp`) du fichier de coûts réels du stage ; mêmes règles (override sinon frais, indices figés à 12 bps).
- `alpha/pipeline.py` : `sha256_code()` normalise les fins de ligne (CRLF vers LF) avant de hacher, pour que l'empreinte soit la même sous Windows et sous Linux (intégration continue). L'ancienne version hachait les octets bruts du checkout Windows : un clone Linux ne pouvait pas la reproduire.
- Tests : les tests qui lisent les données locales sont sautés si `HISTDATA_DIR` est absent (`tests/outils_donnees.py`) ; `test_code_officiel_inchange_empreinte_identique` compare maintenant l'empreinte courante à `results/empreinte_code.json` (voir ci-dessous).

**Reproduction à 1e-9 (preuve).** `scripts/auditer_reproduction_trades_frais.py` recalcule la chaîne complète TRAIN + VAL (TEST scellé) avec le nouveau chargement et compare à `results/train_val.json` huit statistiques (n_jours, Sharpe net et brut, rendement annuel net, vol, drawdown max, rotation, coût annuel) pour les 7 sleeves et la pile, sur TRAIN et VAL.
Résultat : écart maximal **0** (égalité exacte, donc a fortiori < 1e-9), y compris les Sharpe nets VAL ; écart relatif maximal sur `results/rendements_train_val.csv` 4,9e-8 (le CSV est écrit avec 8 chiffres significatifs). Chiffres dans `results/reproduction_et_trades.json`.
Le garde-fou `alpha/approfondissement/chargement.py::_verifier_contre_json` refait la même comparaison (Sharpe nets VAL, 1e-9) à chaque reconstruction de la base de l'approfondissement ; comme l'empreinte du code a changé, le cache `cache/appro_base.pkl` (ignoré par git) est reconstruit au premier appel.

**Empreinte du code : pourquoi `train_val.json` n'a pas été réécrit.** `results/train_val.json` n'a pas été régénéré : il garde `meta.code_sha256 = ad21bbc8…`, l'empreinte du code **tel qu'il était quand les résultats ont été produits** (octets bruts, fins de ligne CRLF). Les chiffres étant reproduits à l'identique, réécrire ce fichier n'aurait changé que la date et l'empreinte. `results/empreinte_code.json` relie les deux versions :
- avant : `ad21bbc8…` (octets bruts) ; le même code haché avec fins de ligne normalisées donne `d9f6fe23…` ;
- après : `75933d8f…` (`pipeline.sha256_code()` actuel, fins de ligne normalisées) ;
- seuls trois fichiers diffèrent (`alpha/couts.py`, `alpha/donnees.py`, `alpha/pipeline.py`, voir plus haut), les autres fichiers hachés (`alpha/*.py`, `scripts/run_train_val.py`, `scripts/ouvrir_test.py`, `scripts/verdict.py`) ont le même hachage individuel avant et après ; la liste des hachages par fichier est dans `empreinte_code.json`.
Toute nouvelle modification de ces fichiers exigera de mettre à jour `empreinte_code.json` (c'est le rôle du test).

**Nombre de trades.** `train_val.json` ne contenait que la rotation. Le nombre d'ordres exécutés par sleeve (`results/reproduction_et_trades.json`, clé `nb_trades`) est lu dans les poids que reçoit le moteur, sans modifier le code officiel (les deux fonctions du moteur sont enveloppées le temps du calcul) : quotidien = variations de position non nulles par actif ; intrajournalier = 2 ordres (ouverture, fermeture) par position réellement prise (prix d'entrée et de sortie disponibles) ; la pile additionne ses sleeves, sans compensation, comme pour les coûts. TRAIN d'une sleeve = depuis son premier jour actif, par date de signal.

**Non modifié.** `PREREGISTRATION.md` (aucun diff ; il cite toujours le chemin absolu de la machine d'origine, c'est un fichier figé et haché), `scripts/run_train_val.py`, `scripts/ouvrir_test.py`, `scripts/verdict.py`, aucun résultat, aucun paramètre. Le TEST n'a pas été lu : tous les calculs ci-dessus s'arrêtent au 2022-12-30 et `scripts/ouvrir_test.py` n'a pas été lancé.

