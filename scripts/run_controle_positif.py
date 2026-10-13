"""CONTRÔLE POSITIF (EXPLORATOIRE, hors verdict) : une sleeve synthétique à edge connu traverse le même pipeline de statistiques.

Usage : python scripts/run_controle_positif.py
Sorties : results/controle_positif.json, figures/controle_positif.png
Lit seulement results/ (calendrier des jours TRAIN/VAL, verdict, puissance de l'approfondissement) : aucune donnée de marché requise,
le TEST n'existe pas ici. Voir alpha/approfondissement/signal_synthetique.py pour la méthode.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from alpha import donnees as d  # noqa: E402
from alpha.approfondissement import figures as ag  # noqa: E402
from alpha.approfondissement import signal_synthetique as ss  # noqa: E402

RESULTATS, FIGURES = RACINE / "results", RACINE / "figures"


def nettoyer(o):
    if isinstance(o, dict):
        return {str(k): nettoyer(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [nettoyer(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def main() -> None:
    tv = json.loads((RESULTATS / "train_val.json").read_text(encoding="utf-8"))
    verdict = json.loads((RESULTATS / "verdict_alpha.json").read_text(encoding="utf-8"))
    appro = json.loads((RESULTATS / "approfondissement.json").read_text(encoding="utf-8"))
    csv = pd.read_csv(RESULTATS / "rendements_train_val.csv", index_col=0, parse_dates=True)
    assert csv.index.max() < d.DEBUT_TEST, "le TEST ne doit jamais apparaître"
    dates = csv.loc[pd.Timestamp(tv["meta"]["debut_commun_pile"]):].index   # même calendrier que la pile réelle

    rapport = {
        "titre": "EXPLORATOIRE, hors verdict : contrôle positif (sleeve synthétique à edge connu)",
        "avertissement": "Rendements simulés (gaussiens indépendants, vol 10 %, graine fixe) ; aucune donnée de marché ; ne modifie ni le verdict ni le TEST.",
        "verdict_officiel_inchange": {"verdict": verdict["verdict"], "statut_test": verdict["statut_test"]},
        "frontieres": {"train_fin": str(d.FIN_TRAIN.date()), "val_fin": str(d.FIN_VAL.date())},
        "sharpe_min_detectable_80pct": appro["Q3_puissance"]["sharpe_min_detectable_80pct"]["unilateral_alpha5"],
        "pile_reelle_val": {"sharpe_net": tv["series"]["PILE"]["VAL"]["sharpe_net"], "ic95_sharpe": tv["series"]["PILE"]["VAL"]["ic95_sharpe"]},
        "illustration": ss.illustration(dates),
        "puissance": ss.puissance(n_jours=int(tv["series"]["PILE"]["VAL"]["n_jours"])),
    }
    rapport = nettoyer(rapport)
    (RESULTATS / "controle_positif.json").write_text(json.dumps(rapport, indent=2, ensure_ascii=False), encoding="utf-8")
    edge, _ = ss.tirage_illustration(len(dates))
    ag.figure_controle_positif(rapport, edge, dates, FIGURES / "controle_positif.png")

    il, pu = rapport["illustration"], rapport["puissance"]["par_sharpe_vrai"]
    print(f"illustration (Sharpe vrai {il['sharpe_vrai']}) : VAL {il['VAL']['sharpe_net']:.2f} IC95 {il['VAL']['ic95_sharpe']} "
          f"gates {[g + ':' + str(il['gates'][g]['passe']) for g in ('G1', 'G2', 'G3')]}")
    for sr, v in pu.items():
        print(f"Sharpe vrai {sr:>4s} : G1 {v['taux_G1']:.0%}  G2 {v['taux_G2']:.0%}  G3 {v['taux_G3']:.0%}  couverture IC {v['couverture_ic95']:.0%}")


if __name__ == "__main__":
    main()
