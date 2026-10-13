"""Écrit results/verdict_alpha.json (SUCCES / ECHEC / TEST_NON_OUVERT, section 8 du prereg).

Lit results/train_val.json, et results/test_ouvert.json s'il existe. Ne calcule rien de
nouveau et ne touche jamais au TEST : il se contente d'assembler des chiffres déjà écrits.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from alpha import gates  # noqa: E402

RESULTATS = RACINE / "results"


def main() -> None:
    tv = gates.lire_json(RESULTATS / "train_val.json")
    if tv is None:
        sys.exit("results/train_val.json absent : lancer scripts/run_train_val.py d'abord")
    test = gates.lire_json(RESULTATS / "test_ouvert.json")
    if test is not None and "series" not in test:
        sys.exit("results/test_ouvert.json existe mais sans résultats : ouverture interrompue, voir le fichier")
    v = gates.construire_verdict(tv, test)
    (RESULTATS / "verdict_alpha.json").write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")
    p = v["sleeves_et_pile"]["PILE"]["VAL"]
    print(f"verdict : {v['verdict']} (TEST : {v['statut_test']}) ; gates en échec : {v['gates_en_echec']}")
    print(f"pile VAL : Sharpe net {p['sharpe_net']:.2f}, IC95 [{p['ic95_sharpe'][0]:.2f} ; {p['ic95_sharpe'][1]:.2f}], DSR {p['dsr']:.3f}")


if __name__ == "__main__":
    main()
