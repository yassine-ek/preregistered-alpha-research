"""Audit de la mise en conformité GitHub (13/10) : reproduction à 1e-9, nombre de trades, hypothèses de frais.

1. REPRODUCTION. Recalcule la chaîne complète (TRAIN + VAL, TEST scellé) avec le chargement par HISTDATA_DIR et
   data/frais_editable.csv, et compare chaque statistique de base de results/train_val.json (écart absolu max exigé
   < 1e-9) ainsi que results/rendements_train_val.csv (précision d'écriture du CSV : 8 chiffres significatifs).
2. NOMBRE DE TRADES (TRAIN, VAL) par sleeve, lu dans les poids que le moteur reçoit (aucun code officiel modifié :
   on enveloppe les deux fonctions du moteur le temps du calcul). Un « trade » est un ORDRE EXÉCUTÉ : quotidien = une
   variation de position non nulle sur un actif ; intrajournalier = 2 ordres (ouverture + fermeture) par position prise.
   La pile additionne ses sleeves (aucune compensation, comme pour les coûts).
3. FRAIS : coût par jambe (bps) par classe d'actifs sur l'univers réellement utilisé.

Écrit results/reproduction_et_trades.json. Usage : HISTDATA_DIR=... python scripts/auditer_reproduction_trades_frais.py
Ne charge jamais le TEST (calculer_sleeves(FIN_VAL, test_autorise=False) sous le lecteur 1 h strict de l'approfondissement).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from alpha import donnees as d  # noqa: E402
from alpha import moteur  # noqa: E402
from alpha import pipeline as pl  # noqa: E402
from alpha.approfondissement.chargement import lecteur_strict  # noqa: E402
from alpha.couts import FICHIER_FRAIS, charger_couts  # noqa: E402
import verifier_donnees  # noqa: E402  (message guidé si les données manquent)

RESULTATS = RACINE / "results"
CHAMPS = ["n_jours", "sharpe_net", "sharpe_brut", "rendement_annuel_net", "vol_annuelle",
          "drawdown_max", "rotation_annuelle", "cout_annuel"]


def _capturer():
    """Enveloppe resultat_quotidien / resultat_intrajournalier : mémorise leurs entrées, rend le même résultat."""
    prises = {"quotidien": {}, "intra": {}}
    q0, i0 = moteur.resultat_quotidien, moteur.resultat_intrajournalier

    def q(nom, poids, rend, couts_bps):
        prises["quotidien"][nom] = poids
        return q0(nom, poids, rend, couts_bps)

    def i(nom, poids, ret_fenetre, date_pnl, couts_bps, calendrier):
        prises["intra"][nom] = (poids, ret_fenetre)
        return i0(nom, poids, ret_fenetre, date_pnl, couts_bps, calendrier)

    return prises, (q0, i0), (q, i)


def _trades_quotidien(poids: pd.DataFrame) -> pd.Series:
    detenu = poids.fillna(0.0).shift(1).fillna(0.0)
    delta = detenu.diff().fillna(detenu).abs()
    return (delta > 1e-12).sum(axis=1)


def _trades_intra(poids: pd.DataFrame, ret: pd.DataFrame) -> pd.Series:
    cols = list(poids.columns)
    w = poids.reindex(columns=cols).fillna(0.0).to_numpy()
    r = ret.reindex(index=poids.index, columns=cols).to_numpy()
    prises = (w != 0) & np.isfinite(r)
    return pd.Series(2 * prises.sum(axis=1), index=poids.index)


def main() -> None:
    t0 = time.time()
    verifier_donnees.exiger_donnees()
    officiel = json.loads((RESULTATS / "train_val.json").read_text(encoding="utf-8"))

    prises, (q0, i0), (q, i) = _capturer()
    moteur.resultat_quotidien, moteur.resultat_intrajournalier = q, i
    try:
        with lecteur_strict():  # lecteur 1 h qui s'arrête avant 2023 : aucune ligne de TEST n'est même parsée
            sortie = pl.calculer_sleeves(d.FIN_VAL, test_autorise=False, verbeux=True)
    finally:
        moteur.resultat_quotidien, moteur.resultat_intrajournalier = q0, i0
    res = sortie["resultats"]
    pile, _, _ = pl.construire_pile(res)
    tout = {**res, "PILE": pile}

    # ---------------------------------------------------------------- 1. reproduction
    ecarts, pire = {}, 0.0
    for k, r in tout.items():
        for nom, (deb, fin) in {"TRAIN": (d.DEBUT_DONNEES, d.FIN_TRAIN), "VAL": (d.DEBUT_VAL, d.FIN_VAL)}.items():
            neuf = pl.stats_periode(r, deb, fin, avec_ic=False)
            ref = officiel["series"][k][nom]
            e = {c: abs(float(neuf[c]) - float(ref[c])) for c in CHAMPS}
            ecarts[f"{k}_{nom}"] = max(e.values())
            pire = max(pire, ecarts[f"{k}_{nom}"])
    sharpe_val = {k: abs(pl.stats_periode(r, d.DEBUT_VAL, d.FIN_VAL, avec_ic=False)["sharpe_net"]
                         - officiel["series"][k]["VAL"]["sharpe_net"]) for k, r in tout.items()}
    csv = pd.read_csv(RESULTATS / "rendements_train_val.csv", index_col=0, parse_dates=True)
    ecart_csv = 0.0
    for k, r in tout.items():
        for champ, serie in (("brut", r.brut), ("cout", r.cout)):
            a = serie.reindex(csv.index).to_numpy()
            b = csv[f"{k}_{champ}"].to_numpy()
            ecart_csv = max(ecart_csv, float(np.max(np.abs(a - b) / (np.abs(a) + 1e-12))))
    assert pire < 1e-9, f"reproduction KO : écart max {pire}"
    assert max(sharpe_val.values()) < 1e-9
    assert ecart_csv < 1e-6, f"CSV des rendements différent : {ecart_csv}"

    # ---------------------------------------------------------------- 2. trades
    nb = {}
    for k in res:
        if k in prises["quotidien"]:
            par_jour = _trades_quotidien(prises["quotidien"][k])
        else:
            par_jour = _trades_intra(*prises["intra"][k])
        nb[k] = {"TRAIN": int(par_jour.loc[: d.FIN_TRAIN].sum()), "VAL": int(par_jour.loc[d.DEBUT_VAL:].sum())}
    nb["PILE"] = {p: sum(nb[k][p] for k in res) for p in ("TRAIN", "VAL")}

    # ---------------------------------------------------------------- 3. frais
    couts = charger_couts()
    brut = pd.read_csv(FICHIER_FRAIS, encoding="utf-8", encoding_errors="replace")
    classe = dict(zip(brut["actif"], brut["classe"].astype(str)))
    univers = d.univers()
    tab = pd.DataFrame({"cout": couts.reindex(univers), "classe": [classe.get(a, "?") for a in univers]}, index=univers)
    classes = {}
    for c, g in tab.groupby("classe"):
        libelle = "Matière première / métal" if c.startswith("Mati") else c
        classes[libelle] = {"n_actifs": int(len(g)), "min_bps": float(g["cout"].min()),
                            "mediane_bps": float(g["cout"].median()), "max_bps": float(g["cout"].max())}

    out = {
        "meta": {"description": "Audit du 13/10 (chemins relatifs, HISTDATA_DIR) : reproduction, nombre de trades, frais",
                 "date": pd.Timestamp.now().strftime("%Y-%m-%d"), "test": "scellé, non chargé",
                 "dernier_jour_calcule": str(pile.net.index.max().date()), "duree_s": round(time.time() - t0)},
        "reproduction": {"tolerance": 1e-9, "ecart_max_toutes_statistiques": pire,
                         "ecart_max_sharpe_net_val": max(sharpe_val.values()),
                         "ecart_sharpe_net_val_par_serie": sharpe_val,
                         "ecart_relatif_max_csv_rendements": ecart_csv,
                         "champs_compares": CHAMPS, "series": list(tout)},
        "nb_trades": {"definition": "ordres exécutés : quotidien = variations de position non nulles par actif ; "
                                    "intrajournalier = 2 ordres (ouverture, fermeture) par position ; pile = somme des sleeves",
                      "par_serie": nb},
        "frais_univers": {"n_actifs": len(univers), "source_fichier": "data/frais_editable.csv",
                          "regle": "override sinon frais_bps_par_jambe ; indices figés à 12 bps ; coût = bps x |delta position|",
                          "par_classe": classes},
    }
    (RESULTATS / "reproduction_et_trades.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"écart max (toutes statistiques TRAIN/VAL) : {pire:.2e} ; Sharpe net VAL : {max(sharpe_val.values()):.2e} ; CSV : {ecart_csv:.2e}")
    print("trades :", json.dumps(nb))
    print("frais :", json.dumps(classes, ensure_ascii=False))
    print(f"terminé en {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
