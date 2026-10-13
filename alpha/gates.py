"""Gates et verdict (prereg, section 8). Aucun seuil n'est ajustable ici.

G1 : Sharpe net VAL de la pile >= 1,0
G2 : borne basse de l'IC 95 % bootstrap du Sharpe VAL de la pile > 0
G3 : DSR VAL (N = 8) >= 0,95
G4 : TEST (lecture unique) : Sharpe net > 0 ET >= 0,5 x Sharpe VAL
Objectif utilisateur (non bloquant) : Sharpe net >= 2.
"""
from __future__ import annotations

import json
from pathlib import Path

SEUIL_G1 = 1.0
SEUIL_G3 = 0.95
FACTEUR_G4 = 0.5
OBJECTIF_UTILISATEUR = 2.0


def evaluer_gates_val(pile_val: dict, dsr_pile: float) -> dict:
    """G1, G2, G3 sur la pile (VAL). `pile_val` : stats VAL avec sharpe_net et ic95_sharpe."""
    sh = pile_val["sharpe_net"]
    bas = pile_val["ic95_sharpe"][0]
    return {
        "G1": {"critere": f"Sharpe net VAL >= {SEUIL_G1}", "valeur": sh, "passe": bool(sh >= SEUIL_G1)},
        "G2": {"critere": "borne basse IC95 bootstrap du Sharpe VAL > 0", "valeur": bas, "passe": bool(bas > 0)},
        "G3": {"critere": f"DSR VAL (N=8) >= {SEUIL_G3}", "valeur": dsr_pile, "passe": bool(dsr_pile >= SEUIL_G3)},
        "objectif_utilisateur_sharpe_2": {"valeur": sh, "atteint": bool(sh >= OBJECTIF_UTILISATEUR)},
    }


def evaluer_g4(sharpe_test: float, sharpe_val: float) -> dict:
    ok = bool(sharpe_test > 0 and sharpe_test >= FACTEUR_G4 * sharpe_val)
    return {"critere": f"Sharpe net TEST > 0 et >= {FACTEUR_G4} x Sharpe VAL", "valeur": sharpe_test,
            "seuil_coherence": FACTEUR_G4 * sharpe_val, "passe": ok}


def test_ouvrable(gates_val: dict) -> bool:
    """Le TEST n'est ouvert que si G1 ET G2 passent."""
    return bool(gates_val["G1"]["passe"] and gates_val["G2"]["passe"])


def verdict(gates: dict, test_ouvert: bool) -> tuple[str, str]:
    """(verdict, statut du TEST).
    ECHEC dès que G1 ou G2 échoue (le TEST reste scellé) ; TEST_NON_OUVERT si G1 et G2
    passent mais que le TEST n'a pas encore été lu ; sinon SUCCES ssi G1 à G4 passent."""
    if not test_ouvrable(gates):
        return "ECHEC", "scelle_G1_ou_G2_en_echec"
    if not test_ouvert:
        return "TEST_NON_OUVERT", "ouvrable_non_encore_lu"
    tous = all(gates[g]["passe"] for g in ("G1", "G2", "G3", "G4"))
    return ("SUCCES" if tous else "ECHEC"), "ouvert"


def conditions_ouverture_test(train_val: dict | None, chemin_test_ouvert: Path) -> tuple[bool, str]:
    """Garde-fou de ouvrir_test.py. Retourne (autorise, raison)."""
    if Path(chemin_test_ouvert).exists():
        return False, f"{chemin_test_ouvert} existe déjà : le TEST ne s'ouvre qu'une fois"
    if train_val is None:
        return False, "results/train_val.json absent : lancer run_train_val.py d'abord"
    gates = train_val["gates"]
    if not test_ouvrable(gates):
        return False, ("G1 ou G2 échoue sur VAL "
                       f"(G1={gates['G1']['passe']}, G2={gates['G2']['passe']}) : TEST reste scellé")
    return True, "G1 et G2 passent sur VAL"


def lire_json(chemin: Path) -> dict | None:
    chemin = Path(chemin)
    if not chemin.exists():
        return None
    return json.loads(chemin.read_text(encoding="utf-8"))


def construire_verdict(train_val: dict, test: dict | None = None) -> dict:
    """Assemble results/verdict_alpha.json à partir de train_val.json (+ test_ouvert.json
    s'il existe). Tous les chiffres par sleeve et pour la pile y figurent."""
    gates = {k: dict(v) for k, v in train_val["gates"].items()}
    pile_val = train_val["series"]["PILE"]["VAL"]
    test_ouvert = test is not None
    if test_ouvert:
        g4 = evaluer_g4(test["series"]["PILE"]["TEST"]["sharpe_net"], pile_val["sharpe_net"])
        gates["G4"] = g4
    else:
        gates["G4"] = {"critere": f"Sharpe net TEST > 0 et >= {FACTEUR_G4} x Sharpe VAL",
                       "valeur": None, "passe": None, "statut": "TEST non ouvert"}
    verdict_final, statut_test = verdict(gates, test_ouvert)
    echecs = [g for g in ("G1", "G2", "G3", "G4") if gates[g]["passe"] is False]
    sleeves = {}
    for k, v in train_val["series"].items():
        sleeves[k] = {"nom": v["nom"], "debut_actif": v["debut_actif"], "TRAIN": v["TRAIN"], "VAL": v["VAL"]}
        if test_ouvert:
            sleeves[k]["TEST"] = test["series"][k]["TEST"]
    return {
        "verdict": verdict_final,
        "statut_test": statut_test,
        "gates_en_echec": echecs,
        "gates": gates,
        "objectif_utilisateur_sharpe_net_2": {
            "sharpe_net_val_pile": pile_val["sharpe_net"],
            "atteint_en_val": bool(pile_val["sharpe_net"] >= OBJECTIF_UTILISATEUR),
        },
        "n_essais_dsr": train_val["meta"]["n_essais_dsr"],
        "hash_prereg_sha256": train_val["meta"]["prereg_sha256"],
        "code_sha256_train_val": train_val["meta"]["code_sha256"],
        "test": ({"horodatage": test["horodatage"], "code_sha256": test["code_sha256"]} if test_ouvert else "scellé"),
        "poids_pile": train_val["poids_pile"],
        "kappa_pile": train_val["meta"]["kappa_pile"],
        "contribution_annuelle_pile_val": train_val["contribution_annuelle_pile_val"],
        "correlations": train_val["correlations"],
        "sleeves_et_pile": sleeves,
    }
