"""Pré-enregistrement vérifiable : v1 à l'octet près, fichier courant = v1 + avenants, garde-fou de ouvrir_test.py.

Aucune donnée de marché : tout se lit dans les fichiers versionnés du dépôt."""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
EMPREINTE_V1 = "f6007427c1a455525c3e863e680e02aac4775e432783abc1ea6247b656182250"


def _charger(nom: str):
    spec = importlib.util.spec_from_file_location(nom, RACINE / "scripts" / f"{nom}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vp = _charger("verifier_prereg")


def _copie(tmp_path: Path, v1: bytes | None = None, courant: bytes | None = None) -> Path:
    (tmp_path / "PREREGISTRATION_v1.md").write_bytes(v1 if v1 is not None else (RACINE / "PREREGISTRATION_v1.md").read_bytes())
    (tmp_path / "PREREGISTRATION.md").write_bytes(courant if courant is not None else (RACINE / "PREREGISTRATION.md").read_bytes())
    return tmp_path


def test_empreinte_de_la_v1_publiee():
    octets = (RACINE / "PREREGISTRATION_v1.md").read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(octets).hexdigest() == EMPREINTE_V1
    assert vp.sha256_v1() == EMPREINTE_V1


def test_fichier_courant_est_la_v1_plus_les_avenants():
    assert vp.verifier() == []
    v1 = (RACINE / "PREREGISTRATION_v1.md").read_bytes().replace(b"\r\n", b"\n")
    courant = (RACINE / "PREREGISTRATION.md").read_bytes().replace(b"\r\n", b"\n")
    avant = v1[: -len(b"(aucun)\n")]
    assert courant.startswith(avant)                       # rien d'autre n'a bougé avant la section des avenants
    assert b"### AVENANT 1" in courant[len(avant):] and b"### AVENANT 2" in courant[len(avant):]


def test_fins_de_ligne_normalisees(tmp_path):
    """Un clone Windows (CRLF) donne la même empreinte et le même verdict qu'un clone Linux (LF)."""
    v1 = (RACINE / "PREREGISTRATION_v1.md").read_bytes().replace(b"\r\n", b"\n")
    courant = (RACINE / "PREREGISTRATION.md").read_bytes().replace(b"\r\n", b"\n")
    racine = _copie(tmp_path, v1.replace(b"\n", b"\r\n"), courant.replace(b"\n", b"\r\n"))
    assert vp.sha256_v1(racine) == EMPREINTE_V1
    assert vp.verifier(racine) == []


def test_v1_modifiee_est_detectee(tmp_path):
    v1 = (RACINE / "PREREGISTRATION_v1.md").read_bytes()
    racine = _copie(tmp_path, v1.replace(b"Sharpe", b"sharpe", 1))
    assert any("empreinte" in e for e in vp.verifier(racine))


def test_reecriture_du_texte_d_origine_est_detectee(tmp_path):
    """Si PREREGISTRATION.md a modifié une ligne de la v1 (au lieu d'ajouter un avenant), le contrôle échoue."""
    courant = (RACINE / "PREREGISTRATION.md").read_bytes()
    racine = _copie(tmp_path, courant=courant.replace(b"G1 : Sharpe net VAL", b"G1 : Sharpe net VAL (assoupli)", 1))
    assert any("octet près" in e for e in vp.verifier(racine))


def test_absence_d_avenant_est_detectee(tmp_path):
    v1 = (RACINE / "PREREGISTRATION_v1.md").read_bytes()
    racine = _copie(tmp_path, courant=v1[: -len(b"(aucun)\n")])
    assert any("aucun avenant" in e for e in vp.verifier(racine))


def test_commande_de_verification_sans_donnees():
    sortie = subprocess.run([sys.executable, str(RACINE / "scripts" / "verifier_prereg.py")], capture_output=True, text=True,
                            encoding="utf-8")
    assert sortie.returncode == 0, sortie.stdout + sortie.stderr
    assert EMPREINTE_V1 in sortie.stdout


def test_garde_fou_d_ouverture_du_test_verifie_la_v1():
    """ouvrir_test.py compare l'empreinte de la v1 (pas du fichier courant, qui contient les avenants) à celle de train_val.json."""
    source = (RACINE / "scripts" / "ouvrir_test.py").read_text(encoding="utf-8")
    assert "verifier_prereg" in source and "sha256_v1" in source
    assert 'sha256_fichier(RACINE / "PREREGISTRATION.md")' not in source
    tv = json.loads((RACINE / "results" / "train_val.json").read_text(encoding="utf-8"))
    assert tv["meta"]["prereg_sha256"] == vp.sha256_v1() == EMPREINTE_V1
