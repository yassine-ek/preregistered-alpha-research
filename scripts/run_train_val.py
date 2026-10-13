"""Calcule TOUT sur TRAIN et VAL seulement (TEST scellé) et écrit results/train_val.json + figures.

Usage : python scripts/run_train_val.py
Le TEST (>= 2023-01-01) n'est jamais chargé : donnees.py lève PermissionError au-delà
du plafond, et pipeline.calculer_sleeves vérifie qu'aucune date >= 2023 n'est produite.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from alpha import donnees as d  # noqa: E402
from alpha import gates, graphiques  # noqa: E402
from alpha import pipeline as pl  # noqa: E402
import verifier_donnees  # noqa: E402  (message guidé si les données manquent)
import verifier_prereg  # noqa: E402  (empreinte de la v1)

RESULTATS = RACINE / "results"
FIGURES = RACINE / "figures"


def nettoyer(o):
    """JSON strict : NaN/inf -> None, types numpy -> types Python."""
    if isinstance(o, dict):
        return {k: nettoyer(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [nettoyer(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def main() -> None:
    t0 = time.time()
    verifier_donnees.exiger_donnees()
    RESULTATS.mkdir(exist_ok=True)
    FIGURES.mkdir(exist_ok=True)
    sortie = pl.calculer_sleeves(d.FIN_VAL, test_autorise=False, verbeux=True)
    res = sortie["resultats"]
    pile, poids_pile, kappa = pl.construire_pile(res)
    tout = {**res, "PILE": pile}

    series = {}
    for k, r in tout.items():
        series[k] = {
            "nom": pl.NOMS_SLEEVES.get(k, "Pile des 7 sleeves"),
            "debut_actif": str(r.debut.date()),
            "TRAIN": pl.stats_periode(r, d.DEBUT_DONNEES, d.FIN_TRAIN),
            "VAL": pl.stats_periode(r, d.DEBUT_VAL, d.FIN_VAL),
        }
    ext = pl.stats_val_etendues(res, pile)
    for k in tout:
        series[k]["VAL"].update(ext["par_serie"][k])

    # corrélations des rendements nets sur la fenêtre commune (toutes les sleeves actives)
    nets = pd.DataFrame({k: r.net for k, r in res.items()})
    bruts = pd.DataFrame({k: r.brut for k, r in tout.items()})
    couts = pd.DataFrame({k: r.cout for k, r in tout.items()})
    debut_commun = pile.debut
    corr_train = nets.loc[debut_commun: d.FIN_TRAIN].corr()
    corr_val = nets.loc[d.DEBUT_VAL: d.FIN_VAL].corr()

    # contribution annuelle de chaque sleeve au rendement net de la pile (VAL), purement descriptive
    contrib = {k: float(kappa * poids_pile[k] * nets.loc[d.DEBUT_VAL: d.FIN_VAL, k].mean() * 252) for k in res}

    g = gates.evaluer_gates_val(series["PILE"]["VAL"], series["PILE"]["VAL"]["dsr"])
    verdict, statut_test = gates.verdict(g, test_ouvert=False)

    rapport = {
        "meta": {
            "date_calcul": datetime.now().isoformat(timespec="seconds"),
            "prereg_sha256": verifier_prereg.sha256_v1(),  # empreinte de la version d'origine (le fichier courant contient les avenants)
            "code_sha256": pl.sha256_code(),
            "n_essais_dsr": pl.N_ESSAIS,
            "periodes": {"TRAIN": [str(d.DEBUT_DONNEES.date()), str(d.FIN_TRAIN.date())],
                         "VAL": [str(d.DEBUT_VAL.date()), str(d.FIN_VAL.date())],
                         "TEST": "scellé, non chargé"},
            "dernier_jour_calcule": str(pile.net.index.max().date()),
            "bootstrap": {"bloc_moyen_jours": 20, "tirages": 5000},
            "c_s6": sortie["c_s6"],
            "debut_commun_pile": str(debut_commun.date()),
            "kappa_pile": kappa,
        },
        "poids_pile": poids_pile,
        "series": series,
        "correlations": {"TRAIN": corr_train.round(4).to_dict(), "VAL": corr_val.round(4).to_dict()},
        "dsr": {"sr0_annualise": ext["sr0_dsr_annualise"], "sharpes_val_quotidiens": ext["sharpes_val_quotidiens"]},
        "contribution_annuelle_pile_val": contrib,
        "gates": g,
        "verdict_provisoire": {"verdict": verdict, "statut_test": statut_test},
    }
    (RESULTATS / "train_val.json").write_text(json.dumps(nettoyer(rapport), indent=2, ensure_ascii=False),
                                              encoding="utf-8")

    # rendements quotidiens (TRAIN+VAL) pour le notebook et le README
    plat = {}
    for k, r in tout.items():
        plat[f"{k}_brut"], plat[f"{k}_cout"] = r.brut, r.cout
    pd.DataFrame(plat).to_csv(RESULTATS / "rendements_train_val.csv", float_format="%.8g")

    # figures
    net_tout = pd.DataFrame({k: r.net for k, r in tout.items()})
    graphiques.pnl_cumule(net_tout, bruts, d.FIN_TRAIN, FIGURES / "pnl_cumule.png")
    graphiques.matrice_correlation(corr_train, corr_val, FIGURES / "correlations.png")
    graphiques.sharpe_val_ic({k: series[k]["VAL"] for k in tout}, FIGURES / "sharpe_val_ic.png")
    graphiques.cout_annuel({k: series[k]["TRAIN"] for k in tout}, {k: series[k]["VAL"] for k in tout},
                           FIGURES / "cout_annuel.png")

    print(f"terminé en {time.time() - t0:.0f} s")
    print(f"{'serie':6s} {'SharpeTR':>9s} {'SharpeVAL':>10s} {'IC95 VAL':>20s} {'brutVAL':>8s} {'DSR':>6s}")
    for k in tout:
        s_tr, s_va = series[k]["TRAIN"], series[k]["VAL"]
        print(f"{k:6s} {s_tr['sharpe_net']:9.2f} {s_va['sharpe_net']:10.2f} "
              f"[{s_va['ic95_sharpe'][0]:7.2f},{s_va['ic95_sharpe'][1]:7.2f}] {s_va['sharpe_brut']:8.2f} {s_va['dsr']:6.3f}")
    print({k: v["passe"] for k, v in g.items() if "passe" in v}, "->", verdict, statut_test)


if __name__ == "__main__":
    main()
