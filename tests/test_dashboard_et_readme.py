"""Cohérence des sorties « vitrine » : tableau de bord (docs/), blocs de chiffres du README et de docs/*.md, premier écran du README.

Aucune donnée de marché requise : tout est lu dans results/ (versionné). L'hygiène des chemins est dans test_hygiene_depot.py."""
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


def test_titre_et_description_du_tableau_de_bord():
    """Titre propre au projet (sans numéro interne), description d'une phrase pour les balises description / og, VAL dite non vierge."""
    d = _json(DOCS / "data.json")
    assert d["titre"] and not d["titre"].startswith("Projet 0")
    assert 0 < len(d["description"]) <= 160
    assert "projet de recherche antérieur" in d["sous_titre"]


def test_data_js_identique_a_data_json():
    brut = (DOCS / "data.json").read_text(encoding="utf-8")
    assert (DOCS / "data.js").read_text(encoding="utf-8") == "window.DATA = " + brut + ";\n"
    assert (DOCS / ".nojekyll").exists()


def test_page_du_tableau_de_bord_identique_au_gabarit_commun():
    if not GABARIT.exists():
        return  # dépôt isolé : pas de gabarit à côté
    assert (DOCS / "index.html").read_bytes() == GABARIT.read_bytes()


def test_blocs_de_chiffres_des_documents_lus_dans_results():
    """Chaque bloc AUTO du README et de docs/*.md est exactement ce que scripts/generer_readme_tete.py calcule depuis results/."""
    spec = importlib.util.spec_from_file_location("generer_readme_tete", RACINE / "scripts" / "generer_readme_tete.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    attendu = mod.blocs()
    assert set(attendu) == {"README.md", "docs/resultats_detailles.md", "docs/approfondissement.md"}
    for fichier, contenus in attendu.items():
        texte = (RACINE / fichier).read_text(encoding="utf-8").replace("\r\n", "\n")
        for nom, contenu in contenus.items():
            m = re.search(rf"<!-- AUTO:{nom} -->\n(.*?)\n<!-- /AUTO:{nom} -->", texte, re.S)
            assert m, f"balises AUTO:{nom} absentes de {fichier}"
            assert m.group(1) == contenu, f"bloc AUTO:{nom} de {fichier} périmé : relancer scripts/generer_readme_tete.py"


def test_rendements_inferieurs_a_moins_100_pct_affiches_ruine():
    """Un rendement annuel inférieur à −100 % n'existe pas pour un capital réel : le README affiche « ruine », pas −190,9 %."""
    spec = importlib.util.spec_from_file_location("generer_readme_tete", RACINE / "scripts" / "generer_readme_tete.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.rend(-1.909) == "ruine (< −100 %)" and mod.rend(-0.524) == "−52,4 %"
    texte = (RACINE / "README.md").read_text(encoding="utf-8")
    assert "190,9" not in texte and "134,2" not in texte and "ruine" in texte


def test_readme_court_et_premier_ecran_conforme():
    """README <= 400 lignes ; résultats clés, badge CI vivant et figure héro dans les 45 premières lignes ; provenance présente."""
    texte = (RACINE / "README.md").read_text(encoding="utf-8")
    lignes = texte.splitlines()
    tete = "\n".join(lignes[:45])
    assert len(lignes) <= 400
    assert "## Résultats clés" in tete and "actions/workflows/tests.yml/badge.svg" in tete and "figures/hero_equity.png" in tete
    assert "## Comment ce projet a été construit" in texte
    assert "9853" + "f2b" not in texte                 # le commit d'origine n'est pas une preuve publique
    assert "https://yassine-ek.github.io/preregistered-alpha-research/" in texte


def test_tous_les_liens_relatifs_des_documents_existent():
    for chemin in [RACINE / "README.md", *sorted(DOCS.glob("*.md"))]:
        texte = chemin.read_text(encoding="utf-8")
        for cible in re.findall(r"\]\(([^)\s]+)\)", texte) + re.findall(r'src="([^"]+)"', texte):
            if cible.startswith(("http", "#", "mailto:")):
                continue
            assert (chemin.parent / cible.split("#")[0]).exists(), f"{chemin.name} : lien cassé {cible}"
