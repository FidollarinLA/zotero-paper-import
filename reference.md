# Reference

## PDF download sources

| Priority | Source | URL pattern | Notes |
|----------|--------|-------------|-------|
| 1 | Nature / Springer reference PDF | `https://www.nature.com/articles/{slug}_reference.pdf` | Published layout; verify with `file` |
| 2 | Publisher direct PDF | `https://www.nature.com/articles/{slug}.pdf` | Often returns HTML paywall page |
| 3 | Unpaywall | `https://api.unpaywall.org/v2/{doi}?email={email}` | Requires valid email; check `best_oa_location.url_for_pdf` |
| 4 | arXiv | `https://arxiv.org/pdf/{id}.pdf` | Preprint only; ask user before using if `preference=published` |

### Verify download

```bash
file output.pdf
# Good: "PDF document, version 1.x"
# Bad:  "HTML document text"
```

Reject HTML responses. Delete the file and try the next source.

## Paywall handling

When all automated sources return HTML:

1. Ask the user to choose:
   - Log in with their own publisher/database account and download the PDF
   - Download the PDF themselves and provide the file path
2. Do not silently use a preprint when the user requested a published version
3. Do not hardcode institution-specific proxy URLs in this skill

## Why Zotero must be closed

The import script writes to `~/Zotero/zotero.sqlite`. Zotero locks this file while running. The correct sequence:

1. Ask user to quit Zotero
2. Backup database
3. Import metadata and PDF
4. Ask user to reopen Zotero

## Zotero SQLite constants

| Constant | Value | Meaning |
|----------|-------|---------|
| `ITEM_TYPE_JOURNAL` | 22 | Journal article |
| `ITEM_TYPE_ATTACHMENT` | 3 | File attachment |
| `CREATOR_TYPE_AUTHOR` | 8 | Author |
| `LINK_MODE_IMPORTED` | 0 | Imported file |
| `LIBRARY_ID` | 1 | Default local library |

## Collection behavior

- If collection name exists (case-sensitive match), reuse it.
- If not, create a new top-level collection.
- Sub-collections are not created in v1.

## Metadata sources

- Primary: CrossRef (`https://api.crossref.org/works/{doi}`)
- Fallback: Semantic Scholar API for title search

## Safety

- Always backup `zotero.sqlite` before import (`*.sqlite.bak.YYYYMMDD_HHMMSS`)
- Zotero must be closed during SQLite writes
- Never commit `config.md` with personal emails or paths
