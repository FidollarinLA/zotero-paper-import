---
name: zotero-paper-import
description: >-
  Finds academic papers by title, DOI, or URL; downloads publisher or open-access
  PDFs; saves to a user-specified folder; imports metadata and PDF attachments
  into a local Zotero library with a named collection. Use when the user asks to
  find, download, or import papers, add references to Zotero, create a Zotero
  collection or folder, batch-import articles, or get the published PDF version.
---

# Zotero Paper Import

## Scope (v1)

- **In scope**: journal articles, conference papers, preprints (arXiv, etc.)
- **Out of scope**: books, book chapters, theses (defer to user or v2)
- **Platform**: local Zotero on macOS or Linux (`~/Zotero/zotero.sqlite`)

## Before starting

1. Read [config.example.md](config.example.md). If `config.md` exists, use those defaults.
2. Confirm with the user when unclear:
   - collection name (default: `Imported`)
   - download directory (default: `~/Documents/Zotero_Imports/{collection}/`)
   - PDF preference: `published` (default) or `any`
   - duplicate policy: `skip` (default), `replace`, or `new_copy`

## Workflow checklist

```
- [ ] Step 1: Resolve paper identifier (ask user if ambiguous)
- [ ] Step 2: Download and verify PDF
- [ ] Step 3: Handle paywall (ask user before fallback)
- [ ] Step 4: Ask user to quit Zotero, then import
- [ ] Step 5: Ask user to reopen Zotero and report results
```

### Step 1: Resolve identifier

Run `scripts/resolve_paper.py` with one of:

- `--doi 10.xxxx/...`
- `--url https://...`
- `--title "Paper title"`
- `--query "author year keywords"`

Output is JSON with `doi`, `title`, `authors`, `date`, `journal`, `url`, `abstract`.

If multiple matches, show top 3 and ask the user to pick.

### Step 2: Download PDF

Run `scripts/download_pdf.py`:

```bash
python3 scripts/download_pdf.py \
  --doi "<DOI>" \
  --output "<download_dir>/<short_name>.pdf" \
  --preference published
```

**PDF source priority** (see [reference.md](reference.md)):

1. Publisher reference PDF (e.g. Nature `*_reference.pdf`)
2. Unpaywall open-access publisher PDF
3. arXiv or other repository preprint (only if `preference=any` or user confirms)

**Always verify** the file is a real PDF:

```bash
file "<path>.pdf"   # must say "PDF document", not HTML
```

If only a preprint is available but the user asked for `published`, stop and ask.

### Step 3: Handle paywall

If publisher PDF returns HTML (paywall), **ask the user** to choose:

1. Use their own publisher or database account to download the PDF, then provide the path
2. Download the PDF themselves and provide the file path

Do not silently fall back to a preprint. Do not embed institution-specific proxy URLs.

After the user provides a valid PDF path, skip download and proceed to import.

### Step 4: Quit Zotero and import

**Tell the user why**: import writes directly to `~/Zotero/zotero.sqlite`. Zotero locks this file while running, so the user must quit Zotero before import.

```bash
pgrep -x zotero && osascript -e 'tell application "Zotero" to quit'  # macOS
# Linux: pkill zotero
sleep 2
```

Then import:

Single paper:

```bash
python3 scripts/import_to_zotero.py \
  --doi "<DOI>" \
  --pdf "<path>.pdf" \
  --collection "<collection_name>"
```

Batch (multiple papers):

```bash
python3 scripts/import_to_zotero.py \
  --manifest batch.json \
  --collection "<collection_name>"
```

`batch.json` format:

```json
[
  {"doi": "10.1038/...", "pdf": "/path/to/paper.pdf"},
  {"doi": "10.1145/...", "pdf": "/path/to/paper2.pdf"}
]
```

The script automatically backs up `zotero.sqlite` before writing.

### Step 5: Report and reopen

Tell the user:

- collection name (created or reused)
- local PDF path(s)
- PDF version (`published` / `preprint`)
- Zotero item title and DOI
- backup file path

Ask the user to reopen Zotero to view the imported items.

## Duplicate handling

Before import, check if DOI already exists:

```bash
sqlite3 ~/Zotero/zotero.sqlite \
  "SELECT v.value FROM itemData d
   JOIN itemDataValues v ON d.valueID=v.valueID
   JOIN fields f ON d.fieldID=f.fieldID
   WHERE f.fieldName='DOI' AND v.value='<DOI>';"
```

Respect the user's duplicate policy.

## Additional resources

- Usage examples: [examples.md](examples.md)
- PDF sources and Zotero fields: [reference.md](reference.md)
- User configuration template: [config.example.md](config.example.md)
