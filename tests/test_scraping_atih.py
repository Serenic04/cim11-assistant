"""Tests du scraping des actualites ATIH (C1) — source de veille reglementaire.

Les tests rejouent une capture HTML reelle du site (datee, versionnee dans
fixtures/) plutot que d'interroger le site en direct : la chaine d'integration
continue reste ainsi independante du reseau et du contenu changeant du site, et
les tests sont deterministes.
"""
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "data_api"))

from etl.scraping.scrape_atih import extraire, ecrire_csv  # noqa: E402

FIXTURE = RACINE / "data_api" / "etl" / "scraping" / "fixtures" / "atih_actualites_2026-09-07.html"


@pytest.fixture()
def html_reel():
    assert FIXTURE.exists(), "la capture HTML de reference doit etre versionnee"
    return FIXTURE.read_text(encoding="utf-8")


def test_extrait_toutes_les_actualites(html_reel):
    actualites = extraire(html_reel)
    assert len(actualites) == 15


def test_champs_de_la_premiere_actualite(html_reel):
    a = extraire(html_reel)[0]
    assert a["date_iso"] == "2026-09-04"
    assert a["date_affichee"] == "04/09/2026"
    assert a["titre"] == "Evolutions e-PMSI - Module Ovalide"
    assert a["url"] == "https://www.atih.sante.fr/actualites/evolutions-e-pmsi-module-ovalide"


def test_les_liens_relatifs_sont_absolutises(html_reel):
    assert all(a["url"].startswith("https://www.atih.sante.fr/") for a in extraire(html_reel))


def test_le_html_est_nettoye_et_les_entites_decodees(html_reel):
    actualites = extraire(html_reel)
    for a in actualites:
        assert "<" not in a["titre"] and "&amp;" not in a["titre"]
    # Un titre du corpus reel contient une esperluette encodee dans la source.
    assert any("18&19" in a["titre"] for a in actualites)


def test_structure_non_reconnue_echoue_explicitement():
    """Si le site change de structure, le script doit echouer, pas produire un fichier vide."""
    with pytest.raises(RuntimeError, match="structure de page non reconnue"):
        extraire("<html><body><p>Le site a ete refondu.</p></body></html>")


def test_element_incomplet_est_ignore_sans_faire_echouer():
    html = (
        '<li class="item-news"><a class="link-news" href="/a"><h4 class="title-news">Valide</h4></a></li>'
        '<li class="item-news"><a class="link-news" href="/b"></a></li>'  # sans titre
    )
    actualites = extraire(html)
    assert [a["titre"] for a in actualites] == ["Valide"]


def test_ecriture_csv(tmp_path, html_reel):
    sortie = tmp_path / "actualites.csv"
    ecrire_csv(extraire(html_reel), sortie)
    lignes = sortie.read_text(encoding="utf-8").splitlines()
    assert lignes[0] == "date_iso,date_affichee,titre,chapo,url"
    assert len(lignes) == 16  # en-tete + 15 actualites
