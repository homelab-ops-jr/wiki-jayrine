#!/usr/bin/env python3
"""
build-cards.py — Étape 2 (parsing complet)

Scanne docs/<sujet>/notions/*.md et extrait pour chaque page :
- métadonnées (titre, sujet)
- liste des cartes : question + réponse en Markdown brut

À ce stade, affiche un récap + 2 cartes échantillon par page
pour validation visuelle. Pas encore de génération .apkg.

Usage:
    cd <racine-du-repo-wiki>
    python3 scripts/build-cards.py
    python3 scripts/build-cards.py --sample 3   # nb cartes échantillon
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ----- Constantes -----

DOCS_DIR = "docs"
NOTIONS_GLOB = "*/notions/*.md"
CARDS_SECTION_HEADING = "## Cartes d'entraînement"

# Regex métadonnées
RE_H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
RE_SUBJECT = re.compile(
    r"^>\s*\*\*Type\*\*\s*:\s*\S+\s*·\s*\*\*Sujet\*\*\s*:\s*(.+?)\s*(?:·|$)",
    re.MULTILINE,
)

# Regex pour le parsing des cartes
# Capture: "???" ou "???+", suivi de "question", puis la question entre guillemets
RE_CARD_OPEN = re.compile(r'^\?\?\?\+?\s+question\s+"(.+?)"\s*$')

# Une ligne du bloc cartes qui n'est PAS une carte (sous-titre, paragraphe, ...)
RE_NON_CARD_LINE = re.compile(r"^\S")


# ----- Modèle de données -----

@dataclass
class Card:
    question: str
    answer_md: str  # Markdown brut, dé-indenté
    source_path: Path  # chemin relatif depuis racine du repo
    source_title: str
    source_subject: str


@dataclass
class PageReport:
    path: Path  # chemin relatif depuis racine du repo
    title: str
    subject: str
    cards: list[Card] = field(default_factory=list)


# ----- Helpers -----

def find_repo_root() -> Path:
    here = Path.cwd().resolve()
    for candidate in [here] + list(here.parents):
        if (candidate / DOCS_DIR).is_dir() and (candidate / "mkdocs.yml").is_file():
            return candidate
    sys.exit(
        f"[error] Racine du repo introuvable depuis {here}.\n"
        f"        Le repo doit contenir {DOCS_DIR}/ et mkdocs.yml."
    )


def extract_metadata(content: str) -> tuple[str | None, str | None]:
    h1_match = RE_H1.search(content)
    subject_match = RE_SUBJECT.search(content)
    title = h1_match.group(1).strip() if h1_match else None
    subject = subject_match.group(1).strip() if subject_match else None
    return title, subject


def get_cards_section(content: str) -> str | None:
    """Extrait tout le texte à partir de '## Cartes d'entraînement' jusqu'à la fin."""
    idx = content.find(CARDS_SECTION_HEADING)
    if idx == -1:
        return None
    return content[idx:]


def dedent_4(line: str) -> str:
    """Retire 4 espaces de tête, ou tabulation, sans toucher aux lignes vides."""
    if line.startswith("    "):
        return line[4:]
    if line.startswith("\t"):
        return line[1:]
    return line  # ne devrait pas arriver si appelé correctement


def parse_cards_from_section(
    section: str, page: PageReport
) -> list[Card]:
    """
    Parse la section ## Cartes d'entraînement et retourne la liste des cartes.

    Algo : automate à deux états (OUT, INSIDE).
    - OUT : on cherche une ligne ouvrant une carte (??? question "...").
    - INSIDE : on accumule les lignes indentées (au moins 4 espaces ou 1 tab).
              Une ligne non-indentée non-vide ferme la carte.
              Les lignes vides sont conservées (avec contenu vide).
    """
    cards: list[Card] = []
    lines = section.splitlines()

    state = "OUT"
    current_question: str | None = None
    current_answer_lines: list[str] = []

    def flush_card() -> None:
        nonlocal current_question, current_answer_lines
        if current_question is None:
            return
        # Trim les lignes vides en début et fin de réponse
        answer = "\n".join(current_answer_lines).strip("\n")
        # Trim trailing whitespace par ligne mais préserver indentation interne
        cards.append(
            Card(
                question=current_question,
                answer_md=answer,
                source_path=page.path,
                source_title=page.title,
                source_subject=page.subject,
            )
        )
        current_question = None
        current_answer_lines = []

    for line in lines:
        if state == "OUT":
            m = RE_CARD_OPEN.match(line)
            if m:
                current_question = m.group(1)
                current_answer_lines = []
                state = "INSIDE"
            # sinon, on ignore (sous-titres H3, prose, lignes vides)
        else:  # INSIDE
            if line.startswith("    "):
                current_answer_lines.append(dedent_4(line))
            elif line.startswith("\t"):
                current_answer_lines.append(dedent_4(line))
            elif line.strip() == "":
                # Ligne vide : on la garde dans la réponse, peut être un séparateur de paragraphes
                current_answer_lines.append("")
            else:
                # Ligne non-vide non-indentée : fin du bloc de réponse
                flush_card()
                state = "OUT"
                # Cette ligne pourrait être l'ouverture d'une nouvelle carte
                m = RE_CARD_OPEN.match(line)
                if m:
                    current_question = m.group(1)
                    current_answer_lines = []
                    state = "INSIDE"

    # Flush final si on termine en plein milieu d'une carte
    flush_card()
    return cards


def scan_pages(root: Path) -> tuple[list[PageReport], list[Path], list[tuple[Path, str]]]:
    """Retourne (pages_avec_cartes, pages_sans_section, pages_meta_manquante)."""
    docs_root = root / DOCS_DIR
    pages_with_cards: list[PageReport] = []
    pages_without_section: list[Path] = []
    pages_missing_meta: list[tuple[Path, str]] = []

    for md in sorted(docs_root.glob(NOTIONS_GLOB)):
        rel = md.relative_to(root)
        content = md.read_text(encoding="utf-8")

        section = get_cards_section(content)
        if section is None:
            pages_without_section.append(rel)
            continue

        title, subject = extract_metadata(content)
        if not title:
            pages_missing_meta.append((rel, "H1 manquant"))
            continue
        if not subject:
            pages_missing_meta.append((rel, "blockquote Sujet manquante"))
            continue

        page = PageReport(path=rel, title=title, subject=subject)
        page.cards = parse_cards_from_section(section, page)
        pages_with_cards.append(page)

    return pages_with_cards, pages_without_section, pages_missing_meta


# ----- Affichage -----

def print_summary(
    pages_with_cards: list[PageReport],
    pages_without_section: list[Path],
    pages_missing_meta: list[tuple[Path, str]],
) -> None:
    total_pages = len(pages_with_cards) + len(pages_without_section) + len(pages_missing_meta)
    print(f"Pages totales scannées : {total_pages}")
    print(f"  avec cartes          : {len(pages_with_cards)}")
    print(f"  sans cartes          : {len(pages_without_section)}")
    print(f"  meta manquantes      : {len(pages_missing_meta)}")
    print()

    if pages_with_cards:
        print("=== Pages avec cartes ===")
        print(f"{'Sujet':<18} {'Titre':<45} {'Cartes':>7}  Chemin")
        print("-" * 100)
        total_cards = 0
        for page in pages_with_cards:
            total_cards += len(page.cards)
            title = page.title if len(page.title) <= 43 else page.title[:42] + "…"
            print(
                f"{page.subject:<18} "
                f"{title:<45} "
                f"{len(page.cards):>7}  "
                f"{page.path}"
            )
        print("-" * 100)
        print(f"{'TOTAL':<18} {'':<45} {total_cards:>7}")
        print()

    if pages_missing_meta:
        print("=== Pages avec cartes mais métadonnées manquantes ===")
        for rel, reason in pages_missing_meta:
            print(f"  - {rel} : {reason}")
        print()


def print_samples(pages_with_cards: list[PageReport], n_samples: int) -> None:
    if not pages_with_cards or n_samples <= 0:
        return
    print(f"=== Échantillon : {n_samples} cartes par page ===")
    for page in pages_with_cards:
        print(f"\n--- {page.path} ---")
        sample = page.cards[:n_samples]
        for i, card in enumerate(sample, 1):
            print(f"\n  [{i}] Q : {card.question}")
            print(f"      R :")
            for line in card.answer_md.splitlines():
                print(f"        | {line}")


# ----- Main -----

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sample",
        type=int,
        default=2,
        help="Nombre de cartes échantillon à afficher par page (défaut: 2, 0 pour aucune)",
    )
    args = parser.parse_args()

    root = find_repo_root()
    docs_root = root / DOCS_DIR

    print(f"[info] Racine du repo : {root}")
    print(f"[info] Scan dans : {docs_root}/{NOTIONS_GLOB}")
    print()

    pages_with_cards, pages_without_section, pages_missing_meta = scan_pages(root)

    print_summary(pages_with_cards, pages_without_section, pages_missing_meta)
    print_samples(pages_with_cards, args.sample)

    if pages_missing_meta:
        return 2
    if not pages_with_cards:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
