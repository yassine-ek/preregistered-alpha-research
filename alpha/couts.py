"""Coûts réels par jambe (bps) lus dans data/frais_editable.csv (copie du fichier de coûts réels du stage).

Règle du prereg (section 2) : coût = `frais_editable_override` s'il est renseigné, sinon
`frais_bps_par_jambe` ; les indices sont figés à 12 bps. Tout autre coût rend le
résultat invalide, donc on lit toujours ce fichier et jamais de forfait.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

# alpha/ -> racine du dépôt -> data/frais_editable.csv (chemin relatif, versionné)
FICHIER_FRAIS = Path(__file__).resolve().parents[1] / "data" / "frais_editable.csv"
COUT_INDICE_BPS = 12.0


def charger_couts(fichier: Path = FICHIER_FRAIS) -> pd.Series:
    """Série actif -> coût par jambe en bps."""
    # le fichier contient des accents (Matière première) : on tolère l'encodage
    df = pd.read_csv(fichier, encoding="utf-8", encoding_errors="replace")
    cout = df["frais_editable_override"].where(df["frais_editable_override"].notna(), df["frais_bps_par_jambe"])
    est_indice = df["classe"].astype(str).str.startswith("Indice")
    cout = cout.where(~est_indice, COUT_INDICE_BPS)
    out = pd.Series(cout.values.astype(float), index=df["actif"].values, name="cout_bps")
    return out[~out.index.duplicated(keep="first")]
