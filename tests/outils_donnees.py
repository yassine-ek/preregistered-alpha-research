"""Détection des données locales : les tests qui les lisent sont sautés proprement si elles manquent.

Les données (barres 1 h dérivées, minutes HistData) ne sont pas versionnées. Pour lancer la suite complète :
    export HISTDATA_DIR=/chemin/vers/les/donnees     # contient processed/univers/ et histdata_raw/
Sans cela (cas de l'intégration continue), seuls les tests synthétiques tournent.
"""
import os
import subprocess
from pathlib import Path

import pytest

from alpha import donnees as d

DONNEES_1H = (d.DOSSIER_1H / "EURUSD_1h.csv").exists()
MINUTES_2022 = (d.DOSSIER_CACHE / "minutes" / "EURUSD_2022.parquet").exists() or (d.DOSSIER_1MIN / "EURUSD").exists()

MOTIF = "données locales absentes : définir HISTDATA_DIR (voir README, section Reproduire)"
besoin_donnees = pytest.mark.skipif(not DONNEES_1H, reason=MOTIF)
besoin_minutes = pytest.mark.skipif(not MINUTES_2022, reason=MOTIF)


# ------------------------------------------------------------------ fichiers du dépôt (tests d'hygiène)
DOSSIERS_IGNORES = {".venv", "venv", "env", ".git", "build", "cache", "__pycache__", ".pytest_cache", ".ipynb_checkpoints",
                    "site-packages", "node_modules", "histdata", ".mypy_cache", ".ruff_cache"}


def fichiers_du_depot(racine: Path) -> list[Path]:
    """Fichiers versionnés ou nouveaux non ignorés (`git ls-files`) ; à défaut (pas de dépôt git), parcours qui ne descend jamais dans .venv, caches, build…

    Un test d'hygiène ne doit pas lire les dépendances d'un environnement virtuel créé dans le dépôt."""
    racine = Path(racine)
    try:
        sortie = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=racine, capture_output=True, text=True, check=True).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        sortie = []
    suivis = [racine / ligne for ligne in sortie if (racine / ligne).is_file()]
    if suivis:
        return suivis
    trouves = []
    for dossier, sous_dossiers, noms in os.walk(racine):
        sous_dossiers[:] = [s for s in sous_dossiers if s not in DOSSIERS_IGNORES]
        trouves += [Path(dossier) / n for n in noms]
    return trouves
