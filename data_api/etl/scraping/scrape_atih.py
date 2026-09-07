"""Collecte par scraping des actualites de l'ATIH (C1) — source de veille reglementaire.

Pourquoi cette source. L'ATIH (Agence technique de l'information sur l'hospitalisation)
pilote le PMSI et publie les evolutions de nomenclature qui conditionnent ce projet :
c'est elle qui annonce le calendrier de bascule CIM-10 vers CIM-11. Contrairement aux
autres sources du projet (API de l'OMS, API Mistral, fichiers du referentiel), l'ATIH
ne publie ni API ni flux structure pour ces annonces : la seule voie d'acces
programmatique est la lecture de la page HTML publique. D'ou ce script de scraping,
qui complete le mix de sources exige pour C1 (service web, fichier, base de donnees,
systeme big data, scraping).

Ce qui est collecte. Uniquement des metadonnees publiques d'actualites : date de
publication, titre, chapo et lien. Aucune donnee personnelle, aucun contenu soumis a
authentification.

Politesse et robustesse. Le script s'identifie explicitement par un User-Agent
descriptif, respecte un delai entre requetes, borne le nombre d'elements collectes, et
gere les erreurs reseau sans interrompre brutalement la chaine appelante. La structure
HTML d'un site public peut changer sans preavis : le script echoue explicitement s'il
ne reconnait plus la structure attendue, plutot que de produire silencieusement un
fichier vide.

Usage :
    python -m etl.scraping.scrape_atih --out actualites_atih.csv
    python -m etl.scraping.scrape_atih --fixture etl/scraping/fixtures/atih_actualites_2026-09-07.html

Le mode --fixture rejoue une capture locale : c'est ce mode qu'utilisent les tests
automatises, afin que la chaine d'integration continue ne depende ni du reseau ni du
contenu changeant du site.
"""
import argparse
import csv
import re
import sys
import time
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

URL_ATIH = "https://www.atih.sante.fr/actualites"
BASE = "https://www.atih.sante.fr"
USER_AGENT = "cim11-assistant/1.0 (projet de certification RNCP 37827 ; veille reglementaire)"
DELAI_S = 1.0
TIMEOUT_S = 20
MAX_ELEMENTS = 50

# Le bloc d'actualites est une liste <li class="item-news"> contenant un lien, une date
# (attribut content au format ISO), un titre <h4> et un chapo <p>.
RE_ITEM = re.compile(r'<li class="item-news">(.*?)</li>', re.S)
RE_HREF = re.compile(r'<a class="link-news" href="([^"]+)"')
RE_ISO = re.compile(r'class="date-display-single"[^>]*content="([^"]+)"')
RE_DATE = re.compile(r'<span class="date-display-single"[^>]*>([^<]+)</span>')
RE_TITRE = re.compile(r'<h4 class="title-news">(.*?)</h4>', re.S)
RE_CHAPO = re.compile(r'<h4 class="title-news">.*?</h4>\s*<p>(.*?)</p>', re.S)


def _texte(brut: str) -> str:
    """Nettoie un fragment HTML : balises retirees, entites decodees, espaces normalises."""
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", brut))).strip()


def telecharger(url: str = URL_ATIH) -> str:
    """Recupere le HTML de la page publique, en s'identifiant et en respectant un delai."""
    time.sleep(DELAI_S)
    requete = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    try:
        with urlopen(requete, timeout=TIMEOUT_S) as reponse:
            return reponse.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        raise RuntimeError(f"le site a repondu HTTP {exc.code} pour {url}") from exc
    except URLError as exc:
        raise RuntimeError(f"acces reseau impossible a {url} : {exc.reason}") from exc


def extraire(html: str) -> list[dict]:
    """Extrait les actualites du HTML. Leve une erreur si la structure n'est plus reconnue."""
    blocs = RE_ITEM.findall(html)
    if not blocs:
        raise RuntimeError(
            "structure de page non reconnue : aucun element <li class=\"item-news\"> trouve. "
            "Le site a probablement change ; adapter les expressions regulieres du module."
        )

    actualites = []
    for bloc in blocs[:MAX_ELEMENTS]:
        href = RE_HREF.search(bloc)
        titre = RE_TITRE.search(bloc)
        if not href or not titre:
            continue  # element incomplet : ignore plutot que de produire une ligne vide
        iso = RE_ISO.search(bloc)
        date = RE_DATE.search(bloc)
        chapo = RE_CHAPO.search(bloc)
        lien = href.group(1)
        actualites.append({
            "date_iso": (iso.group(1)[:10] if iso else ""),
            "date_affichee": _texte(date.group(1)) if date else "",
            "titre": _texte(titre.group(1)),
            "chapo": _texte(chapo.group(1)) if chapo else "",
            "url": lien if lien.startswith("http") else BASE + lien,
        })
    return actualites


def ecrire_csv(actualites: list[dict], chemin: Path) -> None:
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        redacteur = csv.DictWriter(f, fieldnames=["date_iso", "date_affichee", "titre", "chapo", "url"])
        redacteur.writeheader()
        redacteur.writerows(actualites)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("actualites_atih.csv"))
    parser.add_argument("--fixture", type=Path, help="rejoue une capture HTML locale au lieu du site")
    args = parser.parse_args()

    try:
        html = args.fixture.read_text(encoding="utf-8") if args.fixture else telecharger()
        actualites = extraire(html)
    except (RuntimeError, OSError) as exc:
        print(f"COLLECTE ATIH : ECHEC — {exc}")
        return 1

    if not actualites:
        print("COLLECTE ATIH : ECHEC — aucune actualite exploitable extraite.")
        return 1

    ecrire_csv(actualites, args.out)
    source = args.fixture if args.fixture else URL_ATIH
    print(f"COLLECTE ATIH : OK — {len(actualites)} actualites extraites de {source}")
    print(f"  plus recente : {actualites[0]['date_affichee']} — {actualites[0]['titre']}")
    print(f"  ecrit dans {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
