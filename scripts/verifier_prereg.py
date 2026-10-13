"""Vérifie le pré-enregistrement : empreinte de la version d'origine (v1) et lien v1 -> fichier courant.

Deux contrôles, sans aucune donnée de marché (bibliothèque standard seulement) :
  1. SHA-256 de `PREREGISTRATION_v1.md` (octets d'origine, fins de ligne normalisées en LF) = EMPREINTE_V1 ;
  2. `PREREGISTRATION.md` = `PREREGISTRATION_v1.md` dont la ligne `(aucun)` (section AVENANTS) est remplacée par
     les avenants, sans autre modification. Le test : tout ce qui précède la ligne `(aucun)` est identique
     octet pour octet, et il reste un bloc d'avenants non vide à la place.

Usage : python scripts/verifier_prereg.py        (code de sortie 0 si tout est conforme, 1 sinon)
Équivalent en ligne de commande : `sha256sum PREREGISTRATION_v1.md` (le fichier est versionné en LF).

Les fins de ligne sont normalisées (CRLF -> LF) avant tout hachage : un clone Windows avec `autocrlf` donne la même empreinte.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
V1 = RACINE / "PREREGISTRATION_v1.md"
COURANT = RACINE / "PREREGISTRATION.md"
EMPREINTE_V1 = "f6007427c1a455525c3e863e680e02aac4775e432783abc1ea6247b656182250"
MARQUEUR_AUCUN = b"(aucun)\n"  # dernière ligne de la v1 : « aucun avenant »


def lire_normalise(chemin: Path) -> bytes:
    """Octets du fichier, fins de ligne CRLF ramenées à LF (même empreinte sous Windows et Linux)."""
    return Path(chemin).read_bytes().replace(b"\r\n", b"\n")


def sha256_normalise(chemin: Path) -> str:
    return hashlib.sha256(lire_normalise(chemin)).hexdigest()


def sha256_v1(racine: Path = RACINE) -> str:
    """Empreinte de PREREGISTRATION_v1.md : c'est elle (et non celle du fichier courant) que tous les contrôles comparent."""
    return sha256_normalise(racine / "PREREGISTRATION_v1.md")


def verifier(racine: Path = RACINE) -> list[str]:
    """Liste des écarts (vide = conforme)."""
    v1_chemin, courant_chemin = racine / "PREREGISTRATION_v1.md", racine / "PREREGISTRATION.md"
    ecarts = []
    if not v1_chemin.exists() or not courant_chemin.exists():
        return ["PREREGISTRATION_v1.md ou PREREGISTRATION.md introuvable"]
    v1, courant = lire_normalise(v1_chemin), lire_normalise(courant_chemin)
    empreinte = hashlib.sha256(v1).hexdigest()
    if empreinte != EMPREINTE_V1:
        ecarts.append(f"empreinte de PREREGISTRATION_v1.md = {empreinte}, attendue {EMPREINTE_V1}")
    if v1.count(MARQUEUR_AUCUN) != 1 or not v1.endswith(MARQUEUR_AUCUN):
        ecarts.append("PREREGISTRATION_v1.md ne se termine pas par la ligne « (aucun) » attendue")
        return ecarts
    avant = v1[: -len(MARQUEUR_AUCUN)]
    if not courant.startswith(avant):
        ecarts.append("PREREGISTRATION.md ne reprend pas la v1 à l'octet près avant la section des avenants")
    elif not courant[len(avant):].strip():
        ecarts.append("PREREGISTRATION.md : aucun avenant à la place de « (aucun) »")
    elif not courant[len(avant):].lstrip().startswith(b"### AVENANT"):
        ecarts.append("PREREGISTRATION.md : le bloc ajouté ne commence pas par « ### AVENANT »")
    return ecarts


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # console Windows en cp1252 : guillemets « » illisibles sinon
    ecarts = verifier()
    if ecarts:
        print("ÉCART de pré-enregistrement :")
        for e in ecarts:
            print(" -", e)
        return 1
    print(f"OK : SHA-256 de PREREGISTRATION_v1.md = {EMPREINTE_V1}")
    print("OK : PREREGISTRATION.md = v1 dont « (aucun) » est remplacé par les avenants (reste identique à l'octet près)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
