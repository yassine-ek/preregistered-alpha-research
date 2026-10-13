"""Message guidé quand les données de marché locales manquent (au lieu d'une trace brute).

Les scripts qui REJOUENT le calcul (run_train_val, auditer_reproduction_trades_frais, sensibilite_couts,
run_approfondissement, ouvrir_test) appellent `exiger_donnees()` en premier. Sans les données, ils s'arrêtent
avec le code 2 et expliquent quoi obtenir, où le ranger et comment le dire au code (variable HISTDATA_DIR).
Les scripts qui ne lisent que results/ (exporter_dashboard, generer_*, controle positif) n'en ont pas besoin.
"""
from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from alpha import donnees as d  # noqa: E402

MESSAGE = """Données de marché introuvables : {chemin} n'existe pas.

Ce script rejoue le calcul complet : il lit les barres 1 h et les minutes HistData, qui ne sont pas redistribuées.
 1. Télécharger les minutes (BID, ASCII, M1, une archive par actif et par année) sur https://www.histdata.com
 2. Ranger les fichiers sous le dossier de votre choix, avec l'arborescence attendue :
      <HISTDATA_DIR>/histdata_raw/<ACTIF>/<ACTIF>_<année>.zip       minutes (ex. EURUSD/EURUSD_2019.zip)
      <HISTDATA_DIR>/processed/univers/<ACTIF>_1h.csv               barres 1 h dérivées (colonnes datetime, close)
 3. Dire où elles sont :   export HISTDATA_DIR=/chemin/vers/donnees     (PowerShell : $env:HISTDATA_DIR = "D:/donnees")
    Sans la variable, le défaut est ./data/histdata (ignoré par git).

Sans données, rien n'est cassé : tout se relit dans results/ et se régénère (pytest, scripts/exporter_dashboard.py,
scripts/generer_figures_vitrine.py, scripts/generer_readme_tete.py, scripts/run_controle_positif.py)."""


def donnees_presentes() -> bool:
    return (d.DOSSIER_1H / "EURUSD_1h.csv").exists()


def exiger_donnees() -> None:
    """Quitte proprement (code 2) si les données locales manquent."""
    if not donnees_presentes():
        print(MESSAGE.format(chemin=d.DOSSIER_1H / "EURUSD_1h.csv"), file=sys.stderr)
        sys.exit(2)
