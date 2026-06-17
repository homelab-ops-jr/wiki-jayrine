#!/usr/bin/env python3
"""
build-cards.py — Étape 3 (génération .apkg)

Scanne docs/<sujet>/notions/*.md, extrait les cartes, et génère
un fichier wiki.apkg importable dans Anki.

Architecture du deck :
- Un seul fichier .apkg en sortie.
- À l'import, crée plusieurs decks hiérarchiques : Wiki::Réseau, Wiki::Reverse proxy, etc.
- Chaque carte est taggée hiérarchiquement (reseau::notions::modele-osi-tcpip).
- GUID stable basé sur (chemin de la page + texte exact de la question).

Usage:
    cd <racine-du-repo-wiki>
    python3 scripts/build-cards.py
    python3 scripts/build-cards.py --output ./wiki.apkg
    python3 scripts/build-cards.py --sample 0   # désactive l'affichage d'échantillon
    python3 scripts/build-cards.py --no-build   # parse uniquement, ne génère pas le .apkg
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

try:
    import genanki
    import markdown as md_lib
except ImportError as e:
    sys.exit(
        f"[error] Dépendance manquante : {e.name}\n"
        f"        Installe les dépendances : pip install -r scripts/requirements.txt"
    )

# ----- Constantes -----

DOCS_DIR = "docs"
NOTIONS_GLOB = "*/notions/*.md"
CARDS_SECTION_HEADING = "## Cartes d'entraînement"
DEFAULT_OUTPUT = "wiki.apkg"
DECK_ROOT = "Wiki"

# Regex métadonnées
RE_H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
RE_SUBJECT = re.compile(
    r"^>\s*\*\*Type\*\*\s*:\s*\S+\s*·\s*\*\*Sujet\*\*\s*:\s*(.+?)\s*(?:·|$)",
    re.MULTILINE,
)
RE_CARD_OPEN = re.compile(r'^\?\?\?\+?\s+question\s+"(.+?)"\s*$')

# Model et deck IDs racine. Ne JAMAIS changer ces valeurs après le premier déploiement —
# elles définissent l'identité du modèle de carte et l'ancrage des decks dans Anki.
MODEL_ID_BASE = 1717171717
DECK_ID_NAMESPACE = "wiki-jayrine.anki.decks"
NOTE_GUID_NAMESPACE = "wiki-jayrine.anki.notes"


# ----- Modèle de données -----

@dataclass
class Card:
    question: str
    answer_md: str
    source_path: Path  # relatif depuis racine du repo
    source_title: str
    source_subject: str


@dataclass
class PageReport:
    path: Path
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


def slugify(s: str) -> str:
    """Minuscules, sans accents, espaces et caractères spéciaux → tirets."""
    # NFD pour décomposer les caractères accentués (é = e + ́)
    nfd = unicodedata.normalize("NFD", s)
    no_accents = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    lower = no_accents.lower()
    # Remplace tout ce qui n'est pas alphanumérique par un tiret
    slug = re.sub(r"[^a-z0-9]+", "-", lower)
    return slug.strip("-")


def path_to_tag(rel_path: Path) -> str:
    """
    docs/reseau/notions/01-modele-osi-tcpip.md → reseau::notions::01-modele-osi-tcpip
    """
    parts = rel_path.with_suffix("").parts
    # Retirer le préfixe "docs"
    if parts and parts[0] == DOCS_DIR:
        parts = parts[1:]
    # Slugify chaque segment et joindre avec ::
    return "::".join(slugify(p) for p in parts)


def subject_to_deck_name(subject: str) -> str:
    """Réseau → Wiki::Réseau (on garde les accents pour l'affichage)."""
    return f"{DECK_ROOT}::{subject}"


def stable_int_id(namespace: str, value: str, bits: int = 31) -> int:
    """
    Génère un entier déterministe non-négatif de N bits maximum, à partir
    d'un namespace + valeur. Utile pour genanki qui veut des IDs entiers stables.
    """
    h = hashlib.sha256(f"{namespace}|{value}".encode("utf-8")).digest()
    n = int.from_bytes(h[:8], "big")
    return n & ((1 << bits) - 1)


def deck_id_for(deck_name: str) -> int:
    return stable_int_id(DECK_ID_NAMESPACE, deck_name)


def note_guid_for(card: Card) -> str:
    """
    GUID stable d'une carte : hash de (chemin de la page + texte exact de la question).
    
    Conséquences :
    - Reformuler la réponse → même GUID → mise à jour de la carte existante dans Anki.
    - Reformuler la question → nouveau GUID → nouvelle carte (l'ancienne devient orpheline).
    - Déplacer la page de dossier → nouveau GUID → toutes les cartes deviennent orphelines.
    """
    raw = f"{NOTE_GUID_NAMESPACE}|{card.source_path.as_posix()}|{card.question}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return h[:16]  # 16 hex chars = 64 bits, largement suffisant


# ----- Extraction des cartes (étape 2, repris tel quel) -----

def extract_metadata(content: str) -> tuple[str | None, str | None]:
    h1_match = RE_H1.search(content)
    subject_match = RE_SUBJECT.search(content)
    title = h1_match.group(1).strip() if h1_match else None
    subject = subject_match.group(1).strip() if subject_match else None
    return title, subject


def get_cards_section(content: str) -> str | None:
    idx = content.find(CARDS_SECTION_HEADING)
    if idx == -1:
        return None
    return content[idx:]


def dedent_4(line: str) -> str:
    if line.startswith("    "):
        return line[4:]
    if line.startswith("\t"):
        return line[1:]
    return line


def parse_cards_from_section(section: str, page: PageReport) -> list[Card]:
    cards: list[Card] = []
    lines = section.splitlines()

    state = "OUT"
    current_question: str | None = None
    current_answer_lines: list[str] = []

    def flush_card() -> None:
        nonlocal current_question, current_answer_lines
        if current_question is None:
            return
        answer = "\n".join(current_answer_lines).strip("\n")
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
        else:
            if line.startswith("    ") or line.startswith("\t"):
                current_answer_lines.append(dedent_4(line))
            elif line.strip() == "":
                current_answer_lines.append("")
            else:
                flush_card()
                state = "OUT"
                m = RE_CARD_OPEN.match(line)
                if m:
                    current_question = m.group(1)
                    current_answer_lines = []
                    state = "INSIDE"

    flush_card()
    return cards


def scan_pages(root: Path) -> tuple[list[PageReport], list[Path], list[tuple[Path, str]]]:
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


# ----- Conversion Markdown → HTML -----

def md_to_html(text: str) -> str:
    """
    Convertit le Markdown d'une réponse en HTML pour Anki.
    
    Extensions :
    - fenced_code : blocs ```bash ... ```
    - tables : pour d'éventuels tableaux
    - sane_lists : numérotation propre des listes
    - smarty : guillemets typographiques
    """
    return md_lib.markdown(
        text,
        extensions=["fenced_code", "tables", "sane_lists", "smarty"],
        output_format="html5",
    )


# ----- Modèle Anki -----

CARD_CSS = """
.card {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-size: 17px;
  line-height: 1.5;
  color: #1a1a1a;
  background-color: #ffffff;
  padding: 16px;
  text-align: left;
}

.nightMode.card, .night_mode.card {
  color: #e8e8e8;
  background-color: #1e1e1e;
}

.question {
  font-weight: 500;
}

.answer p { margin: 0.6em 0; }
.answer ul, .answer ol { margin: 0.6em 0; padding-left: 1.5em; }
.answer li { margin: 0.2em 0; }

.answer code {
  background-color: #f4f4f4;
  border-radius: 3px;
  padding: 0.1em 0.35em;
  font-family: "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
  font-size: 0.92em;
}
.nightMode.card .answer code, .night_mode.card .answer code {
  background-color: #2d2d2d;
}

.answer pre {
  background-color: #f4f4f4;
  border-radius: 4px;
  padding: 10px 12px;
  overflow-x: auto;
  font-family: "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
  font-size: 0.92em;
  line-height: 1.4;
  margin: 0.8em 0;
}
.nightMode.card .answer pre, .night_mode.card .answer pre {
  background-color: #2d2d2d;
}
.answer pre code {
  background: transparent;
  padding: 0;
}

.answer strong { color: #000; }
.nightMode.card .answer strong, .night_mode.card .answer strong { color: #fff; }

hr.qa-sep {
  border: none;
  border-top: 1px solid #d0d0d0;
  margin: 14px 0 14px 0;
}
.nightMode.card hr.qa-sep, .night_mode.card hr.qa-sep {
  border-top-color: #444;
}

.footer {
  text-align: center;
  color: #888;
  font-size: 0.82em;
  margin-top: 32px;
  font-style: italic;
}
.nightMode.card .footer, .night_mode.card .footer {
  color: #888;
}
"""

CARD_FRONT_TEMPLATE = """
<div class="question">{{Question}}</div>
"""

CARD_BACK_TEMPLATE = """
<div class="question">{{Question}}</div>
<hr class="qa-sep">
<div class="answer">{{Answer}}</div>
<div class="footer">{{Source}}</div>
"""


def make_model() -> genanki.Model:
    return genanki.Model(
        model_id=MODEL_ID_BASE,
        name="Wiki Card (Q/A)",
        fields=[
            {"name": "Question"},
            {"name": "Answer"},
            {"name": "Source"},
        ],
        templates=[
            {
                "name": "Card 1",
                "qfmt": CARD_FRONT_TEMPLATE.strip(),
                "afmt": CARD_BACK_TEMPLATE.strip(),
            }
        ],
        css=CARD_CSS,
    )


def card_to_note(card: Card, model: genanki.Model) -> genanki.Note:
    answer_html = md_to_html(card.answer_md)
    source_label = f"{card.source_subject} · {card.source_title}"
    tag = path_to_tag(card.source_path)

    # genanki refuse les tags avec espaces — on slugify déjà donc OK
    note = genanki.Note(
        model=model,
        fields=[card.question, answer_html, source_label],
        tags=[tag],
        guid=note_guid_for(card),
    )
    return note


# ----- Build du .apkg -----

def build_package(pages: list[PageReport], output: Path) -> tuple[int, int]:
    """
    Construit le .apkg à partir des pages.
    
    Retourne (n_decks, n_notes).
    """
    model = make_model()

    # Regrouper les cartes par sujet (chaque sujet = un deck)
    decks_by_subject: dict[str, genanki.Deck] = {}

    for page in pages:
        for card in page.cards:
            deck_name = subject_to_deck_name(card.source_subject)
            if deck_name not in decks_by_subject:
                decks_by_subject[deck_name] = genanki.Deck(
                    deck_id=deck_id_for(deck_name),
                    name=deck_name,
                )
            note = card_to_note(card, model)
            decks_by_subject[deck_name].add_note(note)

    decks = list(decks_by_subject.values())
    package = genanki.Package(decks)
    package.write_to_file(str(output))

    n_notes = sum(len(d.notes) for d in decks)
    return len(decks), n_notes


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
            tag = path_to_tag(card.source_path)
            print(f"\n  [{i}] Q : {card.question}")
            print(f"      Tag : {tag}")
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
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(DEFAULT_OUTPUT),
        help=f"Chemin du fichier .apkg de sortie (défaut: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Parse uniquement, ne génère pas le .apkg (utile pour debug)",
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
        print("[warn] Aucune carte trouvée, rien à générer.")
        return 1

    if args.no_build:
        print("[info] --no-build : pas de génération .apkg.")
        return 0

    # Résoudre le chemin de sortie par rapport à la racine du repo si relatif
    output_path = args.output
    if not output_path.is_absolute():
        output_path = root / output_path

    print(f"[info] Génération du package : {output_path}")
    n_decks, n_notes = build_package(pages_with_cards, output_path)
    size_kb = output_path.stat().st_size / 1024
    print(f"[ok] Package généré : {n_decks} deck(s), {n_notes} note(s), {size_kb:.1f} KB")

    return 0


if __name__ == "__main__":
    sys.exit(main())
