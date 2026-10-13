"""Cohérence des sorties « vitrine » : tableau de bord (docs/), blocs de chiffres du README, hygiène des chemins.

Aucune donnée de marché requise : tout est lu dans results/ (versionné)."""
import importlib.util
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
DOCS = RACINE / "docs"
GABARIT = RACINE.parent / "_outils" / "dashboard" / "index.html"


def _json(chemin: Path) -> dict:
    return json.loads(chemin.read_text(encoding="utf-8"))


def test_donnees_du_tableau_de_bord_coherentes_et_sans_test():
    d, tv = _json(DOCS / "data.json"), _json(RACINE / "results" / "train_val.json")
    assert d["frontieres"] == {"train_fin": "2018-12-31", "val_fin": "2022-12-31"}
    assert pd.Timestamp(d["dates"][-1]) < pd.Timestamp("2023-01-01"), "le TEST ne doit jamais apparaître"
    assert [v["id"] for v in d["variantes"]] == ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "PILE"]
    assert sum(1 for v in d["variantes"] if v.get("reference")) == 1          # la pile n'entre pas dans la combinaison
    dates = pd.DatetimeIndex(d["dates"])
    for v in d["variantes"]:
        r = np.array(v["rendements"], dtype=float)
        assert len(r) == len(dates)
        sub = r[(dates >= pd.Timestamp(v["debut"])) & (dates <= pd.Timestamp("2018-12-31"))]
        sharpe = sub.mean() / sub.std(ddof=1) * np.sqrt(252)
        assert abs(sharpe - tv["series"][v["id"]]["TRAIN"]["sharpe_net"]) < 1e-5   # arrondi du CSV à 8 chiffres
    for f in d["filtres"]:
        assert f["type"] in {"min", "max", "choix"}


def test_data_js_identique_a_data_json():
    brut = (DOCS / "data.json").read_text(encoding="utf-8")
    assert (DOCS / "data.js").read_text(encoding="utf-8") == "window.DATA = " + brut + ";\n"
    assert (DOCS / ".nojekyll").exists()


def test_page_du_tableau_de_bord_identique_au_gabarit_commun():
    if not GABARIT.exists():
        return  # dépôt isolé : pas de gabarit à côté
    assert (DOCS / "index.html").read_bytes() == GABARIT.read_bytes()


def test_blocs_de_chiffres_du_readme_lus_dans_results():
    spec = importlib.util.spec_from_file_location("generer_readme_tete", RACINE / "scripts" / "generer_readme_tete.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    tv, tr, csv, frais = mod.charger()
    attendu = {"TETE": mod.bloc_tete(tv, tr, csv, frais), "OVERFIT": mod.bloc_overfit(tv, csv), "VARIANTES": mod.bloc_variantes(tv, tr, csv)}
    texte = (RACINE / "README.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    for nom, contenu in attendu.items():
        m = re.search(rf"<!-- AUTO:{nom} -->\n(.*?)\n<!-- /AUTO:{nom} -->", texte, re.S)
        assert m, f"balises AUTO:{nom} absentes du README"
        assert m.group(1) == contenu, f"bloc AUTO:{nom} périmé : relancer scripts/generer_readme_tete.py"


def test_aucun_chemin_absolu_de_machine_dans_le_depot():
    """Pas de chemin absolu de machine (lecteur, puis dossier Users) dans le code, les notebooks, les README et les résultats.
    PREREGISTRATION.md est exclu : fichier figé et haché, il cite le chemin de la machine d'origine."""
    motif = re.compile(r"[A-Za-z]:[\\/]+Users")
    exclus = {"PREREGISTRATION.md", "test_dashboard_et_readme.py"}
    fautifs = []
    for p in RACINE.rglob("*"):
        if (not p.is_file() or p.name in exclus or p.suffix not in {".py", ".md", ".json", ".ipynb", ".yml", ".txt", ".csv", ".js", ".html"}
                or any(x in p.parts for x in ("cache", "__pycache__", ".pytest_cache", "histdata", ".git"))):
            continue
        if motif.search(p.read_text(encoding="utf-8", errors="ignore")):
            fautifs.append(str(p.relative_to(RACINE)))
    assert not fautifs, fautifs
