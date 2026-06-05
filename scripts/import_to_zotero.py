#!/usr/bin/env python3
"""Import journal articles with PDF attachments into a local Zotero library."""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sqlite3
import string
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ZOTERO_DB = Path.home() / "Zotero" / "zotero.sqlite"
STORAGE_DIR = Path.home() / "Zotero" / "storage"
LIBRARY_ID = 1
ITEM_TYPE_JOURNAL = 22
ITEM_TYPE_ATTACHMENT = 3
CREATOR_TYPE_AUTHOR = 8
LINK_MODE_IMPORTED = 0


def now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def gen_key() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(8))


def ensure_zotero_closed() -> None:
    proc = subprocess.run(["pgrep", "-x", "zotero"], capture_output=True, text=True)
    if proc.returncode == 0:
        print("Error: Zotero is running. Please quit Zotero before importing.", file=sys.stderr)
        sys.exit(1)


def fetch_crossref(doi: str) -> dict:
    result = subprocess.run(
        ["curl", "-fsSL", f"https://api.crossref.org/works/{quote(doi, safe='')}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)["message"]


def get_or_create_value(conn: sqlite3.Connection, value: str) -> int:
    row = conn.execute("SELECT valueID FROM itemDataValues WHERE value = ?", (value,)).fetchone()
    if row:
        return row[0]
    cur = conn.execute("INSERT INTO itemDataValues (value) VALUES (?)", (value,))
    return cur.lastrowid


def set_field(conn: sqlite3.Connection, item_id: int, field_id: int, value: str) -> None:
    value_id = get_or_create_value(conn, value)
    conn.execute(
        "INSERT OR REPLACE INTO itemData (itemID, fieldID, valueID) VALUES (?, ?, ?)",
        (item_id, field_id, value_id),
    )


def get_or_create_creator(conn: sqlite3.Connection, first_name: str, last_name: str) -> int:
    row = conn.execute(
        "SELECT creatorID FROM creators WHERE firstName = ? AND lastName = ? AND fieldMode = 0",
        (first_name, last_name),
    ).fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO creators (firstName, lastName, fieldMode) VALUES (?, ?, 0)",
        (first_name, last_name),
    )
    return cur.lastrowid


def add_authors(conn: sqlite3.Connection, item_id: int, authors: list[dict]) -> None:
    for idx, author in enumerate(authors):
        creator_id = get_or_create_creator(conn, author.get("given", ""), author.get("family", ""))
        conn.execute(
            "INSERT INTO itemCreators (itemID, creatorID, creatorTypeID, orderIndex) VALUES (?, ?, ?, ?)",
            (item_id, creator_id, CREATOR_TYPE_AUTHOR, idx),
        )


def next_id(conn: sqlite3.Connection, table: str, column: str) -> int:
    row = conn.execute(f"SELECT MAX({column}) FROM {table}").fetchone()
    return (row[0] or 0) + 1


def find_collection(conn: sqlite3.Connection, name: str) -> int | None:
    row = conn.execute(
        "SELECT collectionID FROM collections WHERE collectionName = ? AND libraryID = ?",
        (name, LIBRARY_ID),
    ).fetchone()
    return row[0] if row else None


def get_or_create_collection(conn: sqlite3.Connection, name: str, ts: str) -> int:
    existing = find_collection(conn, name)
    if existing:
        return existing
    collection_id = next_id(conn, "collections", "collectionID")
    conn.execute(
        """
        INSERT INTO collections
        (collectionID, collectionName, parentCollectionID, clientDateModified, libraryID, key, version, synced)
        VALUES (?, ?, NULL, ?, ?, ?, 0, 0)
        """,
        (collection_id, name, ts, LIBRARY_ID, gen_key()),
    )
    return collection_id


def doi_exists(conn: sqlite3.Connection, doi: str, field_ids: dict) -> bool:
    if "DOI" not in field_ids:
        return False
    row = conn.execute(
        """
        SELECT 1 FROM itemData d
        JOIN itemDataValues v ON d.valueID = v.valueID
        WHERE d.fieldID = ? AND v.value = ?
        LIMIT 1
        """,
        (field_ids["DOI"], doi),
    ).fetchone()
    return row is not None


def zotero_filename(authors: list[dict], year: str, title: str) -> str:
    lead = authors[0].get("family", "Unknown") if authors else "Unknown"
    if authors and len(authors) > 1:
        lead += " et al."
    safe_title = title[:80].replace("/", "-")
    return f"{lead} - {year} - {safe_title}.pdf"


def import_one(
    conn: sqlite3.Connection,
    field_ids: dict[str, int],
    collection_id: int,
    doi: str,
    pdf_path: Path,
    ts: str,
    duplicate_policy: str,
) -> dict:
    if duplicate_policy == "skip" and doi_exists(conn, doi, field_ids):
        return {"doi": doi, "status": "skipped", "reason": "duplicate"}

    meta = fetch_crossref(doi)
    title = meta["title"][0]
    authors = meta.get("author", [])
    date_parts = (meta.get("published-print") or meta.get("published-online") or {}).get(
        "date-parts", [[None]]
    )[0]
    year = str(date_parts[0] or "0000")
    month = date_parts[1] if len(date_parts) > 1 else 1
    day = date_parts[2] if len(date_parts) > 2 else 1
    date_str = f"{year}-{int(month):02d}-{int(day) if day else 1:02d}"

    item_id = next_id(conn, "items", "itemID")
    item_key = gen_key()
    conn.execute(
        """
        INSERT INTO items
        (itemID, itemTypeID, dateAdded, dateModified, clientDateModified, libraryID, key, version, synced)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)
        """,
        (item_id, ITEM_TYPE_JOURNAL, ts, ts, ts, LIBRARY_ID, item_key),
    )

    journal = (meta.get("container-title") or [""])[0]
    fields = {
        "title": title,
        "publicationTitle": journal,
        "date": date_str,
        "DOI": doi,
        "url": meta.get("URL", f"https://doi.org/{doi}"),
        "libraryCatalog": "DOI.org (Crossref)",
        "accessDate": ts,
        "language": "en",
    }
    abstract = meta.get("abstract")
    if abstract:
        import re

        fields["abstractNote"] = re.sub(r"<[^>]+>", "", abstract)

    for name, value in fields.items():
        if name in field_ids and value:
            set_field(conn, item_id, field_ids[name], value)

    add_authors(conn, item_id, authors)
    conn.execute(
        "INSERT INTO collectionItems (collectionID, itemID) VALUES (?, ?)",
        (collection_id, item_id),
    )

    pdf_name = zotero_filename(authors, year, title)
    attach_id = next_id(conn, "items", "itemID")
    attach_key = gen_key()
    conn.execute(
        """
        INSERT INTO items
        (itemID, itemTypeID, dateAdded, dateModified, clientDateModified, libraryID, key, version, synced)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)
        """,
        (attach_id, ITEM_TYPE_ATTACHMENT, ts, ts, ts, LIBRARY_ID, attach_key),
    )
    set_field(conn, attach_id, field_ids["title"], pdf_name)

    storage_path = STORAGE_DIR / attach_key
    storage_path.mkdir(parents=True, exist_ok=True)
    dest_pdf = storage_path / pdf_name
    shutil.copy2(pdf_path, dest_pdf)

    conn.execute(
        """
        INSERT INTO itemAttachments
        (itemID, parentItemID, linkMode, contentType, path, syncState)
        VALUES (?, ?, ?, ?, ?, 0)
        """,
        (attach_id, item_id, LINK_MODE_IMPORTED, "application/pdf", f"storage:{pdf_name}"),
    )

    return {
        "doi": doi,
        "status": "imported",
        "title": title,
        "item_key": item_key,
        "pdf": str(dest_pdf),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import papers into Zotero")
    parser.add_argument("--doi")
    parser.add_argument("--pdf")
    parser.add_argument("--collection", default="Imported")
    parser.add_argument("--manifest", help="JSON file with [{doi, pdf}, ...]")
    parser.add_argument("--duplicate-policy", choices=["skip", "replace"], default="skip")
    parser.add_argument("--zotero-db", type=Path, default=ZOTERO_DB)
    args = parser.parse_args()

    if not args.manifest and not (args.doi and args.pdf):
        parser.error("Provide --doi and --pdf, or --manifest")

    if not args.zotero_db.exists():
        print(f"Error: Zotero database not found at {args.zotero_db}", file=sys.stderr)
        sys.exit(1)

    ensure_zotero_closed()

    entries: list[dict] = []
    if args.manifest:
        entries = json.loads(Path(args.manifest).read_text())
    else:
        entries = [{"doi": args.doi, "pdf": args.pdf}]

    backup = args.zotero_db.with_suffix(f".sqlite.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(args.zotero_db, backup)

    conn = sqlite3.connect(args.zotero_db)
    field_ids = {
        row[1]: row[0] for row in conn.execute("SELECT fieldID, fieldName FROM fields")
    }
    ts = now_ts()
    collection_id = get_or_create_collection(conn, args.collection, ts)

    results = []
    for entry in entries:
        pdf_path = Path(entry["pdf"]).expanduser().resolve()
        if not pdf_path.exists():
            results.append({"doi": entry["doi"], "status": "failed", "reason": f"PDF not found: {pdf_path}"})
            continue
        results.append(
            import_one(conn, field_ids, collection_id, entry["doi"], pdf_path, ts, args.duplicate_policy)
        )

    conn.commit()
    conn.close()

    print(json.dumps({"backup": str(backup), "collection": args.collection, "results": results}, indent=2))


if __name__ == "__main__":
    main()
