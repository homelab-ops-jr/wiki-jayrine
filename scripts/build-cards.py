#!/usr/bin/env python3
"""
build-cards.py — Étape 1 (smoke test)

Scanne docs/<sujet>/notions/*.md et liste pour chaque page :
- son chemin
- son titre (H1)
- son sujet (extrait de la blockquote méta)
- le nombre de blocs `??? question` détectés (comptage approximatif)

Pas de génération .apkg à ce stade. Le but est juste de valider
que le scan trouve bien les bonnes pages et compte les bonnes cartes.

Usage:
    cd <racine-du-repo-wiki>
    python3 scripts/build-cards.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# ----- Constantes -----

DOCS_DIR = "docs"
NOTIONS_GLOB = "*/notions/*.md"
CARDS_SECTION_HEADING = "## Cartes d'entraînement"

# Regex
RE_H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
RE_SUBJECT = re.compile(
    r"^>\s*\*\*Type\*\*\s*:\s*\S+\s*·\s*\*\*Sujet\*\*\s*:\s*(.+?)\s*(?:·|$)",
    re.MULTILINE,
)
# Compte rapide : lignes commençant par "???" + un espace + le mot "question"
RE_CARD_OPEN = re.compile(r"^\?\?\?\+?\s+question\s+\"", re.MULTILINE)

# ----- Helpers -----

def find_repo_root() -> Path:
    """Cherche la racine du repo en remontant depuis le cwd."""
    here = Path.cwd().resolve()
    for candidate in [here] + list(here.parents):
        if (candidate / DOCS_DIR).is_dir() and (candidate / "mkdocs.yml").is_file():
            return candidate
    sys.exit(
        f"[error] Racine du repo introuvable depuis {here}.\n"
        f"        Le repo doit contenir {DOCS_DIR}/ et mkdocs.yml."
    )


def extract_metadata(content: str, path: Path) -> tuple[str | None, str | None]:
    """Extrait (titre H1, sujet) depuis le contenu Markdown."""
    h1_match = RE_H1.search(content)
    subject_match = RE_SUBJECT.search(content)
    title = h1_match.group(1) if h1_match else None
    subject = subject_match.group(1).strip() if subject_match else None
    return title, subject


def has_cards_section(content: str) -> bool:
    """Détecte la présence d'une section ## Cartes d'entraînement."""
    return CARDS_SECTION_HEADING in content


def count_cards(content: str) -> int:
    """Compte les blocs ??? question dans le contenu."""
    return len(RE_CARD_OPEN.findall(content))


# ----- Main -----

def main() -> int:
    root = find_repo_root()
    docs_root = root / DOCS_DIR

    print(f"[info] Racine du repo : {root}")
    print(f"[info] Scan dans : {docs_root}/{NOTIONS_GLOB}")
    print()

    pages = sorted(docs_root.glob(NOTIONS_GLOB))
    if not pages:
        print(f"[warn] Aucune page trouvée sous {docs_root}/{NOTIONS_GLOB}")
        return 1

    with_cards: list[dict] = []
    without_cards: list[Path] = []
    missing_metadata: list[tuple[Path, str]] = []

    for page in pages:
        rel = page.relative_to(root)
        content = page.read_text(encoding="utf-8")

        if not has_cards_section(content):
            without_cards.append(rel)
            continue

        title, subject = extract_metadata(content, page)
        if not title:
            missing_metadata.append((rel, "H1 manquant"))
            continue
        if not subject:
            missing_metadata.append((rel, "blockquote Sujet manquante"))
            continue

        n_cards = count_cards(content)
        with_cards.append({
            "path": rel,
            "title": title,
            "subject": subject,
            "n_cards": n_cards,
        })

    # ----- Rapport -----

    print(f"Pages totales scannées : {len(pages)}")
    print(f"  avec cartes          : {len(with_cards)}")
    print(f"  sans cartes          : {len(without_cards)}")
    print(f"  meta manquantes      : {len(missing_metadata)}")
    print()

    if with_cards:
        print("=== Pages avec cartes ===")
        print(f"{'Sujet':<18} {'Titre':<45} {'Cartes':>7}  Chemin")
        print("-" * 100)
        total = 0
        for entry in with_cards:
            total += entry["n_cards"]
            title = entry["title"]
            if len(title) > 43:
                title = title[:42] + "…"
            print(
                f"{entry['subject']:<18} "
                f"{title:<45} "
                f"{entry['n_cards']:>7}  "
                f"{entry['path']}"
            )
        print("-" * 100)
        print(f"{'TOTAL':<18} {'':<45} {total:>7}")
        print()

    if missing_metadata:
        print("=== Pages avec cartes mais métadonnées manquantes ===")
        for rel, reason in missing_metadata:
            print(f"  - {rel} : {reason}")
        print()

    if without_cards and len(without_cards) <= 30:
        print(f"=== Pages sans section '{CARDS_SECTION_HEADING}' ({len(without_cards)}) ===")
        for rel in without_cards:
            print(f"  - {rel}")
        print()

    return 0 if not missing_metadata else 2


if __name__ == "__main__":
    sys.exit(main())
