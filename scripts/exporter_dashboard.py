"""Exporte le tableau de bord interactif (gabarit commun de tableau de bord) dans docs/.

Lit UNIQUEMENT des fichiers de results/ (aucune donnée de marché requise, donc exécutable en CI) :
  - results/rendements_train_val.csv   rendements quotidiens bruts et coûts (TRAIN + VAL ; le TEST n'existe pas)
  - results/train_val.json             statistiques officielles (Sharpe, drawdown, début d'activité)
  - results/reproduction_et_trades.json  nombre de trades et frais par classe (facultatif)
Écrit docs/data.json, docs/data.js (même contenu, pour l'ouverture en file://), docs/index.html (copie du gabarit
s'il est présent à côté du dépôt, sinon on garde celui de docs/) et docs/.nojekyll.

Usage : python scripts/exporter_dashboard.py
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
RESULTATS = RACINE / "results"
DOCS = RACINE / "docs"
GABARIT = RACINE.parent / "_outils" / "dashboard" / "index.html"  # présent seulement dans le dépôt d'origine ; ici, docs/index.html est déjà versionné

# (libellé, fréquence, classe d'actifs principale)
SLEEVES = {
    "S1": ("quotidienne", "Multi-actifs"),
    "S2": ("quotidienne", "FX"),
    "S3": ("quotidienne", "FX"),
    "S4": ("intrajournalière", "FX"),
    "S5": ("intrajournalière", "FX"),
    "S6": ("quotidienne", "Indices"),
    "S7": ("intrajournalière", "Indices"),
}


# une phrase (balises description / og du tableau de bord), 160 caractères au plus
DESCRIPTION = "7 stratégies de la littérature sous protocole pré-enregistré, coûts réels, test scellé : filtrez les sleeves, lisez la pile (verdict : échec)."
assert len(DESCRIPTION) <= 160


def _chiffre(x: float) -> float:
    return float(f"{x:.8g}")


def _fmt(x: float, d: int = 1) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def texte_frais(trades_json: dict | None, tv: dict) -> str:
    morceaux = []
    if trades_json:
        cl = trades_json["frais_univers"]["par_classe"]
        morceaux.append(
            "coûts réels par jambe en bps (médiane, min-max) : "
            + " ; ".join(f"{nom} {_fmt(v['mediane_bps'], 2)}" + ("" if v["min_bps"] == v["max_bps"] else f" ({_fmt(v['min_bps'], 2)}-{_fmt(v['max_bps'], 2)})")
                         for nom, v in cl.items())
            + ", indices figés à 12 bps ; coût = bps × |Δ position|")
    morceaux.append("exécution décalée (un jour plein pour les sleeves quotidiennes, une minute en intrajournalier)")
    p = tv["meta"]["periodes"]
    morceaux.append(f"TRAIN {p['TRAIN'][0][:4]}-{p['TRAIN'][1][:4]}, VAL {p['VAL'][0][:4]}-{p['VAL'][1][:4]}, TEST 2023+ scellé")
    morceaux.append("la pile du pré-enregistrement (poids ∝ 1/vol TRAIN) est la courbe orange en pointillés ; "
                    "la courbe bleue est la moyenne équipondérée des sleeves retenues par les filtres")
    return ". ".join(m[0].upper() + m[1:] for m in morceaux) + "."


def main() -> None:
    tv = json.loads((RESULTATS / "train_val.json").read_text(encoding="utf-8"))
    chemin_tr = RESULTATS / "reproduction_et_trades.json"
    tr = json.loads(chemin_tr.read_text(encoding="utf-8")) if chemin_tr.exists() else None
    csv = pd.read_csv(RESULTATS / "rendements_train_val.csv", index_col=0, parse_dates=True)
    fin_val = pd.Timestamp(tv["meta"]["periodes"]["VAL"][1])
    fin_train = pd.Timestamp(tv["meta"]["periodes"]["TRAIN"][1])
    assert csv.index.max() <= fin_val, "le TEST ne doit jamais apparaître"
    dates = [d.strftime("%Y-%m-%d") for d in csv.index]

    variantes = []
    for k in [*SLEEVES, "PILE"]:
        net = (csv[f"{k}_brut"] - csv[f"{k}_cout"]).to_numpy()
        actif = ((csv[f"{k}_brut"] != 0) | (csv[f"{k}_cout"] != 0))
        s = tv["series"][k]
        stats = {
            "sharpe_train": s["TRAIN"]["sharpe_net"], "sharpe_val": s["VAL"]["sharpe_net"],
            "drawdown_train_pct": round(-100 * s["TRAIN"]["drawdown_max"], 2),
            "drawdown_val_pct": round(-100 * s["VAL"]["drawdown_max"], 2),
            "jours_actifs_train": int(actif.loc[:fin_train].sum()), "jours_actifs_val": int(actif.loc[fin_train + pd.Timedelta(days=1):].sum()),
            "cout_annuel_val_pct": round(100 * s["VAL"]["cout_annuel"], 2),
        }
        if tr:
            stats["nb_trades_train"] = tr["nb_trades"]["par_serie"][k]["TRAIN"]
            stats["nb_trades_val"] = tr["nb_trades"]["par_serie"][k]["VAL"]
        v = {"id": k, "libelle": s["nom"], "debut": s["debut_actif"],
             "rendements": [_chiffre(x) for x in net], "stats": stats}
        if k == "PILE":
            v.update({"groupe": "pile", "classe": "Multi-actifs", "reference": True, "libelle": "Pile du pré-enregistrement (poids ∝ 1/vol TRAIN)"})
        else:
            v.update({"groupe": SLEEVES[k][0], "classe": SLEEVES[k][1]})
        variantes.append(v)

    filtres = [
        {"cle": "jours_actifs_train", "libelle": "Jours actifs min (TRAIN)", "type": "min"},
        {"cle": "sharpe_train", "libelle": "Sharpe TRAIN min", "type": "min"},
        {"cle": "drawdown_train_pct", "libelle": "Drawdown TRAIN max (%)", "type": "max"},
        {"cle": "groupe", "libelle": "Fréquence", "type": "choix"},
        {"cle": "classe", "libelle": "Classe d'actifs", "type": "choix"},
    ]
    if tr:
        filtres.insert(0, {"cle": "nb_trades_train", "libelle": "Nb de trades min (TRAIN, ordres exécutés)", "type": "min"})

    data = {
        "titre": "Alpha pré-enregistré : 7 stratégies simples et leur pile (verdict : échec)",
        "description": DESCRIPTION,
        "sous_titre": "Filtrer les sleeves sur leurs statistiques TRAIN, combiner celles qui restent, lire la courbe sur TRAIN puis VAL. "
                      "Attention : VAL (2019-2022) avait déjà été vue lors d'un projet de recherche antérieur ; seul TEST (2023+, scellé) est vierge.",
        "frais": texte_frais(tr, tv),
        "frontieres": {"train_fin": str(fin_train.date()), "val_fin": str(fin_val.date())},
        "dates": dates,
        "variantes": variantes,
        "filtres": filtres,
        "combinaison": "moyenne",
    }
    texte = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    DOCS.mkdir(exist_ok=True)
    (DOCS / "data.json").write_text(texte, encoding="utf-8")
    (DOCS / "data.js").write_text("window.DATA = " + texte + ";\n", encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    if GABARIT.exists():
        shutil.copyfile(GABARIT, DOCS / "index.html")
    assert (DOCS / "index.html").exists(), "docs/index.html manquant (gabarit introuvable)"
    print(f"docs/data.json + data.js : {len(texte) / 1e6:.2f} Mo, {len(dates)} dates ({dates[0]} -> {dates[-1]}), {len(variantes)} variantes")


if __name__ == "__main__":
    main()
