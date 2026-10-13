"""Écrit dans README.md, docs/resultats_detailles.md et docs/approfondissement.md les blocs de chiffres, LUS dans results/.

Les blocs sont délimités par des balises HTML (invisibles sur GitHub) et réécrits à chaque exécution :
  README.md                 AUTO:CLES  AUTO:FRAIS  AUTO:METRIQUES  AUTO:OVERFIT  AUTO:VARIANTES  AUTO:CONTROLE
  docs/resultats_detailles.md   AUTO:DETAIL
  docs/approfondissement.md     AUTO:COUTS  AUTO:CONTROLE_DETAIL
Aucun chiffre de ces blocs n'est tapé à la main. Aucune donnée de marché requise, TEST jamais chargé.
Les rendements annuels inférieurs à −100 % (impossibles pour un capital réel) sont affichés « ruine » : voir `rend()`.

Usage : python scripts/generer_readme_tete.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

import pandas as pd  # noqa: E402

from alpha import stats as st  # noqa: E402

RESULTATS = RACINE / "results"
FICHIERS = {
    "README.md": ("CLES", "FRAIS", "METRIQUES", "OVERFIT", "VARIANTES", "CONTROLE"),
    "docs/resultats_detailles.md": ("DETAIL",),
    "docs/approfondissement.md": ("COUTS", "CONTROLE_DETAIL"),
}
SERIES = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "PILE"]
COURT = {"S1": "S1 Trend following", "S2": "S2 Momentum devises", "S3": "S3 Retournement devises", "S4": "S4 Saisonnalité FX",
         "S5": "S5 Fixing fin de mois", "S6": "S6 Actions vol-gérées", "S7": "S7 Momentum SPX intraj.", "PILE": "**PILE (7 sleeves)**"}
BROKERS = {"IG": "IG", "TICKMILL": "Tickmill", "FTS": "FTS Prime", "FBS": "FBS", "TRADING212": "Trading 212", "PEPPERSTONE": "Pepperstone"}


# ------------------------------------------------------------------ formats français
def n(x, d=2):
    if x is None:
        return "n/d"
    return f"{x:.{d}f}".replace(".", ",").replace("-", "−")


def pct(x, d=1):
    return "n/d" if x is None else n(100 * x, d) + " %"


def rend(x, d=1):
    """Rendement annuel net : « ruine » s'il est inférieur à −100 % (un capital réel ne peut pas perdre plus que tout).

    La valeur du JSON est la moyenne quotidienne × 252 (arithmétique, non composée) ; la série continue après la ruine, rien n'est liquidé."""
    if x is not None and x < -1.0:
        return "ruine (< −100 %)"
    return pct(x, d)


def entier(x):
    return f"{round(x):,}".replace(",", " ")


def p3(x):
    """Probabilité : « < 0,001 » si négligeable."""
    return "< 0,001" if x < 0.001 else n(x, 3)


# ------------------------------------------------------------------ lecture des résultats
def charger() -> dict:
    lire = lambda nom: json.loads((RESULTATS / nom).read_text(encoding="utf-8"))  # noqa: E731
    return {
        "tv": lire("train_val.json"), "tr": lire("reproduction_et_trades.json"),
        "csv": pd.read_csv(RESULTATS / "rendements_train_val.csv", index_col=0, parse_dates=True),
        "frais": pd.read_csv(RACINE / "data" / "frais_editable.csv", encoding="utf-8", encoding_errors="replace"),
        "appro": lire("approfondissement.json"), "cp": lire("controle_positif.json"), "sc": lire("sensibilite_couts_exploratoire.json"),
    }


def periodes(tv, csv, k):
    """Statistiques complémentaires par période (taux de gain, Calmar, PSR TRAIN) pour la série k."""
    fin_train = pd.Timestamp(tv["meta"]["periodes"]["TRAIN"][1])
    debut = pd.Timestamp(tv["series"][k]["debut_actif"])
    brut, cout = csv[f"{k}_brut"], csv[f"{k}_cout"]
    net = (brut - cout).loc[debut:]
    actif = ((brut != 0) | (cout != 0)).loc[debut:]
    out = {}
    for nom, sl in (("TRAIN", slice(None, fin_train)), ("VAL", slice(fin_train + pd.Timedelta(days=1), None))):
        x, a = net.loc[sl], actif.loc[sl]
        s = tv["series"][k][nom]
        out[nom] = {
            "taux_gain": float((x[a] > 0).mean()),
            "calmar": s["rendement_annuel_net"] / abs(s["drawdown_max"]) if s["drawdown_max"] else None,
            "psr": st.psr(x.to_numpy(), 0.0),
        }
    return out


def part_s7(tv) -> float:
    """Part de S7 dans la perte annuelle VAL de la pile (contributions descriptives du JSON)."""
    c = tv["contribution_annuelle_pile_val"]
    return c["S7"] / sum(c.values())


# ------------------------------------------------------------------ README : résultats clés
def bloc_cles(D) -> str:
    tv, cp, ap = D["tv"], D["cp"], D["appro"]
    pile = tv["series"]["PILE"]["VAL"]
    meilleur_brut = max(tv["series"][k]["VAL"]["sharpe_brut"] for k in SERIES[:-1])
    par = cp["puissance"]["par_sharpe_vrai"]
    essais_max = max(h["n_essais"] for h in ap["Q4_tests_multiples"]["historique_essais_anterieurs"])
    return "\n".join([
        f"- **Verdict : échec, et d'abord un manque d'edge brut.** Pile des 7 sleeves en VAL : Sharpe net **{n(pile['sharpe_net'])}** "
        f"(IC 95 % [{n(pile['ic95_sharpe'][0])} ; {n(pile['ic95_sharpe'][1])}]), Sharpe brut {n(pile['sharpe_brut'])} ; aucune sleeve n'a un Sharpe brut VAL "
        f"au-delà de {n(meilleur_brut)}. *Réserve : coûts = spreads publics de courtiers de détail (millésime récent appliqué à toute la période, indices à 12 bp), "
        f"pas des coûts d'exécution mesurés ; S7 porte {n(100 * part_s7(tv), 0)} % de la perte annuelle.*",
        f"- **Le test aurait détecté un vrai edge (contrôle positif, exploratoire).** Sur des sleeves simulées de la longueur de VAL, la gate G2 passe dans "
        f"{pct(par['1.0']['taux_G2'], 0)} des cas à Sharpe vrai 1,0, {pct(par['1.5']['taux_G2'], 0)} à 1,5, {pct(par['2.0']['taux_G2'], 0)} à 2,0, et dans "
        f"{pct(par['0.0']['taux_G2'], 0)} à Sharpe vrai 0. *Réserve : sur 4 ans un Sharpe vrai de 0,5 n'est détecté que dans {pct(par['0.5']['taux_G2'], 0)} des cas : "
        "les sleeves lentes (S1, S6) restent indiscernables de zéro, et d'un petit edge.*",
        "- **VAL n'est pas vierge.** La période 2019-2022 et le même univers avaient déjà servi à au moins "
        f"{essais_max} essais lors d'un projet de recherche antérieur (non publié) ; seul TEST (2023+, scellé, jamais lu) est vierge. "
        "Protocole d'origine publié à l'octet près ([`PREREGISTRATION_v1.md`](PREREGISTRATION_v1.md), SHA-256 `f6007427…`, vérifié par un test), "
        "mais horodaté par un dépôt personnel, pas par un tiers ; le N = 8 du DSR est un plancher, pas un compte exact.",
    ])


# ------------------------------------------------------------------ README : frais et hypothèses (6 lignes de tableau)
def bloc_frais(D) -> str:
    tv, tr, frais = D["tv"], D["tr"], D["frais"]
    cl = tr["frais_univers"]["par_classe"]
    lignes_cl = []
    for nom, v in cl.items():
        borne = "" if v["min_bps"] == v["max_bps"] else f", {n(v['min_bps'])} à {n(v['max_bps'])}"
        lignes_cl.append(f"{nom} : médiane {n(v['mediane_bps'])} bp ({v['n_actifs']} actifs{borne})")
    courtiers = sorted({s.split("_")[0] for s in frais["source"].astype(str) if not s.startswith("DECISION")})
    courtiers = ", ".join(BROKERS.get(c, c) for c in courtiers)
    p, g = tv["meta"]["periodes"], tv["gates"]
    return "\n".join([
        "| Hypothèse | Valeur |",
        "|---|---|",
        f"| Coûts par jambe | {' ; '.join(lignes_cl)}. Indices figés à 12 bp. Coût = bp × \\|Δ position\\| (ouvrir puis fermer = 2 jambes) |",
        f"| Source et limite | spreads publics de courtiers de détail ({courtiers}) dans [`data/frais_editable.csv`](data/frais_editable.csv), millésime récent appliqué "
        "à toute la période (plutôt flatteur pour 2010-2015) : ce ne sont pas des coûts d'exécution mesurés. Non modélisés : portage, financement, impact, compensation entre sleeves |",
        f"| Données | HistData 1 minute (BID) et barres 1 h dérivées ; {tr['frais_univers']['n_actifs']} actifs (60 séries au pré-enregistrement, WTIUSD et GRXEUR exclus), "
        "non redistribuées (voir « Obtenir les données ») |",
        f"| Découpage | TRAIN {p['TRAIN'][0][:4]}-{p['TRAIN'][1][:4]} · VAL {p['VAL'][0][:4]}-{p['VAL'][1][:4]} (**déjà vue lors d'un projet antérieur**) · "
        "**TEST 2023+ scellé**, jamais lu (`scripts/ouvrir_test.py` jamais lancé) |",
        "| Exécution et risque | quotidien : décision à 11h00, exécution le jour suivant, gain du jour suivant au surlendemain ; intrajournalier : entrée à l'open de la minute qui suit le signal. "
        "Chaque sleeve vise 10 % de volatilité annuelle (EWMA, passé seulement) |",
        f"| Gates (pré-enregistrées) | G1 Sharpe net VAL ≥ 1 : **{n(g['G1']['valeur'])}** · G2 borne basse IC 95 % > 0 : **{n(g['G2']['valeur'])}** · "
        "G3 (DSR) échoue, mais n'est pas informatif ici (voir « Pré-enregistrement ») |",
    ])


# ------------------------------------------------------------------ README : métriques (≤ 7 colonnes)
def bloc_metriques(D) -> str:
    tv, tr, csv = D["tv"], D["tr"], D["csv"]
    s = tv["series"]["PILE"]
    pr = periodes(tv, csv, "PILE")
    nb = tr["nb_trades"]["par_serie"]
    v = tv["verdict_provisoire"]["verdict"]

    def ligne(nom, a, b):
        return f"| {nom} | {a} | {b} |"

    pile = [
        "**Pile des 7 sleeves (toutes gardées, nettes de frais)**", "",
        "| Métrique | TRAIN | VAL |", "|---|---|---|",
        ligne("Sharpe net (annualisé, √252)", n(s["TRAIN"]["sharpe_net"]), n(s["VAL"]["sharpe_net"])),
        ligne("Sharpe brut (avant frais)", n(s["TRAIN"]["sharpe_brut"]), n(s["VAL"]["sharpe_brut"])),
        ligne("IC 95 % bootstrap du Sharpe net", f"[{n(s['TRAIN']['ic95_sharpe'][0])} ; {n(s['TRAIN']['ic95_sharpe'][1])}]",
              f"[{n(s['VAL']['ic95_sharpe'][0])} ; {n(s['VAL']['ic95_sharpe'][1])}]"),
        ligne("Rendement annualisé net", rend(s["TRAIN"]["rendement_annuel_net"]), rend(s["VAL"]["rendement_annuel_net"])),
        ligne("Volatilité annualisée", pct(s["TRAIN"]["vol_annuelle"]), pct(s["VAL"]["vol_annuelle"])),
        ligne("Drawdown max", pct(s["TRAIN"]["drawdown_max"]), pct(s["VAL"]["drawdown_max"])),
        ligne("Calmar (rendement / drawdown max)", n(pr["TRAIN"]["calmar"]), n(pr["VAL"]["calmar"])),
        ligne("Nombre de trades (ordres exécutés)", entier(nb["PILE"]["TRAIN"]), entier(nb["PILE"]["VAL"])),
        ligne("Taux de gain (jours actifs gagnants)", pct(pr["TRAIN"]["taux_gain"]), pct(pr["VAL"]["taux_gain"])),
        ligne("Rotation annuelle (× le capital)", f"{entier(s['TRAIN']['rotation_annuelle'])}×", f"{entier(s['VAL']['rotation_annuelle'])}×"),
        ligne("Coût annuel (% du capital)", pct(s["TRAIN"]["cout_annuel"]), pct(s["VAL"]["cout_annuel"])),
        ligne("Verdict", "n/a", f"**{v}** (G1, G2, G3 en échec ; TEST scellé)"),
    ]
    sleeves = ["", "**Chaque sleeve** (7 colonnes ; le détail complet est dans « Toutes les variantes » plus bas)", "",
               "| Série | Sharpe net TRAIN | Sharpe net VAL | Sharpe brut VAL | Rend. net/an VAL | Drawdown VAL | Coût/an VAL |",
               "|---|---|---|---|---|---|---|"]
    for k in SERIES:
        x = tv["series"][k]
        sleeves.append(f"| {COURT[k]} | {n(x['TRAIN']['sharpe_net'])} | {n(x['VAL']['sharpe_net'])} | {n(x['VAL']['sharpe_brut'])} | "
                       f"{rend(x['VAL']['rendement_annuel_net'])} | {pct(x['VAL']['drawdown_max'], 0)} | {pct(x['VAL']['cout_annuel'])} |")
    sleeves += ["", "*Rendement annuel = moyenne quotidienne × 252 (arithmétique), affiché « ruine » s'il est inférieur à −100 % : S7 est une sleeve intrajournalière "
                "(30 minutes d'exposition par jour) dont la volatilité cible de 10 % impose un fort levier ; les coûts qui en découlent "
                f"({pct(tv['series']['S7']['VAL']['cout_annuel'], 0)} du capital par an en VAL, {pct(tv['series']['S7']['TRAIN']['cout_annuel'], 0)} en TRAIN) dépassent tout le capital. "
                "La série continue après la ruine (rien n'est liquidé) ; le chiffre exact est dans `results/train_val.json`.*"]
    return "\n".join(pile + sleeves)


def overfit_30s(D) -> str:
    tv = D["tv"]
    s = tv["series"]
    t, v = s["PILE"]["TRAIN"]["sharpe_net"], s["PILE"]["VAL"]["sharpe_net"]
    positives = [k for k in SERIES[:-1] if s[k]["TRAIN"]["sharpe_net"] > 0]
    details = ", ".join(f"{k} {n(s[k]['TRAIN']['sharpe_net'])} → {n(s[k]['VAL']['sharpe_net'])} (rapport {n(s[k]['VAL']['sharpe_net'] / s[k]['TRAIN']['sharpe_net'])})"
                        for k in positives)
    g = tv["gates"]
    min_det = D["appro"]["Q3_puissance"]["sharpe_min_detectable_80pct"]["unilateral_alpha5"]
    return "\n".join([
        f"1. **Rapport Sharpe VAL / TRAIN de la pile : {n(v)} / {n(t)} = {n(v / t)}, mais les deux sont négatifs.** Il n'y a pas de performance qui s'effondre hors échantillon : "
        f"il n'y en avait pas non plus dans l'échantillon. Seules les sleeves à Sharpe TRAIN positif seraient candidates à un overfit : {details} ; elles se dégradent, "
        "ce qui est compatible avec du bruit (S6 est surtout du bêta actions).",
        f"2. **L'IC 95 % du Sharpe net VAL de la pile est [{n(s['PILE']['VAL']['ic95_sharpe'][0])} ; {n(s['PILE']['VAL']['ic95_sharpe'][1])}]** : borne basse {n(g['G2']['valeur'])}, "
        f"G2 en échec. Puissance : 4 ans de VAL ne détectent avec 80 % de chances qu'un Sharpe vrai d'au moins {n(min_det)}. Verdict `ECHEC`, TEST non ouvert.",
        "3. **Fixé avant de calculer la pile : tout.** Les 7 sleeves et leurs paramètres, les poids (∝ 1/vol TRAIN), la vol cible, les coûts, les gates et le nombre d'essais sont dans "
        "[`PREREGISTRATION_v1.md`](PREREGISTRATION_v1.md) ; aucune sélection par la performance, aucune sleeve retirée après coup (même la pire, S7). "
        "La seule modification venue après la lecture de VAL (horloge HistData, avenant 1) est déclarée. **Mais VAL n'est pas hors échantillon au sens strict** : voir « Pré-enregistrement ».",
    ])


# ------------------------------------------------------------------ README : toutes les variantes (dans un <details>)
def bloc_variantes(D) -> str:
    tv, tr, csv = D["tv"], D["tr"], D["csv"]
    nb = tr["nb_trades"]["par_serie"]
    perf = ["| Variante | Sharpe net TRAIN | Sharpe net VAL | Sharpe brut TRAIN | Sharpe brut VAL | Rend. net/an TRAIN | Rend. net/an VAL | Vol TRAIN | Vol VAL | Drawdown TRAIN | Drawdown VAL |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    act = ["| Variante | Calmar TRAIN | Calmar VAL | Trades TRAIN | Trades VAL | Taux de gain TRAIN | Taux de gain VAL | Rotation/an VAL | Coût/an TRAIN | Coût/an VAL | PSR(0) VAL |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k in SERIES:
        s, pr = tv["series"][k], periodes(tv, csv, k)
        T, V = s["TRAIN"], s["VAL"]
        perf.append(f"| {COURT[k]} | {n(T['sharpe_net'])} | {n(V['sharpe_net'])} | {n(T['sharpe_brut'])} | {n(V['sharpe_brut'])} | "
                    f"{rend(T['rendement_annuel_net'])} | {rend(V['rendement_annuel_net'])} | {pct(T['vol_annuelle'])} | {pct(V['vol_annuelle'])} | "
                    f"{pct(T['drawdown_max'], 0)} | {pct(V['drawdown_max'], 0)} |")
        act.append(f"| {COURT[k]} | {n(pr['TRAIN']['calmar'])} | {n(pr['VAL']['calmar'])} | {entier(nb[k]['TRAIN'])} | {entier(nb[k]['VAL'])} | "
                   f"{pct(pr['TRAIN']['taux_gain'])} | {pct(pr['VAL']['taux_gain'])} | {entier(V['rotation_annuelle'])}× | {pct(T['cout_annuel'])} | "
                   f"{pct(V['cout_annuel'])} | {n(V['psr0'], 3)} |")
    notes = ["", "*Nombre de trades = ordres exécutés (quotidien : variations de position non nulles par actif ; intrajournalier : 2 ordres par position). "
             "TRAIN d'une sleeve = depuis son premier jour actif. « ruine » : rendement annuel inférieur à −100 % (voir la note sous les métriques).*"]
    return "\n".join(["**Performance**", "", *perf, "", "**Activité, coûts et significativité**", "", *act, *notes])


# ------------------------------------------------------------------ README : contrôle positif
def _taux(x):
    return pct(x, 0)


def bloc_controle(D) -> str:
    cp = D["cp"]
    il, par, pu = cp["illustration"], cp["puissance"]["par_sharpe_vrai"], cp["puissance"]
    gates = il["gates"]
    ok = lambda g: "passe" if gates[g]["passe"] else "échoue"  # noqa: E731
    lignes = [
        "| Sharpe vrai | Sharpe estimé moyen | G1 passe | G2 passe | G3 passe | IC 95 % contient le vrai Sharpe |",
        "|---|---|---|---|---|---|",
    ]
    for sr in sorted(par, key=float):
        v = par[sr]
        lignes.append(f"| {n(float(sr), 1)} | {n(v['sharpe_estime_moyen'])} | {_taux(v['taux_G1'])} | {_taux(v['taux_G2'])} | {_taux(v['taux_G3'])} | {_taux(v['couverture_ic95'])} |")
    return "\n".join([
        f"Une sleeve simulée de **Sharpe vrai {n(il['sharpe_vrai'], 1)}** (rendements gaussiens, vol 10 %, graine fixe {il['graine']}, déclarée avant de regarder le résultat) "
        f"plus 7 sleeves nulles (N = 8 essais, comme le protocole) traverse les mêmes fonctions que les sleeves réelles. Sur VAL : Sharpe estimé **{n(il['VAL']['sharpe_net'])}**, "
        f"IC 95 % [{n(il['VAL']['ic95_sharpe'][0])} ; {n(il['VAL']['ic95_sharpe'][1])}] ; G1 {ok('G1')}, G2 {ok('G2')}, G3 {ok('G3')} (DSR {n(il['dsr'])}). "
        f"Part de {pu['n_rep']} simulations de {pu['n_jours']} jours (= VAL) où chaque gate passe :",
        "", *lignes, "",
        f"*Lecture : le pipeline ne crie pas à l'edge dans le bruit ({_taux(par['0.0']['taux_G2'])} de faux positifs à Sharpe vrai 0, couverture de l'IC proche de 95 %) et retrouve un edge "
        f"fort ({_taux(par['2.0']['taux_G2'])} à Sharpe vrai 2,0). Il manque de puissance pour un edge faible (Sharpe vrai 0,5 : {_taux(par['0.5']['taux_G2'])}), "
        "et la gate G3 (DSR, N = 8) est très conservatrice. Exploratoire, hors verdict.*",
    ])


# ------------------------------------------------------------------ docs/resultats_detailles.md
def bloc_detail(D) -> str:
    tv, tr = D["tv"], D["tr"]
    t1 = ["| Série | Début actif | Sharpe net TRAIN | Sharpe net VAL | IC 95 % bootstrap VAL | Sharpe brut VAL | t NW VAL | p Holm | PSR(0) | DSR (N = 8) |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    t2 = ["| Série | Rend. net/an VAL | Vol/an VAL | DD max VAL | Rotation/an VAL | Coût/an VAL | Sharpe brut TRAIN | Rend. net/an TRAIN | Coût/an TRAIN |",
          "|---|---|---|---|---|---|---|---|---|"]
    for k in SERIES:
        s = tv["series"][k]
        T, V = s["TRAIN"], s["VAL"]
        holm = V.get("p_holm_sleeves")
        t1.append(f"| {COURT[k]} | {s['debut_actif']} | {n(T['sharpe_net'])} | {n(V['sharpe_net'])} | [{n(V['ic95_sharpe'][0])} ; {n(V['ic95_sharpe'][1])}] | "
                  f"{n(V['sharpe_brut'])} | {n(V['t_nw'])} | {'n/a' if holm is None else n(holm, 3)} | {n(V['psr0'], 3)} | {p3(V['dsr'])} |")
        t2.append(f"| {COURT[k]} | {rend(V['rendement_annuel_net'])} | {pct(V['vol_annuelle'])} | {pct(V['drawdown_max'], 0)} | {entier(V['rotation_annuelle'])}× | "
                  f"{pct(V['cout_annuel'])} | {n(T['sharpe_brut'])} | {rend(T['rendement_annuel_net'])} | {pct(T['cout_annuel'])} |")
    t3 = ["| Sleeve | Poids de la pile (∝ 1/vol TRAIN) | Contribution annuelle au rendement net de la pile, VAL |", "|---|---|---|"]
    for k in SERIES[:-1]:
        t3.append(f"| {COURT[k]} | {n(tv['poids_pile'][k], 3)} | {pct(tv['contribution_annuelle_pile_val'][k])} |")
    g = tv["gates"]
    dsr_v = tv["series"]["PILE"]["VAL"]["dsr"]
    t4 = ["| Gate | Critère | Valeur | Résultat |", "|---|---|---|---|",
          f"| G1 | Sharpe net VAL de la pile ≥ 1,0 | {n(g['G1']['valeur'])} | {'PASSE' if g['G1']['passe'] else 'ÉCHOUE'} |",
          f"| G2 | borne basse IC 95 % bootstrap du Sharpe VAL > 0 | {n(g['G2']['valeur'])} | {'PASSE' if g['G2']['passe'] else 'ÉCHOUE'} |",
          f"| G3 | DSR VAL (N = 8) ≥ 0,95 | {p3(dsr_v)} | {'PASSE' if g['G3']['passe'] else 'ÉCHOUE'} (non informatif : Sharpe négatif) |",
          "| G4 | TEST : Sharpe net > 0 et ≥ 0,5 × Sharpe VAL | non évalué | TEST scellé (G1 et G2 échouent) |"]
    return "\n".join([f"Chiffres lus dans [`results/train_val.json`](../results/train_val.json) (VAL = {entier(tv['series']['PILE']['VAL']['n_jours'])} jours ; "
                      "Sharpe net annualisé, coûts réels déduits).", "", *t1, "", *t2, "",
                      "*« ruine » : rendement annuel (moyenne quotidienne × 252) inférieur à −100 %, voir la note du README.*", "",
                      "Poids de la pile et contribution de chaque sleeve (purement descriptif) :", "", *t3, "", *t4])


# ------------------------------------------------------------------ docs/approfondissement.md
def bloc_couts(D) -> str:
    sc = D["sc"]
    ms = [str(m) for m in sc["multiplicateurs"]]
    noms = {"0.0": "×0 (brut)", "0.1": "×0,1", "0.25": "×0,25", "0.5": "×0,5", "1.0": "×1 (coûts réels)"}
    lignes = ["| Série | " + " | ".join(noms[m] for m in ms) + " | Coût moyen actuel (bps/jambe) | Coût de rentabilité VAL (bps/jambe) |", "|---|" + "---|" * (len(ms) + 2)]
    for k in SERIES:
        cr = sc["cout_rentabilite_val"][k]
        renta = "jamais (brut VAL ≤ 0)" if cr["cout_rentabilite_bps_par_jambe"] is None else n(cr["cout_rentabilite_bps_par_jambe"])
        lignes.append(f"| {COURT[k]} | " + " | ".join(n(sc["sharpe_net"]["VAL"][k][m]) for m in ms) + f" | {n(cr['cout_moyen_effectif_bps_par_jambe'])} | {renta} |")
    return "\n".join(lignes)


def bloc_controle_detail(D) -> str:
    cp = D["cp"]
    il = cp["illustration"]
    t, v = il["TRAIN"], il["VAL"]
    lignes = ["| Période | Sharpe estimé | IC 95 % bootstrap | t Newey-West | PSR(0) | DSR (N = 8) |", "|---|---|---|---|---|---|",
              f"| TRAIN ({entier(t['n_jours'])} jours) | {n(t['sharpe_net'])} | [{n(t['ic95_sharpe'][0])} ; {n(t['ic95_sharpe'][1])}] | n/d | n/d | n/d |",
              f"| VAL ({entier(v['n_jours'])} jours) | {n(v['sharpe_net'])} | [{n(v['ic95_sharpe'][0])} ; {n(v['ic95_sharpe'][1])}] | {n(il['nw']['t_nw'])} | {n(il['psr0'], 3)} | {n(il['dsr'], 3)} |"]
    return "\n".join([
        f"Sleeve synthétique de Sharpe vrai {n(il['sharpe_vrai'], 1)} (graine {il['graine']}), calendrier réel de la pile (du {cp['frontieres']['train_fin'][:4]} au {cp['frontieres']['val_fin'][:4]}), "
        f"7 sleeves nulles pour le DSR (SR0 annualisé {n(il['sr0_annualise'])}) :", "", *lignes, "",
        f"Pour comparaison, la pile réelle a en VAL un Sharpe net de {n(cp['pile_reelle_val']['sharpe_net'])} (IC 95 % "
        f"[{n(cp['pile_reelle_val']['ic95_sharpe'][0])} ; {n(cp['pile_reelle_val']['ic95_sharpe'][1])}]). "
        f"Sharpe minimal détectable à 80 % de puissance (test unilatéral 5 %, approfondissement Q3) : {n(cp['sharpe_min_detectable_80pct'])}."])


BLOCS = {"CLES": bloc_cles, "FRAIS": bloc_frais, "METRIQUES": bloc_metriques, "OVERFIT": overfit_30s, "VARIANTES": bloc_variantes,
         "CONTROLE": bloc_controle, "DETAIL": bloc_detail, "COUTS": bloc_couts, "CONTROLE_DETAIL": bloc_controle_detail}


def blocs(D=None) -> dict[str, dict[str, str]]:
    """{fichier: {nom du bloc: contenu}} : ce que le script écrit, et ce que le test relit."""
    D = D or charger()
    return {f: {nom: BLOCS[nom](D) for nom in noms} for f, noms in FICHIERS.items()}


# ------------------------------------------------------------------ injection
def injecter(texte: str, nom: str, contenu: str, fichier: str = "") -> str:
    motif = re.compile(rf"(<!-- AUTO:{nom} -->)(.*?)(<!-- /AUTO:{nom} -->)", re.S)
    if not motif.search(texte):
        raise SystemExit(f"balises AUTO:{nom} introuvables dans {fichier}")
    return motif.sub(lambda m: f"{m.group(1)}\n{contenu}\n{m.group(3)}", texte)


def main() -> None:
    tout = blocs()
    for fichier, contenus in tout.items():
        chemin = RACINE / fichier
        texte = chemin.read_bytes().decode("utf-8").replace("\r\n", "\n")
        for nom, contenu in contenus.items():
            texte = injecter(texte, nom, contenu, fichier)
        chemin.write_bytes(texte.encode("utf-8"))
        print(f"{fichier} : blocs AUTO {', '.join(contenus)} réécrits depuis results/")


if __name__ == "__main__":
    main()
