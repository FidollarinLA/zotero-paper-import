#!/usr/bin/env python3
"""Prepare a native RIS import; never write Zotero's database or storage."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from runtime import configure_stdio

from resolve_paper import arxiv_id, resolve_by_arxiv, resolve_by_doi, resolve_by_url


def normalize_identifier(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError('Paper identifiers must be strings')
    identifier = arxiv_id(value)
    if identifier:
        return 'arxiv:' + re.sub(r'v\d+$', '', identifier).lower()
    return re.sub(r'^https?://(?:dx\.)?doi\.org/', '', value.strip(), flags=re.I).lower()


def library_identifiers(db: Path) -> set[str]:
    """Use SQLite's read-only mode, including committed WAL data when present."""
    # sqlite3's context manager commits/rolls back but does not close the handle.
    # Explicit closure matters on Windows, where an open handle locks the file.
    with closing(sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)) as conn:
        rows = conn.execute('''SELECT v.value FROM itemData d
            JOIN itemDataValues v ON d.valueID=v.valueID
            JOIN fields f ON d.fieldID=f.fieldID
            JOIN items i ON i.itemID=d.itemID
            WHERE f.fieldName IN ('DOI','url','extra')
            AND i.itemID NOT IN (SELECT itemID FROM deletedItems)''')
        identifiers = set()
        for (value,) in rows:
            identifiers.add(normalize_identifier(value))
            for found in re.findall(r'arXiv:\s*((?:\d{4}\.\d{4,5}|[\w.-]+/\d{7})(?:v\d+)?)', value, re.I):
                identifiers.add(normalize_identifier(found))
        return identifiers


def validate_pdf(path: Path) -> None:
    if not path.is_file():
        raise ValueError(f'PDF not found: {path}')
    with path.open('rb') as stream:
        if b'%PDF-' not in stream.read(1024):
            raise ValueError(f'Not a PDF (possibly an HTML paywall): {path}')


def clean(value) -> str:
    return ' '.join(str(value or '').split())


def to_ris(meta: dict, pdf: Path) -> str:
    preprint = meta.get('source') == 'arxiv' or meta.get('item_type') == 'preprint'
    lines = ['TY  - ' + ('RPRT' if preprint else 'JOUR')]
    fields = [('TI', meta.get('title')), ('DO', meta.get('doi')),
              ('UR', meta.get('url')), ('AB', meta.get('abstract')),
              ('PY', meta.get('date') or meta.get('year')),
              ('JO', meta.get('journal')), ('VL', meta.get('volume')),
              ('IS', meta.get('issue')), ('SP', meta.get('pages'))]
    for tag, value in fields:
        if value:
            lines.append(f'{tag}  - {clean(value)}')
    authors = meta.get('authors') or []
    if not isinstance(authors, list) or any(not isinstance(author, dict) for author in authors):
        raise ValueError('authors must be an array of objects')
    for author in authors:
        name = ', '.join(filter(None, [clean(author.get('family')), clean(author.get('given'))]))
        if name:
            lines.append('AU  - ' + name)
    if preprint:
        lines.append('M3  - Preprint')
        lines.append('N1  - arXiv: ' + clean(meta.get('arxiv_id', '')))
    if meta.get('published_doi'):
        lines.append('N1  - Published DOI: ' + clean(meta['published_doi']))
    # Local attachment path is used by Zotero's RIS importer, never a remote URL.
    lines.extend(['L1  - ' + str(pdf), 'ER  - ', ''])
    return '\n'.join(lines)


def prepare(entries: list[dict], output: Path, collection: str,
            existing: set[str] | None = None, duplicate_policy: str = 'skip',
            base_dir: Path | None = None) -> dict:
    if not isinstance(entries, list) or not entries:
        raise ValueError('Manifest must be a non-empty array')
    existing = set(existing or ())
    seen = set()
    results, records = [], []
    for index, entry in enumerate(entries):
        try:
            if not isinstance(entry, dict):
                raise ValueError('Each entry must be an object')
            meta = entry.get('metadata')
            if meta is not None and not isinstance(meta, dict):
                raise ValueError('metadata must be an object')
            identifier = (meta or {}).get('doi') or (meta or {}).get('arxiv_id') or entry.get('doi') or entry.get('arxiv') or entry.get('url')
            identity = normalize_identifier(identifier or '')
            if not identity:
                raise ValueError('Provide doi, arxiv, url, or metadata with an identifier')
            if duplicate_policy == 'skip' and identity in existing | seen:
                results.append({'index': index, 'identifier': identifier, 'status': 'skipped', 'reason': 'duplicate'})
                continue
            pdf = Path(entry['pdf']).expanduser()
            if base_dir is not None and not pdf.is_absolute():
                pdf = base_dir / pdf
            pdf = pdf.resolve()
            if '\n' in str(pdf) or '\r' in str(pdf):
                raise ValueError('Attachment filename cannot contain a newline')
            validate_pdf(pdf)
            if meta is None:
                if arxiv_id(identifier):
                    meta = resolve_by_arxiv(identifier)
                elif entry.get('url'):
                    meta = resolve_by_url(identifier)
                else:
                    meta = resolve_by_doi(identifier)
            if not clean(meta.get('title')):
                raise ValueError('Metadata must include a title')
            resolved = normalize_identifier(meta.get('doi') or meta.get('arxiv_id') or meta.get('url', ''))
            if not resolved:
                raise ValueError('Resolved metadata has no identifier')
            if duplicate_policy == 'skip' and resolved in existing | seen:
                results.append({'index': index, 'identifier': identifier, 'status': 'skipped', 'reason': 'duplicate'})
                continue
            records.append(to_ris(meta, pdf))
            seen.update([identity, resolved])
            results.append({'index': index, 'identifier': identifier, 'status': 'prepared',
                            'title': meta['title'], 'pdf': str(pdf),
                            'sha256': pdf_hash(pdf)})
        except (ValueError, KeyError, TypeError, OSError, RuntimeError) as exc:
            results.append({'index': index, 'status': 'failed', 'reason': str(exc)})
    if records:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('\n'.join(records), encoding='utf-8')
    return {'status': 'prepared' if records else 'no_records', 'collection': collection,
            'ris': str(output) if records else None,
            'duplicate_check': 'library_and_batch' if existing else 'batch_only_or_empty_library',
            'results': results,
            'next_step': 'In Zotero: File > Import > A file. Select this RIS, copy attachments, then add the imported items to the target collection. Verify item count and PDFs before reporting success.'}


def pdf_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--doi')
    group.add_argument('--arxiv')
    group.add_argument('--url')
    group.add_argument('--manifest', type=Path)
    parser.add_argument('--pdf')
    parser.add_argument('--collection', default='Imported')
    parser.add_argument('--output', type=Path, default=Path('papers.ris'))
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--zotero-db', type=Path, default=Path.home() / 'Zotero/zotero.sqlite')
    parser.add_argument('--duplicate-policy', choices=['skip', 'new_copy'], default='skip')
    args = parser.parse_args()
    if not args.manifest and not ((args.doi or args.arxiv or args.url) and args.pdf):
        parser.error('Provide an identifier and --pdf, or --manifest')
    try:
        if args.manifest:
            args.manifest = args.manifest.expanduser().resolve()
        entries = json.loads(args.manifest.read_text(encoding='utf-8-sig')) if args.manifest else [
            {'doi': args.doi, 'arxiv': args.arxiv, 'url': args.url, 'pdf': args.pdf}]
        # Refuse to silently bypass a duplicate check if an existing DB cannot be read.
        existing = library_identifiers(args.zotero_db.expanduser()) if args.zotero_db.expanduser().exists() else set()
        report = prepare(entries, args.output.expanduser().resolve(), args.collection, existing,
                         args.duplicate_policy, args.manifest.parent if args.manifest else None)
        report['library_checked'] = args.zotero_db.expanduser().exists()
        if args.receipt:
            args.receipt = args.receipt.expanduser()
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if any(r['status'] == 'failed' for r in report['results']):
            sys.exit(1)
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
