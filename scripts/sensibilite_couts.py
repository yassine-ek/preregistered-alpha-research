"""EXPLORATOIRE, non pré-enregistré, ne modifie pas le verdict : sensibilité du Sharpe net aux coûts.

Recalcule, sur TRAIN et VAL uniquement (TEST scellé : jamais chargé), le Sharpe net de chaque sleeve et
de la pile pour des multiplicateurs de coût {0 ; 0,1 ; 0,25 ; 0,5 ; 1} appliqués au coût réel par actif de
data/frais_editable.csv, puis le coût de rentabilité (break-even) de chaque sleeve sur VAL.

Méthode. Les positions ne dépendent pas des coûts et le coût est linéaire dans le vecteur de coûts :
net(m) = brut - m x coût, exactement. La pile est reconstruite à chaque m par la procédure du prereg
(poids 1/vol réalisée nette sur TRAIN, échelle à 10 % de vol sur TRAIN) ; ses poids bougent donc
légèrement avec m. Break-even d'une sleeve : m* = moyenne(brut) / moyenne(coût) sur VAL, exprimé en bps
par jambe via le coût moyen effectif Somme(coût) / Somme(rotation) de la sleeve sur VAL.

Usage : python scripts/sensibilite_couts.py
Sorties : results/sensibilite_couts_exploratoire.json, figures/sensibilite_couts.png
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from alpha import donnees as d  # noqa: E402
from alpha import graphiques as g  # noqa: E402
from alpha import moteur  # noqa: E402
from alpha import pipeline as pl  # noqa: E402
import verifier_donnees  # noqa: E402  (message guidé si les données manquent)

TITRE = "EXPLORATOIRE — non pré-enregistré, ne modifie pas le verdict"
MULTIPLICATEURS = [0.0, 0.1, 0.25, 0.5, 1.0]
GRILLE_FIGURE = np.round(np.linspace(0.0, 1.0, 21), 2)


def mis_a_l_echelle(res: dict, m: float) -> dict:
    return {k: moteur.Resultat(r.nom, r.brut, r.cout * m, r.rotation, r.debut) for k, r in res.items()}


def sharpes(res: dict, m: float) -> dict:
    """{'TRAIN': {série: Sharpe}, 'VAL': {...}} pour les 7 sleeves et la pile reconstruite au multiplicateur m."""
    echelle = mis_a_l_echelle(res, m)
    pile, _, _ = pl.construire_pile(echelle)
    tout = {**echelle, "PILE": pile}
    return {nom: {k: pl.stats_periode(r, a, b, avec_ic=False)["sharpe_net"] for k, r in tout.items()}
            for nom, (a, b) in {"TRAIN": (d.DEBUT_DONNEES, d.FIN_TRAIN), "VAL": (d.DEBUT_VAL, d.FIN_VAL)}.items()}


def rentabilite_val(r: moteur.Resultat) -> dict:
    sub = r.tranche(max(d.DEBUT_VAL, r.debut), d.FIN_VAL)
    mb, mc = float(sub.brut.mean()), float(sub.cout.mean())
    c_moy = float(sub.cout.sum() / sub.rotation.sum() * 1e4) if sub.rotation.sum() > 0 else None  # bps par jambe
    out = {"cout_moyen_effectif_bps_par_jambe": c_moy, "sharpe_brut_val": float(sub.brut.mean() / sub.brut.std(ddof=1) * np.sqrt(252))}
    if mb <= 0:
        out.update(multiplicateur_rentabilite=None, cout_rentabilite_bps_par_jambe=None,
                   statut="jamais rentable : le rendement brut VAL est déjà <= 0, aucun coût positif ni nul n'y change rien")
    else:
        mstar = mb / mc
        out.update(multiplicateur_rentabilite=float(mstar),
                   cout_rentabilite_bps_par_jambe=None if c_moy is None else float(mstar * c_moy),
                   statut="rentable (Sharpe net > 0) tant que le coût reste sous ce seuil")
    return out


def figure(courbes: dict, chemin: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2), sharex=True)
    for ax, (bas, haut, sous) in zip(axes, ((None, None, "échelle complète"), (-2.5, 1.5, "zoom"))):
        for k, y in courbes.items():
            # S3 et S5 ont presque le même Sharpe : S3 en pointillés pour qu'on voie les deux courbes
            ax.plot(GRILLE_FIGURE, y, color=g.COULEURS[k], lw=2.6 if k == "PILE" else 1.4,
                    ls="--" if k == "S3" else "-", label=k)
        ax.axhline(0, color="black", lw=0.8)
        ax.axhline(1.0, color="green", ls="--", lw=1, label="seuil G1 de la pile (1,0)")
        ax.set_xlabel("multiplicateur de coût (1 = coûts réels du fichier, 0 = sans coûts)")
        ax.set_title(f"Sharpe net VAL 2019-2022, {sous}")
        ax.grid(alpha=0.3)
        if haut is not None:
            ax.set_ylim(bas, haut)
    axes[0].set_ylabel("Sharpe net annualisé, VAL")
    axes[1].legend(fontsize=8, ncol=2, loc="lower right")
    fig.suptitle(TITRE, fontweight="bold", color="#b00020")
    g._sauver(fig, chemin)


def main() -> None:
    verifier_donnees.exiger_donnees()
    sortie = pl.calculer_sleeves(d.FIN_VAL, test_autorise=False)  # TRAIN + VAL seulement
    res = sortie["resultats"]
    assert max(r.net.index.max() for r in res.values()) < d.DEBUT_TEST

    table = {m: sharpes(res, m) for m in MULTIPLICATEURS}
    # garde-fou : à m = 1 on retrouve exactement les chiffres du run officiel
    officiel = json.loads((RACINE / "results" / "train_val.json").read_text(encoding="utf-8"))
    for k, s in officiel["series"].items():
        assert abs(table[1.0]["VAL"][k] - s["VAL"]["sharpe_net"]) < 1e-9, f"{k} : m=1 ne reproduit pas train_val.json"

    pile_base, _, _ = pl.construire_pile(res)
    rentab = {k: rentabilite_val(r) for k, r in res.items()}
    rentab["PILE"] = rentabilite_val(pile_base)  # pile à poids du multiplicateur 1 (approximation, voir en-tête)
    courbes = {k: [] for k in [*res, "PILE"]}
    for m in GRILLE_FIGURE:
        s = sharpes(res, float(m))["VAL"]
        for k in courbes:
            courbes[k].append(s[k])
    figure(courbes, RACINE / "figures" / "sensibilite_couts.png")

    verdict = json.loads((RACINE / "results" / "verdict_alpha.json").read_text(encoding="utf-8"))
    rapport = {
        "titre": TITRE,
        "avertissement": "Analyse a posteriori sur TRAIN/VAL, hors pré-enregistrement : elle sert à localiser la sensibilité "
                         "aux coûts, pas à sélectionner une sleeve ni à rouvrir le verdict. TEST non chargé.",
        "verdict_officiel_inchange": {"verdict": verdict["verdict"], "statut_test": verdict["statut_test"]},
        "methode": "net(m) = brut - m x coût (positions indépendantes des coûts) ; pile reconstruite à chaque m par la procédure du prereg.",
        "multiplicateurs": MULTIPLICATEURS,
        "sharpe_net": {per: {k: {str(m): table[m][per][k] for m in MULTIPLICATEURS} for k in table[1.0][per]}
                       for per in ("TRAIN", "VAL")},
        "courbe_val": {"multiplicateurs": GRILLE_FIGURE.tolist(), "sharpe_net": courbes},
        "cout_rentabilite_val": rentab,
    }
    chemin = RACINE / "results" / "sensibilite_couts_exploratoire.json"
    chemin.write_text(json.dumps(_nettoyer(rapport), indent=2, ensure_ascii=False), encoding="utf-8")

    print(TITRE)
    print(f"{'':6s}" + "".join(f"{'x' + str(m):>8s}" for m in MULTIPLICATEURS) + "   | VAL ; TRAIN à x0 / x1")
    for k in courbes:
        v = "".join(f"{table[m]['VAL'][k]:8.2f}" for m in MULTIPLICATEURS)
        print(f"{k:6s}{v}   | TRAIN {table[0.0]['TRAIN'][k]:6.2f} / {table[1.0]['TRAIN'][k]:6.2f}")
    print("break-even VAL (bps/jambe) :", {k: (None if v['cout_rentabilite_bps_par_jambe'] is None else round(v['cout_rentabilite_bps_par_jambe'], 2),
                                          None if v['cout_moyen_effectif_bps_par_jambe'] is None else round(v['cout_moyen_effectif_bps_par_jambe'], 2))
                                      for k, v in rentab.items()})


def _nettoyer(o):
    if isinstance(o, dict):
        return {k: _nettoyer(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_nettoyer(v) for v in o]
    if isinstance(o, (float, np.floating)):
        return None if not np.isfinite(o) else float(o)
    return o


if __name__ == "__main__":
    main()
