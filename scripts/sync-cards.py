#!/usr/bin/env python3
"""
sync-cards.py — Pousse un .apkg vers un serveur Anki self-hosted

Workflow :
1. Crée une collection Anki éphémère dans un dossier temporaire
2. Login en tant que bot user (ankibot par défaut)
3. Sync depuis le serveur (récupère l'état actuel)
4. Importe le .apkg dans la collection — les GUIDs stables permettent à Anki
   de reconnaître les cartes existantes et de les mettre à jour au lieu de dupliquer
5. Sync vers le serveur (pousse les changements)
6. Cleanup automatique du dossier temporaire

Usage :
    export ANKI_BOT_PASSWORD="..."
    python3 scripts/sync-cards.py [--apkg wiki.apkg]

Configuration via variables d'environnement :
    ANKI_SYNC_URL        URL du serveur de sync (défaut: https://sync.jayrine.com/)
    ANKI_BOT_USER        utilisateur bot          (défaut: ankibot)
    ANKI_BOT_PASSWORD    mot de passe du bot      (REQUIS, pas de défaut)
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

try:
    from anki.collection import Collection
    from anki.import_export_pb2 import (
        ImportAnkiPackageRequest,
        ImportAnkiPackageOptions,
        ImportAnkiPackageUpdateCondition,
    )
    from anki.sync_pb2 import SyncCollectionResponse
except ImportError as e:
    sys.exit(
        f"[error] Dépendance manquante : {e.name}\n"
        f"        Installe les dépendances : pip install -r scripts/requirements.txt"
    )


# ----- Configuration par défaut -----

DEFAULT_SYNC_URL = "https://sync.jayrine.com/"
DEFAULT_USER = "ankibot"


# ----- Sync helpers -----

def _changes_required_name(value: int) -> str:
    """Nom lisible pour un statut SyncCollectionResponse.ChangesRequired."""
    return SyncCollectionResponse.ChangesRequired.Name(value)


def do_sync(col: Collection, auth, label: str) -> None:
    """
    Effectue un sync et gère les cas full_download / full_upload.

    Anki demande un pattern spécifique pour les full syncs :
        col.close_for_full_sync()
        col.full_upload_or_download(...)
        col.reopen(after_full_sync=True)
    """
    print(f"[sync] {label} : tentative...")
    output = col.sync_collection(auth, sync_media=True)
    required = output.required
    name = _changes_required_name(required)
    print(f"[sync] {label} : statut serveur = {name}")

    if required == SyncCollectionResponse.NO_CHANGES:
        return
    if required == SyncCollectionResponse.NORMAL_SYNC:
        # Anki a déjà appliqué le delta des deux côtés.
        return

    # Cas full sync : DOWNLOAD, UPLOAD, ou FULL_SYNC (les deux côtés ont changé)
    if required == SyncCollectionResponse.FULL_DOWNLOAD:
        upload = False
        print(f"[sync] {label} : full download depuis le serveur...")
    elif required == SyncCollectionResponse.FULL_UPLOAD:
        upload = True
        print(f"[sync] {label} : full upload vers le serveur...")
    elif required == SyncCollectionResponse.FULL_SYNC:
        # Conflit : changements des deux côtés. On préfère notre version
        # (le .apkg fraîchement importé) et on force le push.
        upload = True
        print(f"[sync] {label} : full sync (les deux côtés ont changé) → upload local")
    else:
        sys.exit(f"[error] Statut sync inconnu : {required} ({name})")

    col.close_for_full_sync()
    col.full_upload_or_download(
        auth=auth,
        server_usn=output.server_media_usn if hasattr(output, "server_media_usn") else None,
        upload=upload,
    )
    col.reopen(after_full_sync=True)
    print(f"[sync] {label} : terminé")


# ----- Import -----

def import_apkg(col: Collection, apkg_path: Path) -> None:
    """Importe le .apkg dans la collection avec update des notes existantes."""
    print(f"[import] Import de {apkg_path}...")

    options = ImportAnkiPackageOptions(
        merge_notetypes=True,
        update_notes=ImportAnkiPackageUpdateCondition.IMPORT_ANKI_PACKAGE_UPDATE_CONDITION_ALWAYS,
        update_notetypes=ImportAnkiPackageUpdateCondition.IMPORT_ANKI_PACKAGE_UPDATE_CONDITION_ALWAYS,
        with_scheduling=False,   # ne pas écraser la planification existante
        with_deck_configs=False, # ne pas écraser les options de deck existantes
    )
    req = ImportAnkiPackageRequest(
        package_path=str(apkg_path.resolve()),
        options=options,
    )
    result = col.import_anki_package(req)

    log = result.log
    print(f"[import] terminé :")
    print(f"          new         : {len(log.new)}")
    print(f"          updated     : {len(log.updated)}")
    print(f"          duplicate   : {len(log.duplicate)}")
    print(f"          conflicting : {len(log.conflicting)}")


# ----- Main -----

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--apkg",
        type=Path,
        default=Path("wiki.apkg"),
        help="Chemin du fichier .apkg à pousser (défaut: wiki.apkg)",
    )
    parser.add_argument(
        "--user",
        default=os.environ.get("ANKI_BOT_USER", DEFAULT_USER),
        help=f"Utilisateur bot (défaut: env ANKI_BOT_USER ou '{DEFAULT_USER}')",
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("ANKI_SYNC_URL", DEFAULT_SYNC_URL),
        help=f"URL du serveur de sync (défaut: env ANKI_SYNC_URL ou '{DEFAULT_SYNC_URL}')",
    )
    args = parser.parse_args()

    password = os.environ.get("ANKI_BOT_PASSWORD")
    if not password:
        sys.exit(
            "[error] ANKI_BOT_PASSWORD non défini dans l'environnement.\n"
            "        Utilisation : export ANKI_BOT_PASSWORD='...' avant de lancer le script."
        )

    if not args.apkg.is_file():
        sys.exit(f"[error] Fichier .apkg introuvable : {args.apkg}")

    print(f"[info] Endpoint  : {args.url}")
    print(f"[info] User      : {args.user}")
    print(f"[info] Package   : {args.apkg.resolve()}")
    print(f"[info] Taille    : {args.apkg.stat().st_size / 1024:.1f} KB")
    print()

    with tempfile.TemporaryDirectory(prefix="anki-bot-") as tmpdir:
        col_path = Path(tmpdir) / "collection.anki2"
        col = Collection(str(col_path))

        try:
            print(f"[auth] Login sur {args.url} en tant que '{args.user}'...")
            auth = col.sync_login(args.user, password, args.url)
            print(f"[auth] OK")
            print()

            # 1. Récupère l'état du serveur
            do_sync(col, auth, "Sync initial (récupération)")
            print()

            # 2. Importe le .apkg
            import_apkg(col, args.apkg)
            print()

            # 3. Pousse les changements
            do_sync(col, auth, "Sync final (push)")

        finally:
            try:
                col.close()
            except Exception:
                pass

    print()
    print("[ok] Sync terminé avec succès.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
