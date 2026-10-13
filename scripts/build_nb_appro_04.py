"""Génère notebooks/approfondissement.ipynb (puis l'exécuter avec nbconvert, voir README).
Nom unique pour ne pas être confondu avec d'autres générateurs. Les chiffres viennent de
results/approfondissement.json (scripts/run_approfondissement.py) : rien n'est retapé à la main."""
import nbformat as nbf
from pathlib import Path

nb = nbf.v4.new_notebook()
C = []


def md(t):
    C.append(nbf.v4.new_markdown_cell(t.strip("\n")))


def code(t):
    C.append(nbf.v4.new_code_cell(t.strip("\n")))


BANDEAU = ("> **EXPLORATOIRE — ne modifie pas le verdict pré-enregistré.** Analyse a posteriori sur TRAIN (≤ 2018) et VAL (2019-2022). "
           "Le TEST (≥ 2023) reste scellé, aucun paramètre des sleeves n'est touché, `PREREGISTRATION.md` n'est pas modifié.")

md(r"""
# Approfondissement du projet 04 : pourquoi aucune des 7 stratégies connues ne marche ici, et que faudrait-il de vrai pour un Sharpe net > 2 ?

""" + BANDEAU + r"""

Le verdict officiel est `ECHEC` (pile : Sharpe net VAL −5,30, brut −0,70). Ce carnet ne le rouvre pas : il **explique** l'échec avec sept
questions, chacune traitée de la même façon : *Question → Intuition → Théorème → Attente → Expérience → Résultat → Conclusion / limites*.

| # | Question | Outil |
|---|---|---|
| Q1 | Combien d'information, et sur combien de paris, faut-il pour un IR de 2 ? | loi fondamentale de Grinold / Clarke-de Silva-Thorley |
| Q2 | À quelle vitesse le signal s'éteint-il, et quel horizon le coût autorise-t-il ? | IC en fonction de l'horizon, horizon optimal sous coût |
| Q3 | Que peut-on conclure de 4 ans de VAL ? | erreur-type du Sharpe (Lo), puissance |
| Q4 | Que vaut un Sharpe trouvé après N essais ? | Sharpe maximal attendu sous H0 (Bailey-López de Prado) |
| Q5 | Pourquoi chaque sleeve échoue-t-elle ? | brut/net, Sharpe glissant, facteur de marché, régime |
| Q6 | La diversification peut-elle suffire ? | Sharpe d'une pile de N sleeves |
| Q7 | (bonus) Quelle capacité pour S1 et S6 ? | impact en racine carrée |
""")

code(r"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import Markdown, Image, display

RACINE = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(RACINE))
from alpha import donnees as d, stats
from alpha.approfondissement import theorie, diagnostics as dg, chargement as ap

R = json.loads((RACINE / "results" / "approfondissement.json").read_text(encoding="utf-8"))
TV = json.loads((RACINE / "results" / "train_val.json").read_text(encoding="utf-8"))
FIG = RACINE / "figures"
plt.rcParams.update({"figure.dpi": 100, "axes.grid": True, "grid.alpha": 0.3})
pd.set_option("display.width", 200, "display.max_columns", 30)
print(R["titre"])
print("verdict officiel (inchangé) :", R["verdict_officiel_inchange"])
print("dernier jour de données utilisé :", R["meta"]["dernier_jour_utilise"], "(TEST >= 2023-01-01 jamais chargé)")


def aff(texte):
    display(Markdown(texte.replace("$", r"\$")))   # le signe $ des textes (Md$) ne doit pas ouvrir une formule
""")

# ------------------------------------------------------------------------------------------ Q1
md(r"""
## Q1. Combien d'IC, sur combien de paris, pour un IR de 2 ?

""" + BANDEAU + r"""

**Question.** Si une stratégie gagne `IC` de corrélation entre sa prévision et le rendement suivant, sur `BR` paris indépendants par an, quel Sharpe
peut-elle espérer ? Et pour viser 2 avec la breadth de nos 7 sleeves, quel IC faudrait-il ?

**Intuition.** Chaque pari est une loterie légèrement biaisée en notre faveur. Le biais (l'IC) est minuscule, mais on rejoue la loterie des centaines de fois par an
et le hasard se moyenne : le Sharpe grandit comme la racine du nombre de paris. Ce qu'on ne parvient pas à investir (tampon, 3 longs/3 courts, plafond) est perdu :
c'est le coefficient de transfert (TC).

**Théorème (Grinold 1989 ; Clarke-de Silva-Thorley 2002).** Avec des prévisions standardisées $s_i$ (variance 1) et un rendement normalisé de corrélation $\mathrm{IC}$ avec elles,
l'alpha attendu est $\alpha_i = \mathrm{IC}\,\sigma_i s_i$ ; les poids optimaux $w_i = \alpha_i/(\lambda\sigma_i^2)$ donnent $\mathrm{IR}^2=\sum_i (\alpha_i/\sigma_i)^2=\mathrm{IC}^2 \cdot \mathrm{BR}$, et si les
poids réellement tenus ont une corrélation $\mathrm{TC}$ avec les poids optimaux :

$$\boxed{\mathrm{IR} \;\approx\; \mathrm{TC}\times \mathrm{IC}\times\sqrt{\mathrm{BR}}}\qquad\Longrightarrow\qquad \mathrm{IC}^\star=\frac{\mathrm{IR}^\star}{\mathrm{TC}\sqrt{\mathrm{BR}}},\quad \mathrm{BR}^\star=\Big(\frac{\mathrm{IR}^\star}{\mathrm{TC}\cdot \mathrm{IC}}\Big)^2 .$$

**Attente.** Un IC « très bon » en gestion active vaut 0,05 (un IC de 0,1 est rarissime). Avec ~1 800 paris indépendants par an (breadth de la pile, très généreuse), IR = 2 exige un IC proche de 0,06 sur
**chaque** sleeve ; je m'attends donc à ce que nos IC, voisins de zéro, expliquent des Sharpe bruts voisins de zéro. Je m'attends aussi à ce que la loi *suive* le Sharpe brut réalisé (c'est une identité approchée).

**Expérience (1/2) : la loi sur un monde simulé.** On fabrique N actifs, une prévision de variance 1 et des rendements d'IC connu, on investit $w\propto f/\sigma$ chaque jour et on compare le Sharpe réalisé à $\mathrm{IC}\sqrt{N\cdot252}$.
""")

code(r"""
def monde_simule(ic, n_actifs, n_jours=5040, graine=0):
    rng = np.random.default_rng(graine)
    f = rng.standard_normal((n_jours, n_actifs))                       # prévision standardisée
    sigma = 0.01
    r = sigma * (ic * f + np.sqrt(1 - ic ** 2) * rng.standard_normal((n_jours, n_actifs)))   # corr(f, r/sigma) = ic
    pnl = ((f / sigma) * r).sum(axis=1)                                 # poids proportionnels à f/sigma
    return stats.sharpe(pnl)

lignes = []
for ic in (0.01, 0.02, 0.05):
    for n in (10, 40):
        lignes.append({"IC": ic, "N actifs": n, "Sharpe simulé (20 ans)": monde_simule(ic, n),
                       "IC x racine(N x 252)": ic * np.sqrt(n * 252)})
display(pd.DataFrame(lignes).round(2))
""")

md(r"""
**Expérience (2/2) : les 7 sleeves.** Pour chaque sleeve et chaque période on mesure : l'IC (corrélation de rang entre la prévision, ou le poids, et le rendement suivant normalisé par la vol passée,
**exécuté à J+1** comme le moteur, à l'horizon de détention) ; la breadth (nombre effectif de paris indépendants des instruments, par la participation de la matrice de corrélation, × 252 / horizon de détention) ;
le TC (corrélation entre la prévision et la position pondérée du risque $w\sigma$). Contrôle de non-anticipation : les prévisions (sleeves + vol) ne dépendent pas du futur, vérifié par `tests/test_approfondissement_ic.py`.
Reproduction vivante d'une ligne (S2) depuis les données TRAIN/VAL (lecteur 1 h strict, minutes en cache) :
""")

code(r"""
base = ap.charger_base()                      # cache pickle ou pipeline officiel ; TEST jamais lu
specs = dg.specs_quotidiennes(base)
sp = specs["S2"]
ligne = {}
for p, (a, b) in dg.PERIODES.items():
    s = dg.ic_serie(sp, 10)
    r = dg.resume_ic(s, max(a, base["res"]["S2"].debut), b, 10, sp.espacement)   # dès que la sleeve est active
    ligne[p] = (r["ic"], r["t_nw"])
ref = {p: (R["Q1_grinold"]["sleeves"]["S2"][p]["ic"], R["Q1_grinold"]["sleeves"]["S2"][p]["t_nw_ic"]) for p in ("TRAIN", "VAL")}
print("IC de S2 à 10 jours, recalculé ici :", {p: (round(v[0], 4), round(v[1], 2)) for p, v in ligne.items()})
print("valeurs du JSON                    :", {p: (round(v[0], 4), round(v[1], 2)) for p, v in ref.items()})
assert all(abs(ligne[p][0] - ref[p][0]) < 1e-9 for p in ligne)
""")

md(r"""**Résultat.** Tableau complet (IC, TC, breadth, IR prédit, Sharpe brut réalisé, IC et breadth requis pour IR = 2).""")

code(r"""
lignes = []
for nom, blocs in R["Q1_grinold"]["sleeves"].items():
    for p, b in blocs.items():
        lignes.append({"sleeve": nom, "période": p, "IC": b["ic"], "t NW": b["t_nw_ic"], "TC": b["tc"], "N eff": b["n_effectif"],
                       "breadth/an": b["breadth"], "IR prédit": b.get("ir_predit"), "Sharpe brut": b["sharpe_brut"],
                       "écart (z)": b.get("z_ecart_predit_vs_realise"), "IC requis IR=2": b.get("ic_requis_pour_ir_2"),
                       "breadth requise": b.get("breadth_requise_pour_ir_2")})
display(pd.DataFrame(lignes).set_index(["sleeve", "période"]).round(3))
pile = R["Q1_grinold"]["pile"]
display(pd.DataFrame({p: pile[p] for p in ("TRAIN", "VAL")}).round(3))
print("accord prédit/réalisé :", pile["accord_predit_realise"])
display(Image(str(FIG / "appro_q1_grinold.png")))
""")

md(r"""**Conclusion / limites.**""")
code(r"""aff(R["conclusions"]["Q1"])""")
md(r"""
*Limites.* La breadth est une notion fragile : la participation (nombre effectif d'instruments) ignore la corrélation *temporelle* des signaux lents, d'où l'horizon de détention au dénominateur. L'IC de S6 contient la prime de risque
actions (sleeve long seul) : la loi décrit l'IR *actif*, pas le Sharpe total d'un bêta. L'IC de chaque période est lui-même bruité (t de Newey-West ≤ 2 presque partout) : l'accord avec le Sharpe réalisé est un ordre de grandeur sur
14 couples, pas une preuve. Les sleeves intrajournalières (S4, S5, S7) ont un IC mesuré sur toute la fenêtre ; leur TC vaut ≈ 1 par construction (poids = direction × k / σ).
""")

# ------------------------------------------------------------------------------------------ Q2
md(r"""
## Q2. À quelle vitesse le signal s'éteint-il, et quel horizon le coût autorise-t-il ?

""" + BANDEAU + r"""

**Question.** L'IC dépend de l'horizon sur lequel on mesure le rendement suivant. Où le signal paie-t-il, combien de temps vit-il, et comment l'horizon se règle-t-il contre le coût de rotation ?

**Intuition.** Un signal est une information périssable : plus on attend, moins elle vaut. Pour la monétiser il faut la porter ; mais chaque changement de position coûte. Il y a donc une durée de portage optimale :
tenir trop peu paie trop de coûts, tenir trop longtemps fait porter une information morte.

**Théorème (horizon optimal sous coût).** Si le gain cumulé de prévision à l'horizon $h$ est $G(h)=A\,(1-e^{-h/\tau})$ et si chaque ré-signalisation coûte $C$, le rendement net **par jour** est $N(h)=\dfrac{G(h)-C}{h}$.
Son maximum vérifie $N'(h)=0 \iff G'(h^\star)=N(h^\star)$ (le gain marginal égale le rendement net moyen) soit, avec $u=h/\tau$ :

$$1-(1+u^\star)\,e^{-u^\star}=\frac{C}{A},\qquad h^\star=\tau\,u^\star\;\approx\;\tau\sqrt{2C/A}\ \text{ si } C\ll A ;\quad \text{pas de solution (jamais rentable) si } C\ge A .$$

**Attente.** Un signal de momentum doit avoir un IC croissant avec l'horizon puis décroissant ; un signal de retournement court doit avoir un IC fort à court terme et nul au-delà ; les signaux intrajournaliers doivent s'éteindre en minutes.
Je m'attends à ce que S2 et S3 ne soient pas aux horizons où leur règle les tient (63 j de momentum tenu 1-2 semaines ; 5 j de retournement tenu 1 semaine).

**Expérience (1/2) : le théorème sur un signal à décroissance exponentielle connue.**
""")

code(r"""
A, tau = 10.0, 5.0
fig, ax = plt.subplots(figsize=(7, 4))
h = np.linspace(0.2, 60, 400)
for cout, c in ((0.5, "C0"), (1.5, "C1"), (4.0, "C2")):
    hs = theorie.horizon_optimal_exponentiel(A, tau, cout)
    grille = h[np.argmax(theorie.rendement_net_par_jour(h, A, tau, cout))]
    ax.plot(h, theorie.rendement_net_par_jour(h, A, tau, cout), color=c, label=f"C = {cout} : h* théorème {hs:.1f} j, grille {grille:.1f} j")
    ax.axvline(hs, color=c, ls=":")
ax.axhline(0, color="k", lw=0.8)
ax.set_xlabel("horizon h (jours)"); ax.set_ylabel("rendement net par jour (G(h) - C)/h"); ax.legend(fontsize=8)
ax.set_title("A = 10, tau = 5 jours : plus le coût est haut, plus on tient longtemps")
plt.show()
""")

md(r"""**Expérience (2/2) : les 7 sleeves.** IC cumulé à 1, 2, 5, 10, 20, 60 jours (S1, S2, S3, S6 ; exécution à J+1), IC *marginal* du seul jour h (demi-vie de l'IC), autocorrélation du signal (demi-vie du signal), profil gain/coût de re-signalisation
(S1, S2, S3), et pour S4, S5, S7 l'IC en minutes sur le 1 minute (cache TRAIN/VAL). Reproduction vivante de la courbe de S3 :""")

code(r"""
sp3 = specs["S3"]
H = dg.H_GRILLE
vivant = {h: dg.resume_ic(dg.ic_serie(sp3, h), d.DEBUT_DONNEES, d.FIN_VAL, h, sp3.espacement)["ic"] for h in H}
json_ = {h: R["Q2_decroissance"]["sleeves_quotidiennes"]["S3"]["ic"]["cumule"]["TOUT"][str(h)]["ic"] for h in H}
print("IC cumulé de S3 (TRAIN+VAL) recalculé :", {h: round(v, 4) for h, v in vivant.items()})
assert all(abs(vivant[h] - json_[h]) < 1e-9 for h in H)
""")

md(r"""**Résultat.**""")
code(r"""
q2 = R["Q2_decroissance"]
lignes = []
for nom, s in q2["sleeves_quotidiennes"].items():
    for p in ("TRAIN", "VAL", "TOUT"):
        lignes.append({"sleeve": nom, "période": p, **{f"h={h}": s["ic"]["cumule"][p][str(h)]["ic"] for h in dg.H_GRILLE}})
display(pd.DataFrame(lignes).set_index(["sleeve", "période"]).round(3))
print("t de Newey-West de l'IC cumulé TRAIN+VAL :")
display(pd.DataFrame({nom: {f"h={h}": s["ic"]["cumule"]["TOUT"][str(h)]["t_nw"] for h in dg.H_GRILLE} for nom, s in q2["sleeves_quotidiennes"].items()}).T.round(1))
dv = pd.DataFrame({nom: {"demi-vie du signal (j)": s["demi_vie_signal_jours"], "demi-vie IC TRAIN (j)": s["demi_vie_ic_marginal_jours"]["TRAIN"],
                         "demi-vie IC VAL (j)": s["demi_vie_ic_marginal_jours"]["VAL"]} for nom, s in q2["sleeves_quotidiennes"].items()}).T
display(dv.round(1))
""")
code(r"""
lignes = []
for nom in ("S1", "S2", "S3"):
    pg = q2["sleeves_quotidiennes"][nom]["profil_gain_cout"]
    for p in ("TRAIN", "VAL"):
        for h in dg.H_GRILLE:
            x = pg[p][str(h)]
            if x:
                lignes.append({"sleeve": nom, "période": p, "h": h, "gain brut (bps)": x["gain_bps"], "coût (bps)": x["cout_bps"], "net bps/jour": x["net_bps_par_jour"]})
tab = pd.DataFrame(lignes)
display(tab.pivot_table(index=["sleeve", "période"], columns="h", values="net bps/jour").round(2))
for nom in ("S4", "S5", "S7"):
    mm = q2["minutes"][nom]
    cout = next(v["cout_aller_retour_bps"] for v in mm["TOUT"].values() if v)
    display(Markdown(f"**{nom}** : IC de rang (haut) et gain brut moyen par trade en bps (bas) selon les minutes après l'entrée ; coût aller-retour moyen {cout:.2f} bps."))
    cles = sorted(mm["TOUT"], key=int)
    display(pd.DataFrame({p: {f"{k} min": mm[p][k]["ic"] if mm[p][k] else None for k in cles} for p in ("TRAIN", "VAL", "TOUT")}).T.round(3))
    display(pd.DataFrame({p: {f"{k} min": mm[p][k]["gain_bps"] if mm[p][k] else None for k in cles} for p in ("TRAIN", "VAL", "TOUT")}).T.round(2))
delais = q2["minutes"]["S7_delai_bloc_30min"]
repliquent = [h for h, v in delais.items() if abs(v["TRAIN"]["30"]["t_nw"]) > 2 and abs(v["VAL"]["30"]["t_nw"]) > 2
              and np.sign(v["TRAIN"]["30"]["ic"]) == np.sign(v["VAL"]["30"]["ic"])]
display(Markdown("**S7, IC du signal du matin (16h→10h) sur chaque demi-heure de la séance** (début du bloc, heure de New York ; entre parenthèses le t de Newey-West). "
                 f"Blocs où le même signe tient avec |t| > 2 en TRAIN **et** en VAL : {repliquent if repliquent else 'aucun'}."))
display(pd.DataFrame({h: {p: f"{v[p]['30']['ic']:+.3f} (t {v[p]['30']['t_nw']:+.1f})" for p in ("TRAIN", "VAL")} for h, v in delais.items()}).T)
display(Image(str(FIG / "appro_q2_decroissance.png")))
""")
md(r"""**Conclusion / limites.**""")
code(r"""aff(R["conclusions"]["Q2"])""")
md(r"""
*Limites.* (1) Les constats sur S3 et S2 sont **a posteriori** : six horizons × quatre sleeves × trois périodes ont été regardés ; un IC à t ≈ 2,8 parmi tant de lectures peut être de la chance. Ils indiquent où chercher dans un NOUVEAU pré-enregistrement
(avec N cumulé), pas une sleeve à rajouter. (2) Le profil gain/coût utilise des positions « de principe » (signe de la prévision ; 3 meilleurs / 3 pires), pas les poids exacts des sleeves, et un coût de re-signalisation constant par jambe.
(3) La demi-vie de l'IC n'est définie que si l'IC marginal est positif et décroissant sur au moins 3 points : ici elle l'est rarement, ce qui est déjà une information.
""")

# ------------------------------------------------------------------------------------------ Q3
md(r"""
## Q3. Que peut-on conclure de 4 ans de VAL ?

""" + BANDEAU + r"""

**Question.** Quelle est l'incertitude d'un Sharpe estimé sur 1 044 jours, quel Sharpe vrai peut-on détecter avec 80 % de puissance, et quelle est la probabilité qu'une stratégie de vrai Sharpe 0,5 affiche un Sharpe VAL aussi mauvais que celui observé ?

**Intuition.** Un Sharpe est une moyenne divisée par un écart-type : sa précision dépend du nombre d'observations, pas du nombre de lignes de code. Quatre ans de données donnent un Sharpe à ±1 près : il est impossible de distinguer un vrai 0,5 d'un vrai 0.

**Théorème (Lo 2002 ; Mertens 2002).** Pour des rendements iid, le Sharpe par jour estimé a une variance asymptotique $\dfrac{1+\tfrac12 SR_j^2}{n}$ ; avec asymétrie $\gamma_3$ et kurtosis $\gamma_4$ (Mertens) : $\dfrac{1-\gamma_3 SR_j+\tfrac{\gamma_4-1}{4}SR_j^2}{n}$.
Annualisé ($SR=\sqrt{252}\,SR_j$, $Y=n/252$ années) : $\mathrm{SE}(SR)=\sqrt{\dfrac{1+SR^2/504}{Y}}\approx \dfrac1{\sqrt Y}$.
Le plus petit Sharpe vrai détecté avec une puissance $1-\beta$ par un test unilatéral de niveau $\alpha$ est

$$SR_{\min}=z_{1-\alpha}\,\mathrm{SE}(0)+z_{1-\beta}\,\mathrm{SE}(SR_{\min})\approx\frac{z_{1-\alpha}+z_{1-\beta}}{\sqrt Y},\qquad Y_{\text{requis}}(SR)=\Big(\frac{z_{1-\alpha}+z_{1-\beta}\sqrt{1+SR^2/504}}{SR}\Big)^2 .$$

**Attente.** SE ≈ 0,5 ; $SR_{\min}\approx 1{,}2$ (1,6 avec Bonferroni sur 7 sleeves) ; il faut ~25 ans pour confirmer un vrai Sharpe de 0,5. Donc les sleeves à Sharpe VAL proche de zéro ne sont pas « prouvées nulles ».

**Expérience.** (a) Monte-Carlo de la formule sur du bruit blanc ; (b) probabilité $P(\widehat{SR}\le SR_{\text{obs}}\mid SR_{\text{vrai}}=0{,}5)$ par trois méthodes : analytique, simulation paramétrique, bootstrap stationnaire (blocs de 20 jours) qui recentre les rendements *observés* de la sleeve.
""")

code(r"""
rng = np.random.default_rng(1)
n = 1044
x = rng.standard_normal((4000, n))
sh = x.mean(axis=1) / x.std(axis=1, ddof=1) * np.sqrt(252)
print(f"écart-type empirique du Sharpe sur bruit blanc : {sh.std(ddof=1):.3f}   formule de Lo : {theorie.se_sharpe(0.0, n):.3f}")
print("Sharpe minimal détectable à 80 % (4 ans) :", {k: round(v, 2) for k, v in R["Q3_puissance"]["sharpe_min_detectable_80pct"].items()})
print("années pour détecter (80 %, unilatéral 5 %) :", {k: round(v, 1) for k, v in R["Q3_puissance"]["annees_pour_detecter_80pct_unilateral"].items()})
""")
md(r"""**Résultat.**""")
code(r"""
ps = R["Q3_puissance"]["par_serie"]
display(pd.DataFrame({k: {"Sharpe net VAL": v["sharpe_net_val"], "SE Lo": v["se_lo_gaussienne"], "SE Mertens": v["se_mertens_asym_kurt"], "kurtosis": v["kurtosis"],
                          "P(vrai 0,5) analytique": v["p_sharpe_vrai_05_donne_au_plus_obs"]["analytique"],
                          "P(vrai 0,5) paramétrique": v["p_sharpe_vrai_05_donne_au_plus_obs"]["parametrique"],
                          "P(vrai 0,5) bootstrap": v["p_sharpe_vrai_05_donne_au_plus_obs"]["bootstrap"],
                          "P(vrai 0,25) analytique": v["p_sharpe_vrai_025_donne_au_plus_obs_analytique"],
                          "P(vrai 1,0) analytique": v["p_sharpe_vrai_10_donne_au_plus_obs_analytique"]} for k, v in ps.items()}).T.round(4))
display(Image(str(FIG / "appro_q3_puissance.png")))
""")
md(r"""**Conclusion / limites.**""")
code(r"""aff(R["conclusions"]["Q3"])""")
md(r"""
*Limites.* La SE de Lo suppose des rendements iid ; l'autocorrélation (positions persistantes) et les queues épaisses la modifient (SE de Mertens ci-dessus, bootstrap par blocs), mais pas l'ordre de grandeur. Les probabilités conditionnelles à
« vrai Sharpe = 0,5 » sont des tests d'hypothèse ponctuelle, pas des probabilités a posteriori que la sleeve soit à 0,5.
""")

# ------------------------------------------------------------------------------------------ Q4
md(r"""
## Q4. Que vaut un Sharpe trouvé après N essais ?

""" + BANDEAU + r"""

**Question.** Si on teste N stratégies sans aucun edge, quel est le meilleur Sharpe qu'on trouvera en moyenne ? Que valent N = 8 (ce projet) et le nombre d'essais documenté de l'historique AWB ? Que dire d'un « Sharpe > 2 » obtenu par recherche répétée ?

**Intuition.** Le meilleur de N loteries est meilleur que la loterie moyenne, mécaniquement. Un backtest court a des Sharpe très dispersés (SE élevée), donc le meilleur de beaucoup d'essais a l'air excellent par pur hasard.

**Théorème (Bailey-López de Prado 2014).** Pour N Sharpe estimés indépendants, centrés en 0, d'écart-type $\sigma$, avec $\gamma\approx0{,}5772$ la constante d'Euler-Mascheroni :

$$\mathbb E[\max_N \widehat{SR}]\;\approx\;\sigma\Big((1-\gamma)\,\Phi^{-1}\!\big(1-\tfrac1N\big)+\gamma\,\Phi^{-1}\!\big(1-\tfrac1{Ne}\big)\Big),\qquad \mathbb P(\max_N\ge x)=1-\Phi(x/\sigma)^N .$$

**Attente.** Avec $\sigma=\mathrm{SE}$ d'un Sharpe VAL ≈ 0,49 : N = 8 → ≈ 0,7 ; N = 134 → ≈ 1,3 ; un Sharpe de 2 par pur hasard demande des milliers d'essais sur 4 ans mais seulement ~25 sur 1 an.

**Expérience.** On vérifie la formule par simulation de N stratégies de bruit blanc (1 044 jours), puis on l'applique aux nombres d'essais **cités** dans `docs/idees/*_verdict.json` (rien n'est estimé).
""")

code(r"""
sig = theorie.se_sharpe(0.0, 1044)
lignes = []
for N in (2, 8, 50):
    moy, sd = theorie.simuler_sharpe_max(N, 1044, n_rep=400, graine=N)
    lignes.append({"N": N, "formule": theorie.sharpe_max_attendu(N, sig), "exact gaussien": theorie.esperance_max_gaussien(N) * sig, "simulation (400 rép.)": moy})
display(pd.DataFrame(lignes).round(3))
""")
md(r"""**Résultat.**""")
code(r"""
q4 = R["Q4_tests_multiples"]
display(pd.DataFrame(q4["validation_formule_vs_simulation"]).T.round(3))
display(pd.DataFrame(q4["historique_awb"]).set_index("noeud").round(4))
display(pd.DataFrame(q4["n_essais_pour_sharpe_2_selon_duree_backtest_annees"]).T.rename(columns={"n_essais_pour_sr_attendu_2": "N pour un Sharpe 2 par hasard"}).round(3))
print("N pour que le hasard fabrique un Sharpe de ... sur 4 ans :", {k: round(v) for k, v in q4["n_essais_pour_sharpe_cible_sur_4_ans"].items()})
print("illustration :", q4["illustration_selection_1770_paires"])
display(pd.DataFrame({"SR0 annualisé": {"prereg (variance observée des 8 Sharpe)": q4["dsr"]["sr0_annualise_prereg_variance_observee"],
                                         "théorique (variance = SE², N = 8)": q4["dsr"]["sr0_annualise_variance_theorique"]}}).round(2))
display(pd.Series(q4["dsr"]["psr_contre_sr0_theorique_exploratoire"], name="PSR contre le SR0 théorique (exploratoire)").round(4))
display(Image(str(FIG / "appro_q4_tests_multiples.png")))
""")
md(r"""**Conclusion / limites.**""")
code(r"""aff(R["conclusions"]["Q4"])""")
md(r"""
*Limites.* La formule suppose des essais indépendants et de même variance ; les essais d'AWB sont fortement corrélés (mêmes données, variantes d'une idée), donc le N *effectif* est plus petit que N, et le seuil plus bas. Le projet ne tient pas de
compteur cumulé unique : 134 est un plancher déclaré par PIVOT-4, pas une mesure. Les « 1 770 paires » ne sont pas un compte d'essais, seulement l'illustration d'une sélection de la meilleure paire. Le seuil théorique ci-dessus est un
diagnostic exploratoire : le DSR pré-enregistré (SR0 = 6,23) reste celui du verdict.
""")

# ------------------------------------------------------------------------------------------ Q5
md(r"""
## Q5. Pourquoi chaque sleeve échoue-t-elle ?

""" + BANDEAU + r"""

**Question.** Pour chacune des 7 sleeves (et la pile), l'échec vient-il de l'absence d'alpha brut, des coûts, d'un régime de marché ou d'une instabilité dans le temps ?

**Intuition.** Quatre suspects : (1) il n'y a rien à gagner avant coûts ; (2) il y a un peu, mais les coûts le mangent ; (3) l'effet ne vit que dans certains régimes (volatilité haute/basse, marché actions haussier) ; (4) il vit à certaines époques et
disparaît à d'autres. On les départage avec des mesures qui n'utilisent que TRAIN et VAL.

**Théorème (test d'hétérogénéité de Cochran).** Si le Sharpe vrai est constant, les Sharpe de $k$ années civiles, d'erreurs-types $\mathrm{SE}_a$, vérifient
$$Q=\sum_{a=1}^{k}\Big(\frac{\widehat{SR}_a-\overline{SR}_w}{\mathrm{SE}_a}\Big)^2\;\sim\;\chi^2_{k-1},\qquad \overline{SR}_w=\frac{\sum_a \widehat{SR}_a/\mathrm{SE}_a^2}{\sum_a 1/\mathrm{SE}_a^2}.$$
Un $p$ de $Q$ élevé signifie que la variation d'une année à l'autre est compatible avec du simple bruit d'échantillonnage (SE d'un Sharpe annuel ≈ 1).

**Attente.** S4 et S7 : coûts énormes mais brut quasi nul ; S1 et S6 : brut faible mais positif en TRAIN ; S6 : très corrélée aux actions. Je m'attends à ce que « pas d'alpha brut » domine.

**Règle de décision (écrite avant de lire le tableau).** brut ≥ 0,30 sur TRAIN **et** VAL → « coût » si les coûts retirent plus de la moitié du brut VAL ; brut ≥ 0,30 sur **une seule** période → « régime » (corrélation ≥ 0,5 avec le facteur indices, ou écart de Sharpe
vol haute − vol basse ≥ 1) sinon « instabilité » ; sinon « pas d'alpha brut » (avec « + coût amplificateur » si les coûts retirent plus de 0,5 point de Sharpe en VAL). Le facteur de marché simple est la moyenne équipondérée des rendements quotidiens des 58 actifs ;
le régime est le tercile (bornes TRAIN) de la vol réalisée 63 jours du facteur « 8 indices », décalée d'un jour.

**Expérience.** Calcul sur les rendements quotidiens bruts et nets (TRAIN+VAL) de `pipeline.calculer_sleeves`.
""")

code(r"""
q5 = R["Q5_anatomie"]
lignes = []
for nom, v in q5["sleeves"].items():
    lignes.append({"série": nom, "brut TRAIN": v["sharpe_brut"]["TRAIN"], "brut VAL": v["sharpe_brut"]["VAL"], "net TRAIN": v["sharpe_net"]["TRAIN"], "net VAL": v["sharpe_net"]["VAL"],
                   "coût/an VAL": v["cout_annuel"]["VAL"], "rotation/an VAL": v["rotation_annuelle_val"],
                   "perte de Sharpe due aux coûts (VAL)": v["cause"]["perte_de_sharpe_due_aux_couts_val"]})
display(pd.DataFrame(lignes).set_index("série").round(3))
""")
md(r"""**Résultat.**""")
code(r"""
lignes = []
for nom, v in q5["sleeves"].items():
    lignes.append({"série": nom, "Sharpe annuel min": min(v["sharpe_annuel_calendaire_net"].values()), "max": max(v["sharpe_annuel_calendaire_net"].values()),
                   "part d'années > 0": v["part_annees_sharpe_net_positif"], "Q": v["constance"]["q"], "p (constance)": v["constance"]["p_constance"],
                   "glissant 1 an : écart-type": v["sharpe_glissant_1an_net"]["ecart_type"], "corr. indices TRAIN": v["facteur"]["TRAIN"]["indices"]["correlation"],
                   "corr. indices VAL": v["facteur"]["VAL"]["indices"]["correlation"], "bêta indices VAL": v["facteur"]["VAL"]["indices"]["beta"],
                   "corr. 58 actifs VAL": v["facteur"]["VAL"]["tous_actifs"]["correlation"]})
display(pd.DataFrame(lignes).set_index("série").round(3))
display(pd.DataFrame({nom: {g: v["regime"][g]["sharpe_brut"] for g in ("bas", "moyen", "haut")} for nom, v in q5["sleeves"].items()}).T.round(2))
print("bornes des terciles de vol (TRAIN) :", [round(x, 3) for x in q5["regime_vol"]["seuils_terciles_train"]])
tab = pd.DataFrame({nom: {"cause principale": v["cause"]["cause"], "précision": v["cause"]["precision"]} for nom, v in q5["sleeves"].items()}).T
display(tab)
display(Image(str(FIG / "appro_q5_sharpe_glissant.png")))
display(Image(str(FIG / "appro_q5_regimes_facteur.png")))
""")
md(r"""**Conclusion / limites.**""")
code(r"""aff(R["conclusions"]["Q5"])""")
md(r"""
*Limites.* Le seuil de 0,30 (≈ 0,6 erreur-type d'un Sharpe sur 4 ans) est un choix explicite : la règle classe, elle ne prouve pas. Les Sharpe par régime et par année reposent sur peu d'observations (S5 : 12 trades par an et par paire, kurtosis 68) : à lire comme des ordres de grandeur.
Le facteur « 58 actifs équipondérés » mélange des paires cotées dans les deux sens contre l'USD (un signe arbitraire) : c'est pourquoi le facteur « 8 indices » est montré à côté. Les coûts sont ceux du fichier, constants sur toute la période.
""")

# ------------------------------------------------------------------------------------------ Q6
md(r"""
## Q6. La diversification peut-elle suffire ?

""" + BANDEAU + r"""

**Question.** Combien de sleeves de Sharpe net $s$, de corrélation moyenne $\bar\rho$ (observée en VAL), faut-il empiler pour atteindre 2 ?

**Intuition.** Additionner des paris indépendants fait monter le Sharpe comme $\sqrt N$ ; mais la moindre corrélation le plafonne : au-delà d'un certain nombre de sleeves on ne diversifie plus rien. Et diversifier ne crée pas d'edge : cela multiplie un Sharpe individuel qui doit déjà exister.

**Théorème.** $N$ sleeves de Sharpe $s$, de volatilité égale et de corrélation moyenne $\bar\rho$, en risque égal :
$$SR_{\text{pile}}=s\sqrt{\frac{N}{1+(N-1)\bar\rho}}\;\xrightarrow[N\to\infty]{}\;\frac{s}{\sqrt{\bar\rho}},\qquad N_{\text{requis}}(SR^\star)=\frac{{SR^\star}^2(1-\bar\rho)}{s^2-{SR^\star}^2\bar\rho}\quad(\text{impossible si } s^2\le {SR^\star}^2\bar\rho).$$
Avec les vrais Sharpe $s_i$ et la vraie corrélation $\mathbf R$ (risque égal) : $SR=\dfrac{\sum_i s_i}{\sqrt{\mathbf 1^\top\mathbf R\,\mathbf 1}}$.

**Attente.** Sous indépendance il faut 16 sleeves à 0,5 ; avec $\bar\rho\approx0{,}026$, environ 27. Et la formule doit retrouver le Sharpe réalisé de la pile (−5,3) en y mettant les Sharpe réels.

**Expérience.**
""")

code(r"""
q6 = R["Q6_diversification"]
rho = q6["rho_moyen_val"]
lignes = []
for s in (0.3, 0.5, 0.7, 1.0):
    for r_ in (0.0, rho, 0.05, 0.10):
        lignes.append({"s": s, "rho": round(r_, 3), "N requis": theorie.n_sleeves_requis(s, r_), "plafond s/racine(rho)": (s / np.sqrt(r_) if r_ > 0 else np.inf)})
display(pd.DataFrame(lignes).pivot(index="s", columns="rho", values="N requis").round(1))
noms = ["S1", "S2", "S3", "S4", "S5", "S6", "S7"]
corr = pd.DataFrame(TV["correlations"]["VAL"]).loc[noms, noms].to_numpy()
s_val = np.array([TV["series"][k]["VAL"]["sharpe_net"] for k in noms])
m = theorie.sharpe_pile_matrice(s_val, corr)
print(f"corrélation moyenne observée (VAL) : {theorie.correlation_moyenne(corr):.4f}")
print(f"pile à risque égal avec les Sharpe réels : formule {m['risque_egal']:.2f}  vs réalisée {TV['series']['PILE']['VAL']['sharpe_net']:.2f}")
""")
md(r"""**Résultat.**""")
code(r"""
print({k: q6[k] for k in ("rho_moyen_val", "n_sleeves_requis_sharpe_05_rho_observe", "n_sleeves_requis_sharpe_05_independantes", "sharpe_individuel_requis_avec_7_sleeves",
                          "sharpe_pile_si_7_sleeves_de_sharpe_05", "plafond_sharpe_pile_sleeves_05_rho_observe", "meilleur_sharpe_net_val", "meilleure_sleeve",
                          "pile_formule_risque_egal_avec_sharpe_reels", "pile_optimale_theorique_sharpe_reels", "pile_realisee_val")})
display(Image(str(FIG / "appro_q6_diversification.png")))
""")
md(r"""**Conclusion / limites.**""")
code(r"""aff(R["conclusions"]["Q6"])""")
md(r"""
*Limites.* La corrélation moyenne est estimée sur 4 ans (comme les Sharpe) ; la formule suppose des Sharpe et des volatilités égaux. Chercher 27 sleeves « de Sharpe vrai 0,5 » est lui-même soumis à la Q4 : parmi des sleeves candidates, repérer celles qui ont vraiment 0,5 demande des
décennies d'historique (Q3). Le « Sharpe optimal théorique » avec les Sharpe réalisés est de l'in-sample : il n'est donné qu'à titre de borne.
""")

# ------------------------------------------------------------------------------------------ Q7
md(r"""
## Q7 (bonus). Quelle capacité pour S1 et S6 ?

""" + BANDEAU + r"""

**Question.** À partir de quel capital l'impact de marché mange-t-il le rendement net de S1 (trend following) et de S6 (actions gérées par la vol) ?

**Intuition.** Les coûts du fichier sont des coûts de petit porteur (spread fixe). Un gros capital déplace le prix : le coût par dollar traité croît avec la taille de l'ordre.

**Théorème (impact en racine carrée, Almgren ; Bouchaud).** Un ordre de taille $Q$ sur un actif d'écart-type journalier $\sigma$ et de volume journalier $V$ coûte en fraction du montant traité $Y\sigma\sqrt{Q/V}$. Pour un capital $A$ et des variations de position $|\Delta e_{t,i}|$ (fraction du capital) :
$$\text{impact annuel}(A)=\sqrt A\;K,\qquad K=\frac1{\text{années}}\sum_{t,i}\frac{Y\,\sigma_{t,i}\,|\Delta e_{t,i}|^{3/2}}{\sqrt{V_i}},\qquad A_{\max}=\Big(\frac{r_{\text{net avant impact}}}{K}\Big)^2 .$$

**Attente.** Avec des volumes de grandes liquidités, l'impact reste négligeable jusqu'à des milliards : la capacité ne sera pas le goulot.

**Expérience.** Hypothèses d'ordre de grandeur, **non sourcées** (le fichier de prix n'a pas de volume, le volume FX est nul) : ADV de 1e10 $/jour par paire FX, 5e10 par indice, 5e9 par matière première ; $Y=1$. À remplacer par les volumes réels du courtier.
""")
code(r"""
q7 = R["Q7_capacite"]
print(q7["hypotheses"])
""")
md(r"""**Résultat.**""")
code(r"""
lignes = []
for nom, blocs in q7["sleeves"].items():
    for p, b in blocs.items():
        lignes.append({"sleeve": nom, "période": p, "brut/an": b["rendement_brut_annuel"], "coût réel/an": b["cout_reel_annuel"], "net avant impact": b["rendement_net_avant_impact"],
                       "impact/an à 1e8 $": b["impact_annuel_a_1e8_usd"], "impact/an à 1e9 $": b["impact_annuel_a_1e9_usd"],
                       "capacité (Md$)": b["capacite_usd"] / 1e9, "$ où impact = coût réel (Md$)": (b["usd_ou_impact_egale_cout_reel"] or 0) / 1e9})
display(pd.DataFrame(lignes).set_index(["sleeve", "période"]).round(4))
display(Image(str(FIG / "appro_q7_capacite.png")))
""")
md(r"""**Conclusion / limites.**""")
code(r"""aff(R["conclusions"]["Q7"])""")
md(r"""
*Limites.* Ordre de grandeur uniquement : volumes supposés, un seul préfacteur, loi en racine carrée supposée valable bien au-delà de son domaine calibré, pas d'impact croisé entre sleeves ni de décroissance de l'impact. Capacité ∝ ADV ; ×0,1 sur l'ADV donne ×0,1 sur la capacité.
Pour S1 en VAL (brut négatif) et toute sleeve à brut ≤ coût, la capacité est nulle quelle que soit l'ADV.
""")

# ------------------------------------------------------------------------------------------ synthèse
md(r"""
## Ce qu'il faudrait de vrai pour un Sharpe net > 2

""" + BANDEAU)
code(r"""
for i, ligne in enumerate(R["conclusions"]["synthese_pour_sharpe_2"], 1):
    aff(f"{i}. {ligne}")
""")
md(r"""
En une phrase : **un Sharpe net de 2 demande soit un IC durable de l'ordre de 0,06 sur toutes les sleeves d'une pile de ~1 800 paris indépendants par an, soit ~27 sleeves de Sharpe net réel 0,5 peu corrélées, chacune confirmée par des
décennies de données, sous déflation par le N d'essais réel et lue une seule fois sur un TEST scellé.** Rien de tel n'existe dans les 7 sleeves de la littérature essayées ici.

Ce carnet est **exploratoire** : il ne change ni le verdict `ECHEC`, ni le pré-enregistrement, ni le statut du TEST (scellé).
""")

nb["cells"] = C
nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                  "language_info": {"name": "python"}}
out = Path(__file__).resolve().parents[1] / "notebooks" / "approfondissement.ipynb"
nbf.write(nb, out)
print("ok", out)
