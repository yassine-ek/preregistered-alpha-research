"""Hygiène d'un dépôt public : pas de chemin absolu de machine, pas de trace de fabrication interne, fins de ligne, liens de pages.

Les fichiers lus sont ceux du dépôt (`git ls-files`) ; à défaut, un parcours qui ignore .venv, les caches et build :
créer un environnement virtuel dans le dépôt ne fait pas échouer ces tests."""
import re
from pathlib import Path

from outils_donnees import fichiers_du_depot

RACINE = Path(__file__).resolve().parents[1]
EXTENSIONS = {".py", ".md", ".json", ".ipynb", ".yml", ".txt", ".csv", ".js", ".html"}
# fichiers figés et hachés : texte d'origine conservé exprès (chemins locaux historiques, vocabulaire d'époque)
FIGES = {"PREREGISTRATION.md", "PREREGISTRATION_v1.md"}
EXCLUS = FIGES | {"test_hygiene_depot.py", "test_dashboard_et_readme.py"}
# motifs construits par morceaux pour que ce fichier ne contienne pas lui-même les chaînes qu'il interdit
INTERDITS = [r"\bA" + r"WB\b", r"PIV" + r"OT", r"Route " + r"A\b", r"smart" + r"Trade", r"Xr" + r"ays", r"orchestr" + r"ateur", r"agent ind" + r"épendant",
             r"projets" + r"_cv", r"_re" + r"vue/", r"_rech" + r"erche/", r"note de recherche " + r"interne", r"stage " + r"awb", r"docs/id" + r"ees"]
CHEMIN_ABSOLU = re.compile(r"[A-Za-z]:[\\/]+Users")


def _textes():
    for p in fichiers_du_depot(RACINE):
        if p.suffix in EXTENSIONS and p.name not in EXCLUS:
            yield p, p.read_text(encoding="utf-8", errors="ignore")


def test_aucun_chemin_absolu_de_machine_dans_le_depot():
    """Pas de chemin absolu de machine (lecteur, puis dossier Users) dans le code, les notebooks, les README et les résultats."""
    fautifs = [str(p.relative_to(RACINE)) for p, t in _textes() if CHEMIN_ABSOLU.search(t)]
    assert not fautifs, fautifs


def test_aucune_trace_de_fabrication_interne():
    fautifs = [f"{p.relative_to(RACINE)} : {m}" for p, t in _textes() for m in INTERDITS if re.search(m, t)]
    assert not fautifs, fautifs


def test_gitattributes_fins_de_ligne_et_carnets():
    ga = (RACINE / ".gitattributes").read_text(encoding="utf-8")
    for ligne in ("*.ipynb linguist-documentation", "*.md text eol=lf", "*.json text eol=lf"):
        assert ligne in ga


def test_liens_de_tableau_de_bord_valides():
    """Une seule URL de page existe : celle du dépôt lui-même."""
    vus = {m for p, t in _textes() for m in re.findall(r"yassine-ek\.github\.io/([\w-]+)", t)}
    assert vus <= {"preregistered-alpha-research"}, vus


def test_le_parcours_ignore_un_environnement_virtuel(tmp_path):
    """Hors dépôt git, le repli ne descend ni dans .venv ni dans les caches (les tests ci-dessus ne lisent pas les dépendances)."""
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / ".venv" / "lib" / "dep.py").write_text("C:\\Users\\quelquun", encoding="utf-8")
    (tmp_path / "ok.py").write_text("x = 1", encoding="utf-8")
    assert [p.name for p in fichiers_du_depot(tmp_path)] == ["ok.py"]
