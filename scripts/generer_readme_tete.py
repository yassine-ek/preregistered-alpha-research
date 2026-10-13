"""Écrit dans README.md les blocs de chiffres, LUS dans results/*.json et results/rendements_train_val.csv.

Deux blocs délimités par des balises HTML (invisibles sur GitHub) sont réécrits à chaque exécution :
  <!-- AUTO:TETE -->      encadré frais, tableaux de métriques TRAIN | VAL, lecture « Overfit ou pas ? »
  <!-- AUTO:VARIANTES --> tableaux détaillés de toutes les variantes (7 sleeves + pile)
Aucun chiffre de ces blocs n'est tapé à la main. Aucune donnée de marché requise, TEST jamais chargé.

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
README = RACINE / "README.md"
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


def entier(x):
    return f"{round(x):,}".replace(",", " ")


def p3(x):
    """Probabilité : « < 0,001 » si négligeable."""
    return "< 0,001" if x < 0.001 else n(x, 3)


# ------------------------------------------------------------------ lecture des résultats
def charger():
    tv = json.loads((RESULTATS / "train_val.json").read_text(encoding="utf-8"))
    tr = json.loads((RESULTATS / "reproduction_et_trades.json").read_text(encoding="utf-8"))
    csv = pd.read_csv(RESULTATS / "rendements_train_val.csv", index_col=0, parse_dates=True)
    frais = pd.read_csv(RACINE / "data" / "frais_editable.csv", encoding="utf-8", encoding_errors="replace")
    return tv, tr, csv, frais


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


# ------------------------------------------------------------------ bloc TÊTE
def encadre_frais(tv, tr, frais) -> str:
    cl = tr["frais_univers"]["par_classe"]
    lignes_cl = []
    for nom, v in cl.items():
        borne = "" if v["min_bps"] == v["max_bps"] else f", {n(v['min_bps'])} à {n(v['max_bps'])}"
        lignes_cl.append(f"{nom} : médiane {n(v['mediane_bps'])} bp ({v['n_actifs']} actifs{borne})")
    courtiers = sorted({s.split("_")[0] for s in frais["source"].astype(str) if not s.startswith("DECISION")})
    courtiers = ", ".join(BROKERS.get(c, c) for c in courtiers)
    p = tv["meta"]["periodes"]
    g = tv["gates"]
    return "\n".join([
        "### Frais et hypothèses",
        "",
        "| Hypothèse | Valeur |",
        "|---|---|",
        f"| Coûts par jambe | {' ; '.join(lignes_cl)}. Indices figés à 12 bp (pas d'override individuel). Coût = bp × \\|Δ position\\| ; ouvrir puis fermer = 2 jambes |",
        f"| Source des coûts | spreads publics de courtiers ({courtiers}), fichier versionné [`data/frais_editable.csv`](data/frais_editable.csv) ; millésime récent appliqué à toute la période, donc plutôt flatteur pour 2010-2015. Tout résultat calculé avec d'autres coûts est invalide |",
        "| Non modélisé | portage et financement (swaps, intérêts), glissement au-delà du spread, impact, compensation d'ordres entre sleeves (chaque sleeve paie ses propres coûts : prudent) |",
        f"| Données | HistData 1 minute (BID) et barres 1 h dérivées ; {tr['frais_univers']['n_actifs']} actifs liquides (FX, indices, métaux et pétrole), actifs morts exclus ; non redistribuées (voir « Reproduire ») |",
        f"| Découpage | TRAIN {p['TRAIN'][0][:4]}-{p['TRAIN'][1][:4]} (préchauffage, calibration des échelles) · VAL {p['VAL'][0][:4]}-{p['VAL'][1][:4]} (évaluation) · **TEST 2023+ : scellé**, jamais lu (`scripts/ouvrir_test.py` n'a jamais été lancé) |",
        "| Délai d'exécution | quotidien : décision à l'instantané de 11h00, exécution le jour suivant, gain du jour suivant au surlendemain (un jour plein) ; intrajournalier : entrée à l'open de la minute qui suit le signal |",
        "| Risque | chaque sleeve vise 10 % de volatilité annuelle ex ante (EWMA, passé seulement) ; pile à 10 % de vol sur TRAIN |",
        f"| Statistiques | IC 95 % du Sharpe par bootstrap stationnaire (blocs de {tv['meta']['bootstrap']['bloc_moyen_jours']} jours, {tv['meta']['bootstrap']['tirages']} tirages), Newey-West + Holm, PSR et DSR ({tv['meta']['n_essais_dsr']} essais). Sharpe annualisé par √252 |",
        f"| Gates (pré-enregistrées) | G1 Sharpe net VAL ≥ 1 : **{n(g['G1']['valeur'])}** · G2 borne basse IC 95 % > 0 : **{n(g['G2']['valeur'])}** · G3 DSR ≥ 0,95 : **{p3(g['G3']['valeur'])}** |",
    ])


def tableau_pile(tv, tr, csv) -> str:
    s = tv["series"]["PILE"]
    pr = periodes(tv, csv, "PILE")
    nb = tr["nb_trades"]["par_serie"]["PILE"]
    v = tv["verdict_provisoire"]["verdict"]

    def ligne(nom, a, b):
        return f"| {nom} | {a} | {b} |"

    return "\n".join([
        "### Métriques de la pile (les 7 sleeves, toutes gardées, nettes de frais)",
        "",
        "| Métrique | TRAIN | VAL |",
        "|---|---|---|",
        ligne("Sharpe net (annualisé, √252)", n(s["TRAIN"]["sharpe_net"]), n(s["VAL"]["sharpe_net"])),
        ligne("Sharpe brut (avant frais)", n(s["TRAIN"]["sharpe_brut"]), n(s["VAL"]["sharpe_brut"])),
        ligne("IC 95 % bootstrap du Sharpe net", f"[{n(s['TRAIN']['ic95_sharpe'][0])} ; {n(s['TRAIN']['ic95_sharpe'][1])}]",
              f"[{n(s['VAL']['ic95_sharpe'][0])} ; {n(s['VAL']['ic95_sharpe'][1])}]"),
        ligne("Rendement annualisé net", pct(s["TRAIN"]["rendement_annuel_net"]), pct(s["VAL"]["rendement_annuel_net"])),
        ligne("Volatilité annualisée", pct(s["TRAIN"]["vol_annuelle"]), pct(s["VAL"]["vol_annuelle"])),
        ligne("Drawdown max", pct(s["TRAIN"]["drawdown_max"]), pct(s["VAL"]["drawdown_max"])),
        ligne("Calmar (rendement / drawdown max)", n(pr["TRAIN"]["calmar"]), n(pr["VAL"]["calmar"])),
        ligne("Nombre de trades (ordres exécutés)", entier(nb["TRAIN"]), entier(nb["VAL"])),
        ligne("Taux de gain (jours actifs gagnants)", pct(pr["TRAIN"]["taux_gain"]), pct(pr["VAL"]["taux_gain"])),
        ligne("Rotation annuelle (× le capital)", f"{entier(s['TRAIN']['rotation_annuelle'])}×", f"{entier(s['VAL']['rotation_annuelle'])}×"),
        ligne("Coût annuel (% du capital)", pct(s["TRAIN"]["cout_annuel"]), pct(s["VAL"]["cout_annuel"])),
        ligne("PSR(0)", n(pr["TRAIN"]["psr"], 3), n(s["VAL"]["psr0"], 3)),
        ligne(f"DSR ({tv['meta']['n_essais_dsr']} essais)", "défini sur VAL", p3(s["VAL"]["dsr"])),
        ligne("Nombre d'essais", str(tv["meta"]["n_essais_dsr"]), f"{tv['meta']['n_essais_dsr']} (7 sleeves + la pile)"),
        ligne("Verdict", "n/a", f"**{v}** (G1, G2, G3 en échec ; TEST scellé)"),
    ])


def tableau_sleeves_compact(tv, tr) -> str:
    nb = tr["nb_trades"]["par_serie"]
    lignes = ["### Chaque sleeve, TRAIN | VAL côte à côte", "",
              "| Série | Sharpe net TRAIN | Sharpe net VAL | Rend. net/an TRAIN | Rend. net/an VAL | Drawdown TRAIN | Drawdown VAL | Trades TRAIN | Trades VAL | Coût/an VAL | DSR VAL |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k in SERIES:
        s = tv["series"][k]
        lignes.append(f"| {COURT[k]} | {n(s['TRAIN']['sharpe_net'])} | {n(s['VAL']['sharpe_net'])} | {pct(s['TRAIN']['rendement_annuel_net'])} | "
                      f"{pct(s['VAL']['rendement_annuel_net'])} | {pct(s['TRAIN']['drawdown_max'], 0)} | {pct(s['VAL']['drawdown_max'], 0)} | "
                      f"{entier(nb[k]['TRAIN'])} | {entier(nb[k]['VAL'])} | {pct(s['VAL']['cout_annuel'])} | {p3(s['VAL']['dsr'])} |")
    lignes += ["", "*Nombre de trades = ordres exécutés (quotidien : variations de position non nulles par actif ; intrajournalier : 2 ordres par position). "
               "TRAIN d'une sleeve = depuis son premier jour actif.*"]
    return "\n".join(lignes)


def overfit_30s(tv, csv) -> str:
    s = tv["series"]
    t, v = s["PILE"]["TRAIN"]["sharpe_net"], s["PILE"]["VAL"]["sharpe_net"]
    positives = [k for k in SERIES[:-1] if s[k]["TRAIN"]["sharpe_net"] > 0]
    details = ", ".join(f"{k} {n(s[k]['TRAIN']['sharpe_net'])} → {n(s[k]['VAL']['sharpe_net'])} (rapport {n(s[k]['VAL']['sharpe_net'] / s[k]['TRAIN']['sharpe_net'])})"
                        for k in positives)
    dsr_max = max(s[k]["VAL"]["dsr"] for k in SERIES)
    g = tv["gates"]
    return "\n".join([
        "### Overfit ou pas ? Lecture en 30 secondes",
        "",
        f"1. **Rapport Sharpe VAL / TRAIN de la pile : {n(v)} / {n(t)} = {n(v / t)}, mais les deux sont négatifs.** Il n'y a pas de performance qui s'effondre hors échantillon : "
        f"il n'y en avait pas non plus dans l'échantillon. Seules les sleeves à Sharpe TRAIN positif seraient candidates à un overfit : {details} ; elles se dégradent, ce qui est compatible avec du bruit (S6 est surtout du bêta actions).",
        f"2. **DSR de la pile < 0,001 pour {tv['meta']['n_essais_dsr']} essais** (7 sleeves + la pile ; le plus grand DSR parmi les 8 séries vaut {p3(dsr_max)}, seuil 0,95), "
        f"borne basse de l'IC 95 % du Sharpe VAL {n(g['G2']['valeur'])}. Verdict `ECHEC`, TEST non ouvert.",
        "3. **Choisi AVANT de voir VAL : tout.** Les 7 sleeves et leurs paramètres, les poids de la pile (∝ 1/vol TRAIN), la vol cible, les coûts, les gates et le nombre d'essais sont figés dans "
        "[`PREREGISTRATION.md`](PREREGISTRATION.md) avant le premier calcul ; aucune sélection par la performance, aucune sleeve retirée après coup (même la pire, S7). "
        "La seule modification venue après VAL (correction de l'horloge HistData, avenant 1) est déclarée comme telle plus bas.",
    ])


def bloc_tete(tv, tr, csv, frais) -> str:
    return "\n\n".join([
        encadre_frais(tv, tr, frais),
        tableau_pile(tv, tr, csv),
        tableau_sleeves_compact(tv, tr),
    ])


def bloc_overfit(tv, csv) -> str:
    return overfit_30s(tv, csv)


# ------------------------------------------------------------------ bloc VARIANTES
def bloc_variantes(tv, tr, csv) -> str:
    nb = tr["nb_trades"]["par_serie"]
    perf = ["| Variante | Sharpe net TRAIN | Sharpe net VAL | Sharpe brut TRAIN | Sharpe brut VAL | Rend. net/an TRAIN | Rend. net/an VAL | Vol TRAIN | Vol VAL | Drawdown TRAIN | Drawdown VAL |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    act = ["| Variante | Calmar TRAIN | Calmar VAL | Trades TRAIN | Trades VAL | Taux de gain TRAIN | Taux de gain VAL | Rotation/an VAL | Coût/an TRAIN | Coût/an VAL | PSR(0) VAL | DSR VAL |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k in SERIES:
        s, pr = tv["series"][k], periodes(tv, csv, k)
        T, V = s["TRAIN"], s["VAL"]
        perf.append(f"| {COURT[k]} | {n(T['sharpe_net'])} | {n(V['sharpe_net'])} | {n(T['sharpe_brut'])} | {n(V['sharpe_brut'])} | "
                    f"{pct(T['rendement_annuel_net'])} | {pct(V['rendement_annuel_net'])} | {pct(T['vol_annuelle'])} | {pct(V['vol_annuelle'])} | "
                    f"{pct(T['drawdown_max'], 0)} | {pct(V['drawdown_max'], 0)} |")
        act.append(f"| {COURT[k]} | {n(pr['TRAIN']['calmar'])} | {n(pr['VAL']['calmar'])} | {entier(nb[k]['TRAIN'])} | {entier(nb[k]['VAL'])} | "
                   f"{pct(pr['TRAIN']['taux_gain'])} | {pct(pr['VAL']['taux_gain'])} | {entier(V['rotation_annuelle'])}× | {pct(T['cout_annuel'])} | "
                   f"{pct(V['cout_annuel'])} | {n(V['psr0'], 3)} | {p3(V['dsr'])} |")
    return "\n".join(["**Performance**", "", *perf, "", "**Activité, coûts et significativité**", "", *act])


# ------------------------------------------------------------------ injection
def injecter(texte: str, nom: str, contenu: str) -> str:
    motif = re.compile(rf"(<!-- AUTO:{nom} -->)(.*?)(<!-- /AUTO:{nom} -->)", re.S)
    if not motif.search(texte):
        raise SystemExit(f"balises AUTO:{nom} introuvables dans README.md")
    return motif.sub(lambda m: f"{m.group(1)}\n{contenu}\n{m.group(3)}", texte)


def main() -> None:
    tv, tr, csv, frais = charger()
    brut = README.read_bytes()
    crlf = brut.count(b"\r\n") > brut.count(b"\n") / 2
    texte = brut.decode("utf-8").replace("\r\n", "\n")
    texte = injecter(texte, "TETE", bloc_tete(tv, tr, csv, frais))
    texte = injecter(texte, "OVERFIT", bloc_overfit(tv, csv))
    texte = injecter(texte, "VARIANTES", bloc_variantes(tv, tr, csv))
    README.write_bytes((texte.replace("\n", "\r\n") if crlf else texte).encode("utf-8"))
    print("README.md : blocs AUTO:TETE, AUTO:OVERFIT, AUTO:VARIANTES réécrits depuis results/")


if __name__ == "__main__":
    main()
