"""OUVRE LE TEST (2023-01-01 -> fin des données), UNE SEULE FOIS.

Ne pas lancer à la légère. Ce script :
 1. refuse de tourner si results/test_ouvert.json existe déjà, si results/train_val.json est
    absent, ou si G1 ou G2 échoue sur VAL (prereg section 8), ou si l'empreinte de
    PREREGISTRATION_v1.md (version d'origine) ou le lien v1 -> PREREGISTRATION.md ne tient plus ;
 2. recalcule la chaîne complète avec test_autorise=True (mêmes paramètres, mêmes poids de
    pile calibrés sur TRAIN) et vérifie que les chiffres TRAIN/VAL sont identiques à ceux de
    train_val.json (preuve que rien de causal n'a changé en ajoutant des données futures) ;
 3. calcule les statistiques TEST EN MÉMOIRE, puis écrit d'un coup results/test_ouvert.json
    (horodatage + SHA-256 du code + chiffres) et results/verdict_alpha.json. Le fichier est
    créé en mode exclusif : impossible de relire le TEST, même par deux lancements simultanés.
    Un plantage AVANT l'écriture n'a rien révélé et peut être relancé ; après, c'est fini.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from alpha import donnees as d  # noqa: E402
from alpha import gates  # noqa: E402
from alpha import pipeline as pl  # noqa: E402
import verifier_donnees  # noqa: E402  (message guidé si les données manquent)
import verifier_prereg  # noqa: E402  (empreinte de la v1, fins de ligne normalisées)

RESULTATS = RACINE / "results"
CHEMIN_TEST = RESULTATS / "test_ouvert.json"


def nettoyer(o):
    if isinstance(o, dict):
        return {k: nettoyer(v) for k, v in o.items()}
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
    train_val = gates.lire_json(RESULTATS / "train_val.json")
    autorise, raison = gates.conditions_ouverture_test(train_val, CHEMIN_TEST)
    if not autorise:
        sys.exit(f"REFUS : {raison}")
    # on vérifie la version d'ORIGINE (PREREGISTRATION_v1.md) : le fichier courant contient les avenants, donc son hash brut diffère
    if verifier_prereg.sha256_v1() != train_val["meta"]["prereg_sha256"]:
        sys.exit("REFUS : PREREGISTRATION_v1.md ne correspond plus à l'empreinte de train_val.json (hash différent)")
    ecarts = verifier_prereg.verifier()
    if ecarts:
        sys.exit("REFUS : PREREGISTRATION.md n'est plus la v1 + avenants : " + " ; ".join(ecarts))

    verifier_donnees.exiger_donnees()
    # dernière date disponible dans les données 1 h (aucune statistique TEST n'est lue ici)
    fin = d.charger_1h("EURUSD", fin=pd.Timestamp("2100-01-01"), test_autorise=True).index.max().normalize()
    sortie = pl.calculer_sleeves(fin, test_autorise=True, verbeux=True)
    res = sortie["resultats"]
    pile, poids_pile, kappa = pl.construire_pile(res)
    tout = {**res, "PILE": pile}

    # contrôle de causalité : TRAIN et VAL doivent être inchangés
    for k, r in tout.items():
        for nom, (a, b) in {"TRAIN": (d.DEBUT_DONNEES, d.FIN_TRAIN), "VAL": (d.DEBUT_VAL, d.FIN_VAL)}.items():
            s_neuf = pl.stats_periode(r, a, b, avec_ic=False)["sharpe_net"]
            s_ref = train_val["series"][k][nom]["sharpe_net"]
            if abs(s_neuf - s_ref) > 1e-6:
                sys.exit(f"ERREUR : {k} {nom} Sharpe {s_neuf} != {s_ref} de train_val.json (non causal ?)")

    series = {k: {"TEST": pl.stats_periode(r, d.DEBUT_TEST, fin)} for k, r in tout.items()}
    horodatage = datetime.now().isoformat(timespec="seconds")
    contenu = {
        "horodatage": horodatage,
        "code_sha256": pl.sha256_code(),
        "prereg_sha256": train_val["meta"]["prereg_sha256"],
        "periode_test": [str(d.DEBUT_TEST.date()), str(fin.date())],
        "poids_pile_calibres_sur_train": poids_pile,
        "kappa_pile": kappa,
        "series": series,
    }
    contenu["gates_g4"] = gates.evaluer_g4(series["PILE"]["TEST"]["sharpe_net"],
                                            train_val["series"]["PILE"]["VAL"]["sharpe_net"])
    # création exclusive : échoue si le fichier est apparu entre-temps
    with open(CHEMIN_TEST, "x", encoding="utf-8") as f:
        json.dump(nettoyer(contenu), f, indent=2, ensure_ascii=False)
    verdict = gates.construire_verdict(train_val, nettoyer(contenu))
    (RESULTATS / "verdict_alpha.json").write_text(json.dumps(nettoyer(verdict), indent=2, ensure_ascii=False),
                                                  encoding="utf-8")
    p = series["PILE"]["TEST"]
    print(f"TEST ouvert le {horodatage} : pile Sharpe net {p['sharpe_net']:.2f} "
          f"IC95 [{p['ic95_sharpe'][0]:.2f} ; {p['ic95_sharpe'][1]:.2f}] -> verdict {verdict['verdict']}")


if __name__ == "__main__":
    main()
